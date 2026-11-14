# Glossary

**Understanding** — A saved explanation of a question over a scope, with a
stable identity and immutable versions. See [lifecycle](lifecycle.md).

**Version** — A full membership snapshot of exact conclusion revisions,
recorded question gaps, and provenance. It is not a conclusion revision
counter.

**Conclusion revision** — One immutable explanation or withdrawal in a lineage.
The agent owns its meaning and the evidence-to-statement reasoning.

**Recorded question gap** — An unanswered question with a stated basis in a
saved version. It is not a supported conclusion.

**Gap** — The `ask` result when no matched conclusion is current. It carries
exactly one reason: `invalidated`, `unverifiable`, or `unassessed`,
the prior non-current conclusions as historical content, and a recovery that
names the next action.

**Historical conclusion** — A non-current conclusion returned as content in a
`Gap`: exact revision, understanding version, statement, evidence references,
and present non-current state. It never becomes current answer content.

**Surface document view** — The pure surface/reference `ask` result: current
conclusions grouped by the recorded question they answer, plus status, gaps, and
verification. It is assembled on read and cannot drift.

**Surface-first reuse** — Reading the surface document view and selecting the
current conclusion that answers the task. Targeted reuse uses
`RecordedQuestionSelector` only when the exact recorded question is known; a
different or paraphrased value does not similarity-match and is
`Gap/unassessed`.

**Rejection cause** — The exact server message and typed cause kind carried by a
`Rejected` result, with the required action and the structured current version
or boundary version when one exists. It is not derived from keyword matching.

**Surface** — The unit an answer is scoped to: a file, symbol, service, or
domain. A path or declared name resolves to a surface; more than one match is
`AmbiguousSurface`.

**Exact surface** — The public `{kind, locator}` identity supplied to `ask`.
It resolves by identity, never containment. An `AmbiguousSurface` candidate is
copied back verbatim.

**Declared surface** — A service or domain created or updated through
`record(kind="surface")` with a boundary and optional parent. Its boundary has
its own compare-and-set version.

**Historical snapshot** — A `RetrievedUnderstanding` selected by exact
understanding/version. It is never merged into a current `Answer`.

**Continuation** — An opaque, stateless token that resumes selected evidence
from explicit evidence admission. It is valid only for its bound live context
and always advances; an unusable continuation is a typed rejection.

**Possible impact** — A conclusion was included in a `reconsider` result because
its surface or dependency was considered. It may still be `CURRENT`.

**Actual loss** — A conclusion whose support is `REASSESSMENT_REQUIRED` or
`UNVERIFIABLE`; it requires re-establishment.

**Answer** — Current conclusions for one surface with per-conclusion support,
surface status (including `stale_refs`), recorded gaps, and applicable
verification.

**Surface status** — The distribution over a surface: current, stale,
unassessed, unexamined, and descendant statuses. `stale_refs` names each stale
conclusion by exact revision, understanding version, and present state; the
count and references describe the same set. The status carries no statement
content.

**Scope** — The declared paths/evidence references bounding the investigation,
conclusion, or verification run. Unexamined and truncated scope stays explicit.

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

**Recording identity** — `(repository_id, request_id)`, preserved
by the caller before dispatch. Same identity with different content conflicts.

**Compare-and-set** — Accept an update only at the expected understanding or
challenge revision, preventing conflicting concurrent changes.

**Verification run** — Independent record of actual external execution with its
declared scope, command or scenario, outcome, time, observer, limitations, and
the observations or evidence it tested. It applies to surfaces within its
declared scope. Qualification checks currency and does not rerun it or change
its outcome.

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
not the current public lifecycle. See [design references](design-references.md).
