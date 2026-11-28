# Acceptance and evidence

> **Document role: current verification evidence.** This page records only what
> the active Beta-5 repository candidate has demonstrated. It does not define
> product requirements; those remain in the Functional Pyramid and its governing
> requirements pyramid.

> **What can we currently claim about the Beta-5 candidate, based on evidence?**

Superseded Beta-4 and earlier campaign evidence is retained in
[Historical acceptance evidence](acceptance-history.md).

## Current Beta-5 verification state

The governing functional acceptance authority is
[Functional Design §15](functional-design.md#15-version-1-beta-functional-acceptance).
The live requirement-to-test mapping is the
[functional-acceptance matrix](functional-acceptance.md), and the
[Invariant audit matrix](invariants.md) records architectural enforcement.
Neither matrix is a release receipt.

### Current public-boundary implementation candidate (2026-11-28)

Exact code head `053bc712e6bb5f113041dfedda04dbe114b56ddf` on the
canonical Beta-5 release branch failed
[CI run 46090133337](https://github.com/pontivus-com/span/actions/runs/46090133337).
Build/distribution job 140808905712 passed. Test job 140808905961 passed
diff hygiene, Ruff/Black and the zero-error typing ratchet, then reported
**1093 passed, 1 failed, 1 skipped, 252 subtests passed**. The failure was
`tests/unit/test_surface_conformance.py::SurfaceConformanceTest::test_result_union_declarations_agree`
(ask result union: five refreshed initial effect families absent and
retired EvidencePage still present). Plugin notice delivery and coverage
upload were skipped. This is failing diagnostic evidence, not acceptance.

The subsequent selective replacement-lineage/regression commit
`afd76fe4297dc7993c77963b305f7ce229dc2f77` and documentation/history
reconciliation require their own exact-head verification. No result from
the earlier run establishes these later changes. PUB-02–10 and S-FIELD-04
remain open under the single implementation plan.

### Historical repository implementation candidate (Version 2)


Exact implementation head
`af0379f9b4f5234faa2814d642151ebc89733e3f` passed GitHub Actions CI run `45590632230`.

That run demonstrated:

- build, sdist/wheel inspection and distribution verification passed for
  `span-mcp==1.0.0b5`;
- `git diff --check`, Ruff and Black passed;
- the typing ratchet remained at **0 errors**;
- pytest reported **981 passed, 1 skipped, 155 subtests**;
- aggregate coverage was **84%** and the coverage artifact uploaded;
- standalone plugin-notice delivery passed **14/14**;
- the non-editable installed MCP lane passed, including fresh-process cold
  activation, the two-repository Version-2 Functional Pyramid journey, exact
  root and nested directory selection, additive document routes, retained
  normative route support and reconsider/re-establishment behavior;
- the public request/result schemas agreed with compact wire encoding for
  document-route carriers; and
- the schema-14 → 15 transition retained Functional Pyramid
  conclusion/pyramid route-dependency coordinates even when the historical
  support payload itself was intentionally undecodable, without fabricating a
  Version-2 placement graph.

This evidence closes the repository-internal implementation and verification
work in Beta-5 plan tasks 2–13. It does **not** establish adopter-specific
cutover correctness, managed-host preview delivery, authorization for a live
cutover, independent review, or release authorization.

Documentation-only reconciliation after this implementation run must still pass
the ordinary exact-head CI gates. Recording a prior run here does not exempt a
later candidate head from those gates.

## Release identity

| Surface | Identity |
| --- | --- |
| Package/PyPI | `1.0.0b5` |
| Git tag | `v1.0.0b5` |
| GitHub Release | `Span 1.0.0 Beta 5` |
| MCP Registry | `1.0.0-beta.5` |
| Repository lifecycle schema (active candidate target) | **16** |
| Installation Functional Pyramid schema (active candidate target) | **2** |

The historical Version-2 verification above used schema 15/1. The active
candidate uses Version-3 declarations and the schema-16/2 offline cutover.
The public MCP surface remains exactly ask, record and reconsider.
The active transition and public delivery acceptance remain open.

## Remaining gates

- PUB-02–10 and S-FIELD-04: complete the governing implementation plan and
  exact-head verification; no historical run substitutes for this gate;

- task 14: adopter-owned Version-2 declaration preparation and isolated cutover
  rehearsal outside the Span repository;
- task 15: unreleased preview installation and verification in isolated Codex
  and OpenCode host configuration;
- task 16: explicit operator authorization, verified backup, candidate
  revalidation and atomic live cutover; and
- task 17: independent design/code review, finding reconciliation and
  release-owner control.

## Authorization boundary

Implementation completion and green repository CI establish only the internal
candidate evidence above. Publication and live migration are separately owned
operations under [Contributing](contributing.md) and the
[Beta-5 implementation plan](implementation-plans/1.0.0-beta5.md).

**Beta 5 is not authorized for publication or live cutover by this evidence.**
