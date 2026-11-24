# Glossary

Start with the core terms if you are using Span. The advanced section is for
exact protocol, audit, governance, and implementation discussions.

## Core product terms

**Understanding** — A retained explanation of a question about a software scope,
with stable identity and preserved history. See [Agent lifecycle](lifecycle.md).

**Surface** — The software unit an understanding is about: a file, symbol,
service, or domain.

**Scope** — The declared software boundary an investigation, conclusion, or
verification applies to. Incomplete or truncated scope remains explicit.

**Support** — The recorded dependencies that established a conclusion, such as
source evidence, declared authority, another exact conclusion, observed
membership, or a Functional Pyramid route.

**CAPTURED** — The exact semantic revision has been retained from engineering
work but has not yet been accepted for shared reuse by a separate reviewer.

**CURATED** — A reviewer has explicitly accepted that exact semantic revision
for shared reuse. Curation does not certify semantic truth and does not replace
support currency.

**CURRENT** — The recorded support required by the conclusion still passes its
present checks. This is not proof that the interpretation is correct or
complete.

**REASSESSMENT_REQUIRED** — Something the conclusion depends on changed; the
meaning must be investigated again before ordinary reuse.

**UNVERIFIABLE** — Required support cannot currently be established.
Operational failure is reported separately. See
[Support currency and reassessment](freshness.md).

**Gap** — The requested reusable understanding is not currently available for
the selected scope. A gap may represent unassessed knowledge, invalidated
knowledge, or support that cannot presently be established.

**Challenge** — An explicit semantic dispute about retained knowledge. A
challenge is resolved through an explicit disposition; matching source bytes or
a passing test do not settle it automatically.

**Verification run** — An independent record of an external execution or review,
including its scope, observed outcome, evidence, time, observer, and
limitations. Qualification checks whether the recorded support still holds; it
does not rerun the verification.

**Functional Pyramid** — Span's declared project-governance graph. It connects
software scope to applicable project goals, principles, contracts, functional
design, and technical design while leaving canonical rule content at its owning
source.

**Authority binding** — An explicit declaration that identifies governing
project material together with its status and applicability. Relevance alone
does not create authority.

**Hook** — An optional event-local lifecycle reminder. Hook silence or
configuration does not establish semantic completeness or support currency. See
[Lifecycle hooks](hooks.md).

**Readiness** — Operational availability of the required Span runtime/store
boundary. Readiness does not mean the repository has been semantically
understood.

## Retrieval and lifecycle reference terms

**Answer** — The ordinary reusable knowledge returned for one surface, together
with its current status, recorded gaps, and applicable verification.

**Surface document view** — The surface-first `ask` result that assembles
reusable conclusions grouped by the recorded questions they answer, plus status,
gaps, and verification.

**Surface-first reuse** — Starting from a file, symbol, service, or domain and
reading the maintained knowledge associated with it, without requiring a saved
internal understanding ID or previous conversation.

**Exact surface** — The public `{kind, locator}` identity supplied to `ask`.
It resolves by identity rather than containment.

**Declared surface** — A service or domain whose boundary is explicitly
declared through Span. File and symbol surfaces do not require that declaration.

**Recorded question gap** — An unanswered question retained with its basis in an
understanding version. It is not a supported conclusion.

**Historical conclusion** — A prior non-current conclusion retained for history
or recovery. Historical content is not automatically current Answer content.

**Historical snapshot** — An exact retained understanding/version retrieved for
audit or recovery rather than ordinary current reuse.

**Version** — A complete immutable membership snapshot of the conclusion
revisions and recorded question gaps belonging to one understanding at that
point in history.

**Conclusion revision** — One immutable semantic statement or withdrawal in a
conclusion lineage.

**Basis** — The investigator's account of how evidence or premises led to a
conclusion or lifecycle action. Acceptance of a basis does not certify the
statement true.

**Possible impact** — A conclusion appeared in a `reconsider` result because
its surface or dependency was considered. It may still be current.

**Actual loss** — A conclusion whose support is
`REASSESSMENT_REQUIRED` or `UNVERIFIABLE` and therefore requires
re-establishment before ordinary reuse.

## Evidence and bounded-retrieval terms

**Observation** — Immutable admitted evidence identity, such as a source
reference/content hash/range or an observed discovery-membership fingerprint.

**Continuation** — An opaque token used to retrieve the next portion of source
evidence already selected for an investigation. It is bound to that
investigation and is not a general repository cursor.

**Cursor** — An opaque position for resuming a listing operation. It is not an
evidence continuation.

**Bounds** — Explicit limits on operational work or results. Omitted or
truncated material remains visible rather than being silently treated as
complete.

**Rejection cause** — The stable public reason a caller-correctable request was
rejected, together with the action or current coordinate needed to recover when
available.

## Functional Pyramid reference terms

**Functional Pyramid participation** — A repository's explicit relationship to
a Functional Pyramid. The durable participation states are
`UNCONFIGURED`, `EXCLUDED`, or `ACTIVE`. Registration alone does not mean
participation.

**Functional Scope** — The explicitly declared portion of an ACTIVE repository
to which Functional Pyramid governance may apply.

**Functional Context** — A declared governance context whose coverage and
inheritance determine which rules apply to a software scope. Applicable contexts
compose rather than following a most-specific-wins rule.

**Functional Rule** — A stable rule identity in the Functional Pyramid graph.
The canonical rule content remains at its declared owner.

**Functional route support** — Server-derived support identifying the exact
Functional Pyramid route that governed a normative conclusion when it was
recorded. Route applicability and canonical authority content remain separate
dependencies.

## Operational and concurrency terms

**Context** — Recoverable, expiring operational investigation state that binds
an operation to repository/scope and may retain admitted evidence. It is not the
semantic understanding itself.

**Receipt** — Immutable acceptance record for a recording identity and content.
A retained receipt enables safe replay after a lost response.

**Recording identity** — The caller-owned `(repository_id, request_id)` pair
used to identify one recording decision. Reusing the identity with different
content conflicts.

**Compare-and-set** — Update only when the caller's expected version still
matches the current version, preventing silent concurrent overwrite.

**Structural evidence** — Provider-observed symbols, locations, and adjacency.
It can help investigation but grants no semantic meaning or governing authority.

## Legacy terminology

Historical exports and older evidence may contain retired claim taxonomies,
coverage-campaign terms, or suspended interpretation-continuation vocabulary.

Those terms are historical and are not the current public lifecycle. See
[Historical design references](design-references.md) when working with older
artifacts.

For exact wire-level result and carrier definitions, use the
[MCP reference](mcp.md).
