"""Suspension and the baseline frontier."""

from __future__ import annotations


from span.core import model as m
from span.ports.interpretation import PendingInterpretation
from span.ports.continuation import ContinuationPort
from span.core.continuations import SuspendedOperation

from span.service.interpretation.task import InterpretationTask


def _suspend(
    *,
    op: str,
    repository_id: str,
    subject: m.Subject,
    task: InterpretationTask,
    seeds: tuple[m.EvidenceRef, ...],
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    resolution: m.SubjectResolution | None,
    scope: tuple[m.Subject, ...] = (),
    remaining: tuple[m.Subject, ...] = (),
    changed: tuple[m.EvidenceDependency, ...] = (),
    suspended: tuple[m.SubjectId, ...] = (),
    change_kind: str | None = None,
    change_description: str | None = None,
    affected_assertions: tuple[m.ClaimRef | m.RelationshipRef, ...] = (),
    operation_intent: str = "EXPLAIN",
    question_slice: str = "",
    trace_direction: str | None = None,
    trace_filter: tuple[m.RelationshipKind, ...] = (),
    trace_filter_set: bool = False,
    trace_boundary: bool = False,
    continuations: ContinuationPort,
    establish_baseline: bool = False,
    objective: str = "",
    target_scope: m.EvidenceScope = m.EvidenceScope(),
    target_id: m.TargetId | None = None,
    root_question: m.SemanticQuestionScope | None = None,
    question_selection: m.SemanticQuestionSelection | None = None,
) -> PendingInterpretation:
    token = continuations.pend(
        SuspendedOperation(
            op=op,
            repository_id=repository_id,
            subject=subject,
            scope=scope,
            remaining=remaining,
            changed=changed,
            resolution=resolution,
            request=task.request,
            fingerprints=task.fingerprints,
            known_subject_ids=task.known_subject_ids,
            seeds=seeds,
            bounds=bounds,
            state=state,
            suspended=suspended,
            change_kind=change_kind,
            change_description=change_description,
            affected_assertions=affected_assertions,
            operation_intent=operation_intent,
            objective=objective,
            question_slice=question_slice,
            trace_direction=trace_direction,
            trace_filter=trace_filter,
            trace_filter_set=trace_filter_set,
            trace_boundary=trace_boundary,
            establish_baseline=establish_baseline,
            target_scope=target_scope,
            target_id=target_id,
            root_question=root_question,
            question_selection=question_selection,
        )
    )
    return PendingInterpretation(continuation=token, request=task.request)
