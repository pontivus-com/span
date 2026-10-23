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
pip install -e '.[test]'
pytest
```

The installed-MCP lane also needs `uv`, Node, and npm. It builds a
non-editable install in a temporary virtual environment and drives the
installed `span-mcp` over stdio.

## Public surface

The public MCP operations are exactly:

`initialize_repository`, `initialize_target`, `explain`, `impact`, `trace`,
`authority`, `status`, `refresh`, `submit_interpretation`, `locate`, and
`neighbors`.

There are no `semantic_*` aliases. Span never selects a model, calls a
provider, edits a target repository, or runs tests on the user's behalf.

## Contributions

Sign off commits with the Developer Certificate of Origin (`git commit -s`).
Update the affected public document when a contract changes. See
[`CONTRIBUTING.md`](CONTRIBUTING.md).
