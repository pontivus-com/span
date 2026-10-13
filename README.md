# Span — shared memory for coding agents.

Every coding session starts by re-learning the same codebase: what each
part is for, who owns it, how data flows, which contracts govern it,
where failures go. Then the session ends and all of it evaporates — or
worse, gets written down somewhere and quietly rots. Span keeps that
understanding across tasks and sessions as evidence-backed claims, and
tells you when it stops being true.

- **Established answers instead of re-derivation.** Ask what something
  is for; get the recorded answer with its evidence — or a bounded task
  to establish it, never a guess.
- **Stale announces itself.** Change the code and the affected knowledge
  reads back stale on the next query, with exact scope for reassessment.
- **Challenges converge.** Disagree with stored knowledge and correct it
  under the same identity — history intact, superseded claims marked
  stale, never silently forked or presented as current.
- **No lost work.** A rejected submission keeps its place in line: fix
  the named error, resubmit, carry on. Commits happen exactly once.
- **Campaigns with a progress bar.** Point Span at a directory with an
  objective; every call tells you what is done and what remains.

Span is not source-code search, not a call graph, not documentation
retrieval, not conversation history, and not unqualified AI-written
summaries. It is investigation plus memory: trace a producer-to-consumer
path, set governing sources side by side, brief the blast radius of a
change — then persist what was learned, with provenance, until the code
says otherwise. Uncertainty, conflicts, and gaps stay explicit: no
infallible interpretation, no universal coverage, no autonomous
maintenance.

Three functions, one mechanism:

- **Establish** — investigate a bounded architectural scope once;
  persist purpose, owners, contracts, flows, and failure paths as
  evidence-backed claims.
- **Maintain** — as code changes, affected knowledge goes noncurrent
  visibly; the editing agent reassesses its exact scope in the same
  change (closeout), never in a separate maintenance session.
- **Expand** — ordinary investigations that surface new material
  knowledge admit, examine, and persist it through the same canonical
  submission — deliberately, never by silent broadening.

The agent lifecycle runs twelve canonical operations:
`initialize_repository` (explicit setup), `initialize_target` (exact target
boundary and bounded structural candidates), `explain`, `impact`,
`trace`, `authority`, `status`, `refresh`, `submit_interpretation`,
`reissue_interpretation` (exchange recovery), `locate` (read-only
structural find/outline/member listing), and `neighbors` (read-only
bounded adjacency). Structural navigation is evidence input served by
Span itself — no separate structural MCP exists. When stored knowledge is insufficient, an operation
suspends with a bounded task; the agent investigates with its own
model and submits the typed result. Span validates, materializes,
and resumes — it never edits code, runs tests, selects models, or
invokes providers.

Hooks are report-only: they surface scopes needing action
(uninitialized stores, missing coverage, moved dependents,
stale/open/pending work) and stay silent when everything is current.
Host trigger support per host: `integrations/hosts/triggers.md`.
Agent duties per skill: `skills/`.

Onboarding delivers three milestones: A1 operational readiness (installed,
initialized, readiness-verified by the installer), A2 host-connected
exchange (an actual host MCP `explain` round-trip in the selected coding
host session), and B a useful semantic baseline (a bounded scope
investigated, persisted, and demonstrably retrievable by fresh
questions). The installer alone delivers A1 only — never A2 or B.
Ordinary demand-driven queries work regardless, with no establishment
campaign required.

