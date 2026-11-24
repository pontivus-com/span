# Span — agent operating rules

Span is a standalone MCP server that gives coding agents maintained
understanding of a codebase: what a subsystem is for, who owns it, what
depends on it, and whether that understanding is still current.

## Foundations — binding

[`docs/goals.md`](docs/goals.md) (layer 0) states why Span exists and the
outcomes it is judged on. [`docs/foundations.md`](docs/foundations.md) (layer 1)
defines the axioms about the agent and the principles of the system.
[`docs/lifecycle-contract.md`](docs/lifecycle-contract.md) (layer 2) turns them
into operations, payloads, contract laws, and the boundary between the agent's
work and Span's internals. [`docs/functional-design.md`](docs/functional-design.md)
(layer 3) states the behaviour that makes the contract deterministic.
[`docs/technical-design.md`](docs/technical-design.md) (layer 4) records the
implementation baseline, what is retained, and the minimal refactoring set.
[`docs/requirements-pyramid.md`](docs/requirements-pyramid.md)
governs how those layers are structured: what each owns, where a new requirement
belongs, and why a restatement is a defect. All of these are binding on design,
contracts, code, tests, prompts, documentation, and releases, and a lower layer
may not contradict a higher one. Where any plan, ADR, changelog, guide, skill, or
instruction conflicts with them, they govern; amend them explicitly before
working around them. Cite the IDs (G1–G8, A1–A10, F1–F14, L1–L17, FD-1–FD-102) in
changes and reviews.

## Layout

- `src/span/core/` — deterministic semantic core.
- `src/span/ports/` — typed interfaces.
- `src/span/service/` — operation composition.
- `src/span/shell/` — effects, strict ingress/egress, MCP transport.
- `tests/` — unit, integration, and acceptance coverage.
- `docs/` — public architecture, contracts, and operating guides.
- `skills/` and `integrations/` — agent-side lifecycle guidance.

## Independence

Span is independent. No required implementation may import, load, execute,
or depend on a parent workspace, a private service, or a proprietary schema.
Required paths resolve from the Span repository root, an explicitly supplied
target repository, or explicit user configuration.

## Root cause only — no patches, no hacks

Every defect is fixed where the bad state is produced, never where it is
observed. A change that removes the symptom while the cause remains is not a
fix and must not be proposed, implemented, or accepted.

- No patches, shims, bridges, workarounds, retries-as-fix, downstream gates,
  silent fallbacks, or special cases added to absorb a defect.
- No weakening the evidence: never delete or loosen a test, assertion, check,
  threshold, ceiling, or budget to make work pass. If a check is wrong,
  correct the check and record why it was wrong; if it is right, the work is
  wrong.
- No gate editing: a conflict between the correct fix and a hard rule, budget,
  or contract is the owner's decision. Surface it with evidence; never resolve
  it by raising the limit.
- No second shape: a fix that duplicates a carrier, vocabulary, or writer, or
  that admits a state which cannot exist, is a new defect, not a fix.
- A recommendation shown to be wrong is retracted explicitly with the
  corrected reasoning; it is never carried forward.

## No arbitrary numbers as rules

A limit, ceiling, threshold, or budget must be either a measurement of the
current tree (a ratchet: it may not grow without the growth being recorded in
the same change) or derived from a stated principle. An invented constant is
not authority; it is debt, and it never decides what work may proceed.

- A number that exists only because it was once written down is an
  anti-pattern. Replace it with the measurement or the principle it was
  standing in for.
- A measured ratchet records cost; it does not grant or deny permission.
  Growth is visible in the diff and justified there.
- Never introduce a new magic number to make a check pass, and never keep an
  old one because removing it is inconvenient.

## Working rules

- Code is the source of truth for what the software does. Documents describe
  contracts; they do not replace code evidence.
- Normative claims (ownership, governance, policy) need a cited record or
  must remain explicitly unresolved. Do not infer authority from structure.
- Keep missing, ambiguous, conflicted, stale, or unverifiable knowledge
  explicit. Never coerce it into certainty.
- One canonical typed carrier per boundary. Do not add ad-hoc DTOs,
  compatibility bridges, fallback parsing, or parallel semantic writers.
