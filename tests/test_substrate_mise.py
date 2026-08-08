from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from governed_state import all_receipts  # noqa: E402
from substrate import mise_adapter  # noqa: E402
from tests._fake_executable import write_python_executable  # noqa: E402


class MiseAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "project"
        self.root.mkdir()
        (self.root / "mise.toml").write_text(
            '[tasks."test:pass"]\nrun = "echo pass"\n\n[tasks."test:fail"]\nrun = "exit 7"\n',
            encoding="utf-8",
        )
        self.fake = write_python_executable(
            Path(self.temporary.name) / "mise",
            "import sys\n"
            "args = sys.argv[1:]\n"
            "if args == ['--version']:\n"
            "    print('mise TEST-1.0')\n"
            "    raise SystemExit(0)\n"
            "if args[:2] == ['run', 'test:pass']:\n"
            "    print('pass-output')\n"
            "    raise SystemExit(0)\n"
            "if args[:2] == ['run', 'test:fail']:\n"
            "    print('fail-output', file=sys.stderr)\n"
            "    raise SystemExit(7)\n"
            "raise SystemExit(9)\n",
        )
        self.environment = {**os.environ, "BBK_ALLOW_TEST_ADAPTER": "1", "PATH": os.environ.get("PATH", "")}
        os.environ["BBK_ALLOW_TEST_ADAPTER"] = "1"

    def tearDown(self):
        os.environ.pop("BBK_ALLOW_TEST_ADAPTER", None)
        self.temporary.cleanup()

    def request(self, task="test:pass", key="task-1"):
        return {
            "schema": "bbk.qualified-task-request.v1",
            "binding_ref": "binding:1",
            "task": task,
            "candidate_digest": "sha256:" + "a" * 64,
            "toolchain_definition_digest": mise_adapter.toolchain_definition_digest(self.root),
            "idempotency_key": key,
            "arguments": [],
            "environment_allowlist": ["LANG"],
        }

    def test_fake_adapter_executes_only_with_explicit_test_authority_and_receipts_output_digest(self):
        result = mise_adapter.execute(
            self.root, self.request(), mise_path_value=self.fake, test_adapter=True, environment=self.environment
        )
        self.assertEqual("PASS", result["status"])
        self.assertEqual(0, result["exit_status"])
        self.assertRegex(result["output_digest"], r"^sha256:[0-9a-f]{64}$")
        receipt = next(item for item in all_receipts(self.root) if item["receipt_kind"] == "QUALIFIED_TASK")
        self.assertEqual("TEST_ADAPTER", receipt["content"]["adapter_class"])
        with self.assertRaisesRegex(mise_adapter.MiseAdapterError, "REAL_ADAPTER_REQUIRED"):
            mise_adapter.assert_release_qualified(receipt)

    def test_candidate_workspace_execution_keeps_receipt_outside_candidate(self):
        candidate = Path(self.temporary.name) / "candidate"
        candidate.mkdir()
        (candidate / "mise.toml").write_text(
            '[tasks."test:pass"]\nrun = "echo pass"\n',
            encoding="utf-8",
        )
        request = self.request(key="separate-root")
        request["toolchain_definition_digest"] = mise_adapter.toolchain_definition_digest(candidate)
        result = mise_adapter.execute(
            self.root, request, mise_path_value=self.fake, test_adapter=True,
            environment=self.environment, execution_root=candidate,
        )
        self.assertEqual("PASS", result["status"])
        self.assertFalse((candidate / ".bbk").exists())
        receipts = [item for item in all_receipts(self.root) if item["receipt_kind"] == "QUALIFIED_TASK"]
        self.assertEqual(1, len(receipts))

    def test_exact_retry_reuses_receipt_without_rerun(self):
        request = self.request()
        first = mise_adapter.execute(self.root, request, mise_path_value=self.fake, test_adapter=True, environment=self.environment)
        self.fake = write_python_executable(self.fake, "raise SystemExit(99)\n")
        retry = mise_adapter.execute(self.root, request, mise_path_value=self.fake, test_adapter=True, environment=self.environment)
        self.assertTrue(retry["idempotent_reuse"])
        self.assertEqual(first["receipt_id"], retry["receipt_id"])

    def test_failure_is_truthfully_recorded(self):
        result = mise_adapter.execute(
            self.root, self.request(task="test:fail", key="task-fail"), mise_path_value=self.fake,
            test_adapter=True, environment=self.environment,
        )
        self.assertEqual("FAIL", result["status"])
        self.assertEqual(7, result["exit_status"])

    def test_undeclared_task_and_stale_config_digest_block_before_effect(self):
        with self.assertRaisesRegex(mise_adapter.MiseAdapterError, "TASK_NOT_DECLARED"):
            mise_adapter.execute(
                self.root, self.request(task="other", key="other"), mise_path_value=self.fake,
                test_adapter=True, environment=self.environment,
            )
        request = self.request(key="stale")
        request["toolchain_definition_digest"] = "sha256:" + "b" * 64
        with self.assertRaisesRegex(mise_adapter.MiseAdapterError, "DIGEST_MISMATCH"):
            mise_adapter.execute(
                self.root, request, mise_path_value=self.fake, test_adapter=True, environment=self.environment
            )

    def test_sensitive_environment_and_unbound_config_mutation_are_rejected(self):
        request = self.request(key="secret")
        request["environment_allowlist"] = ["API_KEY"]
        with self.assertRaisesRegex(mise_adapter.MiseAdapterError, "SENSITIVE_ENVIRONMENT"):
            mise_adapter.execute(self.root, request, mise_path_value=self.fake, test_adapter=True, environment=self.environment)
        with self.assertRaisesRegex(mise_adapter.MiseAdapterError, "CONFIG_MUTATION_AUTHORITY"):
            mise_adapter.assert_task_config_mutation_authority({
                "request": {"role": "bbk_root_orchestrator", "scope": {"mutation_classes": ["TOOLCHAIN_CONFIGURATION"], "semantic_scope": ["toolchain"]}}
            })
        mise_adapter.assert_task_config_mutation_authority({
            "request": {"role": "bbk_worker", "scope": {"mutation_classes": ["TOOLCHAIN_CONFIGURATION"], "semantic_scope": ["FOUNDATION_TOOLCHAIN"]}}
        })

    def test_missing_real_mise_has_exact_release_blocker(self):
        with self.assertRaisesRegex(mise_adapter.MiseAdapterError, "SUBSTRATE_MISE_UNAVAILABLE"):
            mise_adapter.execute(self.root, self.request(), mise_path_value=None, test_adapter=False, environment={"PATH": ""})


if __name__ == "__main__":
    unittest.main()
