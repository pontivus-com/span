# Lifecycle hooks

Hooks provide optional, bounded notices about readiness or recorded support
that may need attention. Ordinary retrieval and recording perform support
checks themselves, so a missed or disabled hook cannot establish currentness.

## Runtime behavior

`src/span/shell/hooks.py` owns the `span-hooks` commands:

| Command | Scope and effect |
| --- | --- |
| `session-start` | Probe store readiness for the registered repository containing the working directory. |
| `adoption-primer` | Print the FD-58 notice only when the repository has at least one recorded understanding; silent otherwise. |
| `source-changed` | Look up recorded dependents for bounded changed paths and evaluate exact conclusion revisions. |
| `session-stop` | Report bounded affected support for supplied session paths. |

The runner reuses the canonical readiness and support boundaries; it does not
call a retired status tool or maintain its own freshness policy. It never
creates/migrates a store, records semantic state, reinterprets, invokes a model,
runs tests, or rebuilds a structural index.

Routine current state is quiet. Silence is not a repository-wide all-current
or complete-understanding statement. Events outside registered roots are
ignored; unavailable setup or affected support is reported within the
available event scope. Operational availability and semantic uncertainty are
kept separate.

## Host wiring and evidence

The installer can append Codex hooks to an existing `~/.codex/hooks.json`,
preserving foreign entries and avoiding duplicate Span hooks. On upgrade it
replaces Span entries whose binary path or matcher changed, so exactly one
installed invocation remains. Missing files or CLIs are reported as skipped.

For OpenCode, the installer manages the server plugin under an explicit
`--opencode-plugin-scope global|local|none`. Under `global` it deploys the
plugin under Span's own data root and registers it once in the host's global
`opencode.json` (`plugins`); it writes nothing into a target repository. A
legacy per-target `.opencode/plugins/span-hooks.js` copy left by versions before
0.9.0 is moved to `<target>/.opencode/span-retired/`, never deleted, because
OpenCode still auto-loads `.opencode/plugins` and would reject a second plugin
with the same id. The retired directory is operator-owned; Span has no TTL or
reaper for it. Under `local` and `none`, the target plugin is user-managed:
Span removes its own global registration and reports the local copy without
modifying it. Only targets passed with `--repo` are mutable; receipt targets not
selected are inspected read-only and yield `conflict` if a Span-owned copy
remains.

| Scope | Selected target (`--repo`) | Receipt-only target | Global registration |
| --- | --- | --- | --- |
| `global` | retire Span-owned copies | read-only; `conflict` if present | update |
| `local` | report only | read-only; report only | remove Span-owned |
| `none` | report only | read-only; report only | remove Span-owned |

A fresh install defaults to `global`; an upgrade uses the receipt scope and
stops if it is absent or ambiguous. The authoritative full matrix is in
[install](install.md#opencode).

The plugin waits a bounded three seconds at prompt admission for the local MCP
connection, then injects the FD-58 adoption notice once per session through the
`context` hook. An edit-time notice is stored when a tool edit runs and is
delivered once on the next `context` hook, naming the changed paths and the exact
`reconsider(changed_paths=[...])` call. The notices are advisory: a missed or
failed injection changes only efficiency, never currency. A five-run OpenCode
capture recorded the first `ask` before the first source read in 5/5 runs; see
`.context/evidence/fitness/2026-11-02-three-tool/natural-use/F10-2026-11-03.md`.

Implemented wiring, configured entries, actual invocation, affected scope,
and delivered notice are separate facts. Codex beta conformance was run with
hooks explicitly disabled. That proves ordinary operation without hooks; it
does not prove live hook arrival.

See [host trigger support](../integrations/hosts/triggers.md). Automated
coverage is in `tests/unit/test_lifecycle_hooks.py`, installer tests, and
administrative readiness tests. The shipped runtime implementation is the
reference for behavior; older integration transcripts remain historical.
