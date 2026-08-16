from __future__ import annotations

import ctypes
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
HELPER = Path(__file__).with_name("_artifact_windows_native_helper.py")
PYTHON = Path(r"C:/Python313/python.exe")
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import artifact_packages
import artifact_platform


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(artifact_packages.canonical_json_bytes(value))


EVIDENCE_ROOT = Path(os.environ["BBK_NATIVE_EVIDENCE_ROOT"]) if os.environ.get("BBK_NATIVE_EVIDENCE_ROOT") else None


def evidence(name: str, value: object) -> None:
    if EVIDENCE_ROOT is not None:
        write_json(EVIDENCE_ROOT / name, value)


def wait_for(path: Path, timeout: float = 30.0) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
        time.sleep(0.01)
    raise AssertionError(f"control record did not appear: {path}")


def release(path: Path, token: str) -> None:
    write_json(path, {"command": "release", "token": token, "timestamp": artifact_packages.utc_now()})


def make_project(parent: Path, package_id: str = "native-fixture") -> tuple[Path, Path]:
    project = parent / package_id
    draft = project / "draft"
    draft.mkdir(parents=True)
    (draft / "payload.bin").write_bytes(b"native payload\x00\xff\r\n")
    write_json(
        draft / artifact_packages.DRAFT_FILE,
        {
            "schema": "bbk.artifact-package-draft.v1",
            "packageId": package_id,
            "revision": "1",
            "profile": {"id": "generic", "version": "1"},
            "subject": {"kind": "native-test", "id": package_id, "revision": "1"},
            "predecessor": None,
            "artifacts": [{"artifactId": "payload", "path": "payload.bin", "role": "semantic", "references": []}],
        },
    )
    return project, draft


def helper(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(PYTHON), str(HELPER), *args], cwd=cwd, text=True, capture_output=True, timeout=180)


