---
name: span-functional-pyramid
description: Initialize, inspect, revise, deactivate, or explicitly exclude repositories from a Span Functional Pyramid. Use when work needs declared cross-repository governance, Functional Pyramid status/health, candidate validation, participation changes, or post-write governance re-establishment.
---

# Functional Pyramid lifecycle

Complete the canonical lifecycle before calling adoption, revision or deactivation
complete. [Lifecycle authority](https://github.com/pontivus-com/span/blob/master/docs/lifecycle-contract.md#71-functional-pyramid-initializationadoption-lifecycle).

## Initialize or revise governed installation

The repository supplies the owner-approved Functional Pyramid classification
(one file per intended member) under technical design §17.2. Span owns every
mechanical initialization step. Do not manually build declarations, membership
sets, binding files, bootstrap files, candidate payloads or activation requests
as part of installation. Do not require a commit of generated metadata.

1. Obtain or prepare the repository-owned classification only when the user
   requests help with substantive governance decisions; never infer authority or
   edit canonical governance without authorization. Validate the owner-supplied
   member selection, not inferred membership.
2. Invoke the governed `span-install` form from the installation guide with the
   repository paths and classification mappings. Use the existing installed
   command only when the supported build implements it. If unavailable, report
   the implementation blocker; do not reconstruct a manual fallback workflow.
3. Inspect the returned initialization outcome and exact receipt/status. If
   input is invalid, explain the reported defect to the owner; if operationally
   unavailable, report that blocker. Do not bypass validation.
4. For accepted writes with actionable effects, retain the receipt selector and
   use the returned repository-bound contexts and update coordinates to
   investigate and `record` the affected conclusions. Do not call `reconsider`
   again for the participation write. Do not mark initialization complete while
   actionable effects remain or verification is incomplete.

## Status and explicit lifecycle operations

Use `ask` with `FunctionalPyramidSelector` for exact status. ACTIVE + VALID
permits ordinary governed work once semantic obligations are disposed.
UNCONFIGURED routes to governed initialization when intended; EXCLUDED remains
explicit descriptive use unless adoption is requested; ACTIVE + DEGRADED
requires repair. Explicit separately authorized membership changes, deactivation
and exclusion retain their existing candidate/record contracts in the MCP
reference. The public operations remain `ask`, `record`, `reconsider`.

## Deactivate / exclude

Deactivate an ACTIVE pyramid with its exact identity/version. If dependent
effects are returned, re-establish them before the deactivation task is complete.

Use explicit exclusion only for a repository that is not an ACTIVE member:

```json
{
  "request_id": "fp-exclude-1",
  "kind": "functional_pyramid",
  "action": "exclude",
  "repository_id": "repo-1"
}
```

## Ordinary runtime

For ACTIVE repositories, the ordinary lifecycle remains unchanged:

- `ask` returns retained understanding plus governing orientation for the same
  semantic scope;
- a directory lookup returns that directory's declared document placements from
  P0 through the deepest applicable layer, including ancestor and root
  placements. Every participating directory returns a result; there is no
  uncovered-path answer. Absent layers are reported as absent;
- a conformance judgment is NORMATIVE and is recorded with
  assertion_nature=NORMATIVE; Span derives route/authority support;
- `reconsider` after implementation or governance edits returns the same
  affected-surface/conclusion projection, including cross-repository effects.

An accepted NORMATIVE record with non-current qualification is retained but does
not complete the task. Continue investigation/re-establishment until required
dispositions are CURRENT or report the named operational blocker.

Semantic curation is independent of Functional Pyramid authority. Curating a
CURRENT NORMATIVE revision does not change participation, health, applicability,
route identity, or authority support; later governance/support loss still makes
that curated revision non-servable until support is re-established.

Detail: [lifecycle](https://github.com/pontivus-com/span/blob/master/docs/lifecycle.md), [MCP reference](https://github.com/pontivus-com/span/blob/master/docs/mcp.md).
