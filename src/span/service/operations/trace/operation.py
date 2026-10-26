"""Span service trace operation (plan §11.6; v0.6 §14 Amendment A-01).

Bounded structural-semantic traversal with resume. Verbatim from
``span.service_operations``; only the module path changed.
"""

from __future__ import annotations


from span.core import answers as _answers
from span.core import model as m
from span.core import requirements as _requirements
from span.ports.evidence import EvidenceSource
from span.ports.interpretation import PendingInterpretation
from span.ports.store import SemanticStore
from span.ports.structural import StructuralDirection
from span.ports.structural import StructuralSource
from span.ports.continuation import ContinuationPort
from span.core.continuations import SuspendedOperation

from span.service.answers import (
    _answer_id,
    ANSWER_ASSEMBLER,
)
from span.service.bounds import (
    resolve_bounds as _resolve_bounds,
)
from span.service.repository import (
    _is_initialized,
    _uninitialized_answer,
)
from span.service.requests import (
    SemanticTraceRequest,
)
from span.service.resolution import (
    _has_established_semantic_state,
    _resolve_contextual_subjects,
    _resolve_query_subject,
)


from span.service.operations.trace.drive import (
    _trace_drive,
)


def trace(
    request: SemanticTraceRequest,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationPort,
    authority_seeds: tuple[m.EvidenceRef, ...] = (),
) -> m.SemanticAnswer | PendingInterpretation:
    """Context operation (plan §11.6): producers/carriers/consumers,
    explicit semantic-vs-structural path segments, boundary crossings,
    representations/contracts, transformation owners, lifecycle
    transitions and persistence points. Structural paths stay possible
    routes — never runtime facts or authority. Suspends via §11.12 when
    frontier interpretation is missing; never interprets inline.

    Paging (plan I-39): `page_token` windows the target subject's
    initial state load only; frontier expansion loads proceed unpaged.
    Page deep results through narrower targets."""
    bounds = _resolve_bounds(request.bounds, hook=False)
    state = structural.repository_state(request.repository_id)
    if not _is_initialized(request.repository_id, store=store):
        return _uninitialized_answer(
            m.SemanticIntent.TRACE, request.repository_id, bounds, state
        )
    resolution = _resolve_query_subject(
        request.repository_id,
        request.target,
        structural=structural,
        store=store,
        bounds=bounds,
    )
    if request.target.exact_subject_id is None:
        use_direct = False
        if resolution.ambiguity is m.ResolutionAmbiguity.RESOLVED:
            if resolution.candidates and _has_established_semantic_state(
                request.repository_id,
                resolution.candidates[0].subject,
                store=store,
                bounds=bounds,
            ):
                use_direct = True
        elif resolution.ambiguity is m.ResolutionAmbiguity.AMBIGUOUS:
            for candidate in resolution.candidates:
                if _has_established_semantic_state(
                    request.repository_id,
                    candidate.subject,
                    store=store,
                    bounds=bounds,
                ):
                    use_direct = True
                    break
        if not use_direct:
            _, trace_root = _resolve_contextual_subjects(
                request.repository_id,
                request.target,
                structural=structural,
                evidence=evidence,
                store=store,
                bounds=bounds,
            )
            if trace_root.ambiguity is not m.ResolutionAmbiguity.NOT_FOUND:
                resolution = trace_root
    if resolution.ambiguity is not m.ResolutionAmbiguity.RESOLVED:
        requirements = _answers.requirements_for_resolution(
            resolution,
            repository_id=request.repository_id,
            name_or_locator=request.target.name_or_locator,
        )
        if (
            resolution.ambiguity is m.ResolutionAmbiguity.AMBIGUOUS
            and resolution.bound_info.truncated
            and resolution.bound_info.truncated_category in ("inventory", "context")
        ):
            requirements = requirements + (
                _requirements.incomplete_scope(
                    subject_or_claim=None,
                    description=(
                        "path context not completely examined within "
                        "bounds; narrow the path or raise bounds"
                    ),
                    supporting_context=(),
                ),
            )
        return ANSWER_ASSEMBLER.build(
            answer_id=_answer_id(
                "trc",
                request.repository_id,
                request.target.name_or_locator or "unknown",
            ),
            intent=m.SemanticIntent.TRACE,
            repository_state=state,
            subject_resolution=resolution,
            content=m.TraceContent(),
            evidence=(),
            resolution_requirements=requirements,
            bounds=bounds,
            withheld_category=None,
            continuation_token=None,
        )
    return _trace_drive(
        request.repository_id,
        resolution.candidates[0].subject,
        resolution,
        structural=structural,
        evidence=evidence,
        store=store,
        continuations=continuations,
        bounds=bounds,
        state=state,
        direction=request.direction,
        relationship_filter=request.relationship_filter,
        boundary_only=request.boundary_only,
        seeds=authority_seeds,
        suspended=(),
        page_token=request.page_token,
        question_selection=request.question_selection,
        root_subject=resolution.candidates[0].subject.subject_id,
    )


def _resume_trace(
    record: SuspendedOperation,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    continuations: ContinuationPort,
) -> m.SemanticAnswer | PendingInterpretation:
    target = record.scope[0] if record.scope else record.subject
    resumed = record.suspended
    if record.subject.subject_id not in resumed:
        resumed = resumed + (record.subject.subject_id,)
    return _trace_drive(
        record.repository_id,
        target,
        record.resolution,
        structural=structural,
        evidence=evidence,
        store=store,
        continuations=continuations,
        bounds=bounds,
        state=state,
        direction=StructuralDirection(record.trace_direction or "BOTH"),
        relationship_filter=(record.trace_filter if record.trace_filter_set else None),
        boundary_only=record.trace_boundary,
        seeds=record.seeds,
        suspended=resumed,
        question_selection=record.question_selection,
        root_subject=(
            record.root_question.scope_root
            if record.root_question is not None
            else target.subject_id
        ),
    )
