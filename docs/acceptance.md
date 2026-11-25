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

The evidence-only Beta-3 probe at
`72c80b1db7d3f2638b1f516abcf4f51cefd900f4` was exercised by GitHub Actions
CI run `45514490751`. Build, Ruff/Black and typing reached the test lane. The
generic action-aware candidate had no unrelated validation blocker and produced
the exact observed tuple
`(activation_ready=false, validation_findings=(), graph_findings=(INVALID_GOVERNING_EDGE,))`
for the explicit P2W-to-P2S edge. Pytest reported `993 passed, 1 skipped, 156
subtests` plus that deliberate defect assertion.

The earlier pre-fix regression run `45511051193` independently demonstrated
the same released classifier at graph-health/route level: the explicit edge made
health `DEGRADED` instead of `VALID`. Together these are the retained T01
before-state evidence; neither evidence-only commit belongs to the Beta-4
implementation line.

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

### Final pre-review branch verification

Exact Beta-4 candidate `7d49a52f6c9f649d6663aa40bd78fb7ebb623bc4`
passed both push CI run `45515508530` and pull-request CI run
`45515522062`. The PR run executed `git diff --check` over the complete
campaign delta. The build lane created and inspected one sdist and one wheel for
safe paths and required package content, installed the wheel, and verified the
CLI and imported Beta-4 version. Ruff/Black and zero-error typing passed; pytest
reported **1001 passed, 1 skipped, 156 subtests**, aggregate coverage was
**85%**, the installed-MCP Beta-4 journey passed, plugin notice delivery was
**14/14**, and coverage upload passed.

Those runs are retained supporting evidence for the same assembled content.
They do not self-close a later candidate head merely because documentation
records them. T07–T10 are exact-head external closure facts under the Beta-4
programme: any candidate movement reopens the applicable gate, and run/review
identifiers are not written back into the candidate merely to record closure.

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

This was a green assembled-candidate run, but subsequent
evidence/documentation corrections moved the branch head. It is therefore
supporting evidence only; T07 remains open until the final branch head receives
the same complete verification plus the required `git diff --check`. T10
remains the separate exact-head master release-readiness gate.

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
