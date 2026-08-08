from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import governed_filesystem  # noqa: E402
import omp_binding_registry as registry  # noqa: E402
import worker_spawn  # noqa: E402

JJ = Path(
    os.environ.get("BBK_TEST_JJ")
    or shutil.which("jj")
    or "/mnt/data/bbk-alpha17-18-work/toolkit/blueprint-one-shot-toolkit-linux-x86_64/bin/jj"
)
BD = Path(os.environ.get("BBK_TEST_BD") or os.environ.get("BBK_BD") or shutil.which("bd") or "")
GIT = Path(shutil.which("git") or "")
BOOTSTRAP = ROOT / "tools" / "qualification" / "manual-kit-template" / "bootstrap-binding.py"
INTEGRATE = ROOT / "tools" / "qualification" / "manual-kit-template" / "manual-integration.py"


@unittest.skipUnless(os.name != "nt" and JJ.is_file() and BD.is_file() and GIT.is_file(), "POSIX real git/jj/bd fixture required")
class ManualQualificationRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.project = self.base / "qualification" / "project"
        self.project.mkdir(parents=True)
        (self.project / "src" / "worker-a").mkdir(parents=True)
        (self.project / "src" / "worker-b").mkdir(parents=True)
        (self.project / "src" / "worker-a" / ".gitkeep").write_text("", encoding="utf-8")
        (self.project / "src" / "worker-b" / ".gitkeep").write_text("", encoding="utf-8")
        (self.project / "README.md").write_text("manual qualification fixture\n", encoding="utf-8")
        (self.project / "mise.toml").write_text(
            '[tools]\n"github:gastownhall/beads" = "1.1.0"\njj = "0.43.0"\n',
            encoding="utf-8",
        )
        current = self.project / ".bbk-kit" / "current.json"
        current.parent.mkdir(parents=True)
        current.write_text(json.dumps({"path": str(ROOT.resolve())}) + "\n", encoding="utf-8")

        self.run_command([str(GIT), "init", "-b", "main"])
        self.run_command([str(GIT), "config", "user.name", "BBK Test"])
        self.run_command([str(GIT), "config", "user.email", "bbk@example.invalid"])
        self.run_command([str(GIT), "add", "."])
        self.run_command([str(GIT), "commit", "-m", "manual fixture baseline"])
        self.run_command([str(JJ), "--no-pager", "--color=never", "git", "init", "--colocate", "."])

        self.fake_mise = self.base / "mise"
        self.fake_mise.write_text(
            "#!/usr/bin/env python3\n"
            "import os, sys\n"
            f"jj = {str(JJ.resolve())!r}\n"
            "args = sys.argv[1:]\n"
            "if args == ['--version']:\n"
            "    print('mise test adapter 0')\n"
            "    raise SystemExit(0)\n"
            "if args and args[0] == 'which':\n"
            "    print(jj)\n"
            "    raise SystemExit(0)\n"
            "if args and args[0] == 'exec' and '--' in args:\n"
            "    index = args.index('--')\n"
            "    command = args[index + 1]\n"
            "    if command != 'jj':\n"
            "        raise SystemExit('unexpected managed tool: ' + command)\n"
            "    os.execv(jj, [jj, *args[index + 2:]])\n"
            "raise SystemExit('unexpected mise argv: ' + repr(args))\n",
            encoding="utf-8",
        )
        self.fake_mise.chmod(self.fake_mise.stat().st_mode | stat.S_IXUSR)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_command(self, command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command,
            cwd=self.project,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="backslashreplace",
            check=check,
            timeout=120,
        )

    def bootstrap(self, session: str, parent: str = "") -> tuple[subprocess.CompletedProcess[str], dict]:
        command = [
            sys.executable,
            str(BOOTSTRAP),
            "--project-root", str(self.project),
            "--session-id", session,
            "--host-version", "omp/16.4.8",
            "--git", str(GIT),
            "--mise", str(self.fake_mise),
        ]
        if parent:
            command.extend(["--parent-session-id", parent])
        completed = self.run_command(command, check=False)
        value = json.loads(completed.stdout) if completed.stdout.strip() else {}
        return completed, value

    def compile_worker(self, bootstrap: dict, *, letter: str) -> dict:
        lower = letter.lower()
        work_unit = f"WU-MANUAL-WORKER-{letter}"
        compiled = worker_spawn.compile_bound_spawn(
            self.project,
            {
                "schema": "bbk.bound-worker-spawn-create.v1",
                "host_version": "omp/16.4.8",
                "parent_binding_ref": bootstrap["root_binding_ref"],
                "parent_session_id": bootstrap["root_session_id"],
                "parent_invocation_id": bootstrap["root_invocation_id"],
                "task_name": f"Alpha17Worker{letter}",
                "role": "bbk_worker",
                "work_unit_id": work_unit,
                "attempt_id": f"worker-{lower}-1",
                "baseline_ref": bootstrap["baseline_ref"],
                "candidate_ref": f"candidate:alpha17-manual:worker-{lower}",
                "authority_ref": bootstrap["authority_ref"],
                "return_contract": "bbk.worker-return.v2",
                "return_transport_mode": "STRUCTURED_RETURN_ONLY",
                "parent_revision": bootstrap["parent_revision"],
                "workspace_parent": bootstrap["workspace_parent"],
                "path_prefixes": [f"src/worker-{lower}"],
                "mutation_classes": ["PRODUCT_CONTENT"],
                "semantic_scope": ["manual:alpha17", f"worker:{lower}"],
                "assignment": f"Create the exact Worker {letter} fixture result and return it structurally.",
                "description": f"manual worker {letter}",
                "idempotency_key": f"manual-worker-{lower}-spawn",
            },
            jj_path=JJ,
            bd_path=BD,
            recorded_at="2026-08-05T00:00:01Z",
        )
        registry.admit_spawn_dispatch(
            self.project,
            dispatch_ref=compiled["dispatch_ref"],
            dispatch_input_digest=compiled["dispatch_input_digest"],
            parent_session_id=bootstrap["root_session_id"],
            tool_call_id=f"task-worker-{lower}",
            host_version="omp/16.4.8",
            observed_at="2026-08-05T00:00:02Z",
        )
        activation = registry.activate_spawn_session(
            self.project,
            planned_binding_ref=compiled["planned_binding_ref"],
            actual_session_id=f"actual-worker-{lower}-session",
            packet_digest=compiled["worker_packet"]["packet_digest"],
            host_version="omp/16.4.8",
            observed_at="2026-08-05T00:00:03Z",
        )
        binding = activation["binding"]
        payload = {"content": f"alpha17-worker-{lower}\n", "encoding": "utf-8"}
        result = governed_filesystem.execute(
            self.project,
            {
                "schema": "bbk.governed-filesystem-execution.v1",
                "host_version": "omp/16.4.8",
                "session_id": binding["request"]["session_id"],
                "invocation_id": binding["request"]["invocation_id"],
                "intent": {
                    "schema": "bbk.mutation-intent.v1",
                    "binding_ref": binding["binding_id"],
                    "operation": "WRITE",
                    "path": f"src/worker-{lower}/result.txt",
                    "content_or_patch_digest": governed_filesystem.payload_digest(payload),
                    "expected_precondition": {"kind": "ABSENT"},
                    "mutation_class": "PRODUCT_CONTENT",
                    "idempotency_key": f"manual-worker-{lower}-write",
                },
                "payload": payload,
            },
            jj_path=JJ,
        )
        self.assertEqual("PASS", result["status"])
        return compiled

    def integrate(self, bootstrap: dict) -> tuple[subprocess.CompletedProcess[str], dict]:
        completed = self.run_command(
            [
                sys.executable,
                str(INTEGRATE),
                "--project-root", str(self.project),
                "--session-id", bootstrap["root_session_id"],
                "--binding-ref", bootstrap["root_binding_ref"],
                "--invocation-id", bootstrap["root_invocation_id"],
                "--idempotency-key", "manual-integration-1",
                "--git", str(GIT),
                "--mise", str(self.fake_mise),
            ],
            check=False,
        )
        return completed, json.loads(completed.stdout)

    def test_root_bootstrap_is_create_once_and_child_observation_cannot_replace_it(self) -> None:
        first_run, first = self.bootstrap("root-session")
        self.assertEqual(0, first_run.returncode, first_run.stderr)
        path = self.project / ".bbk" / "manual-qualification" / "bootstrap.json"
        original = path.read_bytes()

        repeat_run, repeat = self.bootstrap("root-session")
        self.assertEqual(0, repeat_run.returncode, repeat_run.stderr)
        self.assertTrue(repeat["bootstrap_reused"])
        self.assertEqual(original, path.read_bytes())

        child_run, child = self.bootstrap("child-session", parent="root-session")
        self.assertEqual(0, child_run.returncode, child_run.stderr)
        self.assertEqual("ROOT_PRESERVED", child["status"])
        self.assertFalse(child["is_root_session"])
        self.assertEqual(first["root_binding_ref"], child["root_binding_ref"])
        self.assertEqual(original, path.read_bytes())

    def test_manual_integration_fails_closed_then_admits_exact_two_parent_candidate(self) -> None:
        bootstrap_run, bootstrap = self.bootstrap("root-session")
        self.assertEqual(0, bootstrap_run.returncode, bootstrap_run.stderr)
        self.compile_worker(bootstrap, letter="A")

        failed_run, failed = self.integrate(bootstrap)
        self.assertEqual(2, failed_run.returncode)
        self.assertEqual("BLOCKED_TECHNICAL", failed["status"])
        self.assertFalse(failed["candidate_bind_permitted"])
        self.assertFalse((self.project / ".bbk" / "manual-qualification" / "integration.json").exists())

        self.compile_worker(bootstrap, letter="B")
        passed_run, passed = self.integrate(bootstrap)
        self.assertEqual(0, passed_run.returncode, passed_run.stderr)
        self.assertEqual("INTEGRATED", passed["status"])
        self.assertEqual("DENIED", passed["conflict_resolution_authority"])
        self.assertEqual(
            ["src/worker-a/result.txt", "src/worker-b/result.txt"],
            passed["exact_integrated_paths"],
        )
        self.assertRegex(passed["candidate_admission_ref"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(2, len(passed["candidate_admission"]["parent_commit_ids"]))
        self.assertFalse((self.project / ".bbk" / "manual-qualification" / "integration-failure.json").exists())
        workspace = Path(passed["candidate"]["workspace_path"])
        self.assertEqual("alpha17-worker-a\n", (workspace / "src" / "worker-a" / "result.txt").read_text(encoding="utf-8"))
        self.assertEqual("alpha17-worker-b\n", (workspace / "src" / "worker-b" / "result.txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
