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
        input: { path: path.join(root, "src/a.js") },
      });

      const first = { sessionID: "session-1", system: [] };
      registered["session:context"](first);
      assert.equal(first.system.length, 1);
      assert.match(first.system[0].text, /1 recorded understanding/);
      assert.match(first.system[0].text, /reconsider after editing/);
      assert.doesNotMatch(first.system[0].text, /"changed_paths":/);

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


test("multiple edits are accumulated before lifecycle handoff", async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "span-union-"));
  const bin = path.join(root, "fake-span-hooks");
  const received = path.join(root, "received.txt");
  fs.writeFileSync(bin, `#!/bin/sh
case "$*" in
  *source-changed*) printf '%s\\n' "$@" > "${received}"; echo "changed" ;;
esac
`, { mode: 0o755 });
  const previous = process.env.SPAN_HOOKS_BIN;
  process.env.SPAN_HOOKS_BIN = bin;
  const { ctx, registered } = fakeContext(root);
  const dispose = await (await loadPlugin()).default.setup(ctx);
  try {
    const firstPath = path.join(root, "src/a.js");
    const secondPath = path.join(root, "src/b.js");
    registered["tool:execute.after"]({sessionID:"session-1", tool:"edit", input:{path:firstPath}});
    registered["tool:execute.after"]({sessionID:"session-1", tool:"edit", input:{path:secondPath}});

    const args = fs.readFileSync(received, "utf8").trim().split("\n");
    assert.deepEqual(args, ["source-changed", firstPath, secondPath]);

    const event = {sessionID:"session-1", system:[]};
    registered["session:context"](event);
    assert.equal(event.system.length, 1);
    assert.match(event.system[0].text, /^changed /);
    assert.match(event.system[0].text, /2 changed path\(s\)/);
    assert.match(event.system[0].text, /call reconsider with the complete changed scope/);
  } finally {
    dispose();
    if(previous===undefined) delete process.env.SPAN_HOOKS_BIN;
    else process.env.SPAN_HOOKS_BIN=previous;
    fs.rmSync(root,{recursive:true,force:true});
  }
});


