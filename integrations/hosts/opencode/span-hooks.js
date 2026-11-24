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
    return (out || "").trim();
  } catch {
    return "";
  }
}

//: One bounded pending lifecycle state per session. Session-entry text and
//: changed-scope obligations are retained independently so delivering one cannot
//: discard the other. Only the session context hook is proven to reach the
//: model; successful delivery hands off the corresponding notice. Operations
//: check answer support independently of notice delivery (FD-52).
const PENDING_LIMIT = 8;
const NOTICE_LIMIT = 2000;

function sessionKeyFromNativeEvent(event) {
  const value = event && event.data && event.data.sessionID;
  return typeof value === "string" && value ? value : "*";
}

function sessionKeyFromHook(event) {
  const value = event && event.sessionID;
  return typeof value === "string" && value ? value : "*";
}

function relativePaths(paths, root) {
  const rootPath = root ? path.resolve(root) : null;
  const found = [];
  for (const item of paths) {
    let value = item;
    if (rootPath && path.isAbsolute(item)) {
      const relative = path.relative(rootPath, item);
      if (!relative || relative.startsWith("..") || path.isAbsolute(relative)) {
        continue;
      }
      value = relative;
    }
    if (
      typeof value !== "string" ||
      !value ||
      path.isAbsolute(value) ||
      value.startsWith("..")
    ) {
      continue;
    }
    found.push(value.split(path.sep).join("/"));
  }
  return [...new Set(found)];
}

function ensurePendingCapacity(pending, sessionID) {
  if (pending.size >= PENDING_LIMIT && !pending.has(sessionID)) {
    const oldest = pending.keys().next().value;
    console.warn("span: undelivered lifecycle obligations expired at the session bound; consult Span before completing work.");
    pending.delete(oldest);
  }
}

function pendingState(pending, sessionID) {
  ensurePendingCapacity(pending, sessionID);
  const current = pending.get(sessionID);
  if (current) return current;
  const created = { entryText: "", changeText: "", paths: [] };
  pending.set(sessionID, created);
  return created;
}

function rememberEntryNotice(pending, sessionID, notice) {
  if (!notice) return;
  const state = pendingState(pending, sessionID);
  state.entryText = notice.slice(0, NOTICE_LIMIT);
}

function rememberChangedPaths(pending, sessionID, paths) {
  const state = pendingState(pending, sessionID);
  state.paths = [...new Set([...state.paths, ...paths])];
  return state.paths;
}

function rememberChangeNotice(pending, sessionID, notice) {
  if (!notice) return;
  const state = pendingState(pending, sessionID);
  state.changeText = notice.slice(0, NOTICE_LIMIT);
}

function removeEmptyPending(pending, sessionID, state) {
  if (!state.entryText && !state.changeText && state.paths.length === 0) {
    pending.delete(sessionID);
  }
}

function filePathsFromEditEvent(event) {
  if (!event || !["edit", "write"].includes(event.tool)) return [];
  const input = event.input;
  if (!input || typeof input !== "object" || typeof input.path !== "string") {
    console.warn("span: OpenCode edit/write hook skipped because documented input.path is absent.");
    return [];
  }
  return [input.path];
}

function handleSessionEvent(event, pending, checked, locationRoot) {
  if (!event || typeof event.type !== "string") return;
  if (event.type === "session.created") {
    const key = sessionKeyFromNativeEvent(event);
    if (key === "*" || checked.has(key)) return;
    const notice = run(resolveBin(), [
      "--repo-root",
      locationRoot,
      "session-start",
    ]);
    if (notice) {
      checked.add(key);
      rememberEntryNotice(pending, key, notice);
    }
  } else if (event.type === "session.idle") {
    const key = sessionKeyFromNativeEvent(event);
    const waiting = pending.get(key);
    if (!waiting || waiting.paths.length === 0) return;
    const notice = run(resolveBin(), [
      "--repo-root",
      locationRoot,
      "session-stop",
    ], JSON.stringify(waiting.paths.map((file_path) => ({ file_path }))));
    rememberChangeNotice(pending, key, notice);
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
// Helper failure does not abort the session; missing session identity and
// undelivered capacity expiry are diagnosed. Repo root is ctx.location.directory.
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
          if (!event || !["edit", "write"].includes(event.tool)) return;
          const key = sessionKeyFromHook(event);
          if (key === "*") {
            console.warn("span: edit notice has no session identity; reconsider changed paths before completing work.");
            return;
          }
          const paths = filePathsFromEditEvent(event);
          if (paths.length === 0) return;
          const completePaths = rememberChangedPaths(pending, key, paths);
          const notice = run(resolveBin(), ["source-changed", ...completePaths]);
          if (!notice) return;
          const relative = relativePaths(completePaths, locationRoot);
          const reminder = relative.length
            ? " call reconsider " +
              JSON.stringify({
                repository_id: path.basename(path.resolve(locationRoot)),
                changed_paths: relative,
              }) +
              " after editing; investigate and record supported dispositions before completing work."
            : "";
          rememberChangeNotice(pending, key, notice + reminder);
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
            const notice = run(resolveBin(), [
              "--repo-root",
              locationRoot,
              "session-start",
            ]);
            rememberEntryNotice(pending, sessionID, notice);
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
