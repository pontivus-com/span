# Acceptance and evidence

> **Document role: current verification evidence.** This page records only what
> the active Beta-4 candidate has demonstrated. It does not define product
> requirements; those remain in the Functional Pyramid and its governing
> requirements pyramid.

> **What can we currently claim about the Beta-4 candidate, based on evidence?**

Superseded Beta-3, Beta-1 and earlier campaign evidence is retained in
[Historical acceptance evidence](acceptance-history.md).

## Current Beta-4 verification state

The governing functional acceptance authority is
[Functional Design §15](functional-design.md#15-version-1-beta-functional-acceptance).
The live requirement-to-test mapping is the
[functional-acceptance matrix](functional-acceptance.md), and the
[Invariant audit matrix](invariants.md) records architectural enforcement.
Neither matrix is a release receipt.

### Released-defect reproduction

The immutable published Beta-3 baseline is
`6bbc84f7e074cf8532ed773b0f3fde736a03f0d7`.

Before the runtime semantic correction, the generic FD-67 regression at
`9a3b9981dec60d44f10df467bd91fa63f6fe6999` reached pytest in GitHub Actions
CI run `45511051193`. Ruff/Black and the zero-error typing ratchet passed;
pytest reported `993 passed, 1 skipped, 156 subtests` plus the one deliberate
new regression failure: the explicitly declared P2W-to-P2S graph evaluated
`DEGRADED` instead of `VALID`.

At that immutable baseline, the graph classifier maps the equal-ranked
P2W-to-P2S edge to `INVALID_GOVERNING_EDGE`. Candidate validation projects
structural findings into `graph_findings` and computes
`activation_ready = not validation_findings and not graph_findings`; the
released defect therefore blocks activation for that otherwise-valid graph.
This is the T01 before-state evidence.

### Corrective semantic/runtime candidate

The corrected candidate at
`e711ba96e95f267aa46c483cbb5638504b15c39c` was exercised by GitHub Actions
CI run `45513630593` before release-identity/ratchet reconciliation.

That run demonstrated:

- package build, wheel installation, `span-mcp --help`, and imported-version
  verification passed;
- Ruff and Black passed;
- the typing ratchet remained at zero errors;
- **1000 tests passed, 1 skipped, with 156 subtests**;
- the candidate, graph-health, forward-route, reverse-navigation,
  no-inferred-edge, singular-owner and installed-MCP Beta-4 cases all passed;
  and
- the only pytest failure was the intentionally unreconciled measured
  `test_lines` ratchet: **33,110 -> 33,336**.

That ratchet now records the measured test growth only. No production/source
quality ceiling or correctness gate is raised.

The assembled release candidate must pass the complete gates again after
release-identity reconciliation. Exact-head release readiness is governed by
the Beta-4 implementation plan; an earlier branch run is not substituted for
the exact reviewed master check.

### Assembled branch verification

The assembled Beta-4 branch candidate
`c7e4d45e06ec3411f6c8558a02f7503b27cd7ac4` passed GitHub Actions CI run
`45514424797`:

- build/distribution and wheel installation passed;
- `span-mcp --help` and imported package version passed;
- Ruff and Black passed;
- typing remained at **0 errors**;
- pytest reported **1001 passed, 1 skipped, 156 subtests**;
- aggregate coverage was **85%**;
- standalone plugin-notice delivery passed; and
- the coverage artifact uploaded successfully.

This closes the assembled-candidate verification gate. It is not the exact-head
master release-readiness gate; that remains T10 after reconciliation to
`master`.

## Release identity

| Surface | Identity |
| --- | --- |
| Package/PyPI | `1.0.0b4` |
| Git tag | `v1.0.0b4` |
| GitHub Release | `Span 1.0.0 Beta 4` |
| MCP Registry | `1.0.0-beta.4` |
| Repository lifecycle schema | **15** |
| Installation Functional Pyramid schema | **1** |

No declaration grammar, public MCP tool, persisted graph carrier, repository
schema or installation Functional Pyramid schema changes for Beta 4.

## Authorization boundary

Implementation completion, review, merge and green CI establish readiness only.
Publication requires the separate release-owner authorization defined in
[Contributing](contributing.md) and the
[Beta-4 programme](implementation-plans/1.0.0-beta4.md).

**Beta 4 is not authorized for publication.**
