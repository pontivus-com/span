// Span lifecycle notices (read-only).
//
// Deliver the required lifecycle primer and event-local readiness/support
// reminders. The agent authors and records semantic understanding; the plugin
// retains bounded transient notices for delivery through the context hook.

import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const SIBLING = path.join(
  path.dirname(fileURLToPath(import.meta.url)),
  "span-hooks",
);

const CANDIDATES = [
  process.env.SPAN_HOOKS_BIN,
  SIBLING,
  path.join(
    process.env.HOME || "~",
    ".local/share/span/venv/bin/span-hooks"
  ),
  "span-hooks",
].filter(Boolean);

function resolveBin() {
  for (const candidate of CANDIDATES) {
    try {
      if (candidate === "span-hooks") {
        execFileSync("command", ["-v", "span-hooks"], {
          stdio: ["ignore", "pipe", "ignore"],
        });
        return candidate;
      }
      fs.accessSync(candidate, fs.constants.X_OK);
      return candidate;
    } catch {
      // try next candidate
    }
  }
  return null;
}

function run(bin, args, input) {
  try {
    const out = execFileSync(bin, args, {
      encoding: "utf8",
      timeout: 8000,
      input,
      stdio: [input === undefined ? "ignore" : "pipe", "pipe", "ignore"],
    });
    return { ok: true, text: (out || "").trim() };
  } catch {
    return { ok: false, text: "" };
  }
}

//: One transient pending lifecycle state per session. Session-entry text and
//: changed-scope obligations are retained independently until delivery or the
//: host explicitly discards the session. Only the session context hook is proven
//: to reach the model. Operations check answer support independently of notice
//: delivery (FD-52).

function sessionKeyFromNativeEvent(event) {
  const value = event && event.data && event.data.sessionID;
  return typeof value === "string" && value ? value : "*";
}

function sessionKeyFromHook(event) {
  const value = event && event.sessionID;
  return typeof value === "string" && value ? value : "*";
}

function pendingState(pending, sessionID) {
  const current = pending.get(sessionID);
  if (current) return current;
  const created = { entryText: "", changeText: "", paths: [] };
  pending.set(sessionID, created);
  return created;
}

function rememberEntryNotice(pending, sessionID, notice) {
  if (!notice) return;
  const state = pendingState(pending, sessionID);
  state.entryText = notice;
}

function rememberChangedPaths(pending, sessionID, paths) {
  const state = pendingState(pending, sessionID);
  state.paths = [...new Set([...state.paths, ...paths])];
  return state.paths;
}

function rememberChangeNotice(pending, sessionID, notice) {
  if (!notice) return;
  const state = pendingState(pending, sessionID);
  state.changeText = notice;
}

function removeEmptyPending(pending, sessionID, state) {
  if (!state.entryText && !state.changeText && state.paths.length === 0) {
    pending.delete(sessionID);
  }
}

function patchPaths(patchText) {
  if (typeof patchText !== "string") return null;
  const prefixes = [
    "*** Add File: ",
    "*** Update File: ",
    "*** Delete File: ",
    "*** Move to: ",
  ];
  const found = [];
  let sawFileMarker = false;
  for (const line of patchText.split(/\r?\n/)) {
    for (const prefix of prefixes) {
      if (!line.startsWith(prefix)) continue;
      sawFileMarker = true;
      const value = line.slice(prefix.length).trim();
      if (!value) return null;
      found.push(value);
      break;
    }
  }
  return sawFileMarker ? [...new Set(found)] : null;
}

function filePathsFromEditEvent(event) {
  if (!event || !["edit", "write", "patch"].includes(event.tool)) return [];
  const input = event.input;
  if (!input || typeof input !== "object") return null;
  if (event.tool === "patch") {
    return patchPaths(input.patchText);
  }
  return typeof input.path === "string" ? [input.path] : null;
}

function handleSessionEvent(event, pending, checked, locationRoot) {
  if (!event || typeof event.type !== "string") return;
  if (event.type === "session.created") {
    const key = sessionKeyFromNativeEvent(event);
    if (key === "*" || checked.has(key)) return;
    const result = run(resolveBin(), [
      "--repo-root",
      locationRoot,
      "session-start",
    ]);
    if (result.ok && result.text) {
      checked.add(key);
      rememberEntryNotice(pending, key, result.text);
    }
  } else if (event.type === "session.idle") {
    const key = sessionKeyFromNativeEvent(event);
    const waiting = pending.get(key);
    if (!waiting || waiting.paths.length === 0) return;
    const result = run(resolveBin(), [
      "--repo-root",
      locationRoot,
      "session-stop",
    ], JSON.stringify(waiting.paths.map((file_path) => ({ file_path }))));
    if (!result.ok) return;
    const reminder =
      `span: OpenCode has ${waiting.paths.length} changed path(s) awaiting handoff; ` +
      "call reconsider with the complete changed scope before completing work.";
    rememberChangeNotice(
      pending,
      key,
      result.text ? result.text + " " + reminder : reminder,
    );
  } else if (event.type === "session.deleted") {
    pending.delete(sessionKeyFromNativeEvent(event));
    checked.delete(sessionKeyFromNativeEvent(event));
  }
}

