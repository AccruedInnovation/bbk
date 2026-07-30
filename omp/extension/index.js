import { spawn } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const extensionDir = path.dirname(fileURLToPath(import.meta.url));
const sourceRoot = path.resolve(extensionDir, "..", "..");
const adjacentCli = path.join(extensionDir, "bbk.py");
const sourceCli = path.join(sourceRoot, "tools", "bbk.py");
const cliPath = process.env.BBK_CLI || (process.platform ? (() => {
  try { readFileSync(adjacentCli); return adjacentCli; } catch { return sourceCli; }
})() : sourceCli);
const adjacentRoutingCli = path.join(extensionDir, "omp_model_routing.py");
const sourceRoutingCli = path.join(sourceRoot, "tools", "omp_model_routing.py");
const routingCliPath = process.env.BBK_OMP_ROUTING_CLI || (() => {
  try { readFileSync(adjacentRoutingCli); return adjacentRoutingCli; } catch { return sourceRoutingCli; }
})();
const routingBindingPath = process.env.BBK_OMP_ROUTING_BINDING || path.join(extensionDir, "bbk-package-root.json");
const versionPath = (() => {
  try { readFileSync(path.join(extensionDir, "VERSION")); return path.join(extensionDir, "VERSION"); }
  catch { return path.join(sourceRoot, "VERSION"); }
})();
let version = "0.1.0-alpha.11.11";
try { version = readFileSync(versionPath, "utf8").trim() || version; } catch {}
let packageRoot = sourceRoot;
try {
  const binding = JSON.parse(readFileSync(path.join(extensionDir, "bbk-package-root.json"), "utf8"));
  if (binding?.path) packageRoot = binding.path;
} catch {}

const protectedFragments = [
  `${path.sep}.bbk${path.sep}candidates${path.sep}`,
  `${path.sep}.bbk${path.sep}attestations${path.sep}`,
  `${path.sep}.bbk${path.sep}receipts${path.sep}`,
  `${path.sep}.bbk${path.sep}reviews${path.sep}runs${path.sep}`,
  `${path.sep}.bbk${path.sep}reviews${path.sep}findings${path.sep}`,
  `${path.sep}.bbk${path.sep}reviews${path.sep}dispositions${path.sep}`,
];

