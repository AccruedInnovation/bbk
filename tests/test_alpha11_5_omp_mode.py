from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "omp" / "extension" / "index.js"
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def run_node(source: str) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as temp:
        script = Path(temp) / "test.mjs"
        script.write_text(source, encoding="utf-8")
        result = subprocess.run(
            [shutil.which("node") or "node", script],
            cwd=ROOT,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr or result.stdout)
        return json.loads(result.stdout)


MOCK_PREFIX = r"""
const chain = () => ({ optional() { return this; } });
const z = { object: value => value, string: chain, boolean: chain,
  enum: values => chain(), array: value => chain() };
const commands = new Map(), handlers = new Map();
const userMessages = [], customMessages = [], entries = [], notifications = [], statuses = [];
let branch = [];
const pi = {
  zod: { z }, setLabel() {}, registerTool() {},
  registerCommand(name, value) { commands.set(name, value); },
  on(name, value) { if (!handlers.has(name)) handlers.set(name, []); handlers.get(name).push(value); },
  appendEntry(customType, data) {
    entries.push({customType, data});
    branch.push({type: "custom", customType, data});
  },
  sendMessage(value, options) { customMessages.push({value, options}); },
  async sendUserMessage(value, options) { userMessages.push({value, options: options || null}); },
};
const notificationsFor = () => notifications.map(item => item.message);
const ctx = {
  cwd: process.cwd(), hasUI: true,
  isIdle() { return true; },
  sessionManager: { getBranch() { return branch; } },
  ui: {
    notify(message, level) { notifications.push({message, level}); },
    setStatus(key, value) { statuses.push({key, value: value ?? null}); },
  },
};
"""


