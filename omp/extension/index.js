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
const adjacentGovernanceRegistry = path.join(extensionDir, "omp_binding_registry.py");
const sourceGovernanceRegistry = path.join(sourceRoot, "tools", "omp_binding_registry.py");
const governanceRegistryPath = process.env.BBK_OMP_BINDING_REGISTRY_CLI || (() => {
  try { readFileSync(adjacentGovernanceRegistry); return adjacentGovernanceRegistry; }
  catch { return sourceGovernanceRegistry; }
})();
const adjacentGovernedFilesystem = path.join(extensionDir, "governed_filesystem.py");
const sourceGovernedFilesystem = path.join(sourceRoot, "tools", "governed_filesystem.py");
const governedFilesystemPath = process.env.BBK_GOVERNED_FILESYSTEM_CLI || (() => {
  try { readFileSync(adjacentGovernedFilesystem); return adjacentGovernedFilesystem; }
  catch { return sourceGovernedFilesystem; }
})();
const adjacentWorkerSpawn = path.join(extensionDir, "worker_spawn.py");
const sourceWorkerSpawn = path.join(sourceRoot, "tools", "worker_spawn.py");
const workerSpawnPath = process.env.BBK_WORKER_SPAWN_CLI || (() => {
  try { readFileSync(adjacentWorkerSpawn); return adjacentWorkerSpawn; }
  catch { return sourceWorkerSpawn; }
})();
const adjacentControlPlane = path.join(extensionDir, "control_plane.py");
const sourceControlPlane = path.join(sourceRoot, "tools", "control_plane.py");
const controlPlanePath = process.env.BBK_CONTROL_PLANE_CLI || (() => {
  try { readFileSync(adjacentControlPlane); return adjacentControlPlane; }
  catch { return sourceControlPlane; }
})();
const adjacentGovernanceStatus = path.join(extensionDir, "governance_status.py");
const sourceGovernanceStatus = path.join(sourceRoot, "tools", "governance_status.py");
const governanceStatusPath = process.env.BBK_GOVERNANCE_STATUS_CLI || (() => {
  try { readFileSync(adjacentGovernanceStatus); return adjacentGovernanceStatus; }
  catch { return sourceGovernanceStatus; }
})();
const adjacentReadOnlySpawn = path.join(extensionDir, "read_only_spawn.py");
const sourceReadOnlySpawn = path.join(sourceRoot, "tools", "read_only_spawn.py");
const readOnlySpawnPath = process.env.BBK_READ_ONLY_SPAWN_CLI || (() => {
  try { readFileSync(adjacentReadOnlySpawn); return adjacentReadOnlySpawn; }
  catch { return sourceReadOnlySpawn; }
})();
const adjacentQualifiedTask = path.join(extensionDir, "qualified_task.py");
const sourceQualifiedTask = path.join(sourceRoot, "tools", "qualified_task.py");
const qualifiedTaskPath = process.env.BBK_QUALIFIED_TASK_CLI || (() => {
  try { readFileSync(adjacentQualifiedTask); return adjacentQualifiedTask; }
  catch { return sourceQualifiedTask; }
})();
const adjacentRoleReturnRuntime = path.join(extensionDir, "role_return_runtime.py");
const sourceRoleReturnRuntime = path.join(sourceRoot, "tools", "role_return_runtime.py");
const roleReturnRuntimePath = process.env.BBK_ROLE_RETURN_RUNTIME_CLI || (() => {
  try { readFileSync(adjacentRoleReturnRuntime); return adjacentRoleReturnRuntime; }
  catch { return sourceRoleReturnRuntime; }
})();
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
let version = "0.1.0-alpha.17.0.2.1";
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
function runJsonScript(script, args, cwd, signal, extraEnvironment = {}, stdinValue = null) {
  return new Promise(resolve => {
    const child = spawn(pythonCommand(), [...scriptPrefix(script), ...args], {
      cwd,
      env: pythonUtf8Environment({ BBK_PACKAGE_ROOT: packageRoot, ...extraEnvironment }),
      windowsHide: true,
      stdio: [stdinValue === null ? "ignore" : "pipe", "pipe", "pipe"],
    });
    const stdoutChunks = [], stderrChunks = [];
    child.stdout.on("data", chunk => { stdoutChunks.push(Buffer.from(chunk)); });
    child.stderr.on("data", chunk => { stderrChunks.push(Buffer.from(chunk)); });
    const abort = () => child.kill("SIGTERM");
    signal?.addEventListener?.("abort", abort, { once: true });
    child.on("error", error => resolve({
      code: 2,
      details: { status: "ERROR", reason_code: "BBK_SCRIPT_START_FAILED", message: String(error?.message || error) },
      stdout: "",
      stderr: "",
    }));
    if (stdinValue !== null) {
      child.stdin.on("error", () => {});
      child.stdin.end(typeof stdinValue === "string" ? stdinValue : JSON.stringify(stdinValue));
    }
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
      catch { details = { status: "ERROR", stdout, stderr, parseError: "BBK governed runtime did not return JSON" }; }
      if (stderr.trim()) details.stderr = stderr;
      resolve({ code, details, stdout, stderr });
    });
  });
}
function runGovernanceRegistry(args, projectRoot, signal) {
  return runJsonScript(
    governanceRegistryPath,
    ["--root", projectRoot, ...args],
    projectRoot,
    signal,
    { BBK_PROJECT_ROOT: projectRoot },
  );
}
function runGovernedFilesystem(request, projectRoot, signal) {
  return runJsonScript(
    governedFilesystemPath,
    ["--root", projectRoot, "execute", "--request", "-"],
    projectRoot,
    signal,
    { BBK_PROJECT_ROOT: projectRoot },
    request,
  );
}
function runWorkerSpawn(request, projectRoot, signal) {
  return runJsonScript(
    workerSpawnPath,
    ["--root", projectRoot, "compile", "--request", "-"],
    projectRoot,
    signal,
    { BBK_PROJECT_ROOT: projectRoot },
    request,
  );
}
function runControlPlane(request, projectRoot, signal) {
  return runJsonScript(
    controlPlanePath,
    ["--root", projectRoot, "execute", "--request", "-"],
    projectRoot,
    signal,
    { BBK_PROJECT_ROOT: projectRoot },
    request,
  );
}
function runGovernanceStatus(request, projectRoot, signal) {
  return runJsonScript(
    governanceStatusPath,
    ["--root", projectRoot, "status", "--request", "-"],
    projectRoot,
    signal,
    { BBK_PROJECT_ROOT: projectRoot },
    request,
  );
}
function runReadOnlySpawn(request, projectRoot, signal) {
  return runJsonScript(
    readOnlySpawnPath,
    ["--root", projectRoot, "compile", "--request", "-"],
    projectRoot,
    signal,
    { BBK_PROJECT_ROOT: projectRoot },
    request,
  );
}
function runQualifiedTask(request, projectRoot, signal) {
  return runJsonScript(
    qualifiedTaskPath,
    ["--root", projectRoot, "execute", "--request", "-"],
    projectRoot,
    signal,
    { BBK_PROJECT_ROOT: projectRoot },
    request,
  );
}
function runRoleReturn(command, request, projectRoot, signal) {
  return runJsonScript(
    roleReturnRuntimePath,
    ["--root", projectRoot, "--package-root", packageRoot, command, "--request", "-"],
    projectRoot,
    signal,
    { BBK_PROJECT_ROOT: projectRoot, BBK_PACKAGE_ROOT: packageRoot },
    request,
  );
}
function canonicalJsonValue(value) {
  if (Array.isArray(value)) return value.map(canonicalJsonValue);
  if (value && typeof value === "object") {
    const result = {};
    for (const key of Object.keys(value).sort()) {
      if (value[key] !== undefined) result[key] = canonicalJsonValue(value[key]);
    }
    return result;
  }
  return value;
}
function governedPayloadDigest(value) {
  const normalized = canonicalJsonValue(JSON.parse(JSON.stringify(value ?? {})));
  return `sha256:${createHash("sha256").update(JSON.stringify(normalized), "utf8").digest("hex")}`;
}
function canonicalDispatchEnvelope(input) {
  const value = input && typeof input === "object" && !Array.isArray(input) ? input : {};
  const tasks = Array.isArray(value.tasks) ? value.tasks : [];
  if (tasks.length !== 1 || !tasks[0] || typeof tasks[0] !== "object" || Array.isArray(tasks[0])) return null;
  const context = String(value.context || "").trim();
  const task = String(tasks[0].task || "").trim();
  const pattern = /^<bbk-spawn-dispatch ref="(dispatch:[0-9a-f]{64})"\/>$/;
  const contextMatch = pattern.exec(context);
  const taskMatch = pattern.exec(task);
  if (!contextMatch || !taskMatch || contextMatch[1] !== taskMatch[1]) return null;
  return {
    context,
    tasks: [{
      agent: String(tasks[0].agent || "").trim(),
      name: String(tasks[0].name || "").trim(),
      task,
    }],
  };
}
const governedDispatchLeases = new Map();
const governedActivatedDispatches = new Map();
async function releaseGovernedDispatchLease(toolCallId, reason, signal) {
  const callId = String(toolCallId || "").trim();
  const active = governedDispatchLeases.get(callId);
  if (!callId || !active) return null;
  governedDispatchLeases.delete(callId);
  return runGovernanceRegistry([
    "release-dispatch",
    "--dispatch-ref", active.dispatchRef,
    "--tool-call-id", callId,
    "--reason", String(reason || "HOST_TASK_LAUNCH_FAILED").slice(0, 256),
    "--observed-at", new Date().toISOString(),
  ], active.projectRoot, signal);
}
async function terminalizeGovernedDispatch(event, ctx) {
  const sessionId = hostSessionIdentity(ctx);
  const active = governedActivatedDispatches.get(sessionId);
  if (!sessionId || !active) return null;
  governedActivatedDispatches.delete(sessionId);
  const failed = Boolean(
    event?.isError || event?.error || event?.result?.isError
    || ["error", "failed"].includes(String(event?.status || "").toLowerCase()),
  );
  const cancelled = String(event?.status || "").toLowerCase() === "cancelled";
  return runGovernanceRegistry([
    "terminal-dispatch",
    "--dispatch-ref", active.dispatchRef,
    "--actual-session-id", sessionId,
    "--outcome", cancelled ? "CANCELLED" : failed ? "FAILED" : "COMPLETED",
    "--reason", failed ? "OMP_CHILD_AGENT_END_FAILED" : cancelled ? "OMP_CHILD_AGENT_END_CANCELLED" : "OMP_CHILD_AGENT_END_COMPLETED",
    "--observed-at", new Date().toISOString(),
  ], active.projectRoot);
}
function governedProfileEnabled() {
  return String(process.env.BBK_GOVERNED_PROFILE || "").trim() === "governed-software";
}
function governedProjectRoot() {
  const explicit = String(process.env.BBK_PROJECT_ROOT || "").trim();
  if (explicit) return path.resolve(explicit);
  if (loadedBinding?.scope === "project" && loadedBinding?.projectRoot) return path.resolve(loadedBinding.projectRoot);
  return null;
}
function governedHostVersion() {
  return String(process.env.BBK_OMP_HOST_VERSION || "omp/unknown").trim() || "omp/unknown";
}
function hostSessionIdentity(ctx) {
  const value = promptSessionIdentity(ctx);
  return String(value || "").startsWith("cwd:") ? null : String(value || "");
}
function governedBlock(reasonCode, message, smallestNextAction = "Use a typed governed tool with a complete active binding.") {
  return {
    block: true,
    reason: `${reasonCode}: ${message} Next: ${smallestNextAction}`,
    details: {
      schema: "bbk.governed-tool-block.v1",
      status: "BLOCK",
      reason_code: reasonCode,
      message,
      smallest_next_action: smallestNextAction,
    },
  };
}
async function recordGovernedHostDecision(event, ctx, { eventType = "TOOL_CALL", postEffect = false, bindingRef = null } = {}) {
  const projectRoot = governedProjectRoot();
  const sessionId = hostSessionIdentity(ctx);
  if (!projectRoot || !sessionId) return null;
  const toolCallId = String(event?.toolCallId || event?.tool_call_id || event?.id || event?.toolName || "tool-call");
  const envelope = {
    host_version: governedHostVersion(),
    event_type: eventType,
    session_id: sessionId,
    parent_session: String(event?.parentSessionId || event?.parent_session_id || ""),
    task_or_tool_id: toolCallId,
    payload_digest: governedPayloadDigest(event?.input || {}),
    observed_at: new Date().toISOString(),
  };
  const args = ["record-host-event", "--event", JSON.stringify(envelope)];
  if (bindingRef) args.push("--binding-ref", bindingRef);
  if (postEffect) args.push("--post-effect");
  return runGovernanceRegistry(args, projectRoot);
}
async function admitGovernedTask(event, ctx) {
  const projectRoot = governedProjectRoot();
  if (!projectRoot) {
    return governedBlock(
      "GOVERNED_PROJECT_ROOT_REQUIRED",
      "governed mode has no explicit BBK_PROJECT_ROOT or project-scoped package binding; CWD is not accepted as authority",
      "Bind the exact project root and retry the spawn.",
    );
  }
  const sessionId = hostSessionIdentity(ctx);
  if (!sessionId) {
    return governedBlock(
      "OMP_PARENT_SESSION_REQUIRED",
      "OMP did not expose a stable parent session identity; CWD fallback is not accepted",
      "Use a qualified OMP host/session surface or mark the host unqualified.",
    );
  }
  const input = event?.input && typeof event.input === "object" ? event.input : {};
  const compactEnvelope = canonicalDispatchEnvelope(input);
  const compactDispatchRef = compactEnvelope
    ? /^<bbk-spawn-dispatch ref="(dispatch:[0-9a-f]{64})"\/>$/.exec(compactEnvelope.context)?.[1] || null
    : null;
  if (compactDispatchRef) {
    const toolCallId = String(event?.toolCallId || event?.tool_call_id || event?.id || "").trim();
    if (!toolCallId) {
      return governedBlock(
        "OMP_SPAWN_IDENTITY_INCOMPLETE",
        "compact dispatch lacks a stable OMP tool-call identity",
        "Invoke the exact dispatch_input returned by bbk_control_spawn or bbk_control_bind.",
      );
    }
    const taskItem = compactEnvelope.tasks[0];
    const value = await runGovernanceRegistry([
      "admit-dispatch",
      "--dispatch-ref", compactDispatchRef,
      "--dispatch-envelope-digest", governedPayloadDigest(compactEnvelope),
      "--parent-session-id", sessionId,
      "--task-name", taskItem.name,
      "--agent", taskItem.agent,
      "--tool-call-id", toolCallId,
      "--host-version", governedHostVersion(),
      "--observed-at", new Date().toISOString(),
    ], projectRoot);
    if (value.code !== 0 || value.details?.status !== "ADMITTED") {
      return governedBlock(
        value.details?.reason_code || "OMP_SPAWN_DISPATCH_REQUIRED",
        value.details?.message || "the compact dispatch does not identify one current immutable spawn reservation",
        value.details?.smallest_next_action || "Use the current dispatch_input returned by BBK without alteration.",
      );
    }
    if (value.details?.enforcement_boundary !== "ENFORCED") {
      return governedBlock(
        "OMP_HOST_UNQUALIFIED_FOR_SPAWN",
        `dispatch reservation matched but host boundary is ${String(value.details?.enforcement_boundary || "UNQUALIFIED")}`,
        "Use the qualified OMP 16.4.8 host or re-qualify the changed host.",
      );
    }
    governedDispatchLeases.set(toolCallId, { dispatchRef: compactDispatchRef, projectRoot });
    const resolved = value.details?.resolved_task_input;
    if (!resolved || typeof resolved !== "object" || Array.isArray(resolved)
      || governedPayloadDigest(resolved) !== value.details?.resolved_task_input_digest) {
      await releaseGovernedDispatchLease(toolCallId, "OMP_SPAWN_DISPATCH_PAYLOAD_INVALID");
      return governedBlock(
        "OMP_SPAWN_DISPATCH_PAYLOAD_INVALID",
        "the immutable dispatch payload was absent or failed its exact digest check",
        "Recompile the bound spawn; do not emulate it with eval, shell, Python, or free-form task input.",
      );
    }
    // OMP 16.4.8 accepts a replacement `input` from the pre-effect tool_call
    // hook. Mutate the observed object as a compatibility belt, and return the
    // replacement explicitly so the built-in task tool receives exactly the
    // payload whose digest was admitted.
    try {
      for (const key of Object.keys(input)) delete input[key];
      Object.assign(input, resolved);
      event.input = input;
    } catch (error) {
      await releaseGovernedDispatchLease(toolCallId, "OMP_SPAWN_DISPATCH_REWRITE_FAILED");
      return governedBlock(
        "OMP_SPAWN_DISPATCH_REWRITE_FAILED",
        `OMP did not expose a mutable pre-effect task payload: ${String(error?.message || error)}`,
        "Preserve the failure and re-qualify the host bridge; do not use generic eval as a fallback.",
      );
    }
    return { input: resolved };
  }
  let taskIdentity = input;
  if (Array.isArray(input.tasks)) {
    if (input.tasks.length !== 1) {
      return governedBlock(
        "OMP_BOUND_SPAWN_BATCH_CARDINALITY",
        `bound writable spawn requires exactly one independently reserved task item; received ${input.tasks.length}`,
        "Compile and invoke one bbk_control_spawn result per writable child.",
      );
    }
    if (!String(input.context || "").trim()) {
      return governedBlock(
        "OMP_BOUND_SPAWN_CONTEXT_REQUIRED",
        "OMP batch task input lacks the authenticated worker-packet context",
        "Invoke the exact dispatch_input returned by bbk_control_spawn without alteration.",
      );
    }
    taskIdentity = input.tasks[0] && typeof input.tasks[0] === "object" ? input.tasks[0] : {};
  }
  const taskName = String(taskIdentity.name || taskIdentity.taskName || taskIdentity.task_name || "").trim();
  const agent = String(taskIdentity.agent || taskIdentity.role || "").trim();
  const toolCallId = String(event?.toolCallId || event?.tool_call_id || event?.id || "").trim();
  if (!taskName || !agent || !toolCallId) {
    return governedBlock(
      "OMP_SPAWN_IDENTITY_INCOMPLETE",
      "task spawn lacks exact name, agent, or tool-call identity",
      "Invoke the bound task tool with the exact reserved name, role, and host call identity.",
    );
  }
  const value = await runGovernanceRegistry([
    "admit-spawn",
    "--input-digest", governedPayloadDigest(input),
    "--parent-session-id", sessionId,
    "--task-name", taskName,
    "--agent", agent,
    "--tool-call-id", toolCallId,
    "--host-version", governedHostVersion(),
  ], projectRoot);
  if (value.code !== 0 || value.details?.status !== "ADMITTED") {
    return governedBlock(
      value.details?.reason_code || "OMP_SPAWN_BINDING_REQUIRED",
      value.details?.message || "the task call has no exact active spawn reservation",
      value.details?.smallest_next_action || "Create a complete bound spawn reservation before invoking task.",
    );
  }
  if (value.details?.enforcement_boundary !== "ENFORCED") {
    return governedBlock(
      "OMP_HOST_UNQUALIFIED_FOR_SPAWN",
      `spawn reservation matched but host boundary is ${String(value.details?.enforcement_boundary || "UNQUALIFIED")}`,
      "Use the qualified OMP 16.4.8 host or re-qualify the changed host before writable execution.",
    );
  }
  return undefined;
}
async function guardStructuredReturnTransport(event, ctx) {
  const toolName = String(event?.toolName || event?.tool_name || "").trim().toLowerCase();
  if (toolName !== "bbk_handoff_create" || !governedProfileEnabled()) return undefined;
  const projectRoot = governedProjectRoot();
  const sessionId = hostSessionIdentity(ctx);
  if (!projectRoot || !sessionId) return undefined;
  const value = await runGovernanceRegistry([
    "binding-policy",
    "--session-id", sessionId,
  ], projectRoot);
  // Let the handoff tool's ordinary capability checks handle sessions that are
  // not governed children. A current governed child policy, however, is a
  // deterministic pre-effect transport fence.
  if (value.code !== 0 || value.details?.status !== "PASS") return undefined;
  const mode = String(value.details?.return_transport_mode || "STRUCTURED_RETURN_FIRST");
  if (mode === "STRUCTURED_RETURN_ONLY") {
    return governedBlock(
      "BBK_STRUCTURED_RETURN_ONLY",
      `binding ${String(value.details?.binding_ref || "unknown")} requires the structured role return and forbids manufacturing a sealed handoff package`,
      "Return the exact schema-valid role result through the OMP task-result channel.",
    );
  }
  if (mode === "STRUCTURED_RETURN_FIRST" && !String(value.details?.material_transport_reason || "").trim()) {
    return governedBlock(
      "BBK_MATERIAL_TRANSPORT_REASON_REQUIRED",
      "structured-return-first binding has no recorded material reason for durable exact transport",
      "Use the structured role return, or compile a successor binding with a named large/binary/truncation/recovery/schema transport requirement.",
    );
  }
  return undefined;
}


