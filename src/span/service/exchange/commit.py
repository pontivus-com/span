"""Materialize one prepared submission under single-commit ownership."""

from __future__ import annotations

from span.core import model as m
from span.ports.evidence import EvidenceSource
from span.ports.interpretation import InterpretationUnavailable
from span.ports.store import SemanticStore
from span.ports.continuation import ContinuationPort
from span.core.continuations import SuspendedOperation

from span.service.discovery import (
    _coverage_for_task,
)
from span.service.interpretation import (
    _materialize_unit,
)

from span.service.exchange.prepare import _PreparedSubmission


def _exact_target(operation: SuspendedOperation) -> m.SubjectSelector:
    """Name the admitted subject exactly, so re-issue binds the same identity."""
    return m.SubjectSelector(exact_subject_id=operation.subject.subject_id)


def _admitted_recovery(operation: SuspendedOperation) -> m.QuestionRecovery | None:
    """The recovery inputs the admitting operation can vouch for.

    Only operations that recreate the question from their own resolved inputs
    carry a recipe. ``refresh`` re-binds the persisted identity and
    ``initialize_target`` recovers from its durable target association, so
    both return ``None``; an existing question keeps its stored recipe.
    """
    if operation.op == "explain":
        return m.ExplainReplay(
            target=_exact_target(operation),
            bounds=operation.bounds,
            establish_baseline=operation.establish_baseline,
            question_selection=operation.question_selection,
        )
    if operation.op == "impact":
        if operation.change_kind is None:
            raise AssertionError("impact suspension without change_kind")
        return m.ImpactReplay(
            target=_exact_target(operation),
            proposed_change=m.ProposedChange(
                change_kind=m.ChangeKind(operation.change_kind),
                change_description=operation.change_description,
                affected_assertions=operation.affected_assertions,
            ),
            bounds=operation.bounds,
            question_selection=operation.question_selection,
        )
    if operation.op == "trace":
        if operation.trace_direction is None:
            raise AssertionError("trace suspension without trace_direction")
        return m.TraceReplay(
            target=_exact_target(operation),
            bounds=operation.bounds,
            direction=m.StructuralDirection(operation.trace_direction),
            relationship_filter=(
                operation.trace_filter if operation.trace_filter_set else None
            ),
            boundary_only=operation.trace_boundary,
            question_selection=operation.question_selection,
        )
    if operation.op == "authority":
        return m.AuthorityReplay(
            target=_exact_target(operation),
            bounds=operation.bounds,
            question_selection=operation.question_selection,
        )
    return None


def _commit_prepared(
    continuation: str,
    prepared: _PreparedSubmission,
    result: m.SemanticInterpretationResult,
    *,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationPort,
) -> SuspendedOperation:
    """Materialize the unit under single-commit ownership, then consume it.

    Ownership is acquired only here, for the commit-critical section.
    From here to the claim is release-on-failure; only the claim path leaves
    non-live. A successful commit consumes the token exactly once, before the
    answer/next pending is exposed, so post-commit composition failure
    recovers via idempotent original-operation re-issue.
    """
    acquired = continuations.acquire(continuation)
    if acquired is None:
        raise InterpretationUnavailable(
            f"unknown, expired, or in-flight continuation: {continuation}. Re-run the original operation; this token cannot be recovered."
        )
    task = prepared.task
    try:
        _materialize_unit(
            task,
            result,
            store=store,
            evidence=evidence,
            state=prepared.state,
            extra_known_subjects=prepared.extra_known,
            coverage=_coverage_for_task(
                acquired.repository_id,
                tuple(subject.subject_id for subject in task.request.subjects),
                evidence=evidence,
                seeds=acquired.seeds,
                question=task.request.question,
                discovery_scope=task.request.discovery_scope,
            ),
            retire_scope=tuple(subject.subject_id for subject in task.request.subjects),
            target_id=prepared.target.target_id,
            target_association=prepared.target.association,
            current_inventory_ids=prepared.target.inventory_ids,
            current_inventory_snapshot=prepared.target.inventory_snapshot,
            correction_question=prepared.correction_question,
            recovery=_admitted_recovery(acquired),
        )
    except BaseException:
        continuations.release(continuation)
        raise
    continuations.claim(continuation)
    return acquired
