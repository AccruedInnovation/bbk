from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import types
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import install as install_tool
import install_profiles
import profile_install
import profile_registry
import run_tests
import setup as setup_tool
import verify_all


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _write_profile_package(base: Path, *, profile_id: str = "sample") -> Path:
    """Create one small, fully manifested installable profile package."""
    version = "0.1.0-alpha.3"
    package_name = f"bbk-profile-{profile_id}"
    root = base / f"{package_name}-{version}"
    (root / "tools").mkdir(parents=True)
    (root / "skills" / profile_id).mkdir(parents=True)
    (root / "omp" / "extension").mkdir(parents=True)

    source_profile = json.loads((ROOT / "fixtures" / "profiles" / "alpha8" / "PROFILE.json").read_text(encoding="utf-8"))
    source_profile.update({
        "id": profile_id,
        "name": f"Sample {profile_id} profile",
        "package": package_name,
        "version": version,
        "maturity": "qualified-fixture",
        "requires": {"bbk_minimum": "0.1.0-alpha.8", "python_minimum": "3.10"},
        "installation": {
            "cli": "tools/profile.py",
            "skill_root": "skills",
            "omp_extension": "omp/extension",
        },
        "skills": [
            {"id": profile_id, "kind": "router", "path": f"skills/{profile_id}/SKILL.md"},
        ],
    })
    (root / "PROFILE.json").write_text(json.dumps(source_profile, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / "VERSION").write_text(version + "\n", encoding="utf-8")
    cli = root / "tools" / "profile.py"
    cli.write_text("#!/usr/bin/env python3\nimport json\nprint(json.dumps({'status':'PASS'}))\n", encoding="utf-8")
    cli.chmod(0o755)
    (root / "skills" / profile_id / "SKILL.md").write_text(
        f"---\nname: {profile_id}\ndescription: Sample profile skill.\n---\n\n# Sample profile\n",
        encoding="utf-8",
    )
    (root / "omp" / "extension" / "index.js").write_text(
        "export default function sampleProfile(pi) { pi.setLabel?.('sample-profile'); }\n",
        encoding="utf-8",
    )
    (root / "omp" / "extension" / "package.json").write_text(
        json.dumps({"name": package_name, "version": version, "type": "module"}, indent=2) + "\n",
        encoding="utf-8",
    )
    (root / "omp" / "extension" / "README.md").write_text("# Sample profile extension\n", encoding="utf-8")

    records = []
    for path in sorted((candidate for candidate in root.rglob("*") if candidate.is_file()), key=lambda value: value.relative_to(root).as_posix()):
        data = path.read_bytes()
        records.append({
            "path": path.relative_to(root).as_posix(),
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "executable": bool(path.stat().st_mode & 0o111),
        })
    payload = {
        "schema": "bbk.profile-package-root.v1",
        "name": package_name,
        "version": version,
        "files": records,
    }
    manifest = {
        "schema": "bbk.profile-package-manifest.v1",
        "root_schema": "bbk.profile-package-root.v1",
        "name": package_name,
        "profile_id": profile_id,
        "version": version,
        "file_count": len(records),
        "files": records,
        "root_sha256": hashlib.sha256(_canonical(payload)).hexdigest(),
    }
    (root / "PACKAGE-MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return root


def _write_profile_bundle(base: Path, *, profile_id: str = "sample") -> Path:
    package_root = _write_profile_package(base / "source", profile_id=profile_id)
    bundle_root = base / "bundle-root"
    packages = bundle_root / "packages"
    packages.mkdir(parents=True)
    package_zip = packages / f"{package_root.name}.zip"
    with zipfile.ZipFile(package_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((candidate for candidate in package_root.rglob("*") if candidate.is_file()), key=lambda value: value.relative_to(package_root.parent).as_posix()):
            archive.write(path, path.relative_to(package_root.parent).as_posix())
    record = {
        "path": package_zip.relative_to(bundle_root).as_posix(),
        "bytes": package_zip.stat().st_size,
        "sha256": hashlib.sha256(package_zip.read_bytes()).hexdigest(),
    }
    release = {
        "schema": "bbk.language-profiles-release-bundle-manifest.v1",
        "status": "PASS",
        "fileCount": 1,
        "files": [record],
    }
    (bundle_root / "RELEASE-MANIFEST.json").write_text(json.dumps(release, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    bundle_zip = base / "profiles.zip"
    with zipfile.ZipFile(bundle_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((candidate for candidate in bundle_root.rglob("*") if candidate.is_file()), key=lambda value: value.relative_to(bundle_root.parent).as_posix()):
            archive.write(path, path.relative_to(bundle_root.parent).as_posix())
    return bundle_zip


class Alpha101EntrySetupTests(unittest.TestCase):
    def test_version_and_canonical_inputs_agree(self):
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(version, "0.1.0-alpha.11.7")
        self.assertEqual(json.loads((ROOT / "spec" / "roles.json").read_text(encoding="utf-8"))["package_version"], version)
        self.assertEqual(json.loads((ROOT / "spec" / "model-routing.json").read_text(encoding="utf-8"))["package_version"], version)
        self.assertEqual(json.loads((ROOT / "spec" / "method-content.json").read_text(encoding="utf-8"))["version"], version)
        self.assertEqual(json.loads((ROOT / "spec" / "blueprint-alignment.json").read_text(encoding="utf-8"))["bbkVersion"], version)
        self.assertEqual(json.loads((ROOT / "omp" / "extension" / "package.json").read_text(encoding="utf-8"))["version"], version)

    def test_installed_profile_source_skill_is_a_generated_placeholder(self):
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        rendered = (ROOT / "shared" / "skills" / "bbk-installed-profiles" / "SKILL.md").read_text(encoding="utf-8")
        self.assertEqual(rendered, profile_registry.source_placeholder_skill(bbk_version=version))
        self.assertIn("package-source placeholder", rendered)
        self.assertIn("No language or domain profile is managed", rendered)

    def test_baseline_skill_is_an_entry_controller_without_recursive_rerouting(self):
        canonical = json.loads((ROOT / "spec" / "method-content.json").read_text(encoding="utf-8"))["skills"]["bbk"]
        rendered = (ROOT / "shared" / "skills" / "bbk" / "SKILL.md").read_text(encoding="utf-8")
        self.assertEqual(canonical, rendered)
        self.assertEqual(rendered.count("## Entrypoint responsibility"), 1)
        for value in (
            "BBK entry controller",
            "bbk_root_wayfinder",
            "bbk_root_orchestrator",
            "bbk_reviewer",
            "bbk_validator_orchestrator",
            "named BBK agents",
            "do not perform entrypoint routing again",
        ):
            self.assertIn(value, rendered)
        self.assertIn("baseline itself is invalid", rendered)

    @unittest.skipUnless(shutil.which("node"), "Node.js is required for OMP extension behavior")
    def test_omp_bbk_command_enters_persistent_mode_and_keeps_status_command(self):
        with tempfile.TemporaryDirectory() as temp:
            script = Path(temp) / "omp-entrypoint.mjs"
            script.write_text(textwrap.dedent(f"""
                const chain = () => ({{ optional() {{ return this; }} }});
                const z = {{ object: value => value, string: chain, boolean: chain,
                  enum: values => chain(), array: value => chain() }};
                const tools = [], commands = new Map(), messages = [], handlers = new Map(), entries = [], statuses = [];
                const branch = [];
                const pi = {{ zod: {{ z }}, setLabel() {{}},
                  registerTool(value) {{ tools.push(value); }},
                  registerCommand(name, value) {{ commands.set(name, value); }},
                  on(name, value) {{ if (!handlers.has(name)) handlers.set(name, []); handlers.get(name).push(value); }},
                  appendEntry(customType, data) {{ entries.push([customType, data]); branch.push({{type:'custom', customType, data}}); }},
                  async sendUserMessage(value, options) {{ messages.push([value, options || null]); }}
                }};
                const ctx = {{
                  cwd: {json.dumps(str(ROOT))}, isIdle() {{ return true; }},
                  sessionManager: {{ getBranch() {{ return branch; }} }},
                  ui: {{ notify() {{}}, setStatus(key, value) {{ statuses.push([key, value ?? null]); }} }}
                }};
                const mod = await import({json.dumps((ROOT / 'omp' / 'extension' / 'index.js').as_uri())});
                mod.default(pi);
                if (commands.size !== 27) throw new Error(`commands=${{commands.size}}`);
                if (!commands.has('bbk') || !commands.has('bbk:status') || !commands.has('bbk:exit')) throw new Error('missing BBK commands');
                const entered = await commands.get('bbk').handler('', ctx);
                if (entered !== undefined) throw new Error(`unexpected command payload: ${{JSON.stringify(entered)}}`);
                if (messages.length !== 0) throw new Error(`no-argument /bbk started a model turn`);
                if (entries.length !== 1 || entries[0][1].enabled !== true) throw new Error('mode was not persisted');
                const before = handlers.get('before_agent_start')?.[0];
                if (!before) throw new Error('missing before_agent_start');
                const overlay = await before({{systemPrompt:['base']}}, ctx);
                const joined = overlay.systemPrompt.join(String.fromCharCode(10));
                for (const expected of ['<bbk-session-mode>', 'bbk_root_wayfinder', 'bbk_root_orchestrator',
                  'bbk_reviewer', 'bbk_validator_orchestrator', '/bbk:exit']) {{
                  if (!joined.includes(expected)) throw new Error(`missing ${{expected}}`);
                }}
                await commands.get('bbk').handler('Implement the accepted baseline', ctx);
                if (messages.length !== 1 || messages[0][0] !== 'Implement the accepted baseline') throw new Error('request was not forwarded verbatim');
                if (messages[0][0].includes('bbk_root_wayfinder')) throw new Error('mode prompt leaked into user message');
                console.log(JSON.stringify({{commands: commands.size, messages: messages.length, entries: entries.length, overlayLength: joined.length}}));
            """), encoding="utf-8")
            result = subprocess.run(
                [shutil.which("node") or "node", script], cwd=ROOT,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                encoding="utf-8", errors="replace", check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            value = json.loads(result.stdout)
            self.assertEqual(value["commands"], 27)
            self.assertEqual(value["messages"], 1)
            self.assertEqual(value["entries"], 1)

    def test_run_tests_all_delegates_to_the_ordered_verification_pipeline(self):
        calls: list[dict[str, object]] = []
        fake = types.ModuleType("verify_all")

        def fake_run_all(**kwargs: object) -> int:
            calls.append(kwargs)
            return 7

        fake.run_all = fake_run_all  # type: ignore[attr-defined]
        with mock.patch.dict(sys.modules, {"verify_all": fake}):
            result = run_tests.main(["--all", "--failfast", "--require-node"])
        self.assertEqual(result, 7)
        self.assertEqual(calls, [{"failfast": True, "require_node": True, "skip_package_manifest": False}])
        files = run_tests.matching_test_files("test*.py")
        self.assertEqual(files, sorted(files))

    def test_verification_pipeline_has_trust_gate_generators_tests_and_post_check(self):
        with mock.patch.object(verify_all.shutil, "which", return_value="node"):
            steps = verify_all.verification_steps(require_node=True)
        names = [step.name for step in steps]
        self.assertEqual(names[0], "Package manifest integrity (pre-execution trust gate)")
        self.assertTrue(steps[0].trust_gate)
        self.assertIn("Method-content projection drift", names)
        self.assertIn("Agent projection drift", names)
        self.assertIn("Python compilation and JSON parsing", names)
        self.assertIn("All unittest suites", names)
        self.assertIn("OMP extension JavaScript syntax", names)
        self.assertEqual(names[-1], "Package manifest integrity (post-test mutation check)")
        unittest_step = next(step for step in steps if step.name == "All unittest suites")
        self.assertEqual(unittest_step.command[-1], "-v")

    def test_setup_exposes_requested_test_and_install_flags(self):
        parser = setup_tool.build_parser()
        test = parser.parse_args(["--test"])
        self.assertTrue(test.test)
        combined = parser.parse_args([
            "--test-and-install", "--scope", "project", "--root", "/tmp/project",
            "--omp", "--language-profiles", "profiles.zip", "--profile-id", "rust",
        ])
        self.assertTrue(combined.test_and_install)
        values = setup_tool.install_arguments(combined)
        self.assertIn("--verify", values)
        self.assertIn("--language-profiles", values)
        self.assertIn("profiles.zip", values)
        self.assertIn("--profile-id", values)
        self.assertIn("rust", values)

    def test_profile_zip_extraction_rejects_traversal_and_symlinks(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            traversal = base / "traversal.zip"
            with zipfile.ZipFile(traversal, "w") as archive:
                archive.writestr("../escape.txt", "bad")
            with self.assertRaises(profile_install.ProfileInstallError):
                profile_install.safe_extract_zip(traversal, base / "out-traversal")

            symlink = base / "symlink.zip"
            info = zipfile.ZipInfo("profile/link")
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            with zipfile.ZipFile(symlink, "w") as archive:
                archive.writestr(info, "target")
            with self.assertRaises(profile_install.ProfileInstallError):
                profile_install.safe_extract_zip(symlink, base / "out-symlink")

    def test_profile_zip_rejects_portable_collisions_and_windows_unsafe_names(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            collision = base / "collision.zip"
            with zipfile.ZipFile(collision, "w") as archive:
                archive.writestr("profile/Skill.md", "one")
                archive.writestr("profile/skill.md", "two")
            with self.assertRaises(profile_install.ProfileInstallError):
                profile_install.safe_extract_zip(collision, base / "out-collision")

            for number, name in enumerate(("profile/data.txt:stream", "profile/CON.txt", "profile/trailing. ")):
                unsafe = base / f"unsafe-{number}.zip"
                with zipfile.ZipFile(unsafe, "w") as archive:
                    archive.writestr(name, "bad")
                with self.assertRaises(profile_install.ProfileInstallError):
                    profile_install.safe_extract_zip(unsafe, base / f"out-{number}")

    def test_release_bundle_manifest_requires_qualified_schema_and_exact_inventory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "packages").mkdir()
            payload = root / "packages" / "profile.zip"
            payload.write_bytes(b"profile")
            import hashlib
            manifest = {
                "schema": "bbk.language-profiles-release-bundle-manifest.v1",
                "status": "PASS",
                "fileCount": 1,
                "files": [{
                    "path": "packages/profile.zip",
                    "bytes": payload.stat().st_size,
                    "sha256": hashlib.sha256(payload.read_bytes()).hexdigest(),
                }],
            }
            (root / "RELEASE-MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
            self.assertEqual(profile_install.verify_bundle_manifest(root)["status"], "PASS")
            manifest["status"] = "FAIL"
            (root / "RELEASE-MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaises(profile_install.ProfileInstallError):
                profile_install.verify_bundle_manifest(root)

    def test_install_preflight_rejects_duplicate_destination_ownership(self):
        with self.assertRaises(install_tool.InstallError):
            install_tool.validate_install_plan({
                "files": [
                    {"path": "C:/tmp/shared.md", "sha256": "a", "source": "one"},
                    {"path": "c:\\tmp\\shared.md", "sha256": "b", "source": "two"},
                ]
            })

    def test_install_parser_accepts_verification_and_profile_bundle_flags(self):
        args = install_tool.build_parser().parse_args([
            "install", "--scope", "user", "--omp", "--verify",
            "--language-profiles", "profiles.zip", "--profile-id", "python",
        ])
        self.assertTrue(args.verify)
        self.assertTrue(args.omp)
        self.assertEqual(args.language_profiles, ["profiles.zip"])
        self.assertEqual(args.profile_id, ["python"])

    def test_profile_bundle_installs_with_core_in_one_manifest_and_uninstalls(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            bundle = _write_profile_bundle(base)
            env = os.environ.copy()
            env.update({
                "BBK_HOME": str(base / "home"),
                "BBK_INSTALL_ROOT": str(base / "data"),
                "BBK_BIN_DIR": str(base / "bin"),
            })
            command = [
                sys.executable, str(ROOT / "tools" / "install.py"), "--json", "install",
                "--scope", "user", "--codex", "--omp",
                "--language-profiles", str(bundle),
            ]
            dry = subprocess.run(
                [*command, "--dry-run"], cwd=ROOT, env=env, check=False,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
            )
            self.assertEqual(dry.returncode, 0, dry.stderr or dry.stdout)
            dry_value = json.loads(dry.stdout)
            self.assertEqual([item["id"] for item in dry_value["language_profiles"]], ["sample"])
            self.assertEqual(dry_value["language_profiles"][0]["router_skill"], "sample")
            self.assertEqual(dry_value["language_profile_registry"]["profile_count"], 1)
            self.assertFalse((base / "data").exists())
            self.assertFalse(Path(dry_value["manifest_path"]).exists())
            self.assertTrue(any(str(item.get("source", "")).startswith("profile:sample@") for item in dry_value["files"]))
            self.assertTrue(any(item.get("source") == "generated:installed-profile-registry-skill" for item in dry_value["files"]))

            installed = subprocess.run(
                command, cwd=ROOT, env=env, check=False,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
            )
            self.assertEqual(installed.returncode, 0, installed.stderr or installed.stdout)
            value = json.loads(installed.stdout)
            self.assertEqual(value["schema"], "bbk.install-manifest.v1")
            self.assertEqual(len(value["language_profiles"]), 1)
            self.assertTrue(Path(value["manifest_path"]).is_file())
            self.assertTrue((base / "data" / "profiles" / "sample" / "current.json").is_file())
            self.assertTrue((base / "home" / ".agents" / "skills" / "sample" / "SKILL.md").is_file())
            registry_path = base / "home" / ".agents" / "skills" / "bbk-installed-profiles" / "SKILL.md"
            self.assertTrue(registry_path.is_file())
            registry_text = registry_path.read_text(encoding="utf-8")
            self.assertIn("### `sample@0.1.0-alpha.3`", registry_text)
            self.assertIn("Router skill: `sample`", registry_text)
            self.assertNotIn("package-source placeholder", registry_text)
            effective_registry = json.loads((base / "data" / "effective-language-profiles.json").read_text(encoding="utf-8"))
            self.assertEqual([item["id"] for item in effective_registry["profiles"]], ["sample"])
            self.assertTrue((base / "home" / ".omp" / "agent" / "extensions" / "bbk-profile-sample" / "index.js").is_file())
            self.assertTrue((base / "bin" / ("profile.cmd" if os.name == "nt" else "profile")).is_file())
            registry_skill = base / "home" / ".agents" / "skills" / "bbk-installed-profiles" / "SKILL.md"
            self.assertTrue(registry_skill.is_file())
            registry_text = registry_skill.read_text(encoding="utf-8")
            self.assertIn("`sample@0.1.0-alpha.3`", registry_text)
            self.assertIn("Router skill: `sample`", registry_text)
            self.assertIn("bbk --json profile list", registry_text)
            self.assertNotIn("package-source placeholder", registry_text)
            effective_profiles = json.loads((base / "data" / "effective-language-profiles.json").read_text(encoding="utf-8"))
            self.assertEqual(effective_profiles["schema"], "bbk.installed-profile-registry.v1")
            self.assertEqual(effective_profiles["profiles"][0]["router_skill"], "sample")
            self.assertEqual(effective_profiles["profiles"][0]["skills"][0]["kind"], "router")
            self.assertEqual(value["language_profile_registry"]["profile_count"], 1)
            self.assertEqual(value["language_profile_registry"]["skill"], "bbk-installed-profiles")

            status = subprocess.run(
                [sys.executable, str(ROOT / "tools" / "install.py"), "--json", "status", "--scope", "user"],
                cwd=ROOT, env=env, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace",
            )
            self.assertEqual(status.returncode, 0, status.stderr or status.stdout)
            status_value = json.loads(status.stdout)
            self.assertEqual(status_value["summary"].get("current"), len(status_value["files"]))
            self.assertEqual([item["id"] for item in status_value["language_profiles"]], ["sample"])
            self.assertEqual(status_value["language_profile_registry"]["profile_count"], 1)

            removed = subprocess.run(
                [sys.executable, str(ROOT / "tools" / "install.py"), "--json", "uninstall", "--scope", "user"],
                cwd=ROOT, env=env, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace",
            )
            self.assertEqual(removed.returncode, 0, removed.stderr or removed.stdout)
            self.assertFalse((base / "data" / "install-manifest.json").exists())
            self.assertFalse((base / "home" / ".agents" / "skills" / "sample" / "SKILL.md").exists())
            self.assertFalse((base / "home" / ".agents" / "skills" / "bbk-installed-profiles" / "SKILL.md").exists())
            self.assertFalse((base / "home" / ".agents" / "skills" / "bbk-installed-profiles" / "SKILL.md").exists())

    def test_bundle_outer_pass_does_not_hide_tampered_inner_profile(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            bundle = _write_profile_bundle(base)
            extracted = base / "extracted"
            profile_install.safe_extract_zip(bundle, extracted)
            bundle_root = next(path.parent for path in extracted.rglob("RELEASE-MANIFEST.json"))
            package_zip = next((bundle_root / "packages").glob("*.zip"))
            with zipfile.ZipFile(package_zip, "a") as archive:
                archive.writestr("bbk-profile-sample-0.1.0-alpha.3/unexpected.txt", "tampered")
            release = json.loads((bundle_root / "RELEASE-MANIFEST.json").read_text(encoding="utf-8"))
            release["files"][0]["bytes"] = package_zip.stat().st_size
            release["files"][0]["sha256"] = hashlib.sha256(package_zip.read_bytes()).hexdigest()
            (bundle_root / "RELEASE-MANIFEST.json").write_text(json.dumps(release, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            with tempfile.TemporaryDirectory() as prepared:
                with self.assertRaises(profile_install.ProfileInstallError):
                    profile_install.prepare_profile_sources([bundle_root], temp_root=Path(prepared))

    def test_test_and_install_stops_before_install_plan_on_failed_verification(self):
        args = install_tool.build_parser().parse_args([
            "install", "--scope", "user", "--codex", "--verify",
        ])
        with mock.patch.object(install_tool, "run_verification_gate", side_effect=install_tool.InstallError("verification failed")), \
             mock.patch.object(install_tool, "_perform_install") as perform:
            with self.assertRaises(install_tool.InstallError):
                install_tool.install(args)
        perform.assert_not_called()

    def test_profile_wrapper_defaults_to_test_and_install(self):
        with mock.patch.object(install_profiles.setup_tool, "main", return_value=0) as entry:
            result = install_profiles.main(["--bundle", "profiles.zip", "--omp", "--profile", "rust"])
        self.assertEqual(result, 0)
        values = entry.call_args.args[0]
        self.assertIn("--test-and-install", values)
        self.assertIn("--language-profiles", values)
        self.assertIn("profiles.zip", values)
        self.assertIn("--profile-id", values)
        self.assertIn("rust", values)

    def test_current_docs_show_one_command_paths(self):
        combined = "\n".join(
            (ROOT / relative).read_text(encoding="utf-8")
            for relative in ("README.md", "docs/INSTALL.md", "docs/LANGUAGE-PROFILES.md", "docs/USAGE.md", "docs/DEVELOPMENT.md")
        )
        for command in (
            "python tools/verify_source_repository.py",
            "python tools/repo_setup.py --test-and-install",
            "python tools/run_tests.py --all",
            "--language-profiles",
            "tools/build_public_release.py",
        ):
            self.assertIn(command, combined)


if __name__ == "__main__":
    unittest.main()
