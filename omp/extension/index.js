import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { readFileSync, realpathSync, statSync } from "node:fs";
import { homedir } from "node:os";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { TextDecoder } from "node:util";

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
const defaultRoutingBindingPath = path.join(extensionDir, "bbk-package-root.json");
const explicitRoutingBindingPath = process.env.BBK_OMP_ROUTING_BINDING || null;
const versionPath = (() => {
  try { readFileSync(path.join(extensionDir, "VERSION")); return path.join(extensionDir, "VERSION"); }
  catch { return path.join(sourceRoot, "VERSION"); }
})();
let version = "0.1.0-alpha.15";
try { version = readFileSync(versionPath, "utf8").trim() || version; } catch {}

function normalizedFsPath(value) {
  const requested = path.resolve(String(value || ""));
  let probe = requested;
  const suffix = [];
  let resolved = requested;
  while (true) {
    try {
      resolved = typeof realpathSync.native === "function" ? realpathSync.native(probe) : realpathSync(probe);
      if (suffix.length) resolved = path.join(resolved, ...suffix.reverse());
      break;
    } catch {
      const parent = path.dirname(probe);
      if (parent === probe) break;
      suffix.push(path.basename(probe));
      probe = parent;
    }
  }
  return process.platform === "win32" ? resolved.toLowerCase() : resolved;
}
function sameFsPath(left, right) {
  return normalizedFsPath(left) === normalizedFsPath(right);
}
function pathContains(root, candidate) {
  const base = normalizedFsPath(root);
  const child = normalizedFsPath(candidate);
  return child === base || child.startsWith(base.endsWith(path.sep) ? base : `${base}${path.sep}`);
}
function readableFile(target) {
  try { readFileSync(target); return true; } catch { return false; }
}
function projectOmpInstallExpectation(projectRoot) {
  const extensionRoot = path.join(projectRoot, ".omp", "extensions", "bbk");
  const routingState = path.join(projectRoot, ".bbk-kit", "effective-omp-model-routing.json");
  if (pathExists(extensionRoot, { directory: true })) return extensionRoot;
  if (readableFile(routingState)) return routingState;
  const manifestPath = path.join(projectRoot, ".bbk-kit-install.json");
  if (!readableFile(manifestPath)) return null;
  try {
    const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
    if (manifest?.schema === "bbk.install-manifest.v1" && manifest?.omp === true) return manifestPath;
  } catch {}
  return null;
}
function pathExists(candidate, { directory = false } = {}) {
  try {
    const stat = statSync(candidate);
    return directory ? stat.isDirectory() : true;
  } catch {
    return false;
  }
}
function readRoutingBinding(bindingPath) {
  try {
    const value = JSON.parse(readFileSync(bindingPath, "utf8"));
    if (!["bbk.omp-package-binding.v2", "bbk.omp-package-binding.v3"].includes(value?.schema)) return null;
    if (!value?.package_root || !value?.manifest_path || !value?.omp_agents || !value?.state_path) return null;
    return value;
  } catch {
    return null;
  }
}
function routingTargetFromPath(bindingPath, source) {
  const resolved = path.resolve(bindingPath);
  const binding = readRoutingBinding(resolved);
  if (!binding) return null;
  const scope = binding.scope === "project" ? "project" : binding.scope === "user" ? "user" : "unknown";
  const projectRoot = typeof binding.project_root === "string" && binding.project_root.trim()
    ? path.resolve(binding.project_root)
    : null;
  if (binding.schema === "bbk.omp-package-binding.v3") {
    if (!['project', 'user'].includes(scope)) return null;
    if (scope === "project" && !projectRoot) return null;
    if (scope === "user" && projectRoot) return null;
  }
  return {
    scope,
    projectRoot,
    bindingPath: resolved,
    binding,
    packageRoot: path.resolve(binding.package_root || binding.path),
    source,
  };
}

function ancestorDirectories(start) {
  const result = [];
  let current = path.resolve(start || process.cwd());
  for (;;) {
    result.push(current);
    const parent = path.dirname(current);
    if (parent === current) break;
    current = parent;
  }
  return result;
}
function nearestProjectRoutingTarget(cwd) {
  for (const projectRoot of ancestorDirectories(cwd)) {
    const extensionRoot = path.join(projectRoot, ".omp", "extensions", "bbk");
    const bindingPath = path.join(extensionRoot, "bbk-package-root.json");
    const expectation = projectOmpInstallExpectation(projectRoot);
    if (!expectation && !pathExists(bindingPath)) continue;
    const target = routingTargetFromPath(bindingPath, "nearest-project");
    if (!target) {
      throw new Error(`A project-scoped BBK OMP installation is present at ${projectRoot}, but ${bindingPath} is missing or invalid; routing did not fall back to user scope`);
    }
    if (target.scope !== "project") {
      throw new Error(`Project BBK binding ${bindingPath} declares scope ${target.scope}; routing did not fall back to user scope`);
    }
    const declaredRoot = target.projectRoot || projectRoot;
    if (!sameFsPath(declaredRoot, projectRoot)) {
      throw new Error(`Project BBK binding ${bindingPath} declares a different project_root: ${declaredRoot}`);
    }
    target.projectRoot = projectRoot;
    return target;
  }
  const local = routingTargetFromPath(defaultRoutingBindingPath, "loaded-extension");
  if (local?.scope === "project" && local.projectRoot && pathContains(local.projectRoot, cwd)) return local;
  return null;
}

function userRoutingTarget() {
  const local = routingTargetFromPath(defaultRoutingBindingPath, "loaded-extension");
  if (local?.scope === "user") return local;
  const roots = [
    process.env.PI_CODING_AGENT_DIR,
    process.env.OMP_AGENT_DIR,
    path.join(homedir(), ".omp", "agent"),
  ].filter(Boolean);
  for (const root of roots) {
    const target = routingTargetFromPath(
      path.join(path.resolve(root), "extensions", "bbk", "bbk-package-root.json"),
      "user-installation",
    );
    if (target?.scope === "user") return target;
  }
  return null;
}
function resolveRoutingTarget(cwd, requestedScope = "auto") {
  if (!["auto", "project", "user"].includes(requestedScope)) {
    throw new Error(`Unknown BBK routing target scope: ${requestedScope}`);
  }
  if (explicitRoutingBindingPath) {
    const target = routingTargetFromPath(explicitRoutingBindingPath, "environment");
    if (!target) throw new Error(`BBK_OMP_ROUTING_BINDING is not a valid BBK OMP binding: ${explicitRoutingBindingPath}`);
    if (requestedScope !== "auto" && target.scope !== requestedScope) {
      throw new Error(`BBK_OMP_ROUTING_BINDING is ${target.scope}-scoped, not ${requestedScope}-scoped`);
    }
    return target;
  }
  if (requestedScope === "project") {
    const target = nearestProjectRoutingTarget(cwd);
    if (!target) {
      throw new Error(`No project-scoped BBK OMP installation was found at or above ${path.resolve(cwd)}; project routing was not changed`);
    }
    return target;
  }
  if (requestedScope === "user") {
    const target = userRoutingTarget();
    if (!target) throw new Error("No user-scoped BBK OMP installation was found; user routing was not changed");
    return target;
  }
  const project = nearestProjectRoutingTarget(cwd);
  if (project) return project;
  const local = routingTargetFromPath(defaultRoutingBindingPath, "loaded-extension");
  if (local?.scope === "user") return local;
  const user = userRoutingTarget();
  if (user) return user;
  throw new Error(`No valid BBK OMP routing binding was found for ${path.resolve(cwd)}`);
}

