// FD-53 delivery proof: the edit-time notice reaches `event.system` once.
//
// Run from the repository root with:
//   node --test tests/plugin/test_span_hooks_notice.mjs
//
// The plugin resolves its hook binary from SPAN_HOOKS_BIN. This test points it
// at a small shell fixture so no installation or store is required.

import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PLUGIN = path.join(
  HERE,
  "..",
  "..",
  "integrations",
  "hosts",
  "opencode",
  "span-hooks.js",
);

const NOTICE =
  "span: repo needs attention: 1 recorded understanding(s) affected " +
  "(u-1); call ask or reconsider after editing.";

function makeFixture(root) {
  const bin = path.join(root, "fake-span-hooks");
  fs.writeFileSync(
    bin,
    [
      "#!/bin/sh",
      'case "$*" in',
      `  *source-changed*) echo "${NOTICE}" ;;`,
      "esac",
      "",
    ].join("\n"),
    { mode: 0o755 },
  );
  return bin;
}

async function loadPlugin() {
  return import(pathToFileURL(PLUGIN).href + "?fixture=" + encodeURIComponent(process.env.SPAN_HOOKS_BIN));
}

function fakeContext(root) {
  const registered = {};
  return {
    registered,
    ctx: {
      location: { directory: root },
      event: {
        subscribe: async function* () {},
      },
      tool: {
        list: async () => [{ id: "span_ask" }],
        hook: async (name, handler) => {
          registered[`tool:${name}`] = handler;
        },
      },
      session: {
        hook: async (name, handler) => {
          registered[`session:${name}`] = handler;
          return { dispose() {} };
        },
      },
    },
  };
}

test("the edit-time notice reaches event.system once", async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "span-hooks-"));
  const bin = makeFixture(root);
  const previous = process.env.SPAN_HOOKS_BIN;
  process.env.SPAN_HOOKS_BIN = bin;
  try {
    const plugin = (await loadPlugin()).default;
    const { ctx, registered } = fakeContext(root);
    const dispose = await plugin.setup(ctx);
    try {
      registered["tool:execute.after"]({
        sessionID: "session-1",
        tool: "edit",
        filePath: path.join(root, "src/a.js"),
      });

      const first = { sessionID: "session-1", system: [] };
      registered["session:context"](first);
      assert.equal(first.system.length, 1);
      assert.match(first.system[0].text, /1 recorded understanding/);
      assert.match(
        first.system[0].text,
        /reconsider\(changed_paths=\["src\/a\.js"\]\)/,
      );

      const second = { sessionID: "session-1", system: [] };
      registered["session:context"](second);
      assert.equal(second.system.length, 0);
    } finally {
      if (typeof dispose === "function") dispose();
    }
  } finally {
    if (previous === undefined) delete process.env.SPAN_HOOKS_BIN;
    else process.env.SPAN_HOOKS_BIN = previous;
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test("a missing hook binary leaves the session silent and running", async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "span-hooks-"));
  const previous = process.env.SPAN_HOOKS_BIN;
  process.env.SPAN_HOOKS_BIN = path.join(root, "absent");
  try {
    const plugin = (await loadPlugin()).default;
    const { ctx, registered } = fakeContext(root);
    const dispose = await plugin.setup(ctx);
    try {
      registered["tool:execute.after"]({
        sessionID: "session-1",
        tool: "edit",
        filePath: path.join(root, "src/a.js"),
      });
      const event = { sessionID: "session-1", system: [] };
      registered["session:context"](event);
      assert.equal(event.system.length, 0);
    } finally {
      if (typeof dispose === "function") dispose();
    }
  } finally {
    if (previous === undefined) delete process.env.SPAN_HOOKS_BIN;
    else process.env.SPAN_HOOKS_BIN = previous;
    fs.rmSync(root, { recursive: true, force: true });
  }
});


test("idle forwards unconsumed edit paths through stdin with native session identity", async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "span-idle-"));
  const bin = path.join(root, "fake-span-hooks");
  const received = path.join(root, "received.json");
  fs.writeFileSync(bin, `#!/bin/sh
case "$*" in
  *source-changed*) echo "changed" ;;
  *session-stop*) cat > "${received}"; echo "close: reconsider changed paths" ;;
esac
`, { mode: 0o755 });
  const previous = process.env.SPAN_HOOKS_BIN;
  process.env.SPAN_HOOKS_BIN = bin;
  let release;
  const ready = new Promise((resolve) => { release = resolve; });
  let delivered;
  const done = new Promise((resolve) => { delivered = resolve; });
  const { ctx, registered } = fakeContext(root);
  ctx.event.subscribe = async function* () {
    await ready;
    yield { type: "session.idle", data: { sessionID: "session-1" } };
    delivered();
  };
  const dispose = await (await loadPlugin()).default.setup(ctx);
  try {
    registered["tool:execute.after"]({sessionID:"session-1", tool:"edit", filePath:path.join(root,"src/a.js")});
    release();
    await done;
    assert.deepEqual(JSON.parse(fs.readFileSync(received,"utf8")), [{file_path:path.join(root,"src/a.js")}]);
    const other = {sessionID:"session-2",system:[]};
    registered["session:context"](other);
    assert.equal(other.system.length,0);
    const first = {sessionID:"session-1",system:[]};
    registered["session:context"](first);
    assert.match(first.system[0].text,/close: reconsider/);
    const resumed = {sessionID:"session-1",system:[]};
    registered["session:context"](resumed);
    assert.equal(resumed.system.length,0);
  } finally {
    dispose();
    if(previous===undefined) delete process.env.SPAN_HOOKS_BIN;
    else process.env.SPAN_HOOKS_BIN=previous;
    fs.rmSync(root,{recursive:true,force:true});
  }
});

test("undelivered notices survive malformed context and are reaped on session deletion", async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "span-reap-"));
  const previous = process.env.SPAN_HOOKS_BIN;
  process.env.SPAN_HOOKS_BIN = makeFixture(root);
  let release;
  const ready = new Promise((resolve) => { release = resolve; });
  let delivered;
  const done = new Promise((resolve) => { delivered = resolve; });
  const { ctx, registered } = fakeContext(root);
  ctx.event.subscribe = async function* () {
    await ready;
    yield { type: "session.deleted", data: { sessionID: "session-1" } };
    delivered();
  };
  const dispose = await (await loadPlugin()).default.setup(ctx);
  try {
    const edit = () => registered["tool:execute.after"]({sessionID:"session-1",tool:"edit",filePath:path.join(root,"src/a.js")});
    edit();
    registered["session:context"]({sessionID:"session-1"});
    const valid = {sessionID:"session-1",system:[]};
    registered["session:context"](valid);
    assert.equal(valid.system.length,1);
    edit();
    release();
    await done;
    const afterDelete = {sessionID:"session-1",system:[]};
    registered["session:context"](afterDelete);
    assert.equal(afterDelete.system.length,0);
    edit();
    dispose();
    const afterDispose = {sessionID:"session-1",system:[]};
    registered["session:context"](afterDispose);
    assert.equal(afterDispose.system.length,0);
  } finally {
    dispose();
    if(previous===undefined) delete process.env.SPAN_HOOKS_BIN;
    else process.env.SPAN_HOOKS_BIN=previous;
    fs.rmSync(root,{recursive:true,force:true});
  }
});
