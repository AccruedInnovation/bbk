from __future__ import annotations

import importlib.util
import io
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {relative_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


run_tests = load_module("bbk_alpha93_run_tests", "tools/run_tests.py")


class Alpha93VerificationReportingTests(unittest.TestCase):
    def test_problem_parser_captures_failure_and_error_causes(self):
        output = textwrap.dedent(
            """\
            test_bad (sample.Case.test_bad) ... FAIL
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
            """
        )
        issues = run_tests.parse_issues(output)
        self.assertEqual(run_tests.parse_test_count(output), 2)
        self.assertEqual([issue.kind for issue in issues], ["ERROR", "FAIL"])
        self.assertEqual(issues[0].cause, "RuntimeError: boom")
        self.assertEqual(issues[1].cause, "AssertionError: 1 != 2")

    def test_final_summary_lists_every_problem_and_exit_code(self):
        result = run_tests.SuiteResult(
            name="test_sample.py",
            returncode=1,
            output="",
            tests_run=2,
            issues=(
                run_tests.TestIssue("ERROR", "test_boom (sample.Case.test_boom)", "RuntimeError: boom"),
                run_tests.TestIssue("FAIL", "test_bad (sample.Case.test_bad)", "AssertionError: 1 != 2"),
            ),
        )
        stream = io.StringIO()
        run_tests.print_final_summary([result], expected_suites=1, exit_code=1, stream=stream)
        summary = stream.getvalue()
        self.assertIn("BBK FINAL TEST SUMMARY", summary)
        self.assertIn("Result: FAILED", summary)
        self.assertIn("Errors: 1", summary)
        self.assertIn("Failed suites:", summary)
        self.assertIn("- test_sample.py: exit code 1", summary)
        self.assertIn("Failures: 1", summary)
        self.assertIn("[ERROR] test_boom", summary)
        self.assertIn("Cause: RuntimeError: boom", summary)
        self.assertIn("[FAIL] test_bad", summary)
        self.assertIn("Cause: AssertionError: 1 != 2", summary)
        self.assertIn("Exit code: 1", summary)

    def test_runner_end_to_end_repeats_failure_and_error_at_the_end(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            tests = root / "tests"
            tests.mkdir()
            test_file = tests / "test_deliberate.py"
            test_file.write_text(
                textwrap.dedent(
                    """\
                    import unittest

                    class DeliberateTests(unittest.TestCase):
                        def test_a_failure(self):
                            self.assertEqual(1, 2)

                        def test_b_error(self):
                            raise RuntimeError("deliberate boom")
                    """
                ),
                encoding="utf-8",
            )
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
            test_file.write_text(
                textwrap.dedent(
                    """\
                    import unittest

                    class PassingTests(unittest.TestCase):
                        def test_passes(self):
                            self.assertTrue(True)
                    """
                ),
                encoding="utf-8",
            )
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
        source = (ROOT / "tests" / "test_alpha6_congruence.py").read_text(encoding="utf-8")
        self.assertIn(".samefile(target)", source)
        self.assertNotIn('item["path"] == target.as_posix()', source)


if __name__ == "__main__":
    unittest.main()
