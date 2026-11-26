---
name: span-functional-pyramid
description: Initialize, inspect, revise, deactivate, or explicitly exclude repositories from a Span Functional Pyramid. Use when work needs declared cross-repository governance, Functional Pyramid status/health, candidate validation, participation changes, or post-write governance re-establishment.
---

# Functional Pyramid lifecycle

Complete the canonical lifecycle before calling adoption, revision, or deactivation
complete. [Lifecycle authority](https://github.com/pontivus-com/span/blob/master/docs/lifecycle-contract.md#71-functional-pyramid-initializationadoption-lifecycle).

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

A participating repository declares Version-3 sources. Each source has:

- a stable non-empty source_id;
- a kind of `repository` or `area`;
- one explicit directory `scope` (`.` only for the single repository-kind source);
- an explicit documents membership set using repository_id + document_ref;
- placements at that same scope.

Every listed document has exactly one placement at the source scope. A
placement's scope must equal its source scope. One canonical document occupies
exactly one layer and one scope in its declaring repository; do not repeat it
across sources or layers. A shared-ancestor document belongs in the area-kind
source at the ancestor scope. Only declared sources establish areas; Span never
infers them from paths, workflow names or titles.

Each participating repository has exactly one `repository`-kind source at scope
`.` containing at least one `P0` placement governed by `ROOT`. No other layer is
mandatory. A legitimately scoped area `P0` is governed directly by `ROOT`; lower
area layers are governed by that scoped `P0` or an applicable ancestor. An
absent non-root layer is reported, never required.

```text
{
  "version": 3,
  "source_id": "repo-1:repository",
  "kind": "repository",
  "scope": ".",
  "documents": [
    {"repository_id": "repo-1", "document_ref": "docs/goals.md"},
    {"repository_id": "repo-1", "document_ref": "docs/invariants.md"}
  ],
  "placements": [
    {
      "document": {
        "repository_id": "repo-1",
        "document_ref": "docs/goals.md",
        "layer": "P0"
      },
      "scope": ".",
      "governing_placements": ["ROOT"]
    },
    {
      "document": {
        "repository_id": "repo-1",
        "document_ref": "docs/invariants.md",
        "layer": "P1"
      },
      "scope": ".",
      "governing_placements": [
        {
          "declaring_repository_id": "repo-1",
          "document": {
            "repository_id": "repo-1",
            "document_ref": "docs/goals.md",
            "layer": "P0"
          },
          "scope": "."
        }
      ]
    }
  ]
}
```

An area source uses `"kind": "area"`, a canonical non-root `scope`, and only
placements at that scope. A source governing several descendant areas is an
ordinary area-kind source at their shared ancestor scope.

Layer rubric: P0 states purpose; P1 invariants; P2S shared contracts; P2W
workflow contracts; P3 implementation contracts; P4 behavior/mechanisms. A pure
governance document that states several layers is split into layer-owning
documents. Functional statements in an ADR or `AGENTS.md` are extracted into the
appropriate layer owner while the historical record stays intact. Preserve rule
identity and governing relationships; never invent a rule ID or make a document
own a second layer to fill an absent one. Span validates the declared structure;
the repository owner owns substantive classification and completeness.

If repository-owned declarations must change, edit them outside Span and then use
`reconsider` for each directly edited repository. Dispose every actionable
REASSESSMENT_REQUIRED/UNVERIFIABLE result before candidate validation continues.

### Finding recovery

| Finding | Repair |
|---|---|
| `INVALID_DECLARATION` | Correct source-set topology: exactly one repository-kind source at `.`, area sources non-root, unique source IDs/scopes. |
| `DUPLICATE_DOCUMENT_SOURCE` / `_LAYER` / `_SCOPE` / `_PLACEMENT` | Keep one membership, one layer, one scope and one placement per canonical document. |
| `DOCUMENT_SCOPE_MISMATCH` | Make the placement scope equal its containing source scope, or move the placement to the correct source. |
| `MISSING_AREA_DOCUMENT` / `UNLISTED_AREA_DOCUMENT` | Make `documents` and `placements` agree at the source scope. |
| `MISSING_ROOT_PLACEMENT` | Add a scope `.` P0 placement governed by `ROOT`. |
| `INVALID_GOVERNING_EDGE` / `DOCUMENT_CYCLE` | Correct the governing references under the fixed layer relation. |
| `INVALID_DECLARATION_SOURCE` (including Version 2) | Author a valid Version-3 source; there is no Version-2 translation. |

An ACTIVE Version-2 source stays ACTIVE and reports `DEGRADED` until an accepted
Version-3 revision. Correct the sources, validate the replacement candidate and
record the revision; never bypass with `EXCLUDED` or `UNCONFIGURED`.

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
          {"locator": "docs/functional-pyramid.json", "ranges": []},
          {"locator": "docs/functional-pyramid-area.json", "ranges": []}
        ]
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
      ]
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

### Governed installation inputs

The governed installer names `--functional-pyramid-bootstrap-file REPOSITORY_ID
PATH` and `--authority-bindings-file REPOSITORY_ID PATH` once per participating
repository; omission preserves the prior configuration, so omission is not
neutral. `--authority-seeds-file` joins the governed set only where seeds change.
An existing conventional `.span/functional-pyramid.json` is a governed input even
when no argument is supplied.

`span-install --verify-only` evaluates the complete retained ACTIVE graph and
reports one of `PROVENANCE_MATCH`, `PROVENANCE_MISMATCH` or
`PROVENANCE_NOT_RECORDED`. A structural failure or a mismatch exits non-zero and
prohibits acceptance. Not-recorded is reported as not applicable for a generically
established instance, but is an acceptance failure where a committed governed
baseline exists.

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