test("native patch payload contributes every changed file to one union", async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "span-patch-"));
  const bin = path.join(root, "fake-span-hooks");
  const received = path.join(root, "received.txt");
  fs.writeFileSync(bin, `#!/bin/sh
case "$*" in
  *source-changed*) printf '%s\\n' "$@" > "${received}"; echo "changed" ;;
esac
`, { mode: 0o755 });
  const previous = process.env.SPAN_HOOKS_BIN;
  process.env.SPAN_HOOKS_BIN = bin;
  const { ctx, registered } = fakeContext(root);
  const dispose = await (await loadPlugin()).default.setup(ctx);
  try {
    registered["tool:execute.after"]({
      sessionID: "session-1",
      tool: "patch",
      input: {
        patchText: [
          "*** Begin Patch",
          "*** Update File: src/a.js",
          "*** Move to: src/moved.js",
          "*** Add File: src/new.js",
          "*** Delete File: src/old.js",
          "*** End Patch",
        ].join("\n"),
      },
    });
    const args = fs.readFileSync(received, "utf8").trim().split("\n");
    assert.deepEqual(args, [
      "source-changed",
      path.join(root, "src/a.js"),
      path.join(root, "src/moved.js"),
      path.join(root, "src/new.js"),
      path.join(root, "src/old.js"),
    ]);
    const event = { sessionID: "session-1", system: [] };
    registered["session:context"](event);
    assert.match(event.system[0].text, /^changed /);
    assert.match(event.system[0].text, /4 changed path\(s\)/);
    assert.match(event.system[0].text, /from this patch/);
  } finally {
    dispose();
    if (previous === undefined) delete process.env.SPAN_HOOKS_BIN;
    else process.env.SPAN_HOOKS_BIN = previous;
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test("malformed native patch is explicit incomplete input and never guessed", async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "span-patch-incomplete-"));
  const bin = path.join(root, "fake-span-hooks");
  const touched = path.join(root, "called");
  fs.writeFileSync(bin, `#!/bin/sh
touch "${touched}"
`, { mode: 0o755 });
  const previous = process.env.SPAN_HOOKS_BIN;
  process.env.SPAN_HOOKS_BIN = bin;
  const { ctx, registered } = fakeContext(root);
  const dispose = await (await loadPlugin()).default.setup(ctx);
  try {
    registered["tool:execute.after"]({
      sessionID: "session-1",
      tool: "patch",
      input: { patchText: "*** Begin Patch\n*** End Patch" },
    });
    assert.equal(fs.existsSync(touched), false);
    const event = { sessionID: "session-1", system: [] };
    registered["session:context"](event);
    assert.equal(event.system.length, 1);
    assert.match(
      event.system[0].text,
      /could not normalize its complete changed scope/,
    );
  } finally {
    dispose();
    if (previous === undefined) delete process.env.SPAN_HOOKS_BIN;
    else process.env.SPAN_HOOKS_BIN = previous;
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test("undelivered session obligations are never evicted by another session", async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "span-no-evict-"));
  const previous = process.env.SPAN_HOOKS_BIN;
  process.env.SPAN_HOOKS_BIN = makeFixture(root);
  const { ctx, registered } = fakeContext(root);
  const dispose = await (await loadPlugin()).default.setup(ctx);
  try {
    for (let index = 0; index < 9; index += 1) {
      registered["tool:execute.after"]({
        sessionID: `session-${index}`,
        tool: "edit",
        input: { path: path.join(root, `src/${index}.js`) },
      });
    }
    const oldest = { sessionID: "session-0", system: [] };
    registered["session:context"](oldest);
    assert.equal(oldest.system.length, 1);
    assert.match(oldest.system[0].text, /1 recorded understanding/);
  } finally {
    dispose();
    if (previous === undefined) delete process.env.SPAN_HOOKS_BIN;
    else process.env.SPAN_HOOKS_BIN = previous;
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test("clean preview still hands off the required reconsider obligation", async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "span-clean-preview-"));
  const bin = path.join(root, "fake-span-hooks");
  fs.writeFileSync(bin, `#!/bin/sh
case "$*" in
  *source-changed*) exit 0 ;;
esac
`, { mode: 0o755 });
  const previous = process.env.SPAN_HOOKS_BIN;
  process.env.SPAN_HOOKS_BIN = bin;
  const { ctx, registered } = fakeContext(root);
  const dispose = await (await loadPlugin()).default.setup(ctx);
  try {
    registered["tool:execute.after"]({
      sessionID: "session-1",
      tool: "edit",
      input: { path: path.join(root, "src/a.js") },
    });

    const first = { sessionID: "session-1", system: [] };
    registered["session:context"](first);
    assert.equal(first.system.length, 1);
    assert.match(
      first.system[0].text,
      /call reconsider with the complete changed scope/,
    );

    const second = { sessionID: "session-1", system: [] };
    registered["session:context"](second);
    assert.equal(second.system.length, 0);
  } finally {
    dispose();
    if (previous === undefined) delete process.env.SPAN_HOOKS_BIN;
    else process.env.SPAN_HOOKS_BIN = previous;
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test("clean completion preview still preserves the outstanding handoff", async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "span-clean-idle-"));
  const bin = path.join(root, "fake-span-hooks");
  fs.writeFileSync(bin, `#!/bin/sh
case "$*" in
  *source-changed*) exit 1 ;;
  *session-stop*) cat >/dev/null; exit 0 ;;
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
    registered["tool:execute.after"]({
      sessionID: "session-1",
      tool: "edit",
      input: { path: path.join(root, "src/a.js") },
    });
    release();
    await done;

    const event = { sessionID: "session-1", system: [] };
    registered["session:context"](event);
    assert.equal(event.system.length, 1);
    assert.match(
      event.system[0].text,
      /changed path\(s\) awaiting handoff/,
    );
    assert.match(
      event.system[0].text,
      /call reconsider with the complete changed scope/,
    );
  } finally {
    dispose();
    if (previous === undefined) delete process.env.SPAN_HOOKS_BIN;
    else process.env.SPAN_HOOKS_BIN = previous;
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test("failed newer preview cannot hand off the retained union with a stale notice", async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "span-preview-retry-"));
  const bin = path.join(root, "fake-span-hooks");
  const count = path.join(root, "count");
  const received = path.join(root, "received.txt");
  fs.writeFileSync(
    bin,
    `#!/bin/sh
case "$*" in
  *source-changed*)
    current=$(cat "${count}" 2>/dev/null || echo 0)
    current=$((current + 1))
    printf '%s' "$current" > "${count}"
    if [ "$current" -eq 2 ]; then exit 1; fi
    printf '%s\\n' "$@" > "${received}"
    echo "changed"
    ;;
