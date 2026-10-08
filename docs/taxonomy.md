# Canonical taxonomy (plan §4)

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
