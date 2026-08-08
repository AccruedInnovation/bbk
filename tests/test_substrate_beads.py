from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from tests._path_support import assert_same_path, assert_command_invokes  # noqa: E402
from tests._fake_executable import write_python_executable  # noqa: E402
from substrate import beads_adapter  # noqa: E402


BD = os.environ.get("BBK_TEST_BD") or shutil.which("bd")


@unittest.skipUnless(BD, "real bd executable not configured")
class BeadsAdapterIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.project = Path(self.temporary.name) / "project"
        self.project.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=self.project, check=True)
        subprocess.run(["git", "config", "user.name", "BBK Test"], cwd=self.project, check=True)
        subprocess.run(["git", "config", "user.email", "bbk@example.invalid"], cwd=self.project, check=True)
        subprocess.run(
            [str(BD), "init", "--non-interactive", "--prefix", "bbkt", "--skip-agents", "--skip-hooks", "--stealth"],
            cwd=self.project,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ, "BEADS_DISABLE_METRICS": "1"},
        )

    def tearDown(self):
        self.temporary.cleanup()

    def command(self, transition: str, revision: int, key: str):
        return {
            "schema": "bbk.beads-command.v1",
            "command_id": f"cmd:{key}",
            "work_unit_id": "WU-1",
            "attempt_id": "attempt-1",
            "transition": transition,
            "correlation_id": "correlation-1",
            "expected_revision": revision,
            "idempotency_key": key,
            "summary": f"{transition} WU-1",
            "evidence_refs": [],
            "finding_refs": [],
        }

    def test_typed_transition_sequence_and_backend_projection(self):
        created = beads_adapter.execute(self.project, self.project, self.command("CREATE", 0, "create-1"), bd_path=BD)
        started = beads_adapter.execute(self.project, self.project, self.command("START", 1, "start-1"), bd_path=BD)
        completed = beads_adapter.execute(self.project, self.project, self.command("COMPLETE", 2, "complete-1"), bd_path=BD)
        self.assertEqual((1, 2, 3), (created["revision_after"], started["revision_after"], completed["revision_after"]))
        backend = beads_adapter.read_backend_issue(self.project, "WU-1", bd_path=BD)
        issue = backend[0] if isinstance(backend, list) else backend
        self.assertEqual("closed", issue["status"])
        projection = beads_adapter.rebuild_projection(self.project)
        self.assertEqual("closed", projection["work_units"]["WU-1"]["status"])
        self.assertEqual(3, projection["work_units"]["WU-1"]["revision"])

    def test_exact_idempotent_retry_does_not_repeat_backend_effect(self):
        command = self.command("CREATE", 0, "create-1")
        first = beads_adapter.execute(self.project, self.project, command, bd_path=BD)
        retry = beads_adapter.execute(self.project, self.project, command, bd_path=BD)
        self.assertFalse(first["idempotent_reuse"])
        self.assertTrue(retry["idempotent_reuse"])
        self.assertEqual(first["receipt_id"], retry["receipt_id"])
        self.assertEqual(1, beads_adapter.current_revision(self.project, "WU-1"))

    def test_stale_revision_and_idempotency_collision_block_before_effect(self):
        command = self.command("CREATE", 0, "create-1")
        beads_adapter.execute(self.project, self.project, command, bd_path=BD)
        with self.assertRaisesRegex(beads_adapter.BeadsAdapterError, "REVISION_MISMATCH"):
            beads_adapter.execute(self.project, self.project, self.command("START", 0, "start-1"), bd_path=BD)
        changed = dict(command)
        changed["summary"] = "different"
        with self.assertRaisesRegex(beads_adapter.BeadsAdapterError, "IDEMPOTENCY_COLLISION"):
            beads_adapter.execute(self.project, self.project, changed, bd_path=BD)
        self.assertEqual(1, beads_adapter.current_revision(self.project, "WU-1"))

    def test_single_writer_serializes_parallel_entry(self):
        entered = threading.Event()
        completed = threading.Event()

        def contender():
            with beads_adapter.single_writer(self.project):
                entered.set()
            completed.set()

        with beads_adapter.single_writer(self.project):
            thread = threading.Thread(target=contender, daemon=True)
            thread.start()
            time.sleep(0.1)
            self.assertFalse(entered.is_set())
        thread.join(timeout=2)
        self.assertTrue(entered.is_set())
        self.assertTrue(completed.is_set())

    def test_single_writer_timeout_remains_fail_closed(self):
        prior = os.environ.get("BBK_BEADS_WRITER_WAIT_SECONDS")
        os.environ["BBK_BEADS_WRITER_WAIT_SECONDS"] = "0.01"
        try:
            with beads_adapter.single_writer(self.project):
                with self.assertRaisesRegex(beads_adapter.BeadsAdapterError, "SINGLE_WRITER_TIMEOUT"):
                    with beads_adapter.single_writer(self.project):
                        pass
        finally:
            if prior is None:
                os.environ.pop("BBK_BEADS_WRITER_WAIT_SECONDS", None)
            else:
                os.environ["BBK_BEADS_WRITER_WAIT_SECONDS"] = prior


class BeadsMiseOwnershipTests(unittest.TestCase):
    def test_default_beads_execution_uses_mise_without_global_bd(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            (root / "mise.toml").write_text(
                '[tools]\n"github:gastownhall/beads" = "1.1.0"\n',
                encoding="utf-8",
            )
            fake_bd = write_python_executable(
                Path(directory) / "managed-bd",
                "import sys\n"
                "args = sys.argv[1:]\n"
                "if args[:1] == ['--sandbox']:\n"
                "    args = args[1:]\n"
                "if args[:1] == ['--json']:\n"
                "    args = args[1:]\n"
                "if args[:1] == ['-C']:\n"
                "    args = args[2:]\n"
                "if args[:1] == ['--version']:\n"
                "    print('bd 1.1.0 managed')\n"
                "    raise SystemExit(0)\n"
                "raise SystemExit(9)\n",
            )
            fake_mise = write_python_executable(
                Path(directory) / "mise",
                "import os\n"
                "import subprocess\n"
                "import sys\n"
                "args = sys.argv[1:]\n"
                "if args == ['--version']:\n"
                "    print('mise TEST')\n"
                "    raise SystemExit(0)\n"
                "if len(args) >= 4 and args[0] == 'exec':\n"
                "    if args[1] != 'github:gastownhall/beads@1.1.0':\n"
                "        raise SystemExit(11)\n"
                "    if args[3] != 'bd':\n"
                "        raise SystemExit(12)\n"
                "    completed = subprocess.run([os.environ['FAKE_BD'], *args[4:]], check=False)\n"
                "    raise SystemExit(completed.returncode)\n"
                "raise SystemExit(10)\n",
            )
            previous = {key: os.environ.get(key) for key in ("PATH", "BBK_MISE", "FAKE_BD")}
            os.environ.update({"PATH": "", "BBK_MISE": str(fake_mise), "FAKE_BD": str(fake_bd)})
            try:
                completed = beads_adapter._run(root, ("--version",))
                command, binding = beads_adapter._bd_command(root)
            finally:
                for key, value in previous.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value
            self.assertEqual("bd 1.1.0 managed", completed.stdout.strip())
            assert_command_invokes(self, command, fake_mise, ["exec", "github:gastownhall/beads@1.1.0", "--", "bd"])
            self.assertEqual("MISE_MANAGED", binding["execution_mode"])
            self.assertEqual("github:gastownhall/beads@1.1.0", binding["tool_spec"])
            assert_same_path(self, binding["mise_path"], fake_mise)


if __name__ == "__main__":
    unittest.main()
