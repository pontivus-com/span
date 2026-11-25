# Lifecycle vocabulary

Canonical lifecycle carriers are exported from `span.core.model`.
Reference-only public record wire contracts live in
`span.core.schema.record_wire`.

The installed schemas and [MCP reference](mcp.md) own executable public grammar.

## Understandings and conclusions

| Carrier | Meaning |
| --- | --- |
| `Understanding` | Stable repository-bound semantic identity, question, scope, surface, and current-version pointer. |
| `UnderstandingVersion` | Immutable complete membership snapshot of exact conclusion revisions plus recorded question gaps. |
| `ConclusionRevision` | One immutable revision in a conclusion lineage. |
| `SupportedConclusion` | Agent-authored statement with assertion nature, semantic scope, and declared support. |
| `WithdrawnConclusion` | Explicit withdrawal preserving history rather than deleting the old lineage. |
| `RecordedQuestionGap` | Explicit unresolved question retained in a version. |
| `Challenge` | Explicit semantic dispute with its own revision/disposition history. |

Conclusion revisions and understanding versions are separate counters.

Updates preserve unmentioned membership. Replacement and withdrawal are explicit
semantic operations, not omission-based deletion.

## Capture and curation

Beta 3 separates evidence-near capture from qualification for shared reuse.

| Carrier | Meaning |
| --- | --- |
| `CurationState` | Derived reuse maturity for one exact semantic revision: `CAPTURED` or `CURATED`. |
| `CurationDisposition` | Immutable accepted curation decision for one exact conclusion revision. |
| `CurationOrigin` | How the disposition was established: explicit review or inherited confirmation. |
| `PendingCurationSelector` | Select the deterministic repository-local queue of current captures awaiting review. |
| `PendingCurationItem` | One exact current-membership captured revision awaiting review. |
| `PendingCuration` | One bounded deterministic page of pending-curation references. |

`CAPTURED` means the semantic revision is retained but has no accepted
shared-reuse disposition.

`CURATED` means an immutable curation disposition exists for that exact
revision. Curation does not substitute for support currency, evidence,
governing authority, or challenge settlement.

A semantic create/add/correct/replace produces captured meaning. A
semantic-preserving confirmation may inherit curation only through the explicit
Beta-3 inheritance rule.

## Result-composition carriers

| Carrier | Meaning |
| --- | --- |
| `HistoricalConclusion` | Non-current retained conclusion content projected in a Gap/history path. |
| `StaleConclusionRef` | Exact stale revision reference projected in surface status without carrying statement content. |

These are read-time projections over canonical stored state, not second
persistence models.

Historical content never becomes current Answer content merely because it is
retrieved.

## Support

Source, authority, premise, discovery, and Functional Pyramid route dependencies
form one closed support union.

`FunctionalRouteSupport` is the route-dependency branch; canonical governing
content remains independently represented by authority support.

`SupportState` is exactly:

- `CURRENT`;
- `REASSESSMENT_REQUIRED`; or
- `UNVERIFIABLE`.

`SupportUnavailable` is operational inability to qualify support, not a fourth
support state.

Challenge states are `OPEN`, `UNRESOLVED`, and `RESOLVED`.
Verification outcomes are `PASS`, `FAIL`, and `INCONCLUSIVE`.

## Functional Pyramid

| Carrier | Meaning |
| --- | --- |
| `FunctionalPyramidParticipation` | Repository participation outside an active instance: UNCONFIGURED/EXCLUDED state. |
| `FunctionalPyramidStatus` | Exact participation or ACTIVE pyramid/version/member projection with live health. |
| `FunctionalPyramidCandidate` | Read-only validation/findings for a proposed activation or revision. |
| `FunctionalPyramidView` | Governing projection for the exact semantic scope or directory of an ordinary ask, including declared and absent layers. |
| `FunctionalDocumentPlacement` | Canonical document reference declared at one layer for one repository-relative directory scope in one declaring repository. |
| `FunctionalRouteSupport` | Server-derived dependency on the resolved governing route for a normative conclusion. |
| `FunctionalPyramidRecorded` | Accepted participation lifecycle result with immutable receipt selector and affected projection. |
| `RetrievedFunctionalPyramidReceipt` | Exact installation-scoped accepted participation/effect identities. |

Functional Pyramid lifecycle branches remain inside the existing `ask`,
`record`, and `reconsider` operations. They do not create a fourth MCP
tool.

## Operational carriers

Investigation contexts bind operational request identity to repository/scope and
may retain admitted evidence. They are recoverable and expiring operational
state, not semantic understanding.

Recording identities and receipts support retry/restart recovery.

Exact selectors retrieve current membership, historical snapshots, receipts, or
pending-curation references without converting them into ordinary shared
Answers.

See [Glossary](glossary.md) for the user-facing terminology and
[MCP reference](mcp.md) for public selector/result grammar.

## Structural identities

`SubjectId` remains the typed repository/kind/locator identity used for
structural navigation.

Provider nodes map through the closed structural vocabulary. Structural edges
describe relationships such as defines, imports, calls, references, and
dependencies.

Unknown provider kinds fail explicitly.

A structural node does not establish semantic subsystem ownership or governing
authority.

## Legacy vocabulary

Older retained data or exports may still contain retired claim kinds, semantic
question classes, coverage-campaign vocabulary, or historical interpretation
continuations.

Those retained definitions do not add current public operations, lifecycle
states, or a second semantic writer.

See [Historical design references](design-references.md) when tracing those
older terms.
