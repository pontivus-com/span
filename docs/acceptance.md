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

### Repository implementation candidate

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
| Repository lifecycle schema | **15** |
| Installation Functional Pyramid schema | **1** |

Beta 5 changes the Functional Pyramid declaration grammar and public carriers
from the retired rule/coverage model to Version-2 document placements. It does
not add an MCP tool, change repository schema 15, or change installation
Functional Pyramid schema 1.

## Remaining gates

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
