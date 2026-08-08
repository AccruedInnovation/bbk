import { readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import path from "node:path";

const BBK_RUNTIME_SYMBOL = Symbol.for("bbk.omp.runtime.v1");
const EXPECTED_RUNTIME_SCHEMA = "bbk.omp-runtime.v1";
const EXPECTED_PROMPT_STATUS_SCHEMA = "bbk.prompt-status.v2";

function requireEnv(name) {
  const value = String(process.env[name] || "").trim();
  if (!value) throw new Error(`ALPHA17_MANUAL_ENV_REQUIRED: ${name}`);
  return value;
}

function sessionId(ctx) {
  return String(ctx?.sessionManager?.getSessionId?.() || "").trim();
}

function parentSessionId(event) {
  return String(event?.parentSessionId || event?.parent_session_id || event?.parentSession || "").trim();
}

function rootBootstrap(value) {
  if (!value || typeof value !== "object") return null;
  if (value.schema === "bbk.alpha17-manual-bootstrap.v1") return value;
  if (value.schema === "bbk.alpha17-manual-bootstrap-observation.v1" && value.root_bootstrap) return value.root_bootstrap;
  return null;
}

function runPython(scriptName, args, input = null, { preserveStructuredNonpass = false } = {}) {
  const python = requireEnv("BBK_PYTHON");
  const harness = requireEnv("BBK_MANUAL_HARNESS_ROOT");
  const completed = spawnSync(python, [path.join(harness, scriptName), ...args], {
    cwd: requireEnv("BBK_PROJECT_ROOT"),
    env: process.env,
    input: input === null ? undefined : JSON.stringify(input),
    encoding: "utf8",
    windowsHide: true,
  });
  const stdout = String(completed.stdout || "").trim();
  let parsed = null;
  try { parsed = stdout ? JSON.parse(stdout) : null; } catch {}
  if (completed.status !== 0) {
    if (preserveStructuredNonpass && parsed && typeof parsed === "object") return parsed;
    throw new Error(`ALPHA17_MANUAL_HELPER_FAILED: ${scriptName} exited ${completed.status}: ${String(completed.stderr || completed.stdout).slice(-4000)}`);
  }
  if (!parsed || typeof parsed !== "object") {
    throw new Error(`ALPHA17_MANUAL_HELPER_INVALID_JSON: ${scriptName} returned no JSON object`);
  }
  return parsed;
}

function runtimeFailure(code, message, details = {}) {
  return {
    schema: "bbk.alpha17-manual-runtime-failure.v1",
    status: "BLOCKED_TECHNICAL",
    code,
    message,
    details,
    smallest_next_action: "Exit this OMP session, rerun start-alpha17-qualification.ps1, and execute the emitted PowerShell command manually. Do not continue through a /bbk skill fallback.",
  };
}

export default function alpha17ManualHarness(pi) {
  const { z } = pi.zod;
  let bootstrap = null;
  let startupFailure = null;
  let runtime = null;
  let modeActivatedAt = null;

  function inspectRuntime(ctx, { requireProviderReceipt = false } = {}) {
    const expectedVersion = requireEnv("BBK_EXPECTED_PACKAGE_VERSION");
    runtime = globalThis[BBK_RUNTIME_SYMBOL];
    if (!runtime || runtime.schema !== EXPECTED_RUNTIME_SCHEMA) {
      throw Object.assign(
        new Error("BBK_OMP_EXTENSION_NOT_ACTIVE: the extension-owned runtime marker is absent"),
        { qualificationFailure: runtimeFailure("BBK_OMP_EXTENSION_NOT_ACTIVE", "The installed BBK OMP extension did not publish its runtime marker.") },
      );
    }
    if (runtime.package_version !== expectedVersion) {
      throw Object.assign(
        new Error(`BBK_OMP_EXTENSION_VERSION_MISMATCH: expected ${expectedVersion}, observed ${runtime.package_version}`),
        { qualificationFailure: runtimeFailure("BBK_OMP_EXTENSION_VERSION_MISMATCH", "The loaded BBK extension does not match the qualified package.", { expected_version: expectedVersion, observed_version: runtime.package_version }) },
      );
    }
    runtime.ensureMode(ctx);
    if (!runtime.isModeEnabled()) {
      throw Object.assign(
        new Error("BBK_OMP_MODE_NOT_ACTIVE: persistent BBK mode is not enabled"),
        { qualificationFailure: runtimeFailure("BBK_OMP_MODE_NOT_ACTIVE", "The extension loaded, but persistent BBK controller mode is not active.") },
      );
    }
    const prompt = runtime.promptStatus(ctx);
    if (!prompt || prompt.schema !== EXPECTED_PROMPT_STATUS_SCHEMA || prompt.package_version !== expectedVersion) {
      throw Object.assign(
        new Error("BBK_PROMPT_STATUS_UNAVAILABLE"),
        { qualificationFailure: runtimeFailure("BBK_PROMPT_STATUS_UNAVAILABLE", "The extension did not expose a version-bound prompt-integrity status.") },
      );
    }
    if (requireProviderReceipt) {
      const providerCount = Number(prompt.provider_request_count || 0);
      const guarantee = String(prompt.current_guarantee || "");
      if (providerCount < 1 || prompt.unresolved_failure === true || guarantee !== "PROVIDER_PAYLOAD_VERIFIED_OR_REPAIRED_AT_BBK_HOOK_BOUNDARY") {
        throw Object.assign(
          new Error("BBK_PROVIDER_PROMPT_RECEIPT_NOT_CURRENT"),
          { qualificationFailure: runtimeFailure("BBK_PROVIDER_PROMPT_RECEIPT_NOT_CURRENT", "The current session has not established a successful extension-owned provider prompt receipt.", { provider_request_count: providerCount, current_guarantee: guarantee, unresolved_failure: Boolean(prompt.unresolved_failure) }) },
        );
      }
    }
    return {
      schema: runtime.schema,
      package_version: runtime.package_version,
      mode_enabled: runtime.isModeEnabled(),
      mode_activated_at: modeActivatedAt,
      prompt_status: prompt,
      activity_status: runtime.activityStatus(),
      coordination_status: runtime.coordinationStatus(ctx),
    };
  }

  function rememberFailure(error) {
    startupFailure = error?.qualificationFailure || runtimeFailure(
      "ALPHA17_MANUAL_BOOTSTRAP_FAILED",
      String(error?.message || error),
    );
    return startupFailure;
  }

  pi.on?.("session_start", async (event, ctx) => {
    try {
      runtime = globalThis[BBK_RUNTIME_SYMBOL];
      if (!runtime || runtime.schema !== EXPECTED_RUNTIME_SCHEMA) {
        throw Object.assign(
          new Error("BBK_OMP_EXTENSION_NOT_ACTIVE"),
          { qualificationFailure: runtimeFailure("BBK_OMP_EXTENSION_NOT_ACTIVE", "The manual helper loaded without the BBK extension. Skill discovery is not an acceptable substitute for mode activation.") },
        );
      }
      const expectedVersion = requireEnv("BBK_EXPECTED_PACKAGE_VERSION");
      if (runtime.package_version !== expectedVersion) {
        throw Object.assign(
          new Error("BBK_OMP_EXTENSION_VERSION_MISMATCH"),
          { qualificationFailure: runtimeFailure("BBK_OMP_EXTENSION_VERSION_MISMATCH", "The manual helper and BBK extension versions differ.", { expected_version: expectedVersion, observed_version: runtime.package_version }) },
        );
      }
      runtime.enterMode(ctx);
      modeActivatedAt = new Date().toISOString();
      inspectRuntime(ctx);
      const sid = sessionId(ctx);
      if (!sid) throw new Error("ALPHA17_MANUAL_SESSION_ID_REQUIRED");
      const bootstrapArgs = [
        "--project-root", requireEnv("BBK_PROJECT_ROOT"),
        "--session-id", sid,
        "--host-version", requireEnv("BBK_OMP_HOST_VERSION"),
        "--git", requireEnv("BBK_GIT"),
        "--mise", requireEnv("BBK_MISE"),
      ];
      const parentSid = parentSessionId(event);
      if (parentSid) bootstrapArgs.push("--parent-session-id", parentSid);
      bootstrap = runPython("bootstrap-binding.py", bootstrapArgs);
      const root = rootBootstrap(bootstrap);
      if (!root) throw new Error("ALPHA17_MANUAL_BOOTSTRAP_ROOT_UNAVAILABLE");
      if (bootstrap.is_root_session !== false && root.root_session_id === sid) {
        ctx?.ui?.notify?.("BBK extension verified and persistent mode activated. Paste EXACT-OMP-PROMPT.md.", "info");
      }
    } catch (error) {
      const failure = rememberFailure(error);
      ctx?.ui?.notify?.(`${failure.code}: ${failure.message}`, "error");
    }
  });

  pi.on?.("before_agent_start", async (_event, ctx) => {
    if (startupFailure) {
      return {
        systemPrompt: [
          "<bbk-manual-qualification-fail-closed>",
          `The Alpha.17 manual harness is blocked: ${startupFailure.code}: ${startupFailure.message}`,
          startupFailure.smallest_next_action,
          "Do not plan, dispatch agents, mutate files, or imitate BBK through a skill or generic tools.",
          "</bbk-manual-qualification-fail-closed>",
        ],
      };
    }
    try {
      inspectRuntime(ctx);
    } catch (error) {
      const failure = rememberFailure(error);
      return {
        systemPrompt: [
          "<bbk-manual-qualification-fail-closed>",
          `The Alpha.17 manual harness lost its extension-owned mode binding: ${failure.code}: ${failure.message}`,
          failure.smallest_next_action,
          "Do not continue this campaign.",
          "</bbk-manual-qualification-fail-closed>",
        ],
      };
    }
    return undefined;
  });

  pi.on?.("tool_call", async (event) => {
    if (!startupFailure) return undefined;
    if (String(event?.toolName || "") === "bbk_manual_qualification_status") return undefined;
    return {
      block: true,
      reason: `${startupFailure.code}: ${startupFailure.message} ${startupFailure.smallest_next_action}`,
      details: startupFailure,
    };
  });

  pi.registerTool({
    name: "bbk_manual_qualification_status",
    label: "BBK Alpha.17 Manual Harness Status",
    description: "Fail-closed proof that the exact BBK extension is loaded, persistent BBK mode is active, and the current provider prompt has an extension-owned integrity receipt.",
    parameters: z.object({}),
    async execute(_id, _params, _signal, _onUpdate, ctx) {
      if (startupFailure) {
        return { content: [{ type: "text", text: JSON.stringify(startupFailure, null, 2) }], details: startupFailure };
      }
      try {
        const sid = sessionId(ctx);
        if (!bootstrap) {
          const p = path.join(requireEnv("BBK_PROJECT_ROOT"), ".bbk", "manual-qualification", "bootstrap.json");
          bootstrap = JSON.parse(readFileSync(p, "utf8"));
        }
        const root = rootBootstrap(bootstrap);
        if (!root || root.root_session_id !== sid) throw new Error("ALPHA17_MANUAL_SESSION_BINDING_MISMATCH");
        const runtimeStatus = inspectRuntime(ctx, { requireProviderReceipt: true });
        const status = {
          schema: "bbk.alpha17-manual-harness-status.v2",
          status: "PASS",
          session_id: sid,
          skill_fallback_permitted: false,
          root_binding_ref: root.root_binding_ref,
          root_invocation_id: root.root_invocation_id,
          extension_runtime: runtimeStatus,
          bootstrap: root,
        };
        return { content: [{ type: "text", text: JSON.stringify(status, null, 2) }], details: status };
      } catch (error) {
        const failure = rememberFailure(error);
        return { content: [{ type: "text", text: JSON.stringify(failure, null, 2) }], details: failure };
      }
    },
  });

  pi.registerTool({
    name: "bbk_manual_qualification_integrate",
    label: "BBK Alpha.17 Manual Content-Neutral Integration",
    description: "Qualification-only bridge to the RC content-neutral jj adapter. It accepts only the two predefined activated worker attempts and denies conflict resolution.",
    parameters: z.object({ bindingRef: z.string(), invocationId: z.string(), idempotencyKey: z.string() }),
    async execute(_id, params, _signal, _onUpdate, ctx) {
      const sid = sessionId(ctx);
      inspectRuntime(ctx, { requireProviderReceipt: true });
      const p = path.join(requireEnv("BBK_PROJECT_ROOT"), ".bbk", "manual-qualification", "bootstrap.json");
      const root = rootBootstrap(bootstrap || JSON.parse(readFileSync(p, "utf8")));
      if (!root || root.root_session_id !== sid) throw new Error("ALPHA17_MANUAL_INTEGRATION_ROOT_REQUIRED");
      const result = runPython("manual-integration.py", [
        "--project-root", requireEnv("BBK_PROJECT_ROOT"),
        "--session-id", sid,
        "--binding-ref", params.bindingRef,
        "--invocation-id", params.invocationId,
        "--idempotency-key", params.idempotencyKey,
        "--git", requireEnv("BBK_GIT"),
        "--mise", requireEnv("BBK_MISE"),
      ], null, { preserveStructuredNonpass: true });
      return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }], details: result };
    },
  });
}
