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
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "tools" / "install.py"
SETUP = ROOT / "tools" / "setup.py"
UPDATE_OMP = ROOT / "tools" / "update_omp.py"
EXTENSION = ROOT / "omp" / "extension" / "index.js"
BUNDLED = ROOT / "bundled-language-profiles" / "packages"
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()


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
        timeout=180,
    )


def run_json(command, *, env=None, cwd=ROOT, check=True):
    result = run(command, env=env, cwd=cwd, check=check)
    return json.loads(result.stdout), result


def file_snapshot(root: Path) -> dict[str, tuple[str, int]]:
    return {
        path.relative_to(root).as_posix(): (
            hashlib.sha256(path.read_bytes()).hexdigest(),
            path.stat().st_mtime_ns,
        )
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class Alpha114OmpContextAndUpdateTests(unittest.TestCase):
    def test_core_extension_has_one_deliberate_prompt_path_and_no_command_payloads(self):
        text = EXTENSION.read_text(encoding="utf-8")
        self.assertNotIn(".sendMessage(", text)
        self.assertEqual(text.count(".sendUserMessage("), 1)
        self.assertNotIn("return value.details", text)
        self.assertIn("ctx?.ui?.notify", text)
        self.assertIn('content: [{ type: "text", text: JSON.stringify(value.details, null, 2) }]', text)
        self.assertIn("registerTool", text)
        self.assertIn("registerCommand", text)
        self.assertIn("appendEntry", text)
        self.assertIn('"before_agent_start"', text)
        self.assertIn('"bbk:exit"', text)

    @unittest.skipUnless(shutil.which("node"), "Node.js is required for OMP extension behavior")
    def test_deterministic_commands_are_ui_only_and_only_bbk_directive_enters_prompt_flow(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            home = base / "home"
            home.mkdir()
            env = os.environ.copy()
            env.update(
                {
                    "BBK_HOME": str(home),
                    "HOME": str(home),
                    "BBK_INSTALL_ROOT": str(base / "data"),
                    "BBK_BIN_DIR": str(base / "bin"),
                }
            )
            run(
                [
                    sys.executable,
                    INSTALL,
                    "install",
                    "--scope",
                    "user",
                    "--omp",
                    "--no-language-profiles",
                ],
                env=env,
            )
            extension = home / ".omp" / "agent" / "extensions" / "bbk" / "index.js"
            script = base / "context-boundary.mjs"
            script.write_text(
                textwrap.dedent(
                    f"""
                    const chain = () => ({{ optional() {{ return this; }} }});
                    const z = {{ object: value => value, string: chain, boolean: chain,
                      enum: values => chain(), array: value => chain() }};
                    const commands = new Map(), handlers = new Map();
                    const messages = [], userMessages = [], notifications = [], entries = [], statuses = [];
                    const branch = [];
                    const pi = {{
                      zod: {{ z }}, setLabel() {{}}, registerTool() {{}},
                      on(name, value) {{ if (!handlers.has(name)) handlers.set(name, []); handlers.get(name).push(value); }},
                      registerCommand(name, value) {{ commands.set(name, value); }},
                      sendMessage(value, options) {{ messages.push({{value, options}}); }},
                      async sendUserMessage(value, options) {{ userMessages.push({{value, options}}); }},
                      appendEntry(customType, data) {{ entries.push({{customType, data}}); branch.push({{type:'custom', customType, data}}); }},
                    }};
                    const mod = await import({json.dumps(extension.as_uri())});
                    mod.default(pi);
                    const ctx = {{
                      cwd: {json.dumps(str(base))}, hasUI: true,
                      isIdle() {{ return true; }},
                      sessionManager: {{ getBranch() {{ return branch; }} }},
                      models: {{ list() {{ return []; }}, resolve() {{ return true; }} }},
                      ui: {{
                        notify(message, level) {{ notifications.push({{message, level}}); }},
                        setStatus(key, value) {{ statuses.push({{key, value: value ?? null}}); }},
                        async select() {{ throw new Error('unexpected interactive menu'); }},
                      }},
                    }};
                    const results = [];
                    const commandNames = [...commands.keys()].sort();
                    for (const name of commandNames) {{
                      if (name === 'bbk') {{
                        results.push(await commands.get(name).handler('status', ctx));
                      }} else if (name === 'bbk:models') {{
                        results.push(await commands.get(name).handler('status', ctx));
                      }} else {{
                        results.push(await commands.get(name).handler('', ctx));
                      }}
                    }}
                    const beforeMode = {{ messages: messages.length, userMessages: userMessages.length, entries: entries.length }};
                    results.push(await commands.get('bbk').handler('', ctx));
                    const afterEnter = {{ messages: messages.length, userMessages: userMessages.length, entries: entries.length }};
                    const beforeAgent = handlers.get('before_agent_start')?.[0];
                    if (!beforeAgent) throw new Error('missing before_agent_start');
                    const activeOverlay = await beforeAgent({{systemPrompt:['base']}}, ctx);
                    results.push(await commands.get('bbk').handler('Plan the sample system', ctx));
                    results.push(await commands.get('bbk:exit').handler('', ctx));
                    const inactiveOverlay = await beforeAgent({{systemPrompt:['base']}}, ctx);
                    console.log(JSON.stringify({{
                      allUndefined: results.every(value => value === undefined),
                      commandNames,
                      messages: messages.length,
                      userMessages: userMessages.length,
                      beforeMode,
                      afterEnter,
                      entries,
                      statuses,
                      notifications: notifications.length,
                      prompt: userMessages[0]?.value || '',
                      activeOverlay: activeOverlay?.systemPrompt?.join(String.fromCharCode(10)) || '',
                      inactiveOverlay: inactiveOverlay ?? null,
                    }}));
                    """
                ),
                encoding="utf-8",
            )
            value = json.loads(run([shutil.which("node") or "node", script], env=env).stdout)
            self.assertTrue(value["allUndefined"])
            self.assertEqual(len(value["commandNames"]), 27)
            self.assertIn("bbk:exit", value["commandNames"])
            self.assertEqual(value["messages"], 0)
            self.assertEqual(value["beforeMode"], {"messages": 0, "userMessages": 0, "entries": 0})
            self.assertEqual(value["afterEnter"], {"messages": 0, "userMessages": 0, "entries": 1})
            self.assertEqual(value["userMessages"], 1)
            self.assertGreaterEqual(value["notifications"], 27)
            self.assertEqual(value["prompt"], "Plan the sample system")
            self.assertNotIn("bbk_root_wayfinder", value["prompt"])
            self.assertIn("<bbk-session-mode>", value["activeOverlay"])
            self.assertIn("bbk_root_wayfinder", value["activeOverlay"])
            self.assertIsNone(value["inactiveOverlay"])
            self.assertEqual([entry["data"]["enabled"] for entry in value["entries"]], [True, False])
            self.assertEqual(value["statuses"][-1], {"key": "bbk-mode", "value": None})

    def test_setup_exposes_omp_only_update_and_rejects_harness_selection(self):
        help_text = run([sys.executable, SETUP, "--help"]).stdout
        self.assertIn("--update-omp", help_text)
        self.assertIn("--test-and-update-omp", help_text)
        self.assertIn("preserve Codex", help_text)
        invalid = run(
            [sys.executable, SETUP, "--update-omp", "--scope", "user", "--codex"],
            check=False,
        )
        self.assertNotEqual(invalid.returncode, 0)
        self.assertIn("do not apply to an OMP-only update", invalid.stdout + invalid.stderr)

    def test_omp_only_update_preserves_active_route_and_does_not_touch_codex_files(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            home = base / "home"
            home.mkdir()
            env = os.environ.copy()
            env.update(
                {
                    "BBK_HOME": str(home),
                    "HOME": str(home),
                    "BBK_INSTALL_ROOT": str(base / "data"),
                    "BBK_BIN_DIR": str(base / "bin"),
                }
            )
            installed, _ = run_json(
                [
                    sys.executable,
                    INSTALL,
                    "--json",
                    "install",
                    "--scope",
                    "user",
                    "--omp",
                    "--codex",
                    "--no-language-profiles",
                ],
                env=env,
            )
            extension = home / ".omp" / "agent" / "extensions" / "bbk"
            run_json(
                [
                    sys.executable,
                    extension / "omp_model_routing.py",
                    "--json",
                    "apply-profile",
                    "testing-flash",
                ],
                env=env,
            )
            codex_root = home / ".codex" / "agents"
            before = file_snapshot(codex_root)

            updated, _ = run_json(
                [sys.executable, UPDATE_OMP, "--json", "--scope", "user"],
                env=env,
            )
            self.assertEqual(updated["status"], "PASS")
            self.assertEqual(updated["to_version"], VERSION)
            self.assertEqual(updated["preserved_profile"], "testing-flash")
            self.assertEqual(updated["codex_files_touched"], 0)
            self.assertIn("codex", updated["untouched_harnesses"])
            self.assertEqual(updated["reload_command"], "/reload-plugins")
            self.assertEqual(before, file_snapshot(codex_root))

            routed, _ = run_json(
                [sys.executable, extension / "omp_model_routing.py", "--json", "status"],
                env=env,
            )
            self.assertEqual(routed["active_profile"], "testing-flash")
            self.assertEqual(
                {route["model"] for route in routed["roles"].values()},
                {"deepseek/deepseek-v4-flash"},
            )

            status, _ = run_json(
                [sys.executable, INSTALL, "--json", "status", "--scope", "user"],
                env=env,
            )
            self.assertEqual(status["summary"], {"current": len(status["files"])})
            manifest = json.loads(Path(installed["manifest_path"]).read_text(encoding="utf-8"))
            self.assertEqual(manifest["harness_versions"]["omp"], VERSION)
            self.assertEqual(manifest["last_omp_update"]["kind"], "omp-only")

            removed, _ = run_json(
                [sys.executable, INSTALL, "--json", "uninstall", "--scope", "user"],
                env=env,
            )
            self.assertFalse(removed["preserved"])

    def test_current_documentation_states_the_context_and_update_boundaries(self):
        text = "\n".join(
            (ROOT / name).read_text(encoding="utf-8")
            for name in (
                "README.md",
                "docs/INSTALL.md",
                "docs/USAGE.md",
                "docs/MODEL-ROUTING.md",
                "omp/extension/README.md",
            )
        )
        for expected in (
            "UI-only",
            "sendUserMessage",
            "model context",
            "--update-omp",
            "--test-and-update-omp",
            "/reload-plugins",
            "does not modify `.codex`",
            "testing-flash",
            "before_agent_start",
            "appendEntry",
            "/bbk:exit",
        ):
            self.assertIn(expected, text)


if __name__ == "__main__":
    unittest.main()
