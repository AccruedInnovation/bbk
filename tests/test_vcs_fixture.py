from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests._vcs_fixture import BD, JJ, assert_isolated, init_beads, init_jj, prepare_git_seed


class VcsFixtureTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def test_plain_git_seed_is_byte_exact_lf_and_unique_namespace(self):
        first = prepare_git_seed(
            self.base / "first",
            files={"src/value.txt": b"alpha\n", "binary.dat": b"\x00\xff\n"},
            fixture_id="vcs-fixture",
        )
        second = prepare_git_seed(
            self.base / "second",
            files={"src/value.txt": b"alpha\n", "binary.dat": b"\x00\xff\n"},
            fixture_id="vcs-fixture",
        )
        self.assertEqual(b"alpha\n", (first.root / "src/value.txt").read_bytes())
        self.assertEqual(b"\x00\xff\n", (first.root / "binary.dat").read_bytes())
        self.assertEqual("false", first.run("config", "--get", "core.autocrlf").stdout.strip())
        self.assertEqual("lf", first.run("config", "--get", "core.eol").stdout.strip())
        self.assertNotEqual(first.branch, second.branch)
        self.assertNotEqual(first.head, second.head)
        self.assertTrue(first.branch.startswith("bbk/vcs-fixture/"))
        self.assertFalse((first.root / ".jj").exists())
        self.assertFalse((first.root / ".beads").exists())
        self.assertFalse((first.root / ".bbk").exists())
        assert_isolated(first.root, second.root)

    @unittest.skipUnless(JJ and JJ.is_file(), "real jj executable not configured")
    def test_jj_opt_in_creates_only_fresh_local_store(self):
        first = prepare_git_seed(self.base / "jj-one", fixture_id="jj-opt-in")
        second = prepare_git_seed(self.base / "jj-two", fixture_id="jj-opt-in")
        init_jj(first, jj_path=JJ)
        init_jj(second, jj_path=JJ)
        self.assertTrue((first.root / ".jj").is_dir())
        self.assertTrue((second.root / ".jj").is_dir())
        self.assertFalse((first.root / ".jj").is_symlink())
        self.assertFalse((second.root / ".jj").is_symlink())
        assert_isolated(first.root, second.root)

    @unittest.skipUnless(BD and BD.is_file(), "real bd executable not configured")
    def test_beads_opt_in_creates_only_fresh_local_store(self):
        first = prepare_git_seed(self.base / "bd-one", fixture_id="bd-opt-in")
        second = prepare_git_seed(self.base / "bd-two", fixture_id="bd-opt-in")
        init_beads(first, bd_path=BD)
        init_beads(second, bd_path=BD)
        self.assertTrue((first.root / ".beads").is_dir())
        self.assertTrue((second.root / ".beads").is_dir())
        self.assertFalse((first.root / ".beads").is_symlink())
        self.assertFalse((second.root / ".beads").is_symlink())
        assert_isolated(first.root, second.root)

    def test_seed_root_must_be_fresh(self):
        root = self.base / "occupied"
        root.mkdir()
        (root / "preexisting.txt").write_bytes(b"do not overwrite\n")
        with self.assertRaises(FileExistsError):
            prepare_git_seed(root)
        self.assertEqual(b"do not overwrite\n", (root / "preexisting.txt").read_bytes())


if __name__ == "__main__":
    unittest.main()
