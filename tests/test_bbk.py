from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BBK = ROOT / "tools" / "bbk.py"
INSTALL = ROOT / "tools" / "install.py"
GENERATOR = ROOT / "tools" / "generate_agents.py"
ROUTING = ROOT / "spec" / "model-routing.json"


def run(command, *, cwd=None, env=None, check=True):
    return subprocess.run(
        [str(x) for x in command], cwd=str(cwd or ROOT), env=env,
        check=check, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace",
    )


def run_json(command, *, cwd=None, env=None, check=True):
    result = run(command, cwd=cwd, env=env, check=check)
    return json.loads(result.stdout), result


def parse_simple_yaml_frontmatter(path: Path):
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "---"
    end = lines.index("---", 1)
    data = {}
    key = None
    for line in lines[1:end]:
        if line.startswith("  - "):
            if key is None:
                raise AssertionError(f"orphan list item in {path}: {line}")
            raw = line[4:]
            try:
                value = json.loads(raw)
            except json.JSONDecodeError:
                value = raw
            data.setdefault(key, []).append(value)
            continue
        if not line.strip():
            continue
        if ":" not in line:
            raise AssertionError(f"invalid frontmatter line in {path}: {line}")
        key, raw = line.split(":", 1)
        key = key.strip(); raw = raw.strip()
        if raw == "":
            data[key] = []
        else:
            try:
                data[key] = json.loads(raw)
            except json.JSONDecodeError:
                if raw == "true": data[key] = True
                elif raw == "false": data[key] = False
                else: data[key] = raw
    return data


