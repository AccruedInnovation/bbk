from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests._path_support import assert_same_path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from substrate import git_adapter  # noqa: E402

JJ = os.environ.get("BBK_TEST_JJ") or shutil.which("jj")


class GitAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "repo"
        self.root.mkdir()
        self.git("init")
        self.git("config", "user.name", "BBK Test")
        self.git("config", "user.email", "bbk@example.invalid")
        (self.root / "src").mkdir()
        (self.root / "src" / "a.txt").write_text("a\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-m", "baseline")

    def tearDown(self):
        self.temporary.cleanup()

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def test_worktree_tree_tracks_uncommitted_and_untracked_content_without_index_mutation(self):
        baseline_tree = git_adapter.worktree_tree(self.root)
        staged_before = self.git("diff", "--cached", "--name-only").stdout
        (self.root / "src" / "a.txt").write_text("changed\n", encoding="utf-8")
        (self.root / "src" / "new.txt").write_text("new\n", encoding="utf-8")
        changed_tree = git_adapter.worktree_tree(self.root)
        staged_after = self.git("diff", "--cached", "--name-only").stdout
        self.assertNotEqual(baseline_tree, changed_tree)
        self.assertEqual(staged_before, staged_after)
        self.assertEqual([], self.git("show-ref", "--heads").stderr.splitlines())

    def test_freeze_candidate_is_exact_and_repeatable(self):
        (self.root / "src" / "a.txt").write_text("candidate\n", encoding="utf-8")
        first = git_adapter.freeze_candidate(self.root, candidate_id="candidate-1", jj_change_id="change-1")
        second = git_adapter.freeze_candidate(self.root, candidate_id="candidate-1", jj_change_id="change-1")
        self.assertEqual(first["git_tree"], second["git_tree"])
        self.assertEqual(first["digest"], second["digest"])
        self.assertEqual("GIT_TREE", first["identity_kind"])

    def test_fallback_snapshot_changes_with_content(self):
        first = git_adapter.precommit_snapshot_digest(self.root)
        (self.root / "src" / "a.txt").write_text("other\n", encoding="utf-8")
        second = git_adapter.precommit_snapshot_digest(self.root)
        self.assertNotEqual(first, second)

    def test_repository_subdirectory_is_rejected_as_governed_root(self):
        with self.assertRaisesRegex(git_adapter.GitAdapterError, "ROOT_MISMATCH"):
            git_adapter.assert_repository_boundary(self.root / "src")

    def test_reconciliation_reports_scope_escape(self):
        before = git_adapter.freeze_candidate(self.root, candidate_id="candidate-1", jj_change_id="change-1")
        (self.root / "src" / "a.txt").write_text("inside\n", encoding="utf-8")
        (self.root / "outside.txt").write_text("outside\n", encoding="utf-8")
        receipt = git_adapter.reconcile(
            self.root,
            binding_ref="binding:1",
            candidate_ref="candidate-1",
            before=before,
            jj_change_id="change-1",
            scope_prefixes=["src"],
        )
        self.assertEqual("FAIL", receipt["scope_conformance"])
        self.assertEqual(["outside.txt"], receipt["out_of_scope_paths"])
        self.assertIn("src/a.txt", receipt["changed_paths"])
        self.assertRegex(receipt["receipt_id"], r"^sha256:[0-9a-f]{64}$")

    def test_git_adapter_uses_qualified_git_when_path_is_empty(self):
        qualified_git = shutil.which("git")
        self.assertIsNotNone(qualified_git)
        completed = git_adapter._run(
            self.root,
            ("rev-parse", "--show-toplevel"),
            environment={"PATH": "", "BBK_GIT": str(qualified_git)},
        )
        assert_same_path(
            self,
            Path(completed.stdout.decode("utf-8").strip()),
            self.root,
        )

    @unittest.skipUnless(JJ, "real jj executable not configured")
    def test_secondary_jj_workspace_uses_colocated_git_store_without_metadata_or_index_mutation(self):
        subprocess.run(
            [str(JJ), "--no-pager", "--color=never", "git", "init", "--colocate", "."],
            cwd=self.root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        baseline = self.git("rev-parse", "HEAD").stdout.strip()
        workspace = Path(self.temporary.name) / "worker"
        subprocess.run(
            [
                str(JJ), "--no-pager", "--color=never", "workspace", "add",
                "--name", "worker", "-r", baseline, "-m", "worker",
                "--sparse-patterns", "full", str(workspace),
            ],
            cwd=self.root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        # The primary colocated workspace may advance Git HEAD with control-plane
        # metadata after this worker was allocated. Candidate status must remain
        # relative to the worker's immutable parent, not the shared mutable HEAD.
        (self.root / ".bbk" / "coordination").mkdir(parents=True)
        (self.root / ".bbk" / "coordination" / "root.json").write_text("{}\n", encoding="utf-8")
        subprocess.run(
            [str(JJ), "--no-pager", "--color=never", "status"],
            cwd=self.root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        (workspace / "src" / "a.txt").write_text("worker\n", encoding="utf-8")
        (workspace / "src" / "new.txt").write_text("new\n", encoding="utf-8")
        staged_before = self.git("diff", "--cached", "--name-only").stdout

        candidate = git_adapter.freeze_candidate(
            workspace,
            candidate_id="candidate-worker",
            jj_change_id="change-worker",
            git_repository_root=self.root,
            baseline_commit=baseline,
        )

        staged_after = self.git("diff", "--cached", "--name-only").stdout
        self.assertEqual(staged_before, staged_after)
        self.assertEqual(
            ["src/a.txt", "src/new.txt"],
            [entry["path"] for entry in candidate["status"]],
        )
        self.assertFalse(any(entry["path"].startswith(".jj") for entry in candidate["status"]))
        self.assertRegex(candidate["git_tree"], r"^[0-9a-f]{40,64}$")


if __name__ == "__main__":
    unittest.main()
