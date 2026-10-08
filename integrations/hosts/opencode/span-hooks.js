// Span lifecycle notices (read-only).
//
// Report-only hooks for the Span semantic repository: session start
// reports readiness, file edits report dependent semantic items,
// session idle reports closure counts. Never writes, interprets,
// refreshes, or initializes. Silent no-op when Span is not installed.

const fs = require("node:fs");
const path = require("node:path");
const { execFileSync } = require("node:child_process");

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

export const SpanHooksPlugin = async () => {
  const bin = resolveBin();
  if (!bin) return {};
  return {
    event: async ({ event }) => {
      if (!event || typeof event.type !== "string") return;
      if (event.type === "session.created") {
        const notice = run(bin, ["session-start"]);
        if (notice) console.log(notice);
      } else if (event.type === "session.idle") {
        const notice = run(bin, ["session-stop"]);
        if (notice) console.log(notice);
      }
    },
    "tool.execute.after": async (input, output) => {
      const tool = (input && input.tool) || "";
      if (!["edit", "write"].includes(tool)) return;
      const paths = filePathsFromArgs(
        (output && output.args) || {}
      );
      if (paths.length === 0) return;
      const notice = run(bin, ["source-changed", ...paths]);
      if (notice) console.log(notice);
    },
  };
};
