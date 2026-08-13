from __future__ import annotations

import collections
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import generate_agents
import install as install_tool
import setup as setup_tool
from codex_ds_lifecycle import MANIFEST_NAME, bulk_install
from model_routing import compile_packaged_omp_defaults


FLAG = "--codex-use-packaged-omp-default-routing"


class CodexBulkOmpMirrorTests(unittest.TestCase):
    def test_exact_19_role_12_6_1_provider_parity(self) -> None:
        spec = json.loads((ROOT / "spec" / "roles.json").read_text(encoding="utf-8"))
        roles = {str(item["name"]) for item in spec["roles"]}
        compiled = compile_packaged_omp_defaults()["policy"]
        self.assertEqual(set(compiled["roles"]), roles)
        self.assertEqual(len(roles), 19)
        self.assertEqual(
            collections.Counter(item["provider"] for item in compiled["codex_provider_routes"].values()),
            collections.Counter({"openai-codex": 12, "deepseek": 7}),
        )

        outputs, metadata = generate_agents.rendered_packaged_omp_codex()
        self.assertEqual(len(outputs), 19)
        self.assertEqual(metadata["provider_counts"], {"openai-codex": 12, "deepseek": 7})
        parsed = {name: tomllib.loads(raw.decode("utf-8")) for name, raw in outputs.items()}
        self.assertEqual(
            collections.Counter(
                (value.get("model_provider", "openai-codex"), value["model"])
                for value in parsed.values()
            ),
            collections.Counter(
                {
                    ("openai-codex", "gpt-5.6-sol"): 12,
                    ("deepseek", "deepseek-v4-pro"): 6,
                    ("deepseek", "deepseek-v4-flash"): 1,
                }
            ),
        )
        self.assertEqual({value["name"] for value in parsed.values()}, roles)

    def test_absent_flag_preserves_codex_bytes(self) -> None:
        expected, _ = generate_agents.rendered_projections(
            generate_agents.MODEL_ROUTING_PATH, targets=("codex",)
        )
        install_tool._PROJECTION_BUNDLE_CACHE.clear()
        _, actual, _ = install_tool.ProjectionBundleCache(
            generate_agents.MODEL_ROUTING_PATH, ("codex",), mirror_omp=False
        ).get()
        self.assertEqual(actual["codex"], expected["codex"])
        self.assertTrue(all(b"model_provider = \"deepseek\"" not in raw for raw in actual["codex"].values()))

    def test_flag_forwarding_and_conflict_rejection_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw) / "project"
            args = setup_tool.build_parser().parse_args(
                ["--install", "--scope", "project", "--root", str(root), "--codex", FLAG]
            )
            self.assertIn(FLAG, setup_tool.install_arguments(args))
            custom = Path(raw) / "routing.json"
            custom.write_text("{}\n", encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "install.py"),
                    "--json",
                    "install",
                    "--scope",
                    "project",
                    "--root",
                    str(root),
                    "--codex",
                    "--no-language-profiles",
                    "--model-routing",
                    str(custom),
                    FLAG,
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
            self.assertIn("cannot be combined with --model-routing", proc.stdout + proc.stderr)
            self.assertFalse((root / ".bbk-kit").exists())

    def test_mixed_provider_bulk_lifecycle_is_keyless(self) -> None:
        from codex_ds_lifecycle import bulk_rollback, bulk_status, bulk_uninstall

        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw) / "codex"
            old = os.environ.pop("DEEPSEEK_API_KEY", None)
            try:
                installed = bulk_install(codex_home=home)
                self.assertEqual(installed["role_count"], 19)
                self.assertEqual(installed["mode"], "MIRROR_CANONICAL_OMP")
                parsed = {
                    path.stem: tomllib.loads(path.read_text(encoding="utf-8"))
                    for path in (home / "agents").glob("*.toml")
                }
                self.assertEqual(
                    collections.Counter(
                        (item.get("model_provider", "openai-codex"), item["model"])
                        for item in parsed.values()
                    ),
                    collections.Counter(
                        {
                            ("openai-codex", "gpt-5.6-sol"): 12,
                            ("deepseek", "deepseek-v4-pro"): 6,
                            ("deepseek", "deepseek-v4-flash"): 1,
                        }
                    ),
                )
                self.assertFalse(installed["credential_value_persisted"])
                self.assertTrue(all("DEEPSEEK_API_KEY=" not in path.read_text(encoding="utf-8") for path in (home / "agents").glob("*.toml")))
                self.assertEqual(bulk_status(codex_home=home)["status"], "CURRENT")
                updated = bulk_install(codex_home=home, mode="update")
                self.assertEqual(updated["lifecycle"], "update")
                self.assertEqual(bulk_rollback(codex_home=home)["state"], "ROLLED_BACK")
                self.assertEqual(bulk_status(codex_home=home)["status"], "CURRENT")
                self.assertEqual(bulk_uninstall(codex_home=home)["status"], "PASS")
                self.assertEqual(bulk_status(codex_home=home)["status"], "ABSENT")
            finally:
                if old is not None:
                    os.environ["DEEPSEEK_API_KEY"] = old

    def test_ownership_conflict_and_no_fallback_are_fail_closed(self) -> None:
        from codex_ds_lifecycle import LifecycleError, resolve_actor

        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            (home / MANIFEST_NAME).write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(LifecycleError, "BLOCKED_OWNERSHIP_CONFLICT"):
                bulk_install(codex_home=home)
            self.assertFalse((home / "agents").exists())
        with self.assertRaisesRegex(LifecycleError, "unknown target"):
            resolve_actor("bbk_worker", "deepseek-v4-unknown", codex_home=Path("."))

    def test_cli_and_documentation_contract_strings(self) -> None:
        help_proc = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "install.py"), "install", "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(help_proc.returncode, 0)
        self.assertIn(FLAG, help_proc.stdout)
        setup_help = setup_tool.build_parser().format_help()
        self.assertIn(FLAG, setup_help)
        docs = "\n".join(
            (ROOT / path).read_text(encoding="utf-8")
            for path in ("README.md", "docs/INSTALL.md", "docs/USAGE.md", "docs/MODEL-ROUTING.md")
        )
        for phrase in (FLAG, "MIRROR_CANONICAL_OMP", "12 GPT", "6 DeepSeek Pro", "1 DeepSeek Flash", "without the flag"):
            self.assertIn(phrase, docs)


if __name__ == "__main__":
    unittest.main()
