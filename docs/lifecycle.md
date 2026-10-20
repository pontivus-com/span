# Agent execution lifecycle

```
OFFLINE (dedicated setup session)
  initialize_repository → READY (no interpretation happens here)

NORMAL CODING SESSION (enter anywhere)
  ORIENT        status (no target) → explain
  PREPARE       impact  (material changes: always before editing)
  INVESTIGATE   trace / authority (where required)
  IMPLEMENT     external editing tools
  VERIFY        status + external tests/review
  CLOSE         refresh + status
```

Span never edits target code, generates patches, runs tests, or orchestrates
workflows. The installer synchronizes the managed lifecycle block in the
target `AGENTS.md`; that guidance write is separate from semantic state.
When stored semantics are insufficient, the operation
suspends with a bounded task: interpret it with your own model,
submit via `submit_interpretation`, and continue — a submit may
return the answer or the next pending unit.

## Refresh scope types

```text
stale refresh:
  SubjectSelector OR EvidenceScope
  stale_only=True (default)

CURRENT/unchanged-source challenge:
  SubjectSelector only
  stale_only=false
```

An `EvidenceScope` with `stale_only=false` is rejected: it is not an
unchanged-source challenge target. Ordinary scoped stale refresh continues
to accept either target type.

## Status entry guidance

Normal `status` names the next exact step in each non-current entry:

- `STALE` or `UNVERIFIABLE` → `refresh` with the exact `SubjectSelector`
  for that subject; an `UNVERIFIABLE` empty result proves nothing.
- `UNASSESSED` (no adopted question coverage) → question-local `explain`
  on that subject. A continuation exists only after that operation
  suspends.
- Pending or open question work → continue through the continuation
  returned by the operation that suspended. Never invent or reuse a
  `cont-*` token.

Hooks report the same distinction in compact form and never allocate a
continuation.

## Refresh ownership (Addendum C C-11)

The agent that changes implementation or governing semantic evidence
owns the close-out sequence for the scope it affected (edit → scoped
status → external verification → explicit scoped refresh → scoped
status) in the same change — a `refresh` call without re-examination
proves nothing; adequacy is in the resubmitted content. Hooks stay
report-only and never refresh.
Neglected stale scopes remain visibly noncurrent; Span never presents
a stored `ANSWERED` as effectively current where required support is
stale or unverifiable. Full closeout duty: `skills/span/SKILL.md`
(Freshness, authority, and closeout); expansion: the same skill's
shared analysis-card and boundary guidance.

Every semantic write uses the same compact pending-task card: objective; exact
scope and exclusions; evidence and authority; material input-to-terminal path;
typed result; adversarial check; explicit disposition with requirements; and
fresh readback. The card is projected through the canonical `TaskBrief` and
does not add a second semantic state or quality model.

## Explicit target semantic establishment (Addendum E)

After the repository is identified and confirmed ready (initializing it only
when readiness is `UNINITIALIZED`), an exact
directory or repository path supplied by the user becomes a host-owned
semantic campaign, not a stronger form of administrative readiness. That
supplied path is the complete semantic boundary. The canonical entry point
is `initialize_target` with the exact `EvidenceScope` and user objective.
Each pending task exposes that boundary separately from its current
structural anchor. The active agent uses structural and filesystem discovery
to partition that boundary into material areas, then drives the returned
typed units through investigation and `submit_interpretation` serially,
using `reissue_interpretation` once only for an ingress-failed
continuation (expired or lost continuations never reissue: re-run the
idempotent original operation instead). `explain(establish_baseline=True)` remains for an ordinary
selected root without an exact target directory; it is not the exact-target
path. Every material area must end with persisted coverage or an explicit
`NOT_APPLICABLE`, `OPEN`, or `PENDING` disposition with its requirement; a
representative root, populated store, or `READY` response is not completion.
The agent preserves page tokens, resumes pending work, and performs
fresh-session retrieval before reporting the target complete. A request
without an exact target still requires an explicit bounded scope choice.

Target accounting constraint: structural candidates make the exchange
resumable; they are not semantic areas. Coherent grouping is host-owned and
must be recorded through canonical subjects, relationships, semantic question
coverage, and typed target-inventory accounting in the single
`TargetAssociation` carrier. Target-inventory assignment, evidence-backed
exclusion, or unresolved mapping is distinct from question-level
`NOT_APPLICABLE`. No second progress store, ledger, or writer exists.
`target_scope` alone does not prove grouping or completeness. The accounting
carrier and atomic result/store contract are defined in Addendum E §4C.2 and
remain implementation-gated under E-13.

Exact onboarding path: `docs/onboarding-runbook.md` (copied from Addendum E
§§4A and 6).

## Initialization and readiness

Initialization is explicit and administrative: identity, repository
state, provider-owned structural build when needed
(`ensure_current` into `<data-dir>/structural/<id>/`, wiring-only, no
target writes), evidence inventory, authority seeds, store
schema — then a readiness report. Uninitialized repositories answer
`UNINITIALIZED` plus a setup requirement on every path; hooks and
queries never bootstrap implicitly. A failed provider build is an
actionable setup failure, never a usable provider; a dirty tree after a
successful build still provisions (provider available, freshness
UNVERIFIABLE). Readiness is operational state,
never semantic truth. After initialization, normal repository-level
`status(target=None)` is required to expose the bounded persisted
semantic-coverage inventory (covered/current, incomplete, stale or
unverifiable, unassessed, and explicit bounds), without a structural crawl
or interpretation. This inventory is distinct from readiness. The
ACT-D-10 installed-runtime gate was verified in the 2026-10-17 closeout
run against the installed MCP process; the remaining status-path and
documentation synchronization work is tracked in the current closeout
report.

## Workflow examples

- Investigate: `explain` unfamiliar target → `trace`
  upstream/downstream → `authority` on the governing claim.
- Baseline a subsystem: `explain(establish_baseline=True)` on the
  exact root → work admitted PENDING questions in order → synthesize
  only on established member evidence → report qualified sufficiency.
  Use this only for an ordinary selected root. For an exact user-supplied
  directory target, use `initialize_target` per the section above.
- Implement: `impact` with change kind + affected assertions →
  resolve blockers → edit → `status` → external tests →
  `refresh` → `status`. `refresh` reuses persisted question scope;
  it never starts a new baseline audit.
- Test/review: `status` for verification currency (candidate vs
  current pass/fail) — Span reports currency; it never runs tests.
- Change-context: see `skills/span-change-context/SKILL.md`.

Root selection uses existing repository context plus bounded
structural operations. For an explicit target, the host performs the needed
partitioning outside the MCP structural port; the port has no unrequested
repository-wide enumerate/map. Normal repository-level `status` reads only persisted
semantic coverage and reports its bounded frontier; it never enumerates
structural subjects or interprets them. Skills are guidance only, never
semantic authority.

## Addendum J delta — target mapping

`initialize_target` binds a bounded, deterministic batch of unaccounted
inventory members per mapping unit; every bound member receives exactly one
disposition (assignment, evidence-backed exclusion, or unresolved mapping),
validated atomically. Newly admitted areas take a service-owned first
`PENDING` CQ-01 seed when no reusable current question exists.
