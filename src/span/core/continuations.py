"""Suspended-operation exchange record (plan §11.12).

The record is exchange state, never semantic state: it carries what one
suspended step needs to resume. It lives in the core so the service can name it
without importing the shell that stores it.
"""

from __future__ import annotations

from dataclasses import dataclass as _dataclass
from dataclasses import field as _field

from span.core.model.claims import RelationshipKind
from span.core.model.exchange import (
    EvidenceDependency,
    SemanticInterpretationRequest,
)
from span.core.model.primitives import (
    ClaimRef,
    EvidenceRef,
    EvidenceScope,
    QueryBounds,
    RelationshipRef,
    Subject,
    SubjectId,
    SubjectResolution,
)
from span.core.model.repository import RepositoryState
from span.core.model.semantics import (
    SemanticQuestionScope,
    SemanticQuestionSelection,
)
from span.core.model.targets import TargetId

__all__ = ["SuspendedOperation"]


@_dataclass(frozen=True)
class SuspendedOperation:
    """Record of one suspended indexing step (exchange state, not semantics)."""

    op: str
    repository_id: str
    subject: Subject
    request: SemanticInterpretationRequest
    bounds: QueryBounds
    state: RepositoryState
    scope: tuple[Subject, ...] = ()
    remaining: tuple[Subject, ...] = ()
    changed: tuple[EvidenceDependency, ...] = ()
    resolution: SubjectResolution | None = None
    fingerprints: tuple[tuple[str, str], ...] = ()
    known_subject_ids: tuple[SubjectId, ...] = ()
    seeds: tuple[EvidenceRef, ...] = ()
    # Frontier subjects already suspended, as full canonical identities:
    # two distinct SubjectIds never suppress each other even when they
    # share a locator string.
    suspended: tuple[SubjectId, ...] = ()
    change_kind: str | None = None
    change_description: str | None = None
    affected_assertions: tuple[ClaimRef | RelationshipRef, ...] = ()
    operation_intent: str = "EXPLAIN"
    objective: str = ""
    question_slice: str = ""
    declared_complete: bool = False
    trace_direction: str | None = None
    trace_filter: tuple[RelationshipKind, ...] = ()
    trace_filter_set: bool = False
    trace_boundary: bool = False
    establish_baseline: bool = False
    target_scope: EvidenceScope = _field(default_factory=EvidenceScope)
    target_id: TargetId | None = None
    root_question: SemanticQuestionScope | None = None
    question_selection: SemanticQuestionSelection | None = None

    def __post_init__(self) -> None:
        if self.op not in (
            "explain",
            "authority",
            "refresh",
            "trace",
            "impact",
            "initialize_target",
        ):
            raise ValueError(f"unknown suspended op: {self.op}")
