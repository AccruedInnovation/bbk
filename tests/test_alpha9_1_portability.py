from __future__ import annotations

import importlib.util
import io
import json
import unittest
from pathlib import Path, PureWindowsPath

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {relative_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


generate_agents = load_module("bbk_generate_agents", "tools/generate_agents.py")
run_tests = load_module("bbk_run_tests", "tools/run_tests.py")


class Alpha91PortabilityTests(unittest.TestCase):
    def test_projection_manifest_path_serialization_is_host_independent(self):
        root = PureWindowsPath(r"D:\Projects\BBK\bbk-0.1.0-alpha.9.1")
        path = root / "projections" / "codex" / "agents" / "bbk_architect.toml"
        source = root / "spec" / "roles.json"
        self.assertEqual(
            generate_agents.portable_relative_path(path, root),
            "projections/codex/agents/bbk_architect.toml",
        )
        self.assertEqual(generate_agents.portable_relative_path(source, root), "spec/roles.json")

    def test_packaged_projection_manifest_contains_only_portable_paths(self):
        manifest = json.loads((ROOT / "projections" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["source"], "spec/roles.json")
        self.assertTrue(manifest["files"])
        self.assertTrue(all("\\" not in path for path in manifest["files"]))

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
        for relative_path in ("docs/DEVELOPMENT.md", "docs/QUALIFICATION.md"):
            text = (ROOT / relative_path).read_text(encoding="utf-8")
            self.assertIn("python tools/run_tests.py -v", text, relative_path)


if __name__ == "__main__":
    unittest.main()
