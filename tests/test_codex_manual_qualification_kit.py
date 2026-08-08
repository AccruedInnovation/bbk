from __future__ import annotations

import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "tools" / "qualification" / "codex-manual-kit-template"


class CodexManualQualificationKitTests(unittest.TestCase):
    def test_preparer_is_command_emitter_and_project_scoped(self):
        text = (TEMPLATE / "prepare-codex-fixtures.ps1").read_text(encoding="utf-8")
        for expected in (
            "No Codex process was started",
            "launch-codex-commands.ps1",
            '"--scope", "project"',
            '"--codex"',
            "MH-CODEX-01",
            "MH-CODEX-03",
        ):
            self.assertIn(expected, text)
        for forbidden in ("Start-Process", "System.Diagnostics.Process", "& $CodexPath"):
            self.assertNotIn(forbidden, text)

    def test_principal_prompts_bind_zero_read_followup_and_frontier_gates(self):
        primary = (TEMPLATE / "prompts" / "MH-CODEX-01-PRIMARY.md").read_text(encoding="utf-8")
        self.assertIn("must not read `shared/skills/bbk-work-unit-execution/SKILL.md`", primary)
        self.assertIn("exactly one `bbk_worker` child", primary)
        followup = (TEMPLATE / "prompts" / "MH-CODEX-02-FOLLOWUP.md").read_text(encoding="utf-8")
        self.assertIn("same logical `bbk_worker` child", followup)
        self.assertIn("Do not spawn a replacement child", followup)
        rolling = (TEMPLATE / "prompts" / "MH-CODEX-03-ROLLING-WAVE.md").read_text(encoding="utf-8")
        for expected in ("FAST_CONTINUATION", "ADOPT_AND_GAP", "ROADMAP_READY", "FRONTIER_READY", "DEFERRED_UNTIL_FRONTIER"):
            self.assertIn(expected, rolling)

    def test_analyzer_wrapper_uses_exact_gate_inputs(self):
        text = (TEMPLATE / "analyze-codex-run.ps1").read_text(encoding="utf-8")
        for expected in (
            "alpha17-config.json",
            "evaluate_alpha17_gates.py",
            "bbk-worker-codex-compiled-manifest.json",
            "bbk-worker-codex-effective-catalog.json",
            "planning-readiness.valid.json",
            "bbk_worker.toml",
        ):
            self.assertIn(expected, text)

    def test_zip_builder_excludes_caches_and_is_deterministic(self):
        spec = importlib.util.spec_from_file_location("bbk_build_codex_kit", ROOT / "tools" / "qualification" / "build_codex_manual_kit.py")
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as raw:
            temp = Path(raw)
            source = temp / "codex-kit"
            (source / "nested" / "__pycache__").mkdir(parents=True)
            (source / "stable.txt").write_text("stable\n", encoding="utf-8")
            (source / "nested" / "cache.pyc").write_bytes(b"cache")
            (source / "nested" / "__pycache__" / "cache.pyc").write_bytes(b"cache")
            first = temp / "first.zip"
            second = temp / "second.zip"
            module.build_zip(source, first)
            module.build_zip(source, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                names = archive.namelist()
            self.assertFalse(any("__pycache__" in name or name.endswith(".pyc") for name in names))
            self.assertIn("codex-kit/stable.txt", names)


if __name__ == "__main__":
    unittest.main()
