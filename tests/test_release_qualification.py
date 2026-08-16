from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import release_qualification  # noqa: E402
from gate_kernel import canonical_digest  # noqa: E402
from jsonschema import Draft202012Validator  # noqa: E402

SCHEMA_PATH = ROOT / "spec" / "schemas" / "bbk-alpha17-qualification-report-v2.schema.json"
ORACLE_PATH = ROOT / "evidence" / "qualification" / "session-inspector-oracle-alpha17.json"
HOST_CONTRACT_PATH = ROOT / "evidence" / "qualification" / "omp-host-contract-rc9.json"
JJ = os.environ.get("BBK_TEST_JJ") or shutil.which("jj")
BD = os.environ.get("BBK_TEST_BD") or shutil.which("bd")
MISE = os.environ.get("BBK_TEST_MISE") or shutil.which("mise")


def validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def assert_report_digest(test: unittest.TestCase, report: dict[str, object]) -> None:
    core = {key: value for key, value in report.items() if key != "report_digest"}
    test.assertEqual(f"sha256:{canonical_digest(core)}", report["report_digest"])


class ReleaseQualificationPureTests(unittest.TestCase):
    def test_qualification_schema_is_valid_draft_2020_12(self) -> None:
        validator()

    def test_public_release_excludes_completed_implementation_mapping_checklist(self) -> None:
        retired = ROOT / "IMPLEMENTATION-MAPPING-CHECKLIST-COMPLETED.md"
        self.assertFalse(retired.exists(), "the retired internal implementation checklist must not ship")
        dispositions = json.loads(
            (ROOT / "evidence" / "alpha17-rc6-work-unit-dispositions.json").read_text(encoding="utf-8")
        )
        dangling = [
            unit.get("id")
            for unit in dispositions.get("work_units", [])
            if "IMPLEMENTATION-MAPPING-CHECKLIST-COMPLETED.md" in unit.get("evidence_refs", [])
        ]
        self.assertEqual([], dangling, "release evidence must not reference the retired checklist")

    def test_structured_failure_is_schema_valid_digest_bound_and_blocks_gate(self) -> None:
        report = release_qualification._error_result(  # noqa: SLF001 - release failure contract
            release_qualification.QualificationError(
                "SUBSTRATE_MISE_UNAVAILABLE",
                "real mise executable was not supplied",
                details={"source": "test"},
            )
        )
        validator().validate(report)
        assert_report_digest(self, report)
        self.assertEqual("AUTOMATED_FAIL", report["qualification"])
        self.assertEqual("BLOCK_AUTOMATED", report["gate"]["decision"])
        self.assertEqual("NOT_REACHED", report["gate"]["manual_provider_gate"])
        self.assertEqual("FAIL", report["assertions"]["VER-036"])

    def test_human_report_uses_the_canonical_gate_identifier(self) -> None:
        report = release_qualification._error_result(  # noqa: SLF001 - release rendering contract
            release_qualification.QualificationError("QUALIFICATION_TEST_BLOCK", "blocked")
        )
        rendered = release_qualification.render_human_report(report)
        self.assertIn("`GATE-017-AUTOMATED` → `BLOCK_AUTOMATED`", rendered)
        self.assertIn("VER-036", rendered)


