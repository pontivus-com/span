"""Live interpretation exchange projected against persisted question identity."""

from __future__ import annotations

import dataclasses as _dataclasses

from span.core import model as m
from span.core.continuations import SuspendedOperation
from span.ports.continuation import ContinuationPort

from span.service.questions.slices import _question_identity_key


def _record_matches(
    record: SuspendedOperation,
    scope: m.SemanticQuestionScope,
) -> bool:
    """Whether one live unit is bound to the same persisted question identity."""
    question = record.request.question
    if question is None:
        return False
    if record.repository_id != scope.scope_root.repository_id:
        return False
    return _question_identity_key(question) == _question_identity_key(scope)


def match_live_question(
    records: tuple[SuspendedOperation, ...],
    scope: m.SemanticQuestionScope,
) -> SuspendedOperation | None:
    """Return the first live unit bound to one question identity, if any."""
    for record in records:
        if _record_matches(record, scope):
            return record
    return None


def live_question_records(
    scope: m.SemanticQuestionScope,
    continuations: ContinuationPort,
) -> tuple[SuspendedOperation, ...]:
    """Every live unit bound to one question identity."""
    return tuple(
        record
        for record in continuations.live_records()
        if _record_matches(record, scope)
    )


def live_question_record(
    scope: m.SemanticQuestionScope,
    continuations: ContinuationPort,
) -> SuspendedOperation | None:
    """The first live unit bound to one question identity, if any."""
    return match_live_question(continuations.live_records(), scope)


def _unexamined(coverage: m.InterpretationCoverage | None) -> bool:
    """Whether persisted coverage still needs its first interpretation unit."""
    return coverage is None or coverage.disposition is (
        m.SemanticQuestionDisposition.PENDING
    )


def live_owns_question(
    coverage: m.InterpretationCoverage | None,
    live: SuspendedOperation | None,
) -> bool:
    """Whether the live unit, not persisted coverage, owns first examination."""
    return live is not None and _unexamined(coverage)


def needs_first_examination(
    coverage: m.InterpretationCoverage | None,
    live: SuspendedOperation | None,
) -> bool:
    """Whether a question needs a new interpretation unit.

    A persisted PENDING row is admitted but unexamined. A live exchange for
    the same identity owns that first examination already, so re-entry must
    not mint a second continuation.
    """
    return _unexamined(coverage) and live is None


def live_question_requirement(
    record: SuspendedOperation,
) -> m.ResolutionRequirement:
    """Describe a live question without exposing its continuation token."""
    question = record.request.question
    if question is None:
        raise ValueError("live question requirement requires a bound question")
    scope_root = (
        f"{question.scope_root.subject_kind.value}:"
        f"{question.scope_root.canonical_locator}"
    )
    return m.ResolutionRequirement(
        kind=m.ResolutionKind.INCOMPLETE_SEMANTIC_SCOPE,
        subject_or_claim=question.subject,
        description=(
            f"{question.question_class.value} '{question.question_slice}' "
            f"under scope root '{scope_root}' for "
            f"'{question.subject.canonical_locator}' has a live "
            f"{record.op} interpretation unit; continue with the "
            f"continuation returned by that {record.op} call and pass it "
            "unchanged"
        ),
        supporting_context=(),
    )


def with_live_question_requirements(
    answer: m.SemanticAnswer,
    records: tuple[SuspendedOperation, ...],
) -> m.SemanticAnswer:
    """Attach one requirement per live unit already bound to the question."""
    if not records:
        return answer
    return _dataclasses.replace(
        answer,
        resolution_requirements=(
            *answer.resolution_requirements,
            *(live_question_requirement(record) for record in records),
        ),
    )


def with_live_question_requirement(
    answer: m.SemanticAnswer,
    coverage: m.InterpretationCoverage | None,
    live: SuspendedOperation | None,
) -> m.SemanticAnswer:
    """Attach the live requirement when the live unit owns first examination."""
    if live is None or not live_owns_question(coverage, live):
        return answer
    return with_live_question_requirements(answer, (live,))
