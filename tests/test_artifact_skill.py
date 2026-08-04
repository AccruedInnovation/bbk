"""Codex/Claude exposure and PATH-independent behavior for bbk-artifact."""
from __future__ import annotations

import hashlib
import json
import os
import py_compile
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests._cli_support import run_cli
from tests._path_support import assert_same_path

ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "shared" / "skills" / "bbk-artifact"
WRAPPER = SKILL_ROOT / "scripts" / "bbk_artifact.py"
INSTALLER = ROOT / "tools" / "install.py"
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
EXPECTED_FILES = {
    "SKILL.md",
    "agents/openai.yaml",
    "assets/bbk-package-draft.generic.json",
    "references/artifact-package-reference.md",
    "scripts/bbk-artifact.cmd",
    "scripts/bbk-artifact.sh",
    "scripts/bbk_artifact.py",
}


def _json_command(command: list[str], *, cwd: Path, env: dict[str, str], timeout: float = 180) -> dict[str, object]:
    result = run_cli(command, cwd=cwd, env=env, check=False, timeout=timeout)
    if result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)
    return json.loads(result.stdout)


class BbkArtifactSkillTests(unittest.TestCase):
    def test_canonical_skill_inventory_contract_and_host_projections(self):
        files = {
            path.relative_to(SKILL_ROOT).as_posix()
            for path in SKILL_ROOT.rglob("*")
            if path.is_file()
        }
        self.assertEqual(files, EXPECTED_FILES)

        skill_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(skill_text.startswith("---\nname: bbk-artifact\n"))
        self.assertIn("does not establish semantic acceptance", skill_text)
        self.assertIn(".agents\\skills\\bbk-artifact", skill_text)
        self.assertIn(".claude\\skills\\bbk-artifact", skill_text)
        self.assertIn("bbk_on_path_required", WRAPPER.read_text(encoding="utf-8"))

        method = json.loads((ROOT / "spec" / "method-content.json").read_text(encoding="utf-8"))
        self.assertEqual(method["skills"]["bbk-artifact"], skill_text)
        roles = json.loads((ROOT / "spec" / "roles.json").read_text(encoding="utf-8"))["roles"]
        self.assertEqual(len(roles), 19)
        self.assertTrue(all("bbk-artifact" in role["skills"] for role in roles))
        self.assertTrue(all("bbk-artifact" not in role["mandatory_skills"] for role in roles))

        for target, suffix in (("codex", ".toml"), ("claude", ".md")):
            rendered = list((ROOT / "projections" / target / "agents").glob(f"*{suffix}"))
            self.assertEqual(len(rendered), 19)
            self.assertTrue(all("bbk-artifact" in path.read_text(encoding="utf-8") for path in rendered))

        for rel in ("scripts/bbk-artifact.sh", "scripts/bbk_artifact.py"):
            self.assertTrue(SKILL_ROOT.joinpath(rel).is_file())
            self.assertFalse(SKILL_ROOT.joinpath(rel).is_symlink())
        with tempfile.TemporaryDirectory() as temp:
            py_compile.compile(WRAPPER, cfile=str(Path(temp) / "bbk_artifact.pyc"), doraise=True)
        shell = shutil.which("sh")
        if shell:
            subprocess.run([shell, "-n", str(SKILL_ROOT / "scripts" / "bbk-artifact.sh")], check=True, cwd=ROOT)

    def test_user_install_exposes_skill_to_codex_and_claude_and_wrapper_runs_without_bbk_on_path(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            home = base / "home"
            home.mkdir()
            data_root = base / "data"
            bin_root = base / "bbk-bin-not-on-path"
            env = os.environ.copy()
            env.update(
                {
                    "BBK_HOME": str(home),
                    "HOME": str(home),
                    "BBK_INSTALL_ROOT": str(data_root),
                    "BBK_BIN_DIR": str(bin_root),
                }
            )
            installed = _json_command(
                [
                    sys.executable,
                    str(INSTALLER),
                    "--json",
                    "install",
                    "--scope",
                    "user",
                    "--codex",
                    "--claude",
                    "--no-language-profiles",
                ],
                cwd=ROOT,
                env=env,
            )
            self.assertEqual(installed["version"], VERSION)
            self.assertTrue(installed["codex"])
            self.assertTrue(installed["claude"])

            host_skills = {
                "codex": home / ".agents" / "skills" / "bbk-artifact",
                "claude": home / ".claude" / "skills" / "bbk-artifact",
            }
            manifest_records = {
                Path(item["path"]).resolve(): item
                for item in installed["files"]
                if isinstance(item, dict) and isinstance(item.get("path"), str)
            }
            for skill_root in host_skills.values():
                installed_files = {
                    path.relative_to(skill_root).as_posix()
                    for path in skill_root.rglob("*")
                    if path.is_file()
                }
                self.assertEqual(installed_files, EXPECTED_FILES)
                for rel in EXPECTED_FILES:
                    path = (skill_root / rel).resolve()
                    self.assertIn(path, manifest_records)
                for rel in ("scripts/bbk-artifact.sh", "scripts/bbk_artifact.py"):
                    self.assertTrue((skill_root / rel).is_file())
                    self.assertFalse((skill_root / rel).is_symlink())

            self.assertEqual(
                hashlib.sha256((host_skills["codex"] / "SKILL.md").read_bytes()).hexdigest(),
                hashlib.sha256((host_skills["claude"] / "SKILL.md").read_bytes()).hexdigest(),
            )

            draft = base / "draft"
            draft.mkdir()
            (draft / "design.md").write_text("# Design\n", encoding="utf-8")
            (draft / "evidence.txt").write_text("verified fixture\n", encoding="utf-8")
            descriptor = {
                "schema": "bbk.artifact-package-draft.v1",
                "packageId": "pkg-artifact-skill-test",
                "revision": "1",
                "profile": {"id": "generic", "version": "1"},
                "subject": {"kind": "test-fixture", "id": "artifact-skill", "revision": "1"},
                "predecessor": None,
                "artifacts": [
                    {
                        "artifactId": "design",
                        "path": "design.md",
                        "role": "semantic",
                        "references": ["evidence"],
                    },
                    {
                        "artifactId": "evidence",
                        "path": "evidence.txt",
                        "role": "evidence",
                        "references": [],
                    },
                ],
                "metadata": {"purpose": "artifact skill integration test"},
            }
            (draft / "bbk-package-draft.json").write_text(
                json.dumps(descriptor, ensure_ascii=False, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )

            wrapper_env = env.copy()
            wrapper_env["BBK_PYTHON"] = sys.executable
            if os.name != "nt":
                wrapper_env["PATH"] = os.pathsep.join(path for path in ("/usr/bin", "/bin") if Path(path).is_dir())
                shell = shutil.which("sh")
                if shell is None:
                    self.skipTest("POSIX shell unavailable")
                wrapper_command = [shell, str(host_skills["codex"] / "scripts" / "bbk-artifact.sh")]
                self.assertNotIn(str(bin_root), wrapper_env["PATH"].split(os.pathsep))
            else:
                wrapper_command = [str(host_skills["codex"] / "scripts" / "bbk-artifact.cmd")]
                wrapper_env["PATH"] = str(Path(sys.executable).parent)

            binding = _json_command([*wrapper_command, "binding"], cwd=base, env=wrapper_env)
            self.assertEqual(binding["schema"], "bbk.artifact-skill-binding.v1")
            self.assertEqual(binding["status"], "PASS")
            self.assertEqual(binding["version"], VERSION)
            self.assertFalse(binding["bbk_on_path_required"])
            assert_same_path(self, binding["manifest"], installed["manifest_path"])
            assert_same_path(self, binding["script"], Path(binding["package_root"]) / "tools" / "bbk.py")

            preflight = _json_command([*wrapper_command, "preflight", str(draft)], cwd=base, env=wrapper_env)
            self.assertEqual(preflight["status"], "PASS")
            finalized = _json_command(
                [*wrapper_command, "finalize", str(draft), "--root", str(base)],
                cwd=base,
                env=wrapper_env,
            )
            self.assertEqual(finalized["status"], "PASS")
            self.assertEqual(finalized["packageId"], "pkg-artifact-skill-test")
            sealed = base / ".bbk" / "artifacts" / "sealed" / "pkg-artifact-skill-test-1"
            publication = base / ".bbk" / "artifacts" / "publications" / "pkg-artifact-skill-test-1.json"
            current = base / ".bbk" / "artifacts" / "current" / "pkg-artifact-skill-test.json"
            assert_same_path(self, finalized["outputRoot"], sealed)
            assert_same_path(self, finalized["publicationReceipt"], publication)
            assert_same_path(self, finalized["currentPointer"], current)
            self.assertTrue(publication.is_file())
            self.assertTrue(current.is_file())
            self.assertFalse(publication.is_relative_to(sealed))
            self.assertFalse(current.is_relative_to(sealed))
            verify = _json_command([*wrapper_command, "verify", str(sealed)], cwd=base, env=wrapper_env)
            self.assertEqual(verify["status"], "PASS")
            self.assertTrue(verify["readOnly"])
            self.assertEqual(verify["contentSha256"], finalized["contentSha256"])

            # The managed Codex/Claude wrapper must also expose the alpha.16.1
            # one-shot software path.  This ordinary project intentionally has
            # no hand-authored package descriptor.
            software = base / "software-project"
            (software / "static").mkdir(parents=True)
            (software / "tests").mkdir()
            (software / "app.py").write_text("def answer():\n    return 42\n", encoding="utf-8")
            (software / "static" / "index.html").write_text("<!doctype html><title>Fixture</title>\n", encoding="utf-8")
            (software / "tests" / "test_app.py").write_text("from app import answer\nassert answer() == 42\n", encoding="utf-8")
            (software / "README.md").write_text("# Software fixture\n", encoding="utf-8")
            self.assertFalse((software / "bbk-package-draft.json").exists())
            software_finalized = _json_command(
                [
                    *wrapper_command,
                    "finalize",
                    "--root", str(software),
                    "--package-id", "software-skill-test",
                    "--revision", "1",
                    "--source", "app.py",
                    "--source", "static",
                    "--source", "tests",
                    "--source", "README.md",
                ],
                cwd=software,
                env=wrapper_env,
            )
            self.assertEqual(software_finalized["status"], "PASS")
            self.assertEqual(software_finalized["finalizationMode"], "software-source-set")
            self.assertTrue(software_finalized["stagedDraftRemoved"])
            software_publication = Path(str(software_finalized["publicationReceipt"]))
            software_fresh = _json_command(
                [*wrapper_command, "freshness", str(software_publication), "--root", str(software)],
                cwd=software,
                env=wrapper_env,
            )
            self.assertEqual(software_fresh["status"], "PASS")
            self.assertEqual(software_fresh["sourceStatus"], "PASS")
            (software / "app.py").write_text("def answer():\n    return 43\n", encoding="utf-8")
            stale_run = run_cli(
                [*wrapper_command, "freshness", str(software_publication), "--root", str(software)],
                cwd=software,
                env=wrapper_env,
                check=False,
                timeout=180,
            )
            self.assertEqual(stale_run.returncode, 1)
            stale = json.loads(stale_run.stdout)
            self.assertEqual(stale["status"], "REJECTED")
            self.assertEqual(stale["code"], "PACKAGE_FINALIZATION_SOURCE_STALE")

            removed = _json_command(
                [sys.executable, str(INSTALLER), "--json", "uninstall", "--scope", "user"],
                cwd=ROOT,
                env=env,
            )
            self.assertTrue(removed["removed"])
            self.assertFalse(Path(removed["manifest_path"]).exists())
            self.assertFalse(host_skills["codex"].exists())
            self.assertFalse(host_skills["claude"].exists())
            self.assertEqual(
                [path for path in data_root.rglob("*") if path.is_file()],
                [],
                "PATH-independent artifact execution must not leave unowned bytecode behind after uninstall",
            )

    def test_project_scope_targets_use_host_native_skill_roots(self):
        tools = ROOT / "tools"
        sys.path.insert(0, str(tools))
        try:
            import install as install_tool

            with tempfile.TemporaryDirectory() as temp:
                project = Path(temp).resolve()
                targets = install_tool.installation_targets(scope="project", project=project)
                self.assertEqual(targets["agent_skills"], project / ".agents" / "skills")
                self.assertEqual(targets["claude_skills"], project / ".claude" / "skills")
        finally:
            try:
                sys.path.remove(str(tools))
            except ValueError:
                pass


if __name__ == "__main__":
    unittest.main()