function boundWorkerMarker(event, _ctx) {
  // Ordinary BBK child prompt replacement also parses the canonical role
  // wrapper, including deliberately malformed fixtures that must be converted
  // into a prompt-assembly failure.  Spawn activation is an additional path,
  // not a second unconditional parser: only enter it when the host-supplied
  // invocation block actually carries a bound-worker marker.  Once a marker is
  // present, extractBbkAgentBlock remains strict so a forged/tampered role
  // wrapper fails closed before the first provider turn.
  const blocks = systemPromptBlocks(event);
  if (!blocks.some(block => block.includes("<bbk-bound-worker-packet "))) return null;
  const agent = extractBbkAgentBlock(event);
  if (!agent || agent.alreadyReplaced) return null;
  const context = String(agent.invocation?.context || "").replace(/\r\n?/g, "\n");
  const firstLine = context.split("\n", 1)[0];
  const pattern = /^<bbk-bound-worker-packet planned-binding-ref="([A-Za-z0-9._:/@+\-]+)" packet-digest="(sha256:[0-9a-f]{64})">(?:\r?\n|$)/;
  const match = pattern.exec(`${firstLine}\n`);
  return match ? { plannedBindingRef: match[1], packetDigest: match[2] } : null;
}
async function activateBoundWorker(event, ctx, pi) {
  const marker = boundWorkerMarker(event, ctx);
  if (!marker) return null;
  if (!governedProfileEnabled()) {
    const error = new Error("GOVERNED_PROFILE_REQUIRED: bound worker packet cannot start outside governed-software mode");
    error.code = "GOVERNED_PROFILE_REQUIRED";
    throw error;
  }
  const projectRoot = governedProjectRoot();
  const sessionId = hostSessionIdentity(ctx);
  if (!projectRoot || !sessionId) {
    const error = new Error("OMP_CHILD_BINDING_IDENTITY_REQUIRED: project root and actual child session are required; CWD is not authority");
    error.code = "OMP_CHILD_BINDING_IDENTITY_REQUIRED";
    throw error;
  }
  const value = await runGovernanceRegistry([
    "activate-spawn",
    "--planned-binding-ref", marker.plannedBindingRef,
    "--actual-session-id", sessionId,
    "--packet-digest", marker.packetDigest,
    "--host-version", governedHostVersion(),
    "--observed-at", new Date().toISOString(),
  ], projectRoot);
  if (value.code !== 0 || value.details?.status !== "ACTIVATED") {
    const reason = value.details?.reason_code || "OMP_SPAWN_ACTIVATION_FAILED";
    const error = new Error(`${reason}: ${value.details?.message || "bound child activation failed"}`);
    error.code = reason;
    error.details = value.details;
    throw error;
  }
  const activated = value.details;
  if (activated?.tool_call_id) governedDispatchLeases.delete(String(activated.tool_call_id));
  if (activated?.dispatch_ref && activated?.actual_session_id) {
    governedActivatedDispatches.set(String(activated.actual_session_id), {
      dispatchRef: String(activated.dispatch_ref),
      projectRoot,
    });
  }
  if (typeof pi?.appendEntry === "function") pi.appendEntry("bbk-spawn-activation", activated);
  return activated;
}
function governedToolError(reasonCode, message, smallestNextAction, extraDetails = undefined) {
  const details = {
    schema: "bbk.governed-tool-result.v1",
    status: "BLOCK",
    reason_code: reasonCode,
    message,
    smallest_next_action: smallestNextAction || "Correct the active binding or typed request and retry.",
  };
  if (extraDetails && typeof extraDetails === "object" && !Array.isArray(extraDetails)) {
    for (const [key, value] of Object.entries(extraDetails)) {
      if (value !== undefined && !Object.hasOwn(details, key)) details[key] = value;
    }
  }
  return {
    content: [{ type: "text", text: JSON.stringify(details, null, 2) }],
    details,
    isError: true,
  };
}
async function executeGovernanceStatusTool(_toolCallId, params, signal, ctx) {
  if (!governedProfileEnabled()) {
    return governedToolError(
      "GOVERNED_PROFILE_REQUIRED",
      "bbk_governance_status is available only in governed-software mode",
      "Enable governed-software mode and use the current active binding.",
    );
  }
  const projectRoot = governedProjectRoot();
  const sessionId = hostSessionIdentity(ctx);
  if (!projectRoot || !sessionId) {
    return governedToolError(
      "GOVERNANCE_STATUS_IDENTITY_REQUIRED",
      "explicit BBK project root and stable OMP session identity are required; CWD is not authority",
      "Bind the project and invoke status from a qualified OMP session.",
    );
  }
  const request = {
    schema: "bbk.governance-status-query.v1",
    host_version: governedHostVersion(),
    session_id: sessionId,
    invocation_id: String(params.invocationId || "").trim(),
    binding_ref: String(params.bindingRef || "").trim(),
  };
  const value = await runGovernanceStatus(request, projectRoot, signal);
  if (value.code !== 0 || value.details?.status !== "PASS") {
    return governedToolError(
      value.details?.reason_code || "GOVERNANCE_STATUS_FAILED",
      value.details?.message || "governance status could not be correlated to an active binding",
      value.details?.smallest_next_action || "Use the current active binding and retry.",
    );
  }
  return result(value);
}
async function executeControlBindTool(toolCallId, params, signal, ctx) {
  if (!governedProfileEnabled()) {
    return governedToolError(
      "GOVERNED_PROFILE_REQUIRED",
      "bbk_control_bind is available only in governed-software mode",
      "Enable governed-software mode before binding a read-only child.",
    );
  }
  const projectRoot = governedProjectRoot();
  const parentSessionId = hostSessionIdentity(ctx);
  if (!projectRoot || !parentSessionId) {
    return governedToolError(
      "CONTROL_BIND_PARENT_IDENTITY_REQUIRED",
      "explicit BBK project root and stable OMP parent session are required; CWD is not authority",
      "Bind the project and use the qualified OMP session surface.",
    );
  }
  if (governedHostVersion() !== "omp/16.4.8") {
    return governedToolError(
      "OMP_HOST_UNQUALIFIED_FOR_CONTROL_BIND",
      `host ${governedHostVersion()} is not qualified for read-only child binding`,
      "Use OMP 16.4.8 or re-qualify the changed host.",
    );
  }
  const parentBindingRef = String(params.parentBindingRef || "").trim();
  const hostReceipt = await recordGovernedHostDecision(
    { toolName: "bbk_control_bind", toolCallId, input: params },
    ctx,
    { bindingRef: parentBindingRef },
  );
  if (!hostReceipt || hostReceipt.code !== 0) {
    return governedToolError(
      hostReceipt?.details?.reason_code || "OMP_HOST_EVENT_RECEIPT_FAILED",
      hostReceipt?.details?.message || "the read-only binding host event could not be correlated",
      hostReceipt?.details?.smallest_next_action || "Repair the parent binding before retrying.",
    );
  }
  const request = {
    schema: "bbk.bound-read-only-task-create.v1",
    host_version: governedHostVersion(),
    parent_binding_ref: parentBindingRef,
    parent_session_id: parentSessionId,
    parent_invocation_id: String(params.parentInvocationId || "").trim(),
    task_name: String(params.taskName || "").trim(),
    role: String(params.role || "").trim(),
    work_unit_id: String(params.workUnitId || "").trim(),
    attempt_id: String(params.attemptId || "").trim(),
    baseline_ref: String(params.baselineRef || "").trim(),
    candidate_id: String(params.candidateId || "").trim(),
    candidate_admission_ref: String(params.candidateAdmissionRef || "").trim() || undefined,
    authority_ref: String(params.authorityRef || "").trim(),
    return_contract: String(params.returnContract || "").trim(),
    workspace_ref: String(params.workspaceRef || "").trim(),
    path_prefixes: Array.isArray(params.pathPrefixes) ? params.pathPrefixes.map(String) : [],
    semantic_scope: Array.isArray(params.semanticScope) ? params.semanticScope.map(String) : [],
    assignment: String(params.assignment || ""),
    description: String(params.description || ""),
    idempotency_key: String(params.idempotencyKey || "").trim(),
  };
  const value = await runReadOnlySpawn(request, projectRoot, signal);
  if (value.code !== 0 || value.details?.status !== "READY_TO_DISPATCH") {
    return governedToolError(
      value.details?.reason_code || "CONTROL_BIND_FAILED",
      value.details?.message || "read-only child packet compilation failed",
      value.details?.smallest_next_action || "Correct the typed read-only binding request and retry.",
    );
  }
  return result(value);
}
async function executeQualifiedTaskTool(toolCallId, params, signal, ctx) {
  if (!governedProfileEnabled()) {
    return governedToolError(
      "GOVERNED_PROFILE_REQUIRED",
      "bbk_task_run is available only in governed-software mode",
      "Enable governed-software mode before running a qualified task.",
    );
  }
  const projectRoot = governedProjectRoot();
  const sessionId = hostSessionIdentity(ctx);
  if (!projectRoot || !sessionId) {
    return governedToolError(
      "BOUND_TASK_ACTOR_IDENTITY_REQUIRED",
      "explicit BBK project root and stable OMP session identity are required; CWD is not authority",
      "Bind the project and invoke the task from its exact worker session.",
    );
  }
  if (governedHostVersion() !== "omp/16.4.8") {
    return governedToolError(
      "OMP_HOST_UNQUALIFIED_FOR_BOUND_TASK",
      `host ${governedHostVersion()} is not qualified for bound mise task execution`,
      "Use OMP 16.4.8 or re-qualify the changed host.",
    );
  }
  const bindingRef = String(params.bindingRef || "").trim();
  const hostReceipt = await recordGovernedHostDecision(
    { toolName: "bbk_task_run", toolCallId, input: params },
    ctx,
    { bindingRef },
  );
  if (!hostReceipt || hostReceipt.code !== 0) {
    return governedToolError(
      hostReceipt?.details?.reason_code || "OMP_HOST_EVENT_RECEIPT_FAILED",
      hostReceipt?.details?.message || "the qualified-task host event could not be correlated",
      hostReceipt?.details?.smallest_next_action || "Repair the active worker binding before retrying.",
    );
  }
  const request = {
    schema: "bbk.bound-qualified-task-execution.v1",
    host_version: governedHostVersion(),
    session_id: sessionId,
    invocation_id: String(params.invocationId || "").trim(),
    binding_ref: bindingRef,
    task: String(params.task || "").trim(),
    arguments: Array.isArray(params.arguments) ? params.arguments.map(String) : [],
    environment_allowlist: Array.isArray(params.environmentAllowlist) ? params.environmentAllowlist.map(String) : [],
    idempotency_key: String(params.idempotencyKey || "").trim(),
  };
  const value = await runQualifiedTask(request, projectRoot, signal);
  if (value.code !== 0 || value.details?.status !== "PASS") {
    return governedToolError(
      value.details?.reason_code || "BOUND_TASK_FAILED",
      value.details?.message || (value.details?.status === "FAIL"
        ? "qualified task failed or changed the candidate"
        : "bound qualified task execution failed"),
      value.details?.smallest_next_action || "Use a declared candidate-preserving task and the current worker binding.",
    );
  }
  return result(value);
}
function parseReturnJson(value, field, fallback) {
  if (value === undefined || value === null || String(value).trim() === "") return fallback;
  try {
    return typeof value === "string" ? JSON.parse(value) : value;
  } catch (error) {
    const failure = new Error(`${field} is not valid JSON: ${String(error?.message || error)}`);
    failure.reasonCode = "ROLE_RETURN_REQUEST_INVALID_JSON";
    throw failure;
  }
}
function roleReturnField(params, directField, jsonField, fallback, { required = false } = {}) {
  const hasDirect = Object.hasOwn(params, directField) && params[directField] !== undefined && params[directField] !== null;
  const rawJson = params[jsonField];
  const hasJson = rawJson !== undefined && rawJson !== null && String(rawJson).trim() !== "";
  if (!hasDirect && !hasJson) {
    if (required) {
      const failure = new Error(`${directField} is required; supply the structured value directly or use compatibility field ${jsonField}`);
      failure.reasonCode = "ROLE_RETURN_REQUEST_FIELD_REQUIRED";
      throw failure;
    }
    return fallback;
  }
  const direct = hasDirect ? params[directField] : undefined;
  const parsed = hasJson ? parseReturnJson(rawJson, jsonField, fallback) : undefined;
  if (hasDirect && hasJson && governedPayloadDigest(direct) !== governedPayloadDigest(parsed)) {
    const failure = new Error(`${directField} and ${jsonField} describe different values`);
    failure.reasonCode = "ROLE_RETURN_REQUEST_AMBIGUOUS";
    failure.smallestNextAction = `Use ${directField} directly; keep ${jsonField} only for an exact compatibility duplicate.`;
    throw failure;
  }
  return hasDirect ? direct : parsed;
}
async function activeReturnToolContext(params, ctx) {
  if (!governedProfileEnabled()) {
    throw Object.assign(new Error("BBK structured-return tools are available only in governed-software mode"), {
      reasonCode: "GOVERNED_PROFILE_REQUIRED",
      smallestNextAction: "Enable governed-software mode and use the exact active child binding.",
    });
  }
  const projectRoot = governedProjectRoot();
  const sessionId = hostSessionIdentity(ctx);
  if (!projectRoot || !sessionId) {
    throw Object.assign(new Error("structured return requires an explicit BBK project root and stable OMP session identity"), {
      reasonCode: "ROLE_RETURN_IDENTITY_REQUIRED",
      smallestNextAction: "Invoke the tool from the exact activated BBK child session.",
    });
  }
  return {
    projectRoot,
    sessionId,
    bindingRef: String(params.bindingRef || "").trim(),
    invocationId: String(params.invocationId || "").trim(),
  };
}
async function executeReturnTemplateTool(toolCallId, params, signal, ctx) {
  try {
    const active = await activeReturnToolContext(params, ctx);
    const hostReceipt = await recordGovernedHostDecision(
      { toolName: "bbk_return_template", toolCallId, input: params },
      ctx,
      { bindingRef: active.bindingRef },
    );
    if (!hostReceipt || hostReceipt.code !== 0) {
      return governedToolError(
        hostReceipt?.details?.reason_code || "OMP_HOST_EVENT_RECEIPT_FAILED",
        hostReceipt?.details?.message || "the role-return template query could not be correlated",
        hostReceipt?.details?.smallest_next_action || "Repair the active binding and retry.",
      );
    }
    const value = await runRoleReturn("template", {
      schema: "bbk.role-return-template-query.v1",
      session_id: active.sessionId,
      binding_ref: active.bindingRef,
      invocation_id: active.invocationId,
      invocation_mode: String(params.invocationMode || "").trim() || undefined,
    }, active.projectRoot, signal);
    if (value.code !== 0 || value.details?.status !== "PASS") {
      return governedToolError(
        value.details?.reason_code || "ROLE_RETURN_TEMPLATE_FAILED",
        value.details?.message || "the active role-return template could not be produced",
        value.details?.smallest_next_action || "Use the exact active binding and declared role-parent route.",
      );
    }
    return result(value);
  } catch (error) {
    return governedToolError(
      error?.reasonCode || "ROLE_RETURN_TEMPLATE_FAILED",
      String(error?.message || error),
      error?.smallestNextAction || "Correct the typed template request and retry.",
    );
  }
}
async function executeReturnPrepareTool(toolCallId, params, signal, ctx) {
  try {
    const active = await activeReturnToolContext(params, ctx);
    const hostReceipt = await recordGovernedHostDecision(
      { toolName: "bbk_return_prepare", toolCallId, input: params },
      ctx,
      { bindingRef: active.bindingRef },
    );
    if (!hostReceipt || hostReceipt.code !== 0) {
      return governedToolError(
        hostReceipt?.details?.reason_code || "OMP_HOST_EVENT_RECEIPT_FAILED",
        hostReceipt?.details?.message || "the role-return preparation could not be correlated",
        hostReceipt?.details?.smallest_next_action || "Repair the active binding and retry.",
      );
    }
    const nextAction = {
      action: String(params.nextAction || "").trim(),
      owner: String(params.nextActionOwner || "").trim(),
      reason: String(params.nextActionReason || "").trim(),
      affected_refs: Array.isArray(params.nextActionAffectedRefs)
        ? params.nextActionAffectedRefs.map(value => ({ id: String(value) }))
        : [],
      unaffected_work_may_continue: Boolean(params.unaffectedWorkMayContinue),
    };
    if (nextAction.affected_refs.length === 0) delete nextAction.affected_refs;
    const request = {
      schema: "bbk.role-return-prepare.v1",
      session_id: active.sessionId,
      binding_ref: active.bindingRef,
      invocation_id: active.invocationId,
      invocation_mode: String(params.invocationMode || "").trim() || undefined,
      return_kind: String(params.returnKind || "").trim(),
      detail_level: String(params.detailLevel || "COMPACT").trim(),
      operational_disposition: String(params.operationalDisposition || "").trim(),
      semantic_state_value: String(params.semanticStateValue || "").trim(),
      summary: String(params.summary || ""),
      result: roleReturnField(params, "result", "resultJson", {}, { required: true }),
      smallest_valid_next_action: nextAction,
      authority_refs: roleReturnField(params, "authorityRefs", "authorityRefsJson", undefined),
      allowed_effect_classes: Array.isArray(params.allowedEffectClasses) ? params.allowedEffectClasses.map(String) : [],
      effects_used: roleReturnField(params, "effectsUsed", "effectsUsedJson", []),
      denied_or_uncovered_effects: roleReturnField(params, "deniedOrUncoveredEffects", "deniedOrUncoveredEffectsJson", []),
      violations_or_ambiguities: roleReturnField(params, "violationsOrAmbiguities", "violationsOrAmbiguitiesJson", []),
      outputs: roleReturnField(params, "outputs", "outputsJson", undefined),
      checks_and_evidence: roleReturnField(params, "checksAndEvidence", "checksAndEvidenceJson", undefined),
      effects_and_cleanup: roleReturnField(params, "effectsAndCleanup", "effectsAndCleanupJson", undefined),
      blockers_and_residuals: Array.isArray(params.blockersAndResiduals) ? params.blockersAndResiduals.map(String) : undefined,
      prohibited_claims: Array.isArray(params.prohibitedClaims) ? params.prohibitedClaims.map(String) : undefined,
      durable_handoff_refs: roleReturnField(params, "durableHandoffRefs", "durableHandoffRefsJson", undefined),
      idempotency_key: String(params.idempotencyKey || "").trim(),
    };
    const value = await runRoleReturn("prepare", request, active.projectRoot, signal);
    if (value.code !== 0 || value.details?.status !== "PASS") {
      return governedToolError(
        value.details?.reason_code || "ROLE_RETURN_PREPARE_FAILED",
        value.details?.message || "role-return preparation failed",
        value.details?.smallest_next_action || "Use bbk_return_template, repair the reported fields, and retry in the same attempt.",
        {
          diagnostics: Array.isArray(value.details?.diagnostics) ? value.details.diagnostics : undefined,
          role: value.details?.role,
          contract: value.details?.contract,
          schema_path: value.details?.schema_path,
          document_digest: value.details?.document_digest,
        },
      );
    }
    return result(value);
  } catch (error) {
    return governedToolError(
      error?.reasonCode || "ROLE_RETURN_PREPARE_FAILED",
      String(error?.message || error),
      error?.smallestNextAction || "Correct the typed return fields and retry in the same attempt.",
    );
  }
}
async function guardYieldRoleReturn(event, ctx, pi) {
  const toolName = String(event?.toolName || event?.tool_name || "").trim().toLowerCase();
  if (toolName !== "yield" || !governedProfileEnabled()) return undefined;
  const projectRoot = governedProjectRoot();
  const sessionId = hostSessionIdentity(ctx);
  if (!projectRoot || !sessionId) {
    return governedBlock(
      "BBK_ROLE_RETURN_IDENTITY_REQUIRED",
      "governed yield requires an explicit BBK project root and stable OMP child session identity",
      "Invoke yield only from the exact activated BBK child session.",
    );
  }
  const policy = await runGovernanceRegistry(["binding-policy", "--session-id", sessionId], projectRoot);
  if (policy.code !== 0 || policy.details?.status !== "PASS") {
    return governedBlock(
      policy.details?.reason_code || "BBK_ROLE_RETURN_BINDING_REQUIRED",
      policy.details?.message || `no active immutable BBK binding exists for yielding session ${sessionId}`,
      policy.details?.smallest_next_action || "Activate the exact child binding before yielding; do not bypass return validation.",
    );
  }
  const toolCallId = String(event?.toolCallId || event?.tool_call_id || event?.id || "").trim();
  const input = event?.input && typeof event.input === "object" ? event.input : {};
  const data = input?.result?.data;
  let value;
  if (data?.schema === "bbk.prepared-role-return.v1" && typeof data?.return_ref === "string") {
    return governedBlock(
      "ROLE_RETURN_COMPLETE_YIELD_REQUIRED",
      "OMP 16.4.8 exposes hidden yield to pre-effect validation but does not reliably apply a rewritten yield payload",
      "Call bbk_return_prepare again and invoke hidden yield with the exact complete yield_input it returns.",
    );
  }
  if (!data || typeof data !== "object" || Array.isArray(data)) {
    return governedBlock(
      "BBK_STRUCTURED_ROLE_RETURN_REQUIRED",
      `binding ${String(policy.details.binding_ref || "unknown")} requires a schema-valid ${String(policy.details.return_contract || "role return")}`,
      "Use bbk_return_template and bbk_return_prepare, then invoke the returned yield_input exactly.",
    );
  }
  value = await runRoleReturn("validate", {
    schema: "bbk.role-return-validate.v1",
    session_id: sessionId,
    binding_ref: policy.details.binding_ref,
    invocation_id: policy.details.invocation_id,
    document: data,
    tool_call_id: toolCallId,
  }, projectRoot);
  if (value.code !== 0 || value.details?.status !== "PASS") {
    if (typeof pi?.appendEntry === "function") pi.appendEntry("bbk-role-return-validation", value.details || {});
    const diagnostic = Array.isArray(value.details?.diagnostics) && value.details.diagnostics.length
      ? `; first error ${value.details.diagnostics[0].instance_pointer || "/"}: ${value.details.diagnostics[0].message}`
      : "";
    return governedBlock(
      value.details?.reason_code || "BBK_ROLE_RETURN_SCHEMA_INVALID",
      `${value.details?.message || "role return did not satisfy its declared schema"}${diagnostic}`,
      value.details?.smallest_next_action || "Use bbk_return_template, repair only the reported fields, and retry in the same attempt.",
    );
  }
  if (!value.details?.prepared_return_verified) {
    return governedBlock(
      "ROLE_RETURN_PREPARATION_REQUIRED",
      "the schema-valid role return is not bound to an immutable bbk_return_prepare record",
      "Call bbk_return_prepare with the same role-specific facts, then invoke hidden yield with its exact complete yield_input.",
    );
  }
  if (typeof pi?.appendEntry === "function") pi.appendEntry("bbk-role-return-validation", value.details);
  return undefined;
}