esac
`,
    { mode: 0o755 },
  );
  const previous = process.env.SPAN_HOOKS_BIN;
  process.env.SPAN_HOOKS_BIN = bin;
  const { ctx, registered } = fakeContext(root);
  const dispose = await (await loadPlugin()).default.setup(ctx);
  try {
    const first = path.join(root, "src/a.js");
    const second = path.join(root, "src/b.js");
    const third = path.join(root, "src/c.js");

    registered["tool:execute.after"]({
      sessionID: "session-1",
      tool: "edit",
      input: { path: first },
    });
    registered["tool:execute.after"]({
      sessionID: "session-1",
      tool: "edit",
      input: { path: second },
    });

    const afterFailure = { sessionID: "session-1", system: [] };
    registered["session:context"](afterFailure);
    assert.equal(afterFailure.system.length, 0);

    registered["tool:execute.after"]({
      sessionID: "session-1",
      tool: "edit",
      input: { path: third },
    });
    const args = fs.readFileSync(received, "utf8").trim().split("\n");
    assert.deepEqual(args, ["source-changed", first, second, third]);

    const recovered = { sessionID: "session-1", system: [] };
    registered["session:context"](recovered);
    assert.equal(recovered.system.length, 1);
    assert.match(recovered.system[0].text, /3 changed path\\(s\\)/);
  } finally {
    dispose();
    if (previous === undefined) delete process.env.SPAN_HOOKS_BIN;
    else process.env.SPAN_HOOKS_BIN = previous;
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test("adjacent legacy edit payload shapes are not guessed into changed scope", async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "span-native-shape-"));
  const previous = process.env.SPAN_HOOKS_BIN;
  process.env.SPAN_HOOKS_BIN = makeFixture(root);
  const { ctx, registered } = fakeContext(root);
  const dispose = await (await loadPlugin()).default.setup(ctx);
  try {
    registered["tool:execute.after"]({
      sessionID: "session-1",
      tool: "edit",
      filePath: path.join(root, "src/a.js"),
    });
    const event = { sessionID: "session-1", system: [] };
    registered["session:context"](event);
    assert.equal(event.system.length, 1);
    assert.match(
      event.system[0].text,
      /could not normalize its complete changed scope/,
    );
    assert.doesNotMatch(event.system[0].text, /1 recorded understanding/);
  } finally {
    dispose();
    if(previous===undefined) delete process.env.SPAN_HOOKS_BIN;
    else process.env.SPAN_HOOKS_BIN=previous;
    fs.rmSync(root,{recursive:true,force:true});
  }
});

test("Functional Pyramid session-start notice reaches event.system once", async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "span-fp-start-"));
  const bin = path.join(root, "fake-span-hooks");
  fs.writeFileSync(
    bin,
    [
      "#!/bin/sh",
      'case "$*" in',
      '  *session-start*) echo "span: repo Functional Pyramid UNCONFIGURED; use the span-functional-pyramid skill." ;;',
      '  *adoption-primer*) echo "DUPLICATE ENTRY" ;;',
      "esac",
      "",
    ].join("\n"),
    { mode: 0o755 },
  );
  const previous = process.env.SPAN_HOOKS_BIN;
  process.env.SPAN_HOOKS_BIN = bin;
  let release;
  const ready = new Promise((resolve) => { release = resolve; });
  let delivered;
  const done = new Promise((resolve) => { delivered = resolve; });
  const { ctx, registered } = fakeContext(root);
  ctx.event.subscribe = async function* () {
    await ready;
    yield { type: "session.created", data: { sessionID: "session-fp" } };
    delivered();
  };
  const dispose = await (await loadPlugin()).default.setup(ctx);
  try {
    release();
    await done;
    const first = { sessionID: "session-fp", system: [] };
    registered["session:context"](first);
    assert.equal(first.system.length, 1);
    assert.match(first.system[0].text, /Functional Pyramid UNCONFIGURED/);
    assert.match(first.system[0].text, /span-functional-pyramid/);
    assert.doesNotMatch(first.system[0].text, /DUPLICATE ENTRY/);

    const second = { sessionID: "session-fp", system: [] };
    registered["session:context"](second);
    assert.equal(second.system.length, 0);
  } finally {
    dispose();
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
        input: { path: path.join(root, "src/a.js") },
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
    registered["tool:execute.after"]({sessionID:"session-1", tool:"edit", input:{path:path.join(root,"src/a.js")}});
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

test("session entry delivery preserves changed scope until completion handoff", async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "span-entry-change-"));
  const bin = path.join(root, "fake-span-hooks");
  const received = path.join(root, "received.json");
  fs.writeFileSync(bin, `#!/bin/sh
