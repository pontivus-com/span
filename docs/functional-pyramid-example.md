# Functional Pyramid Version-3 worked example

A neutral, installation-independent example: `repo-a` and `repo-b`, areas
`area-a` and `area-b`, and a shared-ancestor source. It uses no product,
customer, or workspace identifier.

The repository-kind source below is `repo-a`'s only root source. It carries the
mandatory root P0 placement and one P1 invariant. Every other source is an
area-kind source at a canonical non-root scope.

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

## Ingress paths

The bootstrap remains Version 2 navigation configuration and selects declaration
sources; it owns no functional identity.

```json
{
  "version": 2,
  "declaration_sources": [
    {"locator": ".span/repo-a-repository.json", "ranges": []},
    {"locator": ".span/repo-a-area-a.json", "ranges": []},
    {"locator": ".span/repo-a-areas.json", "ranges": []}
  ]
}
```

The equivalent direct member intent names the same whole-document sources:

```json
{
  "repository_id": "repo-a",
  "declaration_sources": [
    {"locator": ".span/repo-a-repository.json", "ranges": []},
    {"locator": ".span/repo-a-area-a.json", "ranges": []},
    {"locator": ".span/repo-a-areas.json", "ranges": []}
  ]
}
```

Both paths resolve through the same decoder and graph validator and produce the
same structural result.

## Absent layer

No P2W placement is declared. A lookup of `area-a/nested` returns the applicable
P0, P1 and P2S placements and reports P2W as absent. Absence is not a finding and
does not make the route unresolved.

## Verify the example

- The structural validator returns no finding for this source set.
- The directory lookup returns the governing closure and the correct absent
  layer.
- A Version-2 declaration is rejected as `INVALID_DECLARATION_SOURCE`.
