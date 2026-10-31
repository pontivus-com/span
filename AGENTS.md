# Span — agent operating rules

Span is a standalone MCP server that gives coding agents maintained
understanding of a codebase: what a subsystem is for, who owns it, what
depends on it, and whether that understanding is still current.

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

## Public surface

The public MCP operations are exactly:

`initialize_repository`; `start_context`, `understand_question`,
`understand_retrieve`, `evidence_start`, `evidence_extend`; `reassess`,
`verification_support`; `record_create`, `record_add`, `record_confirm`,
`record_correct`, `record_replace`, `record_withdraw`, `record_challenge`,
`record_update`, `record_verification`; `locate`; `neighbors`.

The retired operations `explain`, `trace`, `impact`, `authority`, `status`,
`refresh`, `initialize_target`, and `submit_interpretation` are not
registered. There are no `semantic_*` aliases. Span never selects a model,
calls a provider, edits a target repository, or runs tests on the user's
behalf.

## Contributions

Sign off commits with the Developer Certificate of Origin (`git commit -s`).
Update the affected public document when a contract changes. See
[`CONTRIBUTING.md`](CONTRIBUTING.md).
