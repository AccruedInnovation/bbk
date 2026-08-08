import { appendFileSync, mkdirSync, realpathSync, writeFileSync } from "node:fs";
import path from "node:path";

function resolvedPath(value) {
  const requested = path.resolve(String(value || ""));
  let probe = requested;
  const suffix = [];
  while (true) {
    try {
      const resolved = typeof realpathSync.native === "function"
        ? realpathSync.native(probe)
        : realpathSync(probe);
      return suffix.length ? path.join(resolved, ...suffix.reverse()) : resolved;
    } catch {
      const parent = path.dirname(probe);
      if (parent === probe) return requested;
      suffix.push(path.basename(probe));
      probe = parent;
    }
  }
}

function containsPath(root, candidate) {
  const base = resolvedPath(root);
  const target = resolvedPath(candidate);
  const normalizedBase = process.platform === "win32" ? base.toLowerCase() : base;
  const normalizedTarget = process.platform === "win32" ? target.toLowerCase() : target;
  return normalizedTarget === normalizedBase
    || normalizedTarget.startsWith(normalizedBase.endsWith(path.sep) ? normalizedBase : `${normalizedBase}${path.sep}`);
}

function contextIdentity(ctx) {
  return {
    cwd: ctx?.cwd || null,
    session_id: ctx?.sessionManager?.getSessionId?.() || null,
    session_file: ctx?.sessionManager?.getSessionFile?.() || null,
  };
}

function eventSummary(event) {
  const result = {
    type: event?.type || null,
    tool_name: event?.toolName || null,
    tool_call_id: event?.toolCallId || null,
    input: event?.input || event?.args || null,
    is_error: event?.isError ?? null,
  };
  if (event?.prompt) result.prompt = String(event.prompt).slice(0, 500);
  if (event?.status) result.status = event.status;
  if (event?.id) result.id = event.id;
  if (event?.agent) result.agent = event.agent;
  if (event?.parentToolCallId) result.parent_tool_call_id = event.parentToolCallId;
  if (event?.sessionFile) result.session_file = event.sessionFile;
  if (event?.detached !== undefined) result.detached = Boolean(event.detached);
  if (event?.result?.content) result.result_text = event.result.content.map(item => item?.text || "").join("\n").slice(0, 500);
  if (event?.content) result.result_text = event.content.map(item => item?.text || "").join("\n").slice(0, 500);
  return result;
}

function record(kind, event, ctx) {
  appendFileSync(
    process.env.BBK_OMP_FIXTURE_LOG,
    `${JSON.stringify({ kind, event: eventSummary(event), context: contextIdentity(ctx) })}\n`,
    "utf8",
  );
}

export default function fixtureExtension(pi) {
  const { z } = pi.zod;
  for (const eventName of [
    "session_start",
    "before_agent_start",
    "before_provider_request",
    "after_provider_response",
    "agent_end",
    "message_end",
    "tool_call",
    "tool_result",
    "tool_execution_start",
    "tool_execution_end",
  ]) {
    pi.on?.(eventName, async (event, ctx) => {
      record(eventName, event, ctx);
      if (eventName === "tool_call" && ["write", "edit", "bash"].includes(event?.toolName)) {
        return {
          block: true,
          reason: `BBK fixture governed mode blocks ambient ${event.toolName} before effect`,
        };
      }
      if (eventName === "tool_call" && event?.toolName === "yield") {
        const input = event?.input && typeof event.input === "object" ? event.input : {};
        const data = input?.result?.data;
        if (data?.schema === "fixture.invalid-role-return.v1") {
          record("yield_validation_block", event, ctx);
          return {
            block: true,
            reason: "BBK fixture rejected malformed role return before yield acceptance",
          };
        }
        if (data?.schema === "fixture.prepared-role-return.v1") {
          record("yield_token_block", event, ctx);
          return {
            block: true,
            reason: "BBK fixture requires the complete immutable prepared yield input",
          };
        }
        if (data?.schema === "fixture.role-return.v1"
          && data?.status === "PASS"
          && data?.identity === "yield-child"
          && /^return:[0-9a-f]{64}$/.test(String(data?.prepared_return_ref || ""))) {
          record("yield_full_document_admission", event, ctx);
          return undefined;
        }
      }
      if (eventName === "tool_call" && event?.toolName === "task") {
        const compact = event?.input && typeof event.input === "object" ? event.input : {};
        const taskItem = Array.isArray(compact.tasks) && compact.tasks.length === 1 ? compact.tasks[0] : null;
        const markerPattern = /^<bbk-spawn-dispatch ref="dispatch:[0-9a-f]{64}"\/>$/;
        const contextMarker = markerPattern.test(String(compact.context || "").trim());
        const taskMarker = markerPattern.test(String(taskItem?.task || "").trim());
        if (contextMarker && taskMarker) {
          const resolved = {
            i: "Testing compact dispatch input replacement",
            context: "# Goal\nProve OMP uses the hook-replaced task payload\n# Constraints\nNo ambient mutation\n# Contract\nReturn one dispatch identity result",
            tasks: [{
              name: "FixtureWorker",
              agent: "fixture_worker",
              task: "# Target\nFIXTURE_CHILD_MARKER dispatch resolution\n# Change\nCall bbk_fixture_identity once with dispatch-child\n# Acceptance\nYield a PASS identity result",
            }],
          };
          record("dispatch_rewrite", { type: "dispatch_rewrite", toolCallId: event?.toolCallId, input: resolved }, ctx);
          for (const key of Object.keys(compact)) delete compact[key];
          Object.assign(compact, resolved);
          event.input = compact;
          return { input: resolved };
        }
      }
      return undefined;
    });
  }

  for (const channel of ["task:subagent:lifecycle", "task:subagent:progress"]) {
    pi.events?.on?.(channel, event => record(channel, event, null));
  }

  pi.registerTool({
    name: "bbk_fixture_scoped_write",
    label: "BBK fixture scoped write",
    description: "Write one fixture file only below the host-supplied governed root.",
    parameters: z.object({ path: z.string(), content: z.string() }),
    async execute(toolCallId, params, _signal, _onUpdate, ctx) {
      record("custom_scoped_write", { type: "custom_scoped_write", toolCallId, input: params }, ctx);
      const root = process.env.BBK_OMP_FIXTURE_ALLOWED_ROOT;
      const target = path.resolve(root, params.path);
      if (!containsPath(root, target)) {
        return {
          content: [{ type: "text", text: "BBK fixture rejected path outside governed root" }],
          details: { status: "BLOCK", target },
          isError: true,
        };
      }
      mkdirSync(path.dirname(target), { recursive: true });
      writeFileSync(target, params.content, "utf8");
      return {
        content: [{ type: "text", text: "BBK fixture scoped write passed" }],
        details: { status: "PASS", target },
      };
    },
  });

  pi.registerTool({
    name: "bbk_fixture_identity",
    label: "BBK fixture identity",
    description: "Return a child identity marker without mutation.",
    parameters: z.object({ value: z.string() }),
    async execute(toolCallId, params, _signal, _onUpdate, ctx) {
      record("custom_identity", { type: "custom_identity", toolCallId, input: params }, ctx);
      return {
        content: [{ type: "text", text: `BBK fixture identity ${params.value}` }],
        details: { status: "PASS", value: params.value },
      };
    },
  });
}
