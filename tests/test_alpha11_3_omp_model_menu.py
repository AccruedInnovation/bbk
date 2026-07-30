from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "tools" / "install.py"
ROUTING = ROOT / "tools" / "omp_model_routing.py"
PROFILES = ROOT / "spec" / "omp-model-routing-profiles.json"
TEMPLATE = ROOT / "templates" / "omp-model-routing-profile.json"


def run(command, *, env=None, cwd=ROOT, check=True):
    return subprocess.run(
        [str(value) for value in command],
        cwd=str(cwd),
        env=env,
        check=check,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def run_json(command, *, env=None, cwd=ROOT, check=True):
    result = run(command, env=env, cwd=cwd, check=check)
    return json.loads(result.stdout), result


def frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    raw = text.split("---\n", 2)[1]
    result = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        try:
            parsed = json.loads(value.strip())
        except json.JSONDecodeError:
            parsed = value.strip()
        result[key] = parsed
    return result


class Alpha113OmpModelMenuTests(unittest.TestCase):
    def test_bundled_profiles_cover_every_role_and_include_requested_cost_modes(self):
        value = json.loads(PROFILES.read_text(encoding="utf-8"))
        roles = {
            item["name"]
            for item in json.loads((ROOT / "spec" / "roles.json").read_text(encoding="utf-8"))["roles"]
        }
        self.assertEqual(value["schema_version"], "bbk.omp-model-routing-profiles.v1")
        self.assertEqual(value["package_version"], "0.1.0-alpha.11.7")
        self.assertEqual(set(value["profiles"]), {"default", "testing-flash", "deepseek-economy"})
        for profile in value["profiles"].values():
            self.assertEqual(set(profile["roles"]), roles)
        testing = value["profiles"]["testing-flash"]["roles"]
        self.assertEqual({route["model"] for route in testing.values()}, {"deepseek/deepseek-v4-flash"})
        economy = value["profiles"]["deepseek-economy"]["roles"]
        self.assertTrue(all(route["model"].startswith("deepseek/") for route in economy.values()))
        self.assertIn("deepseek/deepseek-v4-pro", {route["model"] for route in economy.values()})
        self.assertIn("deepseek/deepseek-v4-flash", {route["model"] for route in economy.values()})

    def test_template_is_compact_and_valid_for_runtime_application(self):
        value = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        self.assertEqual(value["schema_version"], "bbk.omp-model-routing-profile.v1")
        self.assertEqual(value["package_version"], "0.1.0-alpha.11.7")
        self.assertEqual(set(value["default"]), {"model", "thinkingLevel"})
        canonical = {
            item["name"]
            for item in json.loads((ROOT / "spec" / "roles.json").read_text(encoding="utf-8"))["roles"]
        }
        self.assertLessEqual(set(value["roles"]), canonical)

    def test_install_apply_menu_profiles_manifest_status_and_uninstall_round_trip(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            home = base / "home"; home.mkdir()
            env = os.environ.copy()
            env.update({
                "BBK_HOME": str(home),
                "HOME": str(home),
                "BBK_INSTALL_ROOT": str(base / "data"),
                "BBK_BIN_DIR": str(base / "bin"),
            })
            installed, _ = run_json([
                sys.executable, INSTALL, "--json", "install", "--scope", "user", "--omp", "--no-language-profiles"
            ], env=env)
            extension = home / ".omp" / "agent" / "extensions" / "bbk"
            binding = json.loads((extension / "bbk-package-root.json").read_text(encoding="utf-8"))
            self.assertEqual(binding["schema"], "bbk.omp-package-binding.v2")
            self.assertTrue((extension / "omp_model_routing.py").is_file())
            self.assertTrue(Path(binding["state_path"]).is_file())

            status, _ = run_json([sys.executable, extension / "omp_model_routing.py", "--json", "status"], env=env)
            self.assertEqual(status["active_profile"], "installation-default")
            self.assertEqual(len(status["roles"]), 19)
            self.assertEqual(status["route_surface"], "bbk-managed-agent-frontmatter")
            self.assertIn("task.agentModelOverrides", status["precedence_note"])

            script = base / "model-menu.mjs"
            script.write_text(textwrap.dedent(f"""
                const chain = () => ({{ optional() {{ return this; }} }});
                const z = {{ object: value => value, string: chain, boolean: chain,
                  enum: values => chain(), array: value => chain() }};
                const commands = new Map(), messages = [], userMessages = [], notifications = [];
                const pi = {{ zod: {{ z }}, setLabel() {{}}, registerTool() {{}}, on() {{}},
                  registerCommand(name, value) {{ commands.set(name, value); }},
                  sendMessage(value) {{ messages.push(value); }},
                  sendUserMessage(value) {{ userMessages.push(value); }} }};
                const mod = await import({json.dumps((extension / 'index.js').as_uri())});
                mod.default(pi);
                const command = commands.get('bbk:models');
                if (!command) throw new Error('missing bbk:models');
                const ui = {{
                  async select(title, options) {{
                    if (title.includes('sub-agent model routing')) return 'Apply a routing profile';
                    if (title === 'Routing profile') return options.find(value => value.startsWith('testing-flash'));
                    throw new Error(`unexpected select ${{title}}`);
                  }},
                  async confirm() {{ return true; }},
                  notify(message, level) {{ notifications.push({{message, level}}); }},
                }};
                const result = await command.handler('', {{cwd: {json.dumps(str(base))}, hasUI: true, ui, models: {{list() {{ return []; }}}}}});
                console.log(JSON.stringify({{
                  resultIsUndefined: result === undefined,
                  messages: messages.length,
                  userMessages: userMessages.length,
                  notifications: notifications.length,
                }}));
            """), encoding="utf-8")
            menu = json.loads(run(["node", script], env=env).stdout)
            self.assertTrue(menu["resultIsUndefined"])
            self.assertEqual(menu["messages"], 0)
            self.assertEqual(menu["userMessages"], 0)
            self.assertGreaterEqual(menu["notifications"], 1)

            routed, _ = run_json([sys.executable, extension / "omp_model_routing.py", "--json", "status"], env=env)
            self.assertEqual(routed["active_profile"], "testing-flash")
            self.assertEqual(
                {route["model"] for route in routed["roles"].values()},
                {"deepseek/deepseek-v4-flash"},
            )

            agents = home / ".omp" / "agent" / "agents"
            for role in status["roles"]:
                meta = frontmatter(agents / f"{role}.md")
                self.assertEqual(meta["model"], "deepseek/deepseek-v4-flash")
                self.assertEqual(meta["thinkingLevel"], "high")

            install_status, _ = run_json([sys.executable, INSTALL, "--json", "status", "--scope", "user"], env=env)
            self.assertEqual(install_status["summary"], {"current": len(install_status["files"])})
            self.assertEqual(install_status["omp_runtime_routing"]["active_profile"], "testing-flash")

            custom, _ = run_json([
                sys.executable, extension / "omp_model_routing.py", "--json", "set-role", "bbk_worker",
                "--model", "@task", "--thinking-level", "medium"
            ], env=env)
            self.assertEqual(custom["active_profile"], "custom")
            self.assertEqual(frontmatter(agents / "bbk_worker.md")["model"], "@task")

            exported = base / "exported-routing.json"
            export_result, _ = run_json([
                sys.executable, extension / "omp_model_routing.py", "--json", "export", exported,
                "--id", "round-trip"
            ], env=env)
            self.assertEqual(export_result["status"], "EXPORTED")
            exported_value = json.loads(exported.read_text(encoding="utf-8"))
            self.assertEqual(exported_value["id"], "round-trip")
            exported_value["id"] = "file-profile"
            exported_value["description"] = "Applied from a compact external profile file."
            exported.write_text(json.dumps(exported_value, indent=2) + "\n", encoding="utf-8")
            from_file, _ = run_json([
                sys.executable, extension / "omp_model_routing.py", "--json", "apply-file", exported
            ], env=env)
            self.assertEqual(from_file["active_profile"], "file-profile")
            self.assertEqual(from_file["routes"]["bbk_worker"]["model"], "@task")

            economy, _ = run_json([
                sys.executable, extension / "omp_model_routing.py", "--json", "apply-profile", "deepseek-economy"
            ], env=env)
            self.assertEqual(economy["active_profile"], "deepseek-economy")
            self.assertTrue(all(route["model"].startswith("deepseek/") for route in economy["routes"].values()))

            removed, _ = run_json([sys.executable, INSTALL, "--json", "uninstall", "--scope", "user"], env=env)
            self.assertFalse(removed["preserved"])
            self.assertFalse(Path(installed["manifest_path"]).exists())

    def test_runtime_router_refuses_locally_modified_agent(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            home = base / "home"; home.mkdir()
            env = os.environ.copy()
            env.update({"BBK_HOME": str(home), "HOME": str(home), "BBK_INSTALL_ROOT": str(base / "data"), "BBK_BIN_DIR": str(base / "bin")})
            run([sys.executable, INSTALL, "install", "--scope", "user", "--omp", "--no-language-profiles"], env=env)
            extension = home / ".omp" / "agent" / "extensions" / "bbk"
            agent = home / ".omp" / "agent" / "agents" / "bbk_worker.md"
            agent.write_text(agent.read_text(encoding="utf-8") + "\nlocal change\n", encoding="utf-8")
            value, result = run_json([
                sys.executable, extension / "omp_model_routing.py", "--json", "apply-profile", "testing-flash"
            ], env=env, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(value["status"], "ERROR")
            self.assertIn("differs from the BBK install manifest", value["error"])

    def test_current_docs_describe_menu_profiles_and_headless_commands(self):
        text = "\n".join(
            (ROOT / name).read_text(encoding="utf-8")
            for name in ["README.md", "docs/MODEL-ROUTING.md", "docs/USAGE.md", "omp/extension/README.md"]
        )
        for required in [
            "/bbk:models", "testing-flash", "deepseek-economy", "installation-default",
            "omp-model-routing-profile.json", "future", "sub-agent", "task.agentModelOverrides",
        ]:
            self.assertIn(required, text)

    def test_version_and_extension_metadata_agree(self):
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(version, "0.1.0-alpha.11.7")
        self.assertEqual(json.loads((ROOT / "omp" / "extension" / "package.json").read_text(encoding="utf-8"))["version"], version)
        self.assertEqual(json.loads(PROFILES.read_text(encoding="utf-8"))["package_version"], version)


if __name__ == "__main__":
    unittest.main()