@unittest.skipUnless(os.name == "nt", "A13 requires a real Windows host")
class NativeArtifactProducerTests(unittest.TestCase):
    def test_environment_receipt_is_native_windows_and_doctor_qualified(self):
        self.assertEqual(os.name, "nt")
        self.assertTrue(PYTHON.is_file(), PYTHON)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            doctor = artifact_packages.doctor(root, root)
            self.assertEqual(doctor["status"], "PASS", doctor)
            self.assertEqual(doctor["environment"]["os"], "nt")
            self.assertEqual(doctor["environment"]["python"], "3.13.12")
            self.assertTrue(doctor["capabilities"]["osLocks"]["status"] == "PASS")
            evidence("environment-receipt.json", {"node": platform.node(), "hostname": platform.node(), "windows": platform.platform(), "architecture": platform.machine(), "python": sys.version, "python_executable": str(PYTHON), "bbk_package_root": str(artifact_packages.PACKAGE_ROOT), "command": "C:/Python313/python.exe tools/run_tests.py --profile standard --mode isolated --jobs 1 --pattern test_artifact_windows_native.py --no-timing-report", "workspace": str(ROOT), "temp_root": os.environ.get("TEMP"), "cache_root": os.environ.get("BBK_TEST_CACHE_DIR"), "doctor": doctor, "limitations": ["power-loss durability unclaimed"]})

    def test_real_createfile_handle_and_exact_six_sharing_attempts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "held.bin"
            target.write_bytes(b"original")
            ready, release_file, done = root / "ready.json", root / "release.json", root / "done.json"
            token = "handle-attempt-1"
            proc = subprocess.Popen(
                [str(PYTHON), str(HELPER), "hold-handle", str(target), "--ready", str(ready), "--release", str(release_file), "--done", str(done), "--token", token],
                cwd=ROOT,
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            record = wait_for(ready)
            self.assertEqual(record["command"], "hold-handle")
            self.assertEqual(record["share_mode"], 0)
            journal: dict[str, object] = {
                "retryObservations": [],
            }

            def create_with_native_error() -> None:
                kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
                create = kernel32.CreateFileW
                create.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
                create.restype = ctypes.c_void_p
                handle = create(str(target), 0x80000000, 0, None, 3, 0x02000000, None)
                invalid = ctypes.c_void_p(-1).value
                if handle not in (None, invalid):
                    kernel32.CloseHandle(handle)
                    raise AssertionError("held native handle did not block exclusive open")
                raise ctypes.WinError(ctypes.get_last_error())

            try:
                with self.assertRaises(artifact_packages.ArtifactPackageError) as raised:
                    artifact_packages.retry_sharing(create_with_native_error, effect="native-held-handle", journal=journal)
                self.assertEqual(raised.exception.result["code"], "PACKAGE_PUBLISH_BLOCKED")
            finally:
                release(release_file, token)
                self.assertEqual(proc.wait(timeout=30), 0)
            self.assertEqual([item["delayMs"] for item in journal["retryObservations"]], [0, 25, 50, 100, 200, 400])
            self.assertTrue(all(item["win32Error"] in (32, 33) for item in journal["retryObservations"]))
            self.assertEqual(wait_for(done)["released"], True)
            self.assertEqual(target.read_bytes(), b"original")
            evidence("native-sharing.json", {"command": f"C:/Python313/python.exe {HELPER} hold-handle {target} --ready {ready} --release {release_file} --done {done} --token {token}", "ready": record, "retry": journal, "done": json.loads(done.read_text(encoding="utf-8")), "target_bytes": len(target.read_bytes()), "claim_limits": ["producer evidence only", "no independent assertion pass"]})

    def test_namespace_before_package_lock_order_and_no_age_pid_takeover(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            namespace = root / "namespace.lock"
            ready, release_file, done = root / "ready.json", root / "release.json", root / "done.json"
            token = "lock-owner-token"
            proc = subprocess.Popen([str(PYTHON), str(HELPER), "hold-os-lock", str(namespace), "--token", token, "--ready", str(ready), "--release", str(release_file), "--done", str(done)], cwd=ROOT, text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            first = wait_for(ready)
            self.assertEqual(first["status"], "PASS")
            try:
                second_result = root / "second.json"
                second = helper("hold-os-lock", str(namespace), "--token", "different-token", "--result", str(second_result))
                self.assertNotEqual(second.returncode, 0)
                second_record = json.loads(second_result.read_text(encoding="utf-8"))
                self.assertIn(second_record["status"], {"SHARING_RETRYABLE", "FAILED"})
                os.utime(namespace, (1, 1))
                third = helper("hold-os-lock", str(namespace), "--token", "aged-token", "--result", str(root / "third.json"))
                self.assertNotEqual(third.returncode, 0)
            finally:
                release(release_file, token)
                self.assertEqual(proc.wait(timeout=30), 0)
                self.assertTrue(wait_for(done)["released"])
            evidence("native-locks.json", {"command": f"C:/Python313/python.exe {HELPER} hold-os-lock {namespace} --token {token} --ready {ready} --release {release_file} --done {done}", "owner": first, "contenders": [json.loads(second_result.read_text(encoding="utf-8")), json.loads((root / "third.json").read_text(encoding="utf-8"))], "done": json.loads(done.read_text(encoding="utf-8")), "no_age_pid_takeover": True})

    def test_separate_process_finalize_and_conflict_preserves_existing_target_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project, draft = make_project(root, "finalize-native")
            result_path = root / "finalize.json"
            result = helper("finalize", str(draft), "--project-root", str(project), "--result", str(result_path))
            self.assertEqual(result.returncode, 0, result.stderr)
            value = json.loads(result_path.read_text(encoding="utf-8"))
            self.assertEqual(value["status"], "PASS", value)
            journal = json.loads(Path(value["journalPath"]).read_text(encoding="utf-8"))
            self.assertEqual(journal["phase"], "COMPLETED")
            self.assertEqual([item["kind"] for item in journal["locks"]], ["PUBLICATION_NAMESPACE", "PACKAGE_ID"])
            self.assertEqual(len({item["token"] for item in journal["locks"]}), 1)
            project2, draft2 = make_project(root, "conflict-native")
            target = project2 / ".bbk" / "artifacts" / "sealed" / "conflict-native-1"
            target.mkdir(parents=True)
            (target / "preserve.txt").write_bytes(b"existing-target")
            receipt = project2 / ".bbk" / "artifacts" / "publications" / "conflict-native-1.json"
            receipt.parent.mkdir(parents=True, exist_ok=True)
            receipt.write_bytes(b"existing-receipt")
            target_before, receipt_before = (target / "preserve.txt").read_bytes(), receipt.read_bytes()
            result2 = helper("finalize", str(draft2), "--project-root", str(project2), "--result", str(root / "conflict.json"))
            self.assertNotEqual(result2.returncode, 0)
            conflict = json.loads((root / "conflict.json").read_text(encoding="utf-8"))
            self.assertEqual(conflict.get("code"), "PACKAGE_FINALIZE_PUBLICATION_EXISTS")
            self.assertEqual((target / "preserve.txt").read_bytes(), target_before)
            self.assertEqual(receipt.read_bytes(), receipt_before)
            evidence("native-finalize-conflict.json", {"finalize_command": f"C:/Python313/python.exe {HELPER} finalize {draft} --project-root {project} --result {result_path}", "finalize": value, "journal": journal, "conflict_command": f"C:/Python313/python.exe {HELPER} finalize {draft2} --project-root {project2} --result {root / 'conflict.json'}", "conflict": conflict, "preserved_target_sha256": artifact_packages.sha256_bytes(target_before), "preserved_receipt_sha256": artifact_packages.sha256_bytes(receipt_before)})

    def test_crash_after_each_durable_phase_is_reconciled_without_draft_reread(self):
        phases = ["DOCTOR_PASSED", "LOCKS_HELD", "DRAFT_SNAPSHOTTED", "STAGE_MATERIALIZED", "STAGE_VERIFIED", "PUBLISH_INTENT_RECORDED", "TARGET_PUBLISHED", "TARGET_VERIFIED_INITIAL", "RECEIPT_PUBLISHED", "RECEIPT_VERIFIED", "TARGET_VERIFIED_DECISIVE", "CURRENT_PROJECTED", "CURRENT_VERIFIED"]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for index, phase in enumerate(phases):
                project, draft = make_project(root, f"crash-{index}")
                draft_before = (draft / artifact_packages.DRAFT_FILE).read_bytes()
                phase_record = root / f"phase-{index}.json"
                result = helper("crash-at-phase", str(draft), "--project-root", str(project), "--phase", phase, "--phase-record", str(phase_record))
                self.assertNotEqual(result.returncode, 0, phase)
                record = wait_for(phase_record)
                self.assertEqual(record["phase"], phase)
                journals = sorted((project / ".bbk" / "artifacts" / "operations").glob("*.json"))
                self.assertEqual(len(journals), 1, phase)
                journal_before = journals[0].read_bytes()
                journal = artifact_packages.load_path(journals[0])
                self.assertEqual(journal["phase"], phase)
                self.assertEqual(journal["disposition"], "ACTIVE")
                reconciled = artifact_packages.reconcile_operation(journals[0])
                self.assertEqual(reconciled["status"], "PASS")
                self.assertTrue(reconciled["readOnly"])
                self.assertFalse(reconciled["regenerated"])
                self.assertEqual(journals[0].read_bytes(), journal_before)
                self.assertEqual((draft / artifact_packages.DRAFT_FILE).read_bytes(), draft_before)
                evidence(f"crash-{index:02d}-{phase}.json", {"command": f"C:/Python313/python.exe {HELPER} crash-at-phase {draft} --project-root {project} --phase {phase} --phase-record {phase_record}", "phase_record": record, "journal": journal, "reconcile": reconciled, "journal_sha256_before_reconcile": artifact_packages.sha256_bytes(journal_before), "draft_sha256": artifact_packages.sha256_bytes(draft_before), "regenerated": False})


if __name__ == "__main__":
    unittest.main()


