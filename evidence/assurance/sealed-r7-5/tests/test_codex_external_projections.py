"""Deterministic checks for the additive DeepSeek Codex projection bundle."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECTIONS = ROOT / "projections" / "codex_ds"
GENERATOR = ROOT / "tools" / "generate_agents.py"


class CodexExternalProjectionTests(unittest.TestCase):
    def test_exact_38_role_files_and_manifest_inventory(self) -> None:
        manifest = json.loads((PROJECTIONS / "manifest.json").read_text(encoding="utf-8"))
        files = sorted(PROJECTIONS.glob("*/agents/*.toml"))
        self.assertEqual(manifest["role_count"], 19)
        self.assertEqual(manifest["projection_count"], 38)
        self.assertEqual(len(files), 38)
        self.assertEqual({p.parent.parent.name for p in files}, {"deepseek-v4-pro", "deepseek-v4-flash"})
        inventory = {
            item["path"]: item["sha256"]
            for target in manifest["targets"].values()
            for item in target["files"]
        }
        self.assertEqual(set(inventory), {p.relative_to(ROOT).as_posix() for p in files})
        for path in files:
            raw = path.read_bytes()
            self.assertEqual(inventory[path.relative_to(ROOT).as_posix()], hashlib.sha256(raw).hexdigest())

    def test_provider_model_and_canonical_role_parity(self) -> None:
        canonical = {p.stem for p in (ROOT / "projections" / "codex" / "agents").glob("*.toml")}
        self.assertEqual(len(canonical), 19)
        for path in PROJECTIONS.glob("*/agents/*.toml"):
            value = tomllib.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(value["name"], path.stem)
            self.assertIn(path.stem, canonical)
            self.assertEqual(value["model_provider"], "deepseek")
            self.assertEqual(value["model"], path.parent.parent.name)
            self.assertEqual(value["model_providers"]["deepseek"]["wire_api"], "responses")
            self.assertEqual(value["model_providers"]["deepseek"]["env_key"], "DEEPSEEK_API_KEY")
            self.assertNotIn("DEEPSEEK_API_KEY=", path.read_text(encoding="utf-8"))
            self.assertIn("developer_instructions", value)

    def test_keyless_generation_and_generator_check(self) -> None:
        env = os.environ.copy()
        env.pop("DEEPSEEK_API_KEY", None)
        result = subprocess.run(
            [sys.executable, str(GENERATOR), "--check"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_manifest_preserves_protected_routing(self) -> None:
        manifest = json.loads((PROJECTIONS / "manifest.json").read_text(encoding="utf-8"))
        self.assertTrue(manifest["activation"] == "ACTIVATION_NEUTRAL")
        self.assertTrue(manifest["invariants"]["parent_and_defaults_unchanged"])
        self.assertTrue(manifest["invariants"]["other_host_projections_unchanged"])
        self.assertFalse(manifest["invariants"]["silent_fallback"])
        self.assertFalse(manifest["invariants"]["credential_value_persisted"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
