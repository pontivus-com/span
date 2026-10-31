// Span lifecycle notices (read-only).
//
// Report-only hooks for the Span lifecycle: surfaces only event-local
// action (an absent/old store, or recorded conclusions whose cited
// source changed) and stays silent otherwise. Never writes, records,
// reassesses, interprets, rebuilds, or initializes. Silent no-op when
// Span is not installed.

import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";

const CANDIDATES = [
  process.env.SPAN_HOOKS_BIN,
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

function run(bin, args) {
  try {
    const out = execFileSync(bin, args, {
      encoding: "utf8",
      timeout: 8000,
      stdio: ["ignore", "pipe", "ignore"],
    });
    return (out || "").trim();
  } catch {
    return "";
  }
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
// Report-only safety is preserved: the plugin only shells out to the
// installed span-hooks binary, stays silent when Span is absent or the
// store is clean, and every failure path is a silent no-op that never
// breaks the session. Repo root comes from ctx.location.directory.
export default {
  id: "span-hooks",
  async setup(ctx) {
    const controller = new AbortController();
    const locationRoot =
      (ctx && ctx.location && ctx.location.directory) || process.cwd();

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
            if (!event || typeof event.type !== "string") continue;
            if (event.type === "session.created") {
              const notice = run(resolveBin(), [
                "--repo-root",
                locationRoot,
                "session-start",
              ]);
              if (notice) console.log(notice);
            } else if (event.type === "session.idle") {
              const notice = run(resolveBin(), [
                "--repo-root",
                locationRoot,
                "session-stop",
              ]);
              if (notice) console.log(notice);
            }
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
          const paths = filePathsFromArgs(event || {});
          if (paths.length === 0) return;
          const notice = run(resolveBin(), [
            "source-changed",
            ...paths,
          ]);
          if (notice) console.log(notice);
        } catch {
          // Never break the session on hook failure.
        }
      });
    }

    return () => controller.abort();
  },
};
