# Span

Span is a standalone semantic repository intelligence system for coding agents.

Span provides evidence-grounded repository understanding across purpose,
responsibility, ownership, authority, boundaries, representations, lifecycle,
change impact, verification and freshness.

Span is designed as an independent GPL/open-source project.

The repository may be developed inside a larger private workspace, but Span
has no required Pontivus, Pontivus Legal or Pontivus Graph runtime, build,
test, schema, fixture or documentation dependency.

Implementation authority:
- `.context/requirements/`
- `.context/plans/`

Documentation: `docs/` (architecture, contracts, lifecycle, MCP,
hooks, skills, acceptance, contributing). Guides describe the
governing plan; they never define semantics.

## Install and setup prompt (copy to your agent)

> Automated path (Linux): `python3 scripts/install-span.py --repo
> <TARGET_REPO> [--repo ...] [--opencode-config PATH] [--with-codex]`
> installs into `~/.local/share/span`, links `span-mcp` on PATH,
> merges host MCP entries, provisions each repo, and verifies
> readiness plus one explain round-trip with a printed receipt.
> `span-install --verify` re-checks an existing install (doctor).
> OS specifics live in `src/span/shell/install.py::PLATFORM_PATHS`
> (Linux verified; macOS/Windows reserved). The installer is
> stdlib-only and imports no Span code before install.

Pass the block below to an LLM-connected coding agent to install Span
and bring one target repository to `READY`. It performs setup only;
it does not change target code. Requires explicit paths from you:
`<SPAN_REPO>`, `<TARGET_REPO>`, `<DATA_DIR>`.

```text
Set up Span (standalone semantic repository intelligence) for one
target repository. Do all steps. Stop and ask on any failure; never
guess, coerce uncertainty, or auto-fix by inventing semantics.

0. Authorities: Span v0.6 plan + MI-01..MI-13 govern. Guides in
   <SPAN_REPO>/docs describe; they never define semantics. Span owns
   task contract, validation, authority, freshness, persistence,
   answers — never model selection, endpoints, or credentials.

1. Prerequisites (fail closed if missing):
   - python3 >= 3.12 (`python3 --version`)
   - node + graft CLI (`node --version`, `graft --version`);
     Graft is MIT, structural source only
   - sqlite3 via stdlib (no install); setuptools>=61 for build;
     MCP SDK mcp==2.3.0 (MIT) installed with Span
   - <SPAN_REPO> is standalone GPL-3.0-only; <TARGET_REPO> is the
     subject repo (explicit external config); <DATA_DIR> is outside
     <TARGET_REPO> (holds SQLite stores, created if absent)

2. Isolated install (no parent imports, no target writes):
   python3 -m venv /tmp/span-eval
   source /tmp/span-eval/bin/activate
   pip install <SPAN_REPO>
   span-mcp --help
   python3 -c "import span; print(span.__file__)"
   Expected: span-mcp usage prints; import resolves under
   <SPAN_REPO>/src, not under any other workspace.

3. Structural index check (read-only):
   ls <TARGET_REPO>/graft/.graph/wiring.json
   If missing: STOP. Ask the user whether to run `graft build`
   inside <TARGET_REPO> (writes graft/.graph in target). Never
   auto-build from queries/hooks; init may build only in this
   explicit admin session with user consent.

4. Start data dir:
   mkdir -p <DATA_DIR>
   Expected: empty dir outside <TARGET_REPO>, writable.

5. Initialize (explicit, dedicated setup session):
   span-mcp --data-dir <DATA_DIR> --repo graft:<TARGET_REPO>
   Then call initialize_repository with:
     repository_locator = "graft:<TARGET_REPO>"
     structural_provider_config = "graft:<TARGET_REPO>"
     authority_seeds = () unless the user supplied explicit seeds
       (unknown seed locators fail closed; never invent seeds).
   Expected: SemanticInitializeRepositoryResult with repository_id,
   readiness, structural/evidence/store status, warnings.
   Initialization performs no semantic interpretation.

6. Verify readiness:
   Call status (mode NORMAL, no target).
   - If UNINITIALIZED: report setup notice, remain in setup
     session; normal queries/hooks must never bootstrap implicitly.
   - If READY: proceed. Record repository_id for all later calls.

7. Smoke (read-only):
   status then explain on one known symbol in
   <TARGET_REPO> (SubjectSelector name/locator).
   Expected: SemanticAnswer or PendingInterpretation with evidence
   pointers, per-claim freshness, trust separate from readiness.
   If PendingInterpretation: perform the bounded task with your own
   model, submit via submit_interpretation, repeat until an
   answer returns. Preserve PARTIAL/AMBIGUOUS/CONFLICTED/UNRESOLVED/
   STALE/UNVERIFIABLE verbatim; missing authority stays missing.

8. Boundaries to respect for this setup:
   - 8 ops only: initialize_repository, explain,
     impact, trace, authority, status,
     refresh, submit_interpretation. No semantic_* aliases.
   - Span never edits code, runs tests, orchestrates workflows,
     selects models, or rebuilds implicitly. Hooks call only
     status HOOK_FAST. No whole-repo crawl. Repo-wide refresh
     (target None) is deferred and rejected fail-closed; refresh is
     always scoped. Report typed errors (unknown_tool, ingress,
     unknown_repository, unavailable, validation, rejected,
     transport) as-is.
   - Target writes forbidden: all Span state lives in <DATA_DIR>
     (<repository_id>.db). Target file reads are evidence only.

Exit: READY + one successful explain round-trip recorded
(repository_id, readiness, answer/pending envelope id). Paste the
init result, status result, and explain envelope id back to the user.
```

## Running inside Opencode and Codex

Prerequisite: `span-mcp` on PATH (`pip install <SPAN_REPO>`;
verify with `span-mcp --help`). `<DATA_DIR>` stays outside every
target repo. One `--repo graft:<TARGET>` per target (repeatable).

Large repos report init readiness `DEGRADED` with the warning
`evidence inventory truncated by maximum bounds; remaining sources
discovered on demand`. That is the designed bounded state for repos
over the 96-unit inventory maximum (`service.py` maximum bounds,
`service_operations.py` init): remaining evidence loads on demand.
It is not a failure; `status` still reports operational
readiness. Do not raise bounds to chase `READY`.

### Opencode

Register one server per target in `opencode.json` (same shape as the
existing `graft` entry):

```json
"mcp": {
  "span": {
    "type": "local",
    "command": [
      "span-mcp",
      "--data-dir",
      "<DATA_DIR>",
      "--repo",
      "graft:<TARGET_REPO>"
    ],
    "enabled": true
  }
}
```

Reload Opencode, then ask the agent: `status` (expect
`HookStatusNotice`), then `explain` on a known symbol (expect
`SemanticAnswer` or `PendingInterpretation`, submitted via
`submit_interpretation` until an answer returns).

### Codex

Register via the CLI (verified `codex mcp add --help`):

```text
codex mcp add span -- span-mcp --data-dir <DATA_DIR> --repo graft:<TARGET_REPO>
codex mcp list
```

Use the absolute `span-mcp` path if it is not on Codex's PATH.
Then prompt: `status`, then `explain` on a known symbol;
same expectations as Opencode. If `codex mcp list` fails on
`service_tier`, fix the local Codex config first — that error is
outside Span.

