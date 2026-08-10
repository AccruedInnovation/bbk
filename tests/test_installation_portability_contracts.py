"""Portability and verification-reporting regression contracts."""
from __future__ import annotations

import ast
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path, PureWindowsPath
from unittest import mock

from tests._path_support import source_ast

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {relative_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


generate_agents = load_module("bbk_generate_agents_contracts", "tools/generate_agents.py")
run_tests = load_module("bbk_run_tests_contracts", "tools/run_tests.py")


class Alpha91PortabilityTests(unittest.TestCase):

    def test_child_report_sidecar_is_private_and_not_stdout_marker(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            tests = root / "tests"
            tests.mkdir()
            (tests / "test_sidecar.py").write_text(
                "import unittest\nclass Sidecar(unittest.TestCase):\n    def test_ok(self): self.assertTrue(True)\n",
                encoding="utf-8",
            )
            report = root / "private-report.json"
            env = os.environ.copy()
            env["BBK_TEST_REPORT_JSON"] = str(report)
            completed = subprocess.run(
                [sys.executable, str(ROOT / "tools" / "test_module_runner.py"), "--discover", "test_sidecar.py"],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertNotIn("BBK_TEST_REPORT_JSON:", completed.stdout)
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["selected"], ["test_sidecar.Sidecar.test_ok"])
            self.assertEqual(payload["executed"], payload["selected"])
            self.assertEqual(payload["skipped"], [])
            self.assertEqual(payload["not_run"], [])

    def test_nested_stdout_report_marker_does_not_contaminate_parent_identity_ledger(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            tests = root / "tests"
            tests.mkdir()
            test_file = tests / "test_nested_marker.py"
            test_file.write_text(
                "import unittest\n"
                "class NestedMarker(unittest.TestCase):\n"
                "    def test_actual(self):\n"
                "        print('BBK_TEST_REPORT_JSON:{\"selected\":[\"nested.fake\"],\"executed\":[\"nested.fake\"],\"skipped\":[],\"not_run\":[]}')\n"
                "        self.assertTrue(True)\n",
                encoding="utf-8",
            )
            with mock.patch.object(run_tests, "ROOT", root), mock.patch.object(run_tests, "TESTS", tests):
                self.assertEqual(run_tests.run_test_files([test_file], stream=io.StringIO()), 0)
            report = run_tests.LAST_RUN_REPORT
            self.assertIsNotNone(report)
            self.assertEqual(report["test_ids"]["selected"], ["test_nested_marker.NestedMarker.test_actual"])

    def test_repository_rejects_duplicate_unittest_method_names(self):
        for path in sorted((ROOT / "tests").glob("test*.py")):
            tree = source_ast(path)
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                names = [item.name for item in node.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name.startswith("test")]
                self.assertEqual(len(names), len(set(names)), f"duplicate test method in {path}:{node.name}")

    def test_structured_test_identity_report_partitions_counts(self):
        first = run_tests.SuiteResult("a", 0, "", 2, (), 1,
                                     ("a.test_pass", "a.test_skip"),
                                     ("a.test_pass", "a.test_skip"),
                                     ("a.test_skip",), ())
        second = run_tests.SuiteResult("b", 0, "", 1, (), 0,
                                      ("b.test_pass",), ("b.test_pass",), (), ())
        report = run_tests._identity_report([first, second])
        ids = report["test_ids"]
        self.assertEqual(set(ids["selected"]), {"a.test_pass", "a.test_skip", "b.test_pass"})
        self.assertTrue(set(ids["executed"]).isdisjoint(ids["skipped"]))
        self.assertEqual(set(ids["skipped"]), {"a.test_skip"})
        self.assertEqual(set(ids["executed"]) | set(ids["skipped"]) | set(ids["not_run"]), set(ids["selected"]))
        self.assertEqual(report["selected_count"], len(ids["selected"]))

    def test_projection_manifest_path_serialization_is_host_independent(self):
        root = PureWindowsPath("D:\\Projects\\BBK\\bbk-0.1.0-alpha.9.1")
        path = root / "projections" / "codex" / "agents" / "bbk_architect.toml"
        source = root / "spec" / "roles.json"
        self.assertEqual(generate_agents.portable_relative_path(path, root), "projections/codex/agents/bbk_architect.toml")
        self.assertEqual(generate_agents.portable_relative_path(source, root), "spec/roles.json")

    def test_packaged_projection_manifest_contains_only_portable_paths(self):
        manifest = json.loads((ROOT / "projections" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["source"], "spec/roles.json")
        self.assertTrue(manifest["files"])
        self.assertTrue(all(("\\" not in path for path in manifest["files"])))

    def test_stdout_test_runner_preserves_success_exit_contract(self):
        class PassingTest(unittest.TestCase):
            def runTest(self):
                self.assertTrue(True)
        stream = io.StringIO()
        result = run_tests.run_suite(unittest.TestSuite([PassingTest()]), stream=stream, verbosity=2)
        self.assertTrue(result.wasSuccessful())
        self.assertIn("runTest", stream.getvalue())
        self.assertIn("OK", stream.getvalue())

    def test_current_verification_docs_use_the_stdout_runner(self):
        for relative_path in ("docs/INSTALL.md", "docs/DEVELOPMENT.md"):
            text = (ROOT / relative_path).read_text(encoding="utf-8")
            self.assertIn("python tools/run_tests.py --profile", text, relative_path)
            self.assertIn("-v", text, relative_path)
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("docs/INSTALL.md", readme)


class Alpha93VerificationReportingTests(unittest.TestCase):

    def test_problem_parser_captures_failure_and_error_causes(self):
        output = textwrap.dedent('''            test_bad (sample.Case.test_bad) ... FAIL
            test_boom (sample.Case.test_boom) ... ERROR

            ======================================================================
            ERROR: test_boom (sample.Case.test_boom)
            ----------------------------------------------------------------------
            Traceback (most recent call last):
              File "sample.py", line 8, in test_boom
                raise RuntimeError("boom")
            RuntimeError: boom

            ======================================================================
            FAIL: test_bad (sample.Case.test_bad)
            ----------------------------------------------------------------------
            Traceback (most recent call last):
              File "sample.py", line 5, in test_bad
                self.assertEqual(1, 2)
            AssertionError: 1 != 2

            ----------------------------------------------------------------------
            Ran 2 tests in 0.001s

            FAILED (failures=1, errors=1)
            ''')
        issues = run_tests.parse_issues(output)
        self.assertEqual(run_tests.parse_test_count(output), 2)
        self.assertEqual([issue.kind for issue in issues], ["ERROR", "FAIL"])
        self.assertEqual(issues[0].cause, "RuntimeError: boom")
        self.assertEqual(issues[1].cause, "AssertionError: 1 != 2")

    def test_final_summary_lists_every_problem_and_exit_code(self):
        result = run_tests.SuiteResult(name="test_sample.py", returncode=1, output="", tests_run=2, issues=(run_tests.TestIssue("ERROR", "test_boom (sample.Case.test_boom)", "RuntimeError: boom"), run_tests.TestIssue("FAIL", "test_bad (sample.Case.test_bad)", "AssertionError: 1 != 2")))
        stream = io.StringIO()
        run_tests.print_final_summary([result], expected_suites=1, exit_code=1, stream=stream)
        summary = stream.getvalue()
        for phrase in ("BBK FINAL TEST SUMMARY", "Result: FAILED", "Errors: 1", "Failed suites:", "- test_sample.py: exit code 1", "Failures: 1", "[ERROR] test_boom", "Cause: RuntimeError: boom", "[FAIL] test_bad", "Cause: AssertionError: 1 != 2", "Exit code: 1"):
            self.assertIn(phrase, summary)

    def test_runner_end_to_end_repeats_failure_and_error_at_the_end(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            tests = root / "tests"
            tests.mkdir()
            test_file = tests / "test_deliberate.py"
            test_file.write_text(textwrap.dedent('''                    import unittest

                    class DeliberateTests(unittest.TestCase):
                        def test_a_failure(self):
                            self.assertEqual(1, 2)

                        def test_b_error(self):
                            raise RuntimeError("deliberate boom")
                    '''), encoding="utf-8")
            stream = io.StringIO()
            with mock.patch.object(run_tests, "ROOT", root), mock.patch.object(run_tests, "TESTS", tests):
                code = run_tests.run_test_files([test_file], verbose=True, stream=stream)
            output = stream.getvalue()
            summary_position = output.rfind("BBK FINAL TEST SUMMARY")
            self.assertEqual(code, 1)
            self.assertGreater(summary_position, 0)
            final_summary = output[summary_position:]
            self.assertIn("Result: FAILED", final_summary)
            self.assertIn("- test_deliberate.py: exit code 1", final_summary)
            self.assertIn("test_a_failure", final_summary)
            self.assertIn("Cause: AssertionError: 1 != 2", final_summary)
            self.assertIn("test_b_error", final_summary)
            self.assertIn("Cause: RuntimeError: deliberate boom", final_summary)
            self.assertIn("Exit code: 1", final_summary)

    def test_runner_end_to_end_prints_clean_final_summary(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            tests = root / "tests"
            tests.mkdir()
            test_file = tests / "test_passing.py"
            test_file.write_text(textwrap.dedent('''                    import unittest

                    class PassingTests(unittest.TestCase):
                        def test_passes(self):
                            self.assertTrue(True)
                    '''), encoding="utf-8")
            stream = io.StringIO()
            with mock.patch.object(run_tests, "ROOT", root), mock.patch.object(run_tests, "TESTS", tests):
                code = run_tests.run_test_files([test_file], verbose=True, stream=stream)
            output = stream.getvalue()
            final_summary = output[output.rfind("BBK FINAL TEST SUMMARY"):]
            self.assertEqual(code, 0)
            self.assertIn("Result: PASS", final_summary)
            self.assertIn("No failures or errors.", final_summary)
            self.assertIn("Exit code: 0", final_summary)

    def test_installer_replacement_regression_uses_filesystem_identity(self):
        source = (ROOT / "tests" / "test_core_contracts.py").read_text(encoding="utf-8")
        self.assertIn(".samefile(target)", source)
        self.assertNotIn('item["path"] == target.as_posix()', source)


# Deterministic fast/standard/release selection used by tools/run_tests.py.
from tests._test_profiles import load_profiled_tests as load_tests
