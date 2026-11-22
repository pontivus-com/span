# Lifecycle vocabulary

Canonical carriers are exported from `span.core.model`; reference-only record
wire contracts live in `span.core.schema.record_wire`. The installed schemas
and [MCP reference](mcp.md) define the executable public grammar.

## Understandings and conclusions

| Carrier | Meaning |
| --- | --- |
| `Understanding` | Stable repository-bound identity, question, scope, and current version pointer. |
| `UnderstandingVersion` | Immutable full membership of exact conclusion revisions, with gaps and predecessor. |
| `ConclusionRevision` | Immutable revision in a conclusion lineage, with content and basis. |
| `SupportedConclusion` | Statement, descriptive/normative assertion nature, scope, and declared support. |
| `WithdrawnConclusion` | Explicit reason for withdrawal, preserving earlier content in history. |
| `Gap` | Unanswered question and its basis within a version. |
| `Challenge` | Explicit dispute with its own revision and disposition history. |

Conclusion revisions and understanding versions are different counters.
An update preserves unmentioned membership and challenges. Replacement and
withdrawal are explicit operations, not omission-based deletion.

## Result composition carriers

| Carrier | Meaning |
| --- | --- |
| `HistoricalConclusion` | Non-current conclusion content returned in an ask `Gap`: exact revision, understanding version, statement, evidence references, and present non-current state. |
| `StaleConclusionRef` | Exact stale revision reference in a surface status: revision identity, understanding version, and present non-current state. |

These are read-time projections over stored revisions. They are not a second
stored shape; historical content never becomes current answer content.

## Support

Source, authority, premise, discovery, and Functional Pyramid route dependencies
use one closed tagged union. `FunctionalRouteSupport` is the route branch;
canonical rule currency remains an authority dependency. `SupportState` is
`CURRENT`, `REASSESSMENT_REQUIRED`, or `UNVERIFIABLE`.
`SupportUnavailable` is an operational qualification failure, not another
support state. Challenge states are `OPEN`, `UNRESOLVED`, and `RESOLVED`;
verification outcomes are `PASS`, `FAIL`, and `INCONCLUSIVE`.

## Functional Pyramid

| Carrier | Meaning |
| --- | --- |
| `FunctionalPyramidParticipation` | Exact UNCONFIGURED/EXCLUDED repository participation. |
| `FunctionalPyramidStatus` | Exact participation or ACTIVE pyramid/version/member view with live health. |
| `FunctionalPyramidCandidate` | Read-only action-aware validation and graph findings for proposed participation. |
| `FunctionalPyramidView` | Governing projection for the exact semantic scope of an ordinary ask. |
| `FunctionalRouteSupport` | Server-derived dependency on the exact resolved governing route for a NORMATIVE conclusion. |
| `FunctionalPyramidRecorded` | Accepted activate/revise/deactivate/exclude result with immutable receipt selector and live affected projection. |
| `RetrievedFunctionalPyramidReceipt` | Exact installation-scoped accepted participation/effect identities; live context state is not stored in the receipt. |

Functional Pyramid lifecycle branches are carried through the existing
`ask`, `record`, and `reconsider` operations. They do not create a fourth MCP
tool or a second ordinary-development lifecycle.

## Operational carriers

Contexts bind caller request identity to repository, question/scope, origin,
and expiry. Sources are admitted as immutable observations with per-item
outcomes. Recording identities and receipts support retry/restart recovery.
Discovery candidates and compact references indicate potentially reusable
understanding, never an asserted semantic answer. See [glossary](glossary.md).

## Structural identities

`SubjectId` remains a typed repository/kind/locator identity for structural
navigation. Provider nodes map through a closed vocabulary: files/modules to
components; functions, classes, methods, interfaces, types, enums, structs,
and constants to code symbols. Structural edges describe defines, imports,
calls, references, and dependencies. Unknown provider kinds fail explicitly.
A module node does not establish a semantic subsystem or owner.

The old mandatory claim kinds, semantic-question classes, subject coverage
statuses, campaigns, and interpretation continuations are retired from the
active lifecycle. Retained model definitions and archived data do not add
public operations or a second semantic writer.
