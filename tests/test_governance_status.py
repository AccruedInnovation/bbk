from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import governance_status  # noqa: E402
import governed_state  # noqa: E402
import omp_binding_registry as registry  # noqa: E402
from tests._alpha17_surface_support import control_parent, schema_validate  # noqa: E402


class GovernanceStatusTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "campaign"
        self.root.mkdir()
        self.binding = control_parent(registry, self.root)
        governed_state.append_receipt(
            self.root,
            "TEST_EVIDENCE",
            {"schema": "bbk.test-evidence.v1", "status": "PASS"},
            receipt_id="sha256:" + "a" * 64,
            recorded_at="2026-08-04T00:00:01Z",
        )

    def tearDown(self):
        self.temporary.cleanup()

    def request(self, **changes):
        value = {
            "schema": "bbk.governance-status-query.v1",
            "host_version": "omp/16.4.8",
            "session_id": "parent-session-1",
            "invocation_id": "parent-invocation-1",
            "binding_ref": self.binding["binding_id"],
        }
        value.update(changes)
        return value

    def snapshot(self):
        return {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in sorted((self.root / ".bbk").rglob("*"))
            if path.is_file()
        }

    def test_query_returns_current_binding_and_does_not_mutate_governance_state(self):
        schema_validate(self.request(), "bbk-governance-status-query-v1.schema.json")
        before = self.snapshot()
        result = governance_status.query_status(self.root, self.request())
        after = self.snapshot()
        schema_validate(result, "bbk-governance-status-query-result-v1.schema.json")
        self.assertEqual(before, after)
        self.assertEqual("PASS", result["status"])
        self.assertEqual(self.binding["binding_id"], result["binding"]["binding_ref"])
        self.assertEqual("bbk_root_orchestrator", result["binding"]["role"])
        self.assertGreaterEqual(result["journal"]["binding_count"], 1)
        self.assertGreaterEqual(result["journal"]["receipt_count"], 1)
        self.assertEqual("QUALIFIED", result["enforcement"]["qualification"])
        self.assertEqual("ENFORCED", result["enforcement"]["boundaries"]["task_spawn_tool_call"])

    def test_binding_can_be_resolved_by_session_without_cwd_authority(self):
        request = self.request(binding_ref="", invocation_id="")
        ambient = Path(self.temporary.name) / "ambient"
        ambient.mkdir()
        previous = Path.cwd()
        try:
            import os
            os.chdir(ambient)
            result = governance_status.query_status(self.root, request)
        finally:
            os.chdir(previous)
        self.assertEqual(self.binding["binding_id"], result["binding"]["binding_ref"])

    def test_wrong_session_or_invocation_fails_closed(self):
        with self.assertRaisesRegex(governance_status.GovernanceStatusError, "CORRELATION_MISMATCH"):
            governance_status.query_status(self.root, self.request(session_id="wrong-session"))
        with self.assertRaisesRegex(governance_status.GovernanceStatusError, "CORRELATION_MISMATCH"):
            governance_status.query_status(self.root, self.request(invocation_id="wrong-invocation"))

    def test_stale_binding_capability_and_stale_manifest_are_rejected(self):
        stale, _ = registry.create_initial_binding(
            self.root,
            {
                **self.binding["request"],
                "session_id": "stale-session",
                "invocation_id": "stale-invocation",
                "idempotency_key": "stale-binding",
            },
            capability_ref="role:bbk_root_orchestrator@stale",
        )
        with self.assertRaisesRegex(governance_status.GovernanceStatusError, "CAPABILITY_BINDING_MISMATCH"):
            governance_status.query_status(
                self.root,
                self.request(
                    session_id="stale-session",
                    invocation_id="stale-invocation",
                    binding_ref=stale["binding_id"],
                ),
            )

        capability_root = Path(self.temporary.name) / "capabilities"
        shutil.copytree(ROOT / "spec" / "role-capabilities", capability_root)
        path = capability_root / "bbk_root_orchestrator.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["allowed_tools"] = [item for item in value["allowed_tools"] if item != "bbk_governance_status"]
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaisesRegex(governance_status.GovernanceStatusError, "CAPABILITY_DIGEST_MISMATCH"):
            governance_status.query_status(self.root, self.request(), capability_root=capability_root)

    def test_unknown_request_field_is_rejected(self):
        with self.assertRaisesRegex(governance_status.GovernanceStatusError, "SCHEMA_INVALID"):
            governance_status.query_status(self.root, self.request(ambient_cwd="forbidden"))


if __name__ == "__main__":
    unittest.main()
