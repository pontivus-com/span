# Glossary

Terms used across Span's documentation. Each entry is a pointer to the page that
owns the definition; the code and tests remain the authority.

**AFFECTS** — A derived query-time relation describing what a change can reach.
It is computed from persisted relationships and premises, never stored as a claim
or relationship. See [queries](queries.md#change-impact).

**Authority (`AuthorityBinding`)** — A governing source with a kind, a status
(accepted, declared, draft, superseded, unknown), applicability, and optional
declared precedence. Evidence is not authority: finding a document does not make
it governing. See [authority and trust](authority-trust.md).

**Bounds** — Operational limits on an answer: maximum results, depth, evidence
units, and subjects. Bounds never change semantic meaning, only how much of an
answer is returned. See [queries](queries.md#bounds).

**Claim** — One typed statement about a subject, with exactly one value for its
kind (purpose, ownership, invariant, and so on). Every material claim carries
evidence, optional authority, trust, freshness, and a basis. See
[taxonomy](taxonomy.md#claims-one-typed-value-per-kind).

**Continuation** — An opaque, single-use, TTL-bounded handle to a suspended
interpretation task. It is never persisted and never authoritative. See
[agent interpretation exchange](interpretation.md).

**Coverage disposition** — The state of a semantic question: `PENDING`, `OPEN`,
`ANSWERED`, or `NOT_APPLICABLE`. Coverage is not the same as freshness, and
`ANSWERED` means the analysis was recorded, not that a reviewer approved it.
See [interpretation](interpretation.md#explicit-completion).

**Current / stale / unverifiable** — The three freshness states. `CURRENT` means
the required support still holds; `STALE` means supporting evidence changed;
`UNVERIFIABLE` means Span cannot establish currency. The gap stays visible. See
[freshness](freshness.md).

**Evidence (`EvidenceRef`)** — A located, revisioned source span with a source
kind. Evidence supports reasoning; it confers no authority and no truth. See
[authority and trust](authority-trust.md#evidence).

**Interpretation profile** — The named contract a pending task carries
(`SA_1_7_V1`): scope, evidence, behavior, typed submission, adversarial check,
and fresh readback. See [interpretation](interpretation.md#interpretation-profile).

**PendingInterpretation** — The typed suspension returned when current
understanding is insufficient. It carries a continuation and a bounded
`SemanticInterpretationRequest`. See
[interpretation](interpretation.md#request-semanticinterpretationrequest).

**Question (`SemanticQuestionScope`)** — The bounded question a pending task
answers, identified by a question class (`CQ-01`–`CQ-09`, with `CQ-10`
cross-cutting) plus a subject, scope root, slice, and materiality basis.

**Relationship** — A typed edge between subjects (membership, implementation,
dependency, governance, supersession, and so on) with the same evidence,
authority, trust, and freshness obligations as a claim. See
[taxonomy](taxonomy.md#relationships).

**Repository state** — The revision or state fingerprint Span observed, plus a
dirty-tree flag. Freshness compares understanding against this state, never
against wall-clock age. See [freshness](freshness.md#preflight-before-anything-is-presented-as-current).

**ResolutionRequirement** — A typed, non-silent description of what is missing
for a claim or answer (missing authority, missing evidence, ambiguity, and so
on). It is reported, not hidden. See [authority and trust](authority-trust.md).

**Scope / target** — The exact set of paths or subjects a question or an
establishment campaign is allowed to cover. Scope never silently expands; a
scoped refresh covers one recorded scope. See [lifecycle](lifecycle.md).

**SemanticBasis** — A short typed account of how a claim or relationship was
derived: explicit evidence, semantic interpretation, structural observation, or a
derived join. Empty bases fail validation.

**Structural source** — The wiring-graph provider (a pinned local indexer) that
supplies partitions, locations, and edges. Its output is evidence only; it never
supplies semantic truth or authority. See [indexing](indexing.md).

**Subject** — A typed entity (repository, subsystem, component, capability, code
symbol, contract, boundary, representation, configuration, document, test or
gate, surface, field, external dependency, or other). Identity is
`repository_id + subject_kind + canonical_locator`, never a name alone. See
[taxonomy](taxonomy.md#subjects).

**Trust (`TrustState`)** — How well a claim is established:
`ESTABLISHED`, `PARTIAL`, `AMBIGUOUS`, `CONFLICTED`, or `UNRESOLVED`. Trust and
freshness are separate and are never mixed. See
[authority and trust](authority-trust.md#trust-vs-freshness-never-mixed).

**UNASSESSED** — Coverage for a subject or area nobody has examined yet. It is
reported explicitly rather than treated as complete. See [lifecycle](lifecycle.md).