async function executeControlSpawnTool(toolCallId, params, signal, ctx) {
  if (!governedProfileEnabled()) {
    return governedToolError(
      "GOVERNED_PROFILE_REQUIRED",
      "bbk_control_spawn is available only in governed-software mode",
      "Enable the governed-software profile before compiling a writable child.",
    );
  }
  const projectRoot = governedProjectRoot();
  const parentSessionId = hostSessionIdentity(ctx);
  if (!projectRoot || !parentSessionId) {
    return governedToolError(
      "BOUND_SPAWN_PARENT_IDENTITY_REQUIRED",
      "explicit BBK project root and stable OMP parent session are required; CWD is not authority",
      "Bind the project and use the qualified OMP session surface.",
    );
  }
  if (governedHostVersion() !== "omp/16.4.8") {
    return governedToolError(
      "OMP_HOST_UNQUALIFIED_FOR_SPAWN",
      `host ${governedHostVersion()} is not qualified for bound writable spawn`,
      "Use OMP 16.4.8 or re-qualify the changed host.",
    );
  }
  const parentBindingRef = String(params.parentBindingRef || "").trim();
  const hostReceipt = await recordGovernedHostDecision(
    { toolName: "bbk_control_spawn", toolCallId, input: params },
    ctx,
    { bindingRef: parentBindingRef },
  );
  if (!hostReceipt || hostReceipt.code !== 0) {
    return governedToolError(
      hostReceipt?.details?.reason_code || "OMP_HOST_EVENT_RECEIPT_FAILED",
      hostReceipt?.details?.message || "the writable spawn host event could not be correlated",
      hostReceipt?.details?.smallest_next_action || "Repair the parent binding before retrying.",
    );
  }
  const request = {
    schema: "bbk.bound-worker-spawn-create.v1",
    host_version: governedHostVersion(),
    parent_binding_ref: parentBindingRef,
    parent_session_id: parentSessionId,
    parent_invocation_id: String(params.parentInvocationId || "").trim(),
    task_name: String(params.taskName || "").trim(),
    role: String(params.role || "").trim(),
    work_unit_id: String(params.workUnitId || "").trim(),
    attempt_id: String(params.attemptId || "").trim(),
    baseline_ref: String(params.baselineRef || "").trim(),
    candidate_ref: String(params.candidateRef || "").trim(),
    authority_ref: String(params.authorityRef || "").trim(),
    return_contract: String(params.returnContract || "").trim(),
    return_transport_mode: String(params.returnTransportMode || "STRUCTURED_RETURN_FIRST").trim(),
    material_transport_reason: String(params.materialTransportReason || "").trim(),
    parent_revision: String(params.parentRevision || "").trim(),
    workspace_parent: String(params.workspaceParent || "").trim(),
    path_prefixes: Array.isArray(params.pathPrefixes) ? params.pathPrefixes.map(String) : [],
    mutation_classes: Array.isArray(params.mutationClasses) ? params.mutationClasses.map(String) : [],
    semantic_scope: Array.isArray(params.semanticScope) ? params.semanticScope.map(String) : [],
    assignment: String(params.assignment || ""),
    description: String(params.description || ""),
    idempotency_key: String(params.idempotencyKey || "").trim(),
  };
  const value = await runWorkerSpawn(request, projectRoot, signal);
  const acceptedStatuses = new Set(["READY_TO_DISPATCH", "DISPATCH_LEASED", "ACTIVATED", "TERMINAL"]);
  if (value.code !== 0 || !acceptedStatuses.has(String(value.details?.status || ""))) {
    return governedToolError(
      value.details?.reason_code || "BOUND_SPAWN_FAILED",
      value.details?.message || "bound worker packet compilation failed",
      value.details?.smallest_next_action || "Correct the typed spawn request and retry.",
    );
  }
  return result(value);
}
async function executeDispatchStatusTool(_toolCallId, params, signal, ctx) {
  if (!governedProfileEnabled()) {
    return governedToolError(
      "GOVERNED_PROFILE_REQUIRED",
      "bbk_control_dispatch_status is available only in governed-software mode",
      "Enable governed-software mode and query the current dispatch token.",
    );
  }
  const projectRoot = governedProjectRoot();
  const parentSessionId = hostSessionIdentity(ctx);
  if (!projectRoot || !parentSessionId) {
    return governedToolError(
      "OMP_PARENT_SESSION_REQUIRED",
      "dispatch status requires the exact governed project and stable parent session",
      "Use the qualified OMP parent session that created the reservation.",
    );
  }
  const dispatchRef = String(params.dispatchRef || "").trim();
  const value = await runGovernanceRegistry([
    "dispatch-status",
    "--dispatch-ref", dispatchRef,
    "--parent-session-id", parentSessionId,
    "--observed-at", new Date().toISOString(),
  ], projectRoot, signal);
  if (value.code !== 0 || !["READY", "LEASED", "ACTIVATED", "TERMINAL"].includes(String(value.details?.status || ""))) {
    return governedToolError(
      value.details?.reason_code || "OMP_SPAWN_DISPATCH_STATUS_FAILED",
      value.details?.message || "dispatch status could not be resolved",
      value.details?.smallest_next_action || "Use the exact dispatch_ref returned by BBK.",
    );
  }
  return result(value);
}
async function executeControlPlaneTool(toolCallId, requestSchema, params, signal, ctx) {
  if (!governedProfileEnabled()) {
    return governedToolError(
      "GOVERNED_PROFILE_REQUIRED",
      `${TOOL_NAME_BY_CONTROL_SCHEMA[requestSchema] || "BBK control tool"} is available only in governed-software mode`,
      "Enable the governed-software profile before issuing coordination effects.",
    );
  }
  const projectRoot = governedProjectRoot();
  const sessionId = hostSessionIdentity(ctx);
  if (!projectRoot || !sessionId) {
    return governedToolError(
      "CONTROL_PLANE_ACTOR_IDENTITY_REQUIRED",
      "explicit BBK project root and stable OMP session identity are required; CWD is not authority",
      "Bind the project and invoke the tool from the qualified OMP session surface.",
    );
  }
  if (governedHostVersion() !== "omp/16.4.8") {
    return governedToolError(
      "CONTROL_PLANE_HOST_UNQUALIFIED",
      `host ${governedHostVersion()} is not qualified for enforced orchestrator control effects`,
      "Use OMP 16.4.8 or re-qualify the changed host contract.",
    );
  }
  const bindingRef = String(params.bindingRef || "").trim();
  const request = {
    schema: requestSchema,
    host_version: governedHostVersion(),
    session_id: sessionId,
    binding_ref: bindingRef,
    invocation_id: String(params.invocationId || "").trim(),
    command_id: String(params.commandId || "").trim(),
    work_unit_id: String(params.workUnitId || "").trim(),
    attempt_id: String(params.attemptId || "").trim(),
    correlation_id: String(params.correlationId || "").trim(),
    payload_summary: String(params.payloadSummary || ""),
    expected_revision: params.expectedRevision,
    idempotency_key: String(params.idempotencyKey || "").trim(),
    evidence_refs: Array.isArray(params.evidenceRefs) ? params.evidenceRefs.map(String) : [],
    finding_refs: Array.isArray(params.findingRefs) ? params.findingRefs.map(String) : [],
  };
  if (requestSchema === "bbk.control-assign.v1") {
    request.worker_binding_ref = String(params.workerBindingRef || "").trim();
    request.attempt_registration_ref = String(params.attemptRegistrationRef || "").trim();
  } else if (requestSchema === "bbk.control-update.v1") {
    request.transition = String(params.transition || "").trim();
  } else if (requestSchema === "bbk.control-integrate-request.v1") {
    request.source_candidate_refs = Array.isArray(params.sourceCandidateRefs) ? params.sourceCandidateRefs.map(String) : [];
    request.target_candidate_ref = String(params.targetCandidateRef || "").trim();
    request.conflict_classification = String(params.conflictClassification || "").trim();
  }
  const hostReceipt = await recordGovernedHostDecision(
    { toolName: TOOL_NAME_BY_CONTROL_SCHEMA[requestSchema] || "bbk_control", toolCallId, input: params },
    ctx,
    { bindingRef },
  );
  if (!hostReceipt || hostReceipt.code !== 0) {
    return governedToolError(
      hostReceipt?.details?.reason_code || "OMP_HOST_EVENT_RECEIPT_FAILED",
      hostReceipt?.details?.message || "the control-plane host event could not be durably correlated",
      hostReceipt?.details?.smallest_next_action || "Repair the active binding/host identity before retrying.",
    );
  }
  return result(await runControlPlane(request, projectRoot, signal));
}
const TOOL_NAME_BY_CONTROL_SCHEMA = Object.freeze({
  "bbk.control-assign.v1": "bbk_control_assign",
  "bbk.control-update.v1": "bbk_control_update",
  "bbk.control-integrate-request.v1": "bbk_control_integrate_request",
});
function governedFilesystemPayload(operation, params) {
  if (operation === "WRITE") {
    return { content: String(params.content ?? ""), encoding: String(params.encoding || "utf-8") };
  }
  if (operation === "EDIT") {
    return {
      old_text: String(params.oldText ?? ""),
      new_text: String(params.newText ?? ""),
      replace_all: Boolean(params.replaceAll),
    };
  }
  return {};
}
async function executeGovernedFilesystemTool(toolCallId, operation, params, signal, ctx) {
  if (!governedProfileEnabled()) {
    return governedToolError(
      "GOVERNED_PROFILE_REQUIRED",
      `bbk_governed_${operation.toLowerCase()} is available only in governed-software mode`,
      "Enable the explicit governed-software profile or use the baseline non-governed tool surface.",
    );
  }
  const projectRoot = governedProjectRoot();
  if (!projectRoot) {
    return governedToolError(
      "GOVERNED_PROJECT_ROOT_REQUIRED",
      "no explicit BBK project root is bound; process CWD is not accepted as mutation authority",
      "Set BBK_PROJECT_ROOT or load a valid project-scoped BBK package binding.",
    );
  }
  const sessionId = hostSessionIdentity(ctx);
  if (!sessionId) {
    return governedToolError(
      "OMP_SESSION_ID_REQUIRED",
      "OMP did not expose a stable session identity; CWD fallback is not accepted",
      "Use a qualified host/session surface before invoking governed filesystem tools.",
    );
  }
  const hostVersion = governedHostVersion();
  if (hostVersion !== "omp/16.4.8") {
    return governedToolError(
      "MUTATION_HOST_UNQUALIFIED",
      `host ${hostVersion || "unknown"} is not qualified for governed pre-effect mutation`,
      "Use OMP 16.4.8 or re-qualify the changed host before writable execution.",
    );
  }
  const bindingRef = String(params.bindingRef || "").trim();
  const invocationId = String(params.invocationId || "").trim();
  const relativePath = String(params.path || "").trim();
  const idempotencyKey = String(params.idempotencyKey || "").trim();
  const mutationClass = String(params.mutationClass || (operation === "READ" ? "READ_ONLY" : "")).trim();
  if (!bindingRef || !invocationId || !relativePath || !idempotencyKey || !mutationClass) {
    return governedToolError(
      "MUTATION_IDENTITY_INCOMPLETE",
      "bindingRef, invocationId, path, mutationClass, and idempotencyKey are required",
      "Use the exact identities and scope supplied in the immutable worker binding.",
    );
  }
  const payload = governedFilesystemPayload(operation, params);
  const preconditionKind = String(params.preconditionKind || (operation === "READ" ? "PRESENT" : "ANY")).toUpperCase();
  const expectedPrecondition = { kind: preconditionKind };
  if (preconditionKind === "SHA256") expectedPrecondition.sha256 = String(params.expectedSha256 || "").trim();
  const envelope = {
    schema: "bbk.governed-filesystem-execution.v1",
    host_version: hostVersion,
    session_id: sessionId,
    invocation_id: invocationId,
    intent: {
      schema: "bbk.mutation-intent.v1",
      binding_ref: bindingRef,
      operation,
      path: relativePath,
      content_or_patch_digest: governedPayloadDigest(payload),
      expected_precondition: expectedPrecondition,
      mutation_class: mutationClass,
      idempotency_key: idempotencyKey,
    },
    payload,
  };
  const hostReceipt = await recordGovernedHostDecision(
    { toolName: `bbk_governed_${operation.toLowerCase()}`, toolCallId, input: params },
    ctx,
    { bindingRef },
  );
  if (!hostReceipt || hostReceipt.code !== 0) {
    return governedToolError(
      hostReceipt?.details?.reason_code || "OMP_HOST_EVENT_RECEIPT_FAILED",
      hostReceipt?.details?.message || "the pre-effect host event could not be durably correlated",
      hostReceipt?.details?.smallest_next_action || "Repair the active binding/host identity before retrying.",
    );
  }
  return result(await runGovernedFilesystem(envelope, projectRoot, signal));
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
  if (typeof details.code === "string" && details.code.trim()) lines.push(`code: ${details.code.trim()}`);
  const message = details.error || details.message || details.parseError;
  if (typeof message === "string" && message.trim()) lines.push(message.trim().slice(0, 600));
  if (details.field) {
    const received = details.received !== null && details.received !== undefined ? `; received=${String(details.received)}` : "";
    lines.push(`field: ${String(details.field)}${received}`);
  }
  if (Array.isArray(details.valid_values) && details.valid_values.length) {
    lines.push(`valid values: ${details.valid_values.join(", ")}`);
  }
  for (const key of [
    "path", "output", "outputRoot", "publicationReceipt", "currentPointer",
    "manifest_path", "candidate", "id", "packageId", "revision",
  ]) {
    if (typeof details[key] === "string" && details[key].trim()) lines.push(`${key}: ${details[key].trim()}`);
  }
  if (details.summary && typeof details.summary === "object" && !Array.isArray(details.summary)) {
    const counts = Object.entries(details.summary)
      .filter(([, count]) => typeof count === "number")
      .map(([name, count]) => `${name}=${count}`);
    if (counts.length) lines.push(`summary: ${counts.join(", ")}`);
  }
  if (typeof details.example_command === "string" && details.example_command.trim()) {
    lines.push(`example: ${details.example_command.trim()}`);
  }
  if (typeof details.smallest_next_action === "string" && details.smallest_next_action.trim()) {
    lines.push(`next: ${details.smallest_next_action.trim()}`);
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
const BBK_RUNTIME_SYMBOL = Symbol.for("bbk.omp.runtime.v1");
const BBK_COORDINATION_PROBE_INTERVAL_MS = 300_000;
const BBK_PROMPT_RECEIPT_ENTRY_TYPE = "bbk-effective-prompt-receipt";
const BBK_PROMPT_RECEIPT_SCHEMA = "bbk.effective-prompt-receipt.v2";
const BBK_PROMPT_COMPILATION_ENTRY_TYPE = "bbk-prompt-compilation-event";
const BBK_PROMPT_COMPILATION_SCHEMA = "bbk.prompt-compilation-event.v1";
const BBK_PROMPT_STATUS_SCHEMA = "bbk.prompt-status.v2";
const BBK_PROMPT_INTEGRITY_STATUS_KEY = "bbk-prompt-integrity";
const BBK_ACTIVITY_WIDGET_KEY = "bbk-worker-activity";
const BBK_ARTIFACT_FINALIZATION_ENTRY_TYPE = "bbk-artifact-finalization-state";
const BBK_ARTIFACT_FINALIZATION_SCHEMA = "bbk.omp-artifact-finalization-state.v1";
const BBK_ARTIFACT_FINALIZATION_STATUS_KEY = "bbk-artifact-finalization";
const BBK_ARTIFACT_FINALIZE_MARKER_RE = /(?:bbk\s+artifact\s+finalize|bbk_artifact_finalize|\/bbk:artifact:finalize)/i;
const BBK_ARTIFACT_FINALIZE_REQUIREMENT_RE = /(?:\b(?:must|required|requires?|using|use|run|execute|finalize|publish|deliver)\b[\s\S]{0,180}(?:bbk\s+artifact\s+finalize|bbk_artifact_finalize|\/bbk:artifact:finalize)|(?:bbk\s+artifact\s+finalize|bbk_artifact_finalize|\/bbk:artifact:finalize)[\s\S]{0,180}\b(?:must|required|requires?|before|using|for the final|as part of)\b)/i;
const BBK_ARTIFACT_FINALIZE_NEGATION_RE = /(?:(?:\b(?:do not|don't|must not|without|not required|optional)\b[\s\S]{0,100}(?:bbk\s+artifact\s+finalize|bbk_artifact_finalize|\/bbk:artifact:finalize))|(?:(?:bbk\s+artifact\s+finalize|bbk_artifact_finalize|\/bbk:artifact:finalize)[\s\S]{0,100}\b(?:do not|don't|must not|without|not required|optional)\b))/i;
const BBK_COMPLETION_CLAIM_RE = /(?:\bBYTE_INTEGRITY_VERIFIED\b|\bDELIVERED_AND_VERIFIED\b|\bIMPLEMENTATION_ARTIFACTS_COMPLETE\b|\bSEMANTIC_REVIEW_COMPLETE\b|\bLIVE_ACCEPTANCE_VERIFIED\b|\ball (?:requested )?work (?:is|has been) complete\b|\bimplementation (?:is|has been) complete\b|\bcompleted implementation\b|\bfinal (?:delivery|completion report)\b)/i;
const TASK_SUBAGENT_PROGRESS_CHANNEL = "task:subagent:progress";
const TASK_SUBAGENT_LIFECYCLE_CHANNEL = "task:subagent:lifecycle";
const BBK_COORDINATION_TOOL_NAMES = new Set(["hub", "irc", "job"]);
const BBK_WAKE_OUTCOMES = new Set(["injected", "woken", "revived"]);
const BBK_CONTROLLER_PROMPT_MARKER = "<bbk-controller-system";
const BBK_AGENT_PROMPT_MARKER = "<bbk-agent-system";
const BBK_AGENT_BLOCK_RE = /<bbk-agent-system\b[^>]*\brole="([^"]+)"[^>]*>[\s\S]*?<\/bbk-agent-system>/i;
const BBK_ROLE_NAME_RE = /^bbk_[a-z0-9_]+$/;

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
let cachedProjectionManifest;
function projectionManifest() {
  if (cachedProjectionManifest) return cachedProjectionManifest;
  const value = JSON.parse(packageText("projections", "manifest.json"));
  if (value?.schema !== "bbk.projection-manifest.v10"
    || value?.package_version !== version
    || !value?.agents || !value?.controllers?.omp) {
    throw new Error("installed projection manifest is missing required prompt-compilation metadata");
  }
  cachedProjectionManifest = value;
  return value;
}
function promptCompilationTemplate(identity) {
  if (!identity || !["controller", "agent"].includes(identity.kind)) return null;
  const manifest = projectionManifest();
  const value = identity.kind === "controller"
    ? manifest.controllers?.omp?.event
    : manifest.agents?.[identity.role]?.prompt_compilation_events?.omp;
  if (!value || value.schema !== BBK_PROMPT_COMPILATION_SCHEMA
    || value.harness !== "OMP" || !Array.isArray(value.procedure_ids)
    || value.procedure_ids.length === 0) {
    throw new Error(`installed prompt-compilation event is invalid for ${identity?.role || identity?.kind || "unknown"}`);
  }
  return value;
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
    "Use bbk_return_template when the role-specific payload shape is not already exact, then call bbk_return_prepare. Invoke hidden yield with the returned complete yield_input exactly; do not hand-author or abbreviate the common envelope.",
    "The yield pre-effect hook validates every direct return against the bound role schema and rejects malformed returns with focused same-attempt repair diagnostics.",
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
  const raw = String(text || "");
  const value = raw.replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n/, "");
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
function cloneProviderValue(value) {
  try { return structuredClone(value); }
  catch {
    try { return JSON.parse(JSON.stringify(value)); }
    catch { return value; }
  }
}
function providerContentText(value) {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) {
    return value.map(item => {
      if (typeof item === "string") return item;
      if (item && typeof item === "object") {
        if (typeof item.text === "string") return item.text;
        if (typeof item.content === "string") return item.content;
      }
      return "";
    }).filter(Boolean).join("\n");
  }
  if (value && typeof value === "object") {
    if (typeof value.text === "string") return value.text;
    if (typeof value.content === "string") return value.content;
    if (Array.isArray(value.parts)) return providerContentText(value.parts);
  }
  return "";
}
function providerMessageRole(value) {
  return String(value?.role || "").trim().toLowerCase();
}
function providerMessageBlocks(messages) {
  if (!Array.isArray(messages)) return [];
  return messages
    .filter(item => ["system", "developer"].includes(providerMessageRole(item)))
    .map(item => providerContentText(item?.content))
    .filter(text => text.length > 0);
}
function providerPromptSurfaceData(payload) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return { blocks: [], count: 0 };
  }
  const blocks = [];
  let count = 0;
  for (const key of ["instructions", "system", "systemInstruction", "systemPrompt"]) {
    if (!Object.prototype.hasOwnProperty.call(payload, key)) continue;
    const text = providerContentText(payload[key]);
    if (!text) continue;
    blocks.push(text);
    count += 1;
  }
  for (const key of ["messages", "input"]) {
    if (!Array.isArray(payload[key])) continue;
    const values = providerMessageBlocks(payload[key]);
    blocks.push(...values);
    count += payload[key].filter(item => ["system", "developer"].includes(providerMessageRole(item))).length;
  }
  return { blocks, count };
}
function filterProviderSystemMessages(value) {
  if (!Array.isArray(value)) return value;
  return value.filter(item => !["system", "developer"].includes(providerMessageRole(item)));
}
function repairProviderPromptSurfaces(payload, primary, expected) {
  const result = cloneProviderValue(payload);
  for (const key of ["messages", "input"]) {
    if (Array.isArray(result[key])) result[key] = filterProviderSystemMessages(result[key]);
  }
  for (const key of ["instructions", "system", "systemInstruction", "systemPrompt"]) {
    if (key !== primary) delete result[key];
  }
  if (primary === "messages") {
    result.messages = [
      { role: "system", content: expected },
      ...filterProviderSystemMessages(result.messages || []),
    ];
  } else if (primary === "instructions") {
    result.instructions = expected;
  } else if (primary === "system") {
    result.system = expected;
  } else if (primary === "systemInstruction") {
    if (typeof result.systemInstruction === "string") result.systemInstruction = expected;
    else result.systemInstruction = { ...(result.systemInstruction || {}), parts: [{ text: expected }] };
  } else if (primary === "systemPrompt") {
    result.systemPrompt = expected;
  }
  return result;
}
function providerPayloadAdapterDirect(payload) {
  if (Array.isArray(payload) && payload.every(item => item && typeof item === "object" && "role" in item)) {
    return {
      name: "message-array",
      blocks: providerMessageBlocks(payload),
      system_surface_count: payload.filter(item => ["system", "developer"].includes(providerMessageRole(item))).length,
      repair(expected) {
        return [
          { role: "system", content: expected },
          ...cloneProviderValue(payload).filter(item => !["system", "developer"].includes(providerMessageRole(item))),
        ];
      },
    };
  }
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) return null;

  const surfaces = providerPromptSurfaceData(payload);
  let name = null;
  let primary = null;
  if (Object.prototype.hasOwnProperty.call(payload, "systemInstruction")) {
    name = "google-system-instruction";
    primary = "systemInstruction";
  } else if (Object.prototype.hasOwnProperty.call(payload, "instructions") || (Array.isArray(payload.input) && !Array.isArray(payload.messages))) {
    name = "openai-responses";
    primary = "instructions";
  } else if (Object.prototype.hasOwnProperty.call(payload, "system")) {
    name = "anthropic-system";
    primary = "system";
  } else if (Array.isArray(payload.messages)) {
    name = "openai-messages";
    primary = "messages";
  } else if (Object.prototype.hasOwnProperty.call(payload, "systemPrompt")) {
    name = "system-prompt-field";
    primary = "systemPrompt";
  }
  if (!name || !primary) return null;
  return {
    name,
    blocks: surfaces.blocks,
    system_surface_count: surfaces.count,
    repair(expected) {
      return repairProviderPromptSurfaces(payload, primary, expected);
    },
  };
}
function removedPromptSurfaceCount(adapter, expectedText) {
  if (!adapter) return 0;
  const exactObserved = (adapter.blocks || []).some(block => block === expectedText) ? 1 : 0;
  return Math.max(0, Number(adapter.system_surface_count || 0) - exactObserved);
}

