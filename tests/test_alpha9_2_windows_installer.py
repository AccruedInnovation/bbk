from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path, PureWindowsPath
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {relative_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


install = load_module("bbk_install_alpha92", "tools/install.py")
bbk = load_module("bbk_cli_alpha92", "tools/bbk.py")


class Alpha92WindowsInstallerTests(unittest.TestCase):
    def test_home_override_prevents_windows_verification_from_using_real_profile(self):
        with tempfile.TemporaryDirectory() as temp:
            isolated = Path(temp) / "isolated-home"
            actual = Path(temp) / "actual-home"
            with mock.patch.dict(os.environ, {"HOME": str(isolated)}, clear=False):
                os.environ.pop("BBK_HOME", None)
                with mock.patch.object(install.Path, "home", return_value=actual):
                    self.assertEqual(install.user_home(), isolated.resolve())

    def test_bbk_home_has_explicit_precedence_over_home(self):
        with tempfile.TemporaryDirectory() as temp:
            explicit = Path(temp) / "bbk-home"
            conventional = Path(temp) / "home"
            with mock.patch.dict(
                os.environ,
                {"BBK_HOME": str(explicit), "HOME": str(conventional)},
                clear=False,
            ):
                self.assertEqual(install.user_home(), explicit.resolve())

    def test_windows_backup_layout_cannot_escape_backup_root(self):
        destination = PureWindowsPath(r"C:\Users\operator\.codex\agents\bbk_worker.toml")
        namespace, parts = install.backup_layout(destination)
        self.assertEqual(namespace, "C")
        self.assertEqual(parts, ("Users", "operator", ".codex", "agents", "bbk_worker.toml"))
        self.assertNotIn(destination.anchor, parts)

        unc = PureWindowsPath(r"\\server\share\operator\.omp\agent\extensions\bbk\index.js")
        unc_namespace, unc_parts = install.backup_layout(unc)
        self.assertEqual(unc_namespace, "server_share")
        self.assertEqual(unc_parts[:2], ("operator", ".omp"))

    def test_json_path_fields_are_host_neutral(self):
        path = PureWindowsPath(r"D:\Projects\BBK\.omp\extensions\bbk\bbk.py")
        self.assertEqual(install.json_path(path), "D:/Projects/BBK/.omp/extensions/bbk/bbk.py")
        root = PureWindowsPath(r"D:\Projects\BBK")
        relative = root / ".bbk" / "project.md"
        self.assertEqual(bbk.portable_relative_path(relative, root), ".bbk/project.md")

    def test_current_installer_uses_override_aware_home_for_all_user_targets(self):
        source = (ROOT / "tools" / "install.py").read_text(encoding="utf-8")
        # The sole direct Path.home() call is the fallback inside user_home().
        self.assertEqual(source.count("Path.home()"), 2)  # one docstring mention, one fallback call
        self.assertIn("home = user_home()", source)
        for fragment in (
            'home / ".codex"',
            'home / ".omp"',
            'home / ".claude"',
            'home / ".agents"',
        ):
            self.assertIn(fragment, source)

if __name__ == "__main__":
    unittest.main()
