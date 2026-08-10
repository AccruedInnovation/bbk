from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from tests._path_support import assert_same_path  # noqa: E402
from tests._fake_executable import write_python_executable  # noqa: E402
from tests._vcs_fixture import init_jj, prepare_git_seed, assert_isolated  # noqa: E402
from substrate import jj_adapter  # noqa: E402


JJ = os.environ.get("BBK_TEST_JJ") or shutil.which("jj")


@unittest.skipUnless(JJ, "real jj executable not configured")
class JjAdapterIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.seed = prepare_git_seed(
            Path(self.temporary.name) / "repo",
            files={"base.txt": b"base\n"}, fixture_id="jj-adapter",
        )
        self.root = self.seed.root
        init_jj(self.seed, jj_path=JJ)

    def tearDown(self):
        self.temporary.cleanup()

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def jj(self, *args, cwd=None):
        return subprocess.run([str(JJ), "--no-pager", "--color=never", *args], cwd=cwd or self.root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def test_two_attempts_receive_distinct_changes_and_workspaces(self):
        baseline = self.jj("log", "-r", "@-", "--no-graph", "-T", 'commit_id ++ "\\n"').stdout.strip()
        first = jj_adapter.allocate_workspace(
            self.root, Path(self.temporary.name) / "wu1", work_unit_id="WU-1", attempt_id="A-1",
            parent_revision=baseline, description="WU-1 A-1", jj_path=JJ,
        )
        second = jj_adapter.allocate_workspace(
            self.root, Path(self.temporary.name) / "wu2", work_unit_id="WU-2", attempt_id="A-1",
            parent_revision=baseline, description="WU-2 A-1", jj_path=JJ,
        )
        self.assertNotEqual(first["jj_change_id"], second["jj_change_id"])
        self.assertNotEqual(first["workspace_path"], second["workspace_path"])
        self.assertEqual("CREATED", first["status"])
        self.assertEqual("CREATED", second["status"])

    def test_jj_store_is_local_and_workspace_roots_are_distinct(self):
        baseline = self.jj("log", "-r", "@-", "--no-graph", "-T", 'commit_id ++ "\\n"').stdout.strip()
        first = jj_adapter.allocate_workspace(
            self.root, Path(self.temporary.name) / "one", work_unit_id="WU-ONE", attempt_id="A-1",
            parent_revision=baseline, description="one", jj_path=JJ,
        )
        second = jj_adapter.allocate_workspace(
            self.root, Path(self.temporary.name) / "two", work_unit_id="WU-TWO", attempt_id="A-1",
            parent_revision=baseline, description="two", jj_path=JJ,
        )
        self.assertNotEqual(first["workspace_path"], second["workspace_path"])
        assert_isolated(self.root, Path(first["workspace_path"]), Path(second["workspace_path"]))

    def test_exact_retry_reuses_workspace_but_collision_blocks(self):
        baseline = self.jj("log", "-r", "@-", "--no-graph", "-T", 'commit_id ++ "\\n"').stdout.strip()
        destination = Path(self.temporary.name) / "wu1"
        first = jj_adapter.allocate_workspace(
            self.root, destination, work_unit_id="WU-1", attempt_id="A-1", parent_revision=baseline,
            description="WU-1 A-1", jj_path=JJ,
        )
        retry = jj_adapter.allocate_workspace(
            self.root, destination, work_unit_id="WU-1", attempt_id="A-1", parent_revision=baseline,
            description="WU-1 A-1", jj_path=JJ,
        )
        self.assertEqual("REUSED", retry["status"])
        self.assertEqual(first["jj_change_id"], retry["jj_change_id"])
        with self.assertRaisesRegex(jj_adapter.JjAdapterError, "COLLISION"):
            jj_adapter.allocate_workspace(
                self.root, Path(self.temporary.name) / "other", work_unit_id="WU-1", attempt_id="A-1",
                parent_revision=baseline, description="collision", jj_path=JJ,
            )

    def test_content_neutral_merge_integrates_disjoint_paths_and_rejects_overlap(self):
        baseline = self.jj("log", "-r", "@-", "--no-graph", "-T", 'commit_id ++ "\n"').stdout.strip()
        first = jj_adapter.allocate_workspace(
            self.root, Path(self.temporary.name) / "source-a", work_unit_id="WU-A", attempt_id="A-1",
            parent_revision=baseline, description="source A", jj_path=JJ,
        )
        second = jj_adapter.allocate_workspace(
            self.root, Path(self.temporary.name) / "source-b", work_unit_id="WU-B", attempt_id="A-1",
            parent_revision=baseline, description="source B", jj_path=JJ,
        )
        first_root = Path(first["workspace_path"])
        second_root = Path(second["workspace_path"])
        (first_root / "a").mkdir(); (first_root / "a" / "value.txt").write_text("A\n", encoding="utf-8")
        (second_root / "b").mkdir(); (second_root / "b" / "value.txt").write_text("B\n", encoding="utf-8")
        merged = jj_adapter.merge_content_neutral(
            self.root, Path(self.temporary.name) / "integrated", work_unit_id="WU-I", attempt_id="I-1",
            source_revisions=[first["jj_change_id"], second["jj_change_id"]],
            parent_revision=baseline, description="integrate A and B", jj_path=JJ,
        )
        merged_root = Path(merged["workspace_path"])
        self.assertEqual("INTEGRATED", merged["status"])
        self.assertEqual(["a/value.txt", "b/value.txt"], merged["integrated_paths"])
        self.assertEqual(
            ["a/value.txt", "b/value.txt"],
            jj_adapter.changed_paths_between(
                merged_root,
                from_revision=baseline,
                to_revision=merged["jj_change_id"],
                jj_path=JJ,
            ),
        )
        self.assertEqual("A\n", (merged_root / "a" / "value.txt").read_text(encoding="utf-8"))
        self.assertEqual("B\n", (merged_root / "b" / "value.txt").read_text(encoding="utf-8"))
        self.assertEqual("CONTENT_NEUTRAL_DISJOINT_PATHS", merged["integration_mode"])

        third = jj_adapter.allocate_workspace(
            self.root, Path(self.temporary.name) / "source-c", work_unit_id="WU-C", attempt_id="A-1",
            parent_revision=baseline, description="source C", jj_path=JJ,
        )
        fourth = jj_adapter.allocate_workspace(
            self.root, Path(self.temporary.name) / "source-d", work_unit_id="WU-D", attempt_id="A-1",
            parent_revision=baseline, description="source D", jj_path=JJ,
        )
        (Path(third["workspace_path"]) / "same.txt").write_text("C\n", encoding="utf-8")
        (Path(fourth["workspace_path"]) / "same.txt").write_text("D\n", encoding="utf-8")
        blocked_destination = Path(self.temporary.name) / "blocked-integration"
        with self.assertRaisesRegex(jj_adapter.JjAdapterError, "PATH_OVERLAP"):
            jj_adapter.merge_content_neutral(
                self.root, blocked_destination, work_unit_id="WU-I2", attempt_id="I-1",
                source_revisions=[third["jj_change_id"], fourth["jj_change_id"]],
                parent_revision=baseline, description="must block", jj_path=JJ,
            )
        self.assertFalse(blocked_destination.exists())

    def test_changed_paths_and_operation_recovery_identity(self):
        baseline = self.jj("log", "-r", "@-", "--no-graph", "-T", 'commit_id ++ "\\n"').stdout.strip()
        item = jj_adapter.allocate_workspace(
            self.root, Path(self.temporary.name) / "wu1", work_unit_id="WU-1", attempt_id="A-1",
            parent_revision=baseline, description="WU-1 A-1", jj_path=JJ,
        )
        workspace = Path(item["workspace_path"])
        (workspace / "base.txt").write_text("changed\n", encoding="utf-8")
        self.assertEqual(["base.txt"], jj_adapter.changed_paths(workspace, jj_path=JJ))
        current = jj_adapter.identity(workspace, jj_path=JJ)
        self.assertEqual(item["jj_change_id"], current["jj_change_id"])
        self.assertRegex(current["operation_id"], r"^[0-9a-f]{64,128}$")


class JjAdapterPureTests(unittest.TestCase):
    def test_attempt_workspace_name_is_stable_and_bounded(self):
        first = jj_adapter.workspace_name_for_attempt("WU/Alpha:17", "attempt 1")
        second = jj_adapter.workspace_name_for_attempt("WU/Alpha:17", "attempt 1")
        self.assertEqual(first, second)
        self.assertLessEqual(len(first), 59)
        self.assertRegex(first, r"^[a-z0-9._-]+$")

    def test_changed_path_output_canonicalizes_windows_separators(self):
        output = (
            "src\\worker-a\\result.txt\r\n"
            "docs\\space name\\résumé.txt\r\n"
            "src/worker-b/result.txt\n"
            "src\\worker-a\\result.txt\n"
        )
        self.assertEqual(
            [
                "docs/space name/résumé.txt",
                "src/worker-a/result.txt",
                "src/worker-b/result.txt",
            ],
            jj_adapter._changed_path_output(output),
        )

    def test_changed_path_output_rejects_nonportable_or_escaping_paths(self):
        for value in (
            "../escape.txt\n",
            "src/../escape.txt\n",
            "/absolute.txt\n",
            "C:\\absolute.txt\n",
            "src//ambiguous.txt\n",
            "./relative.txt\n",
        ):
            with self.subTest(value=value):
                with self.assertRaisesRegex(jj_adapter.JjAdapterError, "JJ_CHANGED_PATH_INVALID"):
                    jj_adapter._changed_path_output(value)

    def test_public_changed_path_apis_normalize_windows_jj_output(self):
        result = subprocess.CompletedProcess(
            args=["jj"],
            returncode=0,
            stdout="src\\worker-a\\result.txt\r\nsrc\\worker-b\\result.txt\r\n",
            stderr="",
        )
        with mock.patch.object(jj_adapter, "_run", return_value=result) as run:
            self.assertEqual(
                ["src/worker-a/result.txt", "src/worker-b/result.txt"],
                jj_adapter.changed_paths("C:/fixture", revision="change-a"),
            )
            self.assertEqual(
                ["src/worker-a/result.txt", "src/worker-b/result.txt"],
                jj_adapter.changed_paths_between(
                    "C:/fixture", from_revision="baseline", to_revision="integrated"
                ),
            )
        self.assertEqual(2, run.call_count)


if __name__ == "__main__":
    unittest.main()


class JjMiseOwnershipTests(unittest.TestCase):
    def test_default_jj_execution_uses_mise_without_global_jj(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            (root / "mise.toml").write_text('[tools]\njj = "0.43.0"\n', encoding="utf-8")
            fake_jj = write_python_executable(
                Path(directory) / "managed-jj",
                "import sys\n"
                "args = sys.argv[1:]\n"
                "while args and args[0] in {'--no-pager', '--color=never'}:\n"
                "    args = args[1:]\n"
                "if args[:1] == ['--version']:\n"
                "    print('jj 0.43.0 managed')\n"
                "    raise SystemExit(0)\n"
                "raise SystemExit(9)\n",
            )
            fake_mise = write_python_executable(
                Path(directory) / "mise",
                "import os\n"
                "import subprocess\n"
                "import sys\n"
                "args = sys.argv[1:]\n"
                "if args == ['--version']:\n"
                "    print('mise TEST')\n"
                "    raise SystemExit(0)\n"
                "if len(args) >= 4 and args[0] == 'exec':\n"
                "    if args[1] != 'jj@0.43.0':\n"
                "        raise SystemExit(11)\n"
                "    if args[3] != 'jj':\n"
                "        raise SystemExit(12)\n"
                "    completed = subprocess.run([os.environ['FAKE_JJ'], *args[4:]], check=False)\n"
                "    raise SystemExit(completed.returncode)\n"
                "raise SystemExit(10)\n",
            )
            environment = {**os.environ, "PATH": "", "BBK_MISE": str(fake_mise), "FAKE_JJ": str(fake_jj)}
            result = jj_adapter._run(root, ("--version",), environment=environment)
            self.assertEqual("jj 0.43.0 managed", result.stdout.strip())
            binding = jj_adapter.execution_binding(root, environment=environment)
            self.assertEqual("MISE_MANAGED", binding["execution_mode"])
            self.assertEqual("jj@0.43.0", binding["tool_spec"])
            assert_same_path(self, binding["mise_path"], fake_mise)
