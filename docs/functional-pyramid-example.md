# Functional Pyramid Version-3 worked example

A neutral, installation-independent example: `repo-a` and `repo-b`, areas
`area-a` and `area-b`, and a shared-ancestor source. It uses no product,
customer, or workspace identifier.

The Version-3 source examples below illustrate Span's derived internal
representation, not files that the repository user must author. The user-facing
initialization input is the flat classification in technical design §17.2.
The repository-kind source below is `repo-a`'s only root source; area-kind
sources have canonical non-root scopes.

```json
{
  "version": 3,
  "source_id": "repo-a:repository",
  "kind": "repository",
  "scope": ".",
  "documents": [
    {"repository_id": "repo-a", "document_ref": "docs/goals.md"},
    {"repository_id": "repo-a", "document_ref": "docs/invariants.md"}
  ],
  "placements": [
    {
      "document": {
        "repository_id": "repo-a",
        "document_ref": "docs/goals.md",
        "layer": "P0"
      },
      "scope": ".",
      "governing_placements": ["ROOT"]
    },
    {
      "document": {
        "repository_id": "repo-a",
        "document_ref": "docs/invariants.md",
        "layer": "P1"
      },
      "scope": ".",
      "governing_placements": [
        {
          "declaring_repository_id": "repo-a",
          "document": {
            "repository_id": "repo-a",
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

An area source owns only documents placed at its own scope. This one derives
from the repository P1 invariant and has no own P0; that is valid.

```json
{
  "version": 3,
  "source_id": "repo-a:area-a",
  "kind": "area",
  "scope": "area-a",
  "documents": [
    {"repository_id": "repo-a", "document_ref": "area-a/contract.md"}
  ],
  "placements": [
    {
      "document": {
        "repository_id": "repo-a",
        "document_ref": "area-a/contract.md",
        "layer": "P2S"
      },
      "scope": "area-a",
      "governing_placements": [
        {
          "declaring_repository_id": "repo-a",
          "document": {
            "repository_id": "repo-a",
            "document_ref": "docs/invariants.md",
            "layer": "P1"
          },
          "scope": "."
        }
      ]
    }
  ]
}
```

A shared-ancestor source is an ordinary area-kind source at the common ancestor.
It may govern several descendant areas without declaring a descendant count.

```json
{
  "version": 3,
  "source_id": "repo-a:areas",
  "kind": "area",
  "scope": "areas",
  "documents": [
    {"repository_id": "repo-a", "document_ref": "areas/shared.md"}
  ],
  "placements": [
    {
      "document": {
        "repository_id": "repo-a",
        "document_ref": "areas/shared.md",
        "layer": "P2S"
      },
      "scope": "areas",
      "governing_placements": [
        {
          "declaring_repository_id": "repo-a",
          "document": {
            "repository_id": "repo-a",
            "document_ref": "docs/invariants.md",
            "layer": "P1"
          },
          "scope": "."
        }
      ]
    }
  ]
}
```

## Initialization ingress

Supply the Version-1 Functional Pyramid classification document for each
explicitly selected member, using the exact grammar in
[technical design §17.2](technical-design.md#172-functional-pyramid-initialization-import).
The examples above are produced by Span, not additional inputs. The existing
Version-2 navigation bootstrap and direct member intent name the derived
whole-document sources; initialization constructs both automatically. See
[Install](install.md) for the governed initialization command and its status.

## Absent layer

No P2W placement is declared. A lookup of `area-a/nested` returns the applicable
P0, P1 and P2S placements and reports P2W as absent. Absence is not a finding and
does not make the route unresolved.

## Verify the example

- The structural validator returns no finding for this source set.
- The directory lookup returns the governing closure and the correct absent
  layer.
- A Version-2 declaration is rejected as `INVALID_DECLARATION_SOURCE`.