@unittest.skipUnless(
    all(value and Path(value).is_file() for value in (JJ, BD, MISE)),
    "real jj, bd, and mise are required",
)
class ReleaseQualificationVerticalSliceTests(unittest.TestCase):
    def test_alpha17_real_local_vertical_slice_passes_all_required_invariants(self) -> None:
        with tempfile.TemporaryDirectory() as raw, mock.patch.dict(os.environ, {"BBK_BD": ""}, clear=False):
            report = release_qualification.run_alpha17_automated(
                jj_path=JJ,
                bd_path=BD,
                mise_path=MISE,
                temporary_parent=Path(raw),
            )
            temporary_root = str(Path(raw).resolve())

        validator().validate(report)
        assert_report_digest(self, report)
        self.assertEqual("PASS", report["status"])
        self.assertEqual("0.1.0-alpha.17.0.2.1", report["release"])
        self.assertEqual("0.1.0-alpha.17.0.2", report["release_source"])
        self.assertEqual("AUTOMATED_PASS", report["qualification"])
        self.assertEqual("RC_ELIGIBLE", report["gate"]["decision"])
        self.assertEqual("PENDING_WU_018", report["gate"]["manual_provider_gate"])
        self.assertEqual("PASS", report["assertions"]["VER-036"])

        oracle = report["session_inspector_oracle"]
        self.assertEqual("0.1.0-alpha.17.0.2.1", oracle["current_release"])
        self.assertEqual("0.1.0-alpha.17.0.2", oracle["release_source"])
        self.assertEqual("PREDECESSOR_RELEASE_EVIDENCE", oracle["reuse_status"])
        self.assertIn("does not requalify", oracle["claim_limit"])
        self.assertEqual("PASS", oracle["assertions"]["VER-035"])
        self.assertEqual(
            f"sha256:{__import__('hashlib').sha256(ORACLE_PATH.read_bytes()).hexdigest()}",
            oracle["evidence_digest"],
        )

        workers = report["workers"]
        self.assertEqual(2, len({item["session_id"] for item in workers}))
        self.assertEqual(2, len({item["attempt_id"] for item in workers}))
        self.assertEqual(2, len({item["jj_change_id"] for item in workers}))
        self.assertEqual(2, len({item["workspace_label"] for item in workers}))
        self.assertEqual(
            ["backend/result.json", "frontend/result.json"],
            sorted(path for item in workers for path in item["changed_paths"]),
        )

        integration = report["integration"]
        self.assertEqual(
            ["backend/result.json", "frontend/result.json"],
            integration["integrated_paths"],
        )
        self.assertEqual(
            integration["candidate"]["digest"],
            report["qualified_task"]["candidate_digest"],
        )
        self.assertTrue(report["qualified_task"]["candidate_unchanged"])
        self.assertEqual("PASS", report["qualified_task"]["status"])

        self.assertEqual({"REVIEW", "VALIDATION"}, {item["kind"] for item in report["assurance"]})
        self.assertEqual(
            {"bbk_reviewer", "bbk_validator"},
            {item["role"] for item in report["assurance"]},
        )
        self.assertTrue(
            all(item["write_surface_attestation"] == "READ_ONLY_CONFIRMED" for item in report["assurance"])
        )

        check_by_id = {item["id"]: item for item in report["checks"]}
        self.assertTrue(all(item["status"] == "PASS" for item in report["checks"]))
        self.assertEqual(
            "ROLE_CAPABILITY_FORBIDDEN",
            check_by_id["A17-004-root-orchestrator-product-write-blocked"]["evidence"]["reason_code"],
        )
        self.assertIn("A17-013-session-inspector-oracle-bound", check_by_id)
        self.assertIn("A17-014-keyless-omp-dispatch-rewrite-bound", check_by_id)
        self.assertIn("A17-015-keyless-omp-yield-validation-bound", check_by_id)
        self.assertIn("A17-016-advertised-governance-surfaces-bound", check_by_id)
        self.assertIn("A17-017-report-inputs-complete", check_by_id)
        self.assertEqual(
            [
                "bbk_control_bind",
                "bbk_control_dispatch_status",
                "bbk_governance_status",
                "bbk_task_run",
            ],
            check_by_id["A17-016-advertised-governance-surfaces-bound"]["evidence"]["surfaces"],
        )
        self.assertEqual(
            ["ACTIVATED", "ACTIVATED", "TERMINAL", "TERMINAL"],
            sorted(
                item["status"]
                for item in check_by_id["A17-016-advertised-governance-surfaces-bound"]["evidence"]["dispatch_lifecycles"]
            ),
        )
        self.assertFalse(
            check_by_id["A17-016-advertised-governance-surfaces-bound"]["evidence"]["status_query_mutated_journal"]
        )
        host_contract = report["tools"]["host_contract"]
        self.assertEqual("QUALIFIED_KEYLESS_OMP_HOST", host_contract["mode"])
        self.assertEqual("PASS", host_contract["assertions"]["VER-021"])
        self.assertEqual(
            f"sha256:{__import__('hashlib').sha256(HOST_CONTRACT_PATH.read_bytes()).hexdigest()}",
            host_contract["evidence_digest"],
        )

        counts = report["receipt_accounting"]["counts"]
        for kind in (
            "WORK_UNIT_ATTEMPT_REGISTRATION",
            "SPAWN_ADMISSION",
            "SPAWN_SESSION_ACTIVATION",
            "BEADS_PROJECTION",
            "FILESYSTEM_MUTATION",
            "VCS_MUTATION",
            "CANDIDATE_INTEGRATION",
            "QUALIFIED_TASK",
            "BOUND_QUALIFIED_TASK",
            "READ_ONLY_TASK_REGISTRATION",
            "ASSURANCE_RECORD",
        ):
            self.assertGreaterEqual(counts[kind], 1)

        serialized = json.dumps(report, sort_keys=True)
        self.assertNotIn(temporary_root, serialized)
        self.assertFalse(report["security"]["external_provider_used"])
        self.assertFalse(report["security"]["network_used"])
        self.assertFalse(report["security"]["credentials_used"])
        self.assertEqual([], report["security"]["waivers"])

    def test_alpha17_real_local_vertical_slice_handles_deep_windows_temp(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            deep_parent = Path(raw)
            for name in ("deep-temp-" + "x" * 20,):
                deep_parent /= name
            deep_parent.mkdir(parents=True)
            with mock.patch.dict(
                os.environ,
                {
                    "BBK_BD": "",
                    "BBK_QUALIFICATION_TEMP_ROOT": r"D:\q10",
                    "TEMP": str(deep_parent),
                    "TMP": str(deep_parent),
                    "TMPDIR": str(deep_parent),
                },
                clear=False,
            ):
                report = release_qualification.run_alpha17_automated(
                    jj_path=JJ,
                    bd_path=BD,
                    mise_path=MISE,
                    temporary_parent=deep_parent,
                )

        validator().validate(report)
        assert_report_digest(self, report)
        self.assertEqual("PASS", report["status"])
        self.assertEqual("AUTOMATED_PASS", report["qualification"])
        self.assertEqual("PASS", report["assertions"]["VER-036"])
        self.assertNotIn(str(deep_parent), json.dumps(report, sort_keys=True))
        self.assertFalse(any(Path(r"D:\q10").glob("bbk-alpha17-qualification-*")))


if __name__ == "__main__":
    unittest.main()
