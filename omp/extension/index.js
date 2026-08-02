import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
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
let version = "0.1.0-alpha.13.1";
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
const BBK_MODE_SCHEMA = "bbk.omp-mode-state.v2";
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
    "semantic_state_name", "allowed_invocation_modes", "allowed_return_kinds",
    "allowed_operational_dispositions", "allowed_semantic_states",
    "supplemental_enums", "result_fields", "requirements",
    "readiness_rule", "authority_boundary",
  ];
  if (!contract || typeof contract !== "object" || Array.isArray(contract)) {
    throw new Error(`BBK role ${role?.name || "<unknown>"} has no exact return contract`);
  }
  const keys = Object.keys(contract).sort();
  if (keys.join("\n") !== [...required].sort().join("\n")) {
    throw new Error(`BBK role ${role.name} return contract fields are malformed`);
  }
  for (const key of ["contract_id", "envelope_schema", "return_schema", "result_schema", "semantic_state_name", "readiness_rule", "authority_boundary"]) {
    if (!isNonEmptyString(contract[key])) throw new Error(`BBK role ${role.name} return contract ${key} is invalid`);
  }
  const slug = role.name.replace(/^bbk_/, "").replaceAll("_", "-");
  if (!ROLE_RETURN_CONTRACT_RE.test(contract.contract_id)
    || contract.contract_id !== `bbk.${slug}-return.v1`) {
    throw new Error(`BBK role ${role.name} return contract ID is invalid`);
  }
  if (contract.envelope_schema !== "spec/schemas/bbk-role-return-v1.schema.json") {
    throw new Error(`BBK role ${role.name} does not use the current common return envelope`);
  }
  if (contract.return_schema !== `spec/schemas/role-returns/${role.name.replaceAll("_", "-")}-return-v1.schema.json`
    || contract.result_schema !== `spec/schemas/role-results/${role.name.replaceAll("_", "-")}-result-v1.schema.json`) {
    throw new Error(`BBK role ${role.name} return schema paths are invalid`);
  }
  for (const key of ["allowed_invocation_modes", "allowed_return_kinds", "allowed_operational_dispositions", "allowed_semantic_states", "requirements"]) {
    if (!isUniqueStringArray(contract[key])) throw new Error(`BBK role ${role.name} return contract ${key} is invalid`);
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
  return contract;
}
function exactRoleReturnContractBlock(role, catalogueEntry) {
  const contract = validateRoleReturnContract(role, catalogueEntry);
  const fieldLines = Object.entries(contract.result_fields).map(([name, field]) => {
    const enumPart = Array.isArray(field.enum_values) ? `; enum=${field.enum_values.join("|")}` : "";
    return `- ${name}: kind=${field.kind}; nullable=${field.nullable}${enumPart}; ${field.description}`;
  });
  return [
    `<bbk-exact-role-return-contract role="${role.name}">`,
    "Return one JSON object. The full role schema is controlling; conversational prose is not a substitute.",
    `schema: bbk.role-return.v1`,
    `contract: ${contract.contract_id}`,
    `envelope_schema: ${contract.envelope_schema}`,
    `return_schema: ${contract.return_schema}`,
    `result_schema: ${contract.result_schema}`,
    `role: ${role.name}`,
    `invocation_mode: ${contract.allowed_invocation_modes.join(" | ")}`,
    `return_kind: ${contract.allowed_return_kinds.join(" | ")}`,
    `operational_disposition: ${contract.allowed_operational_dispositions.join(" | ")}`,
    `semantic_state.name: ${contract.semantic_state_name}`,
    `semantic_state.value: ${contract.allowed_semantic_states.join(" | ")}`,
    "required_envelope_fields: schema, contract, role, invocation_mode, return_kind, subject_ref, parent_ref, attempt_ref, operational_disposition, semantic_state, summary, authority_and_effects_used, result, durable_handoff_refs, smallest_valid_next_action",
    "required_result_fields:",
    ...fieldLines,
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
    "2. If the user message answers, corrects, steers, cancels, or authorizes an existing BBK request, relay it through `hub` to the exact requesting peer or active logical root, preserving the request/message ID with `replyTo` when available. Do not launch a duplicate root.",
    "3. Otherwise select exactly one canonical root: no accepted baseline, planning, architecture, design, ambiguity, or material uncertainty -> `bbk_root_wayfinder`; accepted-baseline execution or recovery -> `bbk_root_orchestrator`; bounded independent review -> `bbk_reviewer`; assertion-scoped candidate acceptance -> `bbk_validator_orchestrator`.",
    "4. Invoke that named agent with OMP `task`, preferably as a background/non-blocking job so Main remains available for user relay. When OMP advertises the batch form, use `{ context, tasks: [{ name, agent, task, ... }] }` even for one root: `agent` is the exact canonical `bbk_*` role, `name` is a stable IRC/job identifier, and `task` is the complete self-contained assignment. Never put the role name only in `name` while omitting `agent`. If OMP advertises only a flat form, follow that schema and carry reusable shared background through a durable `local://` context file. Supply exact subject, desired result, bounded context, authority and standing approvals, allowed effects, capability zones, assurance obligations, stopping conditions, logical parent, Main peer ID, branch/request IDs, and return envelope.",
    "5. Before dispatch, perform only bounded controller operations required to recover state and compile the invocation. Do not select architecture, write the operating plan, edit subject files, execute product work, review, validate, or certify in Main.",
    "6. Supervise through task state and `hub`. Continue useful controller work and wait only when no other valid action remains. Resume or message the same logical child when possible instead of restarting discovery.",
    "",
    "## Human-request relay",
    "",
    "- A child needing a material decision, authority grant, private context, protected-floor exception, hard-to-reverse commitment, or explicit acceptance sends Main one compact `BBK_USER_REQUEST` over `hub`/IRC. It must include a stable request ID, the smallest material question, recommendation, credible alternatives, consequences, residual uncertainty, blocking state, and durable packet reference.",
    "- Use OMP's native `ask` tool for every user-facing question or decision request. Do not put a question in ordinary assistant prose and wait for an answer. Anything phrased as a question outside an `ask` tool call is informational text only: it is not a pending BBK question, does not establish a decision surface, and must not be treated as answered.",
    "- Translate the child's packet into the smallest adequate `ask` interaction, preserving its request ID and recommendation. Do not answer on the user's behalf or substitute your own design judgment.",
    "- Only a structured answer returned by `ask` is eligible to become an ADR-compatible accepted decision. Relay it immediately to the exact requesting peer as `BBK_USER_RESPONSE`, with the matching request ID and `source: omp.ask`, and notify its integrating parent when required. Main never authors the ADR; the responsible canonical role records the decision and continues its branch.",
    "- Ordinary user prose may steer, correct, cancel, or grant operational authority, but it is not an answer to an unissued prose question and must not be converted into an ADR. When durable decision authority is required, obtain or confirm it through `ask` first. Silence, timeout, cancellation, `Chat about this`, a send receipt, or anticipated answers are not acceptance.",
    "- Keep IRC concise and plain prose. Large or authority-bearing material belongs in a durable handoff; relay path, bytes, SHA-256, disposition, and smallest next action.",
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

  function clearWidget() {
    try { currentCtx?.ui?.setWidget?.(BBK_ACTIVITY_WIDGET_KEY, undefined, { placement: "aboveEditor" }); }
    catch {}
  }
  function activeAgents() {
    return [...agents.values()].filter(item => ["pending", "running"].includes(item.progress?.status));
  }
  function render() {
    if (!enabled || !currentCtx?.ui?.setWidget) {
      clearWidget();
      return;
    }
    const active = activeAgents().sort((a, b) => b.updated - a.updated);
    if (!active.length) {
      currentCtx.ui.setWidget(
        BBK_ACTIVITY_WIDGET_KEY,
        ["BBK · ready"],
        { placement: "aboveEditor" },
      );
      return;
    }
    const latest = active[0];
    const name = oneLine(latest.progress?.id || latest.id || latest.description || roleDisplayName(latest.agent), 42);
    const gauge = contextGauge(latest.progress);
    const activity = progressActivity(latest.progress);
    let line = `BBK · ${name}${gauge ? ` [${gauge}]` : ""}: ${activity}`;

    const otherGauges = active.slice(1, 4).map(item => {
      const otherName = oneLine(item.progress?.id || item.id || roleDisplayName(item.agent), 28);
      const otherGauge = contextGauge(item.progress, { short: true });
      return otherGauge ? `${otherName} ${otherGauge}` : otherName;
    });
    if (otherGauges.length) line += ` | ${otherGauges.join(" · ")}`;
    if (active.length > 4) line += ` · +${active.length - 4} workers`;
    currentCtx.ui.setWidget(BBK_ACTIVITY_WIDGET_KEY, [oneLine(line, 220)], { placement: "aboveEditor" });
  }
  function setMode(next, ctx) {
    enabled = Boolean(next);
    currentCtx = ctx || currentCtx;
    if (!enabled) agents.clear();
    render();
  }
  function reset(ctx) {
    currentCtx = ctx || currentCtx;
    agents.clear();
    render();
  }
  function updateProgress(payload) {
    if (!payload || !BBK_ROLE_NAME_RE.test(String(payload.agent || payload.progress?.agent || ""))) return;
    const progress = payload.progress && typeof payload.progress === "object" ? payload.progress : {};
    const id = String(progress.id || payload.id || payload.description || payload.agent || `bbk-worker-${sequence + 1}`);
    agents.set(id, {
      id,
      agent: String(payload.agent || progress.agent || ""),
      description: payload.description,
      progress: { ...progress, id, agent: payload.agent || progress.agent },
      updated: ++sequence,
    });
    render();
  }
  function updateLifecycle(payload) {
    if (!payload || !BBK_ROLE_NAME_RE.test(String(payload.agent || ""))) return;
    const id = String(payload.id || payload.description || payload.agent);
    if (payload.status === "started") {
      const previous = agents.get(id);
      agents.set(id, {
        id,
        agent: String(payload.agent || ""),
        description: payload.description,
        progress: {
          ...(previous?.progress || {}),
          id,
          agent: payload.agent,
          status: previous?.progress?.status === "running" ? "running" : "pending",
        },
        updated: ++sequence,
      });
    } else {
      agents.delete(id);
    }
    render();
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
    clearWidget();
    for (const stop of unsubscribe.splice(0)) {
      try { stop(); } catch {}
    }
  }
  return { setMode, reset, updateProgress, updateLifecycle, dispose };
}

function createBbkModeController(pi, onStateChange = () => {}) {
  let enabled = false;
  let loaded = false;

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
    try {
      const extracted = extractBbkAgentBlock(event);
      if (extracted?.alreadyReplaced) return { systemPrompt: systemPromptBlocks(event) };
      if (extracted) return { systemPrompt: [buildAgentSystemPrompt(extracted, ctx)] };
      ensure(ctx);
      if (!enabled) return undefined;
      return { systemPrompt: [buildControllerSystemPrompt(ctx)] };
    } catch (error) {
      return { systemPrompt: [failClosedSystemPrompt(error, ctx)] };
    }
  }
  return { enter, exit, restore, ensure, promptReplacement, isEnabled: () => enabled };
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

  const bbkActivity = createBbkActivityHud(pi);
  const bbkMode = createBbkModeController(pi, (active, ctx) => bbkActivity.setMode(active, ctx));
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

  pi.on?.("before_agent_start", async (event, ctx) => bbkMode.promptReplacement(event, ctx));
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