function pythonCommand() {
  return process.env.BBK_PYTHON || (process.platform === "win32" ? "py" : "python3");
}
function commandPrefix() {
  return process.platform === "win32" && !process.env.BBK_PYTHON ? ["-3", cliPath] : [cliPath];
}
function scriptPrefix(script) {
  return process.platform === "win32" && !process.env.BBK_PYTHON ? ["-3", script] : [script];
}
function runRouting(args, cwd, signal) {
  return new Promise((resolve, reject) => {
    const child = spawn(pythonCommand(), [...scriptPrefix(routingCliPath), "--binding", routingBindingPath, "--json", ...args], {
      cwd, env: { ...process.env, BBK_PACKAGE_ROOT: packageRoot }, windowsHide: true, stdio: ["ignore", "pipe", "pipe"],
    });
    let stdout = "", stderr = "";
    child.stdout.setEncoding("utf8"); child.stderr.setEncoding("utf8");
    child.stdout.on("data", chunk => { stdout += chunk; });
    child.stderr.on("data", chunk => { stderr += chunk; });
    const abort = () => child.kill("SIGTERM");
    signal?.addEventListener?.("abort", abort, { once: true });
    child.on("error", reject);
    child.on("close", code => {
      signal?.removeEventListener?.("abort", abort);
      let details;
      try { details = stdout.trim() ? JSON.parse(stdout) : { status: code === 0 ? "PASS" : "ERROR" }; }
      catch { details = { status: "ERROR", stdout, stderr, parseError: "BBK OMP routing CLI did not return JSON" }; }
      if (stderr.trim()) details.stderr = stderr;
      resolve({ code, details, stdout, stderr });
    });
  });
}
function runBbk(args, cwd, signal) {
  return new Promise((resolve, reject) => {
    const child = spawn(pythonCommand(), [...commandPrefix(), "--json", ...args], {
      cwd, env: { ...process.env, BBK_PACKAGE_ROOT: packageRoot }, windowsHide: true, stdio: ["ignore", "pipe", "pipe"],
    });
    let stdout = "", stderr = "";
    child.stdout.setEncoding("utf8"); child.stderr.setEncoding("utf8");
    child.stdout.on("data", chunk => { stdout += chunk; });
    child.stderr.on("data", chunk => { stderr += chunk; });
    const abort = () => child.kill("SIGTERM");
    signal?.addEventListener?.("abort", abort, { once: true });
    child.on("error", reject);
    child.on("close", code => {
      signal?.removeEventListener?.("abort", abort);
      let details;
      try { details = stdout.trim() ? JSON.parse(stdout) : { status: code === 0 ? "PASS" : "ERROR" }; }
      catch { details = { status: "ERROR", stdout, stderr, parseError: "BBK CLI did not return JSON" }; }
      if (stderr.trim()) details.stderr = stderr;
      resolve({ code, details, stdout, stderr });
    });
  });
}
function result(value) {
  return {
    content: [{ type: "text", text: JSON.stringify(value.details, null, 2) }],
    details: value.details,
    isError: value.code !== 0,
  };
}
function rootArgs(root) { return root ? ["--root", root] : []; }
function repeated(flag, values) { return (values || []).flatMap(value => [flag, value]); }
function registerCliTool(pi, definition) {
  pi.registerTool({
    name: definition.name, label: definition.label, description: definition.description,
    parameters: definition.parameters,
    async execute(_id, params, signal, _onUpdate, ctx) {
      return result(await runBbk(definition.argv(params || {}), ctx?.cwd || process.cwd(), signal));
    },
  });
}
function splitArgs(raw) {
  return (String(raw || "").match(/(?:[^\s"]+|"[^"]*")+/g) || []).map(value => value.replace(/^"|"$/g, ""));
}
function commandInvocation(first, second) {
  // OMP command APIs have used both handler(args, ctx) and handler(ctx) forms.
  if (second) return { args: first || "", ctx: second };
  if (first && typeof first === "object") return { args: first.args || "", ctx: first };
  return { args: first || "", ctx: { cwd: process.cwd(), ui: { notify() {} } } };
}
function conciseResultText(value, label) {
  const details = value?.details && typeof value.details === "object" ? value.details : {};
  const status = String(details.status || (value?.code === 0 ? "PASS" : "ERROR"));
  const lines = [`${label}: ${status}`];
  const message = details.error || details.message || details.parseError;
  if (typeof message === "string" && message.trim()) lines.push(message.trim().slice(0, 600));
  for (const key of ["path", "output", "manifest_path", "candidate", "id"]) {
    if (typeof details[key] === "string" && details[key].trim()) lines.push(`${key}: ${details[key].trim()}`);
  }
  if (details.summary && typeof details.summary === "object" && !Array.isArray(details.summary)) {
    const counts = Object.entries(details.summary)
      .filter(([, count]) => typeof count === "number")
      .map(([name, count]) => `${name}=${count}`);
    if (counts.length) lines.push(`summary: ${counts.join(", ")}`);
  }
  return lines.join("\n");
}
function publishCommandResult(_pi, ctx, value, label) {
  ctx?.ui?.notify?.(conciseResultText(value, label), value.code === 0 ? "info" : "error");
  // Extension slash commands are user-interface operations. Do not use
  // sendMessage here: nextTurn messages are persisted and injected into the
  // model context. LLM-callable tools return structured details separately.
  return undefined;
}
function registerCommand(pi, name, description, baseArgv, { requireArgs = false } = {}) {
  pi.registerCommand(name, {
    description,
    handler: async (first, second) => {
      const { args, ctx } = commandInvocation(first, second);
      const extra = splitArgs(args);
      if (requireArgs && !extra.length) {
        ctx?.ui?.notify?.(`Usage: /${name} ${description}`, "warning");
        return;
      }
      return publishCommandResult(pi, ctx, await runBbk([...baseArgv, ...extra], ctx?.cwd || process.cwd()), name);
    },
  });
}
const BBK_MODE_ENTRY_TYPE = "bbk-mode-state";
const BBK_MODE_SCHEMA = "bbk.omp-mode-state.v1";
const BBK_MODE_STATUS_KEY = "bbk-mode";
const BBK_MODE_PROMPT_MARKER = "<bbk-session-mode>";
const BBK_MODE_SYSTEM_PROMPT = [
  BBK_MODE_PROMPT_MARKER,
  "BBK mode is active in this parent OMP session. Treat the current user message as part of the ongoing BBK-governed workflow, even when it does not mention BBK. Preserve the user's terminal condition and current `.bbk` project state. Use the installed `bbk` skill when procedure detail is needed.",
  "Route unresolved planning or material uncertainty to `bbk_root_wayfinder`; accepted-baseline execution or recovery to `bbk_root_orchestrator`; bounded independent review to `bbk_reviewer`; and assertion-scoped acceptance to `bbk_validator_orchestrator`. Invoke named BBK task agents rather than imitating them so their model routing, skills, tools, spawn policy, and return contracts apply.",
  "Continue existing work instead of restarting it, and keep this parent session user-facing. BBK mode remains active until `/bbk:exit`.",
  "</bbk-session-mode>",
].join("\n");

function createBbkModeController(pi) {
  let enabled = false;
  let loaded = false;

  function setStatus(ctx) {
    ctx?.ui?.setStatus?.(BBK_MODE_STATUS_KEY, enabled ? "BBK" : undefined);
  }
  function restore(ctx) {
    let found = false;
    let restored = false;
    let branch = [];
    try { branch = ctx?.sessionManager?.getBranch?.() || []; } catch {}
    for (const entry of Array.isArray(branch) ? branch : []) {
      if (entry?.type !== "custom" || entry?.customType !== BBK_MODE_ENTRY_TYPE) continue;
      const value = entry?.data?.enabled;
      if (typeof value === "boolean") {
        found = true;
        restored = value;
      }
    }
    enabled = found ? restored : false;
    loaded = true;
    setStatus(ctx);
    return enabled;
  }
  function ensure(ctx) {
    if (!loaded) restore(ctx);
    return enabled;
  }
  function persist(next, ctx) {
    ensure(ctx);
    const changed = enabled !== next;
    enabled = next;
    loaded = true;
    if (changed && typeof pi.appendEntry === "function") {
      pi.appendEntry(BBK_MODE_ENTRY_TYPE, {
        schema: BBK_MODE_SCHEMA,
        package_version: version,
        enabled,
      });
    }
    setStatus(ctx);
    return changed;
  }
  function enter(ctx) { return persist(true, ctx); }
  function exit(ctx) { return persist(false, ctx); }
  function promptOverlay(event, ctx) {
    ensure(ctx);
    if (!enabled) return undefined;
    const existing = Array.isArray(event?.systemPrompt) ? event.systemPrompt : [];
    const withoutPriorOverlay = existing.filter(
      item => !String(item || "").includes(BBK_MODE_PROMPT_MARKER),
    );
    return { systemPrompt: [...withoutPriorOverlay, BBK_MODE_SYSTEM_PROMPT] };
  }
  return { enter, exit, restore, ensure, promptOverlay, isEnabled: () => enabled };
}

function registerBbkEntrypoint(pi, mode) {
  async function exitMode(ctx) {
    const changed = mode.exit(ctx);
    ctx?.ui?.notify?.(changed ? "BBK mode exited" : "BBK mode is not active", "info");
    return undefined;
  }

  pi.registerCommand("bbk", {
    description: "enter persistent BBK mode; optionally submit the first directive",
    handler: async (first, second) => {
      const { args, ctx } = commandInvocation(first, second);
      const trimmed = String(args || "").trim();
      const lower = trimmed.toLowerCase();
      if (["status", "--status"].includes(lower)) {
        return publishCommandResult(pi, ctx, await runBbk(["status"], ctx?.cwd || process.cwd()), "bbk status");
      }
      if (["exit", "off", "--exit", "--off"].includes(lower)) return exitMode(ctx);

      const changed = mode.enter(ctx);
      if (!trimmed) {
        ctx?.ui?.notify?.(changed ? "BBK mode entered; ordinary messages now use BBK context" : "BBK mode is already active", "info");
        return undefined;
      }
      if (typeof pi.sendUserMessage !== "function") {
        ctx?.ui?.notify?.("BBK mode is active, but this OMP host does not expose sendUserMessage. Submit the directive as a normal message.", "warning");
        return undefined;
      }
      const options = ctx?.isIdle?.() === false ? { deliverAs: "followUp" } : undefined;
      await pi.sendUserMessage(trimmed, options);
      ctx?.ui?.notify?.(changed ? "BBK mode entered; first directive submitted" : "BBK directive submitted", "info");
      return undefined;
    },
  });

  pi.registerCommand("bbk:exit", {
    description: "exit persistent BBK mode and return to normal OMP prompting",
    handler: async (first, second) => {
      const { ctx } = commandInvocation(first, second);
      return exitMode(ctx);
    },
  });
}


const THINKING_LEVELS = ["auto", "off", "minimal", "low", "medium", "high", "xhigh", "max"];
const MODEL_ALIASES = ["@default", "@smol", "@slow", "@vision", "@plan", "@designer", "@commit", "@tiny", "@task", "@advisor"];

function modelSelector(value) {
  if (typeof value === "string") return value.trim();
  if (!value || typeof value !== "object") return "";
  const provider = value.provider || value.providerId || value.providerName || value.api;
  const id = value.id || value.modelId || value.model || value.name;
  if (provider && id && !String(id).startsWith(`${provider}/`)) return `${provider}/${id}`;
  return String(id || "").trim();
}
async function availableModelSelectors(ctx) {
  let values = [];
  try { values = await Promise.resolve(ctx?.models?.list?.() || []); } catch {}
  return [...new Set((Array.isArray(values) ? values : []).map(modelSelector).filter(Boolean))].sort();
}
async function selectorResolution(ctx, selector) {
  if (typeof ctx?.models?.resolve !== "function") return null;
  try { return Boolean(await Promise.resolve(ctx.models.resolve(selector))); }
  catch { return false; }
}
async function unresolvedSelectors(ctx, selectors) {
  const result = [];
  for (const selector of [...new Set((selectors || []).filter(Boolean))]) {
    if (await selectorResolution(ctx, selector) === false) result.push(selector);
  }
  return result;
}
function routeSummaryText(details) {
  const lines = [
    `Active BBK-managed profile: ${details.active_profile || "unknown"}`,
    `Source: ${details.source || "unknown"}`,
    "",
    "Routes:",
  ];
  for (const item of details.summary || []) {
    lines.push(`- ${item.roles} roles: ${item.model} / ${item.thinkingLevel}`);
  }
  if (details.precedence_note) lines.push("", `Precedence: ${details.precedence_note}`);
  return lines.join("\n");
}
async function publishRoutingResult(_pi, ctx, value, label) {
  if (value.code === 0) {
    const details = value.details || {};
    let text;
    if (details.status === "EXPORTED") {
      text = `${label}: EXPORTED${details.path ? `\npath: ${details.path}` : ""}`;
    } else if (details.roles || details.summary) {
      text = routeSummaryText(details);
      if (typeof details.changed_role_count === "number") {
        text += `\nChanged roles: ${details.changed_role_count}`;
      }
      text += "\nApplies to future BBK sub-agent spawns.";
    } else {
      text = conciseResultText(value, label);
    }
    ctx?.ui?.notify?.(text, "info");
  } else {
    ctx?.ui?.notify?.(conciseResultText(value, label), "error");
  }
  // Deliberately UI-only. Slash-command handlers return no structured value,
  // so neither prompt flow nor RPC wrappers can surface routing JSON as chat.
  return undefined;
}
async function chooseModel(ctx, status, role) {
  const current = status.roles?.[role]?.model;
  const profileModels = (status.available_profiles || []).flatMap(profile => (profile.summary || []).map(item => item.model));
  const liveModels = await availableModelSelectors(ctx);
  const selectors = [...new Set([current, ...profileModels, ...MODEL_ALIASES, ...liveModels].filter(Boolean))];
  const customLabel = "Enter a custom model selector…";
  const selected = await ctx.ui.select(`Model for ${role}`, [...selectors, customLabel]);
  if (!selected) return null;
  if (selected !== customLabel) return selected;
  const entered = await ctx.ui.input("Model selector", current || "provider/model");
  return String(entered || "").trim() || null;
}
async function interactiveRoutingMenu(pi, ctx) {
  if (!ctx?.hasUI || typeof ctx?.ui?.select !== "function") {
    return publishRoutingResult(pi, ctx, await runRouting(["status"], ctx?.cwd || process.cwd()), "bbk:models status");
  }
  const initial = await runRouting(["status"], ctx.cwd || process.cwd());
  if (initial.code !== 0) return publishRoutingResult(pi, ctx, initial, "bbk:models status");
  const action = await ctx.ui.select("BBK OMP sub-agent model routing", [
    "Apply a routing profile",
    "Edit one sub-agent",
    "View current routing",
    "Apply a profile file",
    "Export current routing",
    "Cancel",
  ]);
  if (!action || action === "Cancel") return;
  if (action === "View current routing") {
    return publishRoutingResult(pi, ctx, initial, "bbk:models status");
  }
  if (action === "Apply a routing profile") {
    const profiles = initial.details.available_profiles || [];
    const labels = profiles.map(item => `${item.id} — ${item.description}`);
    const selected = await ctx.ui.select("Routing profile", labels);
    if (!selected) return;
    const index = labels.indexOf(selected);
    const profile = profiles[index];
    if (!profile) return;
    const unresolved = await unresolvedSelectors(ctx, (profile.summary || []).map(item => item.model));
    const availability = unresolved.length
      ? `\n\nOMP cannot currently resolve: ${unresolved.join(", ")}\nThe profile can still be saved for use after model/provider configuration is available.`
      : "";
    const ok = await ctx.ui.confirm("Apply routing profile?", `${profile.id}\n\n${profile.description}\n\nFuture BBK sub-agent spawns will use this profile.${availability}`);
    if (!ok) return;
    return publishRoutingResult(pi, ctx, await runRouting(["apply-profile", profile.id], ctx.cwd || process.cwd()), `bbk:models ${profile.id}`);
  }
  if (action === "Edit one sub-agent") {
    const roles = Object.keys(initial.details.roles || {}).sort();
    const labels = roles.map(role => `${role} — ${initial.details.roles[role].model} / ${initial.details.roles[role].thinkingLevel}`);
    const selected = await ctx.ui.select("BBK sub-agent", labels);
    if (!selected) return;
    const role = roles[labels.indexOf(selected)];
    if (!role) return;
    const model = await chooseModel(ctx, initial.details, role);
    if (!model) return;
    const currentLevel = initial.details.roles?.[role]?.thinkingLevel || "high";
    const levels = [currentLevel, ...THINKING_LEVELS.filter(value => value !== currentLevel)];
    const thinking = await ctx.ui.select(`Thinking level for ${role}`, levels);
    if (!thinking) return;
    const resolved = await selectorResolution(ctx, model);
    const availability = resolved === false
      ? "\n\nWarning: OMP cannot currently resolve this selector. Save it only if the model/provider or alias will be configured before the agent is spawned."
      : "";
    const ok = await ctx.ui.confirm("Apply sub-agent route?", `${role}\nModel: ${model}\nThinking: ${thinking}${availability}`);
    if (!ok) return;
    return publishRoutingResult(pi, ctx, await runRouting(["set-role", role, "--model", model, "--thinking-level", thinking], ctx.cwd || process.cwd()), `bbk:models ${role}`);
  }
  if (action === "Apply a profile file") {
    const rawPath = await ctx.ui.input("Profile JSON path", "");
    const profilePath = String(rawPath || "").trim();
    if (!profilePath) return;
    const ok = await ctx.ui.confirm("Apply profile file?", profilePath);
    if (!ok) return;
    return publishRoutingResult(pi, ctx, await runRouting(["apply-file", profilePath], ctx.cwd || process.cwd()), "bbk:models apply-file");
  }
  if (action === "Export current routing") {
    const rawPath = await ctx.ui.input("Export path", "bbk-omp-model-routing.json");
    const outputPath = String(rawPath || "").trim();
    if (!outputPath) return;
    const rawId = await ctx.ui.input("Profile id", "exported-profile");
    const profileId = String(rawId || "").trim();
    if (!profileId) return;
    return publishRoutingResult(pi, ctx, await runRouting(["export", outputPath, "--id", profileId], ctx.cwd || process.cwd()), "bbk:models export");
  }
}

function registerModelRoutingCommand(pi) {
  pi.registerCommand("bbk:models", {
    description: "interactively inspect or change BBK OMP sub-agent model routing",
    handler: async (first, second) => {
      const { args, ctx } = commandInvocation(first, second);
      const tokens = splitArgs(args);
      if (!tokens.length) return interactiveRoutingMenu(pi, ctx);
      const [action, ...rest] = tokens;
      let argv;
      if (["status", "profiles", "list"].includes(action)) argv = ["status"];
      else if (action === "profile" && rest.length === 1) argv = ["apply-profile", rest[0]];
      else if (action === "set" && rest.length === 3) argv = ["set-role", rest[0], "--model", rest[1], "--thinking-level", rest[2]];
      else if (["apply", "apply-file"].includes(action) && rest.length === 1) argv = ["apply-file", rest[0]];
      else if (action === "export" && rest.length >= 1) argv = ["export", rest[0], ...(rest[1] ? ["--id", rest[1]] : [])];
      else {
        ctx?.ui?.notify?.("Usage: /bbk:models [status | profile <id> | set <role> <model> <thinking> | apply <file> | export <file> [id]]", "warning");
        return;
      }
      return publishRoutingResult(pi, ctx, await runRouting(argv, ctx?.cwd || process.cwd()), "bbk:models");
    },
  });
}

export default function bbkExtension(pi) {
  const { z } = pi.zod;
  const text = () => z.string().optional();
  const texts = () => z.array(z.string()).optional();
  const bool = () => z.boolean().optional();
  pi.setLabel?.("Blueprint Bootstrap Kit");

  registerCliTool(pi, {
    name: "bbk_init", label: "BBK Initialize", description: "Initialize or add missing .bbk project records without overwriting existing records.",
    parameters: z.object({ root: text(), title: text(), projectId: text() }),
    argv: p => ["init", ...rootArgs(p.root), ...(p.title ? ["--title", p.title] : []), ...(p.projectId ? ["--project-id", p.projectId] : [])],
  });
  registerCliTool(pi, {
    name: "bbk_status", label: "BBK Status", description: "Read package/project, candidate, workspace, profile and gate status.",
    parameters: z.object({ root: text() }), argv: p => ["status", ...rootArgs(p.root)],
  });
  registerCliTool(pi, {
    name: "bbk_manifest", label: "BBK Manifest", description: "Create an exact-byte and canonical-JSON manifest.",
    parameters: z.object({ root: text(), source: text(), output: text() }),
    argv: p => ["manifest", "create", ...rootArgs(p.root), ...(p.source ? ["--source", p.source] : []), ...(p.output ? ["--output", p.output] : [])],
  });
  registerCliTool(pi, {
    name: "bbk_candidate", label: "BBK Candidate", description: "Freeze, check, inspect, invalidate or verify an exact candidate.",
    parameters: z.object({ action: z.enum(["freeze", "check", "status", "invalidate", "verify"]), id: text(), manifest: text(), root: text(), note: text(), reason: text() }),
    argv: p => p.action === "verify"
      ? ["candidate", "verify", p.manifest]
      : ["candidate", p.action, ...rootArgs(p.root), ...(p.id ? ["--id", p.id] : []), ...(p.note && p.action === "freeze" ? ["--note", p.note] : []), ...(p.reason && p.action === "invalidate" ? ["--reason", p.reason] : [])],
  });
  registerCliTool(pi, {
    name: "bbk_gate", label: "BBK Gate", description: "Run configured deterministic gates against a draft or exact candidate.",
    parameters: z.object({ phase: z.string(), root: text(), candidate: text(), gates: texts(), noReuse: bool() }),
    argv: p => ["gate", "run", ...rootArgs(p.root), "--phase", p.phase, ...(p.candidate ? ["--candidate", p.candidate] : []), ...repeated("--gate", p.gates), ...(p.noReuse ? ["--no-reuse"] : [])],
  });
  registerCliTool(pi, {
    name: "bbk_workspace", label: "BBK Workspace", description: "Create, list, inspect, renew, or conservatively clean BBK-owned Git worktrees with leases.",
    parameters: z.object({ action: z.enum(["create", "list", "inspect", "renew", "cleanup"]), root: text(), id: text(), base: text(), purpose: text(), force: bool() }),
    argv: p => ["workspace", p.action, ...rootArgs(p.root), ...(p.id ? ["--id", p.id] : []), ...(p.base && p.action === "create" ? ["--base", p.base] : []), ...(p.purpose && p.action === "create" ? ["--purpose", p.purpose] : []), ...(p.force && p.action === "cleanup" ? ["--force"] : [])],
  });
  registerCliTool(pi, {
    name: "bbk_fit_validate", label: "BBK Solution–Outcome Fit", description: "Validate a SolutionOutcomeFit and derive its planning disposition.",
    parameters: z.object({ path: z.string() }), argv: p => ["fit", "validate", p.path],
  });
  registerCliTool(pi, {
    name: "bbk_fit_check_chain", label: "BBK Fit Chain", description: "Check one fit against structure, execution slices and work units.",
    parameters: z.object({ fit: z.string(), structures: texts(), slices: texts(), workUnits: texts() }),
    argv: p => ["fit", "check-chain", "--fit", p.fit, ...repeated("--structure", p.structures), ...repeated("--slice", p.slices), ...repeated("--work-unit", p.workUnits)],
  });
  registerCliTool(pi, {
    name: "bbk_structure_validate", label: "BBK Structure", description: "Validate a domain-neutral ImplementationStructureContract.",
    parameters: z.object({ path: z.string() }), argv: p => ["structure", "validate", p.path],
  });
  registerCliTool(pi, {
    name: "bbk_slice_validate", label: "BBK Execution Slice", description: "Validate a domain-neutral execution slice.",
    parameters: z.object({ path: z.string() }), argv: p => ["slice", "validate", p.path],
  });
  registerCliTool(pi, {
    name: "bbk_work_unit_validate", label: "BBK Work Unit", description: "Validate legacy alpha.3 or current alpha.6 work-unit syntax.",
    parameters: z.object({ path: z.string() }), argv: p => ["work-unit", "validate", p.path],
  });
  registerCliTool(pi, {
    name: "bbk_profile_resolve", label: "BBK Profile Resolver", description: "Resolve a language/domain profile and centrally dispatch qualified state/effect and review-assurance capabilities.",
    parameters: z.object({ id: z.string(), version: text(), root: text(), source: text(), profileRoots: texts(), role: text(), taskProfile: text(), assuranceTier: text(), paths: texts(), hints: texts(), changeClasses: texts(), solutionOutcomeFits: texts(), structures: texts(), slices: texts(), stateDecisionEffects: texts(), assuranceContracts: texts(), reviewManifests: texts(), evidenceInputs: texts(), workUnit: text(), allowUnverified: bool(), runTools: bool(), writeLock: bool() }),
    argv: p => ["profile", "resolve", ...rootArgs(p.root), "--id", p.id,
      ...(p.version ? ["--version", p.version] : []), ...(p.source ? ["--source", p.source] : []),
      ...repeated("--profile-root", p.profileRoots), ...(p.role ? ["--role", p.role] : []),
      ...(p.taskProfile ? ["--task-profile", p.taskProfile] : []), ...(p.assuranceTier ? ["--assurance-tier", p.assuranceTier] : []),
      ...repeated("--path", p.paths), ...repeated("--hint", p.hints), ...repeated("--change-class", p.changeClasses),
      ...repeated("--solution-outcome-fit", p.solutionOutcomeFits), ...repeated("--structure-contract", p.structures), ...repeated("--execution-slice", p.slices),
      ...repeated("--state-decision-effect", p.stateDecisionEffects), ...repeated("--assurance-contract", p.assuranceContracts), ...repeated("--review-manifest", p.reviewManifests), ...repeated("--evidence-input", p.evidenceInputs),
      ...(p.workUnit ? ["--work-unit", p.workUnit] : []), ...(p.allowUnverified ? ["--allow-unverified"] : []), ...(p.runTools ? ["--run-tools"] : []), ...(p.writeLock ? ["--write-lock"] : [])],
  });
  registerCliTool(pi, {
    name: "bbk_profile_dispatch", label: "BBK Profile Capability Dispatch", description: "Dispatch one qualified profile capability through the read-only, content-addressed typed profile protocol introduced in alpha.8.",
    parameters: z.object({ operation: z.enum(["state-effect", "state-effect-inventory", "state-effect-review", "review-context", "review-lens", "evidence-adapter"]), id: z.string(), version: text(), root: text(), source: text(), profileRoots: texts(), role: text(), taskProfile: text(), assuranceTier: text(), paths: texts(), hints: texts(), changeClasses: texts(), lensIds: texts(), assignmentIds: texts(), stateDecisionEffect: text(), stateEffectInventory: text(), assuranceContract: text(), reviewManifest: text(), reviewContext: text(), evidenceInput: text(), allowUnverified: bool(), runTools: bool(), output: text() }),
    argv: p => ["profile", "dispatch", "--operation", p.operation, ...rootArgs(p.root), "--id", p.id,
      ...(p.version ? ["--version", p.version] : []), ...(p.source ? ["--source", p.source] : []), ...repeated("--profile-root", p.profileRoots),
      ...(p.role ? ["--role", p.role] : []), ...(p.taskProfile ? ["--task-profile", p.taskProfile] : []), ...(p.assuranceTier ? ["--assurance-tier", p.assuranceTier] : []),
      ...repeated("--path", p.paths), ...repeated("--hint", p.hints), ...repeated("--change-class", p.changeClasses), ...repeated("--lens-id", p.lensIds), ...repeated("--assignment-id", p.assignmentIds),
      ...(p.stateDecisionEffect ? ["--state-decision-effect", p.stateDecisionEffect] : []), ...(p.stateEffectInventory ? ["--state-effect-inventory", p.stateEffectInventory] : []),
      ...(p.assuranceContract ? ["--assurance-contract", p.assuranceContract] : []), ...(p.reviewManifest ? ["--review-manifest", p.reviewManifest] : []), ...(p.reviewContext ? ["--review-context", p.reviewContext] : []),
      ...(p.evidenceInput ? ["--evidence-input", p.evidenceInput] : []), ...(p.allowUnverified ? ["--allow-unverified"] : []), ...(p.runTools ? ["--run-tools"] : []), ...(p.output ? ["--output", p.output] : [])],
  });
  registerCliTool(pi, {
    name: "bbk_assurance_validate", label: "BBK Assurance Contract", description: "Validate an exact proportional AssuranceContract.",
    parameters: z.object({ path: z.string() }), argv: p => ["assurance", "validate", p.path],
  });
  registerCliTool(pi, {
    name: "bbk_state_effect_validate", label: "BBK State–Decision–Effect", description: "Validate nested canonical state, decision, effect, recovery, and formalization design.",
    parameters: z.object({ path: z.string() }), argv: p => ["state-effect", "validate", p.path],
  });
  registerCliTool(pi, {
    name: "bbk_trace_validate", label: "BBK Transition Trace", description: "Validate a state-transition trace fixture against its declared design revision.",
    parameters: z.object({ path: z.string() }), argv: p => ["trace", "validate", p.path],
  });
  registerCliTool(pi, {
    name: "bbk_structure_review", label: "BBK Planned/Actual Structure Review", description: "Compare an accepted structure/state-effect design with an actual candidate inventory.",
    parameters: z.object({ contract: z.string(), inventory: z.string(), output: text() }),
    argv: p => ["structure", "review", "--contract", p.contract, "--inventory", p.inventory, ...(p.output ? ["--output", p.output] : [])],
  });
  registerCliTool(pi, {
    name: "bbk_evidence_validate", label: "BBK Evidence Receipt v2", description: "Validate an evidence receipt without treating it as an assertion pass.",
    parameters: z.object({ path: z.string() }), argv: p => ["evidence", "validate", p.path],
  });
  registerCliTool(pi, {
    name: "bbk_review_plan", label: "BBK Review Plan", description: "Compile the smallest sufficient ReviewManifest from an AssuranceContract.",
    parameters: z.object({ assurance: z.string(), id: z.string(), purpose: z.string(), subject: text(), subjectRef: text(), subjectKind: text(), subjectRevision: text(), capabilities: texts(), output: text() }),
    argv: p => ["review", "plan", "--assurance", p.assurance, "--id", p.id, "--purpose", p.purpose,
      ...(p.subject ? ["--subject", p.subject] : []), ...(p.subjectRef ? ["--subject-ref", p.subjectRef] : []),
      ...(p.subjectKind ? ["--subject-kind", p.subjectKind] : []), ...(p.subjectRevision ? ["--subject-revision", p.subjectRevision] : []),
      ...repeated("--capability", p.capabilities), ...(p.output ? ["--output", p.output] : [])],
  });
  registerCliTool(pi, {
    name: "bbk_review_context", label: "BBK Review Context", description: "Compile exact review context, omissions, content roots, and semantic shards.",
    parameters: z.object({ manifest: z.string(), root: text(), source: text(), id: text(), includes: texts(), excludes: texts(), output: text() }),
    argv: p => ["review", "context", "--manifest", p.manifest, ...rootArgs(p.root), ...(p.source ? ["--source", p.source] : []),
      ...(p.id ? ["--id", p.id] : []), ...repeated("--include", p.includes), ...repeated("--exclude", p.excludes), ...(p.output ? ["--output", p.output] : [])],
  });
  registerCliTool(pi, {
    name: "bbk_review_run", label: "BBK Review Run", description: "Assemble and aggregate exact review attempts, receipts, findings, and dispositions.",
    parameters: z.object({ manifest: z.string(), context: z.string(), id: z.string(), root: text(), attempts: texts(), receipts: texts(), findings: texts(), dispositions: texts(), predecessor: text(), output: text() }),
    argv: p => ["review", "run", "--manifest", p.manifest, "--context", p.context, "--id", p.id, ...rootArgs(p.root),
      ...repeated("--attempt", p.attempts), ...repeated("--receipt", p.receipts), ...repeated("--finding", p.findings), ...repeated("--disposition", p.dispositions),
      ...(p.predecessor ? ["--predecessor", p.predecessor] : []), ...(p.output ? ["--output", p.output] : [])],
  });
  registerCliTool(pi, {
    name: "bbk_review_status", label: "BBK Review Status", description: "Inspect and validate a review manifest, context, run, attempt, finding, disposition, evidence receipt, or learning candidate.",
    parameters: z.object({ path: z.string() }), argv: p => ["review", "inspect", p.path],
  });
  registerCliTool(pi, {
    name: "bbk_review_reconcile", label: "BBK Finding Reconciliation", description: "Propose duplicate, recurrence, shared-root-cause, overlap, or contradiction relationships without closing findings.",
    parameters: z.object({ findings: z.array(z.string()), output: text() }),
    argv: p => ["review", "reconcile", ...repeated("--finding", p.findings), ...(p.output ? ["--output", p.output] : [])],
  });
  registerCliTool(pi, {
    name: "bbk_review_close", label: "BBK Finding Disposition", description: "Create an explicit successor disposition from exact closure evidence and authority.",
    parameters: z.object({ finding: z.string(), id: z.string(), disposition: z.enum(["FIXED", "REBUTTED", "ACCEPTED_RISK", "FALSE_POSITIVE", "DUPLICATE_OF", "SUPERSEDED", "DEFERRED", "OUT_OF_SCOPE", "REMAINS_OPEN"]), successorRef: z.string(), successorDigest: text(), successorFile: text(), evidence: texts(), reviewAttempt: text(), authority: text(), residualImpact: z.string(), reopenTriggers: texts(), output: z.string() }),
    argv: p => ["review", "close", "--finding", p.finding, "--id", p.id, "--disposition", p.disposition, "--successor-ref", p.successorRef,
      ...(p.successorDigest ? ["--successor-digest", p.successorDigest] : []), ...(p.successorFile ? ["--successor-file", p.successorFile] : []),
      ...repeated("--evidence", p.evidence), ...(p.reviewAttempt ? ["--review-attempt", p.reviewAttempt] : []), ...(p.authority ? ["--authority", p.authority] : []),
      "--residual-impact", p.residualImpact, ...repeated("--reopen-trigger", p.reopenTriggers), "--output", p.output],
  });
  registerCliTool(pi, {
    name: "bbk_review_learn", label: "BBK Learning Candidate", description: "Create a proposed learning candidate without changing methods, roles, profiles, gates, or policy.",
    parameters: z.object({ id: z.string(), type: z.string(), lesson: z.string(), scope: z.string(), supporting: texts(), contrary: texts(), findings: texts(), runs: texts(), dispositions: texts(), confidence: z.string(), uncertainty: z.string(), action: z.string(), privacyClass: text(), exportClass: text(), output: z.string() }),
    argv: p => ["review", "learn", "--id", p.id, "--type", p.type, "--lesson", p.lesson, "--scope", p.scope,
      ...repeated("--supporting", p.supporting), ...repeated("--contrary", p.contrary), ...repeated("--finding", p.findings), ...repeated("--run", p.runs), ...repeated("--disposition", p.dispositions),
      "--confidence", p.confidence, "--uncertainty", p.uncertainty, "--action", p.action,
      ...(p.privacyClass ? ["--privacy-class", p.privacyClass] : []), ...(p.exportClass ? ["--export-class", p.exportClass] : []), "--output", p.output],
  });

  registerCliTool(pi, {
    name: "bbk_package_verify", label: "BBK Package Verify", description: "Verify the installed package against its content manifest.",
    parameters: z.object({ root: text() }), argv: p => ["package", "verify", ...(p.root ? [p.root] : [])],
  });

  const bbkMode = createBbkModeController(pi);
  registerBbkEntrypoint(pi, bbkMode);
  registerModelRoutingCommand(pi);
  registerCommand(pi, "bbk:init", "initialize BBK in the current project", ["init"]);
  registerCommand(pi, "bbk:status", "show BBK status", ["status"]);
  registerCommand(pi, "bbk:doctor", "run BBK diagnostics", ["doctor"]);
  registerCommand(pi, "bbk:freeze", "<candidate-id>", ["candidate", "freeze", "--id"], { requireArgs: true });
  pi.registerCommand("bbk:gate", {
    description: "Run a gate phase: /bbk:gate <phase> [candidate-id]",
    handler: async (first, second) => {
      const { args, ctx } = commandInvocation(first, second);
      const [phase, candidate] = splitArgs(args);
      if (!phase) { ctx?.ui?.notify?.("Usage: /bbk:gate <phase> [candidate-id]", "warning"); return; }
      const argv = ["gate", "run", "--phase", phase, ...(candidate ? ["--candidate", candidate] : [])];
      return publishCommandResult(pi, ctx, await runBbk(argv, ctx?.cwd || process.cwd()), "bbk:gate");
    },
  });
  registerCommand(pi, "bbk:fit:validate", "<fit-path>", ["fit", "validate"], { requireArgs: true });
  registerCommand(pi, "bbk:fit:check", "--fit <path> [--structure/--slice/--work-unit <path>]", ["fit", "check-chain"], { requireArgs: true });
  registerCommand(pi, "bbk:structure:validate", "<contract-path>", ["structure", "validate"], { requireArgs: true });
  registerCommand(pi, "bbk:slice:validate", "<slice-path>", ["slice", "validate"], { requireArgs: true });
  registerCommand(pi, "bbk:work-unit:validate", "<work-unit-path>", ["work-unit", "validate"], { requireArgs: true });
  registerCommand(pi, "bbk:profile:resolve", "--id <profile> [resolver options]", ["profile", "resolve"], { requireArgs: true });
  registerCommand(pi, "bbk:profile:dispatch", "--operation <operation> --id <profile> [typed capability inputs]", ["profile", "dispatch"], { requireArgs: true });
  registerCommand(pi, "bbk:assurance:validate", "<assurance-contract-path>", ["assurance", "validate"], { requireArgs: true });
  registerCommand(pi, "bbk:state-effect:validate", "<state-effect-design-path>", ["state-effect", "validate"], { requireArgs: true });
  registerCommand(pi, "bbk:trace:validate", "<transition-trace-path>", ["trace", "validate"], { requireArgs: true });
  registerCommand(pi, "bbk:structure:review", "--contract <path> --inventory <path> [--output <path>]", ["structure", "review"], { requireArgs: true });
  registerCommand(pi, "bbk:evidence:validate", "<evidence-receipt-path>", ["evidence", "validate"], { requireArgs: true });
  registerCommand(pi, "bbk:review-plan", "--assurance <path> --id <id> --purpose <purpose> [options]", ["review", "plan"], { requireArgs: true });
  registerCommand(pi, "bbk:review-context", "--manifest <path> [context options]", ["review", "context"], { requireArgs: true });
  registerCommand(pi, "bbk:review-run", "--manifest <path> --context <path> --id <id> [attempt/evidence/finding options]", ["review", "run"], { requireArgs: true });
  registerCommand(pi, "bbk:review-status", "<review-object-path>", ["review", "inspect"], { requireArgs: true });
  registerCommand(pi, "bbk:review-reconcile", "--finding <path> [--finding <path>...]", ["review", "reconcile"], { requireArgs: true });
  registerCommand(pi, "bbk:review-close", "--finding <path> --id <id> --disposition <value> --successor-ref <ref> --residual-impact <text> --output <path>", ["review", "close"], { requireArgs: true });
  registerCommand(pi, "bbk:review-learn", "--id <id> --type <type> --lesson <text> --scope <scope> --confidence <value> --uncertainty <text> --action <text> --output <path>", ["review", "learn"], { requireArgs: true });

  pi.on?.("before_agent_start", async (event, ctx) => bbkMode.promptOverlay(event, ctx));
  const restoreBbkMode = async (_event, ctx) => {
    const active = bbkMode.restore(ctx);
    if (_event?.type === "session_start") {
      ctx?.ui?.notify?.(`BBK ${version} loaded in ${ctx?.cwd || process.cwd()}${active ? "; BBK mode restored" : ""}`, "info");
    }
  };
  for (const eventName of ["session_start", "session_switch", "session_branch", "session_tree"]) {
    pi.on?.(eventName, restoreBbkMode);
  }
  pi.on?.("tool_call", async event => {
    const encoded = JSON.stringify(event.input || {});
    if (["bash", "write", "edit"].includes(event.toolName) && protectedFragments.some(fragment => encoded.includes(fragment))) {
      return { block: true, reason: "BBK protects frozen candidates, attestations, gate receipts, review runs, findings, and dispositions. Create a successor or write an external annotation." };
    }
  });
}