// OpenCode v2 server plugin definition.
// See https://opencode.ai/v2/docs/build/plugins and
// https://opencode.ai/v2/docs/build/plugins/migrate-v1.
// The v2 runtime loads the default export, which must carry a stable id
// plus setup (or effect). V1 implementations do not run in V2, so the
// session/tool hooks below are registered through the V2 context API:
// session boundary notices via ctx.event.subscribe(), post-edit notices
// via ctx.tool.hook("execute.after", ...), which receives one mutable
// event (not v1 input/output pairs).
//
// The installed span-hooks runner supplies lifecycle and support notices.
// Operational registered repositories receive one composed entry notice.
// Helper failure does not abort the session; missing or incomplete native scope
// is diagnosed without discarding retained changed paths. Repo root is
// ctx.location.directory.
export default {
  id: "span-hooks",
  async setup(ctx) {
    const controller = new AbortController();
    const locationRoot =
      (ctx && ctx.location && ctx.location.directory) || process.cwd();
    const pending = new Map();
    const checked = new Set();

    if (
      ctx &&
      ctx.event &&
      typeof ctx.event.subscribe === "function"
    ) {
      void (async () => {
        try {
          for await (const event of ctx.event.subscribe({
            signal: controller.signal,
          })) {
            handleSessionEvent(event, pending, checked, locationRoot);
          }
        } catch {
          // Subscription ended (abort or server shutdown); silent.
        }
      })();
    }

    if (ctx && ctx.tool && typeof ctx.tool.hook === "function") {
      await ctx.tool.hook("execute.after", (event) => {
        try {
          // OpenCode V2 documents execute.after as one mutable event with
          // event.tool, event.input and event.sessionID. Do not guess adjacent
          // legacy shapes into semantic scope.
          if (!event || !["edit", "write", "patch"].includes(event.tool)) return;
          const key = sessionKeyFromHook(event);
          if (key === "*") {
            console.warn("span: edit notice has no session identity; reconsider changed paths before completing work.");
            return;
          }
          const paths = filePathsFromEditEvent(event);
          if (paths === null) {
            rememberChangeNotice(
              pending,
              key,
              "span: OpenCode observed an edit/write event but could not normalize " +
                "its complete changed scope from the documented native payload; " +
                "reconsider the complete edited scope before completing work.",
            );
            return;
          }
          if (paths.length === 0) return;
          const absolutePaths = paths.map((value) =>
            path.isAbsolute(value) ? value : path.join(locationRoot, value),
          );
          const completePaths = rememberChangedPaths(pending, key, absolutePaths);
          const result = run(resolveBin(), ["source-changed", ...completePaths]);
          if (!result.ok) return;
          const reminder =
            `span: OpenCode observed ${completePaths.length} changed path(s); ` +
            `call reconsider with the complete changed scope from this ${event.tool} ` +
            "before completing work.";
          rememberChangeNotice(
            pending,
            key,
            result.text ? result.text + " " + reminder : reminder,
          );
        } catch {
          // Never break the session on hook failure.
        }
      });
    }

    // OpenCode dispatches the first request before a local MCP server has
    // finished connecting. Wait (bounded) at prompt admission so the first
    // tool list already contains the Span tools; otherwise the agent cannot
    // consult Span before investigation. The lifecycle obligation also appears
    // in the managed instructions when this readiness notice cannot arrive.
    let mcpReady = false;
    if (ctx && ctx.session && typeof ctx.session.hook === "function") {
      await ctx.session.hook("prompt", async () => {
        if (mcpReady) return;
        const deadline = Date.now() + 3000;
        while (Date.now() < deadline) {
          try {
            const tools = await ctx.tool.list();
            if (tools.some((tool) => String(tool.id).endsWith("_ask"))) {
              mcpReady = true;
              return;
            }
          } catch {
            // keep waiting
          }
          await new Promise((resolve) => setTimeout(resolve, 50));
        }
      });
    }

    // FD-58 required lifecycle notice for cold and warm repositories.
    let contextRegistration = null;
    if (ctx && ctx.session && typeof ctx.session.hook === "function") {
      contextRegistration = await ctx.session.hook("context", (event) => {
        try {
          const sessionID = sessionKeyFromHook(event || {});
          if (sessionID === "*") return;

          // session.created normally prepares this entry notice. If that native
          // event was missed, the first context hook performs the same composed
          // session-start check as the fallback. It never emits a second entry.
          if (!checked.has(sessionID)) {
            checked.add(sessionID);
            const result = run(resolveBin(), [
              "--repo-root",
              locationRoot,
              "session-start",
            ]);
            if (result.ok) rememberEntryNotice(pending, sessionID, result.text);
          }

          const state = pending.get(sessionID);
          if (!state || !event || !Array.isArray(event.system)) return;
          const parts = [];
          if (state.entryText) parts.push(state.entryText);
          if (state.changeText) parts.push(state.changeText);
          if (parts.length === 0) return;

          // Only delivery of a change notice hands off the accumulated paths.
          event.system.push({ type: "text", text: parts.join(" ") });
          const handedOffChange = Boolean(state.changeText);
          state.entryText = "";
          state.changeText = "";
          if (handedOffChange) state.paths = [];
          removeEmptyPending(pending, sessionID, state);
        } catch {
          // A notice never breaks a model call.
        }
      });
    }

    return () => {
      controller.abort();
      pending.clear();
      checked.clear();
      if (
        contextRegistration &&
        typeof contextRegistration.dispose === "function"
      ) {
        void contextRegistration.dispose();
      }
    };
  },
};