function providerPayloadAdapter(payload) {
  const direct = providerPayloadAdapterDirect(payload);
  if (direct) return direct;
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) return null;
  for (const key of ["body", "request", "payload"]) {
    if (!Object.prototype.hasOwnProperty.call(payload, key)) continue;
    const nested = providerPayloadAdapterDirect(payload[key]);
    if (!nested) continue;
    return {
      name: `${key}.${nested.name}`,
      blocks: nested.blocks,
      system_surface_count: nested.system_surface_count,
      repair(expected) {
        const result = cloneProviderValue(payload);
        result[key] = nested.repair(expected);
        return result;
      },
    };
  }
  return null;
}
function canonicalPromptBlockFromText(value) {
  const text = String(value || "");
  const patterns = [
    /<bbk-controller-system\b[^>]*>[\s\S]*?<\/bbk-controller-system>/i,
    /<bbk-agent-replacement\b[^>]*>[\s\S]*?<\/bbk-agent-replacement>/i,
    /<bbk-prompt-assembly-failure\b[^>]*>[\s\S]*?<\/bbk-prompt-assembly-failure>/i,
  ];
  const matches = patterns.map(pattern => text.match(pattern)?.[0]?.trim()).filter(Boolean);
  return matches.length === 1 ? matches[0] : null;
}
function canonicalPromptBlockFromProvider(adapter) {
  const matches = (adapter?.blocks || []).map(canonicalPromptBlockFromText).filter(Boolean);
  return matches.length === 1 ? matches[0] : null;
}
function validatedPromptMarkerCandidate(text) {
  const raw = String(text || "").trim();
  const candidate = canonicalPromptBlockFromText(raw);
  if (!candidate || candidate !== raw) return null;
  const identity = promptOuterIdentity(candidate);
  const packageVersion = candidate.match(/^<bbk-(?:controller-system|agent-replacement|prompt-assembly-failure)\b[^>]*\bpackage-version="([^"]+)"/i)?.[1];
  if (packageVersion !== version) return null;
  if (identity.kind === "agent" && identity.role && BBK_ROLE_NAME_RE.test(identity.role)) {
    const roleMatches = [...candidate.matchAll(new RegExp(BBK_AGENT_BLOCK_RE.source, "gi"))];
    if (roleMatches.length !== 1
      || roleMatches[0][1] !== identity.role
      || normalizePromptBlock(roleMatches[0][0]) !== canonicalAgentBlock(identity.role)) return null;
  } else if (!['controller', 'assembly-failure'].includes(identity.kind)) {
    return null;
  }
  const summary = promptReceiptSummary([candidate]);
  return { ...summary, text: candidate, role: identity.role, prompt_kind: identity.kind };
}
function promptSessionIdentity(ctx) {
  for (const candidate of [ctx?.sessionId, ctx?.sessionManager?.sessionId]) {
    if (typeof candidate === "string" && candidate.trim()) return candidate.trim();
  }
  try {
    const id = ctx?.sessionManager?.getSessionId?.();
    if (id) return String(id);
  } catch {}
  try {
    const file = ctx?.sessionManager?.getSessionFile?.();
    if (file) return createHash("sha256").update(String(file), "utf8").digest("hex").slice(0, 16);
  } catch {}
  try {
    const header = (ctx?.sessionManager?.getBranch?.() || []).find(entry => entry?.type === "session");
    if (header?.id) return String(header.id);
  } catch {}
  return `cwd:${String(ctx?.cwd || process.cwd())}`;
}
function blockedProviderPayload(reason) {
  return {
    __bbk_prompt_blocked__: true,
    reason: oneLine(reason || "provider prompt integrity could not be established", 240),
  };
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
  const replacementBlocks = blocks.filter(block => /<bbk-agent-replacement\b/i.test(block));
  if (replacementBlocks.length > 0) {
    if (replacementBlocks.length !== 1) throw new Error("ambiguous BBK agent-replacement marker blocks");
    return { alreadyReplaced: true, replacementBlock: replacementBlocks[0] };
  }

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
    const manifestMarker = `- id: ${skill}`;
    const bodyMarker = role.primary_skill === skill
      ? `### Compiled primary procedure: \`${skill}\``
      : `### Compiled procedure: \`${skill}\``;
    if (countLiteral(roleBlock, manifestMarker) !== 1
      || countLiteral(roleBlock, bodyMarker) !== 1
      || !roleBlock.includes("catalog_visibility: SUPPRESSED")
      || !roleBlock.includes("state: COMPILED_COMPLETE")) {
      throw new Error(`BBK role ${roleName} is missing compiled procedure ${skill}`);
    }
    if (roleBlock.includes(`<bbk-inlined-skill name="${skill}"`)) {
      throw new Error(`BBK role ${roleName} exposes legacy inlined skill markup for ${skill}`);
    }
  }
  if (!roleBlock.includes("## End compiled procedures")) {
    throw new Error(`BBK role ${roleName} has no closed compiled-procedure tail`);
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
function generatedControllerProjection(ctx) {
  const source = packageText("projections", "omp", "controllers", "bbk_controller.md");
  const marker = "## Compiled procedures manifest";
  if (!source.includes(marker) || !source.includes("## End compiled procedures")) {
    throw new Error("installed OMP controller projection has no closed compiled-procedure tail");
  }
  // Runtime data is inserted before the compiled procedure tail so the
  // generated primary procedure remains the final semantic instruction.
  return source.replace(marker, `${runtimeBlock(ctx)}

${marker}`);
}
function buildControllerSystemPrompt(ctx) {
  roleCatalogue();
  return generatedControllerProjection(ctx);
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
  const ACTIVE_STATUSES = new Set(["pending", "queued", "running", "waiting", "retrying", "starting", "waking", "busy"]);
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
    if (raw === "active" || raw === "working" || raw === "revived" || raw === "woken" || raw === "injected") return "running";
    if (raw === "idle") return "parked";
    return raw || fallback;
  }
  function statusState(item) {
    const taskStatus = item?.taskStatus ? statusOf(item.taskStatus) : statusOf(item?.progress?.status);
    const peerStatus = item?.peerStatus ? statusOf(item.peerStatus) : null;
    const taskUpdated = Number(item?.taskStatusUpdated || 0);
    const peerUpdated = Number(item?.peerStatusUpdated || 0);
    const peerCurrent = Boolean(peerStatus && peerUpdated >= taskUpdated);
    if (peerCurrent) {
      return {
        status: peerStatus,
        source: item.peerSource || "coordination",
        taskStatus,
        peerStatus,
        peerCurrent,
        wakeOutcome: item.peerOutcome || null,
      };
    }
    return {
      status: taskStatus,
      source: item?.taskSource || item?.source || "task",
      taskStatus,
      peerStatus,
      peerCurrent,
      wakeOutcome: null,
    };
  }
  function effectiveStatus(item) {
    return statusState(item).status;
  }
  function effectiveProgress(item) {
    const state = statusState(item);
    const peerIsCurrent = state.peerStatus && Number(item?.peerStatusUpdated || 0) >= Number(item?.taskStatusUpdated || 0);
    return {
      ...(item?.progress || {}),
      status: state.status,
      lastIntent: peerIsCurrent && item?.peerActivity ? item.peerActivity : item?.progress?.lastIntent,
    };
  }
  function activeAgents() {
    return [...agents.values()].filter(item => ACTIVE_STATUSES.has(effectiveStatus(item)));
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
    const latestProgress = effectiveProgress(latest);
    const gauge = contextGauge(latestProgress);
    const activity = progressActivity(latestProgress);
    let line = `BBK · ${active.length} active · ${pathLabel}${gauge ? ` [${gauge}]` : ""}: ${activity}`;

    const otherGauges = active.slice(1, 4).map(item => {
      const otherName = agentLabel(item, 24);
      const otherGauge = contextGauge(effectiveProgress(item), { short: true });
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
      raw?.agentName, progress?.agentName, raw?.displayName, progress?.displayName,
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
      .filter(item => !ACTIVE_STATUSES.has(effectiveStatus(item)))
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
      const observedStatus = progress.status ?? raw.status ?? inferredTerminalStatus
        ?? (source === "progress" || source === "nested-progress" ? "running" : undefined);
      const hasTaskStatusEvidence = observedStatus !== undefined && observedStatus !== null
        && String(observedStatus).trim() !== "";
      const status = statusOf(
        observedStatus,
        previous?.taskStatus || previous?.progress?.status || (source === "lifecycle" ? "pending" : "running"),
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
      const updateSequence = ++sequence;
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
        taskSource: hasTaskStatusEvidence || !previous ? source : previous?.taskSource || source,
        taskStatus: hasTaskStatusEvidence || !previous ? status : previous?.taskStatus || status,
        taskStatusUpdated: hasTaskStatusEvidence || !previous
          ? updateSequence
          : Number(previous?.taskStatusUpdated || 0),
        peerStatus: previous?.peerStatus || null,
        peerStatusUpdated: Number(previous?.peerStatusUpdated || 0),
        peerSource: previous?.peerSource || null,
        peerOutcome: previous?.peerOutcome || null,
        peerActivity: previous?.peerActivity || "",
        progress: mergedProgress,
        updated: updateSequence,
        started: previous?.started || updateSequence,
        completed: hasTaskStatusEvidence
          ? TERMINAL_STATUSES.has(status) ? updateSequence : null
          : previous?.completed || null,
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
  function identityValues(raw) {
    return [raw?.id, raw?.to, raw?.name, raw?.agentId, raw?.agent_id, raw?.peerId, raw?.peer_id]
      .filter(value => typeof value === "string" && value.trim())
      .map(value => value.trim());
  }
  function coordinationKey(raw) {
    const parentKey = resolveAlias(raw?.parentId || raw?.parent_id || raw?.parentName, null);
    for (const value of identityValues(raw)) {
      const resolved = resolveAlias(value, parentKey) || resolveAlias(value, null);
      if (resolved) return resolved;
      const exact = [...agents.values()].find(item => item.id === value || item.name === value || item.key === value);
      if (exact) return exact.key;
    }
    return null;
  }
  function ensureCoordinationRecord(raw) {
    let key = coordinationKey(raw);
    const role = roleFrom(raw, raw);
    if (key || !role) return key;
    const id = String(identityValues(raw)[0] || role);
    const parentKey = resolveAlias(raw?.parentId || raw?.parent_id || raw?.parentName, null);
    key = `${parentKey || "Main"}/${role}/${id}`;
    const updateSequence = ++sequence;
    const item = {
      key,
      id,
      name: String(raw?.name || raw?.id || id),
      agent: role,
      description: oneLine(raw?.activity || raw?.description || "", 240),
      parentKey: parentKey || null,
      depth: parentKey && agents.get(parentKey) ? Number(agents.get(parentKey).depth || 0) + 1 : 0,
      detached: true,
      model: "",
      sessionId: "",
      sessionFile: "",
      toolCallId: "",
      parentToolCallId: "",
      agentSource: "coordination",
      assignment: oneLine(raw?.activity || "", 240),
      index: undefined,
      source: "coordination-discovery",
      taskSource: null,
      taskStatus: "unknown",
      taskStatusUpdated: 0,
      peerStatus: null,
      peerStatusUpdated: 0,
      peerSource: null,
      peerOutcome: null,
      peerActivity: "",
      progress: { id, name: String(raw?.name || raw?.id || id), agent: role, status: "unknown" },
      updated: updateSequence,
      started: updateSequence,
      completed: null,
    };
    agents.set(key, item);
    aliases.set(key, key);
    for (const value of identityValues(raw)) {
      aliases.set(`id:${value}`, key);
      aliases.set(`${parentKey || "Main"}::id:${value}`, key);
    }
    return key;
  }
  function applyCoordinationStatus(raw, rawStatus, source, outcome = null) {
    const key = ensureCoordinationRecord(raw);
    if (!key) return false;
    const previous = agents.get(key);
    if (!previous) return false;
    const parentKey = resolveAlias(raw?.parentId || raw?.parent_id || raw?.parentName, null) || previous.parentKey || null;
    const status = statusOf(rawStatus, "running");
    const updateSequence = ++sequence;
    const activity = oneLine(raw?.activity || raw?.lastActivityText || previous.peerActivity || "", 240);
    const item = {
      ...previous,
      parentKey,
      depth: parentKey && agents.get(parentKey) ? Number(agents.get(parentKey).depth || 0) + 1 : previous.depth || 0,
      description: activity || previous.description || "",
      assignment: activity || previous.assignment || "",
      source,
      peerStatus: status,
      peerStatusUpdated: updateSequence,
      peerSource: source,
      peerOutcome: outcome || null,
      peerActivity: activity,
      updated: updateSequence,
    };
    agents.set(key, item);
    for (const value of identityValues(raw)) {
      aliases.set(`id:${value}`, key);
      aliases.set(`${parentKey || "Main"}::id:${value}`, key);
    }
    return true;
  }
  function updateCoordinationResult(event) {
    if (!enabled || !event || typeof event !== "object") return;
    const toolName = String(event.toolName || event.tool_name || "").trim().toLowerCase();
    if (!BBK_COORDINATION_TOOL_NAMES.has(toolName)) return;
    const nestedDetails = event.result?.details && typeof event.result.details === "object"
      ? event.result.details
      : {};
    const directDetails = event.details && typeof event.details === "object" ? event.details : {};
    const details = { ...nestedDetails, ...directDetails };
    let changed = false;
    const peers = Array.isArray(details.peers) ? details.peers.filter(item => item && typeof item === "object") : [];
    // First establish every peer alias so child-parent relationships are stable even
    // when a roster is not topologically ordered.
    for (const peer of peers) ensureCoordinationRecord(peer);
    for (const peer of peers) {
      changed = applyCoordinationStatus(peer, peer.status || "running", `${toolName}:roster`) || changed;
    }
    const runningAgents = Array.isArray(details.agents) ? details.agents.filter(item => item && typeof item === "object") : [];
    for (const agent of runningAgents) {
      changed = applyCoordinationStatus(agent, agent.status || "running", `${toolName}:running-agents`) || changed;
    }
    const receipts = Array.isArray(details.receipts) ? details.receipts.filter(item => item && typeof item === "object") : [];
    for (const receipt of receipts) {
      const outcome = String(receipt.outcome || receipt.status || receipt.delivery || "").trim().toLowerCase();
      if (!BBK_WAKE_OUTCOMES.has(outcome)) continue;
      changed = applyCoordinationStatus(receipt, "running", `${toolName}:receipt`, outcome) || changed;
    }
    if (!changed) return;
    trimHistory();
    render();
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
    const state = statusState(item);
    const gauge = contextGauge(effectiveProgress(item));
    const model = item.model ? ` · ${item.model}` : "";
    const detached = item.detached ? " · detached" : " · synchronous";
    const splitStatus = state.peerCurrent && state.peerStatus !== state.taskStatus
      ? ` · task ${state.taskStatus} · peer ${state.peerStatus}${state.wakeOutcome ? ` (${state.wakeOutcome})` : ""}`
      : state.wakeOutcome && state.source.endsWith(":receipt")
        ? ` · ${state.wakeOutcome}`
        : "";
    return `${prefix}${agentLabel(item, 72)} [${item.agent}] · ${state.status}${splitStatus}${gauge ? ` · ${gauge}` : ""}${model}${detached}`;
  }
  function treeLines({ activeOnly = false } = {}) {
    const included = new Set(
      [...agents.values()]
        .filter(item => !activeOnly || ACTIVE_STATUSES.has(effectiveStatus(item)))
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
      status: effectiveStatus(item),
      task_status: statusState(item).taskStatus,
      peer_status: statusState(item).peerStatus,
      peer_status_current: statusState(item).peerCurrent,
      status_source: statusState(item).source,
      wake_outcome: statusState(item).wakeOutcome,
      detached: item.detached,
      spawn_mode: item.detached ? "detached" : "synchronous",
      model: item.model || null,
      task: item.description || null,
      assignment: item.assignment || null,
      activity: progressActivity(effectiveProgress(item)),
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
      .filter(item => !activeOnly || ACTIVE_STATUSES.has(effectiveStatus(item)))
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
  return { setMode, reset, updateProgress, updateLifecycle, updateCoordinationResult, snapshot, details, dispose };
}

function registerAgentViewCommand(pi, activity, timing) {
  function campaignPrefix(ctx) {
    const value = timing?.snapshot?.(ctx);
    if (!value?.current_waiting_on_user) return { value, text: "" };
    const ids = value.request_ids?.length ? value.request_ids.join(", ") : "not exposed by host";
    return {
      value,
      text: [
        `Campaign: WAITING_ON_USER since ${value.waiting_since || "unknown"}`,
        `Pending request IDs: ${ids}`,
        `Independent work active: ${value.independent_work_active}`,
      ].join("\n"),
    };
  }
  pi.registerCommand("bbk:agents", {
    description: "show the complete BBK sub-agent tree, current user-wait state, or inspect one nested agent",
    handler: async (first, second) => {
      const { args, ctx } = commandInvocation(first, second);
      const tokens = splitArgs(args);
      const mode = String(tokens[0] || "all").toLowerCase();
      const campaign = campaignPrefix(ctx);
      let text;
      if (mode === "json") {
        const value = activity.snapshot({ activeOnly: false });
        text = JSON.stringify({ ...value, controller_timing: campaign.value }, null, 2);
      } else if (mode === "active") {
        const value = activity.snapshot({ activeOnly: true });
        text = [
          `BBK agents: ${value.active_count} active / ${value.agent_count} known`,
          campaign.text,
          value.tree.join("\n"),
        ].filter(Boolean).join("\n");
      } else if (mode === "all" || mode === "tree") {
        const value = activity.snapshot({ activeOnly: false });
        text = [
          `BBK agents: ${value.active_count} active / ${value.agent_count} known`,
          campaign.text,
          value.tree.join("\n"),
        ].filter(Boolean).join("\n");
      } else {
        const selector = mode === "details" ? tokens.slice(1).join(" ") : tokens.join(" ");
        if (!selector) {
          text = "Usage: /bbk:agents [all|active|json|details <agent-id-or-name>]";
        } else {
          const found = activity.details(selector);
          text = found.length
            ? JSON.stringify({ schema: "bbk.omp-agent-details.v1", status: "PASS", matches: found, controller_timing: campaign.value }, null, 2)
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
  let providerRequestSequence = 0;
  let turnSequence = 0;
  const expectedBySession = new Map();
  const latestProviderBySession = new Map();
  const integrityBySession = new Map();
  const recordedReplacementDigests = new Set();
  const recordedCompilationEvents = new Set();

  function appendPromptReceipt(data) {
    if (typeof pi.appendEntry !== "function") return;
    pi.appendEntry(BBK_PROMPT_RECEIPT_ENTRY_TYPE, {
      schema: BBK_PROMPT_RECEIPT_SCHEMA,
      package_version: version,
      observed_at: new Date().toISOString(),
      ...data,
    });
  }
  function appendPromptCompilationEvent(identity, effective, sessionId, reused) {
    if (typeof pi.appendEntry !== "function") return;
    const template = promptCompilationTemplate(identity);
    if (!template) return;
    const eventKey = `${sessionId}:${turnSequence}:${identity?.role || identity?.kind}:${effective.sha256}:${reused ? "reuse" : "compile"}`;
    if (recordedCompilationEvents.has(eventKey)) return;
    recordedCompilationEvents.add(eventKey);
    pi.appendEntry(BBK_PROMPT_COMPILATION_ENTRY_TYPE, {
      ...template,
      event: reused ? "PROMPT_REUSED" : "PROMPT_COMPILED",
      logical_child_id: `omp:${sessionId}:${identity?.role || "bbk_controller"}`,
      physical_attempt_id: `omp:${sessionId}:${turnSequence}`,
      effective_prompt_sha256: effective.sha256,
      source_reads_by_compiler: reused ? 0 : Number(template.source_reads_by_compiler || template.procedure_ids.length),
      procedure_reads_by_model: 0,
      reused: Boolean(reused),
      observed_at: new Date().toISOString(),
    });
  }
  function expectedReceiptSummary(binding) {
    if (!binding) return null;
    return {
      block_count: binding.block_count,
      length: binding.length,
      sha256: binding.sha256,
      binding_source: binding.source || "before-agent-start",
    };
  }
  function rememberExpectedPrompt(sessionId, binding) {
    // Session identifiers are the durable separation boundary. Retain bindings
    // across wake/resume/navigation events in the same host process, but keep
    // the cache bounded so long-lived OMP processes cannot accumulate entries
    // without limit.
    if (expectedBySession.has(sessionId)) expectedBySession.delete(sessionId);
    expectedBySession.set(sessionId, binding);
    while (expectedBySession.size > 128) {
      expectedBySession.delete(expectedBySession.keys().next().value);
    }
  }
  function branchEntries(ctx) {
    try {
      const values = ctx?.sessionManager?.getBranch?.();
      return Array.isArray(values) ? values : [];
    } catch {
      return [];
    }
  }
  function receiptMatchesCandidate(receipt, candidate, sessionId) {
    const effective = receipt?.effective;
    return receipt?.schema === BBK_PROMPT_RECEIPT_SCHEMA
      && receipt?.package_version === version
      && receipt?.phase === "before_agent_start"
      && receipt?.action === "BOUND"
      && receipt?.session_id === sessionId
      && receipt?.prompt_kind === candidate.prompt_kind
      && (receipt?.role || null) === (candidate.role || null)
      && effective?.block_count === candidate.block_count
      && effective?.length === candidate.length
      && effective?.sha256 === candidate.sha256;
  }
  function recoverCandidateFromDurableReceipt(text, ctx) {
    const candidate = validatedPromptMarkerCandidate(text);
    if (!candidate) return null;
    const sessionId = promptSessionIdentity(ctx);
    const receipt = [...branchEntries(ctx)].reverse().find(entry => (
      entry?.type === "custom"
      && entry?.customType === BBK_PROMPT_RECEIPT_ENTRY_TYPE
      && receiptMatchesCandidate(entry?.data, candidate, sessionId)
    ));
    if (!receipt) return null;
    return { ...candidate, source: "session-receipt-digest-recovery" };
  }
  function recoverBoundPromptCandidate(text, ctx) {
    const candidate = validatedPromptMarkerCandidate(text);
    if (!candidate) return null;
    const sessionId = promptSessionIdentity(ctx);
    const current = expectedBySession.get(sessionId);
    if (current?.text === candidate.text
      && current.sha256 === candidate.sha256
      && current.prompt_kind === candidate.prompt_kind
      && (current.role || null) === (candidate.role || null)) {
      return current;
    }
    return recoverCandidateFromDurableReceipt(candidate.text, ctx);
  }
  function bindExpectedPrompt(sourceBlocks, effectiveBlocks, status, ctx, source = "before-agent-start") {
    const sessionId = promptSessionIdentity(ctx);
    const sourceSummary = promptReceiptSummary(sourceBlocks);
    const effectiveValues = promptBlocksFromValue(effectiveBlocks);
    const effectiveText = effectiveValues.join("\n\n");
    const effective = promptReceiptSummary(effectiveValues);
    const identity = promptOuterIdentity(effectiveText);
    const binding = {
      ...effective,
      text: effectiveText,
      role: identity.role,
      prompt_kind: identity.kind,
      source,
    };
    rememberExpectedPrompt(sessionId, binding);
    const key = `${sessionId}:${status}:${identity.role || identity.kind}:${effective.sha256}`;
    if (recordedReplacementDigests.has(key)) {
      appendPromptCompilationEvent(identity, effective, sessionId, true);
      return binding;
    }
    recordedReplacementDigests.add(key);
    const genericDetected = sourceHasGenericPromptMaterial(sourceBlocks);
    appendPromptReceipt({
      phase: "before_agent_start",
      action: "BOUND",
      status,
      session_id: sessionId,
      turn_sequence: turnSequence,
      prompt_kind: identity.kind,
      role: identity.role,
      cwd: String(ctx?.cwd || process.cwd()),
      source: sourceSummary,
      effective,
      binding_source: source,
      generic_omp_contamination_detected: genericDetected,
      generic_omp_contamination_removed: genericDetected && ["agent", "controller"].includes(identity.kind),
      enforcement: "PROVIDER_PAYLOAD_GUARD_BOUND",
      raw_prompt_persisted: false,
    });
    appendPromptCompilationEvent(identity, effective, sessionId, false);
    return binding;
  }
  function setPromptIntegrityUi(ctx, sessionId, action, detail = "") {
    const previous = integrityBySession.get(sessionId);
    const unresolved = ["BLOCKED", "UNVERIFIABLE"].includes(action);
    integrityBySession.set(sessionId, {
      action,
      unresolved,
      detail: oneLine(detail, 240),
      observed_at: new Date().toISOString(),
    });
    if (unresolved) {
      ctx?.ui?.setStatus?.(
        BBK_PROMPT_INTEGRITY_STATUS_KEY,
        `BBK prompt ${action.toLowerCase()}${detail ? ` · ${oneLine(detail, 96)}` : ""}`,
      );
      return;
    }
    if (previous?.unresolved) ctx?.ui?.setStatus?.(BBK_PROMPT_INTEGRITY_STATUS_KEY, undefined);
  }
  function recoverExpectedPrompt(adapter, ctx) {
    const sessionId = promptSessionIdentity(ctx);
    const current = expectedBySession.get(sessionId);
    if (current?.text) return current;

    // A cold wake or process/session restoration can lose the in-memory prompt
    // body. The provider payload may carry the exact previously bound BBK block,
    // but a closed marker and canonical embedded role body are not authority on
    // their own: arbitrary text could have been inserted inside the outer block.
    // Authenticate every recovered child/failure prompt against the SHA-256,
    // length, role, kind, and session identity persisted by before_agent_start.
    // User messages are never part of adapter.blocks and are never scanned.
    if (adapter?.blocks?.length) {
      const canonical = canonicalPromptBlockFromProvider(adapter);
      if (canonical) {
        const candidate = validatedPromptMarkerCandidate(canonical);
        if (candidate?.prompt_kind === "controller") {
          ensure(ctx);
          if (enabled) {
            const text = buildControllerSystemPrompt(ctx);
            return bindExpectedPrompt([], [text], "RECOVERED_AT_PROVIDER_BOUNDARY", ctx, "mode-state-controller-rebuild");
          }
        } else {
          const recovered = recoverCandidateFromDurableReceipt(canonical, ctx);
          if (recovered) {
            return bindExpectedPrompt([], [recovered.text], "RECOVERED_AT_PROVIDER_BOUNDARY", ctx, recovered.source);
          }
        }
      }
    }

    ensure(ctx);
    const observed = (adapter?.blocks || []).join("\n\n");
    const looksLikeChild = observed.includes(BBK_AGENT_PROMPT_MARKER)
      || observed.includes("<bbk-agent-replacement");
    if (enabled && !looksLikeChild) {
      const text = buildControllerSystemPrompt(ctx);
      return bindExpectedPrompt([], [text], "RECOVERED_AT_PROVIDER_BOUNDARY", ctx, "mode-state-controller-rebuild");
    }
    return null;
  }
  function recordProviderReceipt(data, ctx) {
    const sessionId = promptSessionIdentity(ctx);
    const receipt = {
      phase: "provider_request_finalization",
      hook: "before_provider_request",
      session_id: sessionId,
      turn_sequence: turnSequence,
      request_sequence: providerRequestSequence,
      cwd: String(ctx?.cwd || process.cwd()),
      raw_prompt_persisted: false,
      raw_provider_payload_persisted: false,
      enforcement: "PROVIDER_PAYLOAD_REWRITE_OR_ABORT",
      extension_order_finality: "ORDER_DEPENDENT_NO_POST_CHAIN_HOOK",
      ...data,
    };
    latestProviderBySession.set(sessionId, receipt);
    appendPromptReceipt(receipt);
  }
  async function blockProviderRequest(ctx, reason) {
    let abortSignalled = false;
    let abortError = null;
    try {
      if (typeof ctx?.abort === "function") {
        await Promise.resolve(ctx.abort());
        abortSignalled = true;
      }
    } catch (error) {
      abortError = oneLine(error?.message || error, 240);
    }
    const sessionId = promptSessionIdentity(ctx);
    setPromptIntegrityUi(ctx, sessionId, "BLOCKED", reason);
    ctx?.ui?.notify?.(`BBK blocked a provider request because prompt integrity could not be established: ${reason}`, "error");
    return {
      abortSignalled,
      abortError,
      payload: blockedProviderPayload(reason),
    };
  }
  async function finalizeProviderPrompt(event, ctx) {
    providerRequestSequence += 1;
    const payload = event?.payload ?? event?.request;
    const payloadSource = event?.payload !== undefined ? "event.payload" : event?.request !== undefined ? "legacy-event.request" : "missing";
    const adapter = providerPayloadAdapter(payload);
    const expected = recoverExpectedPrompt(adapter, ctx);
    let model = null;
    try { model = ctx?.model || ctx?.getModel?.() || null; } catch {}
    const modelBinding = {
      provider: model?.provider || model?.providerId || null,
      model: model?.id || model?.model || null,
    };

    if (!expected?.text) {
      ensure(ctx);
      const observedSystemText = (adapter?.blocks || []).join("\n\n");
      const bbkMarkerObserved = /<bbk-(?:controller-system|agent-system|agent-replacement|prompt-assembly-failure)\b/i.test(observedSystemText);
      // The extension is installed outside BBK mode as well. Ordinary OMP
      // requests must pass through untouched; only an active BBK controller or
      // a provider payload carrying BBK identity is subject to this guard.
      if (!enabled && !bbkMarkerObserved) return undefined;
      const blocked = await blockProviderRequest(ctx, "exact session-bound BBK prompt binding unavailable");
      recordProviderReceipt({
        status: "BLOCKED",
        action: "BLOCKED",
        code: "BBK_PROMPT_EXPECTED_UNAVAILABLE",
        prompt_kind: null,
        role: null,
        provider_adapter: adapter?.name || "unsupported",
        provider_payload_source: payloadSource,
        model: modelBinding,
        expected: null,
        observed_before: adapter ? promptReceiptSummary(adapter.blocks) : null,
        sent: promptReceiptSummary([]),
        system_surfaces_observed: adapter?.system_surface_count || 0,
        generic_blocks_removed: adapter?.system_surface_count || 0,
        abort_signalled: blocked.abortSignalled,
        abort_error: blocked.abortError,
        network_send_prevention: blocked.abortSignalled
          ? "HOST_ABORT_SIGNALLED_AND_USER_PAYLOAD_REMOVED"
          : "USER_PAYLOAD_REMOVED_BUT_HOST_ABORT_UNAVAILABLE",
        smallest_next_action: "Restore the BBK mode/role binding and retry the provider turn.",
      }, ctx);
      return blocked.payload;
    }

    if (!adapter) {
      const blocked = await blockProviderRequest(ctx, "unsupported provider payload shape");
      recordProviderReceipt({
        status: "BLOCKED",
        action: "BLOCKED",
        code: "BBK_PROMPT_PROVIDER_ADAPTER_UNAVAILABLE",
        prompt_kind: expected.prompt_kind,
        role: expected.role,
        provider_adapter: "unsupported",
        provider_payload_source: payloadSource,
        model: modelBinding,
        expected: expectedReceiptSummary(expected),
        observed_before: null,
        sent: promptReceiptSummary([]),
        system_surfaces_observed: 0,
        generic_blocks_removed: 0,
        abort_signalled: blocked.abortSignalled,
        abort_error: blocked.abortError,
        network_send_prevention: blocked.abortSignalled
          ? "HOST_ABORT_SIGNALLED_AND_USER_PAYLOAD_REMOVED"
          : "USER_PAYLOAD_REMOVED_BUT_HOST_ABORT_UNAVAILABLE",
        smallest_next_action: "Use a qualified provider payload adapter or update BBK before retrying this provider.",
      }, ctx);
      return blocked.payload;
    }

    const observedText = adapter.blocks.join("\n\n");
    const observed = promptReceiptSummary(adapter.blocks);
    const exact = adapter.blocks.length === 1
      && adapter.system_surface_count === 1
      && observedText === expected.text
      && observed.sha256 === expected.sha256;
    if (exact) {
      const sessionId = promptSessionIdentity(ctx);
      setPromptIntegrityUi(ctx, sessionId, "VERIFIED");
      recordProviderReceipt({
        status: "VERIFIED",
        action: "VERIFIED",
        code: "BBK_PROMPT_PROVIDER_VERIFIED",
        prompt_kind: expected.prompt_kind,
        role: expected.role,
        provider_adapter: adapter.name,
        provider_payload_source: payloadSource,
        model: modelBinding,
        expected: expectedReceiptSummary(expected),
        observed_before: observed,
        sent: observed,
        system_surfaces_observed: adapter.system_surface_count,
        generic_blocks_removed: 0,
        abort_signalled: false,
        network_send_prevention: "NOT_REQUIRED",
        smallest_next_action: "Continue the governed turn.",
      }, ctx);
      return undefined;
    }

    let repairedPayload;
    let repairedAdapter;
    try {
      repairedPayload = adapter.repair(expected.text);
      repairedAdapter = providerPayloadAdapter(repairedPayload);
    } catch {
      repairedPayload = undefined;
      repairedAdapter = null;
    }
    const sentBlocks = repairedAdapter?.blocks || [];
    const sentText = sentBlocks.join("\n\n");
    const sent = repairedAdapter ? promptReceiptSummary(sentBlocks) : null;
    const repaired = repairedAdapter
      && sentBlocks.length === 1
      && repairedAdapter.system_surface_count === 1
      && sentText === expected.text
      && sent.sha256 === expected.sha256;
    if (repaired) {
      const sessionId = promptSessionIdentity(ctx);
      setPromptIntegrityUi(ctx, sessionId, "REPAIRED");
      ctx?.ui?.notify?.("BBK repaired provider-bound prompt contamination before transmission.", "warning");
      recordProviderReceipt({
        status: "REPAIRED",
        action: "REPAIRED",
        code: "BBK_PROMPT_PROVIDER_REPAIRED",
        prompt_kind: expected.prompt_kind,
        role: expected.role,
        provider_adapter: adapter.name,
        provider_payload_source: payloadSource,
        model: modelBinding,
        expected: expectedReceiptSummary(expected),
        observed_before: observed,
        sent,
        system_surfaces_observed: adapter.system_surface_count,
        generic_blocks_removed: removedPromptSurfaceCount(adapter, expected.text),
        abort_signalled: false,
        network_send_prevention: "NOT_REQUIRED",
        smallest_next_action: "Continue with the repaired canonical provider payload.",
      }, ctx);
      return repairedPayload;
    }

    const blocked = await blockProviderRequest(ctx, `provider payload repair failed for ${adapter.name}`);
    recordProviderReceipt({
      status: "BLOCKED",
      action: "BLOCKED",
      code: "BBK_PROMPT_PROVIDER_REPAIR_FAILED",
      prompt_kind: expected.prompt_kind,
      role: expected.role,
      provider_adapter: adapter.name,
      provider_payload_source: payloadSource,
      model: modelBinding,
      expected: expectedReceiptSummary(expected),
      observed_before: observed,
      sent: promptReceiptSummary([]),
      system_surfaces_observed: adapter.system_surface_count,
      generic_blocks_removed: removedPromptSurfaceCount(adapter, expected.text),
      abort_signalled: blocked.abortSignalled,
      abort_error: blocked.abortError,
      network_send_prevention: blocked.abortSignalled
        ? "HOST_ABORT_SIGNALLED_AND_USER_PAYLOAD_REMOVED"
        : "USER_PAYLOAD_REMOVED_BUT_HOST_ABORT_UNAVAILABLE",
      smallest_next_action: "Stop this turn, repair the provider adapter, and rerun from the preserved session state.",
    }, ctx);
    return blocked.payload;
  }
  function promptStatus(ctx) {
    let branch = [];
    try { branch = ctx?.sessionManager?.getBranch?.() || []; } catch {}
    const receipts = (Array.isArray(branch) ? branch : [])
      .filter(entry => entry?.type === "custom" && entry?.customType === BBK_PROMPT_RECEIPT_ENTRY_TYPE)
      .map(entry => entry.data)
      .filter(value => [BBK_PROMPT_RECEIPT_SCHEMA, "bbk.effective-prompt-receipt.v1"].includes(value?.schema));
    const providerReceipts = receipts.filter(receipt => ["provider_request_finalization", "before_provider_request"].includes(receipt?.phase));
    const latestByKey = new Map();
    for (const receipt of receipts) {
      const key = `${receipt.role || receipt.prompt_kind || "unknown"}:${receipt.phase}`;
      latestByKey.set(key, receipt);
    }
    const counts = { verified: 0, repaired: 0, blocked: 0, unverifiable: 0, mismatch_legacy: 0 };
    for (const receipt of providerReceipts) {
      const value = String(receipt.action || receipt.status || "").toUpperCase();
      if (value === "VERIFIED") counts.verified += 1;
      else if (value === "REPAIRED") counts.repaired += 1;
      else if (value === "BLOCKED") counts.blocked += 1;
      else if (["UNAVAILABLE", "ERROR", "UNVERIFIABLE"].includes(value)) counts.unverifiable += 1;
      else if (value === "MISMATCH") counts.mismatch_legacy += 1;
    }
    const sessionId = promptSessionIdentity(ctx);
    const latestProvider = providerReceipts.at(-1) || latestProviderBySession.get(sessionId) || null;
    const latestAction = String(latestProvider?.action || latestProvider?.status || "").toUpperCase();
    const liveIntegrity = integrityBySession.get(sessionId) || null;
    const unresolved = Boolean(liveIntegrity?.unresolved || latestAction === "BLOCKED");
    return {
      schema: BBK_PROMPT_STATUS_SCHEMA,
      package_version: version,
      session_id: sessionId,
      receipt_count: receipts.length,
      provider_request_count: providerReceipts.length,
      counts,
      requests: counts,
      unresolved_failure: unresolved,
      current_action: liveIntegrity?.action || latestAction || null,
      current_guarantee: unresolved
        ? "PROVIDER_REQUEST_BLOCKED_AT_BBK_HOOK_BOUNDARY"
        : ["VERIFIED", "REPAIRED"].includes(latestAction)
          ? "PROVIDER_PAYLOAD_VERIFIED_OR_REPAIRED_AT_BBK_HOOK_BOUNDARY"
          : "NOT_YET_ESTABLISHED",
      finality_boundary: "A later extension handler can still rewrite the payload because OMP exposes no post-chain finalizer to BBK.",
      latest_provider_request: latestProvider,
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
    // Keep exact per-session prompt bindings across ordinary wake, resume,
    // session-switch, branch, and tree navigation events in this process.
    // A different session ID cannot consume another session's binding, and a
    // cold process must authenticate the candidate against a durable receipt.
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
  function exit(ctx) {
    const sessionId = promptSessionIdentity(ctx);
    expectedBySession.delete(sessionId);
    setPromptIntegrityUi(ctx, sessionId, "VERIFIED");
    return persist(false, ctx);
  }
  function promptReplacement(event, ctx) {
    turnSequence += 1;
    const sourceBlocks = systemPromptBlocks(event);
    try {
      const extracted = extractBbkAgentBlock(event);
      if (extracted?.alreadyReplaced) {
        const recovered = recoverBoundPromptCandidate(extracted.replacementBlock, ctx);
        if (!recovered || recovered.prompt_kind !== "agent") {
          throw new Error("BBK agent-replacement prompt has no exact session-bound or receipt-bound canonical identity");
        }
        const effective = [recovered.text];
        bindExpectedPrompt(sourceBlocks, effective, "ALREADY_REPLACED", ctx, recovered.source);
        return { systemPrompt: effective };
      }
      if (extracted) {
        const effective = [buildAgentSystemPrompt(extracted, ctx)];
        bindExpectedPrompt(sourceBlocks, effective, "REPLACED", ctx);
        return { systemPrompt: effective };
      }
      ensure(ctx);
      if (!enabled) return undefined;
      const effective = [buildControllerSystemPrompt(ctx)];
      bindExpectedPrompt(sourceBlocks, effective, "REPLACED", ctx);
      return { systemPrompt: effective };
    } catch (error) {
      const effective = [failClosedSystemPrompt(error, ctx)];
      bindExpectedPrompt(sourceBlocks, effective, "FAIL_CLOSED", ctx);
      return { systemPrompt: effective };
    }
  }
  function currentPromptBinding(ctx) {
    const sessionId = promptSessionIdentity(ctx);
    const live = expectedBySession.get(sessionId);
    if (live) return live;
    let branch = [];
    try { branch = ctx?.sessionManager?.getBranch?.() || []; } catch {}
    for (let index = branch.length - 1; index >= 0; index -= 1) {
      const entry = branch[index];
      if (entry?.type !== "custom" || entry?.customType !== BBK_PROMPT_RECEIPT_ENTRY_TYPE) continue;
      const receipt = entry.data;
      if (receipt?.phase !== "before_agent_start") continue;
      if (receipt?.session_id && receipt.session_id !== sessionId) continue;
      if (receipt?.prompt_kind) return receipt;
    }
    return null;
  }
  function isControllerSession(ctx) {
    return currentPromptBinding(ctx)?.prompt_kind === "controller";
  }
  return {
    enter, exit, restore, ensure, promptReplacement, finalizeProviderPrompt,
    verifyProviderPrompt: finalizeProviderPrompt,
    promptStatus, currentPromptBinding, isControllerSession,
    isEnabled: () => enabled,
  };
}


function createBbkCoordinationThrottle(bbkMode, activity) {
  const states = new Map();

  function stateFor(ctx) {
    const key = promptSessionIdentity(ctx);
    let state = states.get(key);
    if (!state) {
      state = {
        session_id: key,
        dispatch_observed: false,
        dispatched_at_ms: null,
        last_probe_at_ms: null,
        next_probe_at_ms: null,
      };
      states.set(key, state);
    }
    return state;
  }
  function activeBinding(ctx) {
    if (!bbkMode.isEnabled()) return false;
    const binding = bbkMode.currentPromptBinding(ctx);
    // A controller may dispatch in its first governed turn immediately after
    // mode activation. The durable mode state is sufficient before that first
    // prompt receipt is materialized; later calls retain the exact binding.
    return Boolean(binding || bbkMode.ensure(ctx));
  }
  function activeCount() {
    try { return Number(activity?.snapshot?.({ activeOnly: true })?.active_count || 0); }
    catch { return 0; }
  }
  function noteTaskDispatch(ctx) {
    if (!activeBinding(ctx)) return;
    const now = Date.now();
    const state = stateFor(ctx);
    state.dispatch_observed = true;
    state.dispatched_at_ms = now;
    state.next_probe_at_ms = now + BBK_COORDINATION_PROBE_INTERVAL_MS;
  }
  function reset(ctx) {
    states.delete(promptSessionIdentity(ctx));
  }
  function status(ctx) {
    const state = stateFor(ctx);
    return {
      schema: "bbk.omp-coordination-throttle.v1",
      package_version: version,
      session_id: state.session_id,
      minimum_probe_interval_ms: BBK_COORDINATION_PROBE_INTERVAL_MS,
      active_count: activeCount(),
      ...state,
    };
  }
  function waitingJobInput(input) {
    const keys = Object.keys(input || {}).filter(key => !["i", "intent"].includes(key));
    return keys.length === 0;
  }
  function guard(event, ctx) {
    if (!activeBinding(ctx)) return undefined;
    const toolName = String(event?.toolName || event?.tool_name || "").trim().toLowerCase();
    if (!["job", "irc", "hub"].includes(toolName)) return undefined;
    const input = event?.input && typeof event.input === "object" ? event.input : {};
    const state = stateFor(ctx);

    if (toolName === "job") {
      if (Array.isArray(input.cancel) && input.cancel.length) return undefined;
      if (Array.isArray(input.poll) && input.poll.length) {
        return governedBlock(
          "BBK_COORDINATION_SPECIFIC_POLL_FORBIDDEN",
          "specific job polling creates an avoidable wake/probe loop while OMP already auto-delivers task results",
          "When completely blocked, call job with no fields so completion, steering, or the host wait window wakes the turn.",
        );
      }
      if (waitingJobInput(input)) return undefined;
      if (!input.list) return undefined;
    } else {
      const op = String(input.op || "").trim().toLowerCase();
      if (["send", "wait"].includes(op) || input.await === true) return undefined;
      if (!["inbox", "list", "roster"].includes(op)) return undefined;
    }

    const now = Date.now();
    const active = activeCount();
    // Immediately after a task call the lifecycle bus may not yet have emitted
    // its first event. Treat the dispatch as active until the first five-minute
    // observation window expires; completed results will auto-deliver sooner.
    const assumedActive = state.dispatch_observed
      && state.dispatched_at_ms !== null
      && now < Number(state.next_probe_at_ms || 0);
    if (!active && !assumedActive) return undefined;

    const notBefore = Number(state.next_probe_at_ms || 0);
    if (now < notBefore) {
      const remainingMs = Math.max(0, notBefore - now);
      return governedBlock(
        "BBK_COORDINATION_PROBE_TOO_EARLY",
        `non-blocking ${toolName} status probing is rate-limited while BBK children are active; ${remainingMs} ms remain in the minimum interval`,
        "Continue independent work or use one blocking empty job wait/IRC wait. Probe again only after five minutes of silence.",
      );
    }
    state.last_probe_at_ms = now;
    state.next_probe_at_ms = now + BBK_COORDINATION_PROBE_INTERVAL_MS;
    return undefined;
  }
  function dispose(ctx) {
    if (ctx) reset(ctx);
    else states.clear();
  }
  return { guard, noteTaskDispatch, reset, status, dispose };
}

function publishBbkRuntime(mode, activity, coordination) {
  const runtime = Object.freeze({
    schema: "bbk.omp-runtime.v1",
    package_version: version,
    enterMode(ctx) { return mode.enter(ctx); },
    exitMode(ctx) { return mode.exit(ctx); },
    ensureMode(ctx) { return mode.ensure(ctx); },
    isModeEnabled() { return mode.isEnabled(); },
    promptStatus(ctx) { return mode.promptStatus(ctx); },
    activityStatus() { return activity.snapshot({ activeOnly: false }); },
    coordinationStatus(ctx) { return coordination.status(ctx); },
  });
  globalThis[BBK_RUNTIME_SYMBOL] = runtime;
  return runtime;
}


function createArtifactFinalizationGuard(pi, bbkMode) {
  let state = {
    schema: BBK_ARTIFACT_FINALIZATION_SCHEMA,
    package_version: version,
    required: false,
    finalization_observed: false,
    satisfied: false,
    publication_receipt: null,
    package_id: null,
    revision: null,
    content_sha256: null,
    last_result: null,
    observed_at: null,
  };
  let loaded = false;
  let statusVisible = false;

  function branchEntries(ctx) {
    try {
      const values = ctx?.sessionManager?.getBranch?.();
      return Array.isArray(values) ? values : [];
    } catch { return []; }
  }
  function textParts(value, result = []) {
    if (typeof value === "string") {
      result.push(value);
      return result;
    }
    if (!value || typeof value !== "object") return result;
    if (Array.isArray(value)) {
      for (const item of value) textParts(item, result);
      return result;
    }
    if (typeof value.text === "string") result.push(value.text);
    if (typeof value.content === "string" || Array.isArray(value.content)) textParts(value.content, result);
    return result;
  }
  function userTextsFromBranch(ctx) {
    const result = [];
    for (const entry of branchEntries(ctx)) {
      const message = entry?.message || entry;
      const role = String(message?.role || entry?.role || "").toLowerCase();
      if (entry?.type !== "message" || role !== "user") continue;
      textParts(message?.content, result);
    }
    return result;
  }
  function restore(ctx) {
    let restored = null;
    for (const entry of branchEntries(ctx)) {
      if (entry?.type === "custom" && entry?.customType === BBK_ARTIFACT_FINALIZATION_ENTRY_TYPE
        && entry?.data?.schema === BBK_ARTIFACT_FINALIZATION_SCHEMA) {
        restored = entry.data;
      }
    }
    if (restored) state = { ...state, ...restored };
    loaded = true;
    publishUi(ctx);
    return state;
  }
  function ensure(ctx) {
    if (!loaded) restore(ctx);
    return state;
  }
  function publishUi(ctx) {
    if (!state.required && !state.finalization_observed) {
      if (statusVisible) {
        ctx?.ui?.setStatus?.(BBK_ARTIFACT_FINALIZATION_STATUS_KEY, undefined);
        statusVisible = false;
      }
      return;
    }
    const label = state.satisfied
      ? `BBK artifact finalized · ${state.package_id || "package"}@${state.revision || "?"}`
      : state.required
        ? "BBK artifact finalization required · pending"
        : "BBK finalized implementation stale · successor required";
    ctx?.ui?.setStatus?.(BBK_ARTIFACT_FINALIZATION_STATUS_KEY, label);
    statusVisible = true;
  }
  function persist(next, ctx) {
    state = {
      ...state,
      ...next,
      schema: BBK_ARTIFACT_FINALIZATION_SCHEMA,
      package_version: version,
      observed_at: new Date().toISOString(),
    };
    loaded = true;
    if (typeof pi.appendEntry === "function") pi.appendEntry(BBK_ARTIFACT_FINALIZATION_ENTRY_TYPE, state);
    publishUi(ctx);
    return state;
  }
  function textRequiresArtifactFinalization(text) {
    const value = String(text || "");
    if (!BBK_ARTIFACT_FINALIZE_MARKER_RE.test(value)) return false;
    if (BBK_ARTIFACT_FINALIZE_NEGATION_RE.test(value)) return false;
    return BBK_ARTIFACT_FINALIZE_REQUIREMENT_RE.test(value);
  }
  function detectRequirement(event, ctx) {
    if (!bbkMode.isEnabled() || !bbkMode.isControllerSession(ctx)) return false;
    ensure(ctx);
    if (state.required) return true;
    const candidates = [];
    if (typeof event?.prompt === "string") candidates.push(event.prompt);
    if (typeof event?.userPrompt === "string") candidates.push(event.userPrompt);
    candidates.push(...userTextsFromBranch(ctx));
    if (!candidates.some(textRequiresArtifactFinalization)) return false;
    persist({
      required: true,
      requirement: "EXPLICIT_BBK_ARTIFACT_FINALIZE",
      last_result: state.satisfied && state.publication_receipt ? "REQUIRED_SATISFIED" : "REQUIRED",
      ...(!state.satisfied ? {
        publication_receipt: null,
        package_id: null,
        revision: null,
        content_sha256: null,
      } : {}),
    }, ctx);
    return true;
  }
  function normalizeToolName(event) {
    return String(event?.toolName ?? event?.tool_name ?? event?.name ?? "").trim();
  }
  function resultDetails(event) {
    for (const candidate of [event?.details, event?.result?.details, event?.result, event?.output?.details]) {
      if (candidate && typeof candidate === "object" && !Array.isArray(candidate)) return candidate;
    }
    return {};
  }
  function observeToolResult(event, ctx) {
    if (!bbkMode.isControllerSession(ctx)) return;
    ensure(ctx);
    const toolName = normalizeToolName(event);
    const details = resultDetails(event);
    if (toolName === "bbk_artifact_finalize") {
      const passed = details?.status === "PASS" && typeof details?.publicationReceipt === "string";
      if (!passed && !state.required) return;
      persist({
        finalization_observed: passed || state.finalization_observed,
        // A failed later attempt is evidence about that attempt, not proof
        // that an earlier bound publication became stale.  Preserve the
        // earlier satisfaction state; the completion guard will re-run
        // freshness against it and invalidate it only on actual drift.
        satisfied: passed ? true : state.satisfied,
        publication_receipt: passed ? details.publicationReceipt : state.publication_receipt,
        package_id: passed ? details.packageId || null : state.package_id,
        revision: passed ? details.revision || null : state.revision,
        content_sha256: passed ? details.contentSha256 || null : state.content_sha256,
        last_result: passed ? "FINALIZED" : String(details?.code || details?.status || "FAILED"),
      }, ctx);
      return;
    }
    if (toolName === "bbk_artifact_freshness" && details?.status === "PASS" && typeof details?.publicationReceipt === "string") {
      persist({
        finalization_observed: true,
        satisfied: details.sourceStatus !== "STALE",
        publication_receipt: details.publicationReceipt,
        package_id: details.packageId || state.package_id,
        revision: details.revision || state.revision,
        content_sha256: details.contentSha256 || state.content_sha256,
        source_status: details.sourceStatus || "NOT_BOUND",
        last_result: "FRESHNESS_VERIFIED",
        handoff_observed: null,
      }, ctx);
      return;
    }
    if (toolName === "bbk_handoff_create" && state.required && !state.satisfied && details?.status === "PASS") {
      persist({
        last_result: "HANDOFF_DOES_NOT_SATISFY_FINALIZATION",
        handoff_observed: details?.output || details?.outputRoot || details?.path || null,
      }, ctx);
      ctx?.ui?.notify?.("BBK recorded the handoff, but it does not satisfy the explicit artifact-finalization requirement.", "warning");
    }
  }
  function terminalAssistantMessage(event) {
    const message = event?.message || event;
    if (String(message?.role || "").toLowerCase() !== "assistant") return null;
    const content = message?.content;
    if (Array.isArray(content) && content.some(item => {
      const type = String(item?.type || "").toLowerCase();
      return type === "toolcall" || type === "tool_call" || type === "tooluse" || type === "tool_use";
    })) return null;
    const stop = String(message?.stopReason || message?.stop_reason || "").toLowerCase();
    if (stop.includes("tool")) return null;
    const text = textParts(content, []).join("\n");
    if (!BBK_COMPLETION_CLAIM_RE.test(text)) return null;
    return message;
  }
  function replacementMessage(message, text) {
    return {
      ...message,
      role: "assistant",
      content: [{ type: "text", text }],
    };
  }
  async function finalizeMessage(event, ctx) {
    const message = terminalAssistantMessage(event);
    if (!message || !bbkMode.isEnabled() || !bbkMode.isControllerSession(ctx)) return undefined;
    detectRequirement(event, ctx);
    ensure(ctx);
    if (!state.required && !state.finalization_observed) return undefined;
    if (!state.satisfied || !state.publication_receipt) {
      if (state.finalization_observed && state.publication_receipt) {
        const text = [
          "BBK completion relay blocked: the implementation changed after its most recent artifact-finalization publication and no fresh successor publication is bound to this session.",
          "The prior publication receipt remains historical evidence; it does not describe the current live source tree.",
          "Smallest next action: rerun the relevant local checks and finalize a successor revision before reporting completion.",
        ].join("\n\n");
        persist({ last_result: "FINAL_RELAY_BLOCKED_STALE" }, ctx);
        ctx?.ui?.notify?.("BBK blocked a completion relay because the latest finalized implementation is stale.", "error");
        return { message: replacementMessage(message, text) };
      }
      const text = [
        "BBK completion relay blocked: the user explicitly required `bbk artifact finalize`, but no successful artifact-finalization publication receipt is bound to this session.",
        "A sealed handoff, passing tests, or an unsealed directory is not a substitute.",
        "Smallest next action: run `bbk_artifact_finalize` in one-shot software mode (or the exact CLI), verify its PASS result, then issue a new completion report.",
      ].join("\n\n");
      persist({ last_result: "FINAL_RELAY_BLOCKED_UNFINALIZED" }, ctx);
      ctx?.ui?.notify?.("BBK blocked a completion relay because required artifact finalization is unresolved.", "error");
      return { message: replacementMessage(message, text) };
    }
    const value = await runBbk([
      "artifact", "freshness", state.publication_receipt,
      "--root", String(ctx?.cwd || process.cwd()),
    ], ctx?.cwd || process.cwd());
    const details = value?.details || {};
    if (value?.code !== 0 || details?.status !== "PASS") {
      const changed = Array.isArray(details?.findings)
        ? details.findings.filter(item => item?.path).slice(0, 5).map(item => item.path).join(", ")
        : "";
      const text = [
        "BBK completion relay blocked: the finalized artifact package is no longer fresh against the live implementation source set.",
        changed ? `Changed or missing source paths: ${changed}.` : `Freshness status: ${String(details?.sourceStatus || details?.status || "ERROR")}.`,
        "Smallest next action: rerun the relevant local checks and finalize a successor revision from the current source tree before reporting completion.",
      ].join("\n\n");
      persist({ satisfied: false, last_result: "FINAL_RELAY_BLOCKED_STALE" }, ctx);
      ctx?.ui?.notify?.("BBK blocked a completion relay because the finalized implementation is stale.", "error");
      return { message: replacementMessage(message, text) };
    }
    persist({ last_result: "FINAL_RELAY_FRESHNESS_VERIFIED" }, ctx);
    return undefined;
  }
  function reset(ctx) {
    state = {
      schema: BBK_ARTIFACT_FINALIZATION_SCHEMA,
      package_version: version,
      required: false,
      finalization_observed: false,
      satisfied: false,
      publication_receipt: null,
      package_id: null,
      revision: null,
      content_sha256: null,
      last_result: null,
      observed_at: null,
    };
    loaded = false;
    return restore(ctx);
  }
  function dispose(ctx) {
    state = { ...state, required: false, finalization_observed: false, satisfied: false };
    loaded = false;
    if (statusVisible) {
      ctx?.ui?.setStatus?.(BBK_ARTIFACT_FINALIZATION_STATUS_KEY, undefined);
      statusVisible = false;
    }
  }
  return { detectRequirement, observeToolResult, finalizeMessage, reset, restore, dispose, snapshot: () => ({ ...state }) };
}


function createBbkTimingController(pi, activity) {
  const WAITING_STATUS_KEY = "bbk-waiting-on-user";
  const SUBAGENT_ACTIVE = new Set(["started", "starting", "pending", "queued", "running", "active", "busy", "working", "woken", "revived", "injected"]);
  const SUBAGENT_TERMINAL = new Set(["completed", "complete", "done", "failed", "error", "cancelled", "canceled", "aborted", "stopped", "terminated"]);
  let sequence = 0;
  let sessionStartedAtMs = Date.now();
  let sessionStartedAt = new Date(sessionStartedAtMs).toISOString();
  let subagentStarts = new Map();
  let subagentIntervals = [];
  let providerStarts = [];
  let providerIntervals = [];
  let toolStarts = new Map();
  let toolIntervals = [];
  let askStarts = new Map();
  let askIntervals = [];
  let blockedProviderRequests = 0;
  let waitingStatusVisible = false;
  const unsubscribe = [];

  function nowMs() { return Date.now(); }
  function iso(value) { return new Date(value).toISOString(); }
  function eventId(event, prefix) {
    const raw = event?.toolCallId ?? event?.tool_call_id ?? event?.requestId ?? event?.request_id
      ?? event?.taskId ?? event?.task_id ?? event?.agentId ?? event?.agent_id ?? event?.id;
    if (raw !== undefined && raw !== null && String(raw).trim()) return String(raw);
    sequence += 1;
    return `${prefix}-${sequence}`;
  }
  function normalizeToolName(event) {
    return String(event?.toolName ?? event?.tool_name ?? event?.name ?? "").trim();
  }
  function normalizedStatus(event) {
    const value = event?.status ?? event?.progress?.status ?? event?.state ?? event?.outcome;
    return String(value || "").trim().toLowerCase();
  }
  function requestIds(value) {
    const result = new Set();
    const seen = new Set();
    function visit(item, key = "") {
      if (item == null || seen.has(item)) return;
      if (typeof item === "string") {
        if (/^(?:BUR|REQ|Q|ASK|DEC|AUTH)-?[A-Z0-9_.:-]+$/i.test(item.trim()) || /(?:request|question|decision)[_-]?id/i.test(key)) {
          if (item.trim()) result.add(item.trim());
        }
        return;
      }
      if (typeof item !== "object") return;
      seen.add(item);
      if (Array.isArray(item)) {
        for (const child of item) visit(child, key);
        return;
      }
      for (const [childKey, child] of Object.entries(item)) {
        if (/^(?:id|request_id|requestId|question_id|questionId)$/i.test(childKey) && typeof child === "string" && child.trim()) {
          result.add(child.trim());
        }
        visit(child, childKey);
      }
    }
    visit(value);
    return [...result];
  }
  function intervalPairs(intervals, openStarts = []) {
    const now = nowMs();
    return [
      ...intervals.map(item => [Number(item.start_ms), Number(item.end_ms)]),
      ...openStarts.map(item => [Number(item.start_ms), now]),
    ].filter(([start, end]) => Number.isFinite(start) && Number.isFinite(end) && end >= start)
      .sort((left, right) => left[0] - right[0] || left[1] - right[1]);
  }
  function intervalDuration(intervals, openStarts = []) {
    const raw = intervalPairs(intervals, openStarts);
    if (!raw.length) return 0;
    let total = 0;
    let [start, end] = raw[0];
    for (const [nextStart, nextEnd] of raw.slice(1)) {
      if (nextStart <= end) end = Math.max(end, nextEnd);
      else {
        total += end - start;
        [start, end] = [nextStart, nextEnd];
      }
    }
    return total + (end - start);
  }
  function intervalSum(intervals, openStarts = []) {
    return intervalPairs(intervals, openStarts).reduce((total, [start, end]) => total + end - start, 0);
  }
  function openAskValues() { return [...askStarts.values()]; }
  function setWaitingStatus(ctx) {
    const open = openAskValues();
    if (!open.length) {
      if (waitingStatusVisible) {
        ctx?.ui?.setStatus?.(WAITING_STATUS_KEY, undefined);
        waitingStatusVisible = false;
      }
      return;
    }
    const oldest = Math.min(...open.map(item => item.start_ms));
    const seconds = Math.max(0, Math.floor((nowMs() - oldest) / 1000));
    const ids = [...new Set(open.flatMap(item => item.request_ids || []))];
    ctx?.ui?.setStatus?.(WAITING_STATUS_KEY, `WAITING_ON_USER ${seconds}s${ids.length ? ` · ${ids.join(", ")}` : ""}`);
    waitingStatusVisible = true;
  }
  function reset(ctx) {
    sequence = 0;
    sessionStartedAtMs = nowMs();
    sessionStartedAt = iso(sessionStartedAtMs);
    subagentStarts = new Map();
    subagentIntervals = [];
    providerStarts = [];
    providerIntervals = [];
    toolStarts = new Map();
    toolIntervals = [];
    askStarts = new Map();
    askIntervals = [];
    blockedProviderRequests = 0;
    if (waitingStatusVisible) {
      ctx?.ui?.setStatus?.(WAITING_STATUS_KEY, undefined);
      waitingStatusVisible = false;
    }
  }
  function updateSubagentLifecycle(event) {
    const id = eventId(event, "subagent");
    const status = normalizedStatus(event);
    if (SUBAGENT_ACTIVE.has(status)) {
      if (!subagentStarts.has(id)) {
        subagentStarts.set(id, {
          id,
          role: String(event?.agent ?? event?.role ?? event?.progress?.agent ?? "").trim() || null,
          start_ms: nowMs(),
          start_status: status,
        });
      }
      return;
    }
    if (!SUBAGENT_TERMINAL.has(status)) return;
    const start = subagentStarts.get(id);
    if (!start) return;
    subagentStarts.delete(id);
    subagentIntervals.push({ ...start, end_ms: nowMs(), end_status: status });
  }
  function updateSubagentProgress(event) {
    const status = normalizedStatus(event);
    if (!status) return;
    updateSubagentLifecycle(event);
  }
  function providerStart(event) {
    const start = {
      id: eventId(event, "provider"),
      start_ms: nowMs(),
      header_ms: null,
    };
    providerStarts.push(start);
    return start.id;
  }
  function providerHeader(event) {
    const open = providerStarts.find(item => item.header_ms == null);
    if (!open) return;
    open.header_ms = nowMs();
    open.response_status = event?.status ?? event?.response?.status ?? null;
  }
  function providerEnd(event) {
    if (event?.message && String(event.message.role || "").toLowerCase() !== "assistant") return;
    if (!providerStarts.length) return;
    const start = providerStarts.shift();
    providerIntervals.push({
      ...start,
      end_ms: nowMs(),
      outcome: event?.outcome || "assistant-message-end",
    });
  }
  function providerBlocked() {
    const start = providerStarts.pop();
    if (start) {
      providerIntervals.push({ ...start, end_ms: nowMs(), outcome: "prompt-guard-blocked", blocked: true });
    }
    blockedProviderRequests += 1;
  }
  function closeOpenProviders(outcome = "agent-end-without-message") {
    const end = nowMs();
    while (providerStarts.length) {
      const start = providerStarts.shift();
      providerIntervals.push({ ...start, end_ms: end, outcome });
    }
  }
  function toolStart(event, ctx) {
    const id = eventId(event, "tool");
    const name = normalizeToolName(event);
    const start = { id, tool_name: name, start_ms: nowMs() };
    toolStarts.set(id, start);
    if (name === "ask") {
      const args = event?.args ?? event?.input ?? {};
      askStarts.set(id, { ...start, request_ids: requestIds(args) });
      setWaitingStatus(ctx);
    }
  }
  function toolEnd(event, ctx) {
    const id = String(event?.toolCallId ?? event?.tool_call_id ?? event?.id ?? "");
    let start = id ? toolStarts.get(id) : null;
    let key = id;
    if (!start) {
      const name = normalizeToolName(event);
      const candidate = [...toolStarts.entries()].reverse().find(([, item]) => !name || item.tool_name === name);
      if (candidate) [key, start] = candidate;
    }
    if (!start) return;
    const end = nowMs();
    toolStarts.delete(key);
    toolIntervals.push({ ...start, end_ms: end, is_error: Boolean(event?.isError ?? event?.is_error) });
    const ask = askStarts.get(key);
    if (ask) {
      askStarts.delete(key);
      askIntervals.push({ ...ask, end_ms: end });
      setWaitingStatus(ctx);
    }
  }
  function snapshot(ctx) {
    setWaitingStatus(ctx);
    const observedAtMs = nowMs();
    const elapsed = Math.max(0, observedAtMs - sessionStartedAtMs);
    const openSubagents = [...subagentStarts.values()].map(item => ({ ...item }));
    const openProviders = providerStarts.map(item => ({ ...item }));
    const openTools = [...toolStarts.values()].map(item => ({ ...item }));
    const openAsks = openAskValues().map(item => ({ ...item }));
    const explicitUserWait = intervalDuration(askIntervals, openAsks);
    const subagentWall = intervalDuration(subagentIntervals, openSubagents);
    const providerWall = intervalDuration(providerIntervals, openProviders);
    const providerHeaderIntervals = providerIntervals
      .filter(item => Number.isFinite(Number(item.header_ms)))
      .map(item => ({ ...item, end_ms: Number(item.header_ms) }));
    const openProviderHeaders = openProviders
      .filter(item => Number.isFinite(Number(item.header_ms)))
      .map(item => ({ ...item, end_ms: Number(item.header_ms) }));
    const toolWall = intervalDuration(toolIntervals, openTools);
    const allCoverage = intervalDuration(
      [...subagentIntervals, ...providerIntervals, ...toolIntervals, ...askIntervals],
      [...openSubagents, ...openProviders, ...openTools, ...openAsks],
    );
    const currentWait = openAsks.length
      ? Math.max(0, observedAtMs - Math.min(...openAsks.map(item => item.start_ms)))
      : 0;
    let sessionId = null;
    try { sessionId = ctx?.sessionManager?.getSessionId?.() || ctx?.sessionManager?.getSessionFile?.() || null; } catch {}
    const requestIdValues = [...new Set(openAsks.flatMap(item => item.request_ids || []))];
    const activeSnapshot = activity?.snapshot?.({ activeOnly: true }) || { active_count: openSubagents.length };
    return {
      schema: "bbk.omp-timing.v1",
      status: "PASS",
      package_version: version,
      observed_at: iso(observedAtMs),
      session_id: sessionId,
      session_started_at: sessionStartedAt,
      elapsed_ms: elapsed,
      campaign_state: openAsks.length ? "WAITING_ON_USER" : "OBSERVING",
      explicit_user_wait_ms: explicitUserWait,
      elapsed_excluding_user_wait_ms: Math.max(0, elapsed - explicitUserWait),
      current_waiting_on_user: openAsks.length > 0,
      current_user_wait_ms: currentWait,
      waiting_since: openAsks.length ? iso(Math.min(...openAsks.map(item => item.start_ms))) : null,
      request_ids: requestIdValues,
      independent_work_active: Math.max(Number(activeSnapshot.active_count || 0), openSubagents.length),
      open_user_requests: openAsks.map(item => ({
        tool_call_id: item.id,
        request_ids: item.request_ids,
        waiting_since: iso(item.start_ms),
      })),
      subagents: {
        runs_completed: subagentIntervals.length,
        runs_open: openSubagents.length,
        active_wall_ms: subagentWall,
        active_sum_ms: intervalSum(subagentIntervals, openSubagents),
      },
      provider: {
        requests_completed: providerIntervals.length,
        requests_open: openProviders.length,
        requests_blocked_by_prompt_guard: blockedProviderRequests,
        end_to_end_wall_ms: providerWall,
        end_to_end_sum_ms: intervalSum(providerIntervals, openProviders),
        response_header_wall_ms: intervalDuration([...providerHeaderIntervals, ...openProviderHeaders]),
        response_header_sum_ms: intervalSum([...providerHeaderIntervals, ...openProviderHeaders]),
      },
      tools: {
        executions_completed: toolIntervals.length,
        executions_open: openTools.length,
        execution_wall_ms: toolWall,
        execution_sum_ms: intervalSum(toolIntervals, openTools),
      },
      observed_activity_coverage_ms: Math.min(elapsed, allCoverage),
      unattributed_elapsed_ms: Math.max(0, elapsed - Math.min(elapsed, allCoverage)),
      interpretation: {
        explicit_user_wait: "Measured only while OMP's native ask tool is open.",
        provider_time: "End-to-end provider time is observed from before_provider_request to assistant message_end; response-header time ends at after_provider_response.",
        subagent_time: "Sub-agent lifetimes come from task:subagent lifecycle/progress evidence observed by Main.",
        interval_accounting: "Wall durations merge overlapping intervals; sum durations intentionally retain overlap and must not be read as elapsed wall clock.",
        unattributed: "Elapsed time not covered by observed ask, sub-agent, provider, or tool-execution intervals; it is not evidence of model compute or inactivity.",
      },
    };
  }
  function human(value) {
    const seconds = ms => `${(Number(ms || 0) / 1000).toFixed(1)}s`;
    const lines = [
      `BBK timing (${value.campaign_state})`,
      `Elapsed: ${seconds(value.elapsed_ms)}`,
      `Explicit user wait: ${seconds(value.explicit_user_wait_ms)}`,
      `Elapsed excluding user wait: ${seconds(value.elapsed_excluding_user_wait_ms)}`,
    ];
    if (value.current_waiting_on_user) {
      lines.push(`Waiting since: ${value.waiting_since || "unknown"}`);
      lines.push(`Request IDs: ${value.request_ids.length ? value.request_ids.join(", ") : "not exposed by host"}`);
      lines.push(`Independent work active: ${value.independent_work_active}`);
    }
    lines.push(
      `Sub-agent active wall: ${seconds(value.subagents.active_wall_ms)} (${value.subagents.runs_completed} completed, ${value.subagents.runs_open} open; sum ${seconds(value.subagents.active_sum_ms)})`,
      `Provider end-to-end wall: ${seconds(value.provider.end_to_end_wall_ms)} (${value.provider.requests_completed} completed, ${value.provider.requests_open} open, ${value.provider.requests_blocked_by_prompt_guard} prompt-blocked)`,
      `Provider response-header wall: ${seconds(value.provider.response_header_wall_ms)}`,
      `Tool execution wall: ${seconds(value.tools.execution_wall_ms)} (${value.tools.executions_completed} completed, ${value.tools.executions_open} open)`,
      `Unattributed elapsed: ${seconds(value.unattributed_elapsed_ms)}`,
      "Timing is observational; overlapping categories are merged for wall durations and do not prove active compute.",
    );
    return lines.join("\n");
  }
  function registerCommand() {
    pi.registerCommand("bbk:timing", {
      description: "show observational BBK timing with native-ask user wait separated from session elapsed",
      handler: async (first, second) => {
        const { args, ctx } = commandInvocation(first, second);
        const value = snapshot(ctx);
        const jsonMode = ["json", "--json"].includes(String(args || "").trim().toLowerCase());
        ctx?.ui?.notify?.(jsonMode ? JSON.stringify(value, null, 2) : human(value), "info");
        return undefined;
      },
    });
  }
  try {
    const stop = pi.events?.on?.(TASK_SUBAGENT_LIFECYCLE_CHANNEL, updateSubagentLifecycle);
    if (typeof stop === "function") unsubscribe.push(stop);
  } catch {}
  try {
    const stop = pi.events?.on?.(TASK_SUBAGENT_PROGRESS_CHANNEL, updateSubagentProgress);
    if (typeof stop === "function") unsubscribe.push(stop);
  } catch {}
  function dispose(ctx) {
    setWaitingStatus(ctx);
    ctx?.ui?.setStatus?.(WAITING_STATUS_KEY, undefined);
    for (const stop of unsubscribe.splice(0)) {
      try { stop(); } catch {}
    }
  }
  return {
    reset,
    updateSubagentLifecycle,
    updateSubagentProgress,
    providerStart,
    providerHeader,
    providerEnd,
    providerBlocked,
    closeOpenProviders,
    toolStart,
    toolEnd,
    snapshot,
    registerCommand,
    dispose,
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
          ? [
              `BBK prompt requests: verified=${result.counts.verified}, repaired=${result.counts.repaired}, blocked=${result.counts.blocked}, unverifiable=${result.counts.unverifiable}`,
              `Current guarantee: ${result.current_guarantee}`,
              ...result.latest.map(item => `${item.role || item.prompt_kind || "unknown"} · ${item.phase} · ${item.action || item.status} · ${item.sent?.sha256 || item.effective?.sha256 || item.expected?.sha256 || "no-digest"}`),
            ].join("\n")
          : "No BBK prompt receipts are recorded in the current branch.";
      ctx?.ui?.notify?.(text, result.unresolved_failure ? "error" : "info");
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
    name: "bbk_artifact_finalize", label: "BBK Artifact Package Finalize", description: "Finalize either an existing package draft or an ordinary software source set into project-local .bbk/artifacts/sealed. One-shot software mode requires packageId and revision; when sources is omitted it selects the project root with deterministic built-in exclusions. Returns an external publication receipt and live-source freshness binding.",
    parameters: z.object({ draftRoot: text(), root: text(), output: text(), publicationRoot: text(), registry: text(), packageId: text(), revision: text(), sources: texts(), includes: texts(), excludes: texts(), subjectKind: text(), subjectId: text(), subjectRevision: text(), purpose: text(), allowMutableCoordination: bool(), noCurrentPointer: bool(), recoverStaleLock: bool() }),
    argv: p => ["artifact", "finalize", ...(p.draftRoot ? [p.draftRoot] : []), ...rootArgs(p.root), ...(p.output ? ["--output", p.output] : []),
      ...(p.publicationRoot ? ["--publication-root", p.publicationRoot] : []), ...(p.registry ? ["--registry", p.registry] : []),
      ...(p.packageId ? ["--package-id", p.packageId] : []), ...(p.revision ? ["--revision", p.revision] : []),
      ...repeated("--source", p.sources), ...repeated("--include", p.includes), ...repeated("--exclude", p.excludes),
      ...(p.subjectKind ? ["--subject-kind", p.subjectKind] : []), ...(p.subjectId ? ["--subject-id", p.subjectId] : []),
      ...(p.subjectRevision ? ["--subject-revision", p.subjectRevision] : []), ...(p.purpose ? ["--purpose", p.purpose] : []),
      ...(p.allowMutableCoordination ? ["--allow-mutable-coordination"] : []), ...(p.noCurrentPointer ? ["--no-current-pointer"] : []),
      ...(p.recoverStaleLock ? ["--recover-stale-lock"] : [])],
  });
  registerCliTool(pi, {
    name: "bbk_artifact_freshness", label: "BBK Artifact Package Freshness", description: "Verify a publication/current pointer or sealed package and detect source mutations after one-shot software finalization.",
    parameters: z.object({ subject: z.string(), root: text(), registry: text() }),
    argv: p => ["artifact", "freshness", p.subject, ...rootArgs(p.root), ...(p.registry ? ["--registry", p.registry] : [])],
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

  pi.registerTool({
    name: "bbk_governance_status",
    label: "BBK Governance Status",
    description: "Return the current binding, host-enforcement boundary, and canonical governance-journal counts after verifying the active role capability. This query does not rebuild or mutate projections.",
    parameters: z.object({ bindingRef: text(), invocationId: text() }),
    async execute(id, params, signal, _onUpdate, ctx) {
      return executeGovernanceStatusTool(id, params || {}, signal, ctx);
    },
  });

  const governedIdentity = {
    bindingRef: z.string(),
    invocationId: z.string(),
    path: z.string(),
    mutationClass: z.string(),
    idempotencyKey: z.string(),
    preconditionKind: z.enum(["ANY", "ABSENT", "PRESENT", "SHA256"]).optional(),
    expectedSha256: text(),
  };
  pi.registerTool({
    name: "bbk_governed_read",
    label: "BBK Governed Read",
    description: "Read one regular file from the exact workspace and path scope in an active immutable binding.",
    parameters: z.object({
      bindingRef: z.string(), invocationId: z.string(), path: z.string(),
      mutationClass: text(), idempotencyKey: z.string(),
      preconditionKind: z.enum(["ANY", "PRESENT", "SHA256"]).optional(), expectedSha256: text(),
    }),
    async execute(id, params, signal, _onUpdate, ctx) {
      return executeGovernedFilesystemTool(id, "READ", params || {}, signal, ctx);
    },
  });
  pi.registerTool({
    name: "bbk_governed_write",
    label: "BBK Governed Write",
    description: "Atomically create or replace one file after binding, capability, scope, precondition, sealed-package, and Gate Kernel checks.",
    parameters: z.object({
      ...governedIdentity,
      content: z.string(),
      encoding: z.enum(["utf-8", "base64"]).optional(),
    }),
    async execute(id, params, signal, _onUpdate, ctx) {
      return executeGovernedFilesystemTool(id, "WRITE", params || {}, signal, ctx);
    },
  });
  pi.registerTool({
    name: "bbk_governed_edit",
    label: "BBK Governed Edit",
    description: "Apply one exact UTF-8 replacement after binding, capability, scope, precondition, sealed-package, and Gate Kernel checks.",
    parameters: z.object({
      ...governedIdentity,
      oldText: z.string(), newText: z.string(), replaceAll: bool(),
    }),
    async execute(id, params, signal, _onUpdate, ctx) {
      return executeGovernedFilesystemTool(id, "EDIT", params || {}, signal, ctx);
    },
  });
  pi.registerTool({
    name: "bbk_governed_delete",
    label: "BBK Governed Delete",
    description: "Delete one regular file after binding, capability, scope, precondition, sealed-package, and Gate Kernel checks.",
    parameters: z.object(governedIdentity),
    async execute(id, params, signal, _onUpdate, ctx) {
      return executeGovernedFilesystemTool(id, "DELETE", params || {}, signal, ctx);
    },
  });

  pi.registerTool({
    name: "bbk_task_run",
    label: "BBK Qualified Task",
    description: "Run one declared candidate-preserving mise task from the exact active worker binding. BBK derives candidate and toolchain digests, records the real mise path/version, and fails if the task changes candidate content.",
    parameters: z.object({
      bindingRef: z.string(), invocationId: z.string(), task: z.string(),
      arguments: z.array(z.string()).optional(), environmentAllowlist: z.array(z.string()).optional(),
      idempotencyKey: z.string(),
    }),
    async execute(id, params, signal, _onUpdate, ctx) {
      return executeQualifiedTaskTool(id, params || {}, signal, ctx);
    },
  });

  pi.registerTool({
    name: "bbk_return_template",
    label: "BBK Role Return Template",
    description: "Return the exact active role contract, allowed values, parent route, compact result fields, and a minimal result JSON example. Use this instead of guessing the terminal return envelope.",
    parameters: z.object({
      bindingRef: z.string(), invocationId: z.string(), invocationMode: z.string().optional(),
    }),
    async execute(id, params, signal, _onUpdate, ctx) {
      return executeReturnTemplateTool(id, params || {}, signal, ctx);
    },
  });

  pi.registerTool({
    name: "bbk_return_prepare",
    label: "BBK Validated Role Return",
    description: "Build and Draft-2020-12 validate the exact role-specific structured return from the active binding. Returns the complete immutable yield_input; invoke hidden yield with that input exactly instead of hand-authoring the common envelope.",
    parameters: z.object({
      bindingRef: z.string(), invocationId: z.string(), invocationMode: z.string().optional(),
      returnKind: z.string(), detailLevel: z.enum(["COMPACT", "FULL"]).optional(),
      operationalDisposition: z.string(), semanticStateValue: z.string(), summary: z.string(),
      result: z.any().optional(), resultJson: z.string().optional(),
      nextAction: z.string(), nextActionOwner: z.string(), nextActionReason: z.string(),
      nextActionAffectedRefs: z.array(z.string()).optional(), unaffectedWorkMayContinue: z.boolean().optional(),
      authorityRefs: z.any().optional(), authorityRefsJson: z.string().optional(), allowedEffectClasses: z.array(z.string()).optional(),
      effectsUsed: z.any().optional(), effectsUsedJson: z.string().optional(),
      deniedOrUncoveredEffects: z.any().optional(), deniedOrUncoveredEffectsJson: z.string().optional(),
      violationsOrAmbiguities: z.any().optional(), violationsOrAmbiguitiesJson: z.string().optional(),
      outputs: z.any().optional(), outputsJson: z.string().optional(),
      checksAndEvidence: z.any().optional(), checksAndEvidenceJson: z.string().optional(),
      effectsAndCleanup: z.any().optional(), effectsAndCleanupJson: z.string().optional(),
      blockersAndResiduals: z.array(z.string()).optional(), prohibitedClaims: z.array(z.string()).optional(),
      durableHandoffRefs: z.any().optional(), durableHandoffRefsJson: z.string().optional(), idempotencyKey: z.string(),
    }),
    async execute(id, params, signal, _onUpdate, ctx) {
      return executeReturnPrepareTool(id, params || {}, signal, ctx);
    },
  });

  pi.registerTool({
    name: "bbk_control_bind",
    label: "BBK Read-Only Child Binding",
    description: "Freeze an existing Git/jj candidate, bind one reviewer/validator-style child to that exact workspace with no mutation authority, and return a compact one-use dispatch_input. Invoke that small dispatch_input through OMP task without alteration; BBK resolves the full assignment internally.",
    parameters: z.object({
      parentBindingRef: z.string(), parentInvocationId: z.string(), taskName: z.string(), role: z.string(),
      workUnitId: z.string(), attemptId: z.string(), baselineRef: z.string(), candidateId: z.string(),
      candidateAdmissionRef: z.string().optional(),
      authorityRef: z.string(), returnContract: z.string(), workspaceRef: z.string(),
      pathPrefixes: z.array(z.string()), semanticScope: z.array(z.string()).optional(),
      assignment: z.string(), description: z.string().optional(), idempotencyKey: z.string(),
    }),
    async execute(id, params, signal, _onUpdate, ctx) {
      return executeControlBindTool(id, params || {}, signal, ctx);
    },
  });

  pi.registerTool({
    name: "bbk_control_spawn",
    label: "BBK Bound Worker Spawn",
    description: "Atomically allocate or reuse one logical worker attempt, project its immutable Beads assignment through the single writer, reserve the exact private task payload, and return a compact token dispatch. Invoke the dispatch once through native OMP task; on uncertainty query bbk_control_dispatch_status and never respawn the same attempt.",
    parameters: z.object({
      parentBindingRef: z.string(), parentInvocationId: z.string(), taskName: z.string(), role: z.string(),
      workUnitId: z.string(), attemptId: z.string(), baselineRef: z.string(), candidateRef: z.string(),
      authorityRef: z.string(), returnContract: z.string(),
      returnTransportMode: z.enum(["STRUCTURED_RETURN_FIRST", "STRUCTURED_RETURN_ONLY", "SEALED_HANDOFF_REQUIRED"]).optional(),
      materialTransportReason: z.string().optional(), parentRevision: z.string(), workspaceParent: z.string(),
      pathPrefixes: z.array(z.string()), mutationClasses: z.array(z.string()), semanticScope: z.array(z.string()).optional(),
      assignment: z.string(), description: z.string().optional(), idempotencyKey: z.string(),
    }),
    async execute(id, params, signal, _onUpdate, ctx) {
      return executeControlSpawnTool(id, params || {}, signal, ctx);
    },
  });

  pi.registerTool({
    name: "bbk_control_dispatch_status",
    label: "BBK Dispatch Status",
    description: "Read the durable READY, LEASED, ACTIVATED, or TERMINAL state of one compact dispatch token. Use this on uncertainty instead of creating another binding or retrying through eval/shell/Python.",
    parameters: z.object({ dispatchRef: z.string() }),
    async execute(id, params, signal, _onUpdate, ctx) {
      return executeDispatchStatusTool(id, params || {}, signal, ctx);
    },
  });

  const controlCommandBaseIdentity = {
    bindingRef: z.string(),
    invocationId: z.string(),
    commandId: z.string(),
    workUnitId: z.string(),
    attemptId: z.string(),
    correlationId: z.string(),
    payloadSummary: z.string(),
    idempotencyKey: z.string(),
    evidenceRefs: z.array(z.string()).optional(),
    findingRefs: z.array(z.string()).optional(),
  };
  const controlCommandIdentity = {
    ...controlCommandBaseIdentity,
    expectedRevision: typeof z.number === "function" ? z.number() : z.string(),
  };
  pi.registerTool({
    name: "bbk_control_assign",
    label: "BBK Bound Assignment",
    description: "Compatibility-only explicit assignment projection. Normal worker dispatch performs this transaction inside bbk_control_spawn; orchestrators must not call this separately unless a migration tool explicitly requires it.",
    parameters: z.object({
      ...controlCommandIdentity,
      workerBindingRef: z.string(),
      attemptRegistrationRef: z.string(),
    }),
    async execute(id, params, signal, _onUpdate, ctx) {
      return executeControlPlaneTool(id, "bbk.control-assign.v1", params || {}, signal, ctx);
    },
  });
  pi.registerTool({
    name: "bbk_control_update",
    label: "BBK Coordination Update",
    description: "Project one typed work-unit state transition through BBK's single Beads writer with exact attempt, correlation, revision, and idempotency identities.",
    parameters: z.object({
      ...controlCommandIdentity,
      transition: z.enum(["START", "BLOCK", "UNBLOCK", "COMPLETE", "FAIL", "ANNOTATE"]),
    }),
    async execute(id, params, signal, _onUpdate, ctx) {
      return executeControlPlaneTool(id, "bbk.control-update.v1", params || {}, signal, ctx);
    },
  });
  pi.registerTool({
    name: "bbk_control_integrate_request",
    label: "BBK Integration Request",
    description: "Record an integration request without changing candidate content. BBK derives the current Beads revision internally; the orchestrator must not guess or supply expectedRevision. Content-changing or unknown conflicts are deterministically routed to a future bound Integration Worker, never repaired by the orchestrator.",
    parameters: z.object({
      ...controlCommandBaseIdentity,
      sourceCandidateRefs: z.array(z.string()),
      targetCandidateRef: z.string(),
      conflictClassification: z.enum(["NONE", "CONTENT_NEUTRAL", "CONTENT_CHANGING", "UNKNOWN"]),
    }),
    async execute(id, params, signal, _onUpdate, ctx) {
      return executeControlPlaneTool(id, "bbk.control-integrate-request.v1", params || {}, signal, ctx);
    },
  });

  const bbkActivity = createBbkActivityHud(pi);
  const bbkTiming = createBbkTimingController(pi, bbkActivity);
  const bbkMode = createBbkModeController(pi, (active, ctx) => bbkActivity.setMode(active, ctx));
  const bbkCoordination = createBbkCoordinationThrottle(bbkMode, bbkActivity);
  const bbkRuntime = publishBbkRuntime(bbkMode, bbkActivity, bbkCoordination);
  void bbkRuntime;
  const bbkArtifactFinalization = createArtifactFinalizationGuard(pi, bbkMode);
  registerBbkEntrypoint(pi, bbkMode);
  registerModelRoutingCommand(pi);
  registerAgentViewCommand(pi, bbkActivity, bbkTiming);
  registerBeadsCommand(pi);
  bbkTiming.registerCommand();
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
  registerCommand(pi, "bbk:artifact:finalize", "[<draft-root>] [--root <project> --package-id <id> --revision <rev> --source <path>...]", ["artifact", "finalize"], { requireArgs: true });
  registerCommand(pi, "bbk:artifact:freshness", "<publication-or-current-or-sealed-path> [--root <project>]", ["artifact", "freshness"], { requireArgs: true });
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

  pi.on?.("before_agent_start", async (event, ctx) => {
    await activateBoundWorker(event, ctx, pi);
    const replacement = await bbkMode.promptReplacement(event, ctx);
    bbkArtifactFinalization.detectRequirement(event, ctx);
    return replacement;
  });
  pi.on?.("before_provider_request", async (event, ctx) => {
    bbkTiming.providerStart(event);
    const result = await bbkMode.finalizeProviderPrompt(event, ctx);
    if (result?.__bbk_prompt_blocked__) bbkTiming.providerBlocked();
    return result;
  });
  pi.on?.("after_provider_response", async event => bbkTiming.providerHeader(event));
  pi.on?.("message_end", async (event, ctx) => {
    bbkTiming.providerEnd(event);
    return bbkArtifactFinalization.finalizeMessage(event, ctx);
  });
  pi.on?.("agent_end", async (event, ctx) => {
    bbkTiming.closeOpenProviders();
    await terminalizeGovernedDispatch(event, ctx);
  });
  pi.on?.("tool_execution_start", async (event, ctx) => bbkTiming.toolStart(event, ctx));
  pi.on?.("tool_execution_end", async (event, ctx) => {
    bbkTiming.toolEnd(event, ctx);
    const failed = Boolean(event?.isError || event?.error || event?.result?.isError || String(event?.status || "").toLowerCase() === "error");
    if (failed) await releaseGovernedDispatchLease(event?.toolCallId || event?.tool_call_id, "OMP_TASK_TOOL_EXECUTION_FAILED");
  });
  const restoreBbkMode = async (_event, ctx) => {
    bbkActivity.reset(ctx);
    bbkTiming.reset(ctx);
    bbkCoordination.reset(ctx);
    const active = bbkMode.restore(ctx);
    bbkArtifactFinalization.reset(ctx);
    if (governedProfileEnabled()) {
      await recordGovernedHostDecision(_event || {}, ctx, {
        eventType: String(_event?.type || "SESSION_NAVIGATION").toUpperCase(),
        postEffect: true,
      });
    }
    if (_event?.type === "session_start") {
      ctx?.ui?.notify?.(`BBK ${version} loaded in ${ctx?.cwd || process.cwd()}${active ? "; BBK mode restored" : ""}`, "info");
    }
  };
  for (const eventName of ["session_start", "session_switch", "session_branch", "session_tree"]) {
    pi.on?.(eventName, restoreBbkMode);
  }
  pi.on?.("session_shutdown", async (_event, ctx) => {
    bbkActivity.dispose(ctx);
    bbkTiming.dispose(ctx);
    bbkCoordination.dispose(ctx);
    bbkArtifactFinalization.dispose(ctx);
  });
  pi.on?.("tool_result", async (event, ctx) => {
    bbkActivity.updateCoordinationResult(event);
    bbkArtifactFinalization.observeToolResult(event, ctx);
    const failed = Boolean(event?.isError || event?.error || event?.result?.isError || String(event?.status || "").toLowerCase() === "error");
    if (failed) await releaseGovernedDispatchLease(event?.toolCallId || event?.tool_call_id, "OMP_TASK_TOOL_RESULT_FAILED");
  });
  pi.on?.("tool_call", async (event, ctx) => {
    const toolName = String(event?.toolName || event?.tool_name || "").trim().toLowerCase();
    const encoded = JSON.stringify(event?.input || {});
    const genericExecutionSurface = new Set(["eval", "python", "bash", "shell", "exec", "execute", "javascript", "js"]);
    const dispatchFallbackAttempt = encoded.includes("<bbk-spawn-dispatch")
      || (/dispatch:[0-9a-f]{64}/.test(encoded) && /(tool\.task|\"task\"|tasks)/i.test(encoded));
    if (governedProfileEnabled() && genericExecutionSurface.has(toolName) && dispatchFallbackAttempt) {
      await recordGovernedHostDecision(event, ctx);
      return governedBlock(
        "BBK_GENERIC_DISPATCH_FALLBACK_FORBIDDEN",
        `generic ${toolName} cannot invoke, reconstruct, or emulate a BBK child dispatch`,
        "Use the exact native task dispatch once, then query bbk_control_dispatch_status on uncertainty.",
      );
    }
    if (["bash", "write", "edit"].includes(toolName) && protectedFragments.some(fragment => encoded.includes(fragment))) {
      return governedBlock(
        "BBK_ACCEPTED_RECORD_PROTECTED",
        "BBK protects frozen candidates, attestations, gate receipts, review runs, findings, and dispositions",
        "Create a successor or write an external annotation.",
      );
    }
    if (toolName === "yield") {
      const yieldDecision = await guardYieldRoleReturn(event, ctx, pi);
      if (yieldDecision) return yieldDecision;
      return undefined;
    }
    if (toolName === "task") {
      if (governedProfileEnabled()) {
        const admission = await admitGovernedTask(event, ctx);
        if (admission) return admission;
      }
      bbkCoordination.noteTaskDispatch(ctx);
      return undefined;
    }
    const coordinationDecision = bbkCoordination.guard(event, ctx);
    if (coordinationDecision) return coordinationDecision;
    const transportDecision = await guardStructuredReturnTransport(event, ctx);
    if (transportDecision) return transportDecision;
    if (!governedProfileEnabled()) return undefined;
    if (["bash", "write", "edit"].includes(toolName)) {
      await recordGovernedHostDecision(event, ctx);
      return governedBlock(
        "AMBIENT_MUTATION_TOOL_FORBIDDEN",
        `built-in ${toolName} is disabled before effect in governed-software mode`,
        "Use bbk_governed_read/write/edit/delete with an exact active binding.",
      );
    }
    return undefined;
  });
}
