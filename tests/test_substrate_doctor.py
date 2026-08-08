from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from substrate import doctor  # noqa: E402
from tests._path_support import assert_same_path
from tests._fake_executable import write_python_executable


class SubstrateDoctorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "project"
        self.root.mkdir()
        (self.root / ".git").mkdir()
        (self.root / ".git" / "config").write_text(
            "[core]\n\trepositoryformatversion = 0\n", encoding="utf-8"
        )
        (self.root / ".jj" / "repo").mkdir(parents=True)
        self.bin = Path(self.temporary.name) / "bin"
        self.bin.mkdir()
        self.executables: dict[str, Path] = {}

    def tearDown(self):
        self.temporary.cleanup()

    def executable(self, name: str, version: str, probe_source: str = "") -> Path:
        executable = write_python_executable(
            self.bin / name,
            "import os\n"
            "import shutil\n"
            "import subprocess\n"
            "import sys\n"
            "args = sys.argv[1:]\n"
            + probe_source
            + f"print({version!r})\n",
        )
        self.executables[name] = executable
        return executable

    def fake_all(self):
        # The fake Git/jj commands answer both version and root probes.
        self.executable(
            "git",
            "git version 2.47.3",
            "if args[:1] == ['rev-parse']:\n"
            "    print(os.environ['FAKE_PROJECT_ROOT'])\n"
            "    raise SystemExit(0)\n",
        )
        self.executable(
            "jj",
            "jj 0.43.0",
            "while args and args[0] in {'--no-pager', '--color=never'}:\n"
            "    args = args[1:]\n"
            "if args[:1] == ['root'] or args[:2] == ['git', 'root']:\n"
            "    print(os.environ['FAKE_PROJECT_ROOT'])\n"
            "    raise SystemExit(0)\n",
        )
        self.executable("bd", "bd version 1.1.0")
        self.executable(
            "mise",
            "2026.8.0 linux-x64",
            "if len(args) >= 4 and args[0] == 'exec':\n"
            "    tool = shutil.which(args[3], path=os.environ['FAKE_TOOL_BIN'])\n"
            "    if not tool:\n"
            "        raise SystemExit(127)\n"
            "    completed = subprocess.run([tool, *args[4:]], check=False)\n"
            "    raise SystemExit(completed.returncode)\n",
        )

    def request(self, required=None, policy="PATH_ONLY"):
        return {
            "schema": "bbk.substrate-doctor-request.v1",
            "project_root": str(self.root),
            "profile": "governed-software",
            "required_tools": required or ["git", "jj", "bd", "mise"],
            "search_policy": policy,
            "approved_tool_roots": [str(self.bin)] if policy != "PATH_ONLY" else [],
        }

    def environment(self):
        return {**os.environ, "PATH": str(self.bin), "FAKE_PROJECT_ROOT": str(self.root), "FAKE_TOOL_BIN": str(self.bin)}

    def test_windows_fake_executable_uses_cmd_launcher_and_python_payload(self):
        launcher = write_python_executable(
            self.bin / "mise",
            "print('mise test')",
            platform_name="nt",
        )
        self.assertEqual(launcher.suffix.lower(), ".cmd")
        self.assertTrue(launcher.is_file())
        script = launcher.with_name(f".{launcher.name}.py")
        self.assertEqual(script.read_text(encoding="utf-8"), "print('mise test')\n")
        command = launcher.read_text(encoding="utf-8")
        self.assertIn("-S -X utf8", command)
        self.assertIn(script.name, command)

    def test_path_resolution_rejects_python_payload_from_pathext(self):
        payload = self.bin / "mise.py"
        payload.write_text("print('not a native launcher')\n", encoding="utf-8")
        with (
            mock.patch.object(doctor.shutil, "which", return_value=str(payload)),
            mock.patch.object(doctor.os, "access", return_value=True),
        ):
            discovered = doctor.discover_executable(
                "mise",
                search_policy="PATH_ONLY",
                environment={"PATH": str(self.bin)},
            )
        self.assertIsNone(discovered)

    def test_complete_real_executable_set_passes_and_is_deterministic(self):
        self.fake_all()
        first = doctor.inspect(self.request(), environment=self.environment(), created_at="2026-08-04T00:00:00Z")
        second = doctor.inspect(self.request(), environment=self.environment(), created_at="2026-08-04T00:00:00Z")
        self.assertEqual("PASS", first["status"])
        self.assertEqual(first, second)
        self.assertFalse(first["network_bootstrap_performed"])
        self.assertEqual(["git", "jj", "bd", "mise"], [item["name"] for item in first["tools"]])
        self.assertTrue(all(Path(item["path"]).is_absolute() for item in first["tools"]))
        managed = {item["name"]: item for item in first["tools"] if item["name"] in {"jj", "bd"}}
        self.assertEqual({"MISE_MANAGED"}, {item["execution_mode"] for item in managed.values()})
        self.assertEqual("jj@0.43.0", managed["jj"]["tool_spec"])
        self.assertEqual("github:gastownhall/beads@1.1.0", managed["bd"]["tool_spec"])

    def test_missing_mise_blocks_with_exact_reason_and_no_bootstrap(self):
        self.fake_all()
        self.executables["mise"].unlink()
        lock = doctor.inspect(self.request(), environment=self.environment())
        mise = next(item for item in lock["tools"] if item["name"] == "mise")
        self.assertEqual("BLOCK", lock["status"])
        self.assertEqual("SUBSTRATE_MISE_UNAVAILABLE", mise["reason_code"])
        self.assertIn("will not download", mise["remediation"])
        self.assertFalse(lock["network_bootstrap_performed"])

    def test_approved_offline_root_is_considered_without_path_mutation(self):
        self.fake_all()
        env = self.environment()
        env["PATH"] = ""
        lock = doctor.inspect(self.request(policy="PATH_AND_APPROVED_OFFLINE_ROOTS"), environment=env)
        self.assertEqual("PASS", lock["status"])
        assert_same_path(
            self,
            next(x for x in lock["tools"] if x["name"] == "mise")["path"],
            self.executables["mise"],
        )

    def test_path_only_ignores_unapproved_offline_root(self):
        self.fake_all()
        env = {**os.environ, "PATH": ""}
        lock = doctor.inspect(self.request(policy="PATH_ONLY"), environment=env)
        self.assertEqual("BLOCK", lock["status"])
        self.assertTrue(all(item["path"] is None for item in lock["tools"]))

    def test_lock_is_immutable_and_schema_valid(self):
        self.fake_all()
        lock = doctor.inspect(self.request(), environment=self.environment(), created_at="2026-08-04T00:00:00Z")
        path = doctor.write_lock(self.root, lock)
        self.assertEqual(path, doctor.write_lock(self.root, lock))
        loaded = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(lock, loaded)
        try:
            import jsonschema
        except ImportError:
            return
        schema = json.loads(
            (ROOT / "spec" / "schemas" / "bbk-substrate-lock-v1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        jsonschema.Draft202012Validator(schema).validate(lock)


if __name__ == "__main__":
    unittest.main()