let packageRoot = sourceRoot;
const loadedBinding = routingTargetFromPath(defaultRoutingBindingPath, "loaded-extension");
if (loadedBinding?.packageRoot) packageRoot = loadedBinding.packageRoot;

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
  return process.platform === "win32" && !process.env.BBK_PYTHON
    ? ["-3", "-X", "utf8", cliPath]
    : ["-X", "utf8", cliPath];
}
function scriptPrefix(script) {
  return process.platform === "win32" && !process.env.BBK_PYTHON
    ? ["-3", "-X", "utf8", script]
    : ["-X", "utf8", script];
}
function pythonUtf8Environment(extra = {}) {
  return {
    ...process.env,
    PYTHONUTF8: "1",
    PYTHONIOENCODING: "utf-8",
    ...extra,
  };
}
function decodeStrictUtf8(chunks, streamName) {
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(Buffer.concat(chunks));
  } catch (error) {
    const failure = new Error(`BBK Python ${streamName} was not valid UTF-8: ${String(error?.message || error)}`);
    failure.code = "BBK_INVALID_UTF8";
    failure.streamName = streamName;
    throw failure;
  }
}
function utf8TransportFailure(error, target = null) {
  return {
    code: 2,
    details: {
      schema: "bbk.utf8-transport-error.v1",
      status: "ERROR",
      stream: error?.streamName || null,
      error: String(error?.message || error),
    },
    stdout: "",
    stderr: "",
    ...(target ? { target } : {}),
  };
}
function runRouting(args, cwd, signal, requestedScope = "auto") {
  let target;
  try {
    target = resolveRoutingTarget(cwd, requestedScope);
  } catch (error) {
    return Promise.resolve({
      code: 2,
      details: {
        schema: "bbk.omp-model-routing-target-error.v1",
        status: "ERROR",
        requested_scope: requestedScope,
        error: String(error?.message || error),
      },
      stdout: "",
      stderr: "",
    });
  }
  const targetRoutingCliPath = process.env.BBK_OMP_ROUTING_CLI
    ? path.resolve(process.env.BBK_OMP_ROUTING_CLI)
    : path.join(path.dirname(target.bindingPath), "omp_model_routing.py");
  if (!readableFile(targetRoutingCliPath)) {
    return Promise.resolve({
      code: 2,
      details: {
        schema: "bbk.omp-model-routing-target-error.v1",
        status: "ERROR",
        requested_scope: requestedScope,
        resolved_scope: target.scope,
        resolved_project_root: target.projectRoot || null,
        resolution_source: target.source,
        binding_path: target.bindingPath,
        error: `The selected BBK routing installation is missing its bound router: ${targetRoutingCliPath}; routing did not fall back to another scope or package version`,
      },
      stdout: "",
      stderr: "",
      target,
    });
  }
  return new Promise((resolve, reject) => {
    const child = spawn(pythonCommand(), [...scriptPrefix(targetRoutingCliPath), "--binding", target.bindingPath, "--json", ...args], {
      cwd,
      env: pythonUtf8Environment({ BBK_PACKAGE_ROOT: target.packageRoot }),
      windowsHide: true,
      stdio: ["ignore", "pipe", "pipe"],
    });
    const stdoutChunks = [], stderrChunks = [];
    child.stdout.on("data", chunk => { stdoutChunks.push(Buffer.from(chunk)); });
    child.stderr.on("data", chunk => { stderrChunks.push(Buffer.from(chunk)); });
    const abort = () => child.kill("SIGTERM");
    signal?.addEventListener?.("abort", abort, { once: true });
    child.on("error", reject);
    child.on("close", code => {
      signal?.removeEventListener?.("abort", abort);
      let stdout, stderr;
      try {
        stdout = decodeStrictUtf8(stdoutChunks, "stdout");
        stderr = decodeStrictUtf8(stderrChunks, "stderr");
      } catch (error) {
        resolve(utf8TransportFailure(error, target));
        return;
      }
      let details;
      try { details = stdout.trim() ? JSON.parse(stdout) : { status: code === 0 ? "PASS" : "ERROR" }; }
      catch { details = { status: "ERROR", stdout, stderr, parseError: "BBK OMP routing CLI did not return JSON" }; }
      if (stderr.trim()) details.stderr = stderr;
      details.resolved_scope = details.scope || target.scope;
      details.resolved_project_root = details.project_root || target.projectRoot || null;
      details.resolution_source = target.source;
      resolve({ code, details, stdout, stderr, target });
    });
  });
}
function runBbk(args, cwd, signal) {
  return new Promise((resolve, reject) => {
    const child = spawn(pythonCommand(), [...commandPrefix(), "--json", ...args], {
      cwd, env: pythonUtf8Environment({ BBK_PACKAGE_ROOT: packageRoot }), windowsHide: true, stdio: ["ignore", "pipe", "pipe"],
    });
    const stdoutChunks = [], stderrChunks = [];
    child.stdout.on("data", chunk => { stdoutChunks.push(Buffer.from(chunk)); });
    child.stderr.on("data", chunk => { stderrChunks.push(Buffer.from(chunk)); });
    const abort = () => child.kill("SIGTERM");
    signal?.addEventListener?.("abort", abort, { once: true });
    child.on("error", reject);
    child.on("close", code => {
      signal?.removeEventListener?.("abort", abort);
      let stdout, stderr;
      try {
        stdout = decodeStrictUtf8(stdoutChunks, "stdout");
        stderr = decodeStrictUtf8(stderrChunks, "stderr");
      } catch (error) {
        resolve(utf8TransportFailure(error));
        return;
      }
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
const BBK_MODE_SCHEMA = "bbk.omp-mode-state.v2";
const BBK_PROMPT_RECEIPT_ENTRY_TYPE = "bbk-effective-prompt-receipt";
const BBK_PROMPT_RECEIPT_SCHEMA = "bbk.effective-prompt-receipt.v1";
const BBK_ACTIVITY_WIDGET_KEY = "bbk-worker-activity";
const TASK_SUBAGENT_PROGRESS_CHANNEL = "task:subagent:progress";
const TASK_SUBAGENT_LIFECYCLE_CHANNEL = "task:subagent:lifecycle";
const BBK_CONTROLLER_PROMPT_MARKER = "<bbk-controller-system";
const BBK_AGENT_PROMPT_MARKER = "<bbk-agent-system";
const BBK_AGENT_BLOCK_RE = /<bbk-agent-system\b[^>]*\brole="([^"]+)"[^>]*>[\s\S]*?<\/bbk-agent-system>/i;
const BBK_ROLE_NAME_RE = /^bbk_[a-z0-9_]+$/;
const CONTROLLER_MANDATORY_SKILLS = ["bbk", "bbk-context-routing"];

function oneLine(value, max = 180) {
  const text = String(value ?? "")
    .replace(/\u001B(?:\[[0-?]*[ -/]*[@-~]|\][^\u0007]*(?:\u0007|\u001B\\))/g, "")
    // Progress payloads are host-published but may contain model/tool text.
    // Remove control and invisible format characters before rendering them in
    // the persistent editor-adjacent HUD so they cannot alter terminal state,
    // spoof text direction, or hide content.
    .replace(/[\p{Cc}\p{Cf}\s]+/gu, " ")
    .trim();
  const points = Array.from(text);
  if (points.length <= max) return text;
  return `${points.slice(0, Math.max(1, max - 1)).join("").trimEnd()}…`;
}
function finiteNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) && number >= 0 ? number : undefined;
}
function compactNumber(value) {
  const number = finiteNumber(value);
  if (number === undefined) return "?";
  if (number >= 1_000_000) {
    const digits = number >= 10_000_000 ? 0 : 1;
    return `${(number / 1_000_000).toFixed(digits).replace(/\.0$/, "")}M`;
  }
  if (number >= 1_000) {
    const digits = number >= 100_000 ? 0 : 1;
    return `${(number / 1_000).toFixed(digits).replace(/\.0$/, "")}k`;
  }
  return String(Math.round(number));
}
function contextGauge(progress, { short = false } = {}) {
  const current = finiteNumber(progress?.contextTokens);
  const window = finiteNumber(progress?.contextWindow);
  if (current !== undefined && window && window > 0) {
    const percentage = Math.max(0, current / window * 100);
    const precision = percentage < 10 ? 1 : 0;
    const label = `${compactNumber(current)}/${compactNumber(window)} ${percentage.toFixed(precision)}%`;
    return short ? label : `ctx ${label}`;
  }
  if (current !== undefined) return `${short ? "" : "ctx "}${compactNumber(current)}`;
  const lifetime = finiteNumber(progress?.tokens);
  if (lifetime !== undefined && lifetime > 0) return `${short ? "Σ" : "used "}${compactNumber(lifetime)}`;
  return "";
}
function roleDisplayName(roleName) {
  return String(roleName || "BBK worker")
    .replace(/^bbk_/, "")
    .split("_")
    .filter(Boolean)
    .map(part => part[0]?.toUpperCase() + part.slice(1))
    .join(" ");
}
function progressActivity(progress) {
  if (progress?.retryState) {
    const retry = progress.retryState;
    return `retrying provider request ${retry.attempt || "?"}/${retry.maxAttempts || "?"}: ${oneLine(retry.errorMessage || "rate limited", 96)}`;
  }
  const intent = oneLine(progress?.lastIntent, 112);
  if (intent) return intent;
  const tool = oneLine(progress?.currentTool, 40);
  const args = oneLine(progress?.currentToolArgs, 84);
  if (tool) return args ? `${tool}: ${args}` : `using ${tool}`;
  const outputs = Array.isArray(progress?.recentOutput) ? progress.recentOutput : [];
  const latestOutput = oneLine(outputs.at?.(-1) ?? outputs[outputs.length - 1], 112);
  if (latestOutput) return latestOutput;
  if (progress?.status === "pending") return "starting…";
  if (progress?.status === "running") return "working…";
  return oneLine(progress?.status || "working…", 112);
}

function stripFrontmatter(raw, sourceLabel) {
  const text = String(raw || "").replace(/^\uFEFF/, "");
  if (!text.startsWith("---\n") && !text.startsWith("---\r\n")) return text.trim();
  const match = text.match(/^---\r?\n[\s\S]*?\r?\n---\r?\n/);
  if (!match) throw new Error(`invalid YAML frontmatter in ${sourceLabel}`);
  return text.slice(match[0].length).trim();
}
function packageText(...parts) {
  const target = path.join(packageRoot, ...parts);
  return readFileSync(target, "utf8");
}
function loadControllerSkill(name) {
  const body = stripFrontmatter(
    packageText("shared", "skills", name, "SKILL.md"),
    `shared/skills/${name}/SKILL.md`,
  );
  if (!body) throw new Error(`mandatory controller skill ${name} is empty`);
  return body;
}
let cachedRoleCatalogue;
const cachedCanonicalAgentBlocks = new Map();
const CURRENT_OPERATIONAL_DISPOSITIONS = [
  "COMPLETE", "PARTIAL", "BLOCKED_TECHNICAL", "BLOCKED_AUTHORITY",
  "BLOCKED_DECISION", "PAUSED_CAPACITY", "PAUSED_HOST_WINDOW",
  "CANCELLED", "INCONCLUSIVE",
];
const ROLE_RETURN_FIELD_KINDS = new Set([
  "REFERENCE", "REFERENCE_LIST", "ARTIFACT_REFERENCE",
  "ARTIFACT_REFERENCE_LIST", "STRUCTURED", "STRUCTURED_LIST", "STRING",
  "STRING_LIST", "BOOLEAN", "INTEGER", "NUMBER", "ENUM", "ENUM_LIST",
]);
const ROLE_RETURN_CONTRACT_RE = /^bbk\.[a-z0-9][a-z0-9.-]*\.v[0-9]+$/;
function isNonEmptyString(value) {
  return typeof value === "string" && value.trim().length > 0;
}
function isUniqueStringArray(value) {
  return Array.isArray(value) && value.length > 0
    && value.every(isNonEmptyString) && new Set(value).size === value.length;
}
function validateRoleReturnContract(role, catalogueEntry) {
  const contract = role?.return_contract;
  const required = [
    "contract_id", "envelope_schema", "return_schema", "result_schema",
    "v2_contract_id", "v2_envelope_schema", "v2_return_schema",
    "compact_result_schema", "compact_result_fields", "full_detail_triggers",
    "semantic_state_name", "allowed_invocation_modes", "allowed_return_kinds",
    "allowed_operational_dispositions", "allowed_semantic_states",
    "supplemental_enums", "result_fields", "requirements",
    "readiness_rule", "authority_boundary",
  ];
  if (!contract || typeof contract !== "object" || Array.isArray(contract)) {
    throw new Error(`BBK role ${role?.name || "<unknown>"} has no exact return contract`);
  }
  if (Object.keys(contract).sort().join("\n") !== [...required].sort().join("\n")) {
    throw new Error(`BBK role ${role.name} return contract fields are malformed`);
  }
  for (const key of [
    "contract_id", "envelope_schema", "return_schema", "result_schema",
    "v2_contract_id", "v2_envelope_schema", "v2_return_schema", "compact_result_schema",
    "semantic_state_name", "readiness_rule", "authority_boundary",
  ]) {
    if (!isNonEmptyString(contract[key])) throw new Error(`BBK role ${role.name} return contract ${key} is invalid`);
  }
  const slug = role.name.replace(/^bbk_/, "").replaceAll("_", "-");
  if (!ROLE_RETURN_CONTRACT_RE.test(contract.contract_id)
    || contract.contract_id !== `bbk.${slug}-return.v1`
    || contract.v2_contract_id !== `bbk.${slug}-return.v2`) {
    throw new Error(`BBK role ${role.name} return contract IDs are invalid`);
  }
  if (contract.envelope_schema !== "spec/schemas/bbk-role-return-v1.schema.json"
    || contract.v2_envelope_schema !== "spec/schemas/bbk-role-return-v2.schema.json") {
    throw new Error(`BBK role ${role.name} does not use the canonical v1/v2 return envelopes`);
  }
  const stem = role.name.replaceAll("_", "-");
  if (contract.return_schema !== `spec/schemas/role-returns/${stem}-return-v1.schema.json`
    || contract.result_schema !== `spec/schemas/role-results/${stem}-result-v1.schema.json`
    || contract.v2_return_schema !== `spec/schemas/role-returns/${stem}-return-v2.schema.json`
    || contract.compact_result_schema !== `spec/schemas/role-results/${stem}-compact-result-v2.schema.json`) {
    throw new Error(`BBK role ${role.name} return schema paths are invalid`);
  }
  for (const key of [
    "allowed_invocation_modes", "allowed_return_kinds", "allowed_operational_dispositions",
    "allowed_semantic_states", "requirements", "compact_result_fields", "full_detail_triggers",
  ]) {
    if (!isUniqueStringArray(contract[key])) throw new Error(`BBK role ${role.name} return contract ${key} is invalid`);
  }
  if (contract.compact_result_fields.length > 8) {
    throw new Error(`BBK role ${role.name} compact result contains too many fields`);
  }
  if (!catalogueEntry || catalogueEntry.name !== role.name || !Array.isArray(catalogueEntry.allowed_parent_modes)) {
    throw new Error(`BBK role ${role.name} has no matching catalogue parent-mode entry`);
  }
  const expectedModes = [];
  for (const item of catalogueEntry.allowed_parent_modes) {
    if (!item || !isNonEmptyString(item.mode)) throw new Error(`BBK role ${role.name} has a malformed catalogue parent mode`);
    if (!expectedModes.includes(item.mode)) expectedModes.push(item.mode);
  }
  if (contract.allowed_invocation_modes.join("\n") !== expectedModes.join("\n")) {
    throw new Error(`BBK role ${role.name} return invocation modes do not match the catalogue`);
  }
  if (contract.allowed_operational_dispositions.join("\n") !== CURRENT_OPERATIONAL_DISPOSITIONS.join("\n")) {
    throw new Error(`BBK role ${role.name} uses a noncanonical operational-disposition vocabulary`);
  }
  if (!contract.supplemental_enums || typeof contract.supplemental_enums !== "object" || Array.isArray(contract.supplemental_enums)) {
    throw new Error(`BBK role ${role.name} supplemental return enums are invalid`);
  }
  for (const [name, values] of Object.entries(contract.supplemental_enums)) {
    if (!isNonEmptyString(name) || !isUniqueStringArray(values)) throw new Error(`BBK role ${role.name} supplemental enum ${name} is invalid`);
  }
  if (!contract.result_fields || typeof contract.result_fields !== "object" || Array.isArray(contract.result_fields) || Object.keys(contract.result_fields).length === 0) {
    throw new Error(`BBK role ${role.name} has no closed return-result fields`);
  }
  for (const [name, field] of Object.entries(contract.result_fields)) {
    if (!isNonEmptyString(name) || !field || typeof field !== "object" || Array.isArray(field)
      || !ROLE_RETURN_FIELD_KINDS.has(field.kind) || typeof field.nullable !== "boolean" || !isNonEmptyString(field.description)) {
      throw new Error(`BBK role ${role.name} result field ${name} is invalid`);
    }
    const expectedFieldKeys = ["description", "kind", "nullable"];
    if (["ENUM", "ENUM_LIST"].includes(field.kind)) expectedFieldKeys.push("enum_values");
    if (Object.keys(field).sort().join("\n") !== expectedFieldKeys.sort().join("\n")) {
      throw new Error(`BBK role ${role.name} result field ${name} has malformed metadata`);
    }
    if (["ENUM", "ENUM_LIST"].includes(field.kind) && !isUniqueStringArray(field.enum_values)) {
      throw new Error(`BBK role ${role.name} result enum ${name} is invalid`);
    }
    if (/\bnull\b/i.test(field.description) && field.nullable !== true) {
      throw new Error(`BBK role ${role.name} result field ${name} describes null but rejects it`);
    }
  }
  for (const fieldName of contract.compact_result_fields) {
    if (!Object.hasOwn(contract.result_fields, fieldName)) {
      throw new Error(`BBK role ${role.name} compact result field ${fieldName} is not in the full result schema`);
    }
  }
  return contract;
}
function exactRoleReturnContractBlock(role, catalogueEntry) {
  const contract = validateRoleReturnContract(role, catalogueEntry);
  const fieldLines = contract.compact_result_fields.map(name => {
    const field = contract.result_fields[name];
    const enumPart = Array.isArray(field.enum_values) ? `; enum=${field.enum_values.join("|")}` : "";
    return `- ${name}: kind=${field.kind}; nullable=${field.nullable}${enumPart}; ${field.description}`;
  });
  return [
    `<bbk-exact-role-return-contract role="${role.name}">`,
    "Return one JSON object. New returns use v2 COMPACT by default; conversational prose is not a substitute.",
    "schema: bbk.role-return.v2",
    `contract: ${contract.v2_contract_id}`,
    `envelope_schema: ${contract.v2_envelope_schema}`,
    `return_schema: ${contract.v2_return_schema}`,
    `compact_result_schema: ${contract.compact_result_schema}`,
    `full_result_schema: ${contract.result_schema}`,
    `v1_consume_compatibility: ${contract.return_schema}`,
    `role: ${role.name}`,
    `executor.role: ${role.name}`,
    "detail_level: COMPACT | FULL (COMPACT is the routine default)",
    `invocation_mode: ${contract.allowed_invocation_modes.join(" | ")}`,
    `return_kind: ${contract.allowed_return_kinds.join(" | ")}`,
    `operational_disposition: ${contract.allowed_operational_dispositions.join(" | ")}`,
    `semantic_state.name: ${contract.semantic_state_name}`,
    `semantic_state.value: ${contract.allowed_semantic_states.join(" | ")}`,
    "required_v2_envelope_fields: schema, contract, role, executor, invocation_mode, return_kind, detail_level, subject_ref, parent_ref, attempt_ref, operational_disposition, semantic_state, summary, authority_and_effects_used, result, smallest_valid_next_action",
    "Include material outputs, checks_and_evidence, effects_and_cleanup, blockers_and_residuals, prohibited_claims, and durable_handoff_refs; omit only irrelevant empty sections.",
    "compact_result_fields:",
    ...fieldLines,
    "full_detail_triggers:",
    ...contract.full_detail_triggers.map(item => `- ${item}`),
    "requirements:",
    ...contract.requirements.map(item => `- ${item}`),
    `readiness_rule: ${contract.readiness_rule}`,
    `authority_boundary: ${contract.authority_boundary}`,
    "Operational completion, role semantic readiness, accountable acceptance, and release remain separate. Do not emit READY_FOR_VALIDATION, BLOCKED, or PAUSED as current operational dispositions.",
    "</bbk-exact-role-return-contract>",
  ].join("\n");
}
const PROMPT_MODULE_ID_RE = /^bbk-prompt-[a-z0-9]+(?:-[a-z0-9]+)*$/;
function sourceSha256(text) {
  return createHash("sha256").update(Buffer.from(text, "utf8")).digest("hex");
}
function loadPromptModuleCatalogue(spec) {
  if (spec?.prompt_module_package !== "spec/prompt-modules/catalog.json") {
    throw new Error("installed role catalogue does not name the canonical prompt-module package");
  }
  const source = packageText("spec", "prompt-modules", "catalog.json");
  const catalogue = JSON.parse(source);
  if (catalogue?.schema_version !== "bbk.prompt-modules.v1"
    || catalogue?.package_version !== spec.package_version
    || !Array.isArray(catalogue?.module_entries)
    || catalogue.module_entries.length === 0) {
    throw new Error("installed prompt-module catalogue is invalid or version-incongruent");
  }
  const policy = catalogue.compilation_policy;
  if (!policy || policy.role_field !== "prompt_modules"
    || policy.skill_directive_syntax !== "{{bbk-module:<module-id>}}"
    || policy.embed_each_module_once !== true
    || policy.standalone_skill_expands_modules !== true
    || policy.role_prompt_uses_compact_skill_references !== true
    || !Number.isInteger(policy.mandatory_procedure_default)
    || policy.mandatory_procedure_default < 1
    || (policy.mandatory_procedure_maximum !== null
      && (!Number.isInteger(policy.mandatory_procedure_maximum)
        || policy.mandatory_procedure_maximum < 1))
    || typeof policy.additional_mandatory_procedure_exceptions !== "object"
    || Array.isArray(policy.additional_mandatory_procedure_exceptions)) {
    throw new Error("installed prompt-module compilation policy is malformed");
  }
  const ids = [];
  const paths = ["spec/prompt-modules/catalog.json"];
  for (const entry of catalogue.module_entries) {
    const id = String(entry?.id || "");
    const expectedFile = `spec/prompt-modules/${id}.json`;
    if (!PROMPT_MODULE_ID_RE.test(id) || entry?.file !== expectedFile || ids.includes(id)) {
      throw new Error("installed prompt-module catalogue contains an invalid entry");
    }
    const module = JSON.parse(packageText("spec", "prompt-modules", `${id}.json`));
    if (module?.schema_version !== "bbk.prompt-module.v1" || module?.id !== id
      || !isNonEmptyString(module?.title) || !isNonEmptyString(module?.description)
      || !Array.isArray(module?.clauses) || module.clauses.length === 0
      || module.clauses.some(clause => !isNonEmptyString(clause?.id) || !isNonEmptyString(clause?.text))) {
      throw new Error(`installed prompt module ${id} is malformed`);
    }
    ids.push(id);
    paths.push(expectedFile);
  }
  const records = spec?.source_manifest?.prompt_modules;
  if (!Array.isArray(records) || records.length !== paths.length) {
    throw new Error("installed role projection has no exact prompt-module source manifest");
  }
  for (let index = 0; index < paths.length; index += 1) {
    const expectedPath = paths[index];
    const record = records[index];
    const text = expectedPath === "spec/prompt-modules/catalog.json"
      ? source
      : packageText(...expectedPath.split("/"));
    if (record?.path !== expectedPath
      || record?.bytes !== Buffer.byteLength(text, "utf8")
      || record?.sha256 !== sourceSha256(text)) {
      throw new Error(`installed prompt-module source manifest drift at ${expectedPath}`);
    }
  }
  const methodContentSource = packageText("spec", "method-content.json");
  const methodContent = JSON.parse(methodContentSource);
  if (methodContent?.schema !== "bbk.method-content.v2"
    || methodContent?.version !== spec.package_version
    || methodContent?.prompt_module_source !== "spec/prompt-modules/catalog.json"
    || !methodContent?.skills || typeof methodContent.skills !== "object"
    || Array.isArray(methodContent.skills)) {
    throw new Error("installed method-content source is invalid or version-incongruent");
  }
  return {
    catalogue, ids, policy, methodContent,
    methodContentSha256: sourceSha256(methodContentSource),
  };
}
function stripProcedureFrontmatter(value) {
  let normalized = String(value || "").replace(/\r\n?/g, "\n");
  if (normalized.startsWith("---\n")) {
    const end = normalized.indexOf("\n---\n", 4);
    if (end < 0) throw new Error("mandatory procedure contains unterminated YAML frontmatter");
    normalized = normalized.slice(end + 5);
  }
  return normalized.trim();
}
function compactProcedureForMeasurement(template, promptModules) {
  const compact = String(template || "").replace(
    /\{\{bbk-module:(bbk-prompt-[a-z0-9]+(?:-[a-z0-9]+)*)\}\}/g,
    (_match, moduleId) => {
      if (!promptModules.ids.includes(moduleId)) {
        throw new Error(`mandatory procedure references unknown prompt module ${moduleId}`);
      }
      return `> Apply the already embedded \`${moduleId}\` module here.`;
    },
  );
  if (compact.includes("{{bbk-module:")) {
    throw new Error("mandatory procedure contains a malformed prompt-module directive");
  }
  return stripProcedureFrontmatter(compact);
}
function expectedMandatoryProcedureMeasurement(role, promptModules) {
  const bodies = role.mandatory_skills.map(skillName => {
    const template = promptModules.methodContent.skills[skillName];
    if (typeof template !== "string" || template.trim().length === 0) {
      throw new Error(`mandatory procedure ${skillName} is missing from method content`);
    }
    return compactProcedureForMeasurement(template, promptModules);
  });
  const primaryBytes = Buffer.byteLength(bodies[0], "utf8");
  const allBytes = Buffer.byteLength(bodies.join("\n\n"), "utf8");
  return {
    basis: "UTF8_BYTES_OF_FRONTMATTER_STRIPPED_COMPACT_PROCEDURE_BODIES_JOINED_BY_TWO_LF",
    method_content_sha256: promptModules.methodContentSha256,
    primary_body_bytes: primaryBytes,
    all_mandatory_body_bytes: allBytes,
    incremental_body_bytes: allBytes - primaryBytes,
    duplicated_prompt_module_bodies: 0,
  };
}
function validMeasuredMandatoryProcedureException(role, exception, promptModules) {
  if (!exception || typeof exception !== "object" || Array.isArray(exception)) return false;
  const keys = Object.keys(exception).sort().join("\n");
  if (keys !== ["distinct_behavior", "mandatory_skills", "measurement", "rationale"].sort().join("\n")
    || !Array.isArray(exception.mandatory_skills)
    || exception.mandatory_skills.join("\n") !== role.mandatory_skills.join("\n")
    || !isNonEmptyString(exception.rationale)
    || !exception.distinct_behavior || typeof exception.distinct_behavior !== "object"
    || Array.isArray(exception.distinct_behavior)) return false;
  const expectedAdditional = role.mandatory_skills.slice(1).sort();
  const actualAdditional = Object.keys(exception.distinct_behavior).sort();
  if (expectedAdditional.join("\n") !== actualAdditional.join("\n")
    || actualAdditional.some(name => !isNonEmptyString(exception.distinct_behavior[name]))) return false;
  const expected = expectedMandatoryProcedureMeasurement(role, promptModules);
  if (!exception.measurement || typeof exception.measurement !== "object"
    || Array.isArray(exception.measurement)
    || Object.keys(exception.measurement).sort().join("\n")
      !== Object.keys(expected).sort().join("\n")) return false;
  return Object.entries(expected).every(
    ([key, value]) => exception.measurement[key] === value,
  );
}
function countLiteral(text, value) {
  let count = 0;
  let offset = 0;
  while (true) {
    const index = text.indexOf(value, offset);
    if (index < 0) return count;
    count += 1;
    offset = index + value.length;
  }
}
function roleCatalogue() {
  if (cachedRoleCatalogue) return cachedRoleCatalogue;
  const spec = JSON.parse(packageText("spec", "roles.json"));
  const stagedVersionAllowed = process.env.BBK_ALLOW_STAGED_ROLE_PACKAGE === "1";
  if (spec?.schema_version !== "bbk.roles.v4" || !Array.isArray(spec?.roles)
    || spec?.contract_package !== "spec/contracts/catalog.json"
    || spec?.prompt_module_package !== "spec/prompt-modules/catalog.json"
    || (!stagedVersionAllowed && spec?.package_version !== version)) {
    throw new Error(`installed role catalogue does not match BBK ${version}`);
  }
  if (!Array.isArray(spec.role_entries) || spec.role_entries.length !== spec.roles.length) {
    throw new Error("installed role catalogue has no exact role-entry index");
  }
  const promptModules = loadPromptModuleCatalogue(spec);
  const entries = new Map();
  for (const entry of spec.role_entries) {
    if (!BBK_ROLE_NAME_RE.test(String(entry?.name || "")) || entries.has(entry.name)) {
      throw new Error("installed role catalogue contains an invalid role entry");
    }
    entries.set(entry.name, entry);
  }
  const roles = new Map();
  for (const role of spec.roles) {
    if (!BBK_ROLE_NAME_RE.test(String(role?.name || "")) || roles.has(role.name)) continue;
    if (!isNonEmptyString(role.primary_skill)
      || !Array.isArray(role.mandatory_skills) || role.mandatory_skills.length === 0
      || role.mandatory_skills[0] !== role.primary_skill
      || !Array.isArray(role.skills) || !role.skills.includes(role.primary_skill)
      || !Array.isArray(role.prompt_modules) || role.prompt_modules.length === 0
      || new Set(role.prompt_modules).size !== role.prompt_modules.length) {
      throw new Error(`BBK role ${role.name} has malformed prompt compilation metadata`);
    }
    const selected = new Set(role.prompt_modules);
    const canonicalOrder = promptModules.ids.filter(id => selected.has(id));
    if (canonicalOrder.join("\n") !== role.prompt_modules.join("\n")
      || role.prompt_modules.some(id => !promptModules.ids.includes(id))) {
      throw new Error(`BBK role ${role.name} has unknown or misordered prompt modules`);
    }
    const exception = promptModules.policy.additional_mandatory_procedure_exceptions[role.name];
    if (role.mandatory_skills.length !== promptModules.policy.mandatory_procedure_default) {
      if (!validMeasuredMandatoryProcedureException(role, exception, promptModules)) {
        throw new Error(`BBK role ${role.name} has an unjustified mandatory-procedure count`);
      }
    } else if (exception) {
      throw new Error(`BBK role ${role.name} has an unnecessary mandatory-procedure exception`);
    }
    if (promptModules.policy.mandatory_procedure_maximum !== null
      && role.mandatory_skills.length > promptModules.policy.mandatory_procedure_maximum) {
      throw new Error(`BBK role ${role.name} exceeds the configured mandatory-procedure maximum`);
    }
    validateRoleReturnContract(role, entries.get(role.name));
    roles.set(role.name, role);
  }
  for (const roleName of Object.keys(promptModules.policy.additional_mandatory_procedure_exceptions)) {
    if (!roles.has(roleName)) {
      throw new Error(`prompt-module policy names unknown mandatory-procedure exception role ${roleName}`);
    }
  }
  if (roles.size !== spec.roles.length || entries.size !== roles.size) throw new Error("installed role catalogue contains an invalid canonical role");
  cachedRoleCatalogue = {
    version: spec.package_version,
    schemaVersion: spec.schema_version,
    contractPackage: spec.contract_package,
    promptModulePackage: spec.prompt_module_package,
    promptModuleIds: promptModules.ids,
    entries,
    roles,
  };
  return cachedRoleCatalogue;
}
function normalizePromptBlock(value) {
  return String(value || "")
    .replace(/\r\n?/g, "\n")
    .split("\n")
    .map(line => line.replace(/[ \t]+$/g, ""))
    .filter(line => line.trim().length > 0)
    .join("\n")
    .trim();
}
function canonicalAgentBlock(roleName) {
  if (cachedCanonicalAgentBlocks.has(roleName)) return cachedCanonicalAgentBlocks.get(roleName);
  const sourceLabel = `projections/omp/agents/${roleName}.md`;
  const body = stripFrontmatter(
    packageText("projections", "omp", "agents", `${roleName}.md`),
    sourceLabel,
  );
  const match = body.match(BBK_AGENT_BLOCK_RE);
  if (!match || match[1] !== roleName) {
    throw new Error(`installed canonical OMP projection for ${roleName} is missing its closed BBK marker`);
  }
  const block = normalizePromptBlock(match[0]);
  cachedCanonicalAgentBlocks.set(roleName, block);
  return block;
}
function systemPromptBlocks(event) {
  if (Array.isArray(event?.systemPrompt)) return event.systemPrompt.map(value => String(value || ""));
  if (event?.systemPrompt == null) return [];
  return [String(event.systemPrompt || "")];
}
function systemPromptText(event) {
  return systemPromptBlocks(event).join("\n\n");
}
function promptBlocksFromValue(value) {
  if (Array.isArray(value)) return value.map(item => String(item || ""));
  if (value == null) return [];
  return [String(value || "")];
}
function promptReceiptSummary(blocks) {
  const normalized = promptBlocksFromValue(blocks);
  const text = normalized.join("\n\n");
  return {
    block_count: normalized.length,
    length: text.length,
    sha256: createHash("sha256").update(text, "utf8").digest("hex"),
  };
}
function promptOuterIdentity(text) {
  const value = String(text || "");
  const child = value.match(/^\s*<bbk-agent-replacement\b[^>]*\brole="([^"]+)"/i);
  if (child) return { kind: "agent", role: child[1] };
  if (/^\s*<bbk-controller-system\b/i.test(value)) return { kind: "controller", role: "Main" };
  if (/^\s*<bbk-prompt-assembly-failure\b/i.test(value)) return { kind: "assembly-failure", role: null };
  return { kind: "unknown", role: null };
}
function sourceHasGenericPromptMaterial(blocks) {
  const values = promptBlocksFromValue(blocks);
  if (values.length > 1) return true;
  const text = values.join("\n\n");
  const markers = ["<bbk-agent-system", "<bbk-controller-system", "<bbk-agent-replacement"];
  const positions = markers.map(marker => text.indexOf(marker)).filter(index => index >= 0);
  if (!positions.length) return Boolean(text.trim());
  return Boolean(text.slice(0, Math.min(...positions)).trim());
}
function parseOmpPromptSections(text) {
  const normalized = String(text || "").replace(/\r\n?/g, "\n");
  const lines = normalized.split("\n");
  const headings = [];
  const separator = /^[=─-]{3,}\s*$/;
  const heading = /^[A-Z][A-Z0-9 _/()&.-]{1,}\s*$/;
  const wrapperHeadings = new Set(["ROLE", "CONTEXT", "PLAN", "COOP", "COMPLETION"]);
  for (let index = 0; index < lines.length; index += 1) {
    const current = lines[index].trim();
    const next = lines[index + 1]?.trim() || "";
    const after = lines[index + 2]?.trim() || "";
    if (heading.test(current) && wrapperHeadings.has(current.toUpperCase()) && separator.test(next)) {
      headings.push({ name: current.toUpperCase(), markerStart: index, contentStart: index + 2 });
      index += 1;
      continue;
    }
    if (separator.test(current) && heading.test(next) && wrapperHeadings.has(next.toUpperCase()) && separator.test(after)) {
      headings.push({ name: next.toUpperCase(), markerStart: index, contentStart: index + 3 });
      index += 2;
    }
  }
  return headings.map((item, index) => ({
    name: item.name,
    content: lines.slice(item.contentStart, headings[index + 1]?.markerStart ?? lines.length).join("\n").trim(),
  }));
}
function extractHeadingSection(text, heading) {
  const wanted = String(heading || "").trim().toUpperCase();
  const divided = parseOmpPromptSections(text).find(section => section.name === wanted)?.content || "";
  if (divided) return divided;
  const escaped = String(heading || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const markdown = String(text || "").match(new RegExp(
    `(?:^|\\n)#{1,6}\\s+${escaped}\\s*\\n([\\s\\S]*?)(?=\\n#{1,6}\\s+\\S|$)`,
    "i",
  ));
  return markdown?.[1]?.trim() || "";
}
function firstCaptured(text, patterns) {
  for (const pattern of patterns) {
    const value = text.match(pattern)?.[1]?.trim();
    if (value) return value;
  }
  return "";
}
function extractOmpInvocationData(text) {
  const context = extractHeadingSection(text, "CONTEXT");
  const planTag = text.match(/<plan\b([^>]*)>[\s\S]*?<\/plan>/i);
  const plan = planTag?.[0]?.trim() || extractHeadingSection(text, "PLAN");
  const planPath = planTag?.[1]?.match(/\bpath\s*=\s*["']([^"']*)["']/i)?.[1]?.trim() || "";
  const worktree = firstCaptured(text, [
    /(?:isolated (?:git )?(?:working )?tree|isolated worktree|worktree)[^`\n]*`([^`]+)`/i,
    /(?:isolated (?:git )?(?:working )?tree|isolated worktree|worktree)\s*:\s*([^\n]+)/i,
  ]);
  const agentId = firstCaptured(text, [
    /(?:your (?:IRC |hub |agent |peer )?id is|you are registered as)\s*`([^`]+)`/i,
    /(?:your (?:IRC |hub |agent |peer )?id is|you are registered as)\s*([^\s,.;\n]+)/i,
  ]);
  const peerRoster = firstCaptured(text, [
    /currently visible peers\s*:\s*\n([\s\S]*?)(?=\n\s*(?:use\s+`hub`|when communicating|send messages|[=─-]{3,}\s*$)|$)/i,
    /peer roster\s*:\s*\n([\s\S]*?)(?=\n\s*(?:use\s+`hub`|when communicating|send messages|[=─-]{3,}\s*$)|$)/i,
  ]);
  const yieldSchema = firstCaptured(text, [
    /(?:your\s+)?terminal\s+`yield`[^\n]*?(?:exactly this shape|exact schema)[^\n]*:\s*\n```(?:ts|typescript|json)?\s*\n([\s\S]*?)```/i,
    /(?:submit|return|finish)[^\n]*?through\s+(?:the\s+)?`yield`[^\n]*?(?:exactly this shape|exact schema)[^\n]*:\s*\n```(?:ts|typescript|json)?\s*\n([\s\S]*?)```/i,
    /(?:output|result)\s+schema\s*:\s*\n```(?:ts|typescript|json)?\s*\n([\s\S]*?)```/i,
  ]);
  const schemaOverridesAgent = /(?:caller|task|output)\s+schema[^\n]*(?:override|takes precedence|wins over)[^\n]*(?:agent|role)/i.test(text)
    || /(?:override|takes precedence|wins over)[^\n]*(?:agent|role)[^\n]*(?:schema|field)/i.test(text);
  return {
    context,
    plan,
    planPath,
    worktree,
    agentId,
    peerRoster,
    yieldSchema,
    schemaOverridesAgent,
  };
}
function extractBbkAgentBlock(event) {
  const blocks = systemPromptBlocks(event);
  const replacementBlocks = blocks.filter(block => /^\s*<bbk-agent-replacement\b/i.test(block));
  if (replacementBlocks.length > 0) return { alreadyReplaced: true };

  const markerBlocks = blocks.filter(block => block.includes(BBK_AGENT_PROMPT_MARKER));
  if (markerBlocks.length === 0) return undefined;
  if (markerBlocks.length !== 1) throw new Error("ambiguous BBK agent-system marker blocks");

  const sourceBlock = markerBlocks[0];
  const match = sourceBlock.match(BBK_AGENT_BLOCK_RE);
  if (!match) throw new Error("malformed BBK agent-system marker");
  const roleName = match[1];
  if (!BBK_ROLE_NAME_RE.test(roleName)) throw new Error(`invalid BBK role marker ${roleName}`);
  const catalogue = roleCatalogue();
  const role = catalogue.roles.get(roleName);
  if (!role) throw new Error(`unknown BBK role marker ${roleName}`);
  const roleBlock = match[0].trim();
  if (normalizePromptBlock(roleBlock) !== canonicalAgentBlock(roleName)) {
    throw new Error(`BBK role ${roleName} prompt does not match the installed canonical projection`);
  }
  for (const skill of role.mandatory_skills || []) {
    if (!roleBlock.includes(`<bbk-inlined-skill name="${skill}"`)) {
      throw new Error(`BBK role ${roleName} is missing mandatory inlined skill ${skill}`);
    }
  }
  for (const moduleId of role.prompt_modules || []) {
    const marker = `<bbk-prompt-module id="${moduleId}">`;
    if (countLiteral(roleBlock, marker) !== 1) {
      throw new Error(`BBK role ${roleName} must embed prompt module ${moduleId} exactly once`);
    }
  }
  for (const moduleId of catalogue.promptModuleIds) {
    if (!(role.prompt_modules || []).includes(moduleId)
      && countLiteral(roleBlock, `<bbk-prompt-module id="${moduleId}">`) !== 0) {
      throw new Error(`BBK role ${roleName} embeds undeclared prompt module ${moduleId}`);
    }
  }

  // OMP places the role wrapper, shared batch context, approved plan,
  // worktree/IRC metadata, and yield contract in one dedicated system-prompt
  // block. Parse only the suffix after the authenticated BBK role block. This
  // excludes generic OMP blocks and compatibility-discovered context while
  // retaining the task call's explicit host-supplied invocation data.
  const roleEnd = (match.index || 0) + match[0].length;
  const invocationSource = sourceBlock.slice(roleEnd);
  return {
    roleName,
    role,
    roleBlock,
    catalogueEntry: catalogue.entries.get(roleName),
    catalogueVersion: catalogue.version,
    invocation: extractOmpInvocationData(invocationSource),
  };
}
function runtimeBlock(ctx) {
  const cwd = String(ctx?.cwd || process.cwd());
  return [
    "<bbk-runtime-context>",
    `package_version: ${version}`,
    `cwd: ${cwd}`,
    `platform: ${process.platform}`,
    `architecture: ${process.arch}`,
    `date_utc: ${new Date().toISOString().slice(0, 10)}`,
    "</bbk-runtime-context>",
  ].join("\n");
}
function inlinedControllerSkills() {
  return CONTROLLER_MANDATORY_SKILLS.map(name => [
    `<bbk-inlined-skill name="${name}" source="shared/skills/${name}/SKILL.md">`,
    loadControllerSkill(name),
    "</bbk-inlined-skill>",
  ].join("\n")).join("\n\n");
}
function buildControllerSystemPrompt(ctx) {
  roleCatalogue(); // Fail closed if the installed role catalogue is unavailable or stale.
  return [
    `<bbk-controller-system package-version="${version}">`,
    "",
    "# BBK OMP harness-root controller",
    "",
    "This is the complete system prompt for an active BBK parent session. It replaces, rather than appends to, OMP's generic workflow prompt and compatibility-discovered context. Do not follow planning, delegation, validation, completion, anti-ceremony, `spawn_agent`, or client-specific instructions inherited from `.codex`, `.claude`, `.gemini`, or another harness. OMP tool schemas and runtime containment still define physical capability; they do not create BBK authority.",
    "",
    "## Identity and user channel",
    "",
    "- You are the OMP peer whose kind is `main`, normally named `Main`, and the sole BBK identity that may focus the terminal and interact with the user.",
    "- You are a controller and relay, not a Wayfinder, Orchestrator, Worker, Reviewer, Validator, Architect, or Question Guide. Never imitate, abbreviate, or absorb a canonical role's substantive work.",
    "- Every named `bbk_*` agent is a non-user-facing child, including roles whose names contain `root`, `guide`, `orchestrator`, or `reviewer`.",
    "- Canonical roles communicate through OMP `hub`/IRC. Use `hub` roster data; never invent peer IDs. A send receipt, timeout, silence, or missing heartbeat is not a decision or proof of failure.",
    "- BBK mode remains session-local and active until `/bbk:exit`; that command restores ordinary OMP prompt behavior for subsequent Main turns.",
    "",
    "## Turn procedure",
    "",
    "1. Inspect live `hub` messages, the roster/jobs, and current `.bbk` state before creating a new root child.",
    "2. If the user message answers, corrects, steers, cancels, or authorizes an existing BBK request, collect coherent answers into one response packet and relay it through `hub` to the exact requesting peer or active logical root, preserving every request/message ID and using `replyTo` when available. For baseline acceptance, execution authority, or accepted planning decisions, resume the originating Root Wayfinder so it can integrate the response; do not launch a duplicate or successor root from the raw user answer.",
    "3. Otherwise select exactly one canonical root: no accepted baseline, planning, architecture, design, ambiguity, or material uncertainty -> `bbk_root_wayfinder`; execution or recovery -> `bbk_root_orchestrator` only after the responsible Root Wayfinder has integrated accountable acceptance and current execution authority and returned `READY_TO_EXECUTE` with an exact executable work-graph reference; bounded independent review -> `bbk_reviewer`; assertion-scoped candidate acceptance -> `bbk_validator_orchestrator`. When planning readiness is proposed, missing, stale, or conditional, resume `bbk_root_wayfinder` instead.",
    "4. Invoke that named agent with OMP `task`, preferably as a background/non-blocking job so Main remains available for user relay. When OMP advertises the batch form, use `{ context, tasks: [{ name, agent, task, ... }] }` even for one root: `agent` is the exact canonical `bbk_*` role, `name` is a stable IRC/job identifier, and `task` is the complete self-contained assignment. Never put the role name only in `name` while omitting `agent`. If OMP advertises only a flat form, follow that schema and carry reusable shared background through a durable `local://` context file. Supply exact subject, desired result, bounded context, authority and standing approvals, allowed effects, capability zones, assurance obligations, stopping conditions, logical parent, Main peer ID, branch/request IDs, and return envelope.",
    "5. Before dispatch, perform only bounded controller operations required to recover state and compile the invocation. Do not select architecture, write the operating plan, edit subject files, execute product work, review, validate, or certify in Main.",
    "6. Supervise through task state and `hub`. Continue useful controller work and wait only when no other valid action remains. Resume or message the same logical child when possible instead of restarting discovery.",
    "",
    "## Human-request relay",
    "",
    "- A child first classifies an unresolved item as ENVIRONMENT_FACT, CONFIGURATION_PARAMETER, REVERSIBLE_IMPLEMENTATION_CHOICE, ARCHITECTURAL_DECISION, AUTHORITY_EXPANSION, or USER_RESERVED_PREFERENCE. Only a material architectural branch with several viable consequential alternatives, an authority expansion, a user-reserved preference, protected-floor exception, hard-to-reverse commitment, private-context need, or accountable acceptance normally warrants `BBK_USER_REQUEST`. Discover, parameterize, safely default, or defer ordinary facts and reversible choices.",
    "- A child needing such input sends Main one compact `BBK_USER_REQUEST` packet over `hub`/IRC. It must include stable request IDs, exact subjects, classification, smallest material questions, recommendations, credible materially different alternatives, consequences, residual uncertainty, blocking state, unaffected work, and durable packet references.",
    "- Use OMP's native `ask` tool for every user-facing question or decision request. Do not put a question in ordinary assistant prose and wait for an answer. Anything phrased as a question outside an `ask` tool call is informational text only: it is not a pending BBK question, does not establish a decision surface, and must not be treated as answered.",
    "- Translate coherent child requests into the smallest adequate single `ask` interaction, preserving every request ID and recommendation. Do not answer on the user's behalf or substitute your own design judgment.",
    "- Only a structured answer returned by `ask` is eligible to become an ADR-compatible accepted decision. Relay coherent answers in one `BBK_USER_RESPONSE_BATCH` packet to the exact requesting logical role, with every matching request ID and `source: omp.ask`, and notify its integrating parent when required. Main never authors the ADR, baseline acceptance, or execution-authorization record; the responsible canonical role records and integrates the response and continues its branch.",
    "- Ordinary user prose may steer, correct, cancel, or grant operational authority, but it is not an answer to an unissued prose question and must not be converted into an ADR. When durable decision authority is required, obtain or confirm it through `ask` first. Silence, timeout, cancellation, `Chat about this`, a send receipt, or anticipated answers are not acceptance. Baseline acceptance and execution authority return to the originating Root Wayfinder for durable integration before execution routing.",
    "- Keep IRC concise and plain prose. Large or authority-bearing material belongs in a durable handoff; relay path, bytes, SHA-256, disposition, and smallest next action.",
    "",
    "## Execution autonomy",
    "",
    "- Once an accepted baseline and execution authority are bound, do not interrupt the user for routine plan-detail corrections, local sequencing, reversible implementation choices, ordinary repairs, compatible dependency substitutions, or a technical blocker with one safe realistic scope-preserving resolution inside current authority. Route the work to the responsible role, record the deviation and rationale, and continue.",
    "- Request a user decision only for a genuine material branch with at least two viable consequential paths, an explicitly user-reserved preference, or an authority expansion. A sole path outside current authority still requires the smallest exact additional grant; pause only the affected scope.",
    "",
    "## Non-bypass rule",
    "",
    "Absence of `.bbk` records is a greenfield Wayfinding condition, not permission to bypass BBK. Do not dismiss BBK as ceremony, overhead, over-engineering, or disproportionate process. Proportionality is decided inside the selected canonical procedure.",
    "",
    runtimeBlock(ctx),
    "",
    "# Inlined mandatory controller procedures",
    "",
    "The following procedure bodies are mandatory and already available. Apply them directly; do not spend a Skill/read call reloading them.",
    "",
    inlinedControllerSkills(),
    "",
    "</bbk-controller-system>",
  ].join("\n");
}
function buildAgentSystemPrompt(extracted, ctx) {
  const invocation = extracted.invocation || {};
  const invocationLines = [
    "<bbk-omp-invocation-data>",
    "The following values are host-supplied invocation data, not generic OMP workflow policy. Preserve their exact boundaries.",
  ];
  if (invocation.context) invocationLines.push("", "## Assigned context", invocation.context);
  if (invocation.plan) {
    invocationLines.push("", `## Approved plan${invocation.planPath ? ` (${invocation.planPath})` : ""}`, invocation.plan);
  }
  if (invocation.worktree) invocationLines.push("", `worktree: ${invocation.worktree}`);
  if (invocation.agentId) invocationLines.push(`hub_peer_id: ${invocation.agentId}`);
  if (invocation.peerRoster) invocationLines.push("", "## Initial hub peer roster", invocation.peerRoster);
  invocationLines.push("", "## Completion binding");
  invocationLines.push("- Finish through OMP's hidden `yield` tool. Put the role's structured return envelope in `result.data`; use `result.error` only for a genuine terminal failure.");
  invocationLines.push("- The canonical role contract controls authority, evidence, status, and content. A caller-supplied output schema may refine the field shape but cannot expand authority, erase findings, or convert missing evidence into success.");
  invocationLines.push("- Keep large artifacts in the assigned filesystem/worktree and return verified paths or artifact references rather than oversized IRC or yield payloads.");
  invocationLines.push("- A blocked terminal return must identify the typed blocker, completed work, preserved state, evidence, and smallest valid next action.");
  if (invocation.yieldSchema) {
    invocationLines.push("", "### Caller-supplied yield schema", "```ts", invocation.yieldSchema, "```");
    if (invocation.schemaOverridesAgent) {
      invocationLines.push("The caller explicitly declared this schema's field names controlling. Map the canonical BBK return into it without losing required authority, evidence, findings, or blocker semantics.");
    }
  }
  invocationLines.push("</bbk-omp-invocation-data>");

  return [
    `<bbk-agent-replacement role="${extracted.roleName}" package-version="${version}">`,
    "",
    "This is the complete OMP system prompt for the named canonical BBK agent. The BBK extension discarded OMP's generic workflow prompt and compatibility-discovered `.codex`, `.claude`, `.gemini`, and other client-specific instructions. Only this exact installed BBK role contract, its inlined mandatory procedures, the invocation/user message, the explicit task-call data parsed from the marker-bearing native child wrapper below, host tool schemas, and runtime containment govern the turn.",
    "",
    "The peer whose kind is `main`, normally `Main`, is the sole user-facing controller. Use OMP `hub`/IRC for live communication. Send ordinary coordination to the invoking parent and any permitted `BBK_USER_REQUEST` to Main while notifying the parent. Every request must carry a stable request ID and enough option/recommendation context for Main to invoke OMP `ask`. Accept a user decision for ADR-compatible recording only from a matching `BBK_USER_RESPONSE` marked `source: omp.ask`; ordinary prose, silence, timeouts, send receipts, and inferred intent are not decision evidence. Never call `ask` or another user-interaction surface yourself, seize focus, or infer a response. Discover peer IDs with `hub` list, send concise plain prose, use `replyTo`, keep large material in durable handoffs, continue independent authorized work after sending, and wait only when completely blocked.",
    "",
    runtimeBlock(ctx),
    "",
    invocationLines.join("\n"),
    "",
    extracted.roleBlock,
    "",
    exactRoleReturnContractBlock(extracted.role, extracted.catalogueEntry),
    "",
    "</bbk-agent-replacement>",
  ].join("\n");
}
function failClosedSystemPrompt(reason, ctx) {
  const safeReason = String(reason?.message || reason || "unknown prompt assembly error").slice(0, 800);
  return [
    `<bbk-prompt-assembly-failure package-version="${version}">`,
    "BBK prompt assembly failed closed. Do not perform governed planning, design, implementation, review, validation, or product effects.",
    `Reason: ${safeReason}`,
    "If this is a child agent, report `BLOCKED_TECHNICAL` through `hub`/IRC to the invoking parent and Main. If this is Main, report the blocker to the user. Preserve existing files and state.",
    runtimeBlock(ctx),
    "</bbk-prompt-assembly-failure>",
  ].join("\n");
}

function createBbkActivityHud(pi) {
  let enabled = false;
  let currentCtx;
  let sequence = 0;
  const agents = new Map();
  const aliases = new Map();
  const MAX_RETAINED_AGENTS = 256;
  const ACTIVE_STATUSES = new Set(["pending", "queued", "running", "waiting", "retrying", "starting"]);
  const TERMINAL_STATUSES = new Set(["completed", "failed", "error", "aborted", "cancelled", "canceled", "stopped", "terminated"]);

  function clearWidget() {
    try { currentCtx?.ui?.setWidget?.(BBK_ACTIVITY_WIDGET_KEY, undefined, { placement: "aboveEditor" }); }
    catch {}
  }
  function statusOf(value, fallback = "running") {
    const raw = String(value || fallback).trim().toLowerCase();
    if (raw === "started") return "pending";
    if (raw === "complete" || raw === "done" || raw === "success" || raw === "succeeded") return "completed";
    if (raw === "failure") return "failed";
    return raw || fallback;
  }
  function activeAgents() {
    return [...agents.values()].filter(item => ACTIVE_STATUSES.has(statusOf(item.progress?.status)));
  }
  function agentLabel(item, max = 42) {
    return oneLine(item?.name || item?.id || item?.description || roleDisplayName(item?.agent), max);
  }
  function ancestorPath(item) {
    const values = [];
    const seen = new Set();
    let current = item;
    while (current && !seen.has(current.key)) {
      seen.add(current.key);
      values.push(agentLabel(current, 28));
      current = current.parentKey ? agents.get(current.parentKey) : null;
    }
    return values.reverse();
  }
  function depthOf(item) {
    let depth = 0;
    const seen = new Set();
    let parent = item?.parentKey ? agents.get(item.parentKey) : null;
    while (parent && !seen.has(parent.key)) {
      seen.add(parent.key);
      depth += 1;
      parent = parent.parentKey ? agents.get(parent.parentKey) : null;
    }
    return depth;
  }
  function render() {
    if (!enabled || !currentCtx?.ui?.setWidget) {
      clearWidget();
      return;
    }
    const active = activeAgents().sort((a, b) => b.updated - a.updated);
    if (!active.length) {
      const known = agents.size;
      currentCtx.ui.setWidget(
        BBK_ACTIVITY_WIDGET_KEY,
        [known ? `BBK · ready · ${known} agent${known === 1 ? "" : "s"} in history` : "BBK · ready"],
        { placement: "aboveEditor" },
      );
      return;
    }
    const latest = active[0];
    const pathLabel = ancestorPath(latest).join(" › ") || agentLabel(latest);
    const gauge = contextGauge(latest.progress);
    const activity = progressActivity(latest.progress);
    let line = `BBK · ${active.length} active · ${pathLabel}${gauge ? ` [${gauge}]` : ""}: ${activity}`;

    const otherGauges = active.slice(1, 4).map(item => {
      const otherName = agentLabel(item, 24);
      const otherGauge = contextGauge(item.progress, { short: true });
      return otherGauge ? `${otherName} ${otherGauge}` : otherName;
    });
    if (otherGauges.length) line += ` | ${otherGauges.join(" · ")}`;
    if (active.length > 4) line += ` · +${active.length - 4} agents`;
    currentCtx.ui.setWidget(BBK_ACTIVITY_WIDGET_KEY, [oneLine(line, 260)], { placement: "aboveEditor" });
  }
  function strongAliasValues(raw, progress, parentKey) {
    const values = [
      raw?.id, raw?.taskId, raw?.task_id, raw?.agentId, raw?.agent_id,
      raw?.toolCallId, raw?.tool_call_id,
      progress?.id, progress?.taskId, progress?.task_id,
      progress?.agentId, progress?.agent_id, progress?.toolCallId, progress?.tool_call_id,
    ];
    const result = [];
    for (const value of values) {
      if (typeof value !== "string" || !value.trim()) continue;
      const clean = value.trim();
      result.push(`id:${clean}`, `${parentKey || "Main"}::id:${clean}`);
    }
    return [...new Set(result)];
  }
  function weakAliasValue(raw, progress, role, parentKey) {
    const name = raw?.name || progress?.name || raw?.description || raw?.task || progress?.task;
    return typeof name === "string" && name.trim()
      ? `${parentKey || "Main"}::${role}::${name.trim()}`
      : null;
  }
  function roleFrom(raw, progress) {
    const values = [
      raw?.agent, progress?.agent, raw?.role, progress?.role,
      raw?.agentName, progress?.agentName,
      raw?.agent?.name, progress?.agent?.name,
      raw?.agent?.id, progress?.agent?.id,
    ];
    for (const value of values) {
      const role = String(value || "").trim();
      if (BBK_ROLE_NAME_RE.test(role)) return role;
    }
    return "";
  }
  function resolveAlias(value, parentKey) {
    if (typeof value !== "string" || !value.trim()) return null;
    const clean = value.trim();
    return aliases.get(`${parentKey || "Main"}::id:${clean}`) || aliases.get(`id:${clean}`) || null;
  }
  function directParentKey(raw, progress, inheritedParentKey) {
    if (inheritedParentKey) return inheritedParentKey;
    const values = [
      raw?.parentAgentId, raw?.parent_agent_id, raw?.parentId, raw?.parent_id,
      raw?.parentTaskId, raw?.parent_task_id, raw?.parentName,
      progress?.parentAgentId, progress?.parent_agent_id, progress?.parentId, progress?.parent_id,
      progress?.parentTaskId, progress?.parent_task_id, progress?.parentName,
    ];
    for (const value of values) {
      const resolved = resolveAlias(value, null);
      if (resolved) return resolved;
    }
    return null;
  }
  function detailItems(value) {
    if (!value) return [];
    if (Array.isArray(value)) return value;
    if (typeof value !== "object") return [];
    for (const key of ["progress", "tasks", "items", "children", "inflight", "details"]) {
      if (Array.isArray(value[key])) return value[key];
    }
    const candidates = Object.values(value).filter(item => item && typeof item === "object");
    return candidates.length && candidates.every(item => !Array.isArray(item)) ? candidates : [];
  }
  function nestedItems(raw, progress) {
    const result = [];
    const containers = [
      raw?.inflightTaskDetails, raw?.inflight_task_details,
      progress?.inflightTaskDetails, progress?.inflight_task_details,
      raw?.extractedToolData?.task, raw?.extracted_tool_data?.task,
      progress?.extractedToolData?.task, progress?.extracted_tool_data?.task,
      Array.isArray(raw?.progress) ? raw.progress : null,
      Array.isArray(progress?.progress) ? progress.progress : null,
      raw?.results, progress?.results,
      raw?.children, progress?.children,
    ];
    for (const container of containers) result.push(...detailItems(container));
    return result;
  }
  function trimHistory() {
    if (agents.size <= MAX_RETAINED_AGENTS) return;
    const removable = [...agents.values()]
      .filter(item => !ACTIVE_STATUSES.has(statusOf(item.progress?.status)))
      .sort((a, b) => a.updated - b.updated);
    while (agents.size > MAX_RETAINED_AGENTS && removable.length) {
      const item = removable.shift();
      agents.delete(item.key);
      for (const [alias, key] of aliases) if (key === item.key) aliases.delete(alias);
    }
  }
  function upsert(rawValue, inheritedParentKey = null, source = "progress", visited = new Set()) {
    if (!rawValue || typeof rawValue !== "object" || visited.has(rawValue)) return null;
    visited.add(rawValue);
    const raw = rawValue;
    const progress = raw.progress && typeof raw.progress === "object" && !Array.isArray(raw.progress)
      ? raw.progress
      : raw;
    const role = roleFrom(raw, progress);
    let parentKey = directParentKey(raw, progress, inheritedParentKey);
    let key = null;
    const candidateAliases = role ? strongAliasValues(raw, progress, parentKey) : [];
    for (const alias of candidateAliases) {
      const found = aliases.get(alias);
      if (found) { key = found; break; }
    }
    const weakAlias = role && !candidateAliases.length
      ? weakAliasValue(raw, progress, role, parentKey)
      : null;
    if (!key && weakAlias) key = aliases.get(weakAlias) || null;
    if (role) {
      const fallbackName = String(
        progress.id || raw.id || raw.name || progress.name || raw.taskId || progress.taskId
        || raw.description || raw.task || progress.task || role,
      ).trim();
      if (!key) key = `${parentKey || "Main"}/${role}/${fallbackName}`;
      const previous = agents.get(key);
      if (!parentKey && previous?.parentKey) parentKey = previous.parentKey;
      const exitCodeValue = progress.exitCode ?? raw.exitCode;
      const hasExitCode = exitCodeValue !== undefined
        && exitCodeValue !== null
        && Number.isFinite(Number(exitCodeValue));
      const inferredTerminalStatus = Boolean(progress.aborted ?? raw.aborted)
        ? "aborted"
        : progress.error || raw.error
          ? "failed"
          : hasExitCode
            ? Number(exitCodeValue) === 0 ? "completed" : "failed"
            : undefined;
      const status = statusOf(
        progress.status || raw.status || inferredTerminalStatus,
        previous?.progress?.status || (source === "lifecycle" ? "pending" : "running"),
      );
      const id = String(progress.id || raw.id || progress.taskId || raw.taskId || raw.name || progress.name || fallbackName);
      const name = String(raw.name || progress.name || id);
      const description = oneLine(raw.task || raw.assignment || raw.description || progress.task || progress.assignment || progress.description || "", 240);
      const mergedProgress = {
        ...(previous?.progress || {}),
        ...progress,
        id,
        name,
        agent: role,
        status,
      };
      const modelValue = raw.resolvedModel || progress.resolvedModel || raw.modelOverride || progress.modelOverride || raw.model || progress.model;
      const model = typeof modelValue === "string" ? modelValue : modelSelector(modelValue);
      const item = {
        ...(previous || {}),
        key,
        id,
        name,
        agent: role,
        description: description || previous?.description || "",
        parentKey: parentKey || null,
        depth: parentKey && agents.get(parentKey) ? Number(agents.get(parentKey).depth || 0) + 1 : 0,
        detached: Boolean(raw.detached ?? progress.detached ?? previous?.detached),
        model: model || previous?.model || "",
        sessionId: String(raw.sessionId || raw.session_id || progress.sessionId || progress.session_id || previous?.sessionId || ""),
        sessionFile: String(raw.sessionFile || raw.session_file || progress.sessionFile || progress.session_file || previous?.sessionFile || ""),
        toolCallId: String(raw.toolCallId || raw.tool_call_id || progress.toolCallId || progress.tool_call_id || previous?.toolCallId || ""),
        parentToolCallId: String(raw.parentToolCallId || raw.parent_tool_call_id || progress.parentToolCallId || progress.parent_tool_call_id || previous?.parentToolCallId || ""),
        agentSource: String(raw.agentSource || raw.agent_source || progress.agentSource || progress.agent_source || previous?.agentSource || ""),
        assignment: oneLine(raw.assignment || progress.assignment || previous?.assignment || "", 240),
        index: finiteNumber(raw.index ?? progress.index ?? previous?.index),
        source,
        progress: mergedProgress,
        updated: ++sequence,
        started: previous?.started || sequence,
        completed: TERMINAL_STATUSES.has(status) ? sequence : null,
      };
      agents.set(key, item);
      for (const alias of candidateAliases) aliases.set(alias, key);
      if (weakAlias) aliases.set(weakAlias, key);
      aliases.set(key, key);
      aliases.set(`id:${id}`, key);
      aliases.set(`${parentKey || "Main"}::id:${id}`, key);
    }
    const childParent = key || inheritedParentKey;
    for (const child of nestedItems(raw, progress)) upsert(child, childParent, "nested-progress", visited);
    return key;
  }
  function setMode(next, ctx) {
    enabled = Boolean(next);
    currentCtx = ctx || currentCtx;
    if (!enabled) {
      agents.clear();
      aliases.clear();
    }
    render();
  }
  function reset(ctx) {
    currentCtx = ctx || currentCtx;
    agents.clear();
    aliases.clear();
    render();
  }
  function updateProgress(payload) {
    if (!enabled || !payload || typeof payload !== "object") return;
    upsert(payload, null, "progress");
    trimHistory();
    render();
  }
  function updateLifecycle(payload) {
    if (!enabled || !payload || typeof payload !== "object") return;
    const role = roleFrom(payload, payload.progress || {});
    if (!role) return;
    const status = statusOf(payload.status, "pending");
    upsert({ ...payload, progress: { ...(payload.progress || {}), status } }, null, "lifecycle");
    trimHistory();
    render();
  }
  function childrenOf(parentKey) {
    return [...agents.values()]
      .filter(item => (item.parentKey || null) === (parentKey || null))
      .sort((a, b) => (a.started - b.started) || a.name.localeCompare(b.name));
  }
  function lineFor(item, prefix = "") {
    const status = statusOf(item.progress?.status);
    const gauge = contextGauge(item.progress);
    const model = item.model ? ` · ${item.model}` : "";
    const detached = item.detached ? " · detached" : " · synchronous";
    return `${prefix}${agentLabel(item, 72)} [${item.agent}] · ${status}${gauge ? ` · ${gauge}` : ""}${model}${detached}`;
  }
  function treeLines({ activeOnly = false } = {}) {
    const included = new Set(
      [...agents.values()]
        .filter(item => !activeOnly || ACTIVE_STATUSES.has(statusOf(item.progress?.status)))
        .map(item => item.key),
    );
    if (activeOnly) {
      for (const key of [...included]) {
        let parent = agents.get(key)?.parentKey;
        while (parent) { included.add(parent); parent = agents.get(parent)?.parentKey; }
      }
    }
    const roots = [...agents.values()]
      .filter(item => included.has(item.key) && (!item.parentKey || !included.has(item.parentKey)))
      .sort((a, b) => (a.started - b.started) || a.name.localeCompare(b.name));
    const lines = ["Main"];
    const visit = (item, prefix, isLast) => {
      lines.push(lineFor(item, `${prefix}${isLast ? "└─ " : "├─ "}`));
      const children = childrenOf(item.key).filter(child => included.has(child.key));
      children.forEach((child, index) => visit(child, `${prefix}${isLast ? "   " : "│  "}`, index === children.length - 1));
    };
    roots.forEach((item, index) => visit(item, "", index === roots.length - 1));
    return lines;
  }
  function publicRecord(item) {
    return {
      id: item.id,
      name: item.name,
      role: item.agent,
      parent_id: item.parentKey ? agents.get(item.parentKey)?.id || item.parentKey : "Main",
      depth: depthOf(item),
      status: statusOf(item.progress?.status),
      detached: item.detached,
      spawn_mode: item.detached ? "detached" : "synchronous",
      model: item.model || null,
      task: item.description || null,
      assignment: item.assignment || null,
      activity: progressActivity(item.progress),
      current_tool: oneLine(item.progress?.currentTool || "", 80) || null,
      current_tool_args: oneLine(item.progress?.currentToolArgs || "", 240) || null,
      context_tokens: finiteNumber(item.progress?.contextTokens) ?? null,
      context_window: finiteNumber(item.progress?.contextWindow) ?? null,
      lifetime_tokens: finiteNumber(item.progress?.tokens) ?? null,
      session_id: item.sessionId || null,
      session_file: item.sessionFile || null,
      tool_call_id: item.toolCallId || null,
      parent_tool_call_id: item.parentToolCallId || null,
      agent_source: item.agentSource || null,
      source: item.source,
      index: item.index ?? null,
      updated_sequence: item.updated,
    };
  }
  function snapshot({ activeOnly = false } = {}) {
    const records = [...agents.values()]
      .filter(item => !activeOnly || ACTIVE_STATUSES.has(statusOf(item.progress?.status)))
      .sort((a, b) => (depthOf(a) - depthOf(b)) || (a.started - b.started) || a.name.localeCompare(b.name));
    return {
      schema: "bbk.omp-agent-tree.v1",
      status: "PASS",
      package_version: version,
      active_count: activeAgents().length,
      agent_count: agents.size,
      agents: records.map(publicRecord),
      tree: treeLines({ activeOnly }),
    };
  }
  function details(selector) {
    const query = String(selector || "").trim().toLowerCase();
    if (!query) return [];
    return [...agents.values()]
      .filter(item => [item.id, item.name, item.agent, item.sessionId, item.toolCallId, item.key]
        .some(value => String(value || "").toLowerCase() === query))
      .sort((a, b) => b.updated - a.updated)
      .map(publicRecord);
  }

  const unsubscribe = [];
  try {
    const stop = pi.events?.on?.(TASK_SUBAGENT_PROGRESS_CHANNEL, updateProgress);
    if (typeof stop === "function") unsubscribe.push(stop);
  } catch {}
  try {
    const stop = pi.events?.on?.(TASK_SUBAGENT_LIFECYCLE_CHANNEL, updateLifecycle);
    if (typeof stop === "function") unsubscribe.push(stop);
  } catch {}
  function dispose(ctx) {
    currentCtx = ctx || currentCtx;
    enabled = false;
    agents.clear();
    aliases.clear();
    clearWidget();
    for (const stop of unsubscribe.splice(0)) {
      try { stop(); } catch {}
    }
  }
  return { setMode, reset, updateProgress, updateLifecycle, snapshot, details, dispose };
}

function registerAgentViewCommand(pi, activity) {
  pi.registerCommand("bbk:agents", {
    description: "show the complete BBK sub-agent tree or inspect one nested agent",
    handler: async (first, second) => {
      const { args, ctx } = commandInvocation(first, second);
      const tokens = splitArgs(args);
      const mode = String(tokens[0] || "all").toLowerCase();
      let text;
      if (mode === "json") {
        text = JSON.stringify(activity.snapshot({ activeOnly: false }), null, 2);
      } else if (mode === "active") {
        const value = activity.snapshot({ activeOnly: true });
        text = `BBK agents: ${value.active_count} active / ${value.agent_count} known\n${value.tree.join("\n")}`;
      } else if (mode === "all" || mode === "tree") {
        const value = activity.snapshot({ activeOnly: false });
        text = `BBK agents: ${value.active_count} active / ${value.agent_count} known\n${value.tree.join("\n")}`;
      } else {
        const selector = mode === "details" ? tokens.slice(1).join(" ") : tokens.join(" ");
        if (!selector) {
          text = "Usage: /bbk:agents [all|active|json|details <agent-id-or-name>]";
        } else {
          const found = activity.details(selector);
          text = found.length
            ? JSON.stringify({ schema: "bbk.omp-agent-details.v1", status: "PASS", matches: found }, null, 2)
            : `No BBK agent matched ${selector}. Use /bbk:agents to view the complete tree.`;
        }
      }
      ctx?.ui?.notify?.(text, "info");
      return undefined;
    },
  });
}

function registerBeadsCommand(pi) {
  pi.registerCommand("bbk:beads", {
    description: "plan or apply normal BBK-to-Beads coordination projection",
    handler: async (first, second) => {
      const { args, ctx } = commandInvocation(first, second);
      const tokens = splitArgs(args);
      const action = String(tokens.shift() || "plan").toLowerCase();
      let argv;
      if (action === "plan" || action === "status") argv = ["beads", "plan", ...tokens];
      else if (action === "apply" || action === "sync") argv = ["beads", "plan", ...tokens, "--apply"];
      else if (action === "handoff" || action === "handoff-plan") argv = ["beads", "handoff-plan", ...tokens];
      else if (action === "handoff-apply") argv = ["beads", "handoff-plan", ...tokens, "--apply"];
      else {
        ctx?.ui?.notify?.(
          "Usage: /bbk:beads [plan|apply] [--kind <kind> ...] or /bbk:beads [handoff|handoff-apply] --handoff <file> [--target-bbk-id <id>] [--bead <id>]",
          "warning",
        );
        return undefined;
      }
      return publishCommandResult(pi, ctx, await runBbk(argv, ctx?.cwd || process.cwd()), "bbk:beads");
    },
  });
}

function createBbkModeController(pi, onStateChange = () => {}) {
  let enabled = false;
  let loaded = false;
  let latestExpectedPrompt = null;
  const recordedReplacementDigests = new Set();
  const recordedProviderDigests = new Set();

  function appendPromptReceipt(data) {
    if (typeof pi.appendEntry !== "function") return;
    pi.appendEntry(BBK_PROMPT_RECEIPT_ENTRY_TYPE, {
      schema: BBK_PROMPT_RECEIPT_SCHEMA,
      package_version: version,
      observed_at: new Date().toISOString(),
      ...data,
    });
  }
  function recordReplacement(sourceBlocks, effectiveBlocks, status, ctx) {
    const source = promptReceiptSummary(sourceBlocks);
    const effective = promptReceiptSummary(effectiveBlocks);
    const identity = promptOuterIdentity(promptBlocksFromValue(effectiveBlocks).join("\n\n"));
    const key = `${status}:${identity.role || identity.kind}:${effective.sha256}`;
    latestExpectedPrompt = { ...effective, role: identity.role, prompt_kind: identity.kind };
    if (recordedReplacementDigests.has(key)) return;
    recordedReplacementDigests.add(key);
    const genericDetected = sourceHasGenericPromptMaterial(sourceBlocks);
    appendPromptReceipt({
      phase: "before_agent_start",
      status,
      prompt_kind: identity.kind,
      role: identity.role,
      cwd: String(ctx?.cwd || process.cwd()),
      source,
      effective,
      generic_omp_contamination_detected: genericDetected,
      generic_omp_contamination_removed: genericDetected && ["agent", "controller"].includes(identity.kind),
      raw_prompt_persisted: false,
    });
  }
  async function verifyProviderPrompt(_event, ctx) {
    if (!latestExpectedPrompt) return;
    let observedValue;
    let availability = "AVAILABLE";
    try {
      if (typeof ctx?.getSystemPrompt !== "function") availability = "UNAVAILABLE";
      else observedValue = await Promise.resolve(ctx.getSystemPrompt());
    } catch (error) {
      availability = "ERROR";
      observedValue = null;
    }
    const observed = availability === "AVAILABLE" ? promptReceiptSummary(observedValue) : null;
    const status = availability === "AVAILABLE"
      ? observed.sha256 === latestExpectedPrompt.sha256 ? "VERIFIED" : "MISMATCH"
      : availability;
    const key = `${status}:${latestExpectedPrompt.sha256}:${observed?.sha256 || "none"}`;
    if (recordedProviderDigests.has(key)) return;
    recordedProviderDigests.add(key);
    appendPromptReceipt({
      phase: "before_provider_request",
      status,
      prompt_kind: latestExpectedPrompt.prompt_kind,
      role: latestExpectedPrompt.role,
      cwd: String(ctx?.cwd || process.cwd()),
      expected: {
        block_count: latestExpectedPrompt.block_count,
        length: latestExpectedPrompt.length,
        sha256: latestExpectedPrompt.sha256,
      },
      observed,
      provider_bound_verification: status,
      enforcement: "OBSERVABILITY_ONLY",
      raw_prompt_persisted: false,
    });
  }
  function promptStatus(ctx) {
    let branch = [];
    try { branch = ctx?.sessionManager?.getBranch?.() || []; } catch {}
    const receipts = (Array.isArray(branch) ? branch : [])
      .filter(entry => entry?.type === "custom" && entry?.customType === BBK_PROMPT_RECEIPT_ENTRY_TYPE)
      .map(entry => entry.data)
      .filter(value => value?.schema === BBK_PROMPT_RECEIPT_SCHEMA);
    const latestByKey = new Map();
    for (const receipt of receipts) {
      const key = `${receipt.role || receipt.prompt_kind || "unknown"}:${receipt.phase}`;
      latestByKey.set(key, receipt);
    }
    return {
      schema: "bbk.prompt-status.v1",
      package_version: version,
      receipt_count: receipts.length,
      latest: [...latestByKey.values()],
    };
  }

  function publishState(ctx) {
    try { onStateChange(enabled, ctx); } catch {}
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
    publishState(ctx);
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
    publishState(ctx);
    return changed;
  }
  function enter(ctx) { return persist(true, ctx); }
  function exit(ctx) { return persist(false, ctx); }
  function promptReplacement(event, ctx) {
    const sourceBlocks = systemPromptBlocks(event);
    try {
      const extracted = extractBbkAgentBlock(event);
      if (extracted?.alreadyReplaced) {
        recordReplacement(sourceBlocks, sourceBlocks, "ALREADY_REPLACED", ctx);
        return { systemPrompt: sourceBlocks };
      }
      if (extracted) {
        const effective = [buildAgentSystemPrompt(extracted, ctx)];
        recordReplacement(sourceBlocks, effective, "REPLACED", ctx);
        return { systemPrompt: effective };
      }
      ensure(ctx);
      if (!enabled) return undefined;
      const effective = [buildControllerSystemPrompt(ctx)];
      recordReplacement(sourceBlocks, effective, "REPLACED", ctx);
      return { systemPrompt: effective };
    } catch (error) {
      const effective = [failClosedSystemPrompt(error, ctx)];
      recordReplacement(sourceBlocks, effective, "FAIL_CLOSED", ctx);
      return { systemPrompt: effective };
    }
  }
  return {
    enter, exit, restore, ensure, promptReplacement, verifyProviderPrompt, promptStatus,
    isEnabled: () => enabled,
  };
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

  pi.registerCommand("bbk:prompt-status", {
    description: "show effective BBK prompt replacement and provider-bound verification receipts",
    handler: async (first, second) => {
      const { args, ctx } = commandInvocation(first, second);
      const result = mode.promptStatus(ctx);
      const jsonMode = String(args || "").trim().toLowerCase() === "json";
      const text = jsonMode
        ? JSON.stringify(result, null, 2)
        : result.latest.length
          ? result.latest.map(item => `${item.role || item.prompt_kind || "unknown"} · ${item.phase} · ${item.status} · ${item.observed?.sha256 || item.effective?.sha256 || item.expected?.sha256 || "no-digest"}`).join("\n")
          : "No BBK prompt receipts are recorded in the current branch.";
      ctx?.ui?.notify?.(text, "info");
      return undefined;
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
function routingScope(details) {
  return String(details?.scope || details?.resolved_scope || "unknown");
}
function routingScopeNotice(details) {
  const scope = routingScope(details);
  if (scope === "user") {
    return "This is the shared user-scoped BBK installation. A change affects future BBK sub-agent spawns in every project that uses it.";
  }
  if (scope === "project") {
    return `This change is isolated to project ${details.project_root || details.resolved_project_root || "(unknown project root)"}.`;
  }
  return "The routing target scope could not be established; do not mutate it until the binding is repaired.";
}
function routeSummaryText(details) {
  const lines = [
    `Active BBK-managed profile: ${details.active_profile || "unknown"}`,
    `Scope: ${routingScope(details)}`,
    `Project: ${details.project_root || details.resolved_project_root || "n/a"}`,
    `Resolution: ${details.resolution_source || "binding"}`,
    `Binding: ${details.binding_path || "unknown"}`,
    `Agents: ${details.omp_agents || "unknown"}`,
    `State: ${details.state_path || "unknown"}`,
    `Manifest: ${details.manifest_path || "unknown"}`,
    `Source: ${details.source || "unknown"}`,
    "",
    "Routes:",
  ];
  for (const item of details.summary || []) {
    lines.push(`- ${item.roles} roles: ${item.model} / ${item.thinkingLevel}`);
  }
  if (details.precedence_note) lines.push("", `Precedence: ${details.precedence_note}`);
  lines.push("", routingScopeNotice(details));
  return lines.join("\n");
}
async function publishRoutingResult(_pi, ctx, value, label) {
  if (value.code === 0) {
    const details = value.details || {};
    let text;
    if (details.status === "EXPORTED") {
      text = `${label}: EXPORTED${details.path ? `\npath: ${details.path}` : ""}\nScope: ${routingScope(details)}${details.project_root ? `\nProject: ${details.project_root}` : ""}`;
    } else if (["bbk.omp-project-routing-status.v1", "bbk.omp-project-routing-localization.v1", "bbk.omp-project-routing-repair.v1"].includes(details.schema)) {
      text = [
        `${label}: ${details.status || "UNKNOWN"}`,
        `Project: ${details.project_root || "unknown"}`,
        `User routing unchanged: ${details.user_state_unchanged === false ? "no" : "yes"}`,
        details.reload_required ? "Reload required: yes" : "Reload required: no",
        details.smallest_next_action ? `Next: ${details.smallest_next_action}` : null,
      ].filter(Boolean).join("\n");
    } else if (details.roles || details.summary) {
      text = routeSummaryText(details);
      if (typeof details.changed_role_count === "number") {
        text += `\nChanged roles: ${details.changed_role_count}`;
      }
      text += "\nApplies to future BBK sub-agent spawns; already-running agents are unchanged.";
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
async function confirmRoutingMutation(ctx, details, title, body) {
  const scope = routingScope(details);
  const notice = routingScopeNotice(details);
  if (!['user', 'project'].includes(scope)) {
    ctx?.ui?.notify?.(`${notice}\nNo routing change was made.`, "warning");
    return false;
  }
  if (typeof ctx?.ui?.confirm === "function") {
    return Boolean(await ctx.ui.confirm(title, `${body}\n\n${notice}`));
  }
  if (scope === "user") {
    ctx?.ui?.notify?.(`${notice}\nUse an explicit 'user' target from a UI-enabled OMP session to confirm this shared change.`, "warning");
    return false;
  }
  return true;
}
function routingTargetLabels() {
  return [
    "Automatic — nearest project installation, otherwise user installation",
    "Project — nearest project-scoped BBK installation",
    "User — shared user-scoped BBK installation",
    "Cancel",
  ];
}
function routingTargetFromLabel(label) {
  if (String(label || "").startsWith("Project")) return "project";
  if (String(label || "").startsWith("User")) return "user";
  if (String(label || "").startsWith("Automatic")) return "auto";
  return null;
}

function projectLocalizationRoot(ctx, details = {}) {
  return path.resolve(details.project_root || details.resolved_project_root || ctx?.cwd || process.cwd());
}
async function executeProjectLocalization(pi, ctx, action, projectRoot, { dryRunOnly = false } = {}) {
  const cwd = ctx?.cwd || process.cwd();
  const root = path.resolve(projectRoot || cwd);
  if (action === "status") {
    return publishRoutingResult(
      pi,
      ctx,
      await runRouting(["project-status", "--project-root", root], cwd, undefined, "user"),
      "bbk:models project-status",
    );
  }
  const planArgs = action === "create"
    ? ["create-project", "--project-root", root, "--dry-run"]
    : ["repair-project", "--project-root", root];
  const plan = await runRouting(planArgs, cwd, undefined, "user");
  if (plan.code !== 0) return publishRoutingResult(pi, ctx, plan, `bbk:models ${action}-project`);
  if (dryRunOnly) return publishRoutingResult(pi, ctx, plan, `bbk:models ${action}-project dry-run`);
  const details = plan.details || {};
  const planSummary = details.installer_result?.summary
    ? JSON.stringify(details.installer_result.summary)
    : `${details.installer_result?.file_count || details.installer_result?.files?.length || "unknown"} planned files`;
  let confirmed = true;
  if (typeof ctx?.ui?.confirm === "function") {
    confirmed = Boolean(await ctx.ui.confirm(
      action === "create" ? "Create project-local BBK routing?" : "Repair project-local BBK routing?",
      [
        `Project: ${root}`,
        `Plan: ${planSummary}`,
        "Source: exact effective authenticated user OMP routes",
        "Effect: project-scoped OMP-only BBK installation; user routing remains unchanged",
        action === "repair" ? "Modified manifest-owned files are backed up by the installer before replacement." : null,
      ].filter(Boolean).join("\n"),
    ));
  } else if (!ctx?.hasUI) {
    ctx?.ui?.notify?.("A UI confirmation is required for project routing creation or repair. Use the Python router with explicit arguments for headless automation.", "warning");
    return undefined;
  }
  if (!confirmed) return undefined;
  const applyArgs = action === "create"
    ? ["create-project", "--project-root", root]
    : ["repair-project", "--project-root", root, "--apply"];
  const applied = await runRouting(applyArgs, cwd, undefined, "user");
  const result = await publishRoutingResult(pi, ctx, applied, `bbk:models ${action}-project`);
  if (applied.code === 0 && applied.details?.reload_required) {
    ctx?.ui?.notify?.(`Project-local BBK routing is installed at ${root}. Reload or restart OMP in this project before spawning new BBK agents.`, "info");
  }
  return result;
}
async function interactiveRoutingMenu(pi, ctx, requestedScope = "auto") {
  if (!ctx?.hasUI || typeof ctx?.ui?.select !== "function") {
    return publishRoutingResult(pi, ctx, await runRouting(["status"], ctx?.cwd || process.cwd(), undefined, requestedScope), "bbk:models status");
  }
  const initial = await runRouting(["status"], ctx.cwd || process.cwd(), undefined, requestedScope);
  if (initial.code !== 0) return publishRoutingResult(pi, ctx, initial, "bbk:models status");
  const scopeLabel = `${routingScope(initial.details)}${initial.details.project_root ? ` · ${initial.details.project_root}` : ""}`;
  const projectAction = routingScope(initial.details) === "user"
    ? "Create project-local routing for this directory"
    : "Inspect or repair this project-local routing";
  const action = await ctx.ui.select(`BBK OMP sub-agent model routing [${scopeLabel}]`, [
    projectAction,
    "Apply a routing profile",
    "Edit one sub-agent",
    "View current routing",
    "Choose routing target",
    "Apply a profile file",
    "Export current routing",
    "Cancel",
  ]);
  if (!action || action === "Cancel") return;
  if (action === "Create project-local routing for this directory") {
    return executeProjectLocalization(pi, ctx, "create", projectLocalizationRoot(ctx));
  }
  if (action === "Inspect or repair this project-local routing") {
    const projectRoot = projectLocalizationRoot(ctx, initial.details);
    const choice = await ctx.ui.select("Project-local routing", ["View project routing status", "Dry-run repair", "Apply repair", "Cancel"]);
    if (!choice || choice === "Cancel") return;
    if (choice === "View project routing status") return executeProjectLocalization(pi, ctx, "status", projectRoot);
    return executeProjectLocalization(pi, ctx, "repair", projectRoot, { dryRunOnly: choice === "Dry-run repair" });
  }
  if (action === "Choose routing target") {
    const selected = await ctx.ui.select("Routing target", routingTargetLabels());
    const nextScope = routingTargetFromLabel(selected);
    if (!nextScope) return;
    return interactiveRoutingMenu(pi, ctx, nextScope);
  }
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
    const ok = await confirmRoutingMutation(
      ctx,
      initial.details,
      "Apply routing profile?",
      `${profile.id}\n\n${profile.description}\n\nFuture BBK sub-agent spawns will use this profile.${availability}`,
    );
    if (!ok) return;
    return publishRoutingResult(
      pi,
      ctx,
      await runRouting(["apply-profile", profile.id], ctx.cwd || process.cwd(), undefined, requestedScope),
      `bbk:models ${profile.id}`,
    );
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
    const ok = await confirmRoutingMutation(ctx, initial.details, "Apply sub-agent route?", `${role}\nModel: ${model}\nThinking: ${thinking}${availability}`);
    if (!ok) return;
    return publishRoutingResult(
      pi,
      ctx,
      await runRouting(["set-role", role, "--model", model, "--thinking-level", thinking], ctx.cwd || process.cwd(), undefined, requestedScope),
      `bbk:models ${role}`,
    );
  }
  if (action === "Apply a profile file") {
    const rawPath = await ctx.ui.input("Profile JSON path", "");
    const profilePath = String(rawPath || "").trim();
    if (!profilePath) return;
    const ok = await confirmRoutingMutation(ctx, initial.details, "Apply profile file?", profilePath);
    if (!ok) return;
    return publishRoutingResult(
      pi,
      ctx,
      await runRouting(["apply-file", profilePath], ctx.cwd || process.cwd(), undefined, requestedScope),
      "bbk:models apply-file",
    );
  }
  if (action === "Export current routing") {
    const rawPath = await ctx.ui.input("Export path", "bbk-omp-model-routing.json");
    const outputPath = String(rawPath || "").trim();
    if (!outputPath) return;
    const rawId = await ctx.ui.input("Profile id", "exported-profile");
    const profileId = String(rawId || "").trim();
    if (!profileId) return;
    return publishRoutingResult(
      pi,
      ctx,
      await runRouting(["export", outputPath, "--id", profileId], ctx.cwd || process.cwd(), undefined, requestedScope),
      "bbk:models export",
    );
  }
}

function registerModelRoutingCommand(pi) {
  pi.registerCommand("bbk:models", {
    description: "inspect or change project- or user-scoped BBK OMP sub-agent model routing",
    handler: async (first, second) => {
      const { args, ctx } = commandInvocation(first, second);
      const tokens = splitArgs(args);
      if (!tokens.length) return interactiveRoutingMenu(pi, ctx, "auto");
      if (tokens[0] === "project" && ["create", "repair", "status"].includes(tokens[1])) {
        const projectAction = tokens[1];
        const remainder = tokens.slice(2);
        const dryRunOnly = remainder.includes("--dry-run");
        const explicitPath = remainder.find(value => value !== "--dry-run" && value !== "--apply");
        const projectRoot = path.resolve(explicitPath || ctx?.cwd || process.cwd());
        if (projectAction === "status") return executeProjectLocalization(pi, ctx, "status", projectRoot);
        return executeProjectLocalization(pi, ctx, projectAction, projectRoot, { dryRunOnly });
      }
      let requestedScope = "auto";
      if (tokens[0] === "--scope" && ["auto", "project", "user"].includes(tokens[1])) {
        tokens.shift();
        requestedScope = tokens.shift();
      } else if (["auto", "project", "user"].includes(tokens[0])) {
        requestedScope = tokens.shift();
      }
      const [action, ...rest] = tokens;
      if (["project-status", "create-project", "repair-project"].includes(action)) {
        const dryRunOnly = rest.includes("--dry-run");
        const explicitPath = rest.find(value => value !== "--dry-run" && value !== "--apply");
        const projectRoot = path.resolve(explicitPath || ctx?.cwd || process.cwd());
        if (action === "project-status") return executeProjectLocalization(pi, ctx, "status", projectRoot);
        if (action === "create-project") return executeProjectLocalization(pi, ctx, "create", projectRoot, { dryRunOnly });
        return executeProjectLocalization(pi, ctx, "repair", projectRoot, { dryRunOnly });
      }
      let argv;
      let mutating = false;
      if (!action || ["status", "profiles", "list"].includes(action)) argv = ["status"];
      else if (action === "profile" && rest.length === 1) { argv = ["apply-profile", rest[0]]; mutating = true; }
      else if (action === "set" && rest.length === 3) { argv = ["set-role", rest[0], "--model", rest[1], "--thinking-level", rest[2]]; mutating = true; }
      else if (["apply", "apply-file"].includes(action) && rest.length === 1) { argv = ["apply-file", rest[0]]; mutating = true; }
      else if (action === "export" && rest.length >= 1) argv = ["export", rest[0], ...(rest[1] ? ["--id", rest[1]] : [])];
      else {
        ctx?.ui?.notify?.("Usage: /bbk:models project [create|repair|status] [path] [--dry-run]; /bbk:models project profile <id>; or /bbk:models [auto|project|user] [status | profile <id> | set <role> <model> <thinking> | apply <file> | export <file> [id]]", "warning");
        return;
      }
      if (mutating) {
        // Direct slash commands already carry a complete action. Resolve the
        // target from its v3 binding in-process so project mutations need only
        // one routing CLI invocation. The Python router still authenticates the
        // complete binding, manifest, state, and managed agents before writing.
        let target;
        try {
          target = resolveRoutingTarget(ctx?.cwd || process.cwd(), requestedScope);
        } catch (error) {
          return publishRoutingResult(pi, ctx, {
            code: 2,
            details: {
              schema: "bbk.omp-model-routing-target-error.v1",
              status: "ERROR",
              requested_scope: requestedScope,
              error: String(error?.message || error),
            },
          }, "bbk:models target");
        }
        const targetDetails = {
          scope: target.scope,
          resolved_scope: target.scope,
          project_root: target.projectRoot,
          resolved_project_root: target.projectRoot,
          binding_path: target.bindingPath,
          resolution_source: target.source,
        };
        if (target.scope !== "project") {
          const ok = await confirmRoutingMutation(
            ctx,
            targetDetails,
            target.scope === "user" ? "Change shared user routing?" : "Change routing with unresolved scope?",
            `Command: ${tokens.join(" ")}\n\nAlready-running agents are unchanged.`,
          );
          if (!ok) return;
        }
      }
      return publishRoutingResult(pi, ctx, await runRouting(argv, ctx?.cwd || process.cwd(), undefined, requestedScope), "bbk:models");
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
    parameters: z.object({ root: text(), title: text(), projectId: text(), noExamples: bool() }),
    argv: p => ["init", ...rootArgs(p.root), ...(p.title ? ["--title", p.title] : []), ...(p.projectId ? ["--project-id", p.projectId] : []), ...(p.noExamples ? ["--no-examples"] : [])],
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
    name: "bbk_beads_sync", label: "BBK Beads Projection", description: "Plan or apply the role-owned BBK-to-Beads coordination projection while keeping canonical BBK records authoritative.",
    parameters: z.object({ root: text(), workUnit: text(), kinds: texts(), ids: texts(), apply: bool(), initialize: bool() }),
    argv: p => ["beads", "plan", ...rootArgs(p.root), ...(p.workUnit ? ["--work-unit", p.workUnit] : []),
      ...repeated("--kind", p.kinds), ...repeated("--id", p.ids), ...(p.apply ? ["--apply"] : []), ...(p.initialize ? ["--initialize"] : [])],
  });
  registerCliTool(pi, {
    name: "bbk_beads_handoff", label: "BBK Beads Handoff Pointer", description: "Plan or append a compact verified BBK handoff pointer to its bound Beads issue.",
    parameters: z.object({ root: text(), handoff: z.string(), targetBbkId: text(), bead: text(), apply: bool() }),
    argv: p => ["beads", "handoff-plan", ...rootArgs(p.root), "--handoff", p.handoff,
      ...(p.targetBbkId ? ["--target-bbk-id", p.targetBbkId] : []), ...(p.bead ? ["--bead", p.bead] : []), ...(p.apply ? ["--apply"] : [])],
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
    name: "bbk_schema_template", label: "BBK Schema Template", description: "Create a canonical BBK template, including compact infrastructure and network contracts.",
    parameters: z.object({ kind: z.string(), output: z.string(), subjectKind: text(), depth: text(), force: bool() }),
    argv: p => ["schema", "template", "--kind", p.kind, "--output", p.output,
      ...(p.subjectKind ? ["--subject-kind", p.subjectKind] : []), ...(p.depth ? ["--depth", p.depth] : []), ...(p.force ? ["--force"] : [])],
  });
  registerCliTool(pi, {
    name: "bbk_schema_enum", label: "BBK Schema Enum", description: "Inspect the schema node, allowed values, description, and smallest valid example for an instance pointer.",
    parameters: z.object({ schema: z.string(), pointer: z.string() }),
    argv: p => ["schema", "enum", "--schema", p.schema, "--pointer", p.pointer],
  });
  registerCliTool(pi, {
    name: "bbk_schema_explain", label: "BBK Schema Explain", description: "Explain validation failures and applicability using built-in validation plus an optional Draft 2020-12 cross-check.",
    parameters: z.object({ schema: z.string(), instance: z.string(), pointer: text() }),
    argv: p => ["schema", "explain", "--schema", p.schema, "--instance", p.instance, ...(p.pointer ? ["--pointer", p.pointer] : [])],
  });
  registerCliTool(pi, {
    name: "bbk_artifact_manifest", label: "BBK Artifact Manifest", description: "Create a deterministic, content-addressed manifest for an exact artifact set without ad hoc hashing scripts.",
    parameters: z.object({ root: text(), paths: texts(), includes: texts(), excludes: texts(), includeExamples: bool(), subject: text(), rootLabel: text(), output: text() }),
    argv: p => ["artifact", "manifest", ...rootArgs(p.root), ...repeated("--path", p.paths), ...repeated("--include", p.includes),
      ...repeated("--exclude", p.excludes), ...(p.includeExamples ? ["--include-examples"] : []), ...(p.subject ? ["--subject", p.subject] : []),
      ...(p.rootLabel ? ["--root-label", p.rootLabel] : []), ...(p.output ? ["--output", p.output] : [])],
  });
  registerCliTool(pi, {
    name: "bbk_artifact_preflight", label: "BBK Artifact Package Preflight", description: "Run strict JSON, profile, identity, reference, and package-closure checks against an artifact-package draft before review or sealing.",
    parameters: z.object({ draftRoot: z.string(), registry: text(), maxDepth: text() }),
    argv: p => ["artifact", "preflight", p.draftRoot, ...(p.registry ? ["--registry", p.registry] : []), ...(p.maxDepth ? ["--max-depth", String(p.maxDepth)] : [])],
  });
  registerCliTool(pi, {
    name: "bbk_artifact_seal", label: "BBK Artifact Package Seal", description: "Preflight, canonicalize, stage, verify, and atomically publish a new immutable artifact package.",
    parameters: z.object({ draftRoot: z.string(), output: z.string(), registry: text(), recoverStaleLock: bool() }),
    argv: p => ["artifact", "seal", p.draftRoot, "--output", p.output, ...(p.registry ? ["--registry", p.registry] : []), ...(p.recoverStaleLock ? ["--recover-stale-lock"] : [])],
  });
  registerCliTool(pi, {
    name: "bbk_artifact_verify", label: "BBK Artifact Verify", description: "Read-only verify either a sealed artifact package or a legacy artifact manifest against exact stored bytes.",
    parameters: z.object({ manifest: z.string(), root: text(), registry: text() }),
    argv: p => ["artifact", "verify", p.manifest, ...rootArgs(p.root), ...(p.registry ? ["--registry", p.registry] : [])],
  });
  registerCliTool(pi, {
    name: "bbk_artifact_successor", label: "BBK Artifact Package Successor", description: "Create a new editable draft bound to an exact immutable predecessor package without modifying the predecessor.",
    parameters: z.object({ sealedRoot: z.string(), output: z.string(), revision: z.string(), reason: z.string(), registry: text(), recoverStaleLock: bool() }),
    argv: p => ["artifact", "successor", p.sealedRoot, "--output", p.output, "--revision", p.revision, "--reason", p.reason,
      ...(p.registry ? ["--registry", p.registry] : []), ...(p.recoverStaleLock ? ["--recover-stale-lock"] : [])],
  });
  registerCliTool(pi, {
    name: "bbk_host_preflight", label: "BBK Host Preflight", description: "Run bounded read-only probes for only the capabilities named by an exact host-preflight request, with host-bound cache evidence.",
    parameters: z.object({ request: z.string(), root: text(), output: text(), cacheDir: text(), noCache: bool(), timeout: text() }),
    argv: p => ["preflight", "run", p.request, ...rootArgs(p.root), ...(p.output ? ["--output", p.output] : []),
      ...(p.cacheDir ? ["--cache-dir", p.cacheDir] : []), ...(p.noCache ? ["--no-cache"] : []), ...(p.timeout ? ["--timeout", String(p.timeout)] : [])],
  });
  registerCliTool(pi, {
    name: "bbk_context_worker", label: "BBK Worker Context Package", description: "Generate and seal a standard Worker context from a complete WorkUnit, profile lock, host preflight, governing references, and optional prototype charter.",
    parameters: z.object({ root: text(), workUnit: z.string(), profileLock: z.string(), hostPreflight: z.string(), prototypeCharter: text(), output: text(), id: text(), revision: text() }),
    argv: p => ["context", "worker", ...rootArgs(p.root), "--work-unit", p.workUnit, "--profile-lock", p.profileLock, "--host-preflight", p.hostPreflight,
      ...(p.prototypeCharter ? ["--prototype-charter", p.prototypeCharter] : []), ...(p.output ? ["--output", p.output] : []),
      ...(p.id ? ["--id", p.id] : []), ...(p.revision ? ["--revision", p.revision] : [])],
  });
  registerCliTool(pi, {
    name: "bbk_context_review", label: "BBK Review Context Package", description: "Generate and seal a candidate-bound review or focused-recheck package from exact review focus, floors, findings, evidence, and assurance mode.",
    parameters: z.object({ root: text(), candidate: z.string(), request: z.string(), output: text(), id: text(), revision: text() }),
    argv: p => ["context", "review", ...rootArgs(p.root), "--candidate", p.candidate, "--request", p.request,
      ...(p.output ? ["--output", p.output] : []), ...(p.id ? ["--id", p.id] : []), ...(p.revision ? ["--revision", p.revision] : [])],
  });
  registerCliTool(pi, {
    name: "bbk_handoff_create", label: "BBK Sealed Handoff", description: "Create a new immutable bbk.handoff.v2 package; use legacyV1 only for an explicit compatibility record.",
    parameters: z.object({ root: text(), id: text(), workUnit: z.string(), attempt: text(), role: text(), invocationId: text(), threadId: text(), subjectKind: text(), subjectId: text(), subjectRevision: text(), authoritySource: text(), authorityScopes: texts(), authorityNotStanding: bool(), capabilityZones: texts(), interruptReason: text(), interruptEvidence: texts(), partialWorkLocation: text(), disposition: z.string(), summary: z.string(), workPerformed: texts(), changedPaths: texts(), commandsRun: texts(), checks: texts(), findings: texts(), discoveries: texts(), residuals: texts(), blockers: texts(), artifacts: texts(), evidence: texts(), continuationState: text(), checkpoint: text(), noResumeSameThread: bool(), completedStep: text(), nextStep: text(), nextAction: z.string(), cleanupState: text(), cleanupActions: texts(), prohibitedClaims: texts(), legacyV1: bool(), output: text(), force: bool() }),
    argv: p => ["handoff", "create", ...rootArgs(p.root), ...(p.id ? ["--id", p.id] : []), "--work-unit", p.workUnit,
      ...(p.attempt ? ["--attempt", String(p.attempt)] : []), ...(p.role ? ["--role", p.role] : []), ...(p.invocationId ? ["--invocation-id", p.invocationId] : []),
      ...(p.threadId ? ["--thread-id", p.threadId] : []), ...(p.subjectKind ? ["--subject-kind", p.subjectKind] : []), ...(p.subjectId ? ["--subject-id", p.subjectId] : []),
      ...(p.subjectRevision ? ["--subject-revision", p.subjectRevision] : []), ...(p.authoritySource ? ["--authority-source", p.authoritySource] : []),
      ...repeated("--authority-scope", p.authorityScopes), ...(p.authorityNotStanding ? ["--authority-not-standing"] : []), ...repeated("--capability-zone", p.capabilityZones),
      ...(p.interruptReason ? ["--interrupt-reason", p.interruptReason] : []), ...repeated("--interrupt-evidence", p.interruptEvidence),
      ...(p.partialWorkLocation ? ["--partial-work-location", p.partialWorkLocation] : []), "--disposition", p.disposition, "--summary", p.summary,
      ...repeated("--work-performed", p.workPerformed), ...repeated("--changed-path", p.changedPaths), ...repeated("--command-run", p.commandsRun),
      ...repeated("--check", p.checks), ...repeated("--finding", p.findings), ...repeated("--discovery", p.discoveries), ...repeated("--residual", p.residuals),
      ...repeated("--blocker", p.blockers), ...repeated("--artifact", p.artifacts), ...repeated("--evidence", p.evidence),
      ...(p.continuationState ? ["--continuation-state", p.continuationState] : []), ...(p.checkpoint ? ["--checkpoint", p.checkpoint] : []),
      ...(p.noResumeSameThread ? ["--no-resume-same-thread"] : []), ...(p.completedStep ? ["--completed-step", p.completedStep] : []), ...(p.nextStep ? ["--next-step", p.nextStep] : []),
      "--next-action", p.nextAction, ...(p.cleanupState ? ["--cleanup-state", p.cleanupState] : []), ...repeated("--cleanup-action", p.cleanupActions),
      ...repeated("--prohibited-claim", p.prohibitedClaims), ...(p.legacyV1 ? ["--legacy-v1"] : []), ...(p.output ? ["--output", p.output] : []), ...(p.force ? ["--force"] : [])],
  });
  registerCliTool(pi, {
    name: "bbk_handoff_verify", label: "BBK Handoff Verify", description: "Verify a sealed bbk.handoff.v2 package or consume-compatible bbk.handoff.v1 record.",
    parameters: z.object({ path: z.string(), root: text() }), argv: p => ["handoff", "verify", p.path, ...rootArgs(p.root)],
  });
  registerCliTool(pi, {
    name: "bbk_handoff_list", label: "BBK Handoff List", description: "List sealed v2 handoffs and legacy v1 handoffs without treating package internals as independent records.",
    parameters: z.object({ root: text(), workUnit: text(), latest: bool() }),
    argv: p => ["handoff", "list", ...rootArgs(p.root), ...(p.workUnit ? ["--work-unit", p.workUnit] : []), ...(p.latest ? ["--latest"] : [])],
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

  const bbkActivity = createBbkActivityHud(pi);
  const bbkMode = createBbkModeController(pi, (active, ctx) => bbkActivity.setMode(active, ctx));
  registerBbkEntrypoint(pi, bbkMode);
  registerModelRoutingCommand(pi);
  registerAgentViewCommand(pi, bbkActivity);
  registerBeadsCommand(pi);
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
  registerCommand(pi, "bbk:schema:list", "list known BBK schema and template kinds", ["schema", "list"]);
  registerCommand(pi, "bbk:schema:template", "--kind <kind> --output <path> [--subject-kind <kind> --depth compact|standard|full]", ["schema", "template"], { requireArgs: true });
  registerCommand(pi, "bbk:schema:enum", "--schema <kind-or-path> --pointer </json/pointer>", ["schema", "enum"], { requireArgs: true });
  registerCommand(pi, "bbk:schema:explain", "--schema <kind-or-path> --instance <path> [--pointer </json/pointer>]", ["schema", "explain"], { requireArgs: true });
  registerCommand(pi, "bbk:artifact:manifest", "[--root <path>] [--path <path>...] [--output <path>]", ["artifact", "manifest"]);
  registerCommand(pi, "bbk:artifact:preflight", "<draft-root> [--registry <path>] [--max-depth <n>]", ["artifact", "preflight"], { requireArgs: true });
  registerCommand(pi, "bbk:artifact:seal", "<draft-root> --output <new-package-dir> [--registry <path>]", ["artifact", "seal"], { requireArgs: true });
  registerCommand(pi, "bbk:artifact:verify", "<manifest-path> [--root <path>]", ["artifact", "verify"], { requireArgs: true });
  registerCommand(pi, "bbk:artifact:successor", "<sealed-package-dir> --output <draft-dir> --revision <revision> --reason <reason>", ["artifact", "successor"], { requireArgs: true });
  registerCommand(pi, "bbk:preflight", "<request-path> [--output <path>] [--no-cache]", ["preflight", "run"], { requireArgs: true });
  registerCommand(pi, "bbk:context:worker", "--work-unit <path> --profile-lock <path> --host-preflight <path> [options]", ["context", "worker"], { requireArgs: true });
  registerCommand(pi, "bbk:context:review", "--candidate <sealed-dir> --request <path> [options]", ["context", "review"], { requireArgs: true });
  registerCommand(pi, "bbk:handoff:create", "--work-unit <id> --disposition <value> --summary <text> --next-action <text> [options]", ["handoff", "create"], { requireArgs: true });
  registerCommand(pi, "bbk:handoff:verify", "<path> [--root <path>]", ["handoff", "verify"], { requireArgs: true });
  registerCommand(pi, "bbk:handoff:list", "[--work-unit <id>] [--latest]", ["handoff", "list"]);
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

  pi.on?.("before_agent_start", async (event, ctx) => bbkMode.promptReplacement(event, ctx));
  pi.on?.("before_provider_request", async (event, ctx) => bbkMode.verifyProviderPrompt(event, ctx));
  const restoreBbkMode = async (_event, ctx) => {
    bbkActivity.reset(ctx);
    const active = bbkMode.restore(ctx);
    if (_event?.type === "session_start") {
      ctx?.ui?.notify?.(`BBK ${version} loaded in ${ctx?.cwd || process.cwd()}${active ? "; BBK mode restored" : ""}`, "info");
    }
  };
  for (const eventName of ["session_start", "session_switch", "session_branch", "session_tree"]) {
    pi.on?.(eventName, restoreBbkMode);
  }
  pi.on?.("session_shutdown", async (_event, ctx) => bbkActivity.dispose(ctx));
  pi.on?.("tool_call", async event => {
    const encoded = JSON.stringify(event.input || {});
    if (["bash", "write", "edit"].includes(event.toolName) && protectedFragments.some(fragment => encoded.includes(fragment))) {
      return { block: true, reason: "BBK protects frozen candidates, attestations, gate receipts, review runs, findings, and dispositions. Create a successor or write an external annotation." };
    }
  });
}
