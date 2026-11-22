---
name: span-functional-pyramid
description: Initialize, inspect, revise, deactivate, or explicitly exclude repositories from a Span Functional Pyramid. Use when work needs declared cross-repository governance, Functional Pyramid status/health, candidate validation, participation changes, or post-write governance re-establishment.
---

# Functional Pyramid lifecycle

Complete the canonical lifecycle before calling adoption, revision, or deactivation
complete. [Lifecycle authority](https://github.com/pontivus-com/span/blob/master/docs/lifecycle-contract.md#71-initialization--adoption-state-machine).

The Functional Pyramid adds declared governing applicability to Span's existing
maintained-understanding lifecycle. It does not replace canonical documents,
invent rule meaning, generate conformance judgments, or add another MCP tool.
Use only `ask`, `record`, and `reconsider`.

## 1. STATUS

Obtain durable participation and live health:

```json
{
  "selector": {
    "$type": "FunctionalPyramidSelector",
    "repository_id": "repo-1"
  }
}
```

- UNCONFIGURED: adoption may proceed when intended.
- EXCLUDED: remain excluded unless adoption is explicitly intended.
- ACTIVE + VALID: ordinary runtime may proceed unless a revision is intended.
- ACTIVE + DEGRADED: investigate/repair governance before treating setup as
  complete.

## 2. DISCOVER / DECLARE / REALIGN

The agent establishes the intended members, declaration sources, FunctionalScope,
and PARTIAL/COMPLETE coverage. Span does not manufacture that intent.

If repository-owned declarations must change, edit them outside Span and then use
`reconsider` for each directly edited repository. Dispose every actionable
REASSESSMENT_REQUIRED/UNVERIFIABLE result before candidate validation continues.

## 3. VALIDATE

Validate the complete intended member set through `ask`:

```json
{
  "selector": {
    "$type": "FunctionalPyramidCandidateSelector",
    "action": "activate",
    "members": [
      {
        "repository_id": "repo-1",
        "declaration_sources": [
          {"locator": "docs/functional-pyramid.json", "ranges": []}
        ],
        "functional_scope": {
          "selectors": [{"kind": "PREFIX", "path": "src"}]
        },
        "coverage": "PARTIAL"
      }
    ]
  }
}
```

Proceed only when the returned candidate has no validation/graph blockers and
activation readiness is true. Source/graph findings require declaration repair;
registration/membership/version findings require fresh STATUS orientation.
Rejected means fix the request. Unavailable is an operational blocker.

## 4. ACTIVATE / REVISE

Record the already-validated intent through the existing `record` tool:

```json
{
  "request_id": "fp-activate-1",
  "kind": "functional_pyramid",
  "action": "activate",
  "members": [
    {
      "repository_id": "repo-1",
      "declaration_sources": [
        {"locator": "docs/functional-pyramid.json", "ranges": []}
      ],
      "functional_scope": {
        "selectors": [{"kind": "PREFIX", "path": "src"}]
      },
      "coverage": "PARTIAL"
    }
  ]
}
```

Revision uses the exact current pyramid identity/version and the complete
replacement member set. Do not send an investigation context: participation
writes are installation-scoped.

## 5. VERIFY / REESTABLISH

After acceptance, obtain exact status again and verify the returned
pyramid/version/member set and VALID health.

Acceptance is not completion when the accepted write returns actionable
dependent effects. Use its repository-bound re-establishment contexts and update
coordinates to investigate and `record` the affected conclusions. Do not call
`reconsider` again for the participation write itself: that write already
returned the canonical affected projection.

Keep the Functional Pyramid receipt selector until all accepted dependent-effect
identities are no longer actionable or have been re-established CURRENT. If a
later repair/revision occurs, it does not erase an earlier accepted obligation.

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
- a conformance judgment is NORMATIVE and is recorded with
  assertion_nature=NORMATIVE; Span derives route/authority support;
- `reconsider` after implementation or governance edits returns the same
  affected-surface/conclusion projection, including cross-repository effects.

An accepted NORMATIVE record with non-current qualification is retained but does
not complete the task. Continue investigation/re-establishment until required
dispositions are CURRENT or report the named operational blocker.

Detail: [lifecycle](https://github.com/pontivus-com/span/blob/master/docs/lifecycle.md), [MCP reference](https://github.com/pontivus-com/span/blob/master/docs/mcp.md).