def make_test_profile(base: Path) -> Path:
    profile_root = base / "rust" / "0.0.0-test"
    (profile_root / "tools").mkdir(parents=True)
    resolver = profile_root / "tools" / "resolve.py"
    resolver.write_text(textwrap.dedent("""
        import argparse, hashlib, json
        p = argparse.ArgumentParser(); p.add_argument('--json', action='store_true')
        sub = p.add_subparsers(dest='command', required=True); r = sub.add_parser('resolve')
        r.add_argument('--root'); r.add_argument('--work-unit'); r.add_argument('--task-profile')
        r.add_argument('--assurance-tier'); r.add_argument('--role'); r.add_argument('--change-class', action='append')
        r.add_argument('--hint', action='append'); r.add_argument('--path', action='append'); r.add_argument('--run-tools', action='store_true')
        args = p.parse_args()
        payload = {'id':'rust','version':'0.0.0-test','root':args.root,'task':args.task_profile,'tier':args.assurance_tier,'role':args.role,'hints':args.hint or [],'paths':args.path or []}
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        lock = {'schema':'bbk.profile-lock.v1','generated_at':'2026-07-23T00:00:00Z','profiles':[payload],'effective_sha256':digest}
        print(json.dumps({'schema':'bbk.test-profile-resolution.v1','selected_components':[{'id':'test-rust'}],'effective_sha256':digest,'lock':lock}))
    """), encoding="utf-8")
    resolver.chmod(0o755)
    profile = {
        "schema": "bbk.language-profile.v1", "id": "rust", "name": "Test Rust",
        "package": "bbk-profile-rust-test", "version": "0.0.0-test", "maturity": "review-only",
        "authority": {"may_grant_tools_or_effects": False, "may_expand_work_scope": False, "may_reduce_assurance": False, "may_declare_pass": False},
        "entrypoints": {"resolve": ["{python}", "tools/resolve.py", "--json", "resolve"]},
        "skills": [],
    }
    (profile_root / "PROFILE.json").write_text(json.dumps(profile, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    records = []
    for path in sorted([profile_root / "PROFILE.json", resolver]):
        data = path.read_bytes(); rel = path.relative_to(profile_root).as_posix()
        records.append({"path": rel, "bytes": len(data), "sha256": __import__('hashlib').sha256(data).hexdigest(), "executable": bool(path.stat().st_mode & 0o111)})
    payload = {"schema":"bbk.profile-package-root.v1","name":"Test Rust","version":"0.0.0-test","files":records}
    root_digest = __import__('hashlib').sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    manifest = {"schema":"bbk.profile-package-manifest.v1","root_schema":"bbk.profile-package-root.v1","name":"Test Rust","profile_id":"rust","version":"0.0.0-test","file_count":len(records),"files":records,"root_sha256":root_digest}
    (profile_root / "PACKAGE-MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return profile_root


class BbkTests(unittest.TestCase):
    def test_agent_generation_and_counts(self):
        run([sys.executable, GENERATOR, "--check"])
        manifest = json.loads((ROOT / "projections" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["role_count"], 19)
        self.assertEqual(manifest["target_count"], 4)
        self.assertEqual(manifest["projection_count"], 76)
        self.assertEqual(manifest["model_profile_count"], 3)
        self.assertEqual(manifest["role_profile_counts"], {"coordination": 5, "judgment": 12, "mechanical": 2})
        self.assertEqual(manifest["targets"], ["claude", "codex", "generic", "omp"])
        for target in manifest["targets"]:
            self.assertEqual(len(list((ROOT / "projections" / target / "agents").glob("*"))), 19)

    def test_codex_toml_parses(self):
        routing = json.loads(ROUTING.read_text(encoding="utf-8"))
        for path in (ROOT / "projections" / "codex" / "agents").glob("*.toml"):
            value = tomllib.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(value["name"].startswith("bbk_"))
            self.assertTrue(value["model"])
            self.assertIn(value["model_reasoning_effort"], {"minimal", "low", "medium", "high", "xhigh", "max", "ultra"})
            self.assertIn("developer_instructions", value)
            profile = routing["role_profiles"][value["name"]]
            expected = routing["profiles"][profile]["codex"]
            self.assertEqual(value["model"], expected["model"])
            self.assertEqual(value["model_reasoning_effort"], expected["model_reasoning_effort"])

    def test_claude_frontmatter_and_containment(self):
        paths = list((ROOT / "projections" / "claude" / "agents").glob("*.md"))
        self.assertEqual(len(paths), 19)
        names = set()
        routing = json.loads(ROUTING.read_text(encoding="utf-8"))
        for path in paths:
            value = parse_simple_yaml_frontmatter(path)
            name = value["name"]
            self.assertRegex(name, r"^[a-z][a-z0-9-]*$")
            self.assertNotIn(name, names); names.add(name)
            canonical_name = name.replace("-", "_")
            profile = routing["role_profiles"][canonical_name]
            expected = routing["profiles"][profile]["claude"]
            self.assertEqual(value["model"], expected["model"])
            self.assertEqual(value["effort"], expected["effort"])
            self.assertEqual(value["permissionMode"], "default")
            self.assertTrue(value["description"])
            self.assertIn("Read", value["tools"])
            self.assertIn("Skill", value["tools"])
            self.assertTrue(value["skills"])
            if name in {"bbk-worker", "bbk-prototyper"}:
                self.assertEqual(value["isolation"], "worktree")
                self.assertIn("Edit", value["tools"])
                self.assertIn("Write", value["tools"])
            else:
                self.assertIn("Edit", value["disallowedTools"])
                self.assertIn("Write", value["disallowedTools"])
        root = parse_simple_yaml_frontmatter(ROOT / "projections" / "claude" / "agents" / "bbk-root-wayfinder.md")
        self.assertTrue(any(tool.startswith("Agent(") for tool in root["tools"]))
        self.assertIn("AskUserQuestion", root["tools"])

    def test_omp_extension_parses_and_registers(self):
        run(["node", "--check", ROOT / "omp" / "extension" / "index.js"])
        script = ROOT / "tests" / ".omp-mock.mjs"
        script.write_text(textwrap.dedent(f"""
            const chain = () => ({{ optional() {{ return this; }} }});
            const z = {{
              object: value => value,
              string: chain,
              boolean: chain,
              enum: values => chain(),
              array: value => chain(),
            }};
            const tools = [], commands = [], handlers = [];
            const pi = {{
              zod: {{ z }}, setLabel() {{}},
              registerTool(value) {{ tools.push(value); }},
              registerCommand(name, value) {{ commands.push([name, value]); }},
              on(name, value) {{ handlers.push([name, value]); }},
              sendMessage() {{}},
            }};
            const mod = await import({json.dumps((ROOT / 'omp' / 'extension' / 'index.js').as_uri())});
            mod.default(pi);
            if (tools.length !== 26) throw new Error(`tools=${{tools.length}}`);
            if (commands.length !== 27) throw new Error(`commands=${{commands.length}}`);
            if (!handlers.some(([n]) => n === 'tool_call')) throw new Error('missing tool_call');
            if (!handlers.some(([n]) => n === 'session_start')) throw new Error('missing session_start');
            if (!handlers.some(([n]) => n === 'before_agent_start')) throw new Error('missing before_agent_start');
            console.log(JSON.stringify({{tools: tools.map(x=>x.name), commands: commands.map(x=>x[0])}}));
        """), encoding="utf-8")
        try:
            result = run(["node", script])
            value = json.loads(result.stdout)
            self.assertIn("bbk_status", value["tools"])
            self.assertIn("bbk:gate", value["commands"])
            self.assertIn("bbk:models", value["commands"])
            self.assertIn("bbk:exit", value["commands"])
        finally:
            script.unlink(missing_ok=True)

    def test_installed_omp_extension_executes_copied_cli(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            home = base / "home"; home.mkdir()
            project = base / "project"; project.mkdir()
            env = os.environ.copy(); env.update({
                "BBK_HOME": str(home),
                "HOME": str(home),
                "BBK_INSTALL_ROOT": str(base / "data"),
                "BBK_BIN_DIR": str(base / "bin"),
            })
            run([sys.executable, BBK, "init", "--root", project, "--project-id", "TEST-INSTALLED-OMP"])
            installed, _ = run_json([sys.executable, INSTALL, "--json", "install", "--scope", "user", "--omp", "--no-language-profiles"], env=env)
            self.assertTrue(installed["omp"])
            extension = home / ".omp" / "agent" / "extensions" / "bbk" / "index.js"
            self.assertTrue((extension.parent / "VERSION").is_file())
            installed_package = Path(installed["package_root"])
            script = base / "installed-omp-mock.mjs"
            script.write_text(textwrap.dedent(f"""
                const chain = () => ({{ optional() {{ return this; }} }});
                const z = {{ object: value => value, string: chain, boolean: chain,
                  enum: values => chain(), array: value => chain() }};
                const tools = [], commands = [], handlers = [];
                const pi = {{ zod: {{ z }}, setLabel() {{}},
                  registerTool(value) {{ tools.push(value); }},
                  registerCommand(name, value) {{ commands.push([name, value]); }},
                  on(name, value) {{ handlers.push([name, value]); }}, sendMessage() {{}} }};
                const mod = await import({json.dumps(extension.as_uri())});
                mod.default(pi);
                const tool = tools.find(value => value.name === 'bbk_status');
                if (!tool) throw new Error('missing bbk_status');
                const result = await tool.execute('call-1', {{root: {json.dumps(str(project))}}}, undefined, undefined, {{cwd: {json.dumps(str(project))}}});
                if (result.isError || result.details?.schema !== 'bbk.status.v1')
                  throw new Error(JSON.stringify(result.details));
                const stateEffect = tools.find(value => value.name === 'bbk_state_effect_validate');
                const sde = await stateEffect.execute('call-2', {{path: {json.dumps(str(installed_package / 'fixtures' / 'state-effect' / 'contract-order.json'))}}}, undefined, undefined, {{cwd: {json.dumps(str(project))}}});
                if (sde.isError || sde.details?.kind !== 'state-decision-effect-design' || !sde.details?.valid)
                  throw new Error(JSON.stringify(sde.details));
                const review = tools.find(value => value.name === 'bbk_review_status');
                const rr = await review.execute('call-3', {{path: {json.dumps(str(installed_package / 'fixtures' / 'review' / 'run-pass.json'))}}}, undefined, undefined, {{cwd: {json.dumps(str(project))}}});
                if (rr.isError || rr.details?.kind !== 'review-run' || !rr.details?.valid)
                  throw new Error(JSON.stringify(rr.details));
                console.log(JSON.stringify({{schema: result.details.schema, tools: tools.length, sde: sde.details.kind, review: rr.details.kind}}));
            """), encoding="utf-8")
            value = json.loads(run(["node", script], env=env).stdout)
            self.assertEqual(value["schema"], "bbk.status.v1")
            self.assertEqual(value["sde"], "state-decision-effect-design")
            self.assertEqual(value["review"], "review-run")
            run([sys.executable, INSTALL, "uninstall", "--scope", "user"], env=env)
            self.assertTrue(home.exists())

    def test_manifest_distinguishes_semantic_and_byte_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source"; source.mkdir()
            (source / "data.json").write_text('{"a":1,"b":2}\n', encoding="utf-8")
            left, _ = run_json([sys.executable, BBK, "--json", "manifest", "create", "--source", source])
            (source / "data.json").write_text('{\n  "b": 2,\n  "a": 1\n}\n', encoding="utf-8")
            right, _ = run_json([sys.executable, BBK, "--json", "manifest", "create", "--source", source])
            left_path = Path(temp) / "left.json"; right_path = Path(temp) / "right.json"
            left_path.write_text(json.dumps(left), encoding="utf-8"); right_path.write_text(json.dumps(right), encoding="utf-8")
            comparison, _ = run_json([sys.executable, BBK, "--json", "manifest", "compare", "--left", left_path, "--right", right_path])
            self.assertFalse(comparison["equal"])
            self.assertEqual(comparison["summary"], {"semantic_equivalent_byte_change": 1})
            (source / "data.json").write_text('{"a":1,"b":3}\n', encoding="utf-8")
            changed, _ = run_json([sys.executable, BBK, "--json", "manifest", "create", "--source", source])
            changed_path = Path(temp) / "changed.json"; changed_path.write_text(json.dumps(changed), encoding="utf-8")
            comparison, _ = run_json([sys.executable, BBK, "--json", "manifest", "compare", "--left", left_path, "--right", changed_path])
            self.assertEqual(comparison["summary"], {"semantic_changed": 1})

    def test_candidate_staleness_and_gate_reuse(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "project"; root.mkdir()
            run([sys.executable, BBK, "init", "--root", root, "--project-id", "TEST-CANDIDATE"])
            (root / "subject.txt").write_text("one\n", encoding="utf-8")
            gates = {
                "schema": "bbk.gates.v1", "prevalidation": {"allow_empty": False},
                "gates": [{
                    "id": "focused", "enabled": True, "phases": ["prevalidate"],
                    "description": "focused pass", "command": [sys.executable, "-c", "print('ok')"],
                    "cwd": ".", "blocking": True, "requires": [Path(sys.executable).name],
                    "assertions": ["focused-pass"],
                }],
            }
            (root / ".bbk" / "gates.json").write_text(json.dumps(gates), encoding="utf-8")
            run([sys.executable, BBK, "candidate", "freeze", "--root", root, "--id", "C-001"])
            first, _ = run_json([sys.executable, BBK, "--json", "gate", "run", "--root", root, "--phase", "prevalidate", "--candidate", "C-001"])
            self.assertEqual(first["status"], "PASS")
            self.assertFalse(first["results"][0]["reused"])
            second, _ = run_json([sys.executable, BBK, "--json", "gate", "run", "--root", root, "--phase", "prevalidate", "--candidate", "C-001"])
            self.assertEqual(second["status"], "PASS")
            self.assertTrue(second["results"][0]["reused"])
            status, _ = run_json([sys.executable, BBK, "--json", "candidate", "status", "--root", root, "--id", "C-001"])
            self.assertTrue(status["state"]["validator_ready"])
            (root / "subject.txt").write_text("two\n", encoding="utf-8")
            checked, _ = run_json([sys.executable, BBK, "--json", "candidate", "check", "--root", root, "--id", "C-001"])
            self.assertFalse(checked["current"])
            self.assertFalse(checked["state"]["validator_ready"])

    def test_git_worktree_lifecycle(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repo"; root.mkdir()
            run(["git", "init", "-q"], cwd=root)
            run(["git", "config", "user.email", "bbk@example.invalid"], cwd=root)
            run(["git", "config", "user.name", "BBK Test"], cwd=root)
            (root / "README.md").write_text("test\n", encoding="utf-8")
            run(["git", "add", "README.md"], cwd=root); run(["git", "commit", "-qm", "initial"], cwd=root)
            run([sys.executable, BBK, "init", "--root", root, "--project-id", "TEST-WORKSPACE"])
            created, _ = run_json([sys.executable, BBK, "--json", "workspace", "create", "--root", root, "--id", "worker-1"])
            worktree = Path(created["workspace"]["path"])
            self.assertTrue(worktree.is_dir())
            inspected, _ = run_json([sys.executable, BBK, "--json", "workspace", "inspect", "--root", root, "--id", "worker-1"])
            self.assertTrue(inspected["inspection"]["exists"])
            removed, _ = run_json([sys.executable, BBK, "--json", "workspace", "cleanup", "--root", root, "--id", "worker-1", "--delete-branch"])
            self.assertEqual(removed["status"], "REMOVED")
            self.assertFalse(worktree.exists())

    def test_beads_projection_is_dry_run(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "project"; root.mkdir()
            run([sys.executable, BBK, "init", "--root", root, "--project-id", "TEST-BEADS"])
            project_map = json.loads((root / ".bbk" / "map.json").read_text(encoding="utf-8"))
            project_map["territories"] = [{"id": "T-1", "name": "Core"}]
            project_map["questions"] = [{"id": "Q-1", "title": "Choose storage", "territory_id": "T-1"}]
            (root / ".bbk" / "map.json").write_text(json.dumps(project_map), encoding="utf-8")
            value, _ = run_json([sys.executable, BBK, "--json", "beads", "plan", "--root", root])
            self.assertTrue(value["dry_run"])
            self.assertFalse(value["write_enabled"])
            self.assertEqual(len(value["operations"]), 3)

    def test_user_install_all_targets_and_uninstall(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp) / "home"; home.mkdir()
            env = os.environ.copy(); env.update({"BBK_HOME": str(home), "HOME": str(home), "BBK_INSTALL_ROOT": str(home / "data"), "BBK_BIN_DIR": str(home / "bin")})
            installed, _ = run_json([sys.executable, INSTALL, "--json", "install", "--scope", "user", "--no-language-profiles"], env=env)
            self.assertTrue(installed["codex"] and installed["omp"] and installed["claude"] and installed["generic"])
            self.assertEqual(len(list((home / ".claude" / "agents").glob("*.md"))), 19)
            self.assertEqual(len(list((home / ".claude" / "skills").glob("*/SKILL.md"))), 21)
            self.assertEqual(len(list((home / ".codex" / "agents").glob("*.toml"))), 19)
            registry = (home / ".agents" / "skills" / "bbk-installed-profiles" / "SKILL.md").read_text(encoding="utf-8")
            self.assertEqual(installed["language_profiles"], [])
            self.assertEqual(installed["language_profile_source_mode"], "disabled")
            self.assertEqual(installed["language_profile_registry"]["profile_count"], 0)
            self.assertIn("No language or domain profile is managed", registry)
            self.assertEqual(len(list((home / ".agents" / "bbk" / "agents").glob("*.md"))), 19)
            status, _ = run_json([sys.executable, INSTALL, "--json", "status", "--scope", "user"], env=env)
            self.assertTrue(status["installed"])
            self.assertEqual(status["summary"].get("current"), len(status["files"]))
            run([sys.executable, INSTALL, "uninstall", "--scope", "user"], env=env)
            self.assertTrue(home.exists())
            self.assertFalse((home / "data" / "install-manifest.json").exists())

    def test_project_all_targets_dry_run_does_not_require_staged_copy(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"; project.mkdir()
            value, _ = run_json([sys.executable, INSTALL, "--json", "install", "--scope", "project", "--root", project, "--dry-run", "--no-language-profiles"])
            self.assertTrue(value["codex"] and value["omp"] and value["claude"] and value["generic"])
            self.assertTrue(any(item["path"].endswith(".omp/extensions/bbk/bbk.py") for item in value["files"]))
            self.assertFalse((project / ".bbk-kit").exists())

    def test_project_claude_only_install_preserves_root(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"; project.mkdir()
            installed, _ = run_json([sys.executable, INSTALL, "--json", "install", "--scope", "project", "--root", project, "--claude", "--no-language-profiles"])
            self.assertFalse(installed["codex"]); self.assertFalse(installed["omp"]); self.assertTrue(installed["claude"])
            self.assertEqual(len(list((project / ".claude" / "agents").glob("*.md"))), 19)
            self.assertFalse((project / ".codex" / "agents").exists())
            run([sys.executable, INSTALL, "uninstall", "--scope", "project", "--root", project])
            self.assertTrue(project.exists())
            self.assertFalse((project / ".bbk-kit-install.json").exists())

    def test_profile_discovery_resolution_lock_and_extra_file_rejection(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            project = temp_root / "project"; project.mkdir()
            run([sys.executable, BBK, "init", "--root", project, "--project-id", "TEST-PROFILE"])
            profile_base = temp_root / "profiles"
            profile_root = make_test_profile(profile_base)
            listed, _ = run_json([sys.executable, BBK, "--json", "profile", "list", "--root", project, "--profile-dir", profile_base])
            self.assertEqual(len(listed["profiles"]), 1)
            self.assertEqual(listed["profiles"][0]["package_verification"]["status"], "PASS")
            inspected, _ = run_json([sys.executable, BBK, "--json", "profile", "inspect", "--root", project, "--profile-dir", profile_base, "--id", "rust"])
            self.assertEqual(inspected["version"], "0.0.0-test")
            resolved, _ = run_json([sys.executable, BBK, "--json", "profile", "resolve", "--root", project, "--source", project, "--profile-dir", profile_base, "--id", "rust", "--role", "worker", "--task-profile", "implementation", "--assurance-tier", "routine", "--hint", "public-api", "--path", "src/lib.rs", "--write-lock"])
            self.assertEqual(resolved["resolution"]["selected_components"][0]["id"], "test-rust")
            lock = json.loads((project / ".bbk" / "profile-lock.json").read_text(encoding="utf-8"))
            self.assertRegex(lock["effective_sha256"], r"^[0-9a-f]{64}$")
            (profile_root / "unexpected.txt").write_text("drift\n", encoding="utf-8")
            drifted, _ = run_json([sys.executable, BBK, "--json", "profile", "inspect", "--root", project, "--profile-dir", profile_base, "--id", "rust"])
            self.assertEqual(drifted["package_verification"]["status"], "FAIL")
            self.assertTrue(any("unexpected" in error for error in drifted["package_verification"]["errors"]))

    def test_init_creates_empty_profile_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "project"; root.mkdir()
            run([sys.executable, BBK, "init", "--root", root, "--project-id", "TEST-LOCK"])
            value = json.loads((root / ".bbk" / "profile-lock.json").read_text(encoding="utf-8"))
            self.assertEqual(value["schema"], "bbk.profile-lock.v1")
            self.assertIsNone(value["generated_at"])
            self.assertEqual(value["profiles"], [])
            self.assertIsNone(value["effective_sha256"])


if __name__ == "__main__":
    unittest.main()
