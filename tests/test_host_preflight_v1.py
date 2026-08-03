from __future__ import annotations

import datetime as dt
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import host_preflight
from artifact_packages import validate_schema_instance


def request(requirements: list[dict], freshness: int = 3600) -> dict:
    return {
        "schema": "bbk.host-preflight-request.v1",
        "requestId": "HP-TEST",
        "freshnessSeconds": freshness,
        "requirements": requirements,
    }


class HostPreflightV1Tests(unittest.TestCase):
    def test_template_and_result_validate_and_only_named_capabilities_are_probed(self) -> None:
        template = json.loads((ROOT / "templates" / "host-preflight-request.json").read_text(encoding="utf-8"))
        self.assertEqual(validate_schema_instance(template, "bbk.host-preflight-request.v1"), [])
        seen: list[str] = []
        original = host_preflight._probe

        def capture(item, timeout):
            seen.append(item["id"])
            return original(item, timeout)

        with tempfile.TemporaryDirectory() as temp, mock.patch.object(host_preflight, "_probe", side_effect=capture):
            value = host_preflight.run_preflight(
                request([
                    {"id": "python", "kind": "COMMAND", "required": True, "command": Path(sys.executable).name, "versionArgs": ["--version"], "expectedVersionPattern": r"Python 3\."},
                    {"id": "workspace", "kind": "PATH", "required": True, "path": temp, "expectedKind": "DIRECTORY", "access": ["READ"]},
                ]),
                use_cache=False,
            )
        self.assertEqual(seen, ["python", "workspace"])
        self.assertEqual(value["status"], "PASS")
        self.assertEqual(validate_schema_instance(value, "bbk.host-preflight-result.v1"), [])
        self.assertIn("not execution authorization", value["authorityBoundary"])

    def test_all_six_statuses_are_observable_and_environment_values_are_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            existing = Path(temp)
            missing = existing / "missing"
            req = request([
                {"id": "available", "kind": "COMMAND", "required": False, "command": Path(sys.executable).name, "versionArgs": ["--version"], "expectedVersionPattern": r"Python 3\."},
                {"id": "unavailable", "kind": "PATH", "required": False, "path": str(missing)},
                {"id": "mismatch", "kind": "COMMAND", "required": False, "command": Path(sys.executable).name, "versionArgs": ["--version"], "expectedVersionPattern": r"definitely-not-this-version"},
                {"id": "permission", "kind": "PATH", "required": False, "path": str(existing), "access": ["WRITE"]},
                {"id": "unknown", "kind": "COMMAND", "required": False, "command": Path(sys.executable).name, "versionArgs": "invalid"},
                {"id": "live", "kind": "LIVE", "required": False, "description": "exact live device window"},
                {"id": "secret", "kind": "ENVIRONMENT", "required": False, "name": "BBK_PREFLIGHT_SECRET"},
            ])
            real_access = os.access

            def access(path, mode):
                if Path(path) == existing and mode == os.W_OK:
                    return False
                return real_access(path, mode)

            with mock.patch.object(host_preflight.os, "access", side_effect=access), mock.patch.dict(os.environ, {"BBK_PREFLIGHT_SECRET": "must-not-leak"}):
                value = host_preflight.run_preflight(req, use_cache=False)
        by_id = {item["id"]: item for item in value["observations"]}
        self.assertEqual(by_id["available"]["status"], "AVAILABLE")
        self.assertEqual(by_id["unavailable"]["status"], "UNAVAILABLE")
        self.assertEqual(by_id["mismatch"]["status"], "VERSION_MISMATCH")
        self.assertEqual(by_id["permission"]["status"], "PERMISSION_BLOCKED")
        self.assertEqual(by_id["unknown"]["status"], "UNKNOWN")
        self.assertEqual(by_id["live"]["status"], "REQUIRES_LIVE_PROBE")
        self.assertEqual(by_id["secret"]["status"], "AVAILABLE")
        self.assertTrue(by_id["secret"]["valueRedacted"])
        self.assertNotIn("must-not-leak", json.dumps(value))

    def test_required_non_available_status_blocks_without_becoming_authority(self) -> None:
        value = host_preflight.run_preflight(
            request([{"id": "live", "kind": "LIVE", "required": True, "description": "confirm machine access"}]),
            use_cache=False,
        )
        self.assertEqual(value["status"], "BLOCKED")
        self.assertEqual(value["requiredCapabilityBlockers"], ["live"])
        self.assertIn("execution authorization", value["claimsNotEstablished"])

    def test_cache_is_bound_to_host_requirements_tool_identity_and_freshness(self) -> None:
        now = dt.datetime(2026, 8, 3, 12, 0, tzinfo=dt.timezone.utc)
        req = request([{"id": "python", "kind": "COMMAND", "required": True, "command": Path(sys.executable).name, "versionArgs": ["--version"]}], freshness=120)
        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp)
            first = host_preflight.run_preflight(req, cache_dir=cache, now=now)
            second = host_preflight.run_preflight(req, cache_dir=cache, now=now + dt.timedelta(seconds=30))
            changed = request([{"id": "python", "kind": "COMMAND", "required": True, "command": Path(sys.executable).name, "versionArgs": ["-VV"]}], freshness=120)
            third = host_preflight.run_preflight(changed, cache_dir=cache, now=now + dt.timedelta(seconds=30))
            with mock.patch.object(host_preflight, "host_identity", return_value={**first["host"], "node": "other", "digest": "0" * 64}):
                fourth = host_preflight.run_preflight(req, cache_dir=cache, now=now + dt.timedelta(seconds=30))
        self.assertFalse(first["cache"]["hit"])
        self.assertTrue(second["cache"]["hit"])
        self.assertNotEqual(first["cache"]["key"], third["cache"]["key"])
        self.assertNotEqual(first["cache"]["key"], fourth["cache"]["key"])

    def test_duplicate_requirement_ids_fail_closed(self) -> None:
        with self.assertRaises(host_preflight.HostPreflightError):
            host_preflight.run_preflight(request([
                {"id": "same", "kind": "LIVE", "required": False, "description": "a"},
                {"id": "same", "kind": "LIVE", "required": False, "description": "b"},
            ]), use_cache=False)


if __name__ == "__main__":
    unittest.main()