@unittest.skipUnless(shutil.which("node"), "Node.js is required for OMP extension behavior")
class Alpha115OmpModeTests(unittest.TestCase):
    def test_mode_source_uses_session_state_and_system_prompt_not_transcript_payloads(self):
        source = EXTENSION.read_text(encoding="utf-8")
        self.assertIn('const BBK_MODE_ENTRY_TYPE = "bbk-mode-state"', source)
        self.assertIn('const BBK_MODE_SCHEMA = "bbk.omp-mode-state.v1"', source)
        self.assertIn('"before_agent_start"', source)
        self.assertIn("appendEntry", source)
        self.assertIn("getBranch", source)
        self.assertIn('"session_switch"', source)
        self.assertIn('"session_branch"', source)
        self.assertIn('"session_tree"', source)
        self.assertIn('"bbk:exit"', source)
        self.assertEqual(source.count(".sendUserMessage("), 1)
        self.assertNotIn(".sendMessage(", source)
        self.assertNotIn("bbkEntrypointPrompt", source)
        self.assertNotIn("Installed baseline BBK skill", source)
        self.assertNotIn('readPackageText("shared", "skills", "bbk"', source)

    def test_enter_every_turn_overlay_verbatim_first_directive_and_exit(self):
        value = run_node(
            textwrap.dedent(
                f"""
                {MOCK_PREFIX}
                const mod = await import({json.dumps(EXTENSION.as_uri())});
                mod.default(pi);
                const before = handlers.get("before_agent_start")?.[0];
                if (!before) throw new Error("before_agent_start missing");

                const inactive = await before({{systemPrompt:["base"]}}, ctx);
                const enterResult = await commands.get("bbk").handler("", ctx);
                const afterEnterMessages = userMessages.length;
                const active = await before({{systemPrompt:["base"]}}, ctx);
                const repeated = await before({{systemPrompt:active.systemPrompt}}, ctx);
                const directive = "Implement the accepted baseline without restarting planning";
                await commands.get("bbk").handler(directive, ctx);
                const exitResult = await commands.get("bbk:exit").handler("", ctx);
                const afterExit = await before({{systemPrompt:["base"]}}, ctx);

                const activeText = active.systemPrompt.join("\\n");
                const repeatedText = repeated.systemPrompt.join("\\n");
                console.log(JSON.stringify({{
                  version: {json.dumps(VERSION)},
                  commands: commands.size,
                  inactive: inactive ?? null,
                  enterUndefined: enterResult === undefined,
                  exitUndefined: exitResult === undefined,
                  afterEnterMessages,
                  userMessages,
                  customMessages,
                  entries,
                  activeText,
                  markerCount: (repeatedText.match(/<bbk-session-mode>/g) || []).length,
                  afterExit: afterExit ?? null,
                  statuses,
                  notifications: notificationsFor(),
                }}));
                """
            )
        )
        self.assertEqual(value["commands"], 27)
        self.assertIsNone(value["inactive"])
        self.assertTrue(value["enterUndefined"])
        self.assertTrue(value["exitUndefined"])
        self.assertEqual(value["afterEnterMessages"], 0)
        self.assertEqual(value["customMessages"], [])
        self.assertEqual(len(value["userMessages"]), 1)
        self.assertEqual(
            value["userMessages"][0]["value"],
            "Implement the accepted baseline without restarting planning",
        )
        self.assertNotIn("bbk_root_wayfinder", value["userMessages"][0]["value"])
        self.assertEqual([entry["data"]["enabled"] for entry in value["entries"]], [True, False])
        self.assertEqual(value["entries"][0]["data"]["schema"], "bbk.omp-mode-state.v1")
        self.assertEqual(value["entries"][0]["data"]["package_version"], VERSION)
        for expected in (
            "<bbk-session-mode>",
            "BBK mode is active",
            "bbk_root_wayfinder",
            "bbk_root_orchestrator",
            "bbk_reviewer",
            "bbk_validator_orchestrator",
            "/bbk:exit",
        ):
            self.assertIn(expected, value["activeText"])
        self.assertEqual(value["markerCount"], 1)
        self.assertIsNone(value["afterExit"])
        self.assertIn({"key": "bbk-mode", "value": "BBK"}, value["statuses"])
        self.assertEqual(value["statuses"][-1], {"key": "bbk-mode", "value": None})

    def test_mode_restores_per_branch_and_session_navigation(self):
        value = run_node(
            textwrap.dedent(
                f"""
                {MOCK_PREFIX}
                const mod = await import({json.dumps(EXTENSION.as_uri())});
                mod.default(pi);
                const before = handlers.get("before_agent_start")?.[0];
                const sessionStart = handlers.get("session_start")?.[0];
                const sessionSwitch = handlers.get("session_switch")?.[0];
                const sessionBranch = handlers.get("session_branch")?.[0];
                const sessionTree = handlers.get("session_tree")?.[0];
                if (![before, sessionStart, sessionSwitch, sessionBranch, sessionTree].every(Boolean)) throw new Error("lifecycle handler missing");

                branch = [{{type:"custom", customType:"bbk-mode-state", data:{{enabled:true}}}}];
                await sessionStart({{type:"session_start"}}, ctx);
                const startActive = await before({{systemPrompt:["base"]}}, ctx);

                branch = [];
                await sessionSwitch({{type:"session_switch"}}, ctx);
                const switchedOff = await before({{systemPrompt:["base"]}}, ctx);

                branch = [
                  {{type:"custom", customType:"bbk-mode-state", data:{{enabled:true}}}},
                  {{type:"custom", customType:"bbk-mode-state", data:{{enabled:false}}}},
                ];
                await sessionBranch({{type:"session_branch"}}, ctx);
                const branchOff = await before({{systemPrompt:["base"]}}, ctx);

                branch.push({{type:"custom", customType:"bbk-mode-state", data:{{enabled:true}}}});
                await sessionTree({{type:"session_tree"}}, ctx);
                const treeActive = await before({{systemPrompt:["base"]}}, ctx);
                console.log(JSON.stringify({{
                  startActive: Boolean(startActive), switchedOff: switchedOff ?? null,
                  branchOff: branchOff ?? null, treeActive: Boolean(treeActive),
                  statuses, notifications: notificationsFor(),
                }}));
                """
            )
        )
        self.assertTrue(value["startActive"])
        self.assertIsNone(value["switchedOff"])
        self.assertIsNone(value["branchOff"])
        self.assertTrue(value["treeActive"])
        self.assertIn("BBK mode restored", "\n".join(value["notifications"]))

    def test_no_argument_entry_is_idempotent_and_exit_has_non_colon_alias(self):
        value = run_node(
            textwrap.dedent(
                f"""
                {MOCK_PREFIX}
                const mod = await import({json.dumps(EXTENSION.as_uri())});
                mod.default(pi);
                await commands.get("bbk").handler("", ctx);
                await commands.get("bbk").handler("", ctx);
                await commands.get("bbk").handler("exit", ctx);
                await commands.get("bbk").handler("off", ctx);
                console.log(JSON.stringify({{entries, userMessages, customMessages, notifications:notificationsFor()}}));
                """
            )
        )
        self.assertEqual([entry["data"]["enabled"] for entry in value["entries"]], [True, False])
        self.assertEqual(value["userMessages"], [])
        self.assertEqual(value["customMessages"], [])
        self.assertIn("BBK mode is already active", value["notifications"])
        self.assertIn("BBK mode is not active", value["notifications"])

    def test_current_docs_describe_persistent_mode_without_claiming_native_tool_restriction(self):
        text = "\n".join(
            (ROOT / name).read_text(encoding="utf-8")
            for name in (
                "README.md",
                "docs/USAGE.md",
                "docs/INSTALL.md",
                "omp/extension/README.md",
                "docs/DEVELOPMENT.md",
            )
        )
        for expected in (
            "/bbk:exit",
            "persistent BBK mode",
            "before_agent_start",
            "appendEntry",
            "system-prompt overlay",
            "session-local",
            "footer",
            "ordinary messages",
            "does not change the parent model",
            "--update-omp",
        ):
            self.assertIn(expected, text)
        self.assertIn("does not replace OMP's native plan or vibe modes", text)


if __name__ == "__main__":
    unittest.main()
