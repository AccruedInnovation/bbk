"""Repository path assertion regressions."""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from tests._path_support import (
    assert_same_path,
    assert_labeled_path,
    create_symlink_or_skip,
    find_unsafe_path_assertions,
    find_unguarded_symlink_creations,
)

class SharedPathAssertionSupportTests(unittest.TestCase):
    """Keep filesystem-identity assertions centralized and alias-safe."""

    def test_shared_helpers_collapse_aliases_in_direct_and_notification_paths(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            target = root / 'physical-project'
            target.mkdir()
            alias = root / 'project-alias'
            try:
                alias.symlink_to(target, target_is_directory=True)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f'directory aliases unavailable on this host: {exc}')

            assert_same_path(self, alias, target)
            assert_labeled_path(
                self,
                [f'Scope: project\nProject: {target.resolve()}'],
                'Project',
                alias,
                required_text='Scope: project',
            )

    def test_shared_helper_failure_identifies_raw_and_canonical_spellings(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            left = root / 'left'
            right = root / 'right'
            left.mkdir()
            right.mkdir()
            with self.assertRaisesRegex(AssertionError, r'raw=.*canonical=.*exists='):
                assert_same_path(self, left, right)

    def test_identity_sensitive_assertions_use_shared_helpers(self):
        """Prevent regressions to raw path-spelling comparisons in test code."""
        tests_root = Path(__file__).resolve().parent
        violations = [
            finding
            for path in sorted(tests_root.glob('test_*.py'))
            for finding in find_unsafe_path_assertions(path)
        ]
        self.assertEqual(violations, [], '\n'.join(violations))

    def test_symlink_fixtures_are_capability_guarded(self):
        """Prevent API-presence checks from standing in for host capability."""
        tests_root = Path(__file__).resolve().parent
        violations = [
            finding
            for path in sorted(tests_root.glob('test_*.py'))
            for finding in find_unguarded_symlink_creations(path)
        ]
        self.assertEqual(violations, [], '\n'.join(violations))

    def test_symlink_helper_converts_permission_denial_to_skip(self):
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            with mock.patch.object(Path, 'symlink_to', side_effect=PermissionError('privilege unavailable')):
                with self.assertRaises(unittest.SkipTest):
                    create_symlink_or_skip(self, root / 'link', root / 'target')

