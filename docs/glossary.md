# Glossary

**Understanding** — A saved explanation of a question over a scope, with a
stable identity and immutable versions. See [lifecycle](lifecycle.md).

**Version** — A full membership snapshot of exact conclusion revisions, gaps,
and provenance. It is not a conclusion revision counter.

**Conclusion revision** — One immutable explanation or withdrawal in a lineage.
The agent owns its meaning and the evidence-to-statement reasoning.

**Gap** — An unanswered question with a stated basis in a saved version.
A gap is not a supported conclusion.

**Candidate** — Potentially relevant saved understanding found by bounded scope
association or term overlap. Matching does not establish applicability.

**Scope** — The declared paths/evidence references bounding the investigation
or conclusion. Unexamined and truncated scope stays explicit.

**Observation** — Immutable admitted source content identity and excerpts, or
a recorded discovery-membership fingerprint. See [authority](authority-trust.md).

**Support** — A declared dependency on a source observation, authority binding,
exact premise revision, or discovery observation.

**CURRENT** — Declared support passed its present checks. This is neither
semantic truth nor proof of complete investigation.

**REASSESSMENT_REQUIRED** — Support changed or a premise was superseded or
withdrawn; investigate before treating the explanation as current.

**UNVERIFIABLE** — Required support cannot be established. Operational failure
is reported separately. See [freshness](freshness.md).

**Authority binding** — Declared governance with evidence, kind, status,
applicability, and any explicitly stated precedence. Relevance does not confer it.

**Basis** — The account of how evidence or premises led to a conclusion or action.
An accepted basis does not certify the prose as true.

**Challenge** — An explicit dispute with an independent revision counter and
history. Settlement requires a named disposition tied to resulting state.

**Context** — Recoverable, expiring operational investigation state. It binds a
caller request to a repository and scope, and retains admitted evidence.

**Receipt** — Immutable acceptance record for a recording identity and content.
Matching replay can succeed after context expiry while the receipt is retained.

**Recording identity** — `(repository_id, context_id, submission_id)`, preserved
by the caller before dispatch. Same identity with different content conflicts.

**Compare-and-set** — Accept an update only at the expected understanding or
challenge revision, preventing conflicting concurrent changes.

**Verification run** — Independent record of actual external execution and
its tested observations, outcome, time, observer, and limitations.
Qualification checks currency and does not rerun it or change its outcome.

**Cursor** — Opaque listing position. Resume the same operation with the same
request arguments and identity. It is not an interpretation continuation.

**Bounds** — Operational work/result limits with explicit omissions and
continuations. Question byte budgets do not measure total host context size.

**Readiness** — Store/provider availability and root binding, separate from
understanding, correctness, or completeness.

**Hook** — Optional event-local notice. Silence and configured wiring do not
prove delivery or semantic completeness. See [hooks](hooks.md).

**Structural evidence** — Provider-observed symbols, locations, and adjacency.
It supports investigation and grants no semantic or normative authority.

**Legacy terminology** — Claim taxonomies, coverage campaigns, and suspended
interpretation continuations in historical exports or older evidence. They are
not the 0.9.0 public lifecycle. See [design references](design-references.md).
