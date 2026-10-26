"""Span service impact operation (plan §11.5; v0.6 §14 Amendment A-01).

Change-condition derivation and impact answers. Verbatim from
``span.service_operations``; only the module path changed.
"""

from __future__ import annotations


from span.core import answers as _answers
from span.core import model as m
from span.ports.evidence import EvidenceSource
from span.ports.interpretation import PendingInterpretation
from span.ports.store import SemanticStore
from span.ports.structural import StructuralSource
from span.ports.continuation import ContinuationPort

from span.service.answers import (
    _answer_id,
    ANSWER_ASSEMBLER,
)
from span.service.bounds import (
    resolve_bounds as _resolve_bounds,
)
from span.service.interpretation import (
    _suspend,
    prepare_interpretation_task,
)
from span.service.questions import (
    derive_service_question,
    effective_impact_slice,
)
from span.service.repository import (
    _is_initialized,
    _uninitialized_answer,
)
from span.service.requests import (
    ChangeKind,
    SemanticImpactRequest,
)
from span.service.operations.impact.answer import _compose_impact_answer
from span.service.resolution import (
    _resolve_query_subject,
)


def impact(
    request: SemanticImpactRequest,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationPort,
    authority_seeds: tuple[m.EvidenceRef, ...] = (),
) -> m.SemanticAnswer | PendingInterpretation:
    """Pre-change semantic brief (plan §11.5, task 3.8).

    Composes already-established CQ/F information for a proposed
    material change: identity/purpose/responsibility, owner/custodian,
    governing authority and invariants, boundary/representation context,
    derived ChangeConditions (§11.5.1), established vs structural-only
    downstream impacts, verification currency, conflicts/staleness, and
    requirements. Suspends via §11.12 when interpretation is missing;
    never interprets inline, never invents authority or severity.

    Paging (plan I-39): `page_token` windows the target subject's
    initial state load only; downstream node loads proceed unpaged.
    Page deep results through narrower targets.
    """
    bounds = _resolve_bounds(request.bounds, hook=False)
    state = structural.repository_state(request.repository_id)
    if not _is_initialized(request.repository_id, store=store):
        return _uninitialized_answer(
            m.SemanticIntent.IMPACT, request.repository_id, bounds, state
        )
    resolution = _resolve_query_subject(
        request.repository_id,
        request.target,
        structural=structural,
        store=store,
        bounds=bounds,
    )
    if resolution.ambiguity is not m.ResolutionAmbiguity.RESOLVED:
        return _unresolved_impact_answer(
            request.repository_id,
            request.target.name_or_locator,
            resolution,
            state=state,
            bounds=bounds,
        )
    if request.change_kind is ChangeKind.OTHER and not request.change_description:
        raise ValueError("change_kind OTHER requires a change_description (§11.10)")
    # S4 §5.4 IMPACT discriminator: different change proposals never
    # share one persisted identity — for explicit AND default questions.
    # Host slice/basis/anchors only; service derives root/subject/class.
    _sel_scope, _sel_anchors = derive_service_question(
        subject=resolution.candidates[0].subject,
        scope_root=resolution.candidates[0].subject.subject_id,
        question_class=m.SemanticQuestionClass.CQ_08,
        selection=request.question_selection,
        default_slice=m.QUESTION_CLASS_DEFAULT_SLICE[m.SemanticQuestionClass.CQ_08],
        default_basis="IMPACT question-local",
    )
    _eff_slice = effective_impact_slice(
        _sel_scope.question_slice,
        request.change_kind,
        request.change_description,
        request.affected_assertions,
    )
    _eff_scope = m.SemanticQuestionScope(
        scope_root=_sel_scope.scope_root,
        subject=_sel_scope.subject,
        question_class=_sel_scope.question_class,
        question_slice=_eff_slice,
        materiality_basis=_sel_scope.materiality_basis,
    )
    try:
        _existing = store.load_all_question_coverages(
            request.repository_id,
            _eff_scope.scope_root,
            (_eff_scope.subject,),
        )
    except Exception:
        _existing = ()
    _found = any(
        _c.question is not None
        and _c.question.scope_root == _eff_scope.scope_root
        and _c.question.subject == _eff_scope.subject
        and _c.question.question_class == _eff_scope.question_class
        and _c.question.question_slice == _eff_scope.question_slice
        for _c in _existing
    )
    if not _found:
        return _suspend_first_impact_unit(
            request,
            resolution.candidates[0].subject,
            resolution,
            _eff_scope,
            _sel_anchors,
            structural=structural,
            evidence=evidence,
            store=store,
            bounds=bounds,
            state=state,
            authority_seeds=authority_seeds,
            continuations=continuations,
        )
    return _compose_impact_answer(
        request.repository_id,
        resolution.candidates[0].subject,
        resolution,
        structural=structural,
        evidence=evidence,
        store=store,
        continuations=continuations,
        bounds=bounds,
        state=state,
        change_kind=request.change_kind,
        change_description=request.change_description,
        affected_assertions=request.affected_assertions,
        seeds=authority_seeds,
        suspended=(),
        page_token=request.page_token,
        question_selection=request.question_selection,
        root_question=None,
    )


def _unresolved_impact_answer(
    repository_id: str,
    name_or_locator: str | None,
    resolution: m.SubjectResolution,
    *,
    state: m.RepositoryState,
    bounds: m.QueryBounds,
) -> m.SemanticAnswer:
    """The answer when the requested change target does not resolve."""
    requirements = _answers.requirements_for_resolution(
        resolution,
        repository_id=repository_id,
        name_or_locator=name_or_locator,
    )
    return ANSWER_ASSEMBLER.build(
        answer_id=_answer_id("imp", repository_id, name_or_locator or "unknown"),
        intent=m.SemanticIntent.IMPACT,
        repository_state=state,
        subject_resolution=resolution,
        content=m.ImpactContent(),
        evidence=(),
        resolution_requirements=requirements,
        bounds=bounds,
        withheld_category=None,
        continuation_token=None,
    )


def _suspend_first_impact_unit(
    request: SemanticImpactRequest,
    subject: m.Subject,
    resolution: m.SubjectResolution,
    scope: m.SemanticQuestionScope,
    anchors: tuple[str, ...],
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    authority_seeds: tuple[m.EvidenceRef, ...],
    continuations: ContinuationPort,
) -> PendingInterpretation:
    """Suspend the first unit when the discriminated question was never examined."""
    task = prepare_interpretation_task(
        request.repository_id,
        subject,
        structural=structural,
        evidence=evidence,
        bounds=bounds,
        state=state,
        authority_seeds=authority_seeds,
        operation_intent=m.SemanticIntent.IMPACT,
        question_slice=scope.question_slice,
        proposed_change=m.ProposedChange(
            change_kind=request.change_kind,
            change_description=request.change_description,
            affected_assertions=request.affected_assertions,
        ),
        store=store,
        scope_root=scope.scope_root,
        question_class=scope.question_class,
        materiality_basis=scope.materiality_basis,
        question_terms=anchors,
    )
    return _suspend(
        op="impact",
        repository_id=request.repository_id,
        subject=subject,
        task=task,
        seeds=authority_seeds,
        bounds=bounds,
        state=state,
        resolution=resolution,
        scope=(subject,),
        suspended=(),
        change_kind=request.change_kind.value,
        change_description=request.change_description,
        affected_assertions=request.affected_assertions,
        operation_intent="IMPACT",
        question_slice=scope.question_slice,
        continuations=continuations,
        root_question=scope,
        question_selection=request.question_selection,
    )