case "$*" in
  *session-start*) echo "entry" ;;
  *source-changed*) exit 1 ;;
  *session-stop*) cat > "${received}"; echo "close changed scope" ;;
esac
`, { mode: 0o755 });
  const previous = process.env.SPAN_HOOKS_BIN;
  process.env.SPAN_HOOKS_BIN = bin;
  let releaseCreated;
  const createdReady = new Promise((resolve) => { releaseCreated = resolve; });
  let createdDelivered;
  const createdDone = new Promise((resolve) => { createdDelivered = resolve; });
  let releaseIdle;
  const idleReady = new Promise((resolve) => { releaseIdle = resolve; });
  let idleDelivered;
  const idleDone = new Promise((resolve) => { idleDelivered = resolve; });
  const { ctx, registered } = fakeContext(root);
  ctx.event.subscribe = async function* () {
    await createdReady;
    yield { type: "session.created", data: { sessionID: "session-1" } };
    createdDelivered();
    await idleReady;
    yield { type: "session.idle", data: { sessionID: "session-1" } };
    idleDelivered();
  };
  const dispose = await (await loadPlugin()).default.setup(ctx);
  try {
    releaseCreated();
    await createdDone;
    const changedPath = path.join(root, "src/a.js");
    registered["tool:execute.after"]({
      sessionID:"session-1",
      tool:"edit",
      input:{path:changedPath},
    });
    const entry = {sessionID:"session-1", system:[]};
    registered["session:context"](entry);
    assert.equal(entry.system.length, 1);
    assert.equal(entry.system[0].text, "entry");
    releaseIdle();
    await idleDone;
    assert.deepEqual(
      JSON.parse(fs.readFileSync(received, "utf8")),
      [{file_path:changedPath}],
    );
    const completion = {sessionID:"session-1", system:[]};
    registered["session:context"](completion);
    assert.equal(completion.system.length, 1);
    assert.match(completion.system[0].text, /close changed scope/);
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
    const edit = () => registered["tool:execute.after"]({sessionID:"session-1",tool:"edit",input:{path:path.join(root,"src/a.js")}});
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
