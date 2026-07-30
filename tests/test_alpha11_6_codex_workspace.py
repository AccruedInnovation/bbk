from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODEX_AGENTS = ROOT / "projections" / "codex" / "agents"
INSTALL = ROOT / "tools" / "install.py"
SETUP = ROOT / "tools" / "setup.py"
UPDATE_CODEX = ROOT / "tools" / "update_codex.py"
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def run(command, *, env=None, check=True):
    return subprocess.run(
        [str(value) for value in command],
        cwd=ROOT,
        env=env,
        check=check,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )


def run_json(command, *, env=None, check=True):
    result = run(command, env=env, check=check)
    return json.loads(result.stdout), result


def snapshot(root: Path) -> dict[str, tuple[str, int]]:
    return {
        path.relative_to(root).as_posix(): (
            hashlib.sha256(path.read_bytes()).hexdigest(),
            path.stat().st_mtime_ns,
        )
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class Alpha116CodexWorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.roles = json.loads((ROOT / "spec" / "roles.json").read_text(encoding="utf-8"))["roles"]
        cls.by_name = {item["name"]: item for item in cls.roles}

    def test_current_version_is_alpha116(self) -> None:
        self.assertEqual(VERSION, "0.1.0-alpha.11.7")

    def test_all_codex_agents_inherit_parent_sandbox(self) -> None:
        files = sorted(CODEX_AGENTS.glob("*.toml"))
        self.assertEqual(len(files), len(self.roles))
        self.assertEqual({path.stem for path in files}, set(self.by_name))
        for path in files:
            with self.subTest(agent=path.stem):
                value = tomllib.loads(path.read_text(encoding="utf-8"))
                self.assertNotIn("sandbox_mode", value)
                instructions = value["developer_instructions"]
                self.assertIn("inherits the parent turn's active Codex sandbox and approval settings", instructions)
                self.assertIn("notes, handoffs, plans, ADRs, manifests, evidence records", instructions)

    def test_semantic_mutation_boundary_remains_role_specific(self) -> None:
        for role in self.roles:
            path = CODEX_AGENTS / f"{role['name']}.toml"
            instructions = tomllib.loads(path.read_text(encoding="utf-8"))["developer_instructions"]
            with self.subTest(agent=role["name"], mutates=role.get("mutates")):
                if role.get("mutates"):
                    self.assertIn("may also modify subject or product artifacts only within", instructions)
                    self.assertNotIn("Inherited host write access does not authorize changes", instructions)
                else:
                    self.assertIn("Inherited host write access does not authorize changes to subject or product artifacts", instructions)
                    self.assertNotIn("may also modify subject or product artifacts only within", instructions)

    def test_generator_no_longer_projects_read_only_codex_overrides(self) -> None:
        source = (ROOT / "tools" / "generate_agents.py").read_text(encoding="utf-8")
        self.assertNotIn("lines.append('sandbox_mode = \"read-only\"')", source)
        completed = run([sys.executable, ROOT / "tools" / "generate_agents.py", "--check"])
        self.assertEqual(completed.returncode, 0, completed.stdout)

    def test_setup_exposes_codex_only_update_and_rejects_harness_selection(self) -> None:
        help_text = run([sys.executable, SETUP, "--help"]).stdout
        self.assertIn("--update-codex", help_text)
        self.assertIn("--test-and-update-codex", help_text)
        self.assertIn("preserve OMP", help_text)
        invalid = run(
            [sys.executable, SETUP, "--update-codex", "--scope", "user", "--omp"],
            check=False,
        )
        self.assertNotEqual(invalid.returncode, 0)
        self.assertIn("do not apply to a Codex-only update", invalid.stdout + invalid.stderr)

    def test_codex_only_update_removes_legacy_overrides_without_touching_shared_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            home = base / "home"
            home.mkdir()
            env = os.environ.copy()
            env.update(
                {
                    "BBK_HOME": str(home),
                    "HOME": str(home),
                    "BBK_INSTALL_ROOT": str(base / "data"),
                    "BBK_BIN_DIR": str(base / "bin"),
                }
            )
            installed, _ = run_json(
                [
                    sys.executable,
                    INSTALL,
                    "--json",
                    "install",
                    "--scope",
                    "user",
                    "--codex",
                    "--omp",
                    "--no-language-profiles",
                ],
                env=env,
            )
            manifest_path = Path(installed["manifest_path"])
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            initial_version = manifest["version"]
            records = {Path(item["path"]): item for item in manifest["files"]}
            codex_root = home / ".codex" / "agents"
            for path in sorted(codex_root.glob("bbk_*.toml")):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn('\nsandbox_mode = "read-only"\n', text)
                text = text.replace(
                    "\ndeveloper_instructions = ",
                    '\nsandbox_mode = "read-only"\ndeveloper_instructions = ',
                    1,
                )
                path.write_text(text, encoding="utf-8")
                records[path]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            manifest.setdefault("harness_versions", {})["codex"] = "0.1.0-alpha.11.5"
            manifest["harness_versions"]["omp"] = initial_version
            manifest_path.write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            omp_root = home / ".omp"
            shared_root = base / "data"
            current_file = shared_root / "current.json"
            effective_file = Path(manifest["model_routing"]["effective_copy"])
            launcher_root = base / "bin"
            package_root = Path(manifest["package_root"])
            omp_before = snapshot(omp_root)
            package_before = snapshot(package_root)
            launcher_before = snapshot(launcher_root)
            current_before = current_file.read_bytes()
            effective_before = effective_file.read_bytes()

            updated, _ = run_json(
                [sys.executable, UPDATE_CODEX, "--json", "--scope", "user"],
                env=env,
            )
            self.assertEqual(updated["status"], "PASS")
            self.assertEqual(updated["from_version"], "0.1.0-alpha.11.5")
            self.assertEqual(updated["to_version"], VERSION)
            self.assertEqual(updated["codex_agent_count"], 19)
            self.assertEqual(updated["actions"], {"replace": 19})
            self.assertFalse(updated["shared_package_updated"])
            self.assertFalse(updated["effective_model_routing_updated"])
            self.assertEqual(updated["omp_files_touched"], 0)
            self.assertIn("omp", updated["untouched_harnesses"])
            self.assertTrue(
                all("/.codex/agents/bbk_" in item["path"].replace("\\", "/") for item in updated["files"])
            )

            self.assertEqual(omp_before, snapshot(omp_root))
            self.assertEqual(package_before, snapshot(package_root))
            self.assertEqual(launcher_before, snapshot(launcher_root))
            self.assertEqual(current_before, current_file.read_bytes())
            self.assertEqual(effective_before, effective_file.read_bytes())

            binding = omp_root / "agent" / "extensions" / "bbk" / "bbk-package-root.json"
            routing, _ = run_json(
                [
                    sys.executable,
                    ROOT / "tools" / "omp_model_routing.py",
                    "--binding",
                    binding,
                    "--json",
                    "status",
                ],
                env=env,
            )
            self.assertEqual(routing["status"], "PASS")

            for path in sorted(codex_root.glob("bbk_*.toml")):
                value = tomllib.loads(path.read_text(encoding="utf-8"))
                self.assertNotIn("sandbox_mode", value)

            current = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(current["version"], initial_version)
            self.assertEqual(current["package_root"], manifest["package_root"])
            self.assertEqual(current["harness_versions"]["codex"], VERSION)
            self.assertEqual(current["harness_versions"]["omp"], initial_version)
            self.assertEqual(current["last_codex_update"]["kind"], "codex-only")
            self.assertFalse(current["last_codex_update"]["shared_package_updated"])
            status, _ = run_json(
                [sys.executable, INSTALL, "--json", "status", "--scope", "user"],
                env=env,
            )
            self.assertEqual(status["summary"], {"current": len(status["files"])})

    def test_current_docs_explain_permission_and_authority_separation(self) -> None:
        corpus = "\n".join(
            (ROOT / rel).read_text(encoding="utf-8")
            for rel in ("README.md", "docs/AGENT-COMPOSITION.md", "docs/USAGE.md", "docs/INSTALL.md")
        )
        for expected in (
            "inherit the parent",
            "sandbox",
            "coordination artifacts",
            "does not authorize",
            "subject or product artifacts",
            "--update-codex",
        ):
            self.assertIn(expected, corpus)


if __name__ == "__main__":
    unittest.main()