Start with [Install](#install-linux-verified), verify readiness, then
use `initialize_target` for the user-directed semantic boundary (A2/B).

## Agent lifecycle — what Span does at each stage

```
session begins
  │
  ▼
1. ORIENT ......... agent calls normal status (no target), then explain
  Span: reports readiness plus the bounded persisted semantic-coverage
  frontier — covered/current, incomplete, stale/unverifiable, and
  unassessed state — or suspends with a bounded task. READY means
  operational, never known.
  │
  ▼
2. PREPARE ........ agent calls impact (+ trace / authority)
  Span: assesses the proposal against stored semantics and returns
  a blast-radius brief with requirements. Never approval to act.
  │
  ▼
3. INVESTIGATE .... agent calls explain / trace / authority, submits
  Span: serves bounded evidence + priors; suspends while knowledge
  is insufficient. Agent examines, submits typed results, repeats
  until answers resolve. Span validates + materializes each unit.
  │
  ▼
4. IMPLEMENT ...... agent edits with external tools
  Span: nothing. Span never edits code, runs tests, or orchestrates.
  │
  ▼
5. VERIFY ......... agent calls status + runs external tests
  Span: reports currency of the change scope (CURRENT / STALE /
  UNVERIFIABLE). Passing tests never count as semantic proof.
  │
  ▼
6. CLOSEOUT ....... editing agent calls scoped refresh, then status
  Span: re-examines the stale scope from persisted coverage and
  materializes reassessed answers (or visible OPENs). A bare
  refresh call proves nothing — adequacy is in resubmitted content.
  │
  ▼
7. REUSE .......... any later agent calls explain / status
  Span: answers from established knowledge; respects OPENs;
  suspends only where material questions remain unexamined.
```

Around the edges, report-only hooks observe session boundaries
(`session-start`, `source-changed`, `session-stop`): they surface
scopes needing action and stay silent when everything is current.
They never initialize, interpret, refresh, or decide anything.

Normal `status(target=None)` has a repository-level reporting promise: it
must expose a bounded inventory derived from persisted canonical semantic
coverage, including what is covered and current, what remains
`PENDING`/`OPEN`, what is stale or unverifiable, what is unassessed in the
returned frontier, and what was omitted by bounds or pagination. It does
not enumerate structural subjects, interpret evidence, write coverage, or
claim repository completeness. Exact-target `status` and `explain` provide
the detailed scoped view;
`HOOK_FAST` remains compact readiness/event reporting. A readiness-only
response is an activation gap, not proof that the repository holds no
semantic knowledge; formal gate status lives in
`docs/verification-record-2026-10-13.md`.

---

# Span (technical reference)

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

## Install (Linux, verified)

Prerequisites: `python3 >= 3.12`, `node`, and an existing graft index at
`<TARGET_REPO>/graft/.graph/wiring.json` for every target. Span never
builds the index — create it with the independent Graft workflow first,
or stop here. The data directory must live outside every target
repository. OS specifics live in `src/span/shell/install.py::PLATFORM_PATHS`
(Linux verified; macOS/Windows reserved). The installer is
stdlib-only and imports no Span code before install.

From the workspace root:

```bash
python3 span/scripts/install-span.py --span-repo <SPAN_REPO> \
  --repo <TARGET_REPO> [--repo ...] [--data-dir <DATA_DIR>]
```

`<SPAN_REPO>` is this checkout, `<TARGET_REPO>` the subject repo,
`<DATA_DIR>` the store directory. `--repo` takes an absolute path or a
path relative to the current directory and is repeatable. `--data-dir`
defaults to the platform directory (`~/.local/share/span/data`). Add
`--dry-run` to preview without changing anything.

What the installer does: preflight (index presence, git state), syncs
the isolated venv from the span checkout with proof, links `span-mcp`
onto PATH, merges the span entry into `opencode.json`, registers Codex
and removes the retired graft entry, deploys the skills, writes a
receipt to `<DATA_DIR>/install.json`, and verifies readiness. It
performs readiness checks only — it never runs `explain`, never creates
semantic knowledge, and never implies host connection (A2) or a
baseline (B). `span-install --verify` re-checks an existing install.

### Verify in one minute

`span-mcp --help` must print usage. Then, in any host session with the
span MCP connected: call `status` with no target (expect `READY`), then
`explain` on one known symbol. Expect a `SemanticAnswer` with evidence
pointers, per-claim freshness, and trust kept separate from readiness —
or a `PendingInterpretation` carrying the bounded task, which you
perform with your own model and submit until an answer returns
(submitting persists knowledge; reading never does). That round-trip is
the entire proof of connection: installing the skill or reading the
driver never proves a host connection — only an observed host MCP
request and response does.

Agents running the loop above use `skills/span/SKILL.md` as the
operating procedure; the uniform shape is status → investigate →
submit-until-answer.

Host wiring details (the exact entries the installer writes for Opencode
and Codex) follow under [Running inside Opencode and
Codex](#running-inside-opencode-and-codex).

## Running inside Opencode and Codex

Prerequisite: `span-mcp` on PATH (`pip install <SPAN_REPO>`;
verify with `span-mcp --help`). `<DATA_DIR>` stays outside every
target repo. One `--repo graft:<TARGET>` per target (repeatable).

Large repos keep init readiness `READY` with the warning
`evidence inventory truncated by maximum bounds; remaining sources
discovered on demand`. That is the designed bounded state for repos
over the 96-unit inventory maximum (`service/bounds.py` maximum bounds,
`service/repository.py` init, which always returns `READY`): the
truncation is reported in the existing `evidence_inventory_status`
(`degraded:truncated-at-<n>`) plus warnings, never in `readiness`,
and remaining evidence loads on demand.
It is not a failure; `status` still reports `READY` alongside the
explicit `degraded:truncated-at-<n>` inventory state (readiness plus
bounds, never readiness instead of coverage). Do not raise bounds to chase inventory completeness.

### Opencode

The installer writes this entry for you (one server covering all
`--repo` targets). Manual shape for reference:

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

Reload Opencode, then ask the agent: normal `status` with no target,
then `status`/`explain` on a known symbol. Exact-target calls may
return a `SemanticAnswer` or `PendingInterpretation`, submitted via
`submit_interpretation` until an answer returns; the compact
`HookStatusNotice` is returned only in `HOOK_FAST` mode.

### Codex

Register via the CLI (verified `codex mcp add --help`):

```text
codex mcp add span -- span-mcp --data-dir <DATA_DIR> --repo graft:<TARGET_REPO>
codex mcp list
```

Use the absolute `span-mcp` path if it is not on Codex's PATH.
Then prompt: normal `status` with no target, then exact-target
`status`/`explain` on a known symbol. If `codex mcp list` fails on
`service_tier`, fix the local Codex config first — that error is
outside Span.
