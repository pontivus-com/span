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

## Support

Source, authority, premise, and discovery dependencies use a closed tagged
union. `SupportState` is `CURRENT`, `REASSESSMENT_REQUIRED`, or `UNVERIFIABLE`.
`SupportUnavailable` is an operational qualification failure, not another
support state. Challenge states are `OPEN`, `UNRESOLVED`, and `RESOLVED`;
verification outcomes are `PASS`, `FAIL`, and `INCONCLUSIVE`.

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