- Do not edit generated artifacts or `BUILD_IDENTITY`.
- Keep raw acceptance captures, transcripts, receipts and manifests out of Git
  and distributions. Exception: the deployable per-repository artifact under
  `<repo>/.span/backups/` is intended Git content and is committed by the
  operator; all other raw captures, receipts and ad-hoc manifests remain out. Report sanitized verification summaries in release notes.

## Testing

From the repository root:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[test,dev]'
pytest
ruff check .
black --check .
```

The installed-MCP lane also needs `uv`, Node, and npm. It builds a
non-editable install in a temporary virtual environment and drives the
installed `span-mcp` over stdio.

## Required agent lifecycle

Follow [lifecycle contract §7](docs/lifecycle-contract.md#required-agent-completion)
before deriving understanding, when establishing conclusions and after changes.
Retain supported conclusions and complete affected dispositions as part of the
work. Hooks remind; the agent performs these actions.

## Public surface

The public MCP operations are exactly three, one per lifecycle moment:

`ask`, `record`, `reconsider`.

`record` carries `kind` (`understanding`, `verification`, `surface`, or
`functional_pyramid`). An
understanding create is flat — one `conclusion` with dependency evidence from
`locator`, `observation_id`, or non-empty `support`; scope is supplied or
derived independently. A `locator` may accompany explicit `support` solely as
carried code scope; `support` remains the complete dependency set and
`observation_id` remains exclusive. `actions` is for understanding updates and `action` for surface or Functional
Pyramid lifecycle writes. Those are semantic fields, not separate tools.
Operational repository installation/registration belongs to the installer;
Functional Pyramid participation is governed through the ordinary MCP lifecycle.
Structural navigation belongs to the host. Any other
operation name follows the ordinary unknown-tool path. Span carries no
retired-name map, aliases, compatibility grammar, or replacement routing for
removed public operations. There are no `semantic_*` names or dual grammar.
Span never selects a model, calls a model
provider, edits a target repository, or runs tests on the user's behalf.

## Contributions

Sign off commits with the Developer Certificate of Origin (`git commit -s`).
Update the affected public document when a contract changes. See
[`CONTRIBUTING.md`](CONTRIBUTING.md).

<!-- span:start -->
## Span lifecycle (MCP only)

Consult Span before deriving semantic understanding. Record supported
conclusions when established. After edits, reconsider changed paths and record
the supported dispositions before completing the work.

- Before any source access used to understand a surface — native `Read`/`Grep` or shell reads/searches such as `cat`, `rg`, or `grep` — `ask` the exact surface or reference with no question or request identity.
- Use `RecordedQuestionSelector` only when you already know the exact recorded question; it is exact surface-scoped lookup, not semantic matching.
- If a Gap's source pointers need bytes, make an explicit evidence-admission `ask`; follow only the continuation it returns.
- Treat returned context references as opaque handles; copy them only into declared `context` fields.
- After editing: `reconsider`; investigate `REASSESSMENT_REQUIRED`/`UNVERIFIABLE` conclusions and record their dispositions.
- After establishing a conclusion: `record` it as evidence-near capture. A new or semantically changed conclusion is not shared reusable knowledge until a separate reviewer/curator accepts that exact revision through the curation action inside `record`. Acceptance is not task completion when `UnderstandingRecorded.qualification` is non-current; continue investigation/re-establishment until required dispositions are CURRENT or an explicit blocker remains.
- A conformance judgment is a NORMATIVE conclusion; use `assertion_nature=NORMATIVE`.
- For ACTIVE Functional Pyramid participation, use the governing projection returned by the same `ask`; do not infer or copy governing prose. Functional Pyramid adoption/revision uses the dedicated selector/record branches inside the same three MCP tools.
- For curation work: obtain `PendingCurationSelector`, review the exact captured revision against retained knowledge and applicable governance, repair semantic defects through the existing challenge/correct/replace/withdraw lifecycle, and curate only a stable exact revision. Curation does not create authority or certify semantic truth.
- After accepted Functional Pyramid ACTIVATE/REVISE/DEACTIVATE, inspect returned `dependent_effects` and `reestablishment_contexts`. Dispose actionable effects before calling that lifecycle task complete; do not call `reconsider` again for the participation write itself. Keep its receipt selector until those accepted effect refs are no longer actionable or have been re-established.

Detail: [MCP reference](https://github.com/pontivus-com/span/blob/master/docs/mcp.md),
[router skill](https://github.com/pontivus-com/span/blob/master/skills/span-router/SKILL.md).
<!-- span:end -->
