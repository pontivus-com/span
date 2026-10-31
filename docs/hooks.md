# Lifecycle hooks

Hooks provide optional, bounded notices about readiness or recorded support
that may need attention. Ordinary retrieval and recording perform support
checks themselves, so a missed or disabled hook cannot establish currentness.

## Runtime behavior

`src/span/shell/hooks.py` owns the `span-hooks` commands:

| Command | Scope and effect |
| --- | --- |
| `session-start` | Probe store readiness for the registered repository containing the working directory. |
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

The installer can append Codex hooks to an existing `~/.codex/hooks.json` and
Claude hooks to an existing `~/.claude/settings.json`, preserving foreign
entries and avoiding duplicate Span hooks. Missing files/CLIs are reported
as skipped. OpenCode plugin deployment is not active; its reference plugin is
not evidence that lifecycle events were delivered.

Implemented wiring, configured entries, actual invocation, affected scope,
and delivered notice are separate facts. Codex beta conformance was run with
hooks explicitly disabled. That proves ordinary operation without hooks; it
does not prove live hook arrival. Claude model behavior remains UNVERIFIED
under the owner waiver.

See [host trigger support](../integrations/hosts/triggers.md). Automated
coverage is in `tests/unit/test_lifecycle_hooks.py`, installer tests, and
administrative readiness tests. The shipped runtime implementation is the
reference for behavior; older integration transcripts remain historical.
