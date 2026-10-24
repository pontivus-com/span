# Canonical taxonomy

Closed vocabularies — workers never invent kinds without a contract
amendment.

## Subjects

`SubjectKind`: REPOSITORY, SUBSYSTEM, COMPONENT, CAPABILITY,
CODE_SYMBOL, CONTRACT, BOUNDARY, REPRESENTATION, CONFIGURATION,
DOCUMENT, TEST_OR_GATE, SURFACE, FIELD, EXTERNAL_DEPENDENCY, OTHER
(`OTHER` only with non-empty `declared_kind`; no built-in semantics).

Identity: `repository_id + subject_kind + canonical_locator`. Names
alone are never identity. Ambiguity returns candidates. Provider IDs
are opaque evidence, never canonical identity. Semantic-only subjects
(capabilities, boundaries, surfaces…) enter through evidence-backed
agent proposal plus core validation — never from the structural
provider.

### Structural node kinds

The structural provider vocabulary is closed and mapped, never
free-form. Every node kind maps to exactly one `SubjectKind`:

| Provider node kind | `SubjectKind` |
| --- | --- |
| `file`, `module` | COMPONENT |
| `function`, `class`, `method`, `interface`, `type`, `enum` | CODE_SYMBOL |
| `struct`, `constant` | CODE_SYMBOL |

`enum` is a named type declaration in the same sense as `class`,
`interface`, and `type`. `struct` is a nominal data carrier — Go
structs, Java records, Swift structs — reported by the provider as its
own node kind rather than as `class`, and classified here as
CODE_SYMBOL. `module` is a code container, the role a file plays (Rust
`mod`), and never a subsystem: it carries no semantic boundary.
`constant` is a named value declaration (Rust `const`/`static`); like a
type declaration it is a named declaration in code, not a callable and
not a member of a type. A kind outside this table is rejected, never
guessed.

Edges are mapped the same way: `contains` → DEFINES; `imports`,
`calls`, `references`, and `depends_on` → their namesake kinds; and
`extends` / `implements` → DEPENDS_ON, because a compile-time
dependency is structural possibility, never a semantic IMPLEMENTS
claim.

### Coverage status

Every persisted semantic subject carries exactly one coverage status.
They are evaluated in this order, and the first match wins:

| Status | Meaning |
| --- | --- |
| `UNVERIFIABLE` | A conclusion exists, but the support needed to confirm it could not be obtained: a recorded source is absent from the inventory, an authority seed is missing, an inventory fingerprint is unavailable, or a bounded premise walk did not complete. It is neither current nor known-stale. A provider or store failure is not this state — the operation fails instead. |
| `STALE` | Supporting evidence, or an effective question, changed; the affected conclusion needs reassessment. |
| `INCOMPLETE` | Adopted understanding with work outstanding — a pending or open question, an unexamined question scope, or a truncated page. |
| `UNASSESSED` | No adopted question coverage is persisted for the subject; this is the `explain` entry point. |
| `CURRENT` | Adopted understanding whose questions are decided and whose evidence, verification, and dependencies are current. |

A persisted question carries exactly one decision: `PENDING`
(unresolved and handed out), `ANSWERED`, `OPEN` (examined and still
unresolved), or `NOT_APPLICABLE`. A stale effective question is
reported as `STALE` coverage; the stored decision is never rewritten to
express freshness.

Readiness is a separate, operational state. It is not coverage, and it
is never semantic truth.

## Claims (one typed value per kind)

PURPOSE · CAPABILITY_MEMBERSHIP · RESPONSIBILITY ·
OWNERSHIP_CUSTODY (owner/custodian/writer/producer/judge ×
exclusive/non-exclusive/unknown) · REPRESENTATION_CONTRACT ·
TRANSFORMATION_OWNERSHIP · INVARIANT_CONSTRAINT ·
CONFIGURATION_ENVIRONMENT · LIFECYCLE_STATE (create/use/change/
persist/terminal/fail/recover/abandon/replay/retain/remove/other) ·
VERIFICATION (test/gate/review × candidate/current-pass/current-fail/
stale/unknown — candidates are never reported as passes).

## Relationships

MEMBER_OF · IMPLEMENTS · PRODUCES · CARRIES · CONSUMES · DEPENDS_ON ·
CROSSES_BOUNDARY · REPRESENTS_AS · TRANSFORMS_TO · GOVERNED_BY ·
CONFIGURED_BY · PERSISTS_AT · TRANSITIONS_TO · VERIFIED_BY ·
SUPERSEDES. (`AFFECTS` is derived at query time, never persisted.)

Every material claim/relationship carries evidence, an optional
authority binding, trust, freshness, and a bounded `SemanticBasis`
whose summary restates the evidence/derivation relationship.
