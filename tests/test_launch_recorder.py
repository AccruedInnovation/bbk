"""Focused qualification checks for repository-owned launch receipts."""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import launch_recorder
import build_release
import run_tests
import source_sanity
import verify_all
import verify_package
from runtime_requirements import python_command

ROOT = Path(__file__).resolve().parents[1]
SITE = Path(r"C:\Users\Tombstone\.cache\bbk\tooling\jsonschema-4.25.1\Lib\site-packages")
S10_MIRROR = Path(r"D:\AHR13\S10-FINAL-A1\mirror")
S19_DIAGNOSTIC_RECORDS = {
    "c389117c8dc3784cae4990a079683f26ba3a00e83733e82b7887954097ed5fb5": Path(r"D:\AHR13\S19-FINAL-A1\evidence\launch-ledger\launch-record-errors\753e8ee2c77dd87f84a9673b80357894f50e659e19b85c4b9296c8cdaad287e8.json"),
    "294661f7995364205725341e12a281b3be7ad5e2825916bb9b5d0edf06b1ab86": Path(r"D:\AHR13\S19-FINAL-A1\evidence\launch-ledger\launch-record-errors\1923c8b7c9962a68d97b773a9b6efa85d7b85cfcca6d0a006ee3dae8db21d96a.json"),
    "57c3643c1c6d356a5d597ad2796b9743b6c8a379e46d80027c8cf39593ac23a0": Path(r"D:\AHR13\S19-FINAL-A1\evidence\launch-ledger\launch-record-errors\e5d14120970c2ca6ff29a1e335d5ee1b89e6c20987e5079786707c02691cb253.json"),
}
S22_DIAGNOSTIC_RECORDS = {
    "c6d00203fc96d330954320cfdfca7aab2238824de424920ff0819157e45f17b9": Path(r"D:\AHR13\S22-FINAL-A1\evidence\launch-ledger\launch-record-errors\723766198ea1411e21c8d648dd5e92935984503092b7ea9566183799206de82f.json"),
    "d23fc95aa2331a30dcfdb4da88295509ee99db31c007a1d7053bd64019464e94": Path(r"D:\AHR13\S22-FINAL-A1\evidence\launch-ledger\launch-record-errors\861962e9a5e3d9d4680ff436a7433aa45a41375eaf2276680e20415736279418.json"),
    "1f62b9105aca5ff871ef15ae199d3e076a77bcb0c6ae800cf84635b02af92f37": Path(r"D:\AHR13\S22-FINAL-A1\evidence\launch-ledger\launch-record-errors\db095df8d2577abeb489710bfdd2b320aa65b00d291169fed8f016cebf008531.json"),
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class LaunchRecorderFocusedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="bbk-s11-launch-")
        base = Path(self.temp.name)
        self.attempt = base / "attempt evidence with spaces"
        self.cwd = base / "nested cwd with backslash-like spaces"
        self.attempt.mkdir(parents=True)
        self.cwd.mkdir(parents=True)
        for name in ("temp", "cache", "pycache", "tmp"):
            (self.attempt / name).mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def env(self) -> dict[str, str]:
        qualified = os.pathsep.join((str(ROOT), str(ROOT / "tools"), str(SITE)))
        environment = {
            **os.environ,
            "BBK_LAUNCH_RECORD_ROOT": str(self.attempt),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "PYTHONPATH": qualified,
            "BBK_QUALIFIED_PYTHONPATH": qualified,
            "TEMP": str(self.attempt / "temp"),
            "TMP": str(self.attempt / "tmp"),
            "TMPDIR": str(self.attempt / "tmp"),
            "PYTHONPYCACHEPREFIX": str(self.attempt / "pycache"),
            "BBK_TEST_CACHE_DIR": str(self.attempt / "cache"),
        }
        environment.pop(launch_recorder.LEGACY_ROOT_ENV, None)
        return environment

    def child(self, index: int, env: dict[str, str]) -> int:
        script = self.cwd / f"child {index}.py"
        script.write_text("print('nested-child-ok', flush=True)\n", encoding="utf-8")
        command = python_command(script)
        launch = launch_recorder.prepare(
            command,
            cwd=self.cwd,
            environment=env,
            kind="focused-real-child",
            require_evidence_root=True,
        )
        process = subprocess.Popen(
            command,
            cwd=self.cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        launch.started(process.pid)
        process.communicate()
        launch.completed(returncode=process.returncode)
        return int(process.returncode)

    def test_nested_parallel_children_are_atomic_and_deterministic(self) -> None:
        env = self.env()
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            statuses = list(pool.map(lambda number: self.child(number, env), range(4)))
        self.assertEqual(statuses, [0, 0, 0, 0])
        first = launch_recorder.aggregate(self.attempt)
        second = launch_recorder.aggregate(self.attempt)
        self.assertEqual(first["records"], second["records"])
        self.assertEqual(first["record_count"], 4)
        for record in first["records"]:
            self.assertEqual(record["state"], "completed")
            self.assertEqual(record["argv"][0], r"C:\Python313\python.exe")
            self.assertIn("-B", record["argv"][:3])
            self.assertNotRegex(json.dumps(record["argv"]), r"[\x00-\x1f]")
        ledger = self.attempt / launch_recorder.LEDGER_NAME
        self.assertTrue(ledger.is_file())
        self.assertEqual(json.loads(ledger.read_text(encoding="utf-8")), second)

    def test_fail_closed_python_invariants_and_conflicting_roots(self) -> None:
        env = self.env()
        script = self.cwd / "invariant.py"
        script.write_text("pass\n", encoding="utf-8")
        command = python_command(script)
        bad_commands = [
            ["C:\\Python313\\python.exe".replace("313", "312"), *command[1:]],
            [command[0], *command[2:]],
        ]
        for bad in bad_commands:
            with self.assertRaises(launch_recorder.LaunchRecordError):
                launch_recorder.prepare(bad, cwd=self.cwd, environment=env, require_evidence_root=True)
        for key in (
            "PYTHONDONTWRITEBYTECODE", "PYTHONNOUSERSITE", "PYTHONPATH",
            "BBK_QUALIFIED_PYTHONPATH", "TEMP", "TMP", "TMPDIR",
            "PYTHONPYCACHEPREFIX", "BBK_TEST_CACHE_DIR", "BBK_LAUNCH_RECORD_ROOT",
        ):
            changed = dict(env)
            changed.pop(key, None)
            with self.assertRaises(launch_recorder.LaunchRecordError, msg=key):
                launch_recorder.prepare(command, cwd=self.cwd, environment=changed, require_evidence_root=True)
        changed = dict(env)
        changed["BBK_NATIVE_EVIDENCE_ROOT"] = str(self.attempt / "different-root")
        with self.assertRaises(launch_recorder.LaunchRecordError):
            launch_recorder.prepare(command, cwd=self.cwd, environment=changed, require_evidence_root=True)
        for malformed in ("", "   ", "bad\x00root"):
            changed = dict(env)
            changed["BBK_LAUNCH_RECORD_ROOT"] = malformed
            with self.assertRaises(launch_recorder.LaunchRecordError):
                launch_recorder.prepare(command, cwd=self.cwd, environment=changed, require_evidence_root=True)
        for key in ("PYTHONDONTWRITEBYTECODE", "PYTHONNOUSERSITE"):
            changed = dict(env)
            changed[key] = "0"
            with self.assertRaises(launch_recorder.LaunchRecordError):
                launch_recorder.prepare(command, cwd=self.cwd, environment=changed, require_evidence_root=True)

    def test_malformed_incomplete_conflicting_unfinished_and_no_child(self) -> None:
        env = self.env()
        path = launch_recorder.record_no_child(
            argv=[r"C:\Python313\python.exe", "-B", "in-process-check.py"],
            cwd=self.cwd,
            environment=env,
            kind="verification-in-process",
        )
        self.assertIsNotNone(path)
        self.assertEqual(launch_recorder.aggregate(self.attempt)["records"][0]["state"], "no-child")
        records = self.attempt / launch_recorder.RECORDS_DIR
        (records / "malformed.json").write_text("{", encoding="utf-8")
        with self.assertRaises(launch_recorder.LaunchRecordError):
            launch_recorder.aggregate(self.attempt)
        (records / "malformed.json").unlink()
        (records / "unfinished.json").write_text(json.dumps({"schema": launch_recorder.SCHEMA}), encoding="utf-8")
        with self.assertRaises(launch_recorder.LaunchRecordError):
            launch_recorder.aggregate(self.attempt)

    def _manual_record(self, *, pid: int, owner_pid: int, state: str, kind: str = "verification-gate", environment: dict[str, str] | None = None) -> Path:
        command = tuple(python_command(self.cwd / "nested-runner.py"))
        selected_environment = environment or self.env()
        handle = launch_recorder.prepare(
            command,
            cwd=self.cwd,
            environment=selected_environment,
            kind=kind,
            require_evidence_root=True,
        )
        handle.started(pid)
        assert handle._path is not None
        value = json.loads(handle._path.read_text(encoding="utf-8"))
        value["owner_pid"] = owner_pid
        value["owner_scope"] = "parent-process"
        value["state"] = state
        if state != "running":
            value["returncode"] = 0
        handle._path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
        return handle._path

    def _copy_s19_shape(self, record_id: str) -> dict[str, object]:
        document = json.loads(S19_DIAGNOSTIC_RECORDS[record_id].read_text(encoding="utf-8"))
        record = next(item["snapshot"]["value"] for item in document["records"] if item["record_id"] == record_id)
        destination = self.attempt / launch_recorder.RECORDS_DIR / f"{record_id}.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(record, sort_keys=True), encoding="utf-8")
        return record

    def _copy_s22_shape(self, record_id: str, *, pid: int, owner_pid: int) -> Path:
        document = json.loads(S22_DIAGNOSTIC_RECORDS[record_id].read_text(encoding="utf-8"))
        value = next(item["snapshot"]["value"] for item in document["records"] if item["record_id"] == record_id)
        value = dict(value)
        value["pid"] = pid
        value["owner_pid"] = owner_pid
        value["state"] = "running"
        destination = self.attempt / launch_recorder.RECORDS_DIR / f"{record_id}.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
        return destination

    def test_child_scope_excludes_all_s22_external_pending_shapes(self) -> None:
        current = os.getpid()
        paths = [
            self._copy_s22_shape(record_id, pid=current + offset, owner_pid=current - index)
            for index, (record_id, offset) in enumerate(zip(S22_DIAGNOSTIC_RECORDS, (0, 707, 808), strict=True), start=1)
        ]
        completed = self._manual_record(pid=current + 909, owner_pid=current, state="completed")
        ledger = launch_recorder.aggregate(self.attempt, exclude_enclosing_ancestor=True)
        self.assertEqual(ledger["record_count"], 1)
        self.assertEqual(ledger["records"][0]["record_id"], completed.stem)
        self.assertEqual({item["record_id"] for item in ledger["excluded_ancestors"]}, {path.stem for path in paths})
        self.assertTrue(all(item["aggregation"] == "excluded-externally-owned-pending" for item in ledger["excluded_ancestors"]))

    def test_top_level_scope_fails_external_pending_and_malformed_owner(self) -> None:
        current = os.getpid()
        external = self._copy_s22_shape(next(iter(S22_DIAGNOSTIC_RECORDS)), pid=current + 1001, owner_pid=current - 1)
        with self.assertRaises(launch_recorder.LaunchRecordError) as raised:
            launch_recorder.aggregate(self.attempt, exclude_enclosing_ancestor=False)
        self.assertIn(external.stem, str(raised.exception))
        external.unlink()
        malformed = self._manual_record(pid=current + 1002, owner_pid=current - 1, state="running")
        value = json.loads(malformed.read_text(encoding="utf-8"))
        value.pop("owner_pid")
        malformed.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
        with self.assertRaises(launch_recorder.LaunchRecordError):
            launch_recorder.aggregate(self.attempt, exclude_enclosing_ancestor=True)

    def test_s19_enclosing_shapes_use_exact_running_child_pid_predicate(self) -> None:
        for record_id in S19_DIAGNOSTIC_RECORDS:
            record = self._copy_s19_shape(record_id)
            child_pid = record["pid"]
            self.assertEqual(record["state"], "running")
            self.assertNotEqual(record["owner_pid"], child_pid)
            self.assertTrue(launch_recorder._is_enclosing_ancestor(record, child_pid))
            self.assertFalse(launch_recorder._is_enclosing_ancestor(record, record["owner_pid"]))
            (self.attempt / launch_recorder.RECORDS_DIR / f"{record_id}.json").unlink()

    def test_enclosing_predicate_rejects_current_owned_sibling_and_missing_pid(self) -> None:
        current = os.getpid()
        current_owned = {"state": "running", "pid": current, "owner_pid": current}
        sibling = {"state": "running", "pid": current + 100, "owner_pid": current - 1}
        missing = {"state": "running", "owner_pid": current - 1}
        self.assertFalse(launch_recorder._is_enclosing_ancestor(current_owned, current))
        self.assertFalse(launch_recorder._is_enclosing_ancestor(sibling, current))
        self.assertFalse(launch_recorder._is_enclosing_ancestor(missing, current))

    def test_nested_finalization_excludes_only_exact_enclosing_parent_record(self) -> None:
        current = os.getpid()
        ancestor = self._manual_record(pid=current, owner_pid=current - 1, state="running")
        descendant = self._manual_record(pid=current + 1000, owner_pid=current, state="completed")
        ledger = launch_recorder.aggregate(self.attempt, exclude_enclosing_ancestor=True)
        self.assertEqual(ledger["record_count"], 1)
        self.assertEqual(ledger["records"][0]["record_id"], descendant.stem)
        self.assertEqual(len(ledger["excluded_ancestors"]), 1)
        excluded = ledger["excluded_ancestors"][0]
        self.assertEqual(excluded["record_id"], ancestor.stem)
        self.assertEqual(excluded["pid"], current)
        self.assertEqual(excluded["ownership_status"], "externally-owned-pending")
        self.assertNotIn(excluded["record_id"], {record["record_id"] for record in ledger["records"]})

    def test_nested_finalization_fails_on_incomplete_current_process_descendant(self) -> None:
        current = os.getpid()
        self._manual_record(pid=current, owner_pid=current - 1, state="running")
        descendant = self._manual_record(pid=current + 1001, owner_pid=current, state="running")
        with self.assertRaises(launch_recorder.LaunchRecordError) as raised:
            launch_recorder.aggregate(self.attempt, exclude_enclosing_ancestor=True)
        self.assertIn(descendant.stem, str(raised.exception))
        self.assertIn("state=running", str(raised.exception))
        self.assertIn(f"owner_pid={current}", str(raised.exception))
        self.assertIn(f"current_pid={current}", str(raised.exception))
        self.assertIn("owner_scope=parent-process", str(raised.exception))
        self.assertEqual(raised.exception.records[0]["record_id"], descendant.stem)

    def test_runner_ledger_error_preserves_exact_record_context(self) -> None:
        env = self.env()
        record_path = self._manual_record(pid=os.getpid() + 202, owner_pid=os.getpid(), state="running")
        details = {
            "path": str(record_path),
            "record_id": "descendant",
            "state": "running",
            "owner_pid": os.getpid(),
            "current_pid": os.getpid(),
            "owner_scope": "parent-process",
        }
        failure = launch_recorder.LaunchRecordError(
            "incomplete launch state; record_id=descendant state=running owner_pid={owner} current_pid={current} owner_scope=parent-process".format(owner=os.getpid(), current=os.getpid()),
            records=(details,),
        )
        report: dict[str, object] = {}
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(launch_recorder, "finalize", side_effect=failure):
            self.assertFalse(run_tests._attach_launch_ledger(report))
        self.assertEqual(report["launch_ledger_error_records"], [details])
        self.assertEqual(report["launch_ledger_error_context"]["scope"], "current-process")
        diagnostic_path = Path(report["launch_ledger_error_diagnostic"]["path"])
        diagnostic = json.loads(diagnostic_path.read_text(encoding="utf-8"))
        self.assertEqual(diagnostic["exception"]["type"], "LaunchRecordError")
        self.assertIn("incomplete launch state", diagnostic["exception"]["text"])
        self.assertEqual(diagnostic["records"][0]["snapshot"]["status"], "captured")
        self.assertEqual(diagnostic["records"][0]["snapshot"]["value"]["state"], "running")
        self.assertEqual(diagnostic["records"][0]["owner_pid"], os.getpid())
        self.assertEqual(diagnostic["records"][0]["current_pid"], os.getpid())
        self.assertEqual(diagnostic["records"][0]["owner_scope"], "parent-process")
        self.assertEqual(diagnostic["records"][0]["subtree"], "current-process")
        self.assertTrue(diagnostic["material_environment_digest"])

    def test_production_run_tests_attach_enables_child_scope(self) -> None:
        env = self.env()
        current = os.getpid()
        ancestor = self._manual_record(pid=current, owner_pid=current - 1, state="running")
        descendant = self._manual_record(pid=current + 505, owner_pid=current, state="completed")
        report: dict[str, object] = {}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertTrue(run_tests._attach_launch_ledger(report, child_scope=True))
        ledger = report["launch_ledger"]
        self.assertEqual(ledger["record_count"], 1)
        self.assertEqual(ledger["records"][0]["record_id"], descendant.stem)
        self.assertEqual(ledger["excluded_ancestors"][0]["record_id"], ancestor.stem)

    def test_production_verify_report_explicitly_fails_external_pending_record(self) -> None:
        env = self.env()
        current = os.getpid()
        ancestor = self._manual_record(pid=current, owner_pid=current - 1, state="running")
        descendant = self._manual_record(pid=current + 506, owner_pid=current, state="completed")
        with mock.patch.dict(os.environ, env, clear=True), self.assertRaises(launch_recorder.LaunchRecordError) as raised:
            verify_all.report_dict([], expected=0, exit_code=0)
        self.assertIn(ancestor.stem, str(raised.exception))

    def test_incomplete_owned_descendant_is_durably_reported(self) -> None:
        env = self.env()
        if raw_diagnostic_root := (os.environ.get("BBK_S23_DIAGNOSTIC_ROOT") or os.environ.get("BBK_S21_DIAGNOSTIC_ROOT") or os.environ.get("BBK_S20_DIAGNOSTIC_ROOT") or os.environ.get("BBK_S19_DIAGNOSTIC_ROOT")):
            diagnostic_root = Path(raw_diagnostic_root) / "incomplete-descendant"
            (diagnostic_root / launch_recorder.RECORDS_DIR).mkdir(parents=True, exist_ok=True)
            env["BBK_LAUNCH_RECORD_ROOT"] = str(diagnostic_root)
        self._manual_record(pid=os.getpid(), owner_pid=os.getpid() - 1, state="running", environment=env)
        descendant = self._manual_record(pid=os.getpid() + 303, owner_pid=os.getpid(), state="running", environment=env)
        report: dict[str, object] = {}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertFalse(run_tests._attach_launch_ledger(report, child_scope=True))
        diagnostic_path = Path(report["launch_ledger_error_diagnostic"]["path"])
        diagnostic = json.loads(diagnostic_path.read_text(encoding="utf-8"))
        self.assertEqual(diagnostic["exception"]["type"], "LaunchRecordError")
        records = diagnostic["records"]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["path"], str(descendant))
        self.assertEqual(records[0]["snapshot"]["value"]["state"], "running")
        self.assertEqual(records[0]["owner_pid"], os.getpid())
        self.assertEqual(records[0]["current_pid"], os.getpid())
        self.assertEqual(records[0]["owner_scope"], "parent-process")

    def test_unrelated_running_sibling_is_excluded_in_child_scope(self) -> None:
        env = self.env()
        if raw_diagnostic_root := (os.environ.get("BBK_S23_DIAGNOSTIC_ROOT") or os.environ.get("BBK_S21_DIAGNOSTIC_ROOT") or os.environ.get("BBK_S20_DIAGNOSTIC_ROOT")):
            diagnostic_root = Path(raw_diagnostic_root) / "external-sibling"
            (diagnostic_root / launch_recorder.RECORDS_DIR).mkdir(parents=True, exist_ok=True)
            env["BBK_LAUNCH_RECORD_ROOT"] = str(diagnostic_root)
        sibling = self._manual_record(pid=os.getpid() + 404, owner_pid=os.getpid() - 1, state="running", environment=env)
        report: dict[str, object] = {}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertTrue(run_tests._attach_launch_ledger(report, child_scope=True))
        ledger = report["launch_ledger"]
        self.assertEqual(ledger["record_count"], 0)
        self.assertEqual(ledger["excluded_ancestors"][0]["record_id"], sibling.stem)

    def test_report_persistence_and_exact_cli_surfaces(self) -> None:
        env = self.env()
        report_path = self.attempt / "verify report.json"
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(
            verify_all, "run_all_report", return_value=(0, [])
        ):
            self.assertEqual(verify_all.main(["--report-file", str(report_path), "--profile", "standard"]), 0)
        self.assertTrue(report_path.is_file())
        self.assertEqual(json.loads(report_path.read_text(encoding="utf-8"))["schema"], "bbk.verification-report.v1")
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(
            verify_all, "run_all", return_value=0
        ) as runner:
            self.assertEqual(run_tests.main(["--all", "--profile", "standard", "--mode", "batch", "--jobs", "1"]), 0)
        runner.assert_called_once()
        self.assertIn("--all", run_tests.main.__code__.co_consts)

    def test_actual_command_constructors_and_in_process_semantics(self) -> None:
        steps = verify_all.verification_steps(profile="standard", test_mode="batch", jobs=1)
        managed = [step.command for step in steps if step.command and step.command[0].casefold().endswith("python.exe") and not step.in_process]
        self.assertTrue(managed)
        self.assertTrue(all(command[0] == r"C:\Python313\python.exe" and "-B" in command[:3] for command in managed))
        self.assertEqual(run_tests.unittest_command("test_launch_recorder.py")[0], r"C:\Python313\python.exe")
        self.assertEqual(run_tests.unittest_modules_command([ROOT / "tests" / "test_launch_recorder.py"])[0], r"C:\Python313\python.exe")
        spec = next(step for step in steps if step.in_process)
        with mock.patch.dict(os.environ, self.env(), clear=True):
            result = verify_all._execute_python_step_in_process(spec, stream=tempfile.TemporaryFile(mode="w+"))
        self.assertEqual(result.execution, "in-process")
        self.assertTrue((self.attempt / launch_recorder.RECORDS_DIR).exists())
        self.assertEqual(launch_recorder.aggregate(self.attempt)["records"][-1]["state"], "no-child")

    def test_s10_mirror_fixture_bytes_git_context_and_package_exclusions(self) -> None:
        source_paths = (
            (ROOT / "evidence" / "alpha17-rc6-work-unit-dispositions.json", S10_MIRROR / ".s10-gate-only" / "source-evidence-fixtures" / "alpha17-rc6-work-unit-dispositions.json"),
            (ROOT / "evidence" / "qualification" / "deepseek-codex-provider-seam-r4" / "qualification-receipt.json", S10_MIRROR / ".s10-gate-only" / "source-evidence-fixtures" / "qualification-receipt.json"),
        )
        self.assertTrue((S10_MIRROR / ".git").is_dir())
        for source, mirror in source_paths:
            self.assertEqual(source.read_bytes(), mirror.read_bytes())
            relative = "evidence/alpha17-rc6-work-unit-dispositions.json" if source.name.startswith("alpha17") else "evidence/qualification/deepseek-codex-provider-seam-r4/qualification-receipt.json"
            shown = subprocess.run(["git", "-C", str(S10_MIRROR), "show", f"HEAD:{relative}"], check=True, capture_output=True).stdout
            self.assertEqual(shown, source.read_bytes())
        manifest = json.loads((ROOT / "PACKAGE-MANIFEST.json").read_text(encoding="utf-8"))
        files = [str(item.get("path", "")) for item in manifest.get("files", []) if isinstance(item, dict)]
        self.assertIn("evidence/alpha17-rc6-work-unit-dispositions.json", files)
        self.assertIn("evidence/qualification/deepseek-codex-provider-seam-r4/qualification-receipt.json", files)
        self.assertIn("evidence/qualification/session-inspector-oracle-alpha17.json", files)
        self.assertFalse(any(any(part in path.replace("\\", "/").lower() for part in ("__pycache__", ".pyc", ".bbk/", "/cache/", "/temp/")) for path in files))

    def test_manifest_control_closure_is_separate_and_source_sanity_is_clean(self) -> None:
        manifest = json.loads((ROOT / "PACKAGE-MANIFEST.json").read_text(encoding="utf-8"))
        files = {str(item.get("path", "")) for item in manifest.get("files", []) if isinstance(item, dict)}
        self.assertNotIn("PACKAGE-MANIFEST.json", files)
        closure = build_release.package_control_closure(manifest)
        self.assertEqual(closure[-1], ROOT / "PACKAGE-MANIFEST.json")
        self.assertEqual(sum(path == ROOT / "PACKAGE-MANIFEST.json" for path in closure), 1)
        self.assertEqual(
            source_sanity.text_encoding_violations(
                ROOT / "third_party" / "codex-deepseek-subagent" / "tests" / "test_plaintext_handoff.py"
            ),
            [],
        )

    def test_strict_subject_excludes_candidate_carrier_and_keeps_rc9_control(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bbk-mirror-subject-") as raw:
            root = Path(raw)
            (root / "candidate.json").write_text("{\"id\": \"carrier\"}\n", encoding="utf-8")
            (root / "product.txt").write_text("product\n", encoding="utf-8")
            self.assertNotIn("candidate.json", verify_package.actual_files(root))
        manifest = json.loads((ROOT / "PACKAGE-MANIFEST.json").read_text(encoding="utf-8"))
        files = {item["path"] for item in manifest["files"]}
        self.assertIn("evidence/qualification/omp-host-contract-rc9.json", files)
        self.assertNotIn("candidate.json", files)

    def test_timeout_finally_closes_record_without_masking_failure(self) -> None:
        env = self.env()
        command = tuple(python_command(ROOT / "tools" / "run_tests.py", "--all"))

        class FakeProcess:
            pid = 31313
            returncode = 2

            def __init__(self) -> None:
                self.terminated = False

            def poll(self):
                return self.returncode if self.terminated else None

            def wait(self, timeout=None):
                self.terminated = True
                return self.returncode

        process = FakeProcess()

        def terminate(fake):
            fake.terminated = True

        original_completed = launch_recorder.LaunchHandle.completed
        completion_calls = 0

        def complete_after_one_failure(handle, *, returncode, state="completed", error=None):
            nonlocal completion_calls
            completion_calls += 1
            if completion_calls == 1:
                raise launch_recorder.LaunchRecordError("simulated persistence failure")
            return original_completed(handle, returncode=returncode, state=state, error=error)

        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(
            run_tests.subprocess, "Popen", return_value=process
        ), mock.patch.object(run_tests, "_terminate_process_tree", side_effect=terminate), mock.patch.object(
            run_tests.time, "monotonic", side_effect=[0.0, 2.0]
        ), mock.patch.object(
            launch_recorder.LaunchHandle,
            "completed",
            autospec=True,
            side_effect=complete_after_one_failure,
        ), mock.patch.object(run_tests, "read_structured_test_report", return_value=run_tests._empty_structured_test_report()):
            result = run_tests._execute_unittest_command(command, label="simulated-timeout", timeout=1.0)
        self.assertEqual(result.returncode, 2)
        ledger = launch_recorder.aggregate(self.attempt)
        self.assertEqual(ledger["record_count"], 1)
        self.assertEqual(ledger["records"][0]["state"], "timed-out")
        self.assertEqual(ledger["records"][0]["returncode"], 2)
        self.assertIn("simulated persistence failure", ledger["records"][0]["error"])
        self.assertNotIn("launch finalized during runner cleanup", ledger["records"][0]["error"])
        self.assertNotIn("running", {record["state"] for record in ledger["records"]})

    def _qualification_fixture(self) -> tuple[Path, Path, dict[str, str]]:
        candidate = self.attempt / "sealed candidate with spaces"
        candidate.mkdir()
        (candidate / "candidate.json").write_text(json.dumps({"id": "CAND-S12"}), encoding="utf-8")
        (candidate / "bbk-seal-receipt.json").write_text(json.dumps({"packageId": "bbk-artifact-hardening-candidate", "contentSha256": "a" * 64, "manifestSha256": "b" * 64}), encoding="utf-8")
        source = self.attempt / "mirror source with spaces"
        source.mkdir()
        return candidate, source, {"candidate_id": "CAND-S12", "content_sha256": "a" * 64, "manifest_sha256": "b" * 64}

    def test_standard_qualification_has_exact_seven_bound_operations(self) -> None:
        candidate, source, binding = self._qualification_fixture()
        steps = verify_all.standard_qualification_steps(candidate=candidate, source_root=source)
        self.assertEqual(len(steps), 7)
        self.assertEqual([step.name for step in steps], [
            "PRE sealed artifact verify", "STRICT package verification",
            "FAST verification without duplicate package checks", "STANDARD verification without duplicate package checks",
            "RELEASE verification without duplicate package checks", "A13 native Windows artifact tests", "POST sealed artifact verify",
        ])
        self.assertTrue(all(step.command[0] == r"C:\Python313\python.exe" and "-B" in step.command[:3] for step in steps))
        self.assertEqual(steps[0].command[-3:], ("artifact", "verify", str(candidate)))
        self.assertEqual(steps[1].command[-1], "--strict-mode")
        fast_start = steps[2].command.index("--test-mode")
        self.assertEqual(steps[2].command[fast_start:fast_start + 4], ("--test-mode", "batch", "--jobs", "1"))
        standard_start = steps[3].command.index("--test-mode")
        release_start = steps[4].command.index("--test-mode")
        self.assertEqual(steps[3].command[standard_start:standard_start + 4], ("--test-mode", "pooled", "--jobs", "0"))
        self.assertEqual(steps[4].command[release_start:release_start + 4], ("--test-mode", "pooled", "--jobs", "0"))
        self.assertIn("--skip-package-manifest", steps[3].command)
        self.assertIn("--profile", steps[4].command)
        for index in (2, 3, 4):
            self.assertEqual(steps[index].command.count("--launch-child-scope"), 1)
        for index in (0, 1, 5, 6):
            self.assertNotIn("--launch-child-scope", steps[index].command)
        self.assertEqual(steps[5].command[-7:], ("--mode", "isolated", "--jobs", "1", "--pattern", "test_artifact_windows_native.py", "--no-timing-report"))
        self.assertEqual(steps[6].command[-3:], ("artifact", "verify", str(candidate)))
        self.assertEqual(binding["candidate_id"], "CAND-S12")

    def test_standard_qualification_binding_and_failure_semantics(self) -> None:
        candidate, source, binding = self._qualification_fixture()
        with self.assertRaises(verify_all.QualificationBindingError):
            verify_all._qualification_candidate_binding(str(candidate), "WRONG", binding["content_sha256"], binding["manifest_sha256"], str(source))
        evidence = self.attempt / "qualification evidence"
        report = self.attempt / "qualification report.json"
        calls: list[str] = []

        def product_failure(spec):
            calls.append(spec.name)
            return verify_all.CheckResult(spec.name, spec.command, "FAIL" if len(calls) == 1 else "PASS", 1 if len(calls) == 1 else 0, "", "product failure" if len(calls) == 1 else None)

        exit_code, results, value = verify_all.run_standard_qualification(candidate=candidate, source_root=source, report_path=report, evidence_root=evidence, executor=product_failure)
        self.assertEqual(exit_code, 1)
        self.assertEqual(len(results), 7)
        self.assertTrue(report.is_file())
        self.assertEqual(value["checks_expected"], 7)
        calls.clear()

        def method_failure(spec):
            calls.append(spec.name)
            return verify_all.CheckResult(spec.name, spec.command, "FAIL", 2, "", "LaunchRecordError: recorder failure")

        exit_code, results, value = verify_all.run_standard_qualification(candidate=candidate, source_root=source, report_path=report, evidence_root=evidence, executor=method_failure)
        self.assertEqual(exit_code, 2)
        self.assertEqual(len(results), 1)
        self.assertEqual(value["qualification"]["stop_reason"], "managed launch-recorder or Python invariant failure")

    def test_standard_qualification_wiring_preserves_public_facade_and_forbids_shell_paths(self) -> None:
        source = (ROOT / "tools" / "verify_all.py").read_text(encoding="utf-8")
        self.assertNotIn("shell=True", source)
        self.assertNotIn("python -c", source)
        self.assertIn("execute_step", source)
        self.assertIn("run_tests.py", source)
        self.assertIn("--standard-qualification", source)
        self.assertEqual(run_tests.main.__name__, "main")

    def test_verify_all_child_scope_flag_controls_actual_report_aggregation(self) -> None:
        env = self.env()
        current = os.getpid()
        ancestor = self._manual_record(pid=current, owner_pid=current - 1, state="running", environment=env)
        with mock.patch.dict(os.environ, env, clear=True):
            child = verify_all.report_dict([], expected=0, exit_code=0, launch_child_scope=True)
            self.assertEqual(child["launch_ledger"]["excluded_ancestors"][0]["record_id"], ancestor.stem)
        with mock.patch.dict(os.environ, env, clear=True), self.assertRaises(launch_recorder.LaunchRecordError):
            verify_all.report_dict([], expected=0, exit_code=0, launch_child_scope=False)

    def test_verify_all_launch_error_is_durable_before_raise(self) -> None:
        env = self.env()
        self._manual_record(pid=os.getpid() + 1, owner_pid=os.getpid(), state="running", environment=env)
        with mock.patch.dict(os.environ, env, clear=True), self.assertRaises(launch_recorder.LaunchRecordError):
            verify_all.report_dict([], expected=0, exit_code=0, launch_child_scope=True)
        diagnostics = sorted((self.attempt / "launch-record-errors").glob("*.json"))
        self.assertTrue(diagnostics)
        diagnostic = json.loads(diagnostics[-1].read_text(encoding="utf-8"))
        self.assertEqual(diagnostic["schema"], "bbk.launch-record-error.v1")
        self.assertEqual(diagnostic["exception"]["type"], "LaunchRecordError")
        self.assertTrue(diagnostic["records"])


if __name__ == "__main__":
    unittest.main()
