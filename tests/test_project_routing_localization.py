"""Alpha.15 project-local OMP routing creation and repair contracts."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from tests._cli_support import run_cli

ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "tools" / "install.py"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ProjectRoutingLocalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temp = tempfile.TemporaryDirectory()
        cls.base = Path(cls._temp.name)
        cls.home = cls.base / "home"
        cls.home.mkdir()
        cls.env = os.environ.copy()
        cls.env.update(
            {
                "HOME": str(cls.home),
                "BBK_HOME": str(cls.home),
                "BBK_INSTALL_ROOT": str(cls.base / "data"),
                "BBK_BIN_DIR": str(cls.base / "bin"),
                "PYTHONUTF8": "1",
                "PYTHONIOENCODING": "utf-8",
            }
        )
        installed = run_cli(
            [
                sys.executable,
                INSTALL,
                "--json",
                "install",
                "--scope",
                "user",
                "--omp",
                "--no-language-profiles",
            ],
            cwd=ROOT,
            env=cls.env,
        )
        cls.install_result = json.loads(installed.stdout)
        cls.extension = cls.home / ".omp" / "agent" / "extensions" / "bbk"
        cls.router = cls.extension / "omp_model_routing.py"
        cls.binding = cls.extension / "bbk-package-root.json"
        cls.user_state = cls.base / "data" / "effective-omp-model-routing.json"
        cls.user_manifest = cls.base / "data" / "install-manifest.json"
        cls.user_agents = cls.home / ".omp" / "agent" / "agents"

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temp.cleanup()

    def run_router(self, *args: str, check: bool = True) -> tuple[dict, subprocess.CompletedProcess[str]]:
        completed = run_cli(
            [
                sys.executable,
                self.router,
                "--binding",
                self.binding,
                "--json",
                *args,
            ],
            cwd=ROOT,
            env=self.env,
            check=check,
        )
        return json.loads(completed.stdout), completed

    def user_surface(self) -> dict[str, str]:
        paths = [self.user_state, self.user_manifest, *sorted(self.user_agents.glob("bbk_*.md"))]
        return {str(path.resolve()): sha256_file(path) for path in paths}

    def test_create_clones_effective_user_routes_in_empty_non_git_directory(self) -> None:
        self.run_router(
            "set-role",
            "bbk_worker",
            "--model",
            "@task",
            "--thinking-level",
            "medium",
        )
        before = self.user_surface()
        project = self.base / "empty-project"
        project.mkdir()

        dry, _ = self.run_router("create-project", "--project-root", str(project), "--dry-run")
        self.assertEqual(dry["status"], "DRY-RUN")
        self.assertTrue(dry["user_state_unchanged"])
        self.assertFalse((project / ".bbk-kit").exists())
        self.assertFalse((project / ".omp").exists())
        self.assertFalse((project / ".bbk").exists())
        self.assertFalse((project / ".git").exists())

        created, _ = self.run_router("create-project", "--project-root", str(project))
        self.assertEqual(created["status"], "CREATED")
        self.assertTrue(created["user_state_unchanged"])
        self.assertTrue(created["reload_required"])
        self.assertEqual(created["verification"]["role_count"], 19)
        self.assertEqual(created["command_contract"]["scope"], "project")
        self.assertTrue(created["command_contract"]["omp_only"])
        self.assertTrue(created["command_contract"]["no_language_profiles"])

        user_routes = json.loads(self.user_state.read_text(encoding="utf-8"))["roles"]
        project_state = json.loads(
            (project / ".bbk-kit" / "effective-omp-model-routing.json").read_text(encoding="utf-8")
        )
        self.assertEqual(project_state["roles"], user_routes)
        self.assertEqual(project_state["roles"]["bbk_worker"], {"model": "@task", "thinkingLevel": "medium"})
        manifest = json.loads((project / ".bbk-kit-install.json").read_text(encoding="utf-8"))
        self.assertTrue(manifest["omp"])
        self.assertFalse(manifest["codex"])
        self.assertFalse(manifest["claude"])
        self.assertFalse(manifest["generic"])
        self.assertEqual(manifest["language_profiles"], [])
        self.assertEqual(manifest["language_profile_source_mode"], "disabled")
        self.assertFalse((project / ".bbk").exists())
        self.assertFalse((project / ".git").exists())
        self.assertEqual(before, self.user_surface())

        current, _ = self.run_router("create-project", "--project-root", str(project))
        self.assertEqual(current["status"], "CURRENT")
        self.assertFalse(current["created"])
        self.assertEqual(before, self.user_surface())

    def test_divergent_or_partial_install_fails_closed_then_repairs_from_dry_run(self) -> None:
        project = self.base / "repair-project"
        project.mkdir()
        created, _ = self.run_router("create-project", "--project-root", str(project))
        self.assertEqual(created["status"], "CREATED")
        before = self.user_surface()

        worker = project / ".omp" / "agents" / "bbk_worker.md"
        worker.write_text(worker.read_text(encoding="utf-8") + "\nlocal divergence\n", encoding="utf-8")
        divergent_digest = sha256_file(worker)
        refused, completed = self.run_router("create-project", "--project-root", str(project), check=False)
        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(refused["status"], "REPAIR_REQUIRED")
        self.assertEqual(refused["inspection"]["status"], "BROKEN")
        self.assertEqual(divergent_digest, sha256_file(worker))
        self.assertEqual(before, self.user_surface())

        plan, _ = self.run_router("repair-project", "--project-root", str(project))
        self.assertEqual(plan["status"], "DRY-RUN")
        self.assertFalse(plan["repaired"])
        self.assertTrue(plan["command_contract"]["replacement"])
        self.assertTrue(plan["command_contract"]["dry_run"])
        self.assertEqual(divergent_digest, sha256_file(worker))
        self.assertEqual(before, self.user_surface())

        repaired, _ = self.run_router("repair-project", "--project-root", str(project), "--apply")
        self.assertEqual(repaired["status"], "REPAIRED")
        self.assertTrue(repaired["user_state_unchanged"])
        self.assertEqual(repaired["verification"]["status"], "CURRENT")
        preexisting = repaired["installer_result"]["preexisting_install"]
        self.assertGreaterEqual(preexisting["modified_backup_count"], 1)
        self.assertTrue(Path(preexisting["modified_backup_root"]).is_dir())
        self.assertNotEqual(divergent_digest, sha256_file(worker))
        self.assertEqual(before, self.user_surface())

        binding = project / ".omp" / "extensions" / "bbk" / "bbk-package-root.json"
        binding.unlink()
        broken, _ = self.run_router("project-status", "--project-root", str(project))
        self.assertEqual(broken["status"], "BROKEN")
        self.assertTrue(broken["repair_required"])
        plan, _ = self.run_router("repair-project", "--project-root", str(project))
        self.assertEqual(plan["status"], "DRY-RUN")
        self.assertEqual(before, self.user_surface())

    @unittest.skipUnless(shutil.which("node"), "Node.js is required for OMP command-surface verification")
    def test_bbk_models_offers_project_create_nested_commands_profile_and_reload_guidance(self) -> None:
        project = self.base / "menu-project"
        project.mkdir()
        script = self.base / "project-localization-menu.mjs"
        script.write_text(
            textwrap.dedent(
                f"""
                const chain = () => ({{ optional() {{ return this; }} }});
                const z = {{ object: value => value, string: chain, boolean: chain,
                  enum: values => chain(), array: value => chain() }};
                const commands = new Map(), notifications = [], confirmations = [], menus = [];
                const pi = {{ zod: {{ z }}, setLabel() {{}}, registerTool() {{}}, on() {{}},
                  registerCommand(name, value) {{ commands.set(name, value); }} }};
                const mod = await import({json.dumps(self.extension.joinpath('index.js').as_uri())});
                mod.default(pi);
                const command = commands.get('bbk:models');
                const ctx = {{
                  cwd: {json.dumps(str(project))}, hasUI: true,
                  models: {{ list() {{ return []; }}, resolve() {{ return true; }} }},
                  ui: {{
                    notify(message, level) {{ notifications.push({{message, level}}); }},
                    async select(title, options) {{
                      menus.push({{title, options}});
                      if (title.includes('sub-agent model routing')) return options.find(value => value.startsWith('Create project-local routing'));
                      throw new Error(`unexpected menu ${{title}}`);
                    }},
                    async confirm(title, body) {{ confirmations.push({{title, body}}); return true; }},
                  }},
                }};
                await command.handler('', ctx);
                await command.handler('project status', ctx);
                await command.handler('project profile testing-flash', ctx);
                await command.handler('project status', ctx);
                console.log(JSON.stringify({{notifications, confirmations, menus}}));
                """
            ),
            encoding="utf-8",
        )
        completed = run_cli(["node", script], cwd=project, env=self.env)
        value = json.loads(completed.stdout)
        menu_options = value["menus"][0]["options"]
        self.assertTrue(any(item.startswith("Create project-local routing") for item in menu_options))
        self.assertEqual(len(value["confirmations"]), 1)
        self.assertIn("project-scoped OMP-only", value["confirmations"][0]["body"])
        messages = "\n".join(item["message"] for item in value["notifications"])
        self.assertIn("Reload or restart OMP", messages)
        self.assertIn("bbk:models project-status: CURRENT", messages)
        state = json.loads((project / ".bbk-kit" / "effective-omp-model-routing.json").read_text(encoding="utf-8"))
        self.assertEqual(state["active_profile"], "testing-flash")
        self.assertEqual({route["model"] for route in state["roles"].values()}, {"deepseek/deepseek-v4-flash"})


if __name__ == "__main__":
    unittest.main()
