"""Span service refresh operation (plan §9; v0.6 §14 Amendment A-01).

Explicit reassessment of stale/unverifiable semantics. Verbatim from
``span.service_operations``; only the module path changed.
"""

from __future__ import annotations


from span.core import model as m
from span.core import requirements as _requirements
from span.ports.evidence import EvidenceSource
from span.ports.interpretation import PendingInterpretation
from span.ports.store import SemanticStore
from span.ports.structural import StructuralSource
from span.ports.continuation import ContinuationPort
from span.core.continuations import RefreshSnapshot

from span.service.bounds import (
    resolve_bounds as _resolve_bounds,
)
from span.service.interpretation import (
    _suspend,
    prepare_interpretation_task,
)
from span.service.questions import (
    _stale_question_scopes,
)
from span.service.repository import (
    _is_initialized,
    _uninitialized_answer,
)
from span.service.requests import (
    SemanticRefreshRequest,
)


from span.service.operations.refresh.answer import (
    _compose_refresh_answer,
)


from span.service.operations.refresh.scan import (
    _bind_correction_brief,
    _collect_refresh_scope,
    _correction_candidates,
    _resolve_refresh_subjects,
    _unresolved_refresh_answer,
)


def refresh(
    request: SemanticRefreshRequest,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationPort,
    authority_seeds: tuple[m.EvidenceRef, ...] = (),
) -> m.SemanticAnswer | PendingInterpretation:
    """Explicit synchronization (plan §9.5, [design note B](docs/design-references.md#b) B-06).

    Identifies stale/unverifiable dependencies — including semantic
    premise dependents via the reverse lookup — and reinterprets only
    affected semantic units. Never expands into a baseline audit.
    """
    bounds = _resolve_bounds(request.bounds, hook=False)
    state = structural.repository_state(request.repository_id)
    if not _is_initialized(request.repository_id, store=store):
        return _uninitialized_answer(
            m.SemanticIntent.STATUS, request.repository_id, bounds, state
        )
    subjects, resolution, ambiguity = _resolve_refresh_subjects(
        request,
        structural=structural,
        evidence=evidence,
        store=store,
        bounds=bounds,
    )
    if ambiguity is not m.ResolutionAmbiguity.RESOLVED or not subjects:
        return _unresolved_refresh_answer(
            request.repository_id,
            request.target,
            resolution,
            state=state,
            bounds=bounds,
        )
    scan = _collect_refresh_scope(
        request,
        subjects,
        structural=structural,
        evidence=evidence,
        store=store,
        bounds=bounds,
        continuations=continuations,
    )
    if not scan.affected:
        missing = tuple(
            _requirements.missing_semantic_coverage(
                subject_or_claim=subject.subject_id,
                description=(
                    "no adopted question coverage is persisted for this "
                    f"semantic subject; run question-local explain for "
                    f"'{subject.subject_id.canonical_locator}'"
                ),
                supporting_context=(),
            )
            for subject in scan.unassessed
        )
        return _compose_refresh_answer(
            request.repository_id,
            subjects,
            structural=structural,
            evidence=evidence,
            store=store,
            bounds=bounds,
            state=state,
            changed=tuple(scan.changed),
            extra_unresolved=tuple(scan.currency_notes) + missing,
        )
    first, rest = scan.affected[0], scan.affected[1:]
    # B.3/B-06: refresh re-examines under the persisted stale question scope —
    # never a fresh generic question and never a silent baseline expansion.
    # Unassessed subjects were excluded above.
    first_stale = _stale_question_scopes(
        request.repository_id,
        first,
        store=store,
        evidence=evidence,
        bounds=bounds,
        suspended=continuations.live_question_keys(),
    )
    first_scope = first_stale[0] if first_stale else None
    correction_candidates: tuple[m.SemanticQuestionScope, ...] = ()
    if first_scope is None and not request.stale_only:
        correction_candidates = _correction_candidates(
            request,
            first,
            store=store,
        )
    task = prepare_interpretation_task(
        request.repository_id,
        first,
        structural=structural,
        evidence=evidence,
        bounds=bounds,
        state=state,
        authority_seeds=authority_seeds,
        operation_intent=m.SemanticIntent.STATUS,
        question_slice=(
            first_scope.question_slice
            if first_scope is not None
            else first.subject_id.canonical_locator
        ),
        store=store,
        scope_root=(
            first_scope.scope_root if first_scope is not None else first.subject_id
        ),
        question_class=(
            first_scope.question_class if first_scope is not None else None
        ),
        materiality_basis=(
            first_scope.materiality_basis if first_scope is not None else ""
        ),
    )
    if correction_candidates:
        task = _bind_correction_brief(task, correction_candidates)
    return _suspend(
        op="refresh",
        repository_id=request.repository_id,
        subject=first,
        task=task,
        seeds=authority_seeds,
        bounds=bounds,
        state=state,
        resolution=None,
        scope=subjects,
        remaining=tuple(rest),
        changed=tuple(scan.changed),
        continuations=continuations,
        operation_intent="STATUS",
        question_slice=task.request.question_slice,
        refresh=RefreshSnapshot(
            eligible=tuple(first_stale),
            attempted=(first_stale[0],) if first_stale else (),
        ),
    )
