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

//: One bounded pending notice per session. The edit-time notice is computed
//: in `tool.execute.after`, but only the session `context` hook is proven to
//: reach the model, so the notice waits for the next context call and is
//: consumed once. Operations check answer support independently of notice
//: delivery (FD-52); agent lifecycle actions remain required. FD-53 qualifies
//: claims about actual host delivery.
const PENDING_LIMIT = 8;
const NOTICE_LIMIT = 2000;

function sessionKey(event) {
  const value =
    (event && event.data && event.data.sessionID) ||
    (event && (event.sessionID || event.session_id)) ||
    (event && event.session && event.session.id) ||
    "";
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

function rememberNotice(pending, sessionID, notice, paths = []) {
  if (!notice) return;
  if (pending.size >= PENDING_LIMIT && !pending.has(sessionID)) {
    const oldest = pending.keys().next().value;
    console.warn("span: an undelivered lifecycle notice expired at the session bound; consult Span before completing work.");
    pending.delete(oldest);
  }
  pending.set(sessionID, { text: notice.slice(0, NOTICE_LIMIT), paths });
}

function filePathsFromArgs(args) {
  const found = [];
  const walk = (node, depth) => {
    if (depth > 4 || found.length > 16) return;
    if (typeof node === "string") {
      if (
        node.includes("/") &&
        !node.startsWith("{") &&
        node.length < 512
      ) {
        found.push(node);
      }
      return;
    }
    if (Array.isArray(node)) {
      node.forEach((v) => walk(v, depth + 1));
      return;
    }
    if (node && typeof node === "object") {
      for (const key of [
        "filePath",
        "file_path",
        "path",
        "filename",
        "file",
      ]) {
        if (typeof node[key] === "string") found.push(node[key]);
      }
      Object.values(node).forEach((v) => walk(v, depth + 1));
    }
  };
  walk(args, 0);
  return [...new Set(found)];
}

function handleSessionEvent(event, pending, checked, locationRoot) {
  if (!event || typeof event.type !== "string") return;
  if (event.type === "session.created") {
    const notice = run(resolveBin(), [
      "--repo-root",
      locationRoot,
      "session-start",
    ]);
    rememberNotice(pending, sessionKey(event), notice);
  } else if (event.type === "session.idle") {
    const key = sessionKey(event);
    const waiting = pending.get(key);
    if (!waiting || waiting.paths.length === 0) return;
    const notice = run(resolveBin(), [
      "--repo-root",
      locationRoot,
      "session-stop",
    ], JSON.stringify(waiting.paths.map((file_path) => ({ file_path }))));
    if (notice) rememberNotice(pending, key, notice, waiting.paths);
  } else if (event.type === "session.deleted") {
    pending.delete(sessionKey(event));
    checked.delete(sessionKey(event));
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
// Operational registered repositories receive the primer even when cold.
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
          // V2 passes one mutable event; accept the documented shape but
          // also tolerate adjacent shapes. Run only on a positively
          // identified edit/write tool with at least one path; otherwise
          // skip silently rather than guessing.
          const toolName =
            (event &&
              (event.tool ||
                event.toolName ||
                event.name ||
                (event.input &&
                  (event.input.tool || event.input.name)) ||
                "")) ||
            "";
          if (!["edit", "write"].includes(toolName)) return;
          const changed = event || {};
          if (sessionKey(changed) === "*") {
            console.warn("span: edit notice has no session identity; reconsider changed paths before completing work.");
            return;
          }
          const paths = filePathsFromArgs(changed);
          if (paths.length === 0) return;
          const notice = run(resolveBin(), ["source-changed", ...paths]);
          if (!notice) return;
          const relative = relativePaths(paths, locationRoot);
          const reminder = relative.length
            ? " call reconsider(changed_paths=" +
              JSON.stringify(relative) +
              ") after editing; investigate and record supported dispositions before completing work."
            : "";
          rememberNotice(
            pending,
            sessionKey(changed),
            notice + reminder,
            paths,
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
          const sessionID = sessionKey(event || {});
          // The edit-time notice is delivered once, on the next context call.
          // Session identity is required; notices never cross session boundaries.
          const pendingNotice = pending.get(sessionID);
          if (pendingNotice !== undefined) {
            if (event && Array.isArray(event.system)) {
              event.system.push({ type: "text", text: pendingNotice.text });
              pending.delete(sessionID);
            }
          }
          if (sessionID === "*" || checked.has(sessionID)) return;
          checked.add(sessionID);
          const notice = run(resolveBin(), [
            "--repo-root",
            locationRoot,
            "adoption-primer",
          ]);
          if (!notice) return;
          if (!event || !Array.isArray(event.system)) return;
          event.system.push({ type: "text", text: notice });
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
