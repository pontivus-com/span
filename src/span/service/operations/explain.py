"""Span service explain operation (plan §11.4; v0.6 §14 Amendment A-01).

Bounded semantic explanation with baseline establishment. Verbatim from
``span.service_operations``; only the module path changed.
"""

from __future__ import annotations

from span.core import answers as _answers
from span.core import model as m
from span.ports.evidence import EvidenceSource
from span.ports.interpretation import PendingInterpretation
from span.ports.store import SemanticStore
from span.ports.structural import StructuralSource
from span.shell.agent_exchange.continuations import ContinuationStore

from span.service.answers import (
    _answer_id,
    _bound_info,
    _conflicts_for,
    _next_service_token,
    _query_digest,
    _validate_service_token,
    _select_answer_items,
    coverage_counts_for,
    state_explanation_for,
)
from span.service.bounds import (
    resolve_bounds as _resolve_bounds,
)
from span.service.freshness import (
    _premise_preflight,
    _refresh_view,
)
from span.service.interpretation import (
    _next_baseline_pending,
    _suspend,
    _suspend_baseline_pending,
    prepare_interpretation_task,
)
from span.service.questions import (
    _paged_question_views,
    _question_local_missing,
    effective_question_view,
)
from span.service.refs import (
    _claim_ref,
    _relationship_ref,
)
from span.service.repository import (
    _is_initialized,
    _uninitialized_answer,
)
from span.service.requests import (
    SemanticExplainRequest,
)
from span.service.resolution import (
    _has_established_semantic_state,
    _load_all_coverages_or_defer,
    _load_subject_state,
    _resolve_contextual_subjects,
    _resolve_query_subject,
)

__all__ = [
    '_baseline_sufficient',
    '_compose_explain_answer',
    'explain',
]

def _baseline_sufficient(
    repository_id: str,
    scope_root: m.SubjectId,
    *,
    store: SemanticStore,
    evidence: EvidenceSource,
    bounds: m.QueryBounds,
) -> bool:
    """Recorded scoped sufficiency for an expressly selected root (B.3.2).

    True only when: (a) all nine root CQ classes have an explicit
    applicability disposition; (b) every admitted material root/member
    question is ANSWERED or genuinely NOT_APPLICABLE with *current*
    (effective) dependencies; (c) no unresolved requirements, conflicts,
    or unassessed items remain in scope; (d) no outstanding
    pages, unexamined questions, unprocessed premise frontier, or
    stale/unverifiable items; (e) synthesis rests on established,
    currently supported member evidence. Recorded dispositions alone
    never suffice — effective currentness is recomputed.
    """
    try:
        coverages = _load_all_coverages_or_defer(
            repository_id, scope_root, (),
            store=store, bounds=bounds,
            purpose="baseline sufficiency audit",
        )
    except Exception:
        return False
    root_covs = [
        cov for cov in coverages
        if cov.question is not None and cov.question.scope_root == scope_root
    ]
    if not root_covs:
        return False
    # (a) all nine root CQ classes have an explicit disposition entry
    # on the root subject itself.
    root_classes = {
        cov.question.question_class
        for cov in root_covs
        if cov.question.subject == scope_root
    }
    if any(cls not in root_classes for cls in m.SemanticQuestionClass):
        return False
    # (b)+(d) every admitted question effective-current ANSWERED or
    # NOT_APPLICABLE; PENDING/OPEN/noncurrent/stale block sufficiency.
    for cov in root_covs:
        if cov.question is None:
            continue
        try:
            view = effective_question_view(
                cov, evidence=evidence, store=store,
                repository_id=repository_id,
            )
        except Exception:
            return False
        if view.recorded_disposition in (
            m.SemanticQuestionDisposition.PENDING,
            m.SemanticQuestionDisposition.OPEN,
        ):
            return False
        if view.effective_disposition not in (
            m.SemanticQuestionDisposition.ANSWERED,
            m.SemanticQuestionDisposition.NOT_APPLICABLE,
        ):
            return False
        if view.freshness.state is not m.FreshnessState.CURRENT:
            return False
        # (c) any open requirement (missing authority/evidence,
        # conflicts, stale premises) prevents full sufficiency.
        if view.resolution_requirements:
            return False
    # (c) no conflicts among scoped canonical items.
    try:
        scoped_subjects = tuple(
            dict.fromkeys(
                cov.question.subject for cov in root_covs
                if cov.question is not None
            )
        )
        scoped_claims: list[m.SemanticClaim] = []
        scoped_rels: list[m.SemanticRelationship] = []
        for sid in scoped_subjects:
            loaded_c, loaded_r, _, _ = _load_subject_state(
                repository_id, sid, store=store, bounds=bounds,
            )
            scoped_claims.extend(loaded_c)
            scoped_rels.extend(loaded_r)
        if _conflicts_for(
            repository_id, tuple(scoped_claims), tuple(scoped_rels),
            store=store,
        ):
            return False
        # (d) no stale/unverifiable items and no unprocessed premise
        # frontier across scoped results.
        all_refs: tuple[m.ClaimRef | m.RelationshipRef, ...] = tuple(
            _claim_ref(c) for c in scoped_claims
        ) + tuple(_relationship_ref(r) for r in scoped_rels)
        if all_refs:
            premise_updates = _premise_preflight(
                repository_id, all_refs, store=store, bounds=bounds,
            )
            if premise_updates:
                return False
            if any(
                c.freshness.state is not m.FreshnessState.CURRENT
                for c in scoped_claims
            ) or any(
                r.freshness.state is not m.FreshnessState.CURRENT
                for r in scoped_rels
            ):
                return False
        # (d) no outstanding pages: every scoped subject load must be
        # exhaustive within bounds.
        for sid in scoped_subjects:
            claim_page = store.load_claims(
                repository_id, (sid,), (), bounds, None
            )
            if claim_page.bound_info.truncated:
                return False
    except Exception:
        return False
    # (e) is entailed by (b)+(d): every ANSWERED result ref resolved
    # above to a CURRENT canonical item through the effective views.
    return True

def _compose_explain_answer(
    repository_id: str,
    subject: m.Subject,
    resolution: m.SubjectResolution | None,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    page_token: str | None = None,
    scope_root: m.SubjectId | None = None,
    question_key: str = "",
) -> m.SemanticAnswer:
    sid = subject.subject_id
    _digest = _query_digest(
        "EXPLAIN",
        repository_id,
        f"{sid.subject_kind.value}:{sid.canonical_locator}",
        question_key,
        bounds,
    )
    _validate_service_token(page_token, _digest)
    claims, relationships, claims_token, rels_token = _load_subject_state(
        repository_id, sid, store=store, bounds=bounds,
        page_token=page_token,
    )
    claims, relationships = _refresh_view(
        repository_id, claims, relationships,
        evidence=evidence, store=store, bounds=bounds,
    )
    conflicts_all = _conflicts_for(
        repository_id, claims, relationships, store=store
    )
    kept_claims, kept_rels, kept_conf, items_truncated, items_category = (
        _select_answer_items(
            claims, relationships, conflicts_all, bounds.max_results
        )
    )
    locations = structural.locations(
        repository_id, sid, bounds
    ).items
    requirements: list[m.ResolutionRequirement] = []
    if resolution is not None:
        requirements.extend(_answers.requirements_for_resolution(resolution))
    for claim in kept_claims:
        requirements.extend(_answers.requirements_for_claim(claim))
    (kept_locs,), truncated_locs, category_locs, _ = (
        _answers.truncate_fields(
            ((locations, "locations"),),
            max(
                0,
                bounds.max_results
                - len(kept_conf) - len(kept_claims) - len(kept_rels),
            ),
        )
    )
    truncated = items_truncated or truncated_locs
    category = items_category if items_category is not None else category_locs
    views, qshown, qremaining = _paged_question_views(
        repository_id, scope_root or sid, (sid,),
        store=store, bounds=bounds, page_token=page_token,
        evidence=evidence,
    )
    if not views and not kept_claims and not kept_rels:
        requirements.append(
            m.ResolutionRequirement(
                kind=m.ResolutionKind.MISSING_SEMANTIC_COVERAGE,
                subject_or_claim=sid,
                description="no examined semantic question for subject",
                supporting_context=(),
            )
        )
    elif not views and (kept_claims or kept_rels):
        # Every current semantic item is written with its owning
        # question coverage in the same atomic batch. Stored assertions
        # with no coverage at all mean the store violates that
        # invariant; exposed current data is never downgraded to
        # unassessed content.
        raise RuntimeError(
            "semantic store invariant violation: stored assertions "
            f"without question coverage for subject {sid.canonical_locator}"
        )
    if qremaining > 0:
        truncated = True
        category = category or "question_coverage"
        requirements.append(
            m.ResolutionRequirement(
                kind=m.ResolutionKind.INCOMPLETE_SEMANTIC_SCOPE,
                subject_or_claim=sid,
                description=(
                    f"{qremaining} question coverage entries truncated; "
                    "continue with page_token"
                ),
                supporting_context=(),
            )
        )
    content = m.ExplainContent(
        claims=kept_claims,
        relationships=kept_rels,
        implementation_locations=kept_locs,  # type: ignore[arg-type]
        conflicts=kept_conf,
        question_coverage=views,
    )
    returned = len(kept_claims) + len(kept_rels) + len(kept_locs)
    return m.SemanticAnswer(
        answer_id=_answer_id(
            "ans", repository_id, sid.canonical_locator
        ),
        intent=m.SemanticIntent.EXPLAIN,
        repository_state=state,
        subject_resolution=resolution,
        content=content,
        evidence=tuple(ref for c in kept_claims for ref in c.evidence),
        resolution_requirements=tuple(requirements),
        bound_info=_bound_info(
            bounds, returned, truncated, category,
            _next_service_token(
                page_token, kept_claims, kept_rels, claims, relationships,
                claims_token, rels_token,
                questions_skip=qshown,
                questions_remaining=qremaining,
                query_digest=_digest,
            ),
        ),
        state_explanation=state_explanation_for(
            tuple(kept_claims), tuple(kept_rels),
            coverage=coverage_counts_for(views),
            bounds=(bounds.max_results, truncated),
        ),
    )

def explain(
    request: SemanticExplainRequest,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationStore,
    authority_seeds: tuple[m.EvidenceRef, ...] = (),
) -> m.SemanticAnswer | PendingInterpretation:
    """Orientation operation (plan §11.4).

    Returns an answer from stored/current semantics, or suspends with a
    pending-interpretation envelope when interpretation is missing
    (§11.12). Never interprets inline.
    """
    bounds = _resolve_bounds(request.bounds, hook=False)
    state = structural.repository_state(request.repository_id)
    if not _is_initialized(request.repository_id, store=store):
        return _uninitialized_answer(
            m.SemanticIntent.EXPLAIN, request.repository_id, bounds, state
        )
    resolution = _resolve_query_subject(
        request.repository_id, request.target, structural=structural,
        store=store, bounds=bounds,
    )
    if request.target.exact_subject_id is None:
        use_direct = False
        if resolution.ambiguity is m.ResolutionAmbiguity.RESOLVED:
            if resolution.candidates and _has_established_semantic_state(
                request.repository_id, resolution.candidates[0].subject,
                store=store, bounds=bounds,
            ):
                use_direct = True
        elif resolution.ambiguity is m.ResolutionAmbiguity.AMBIGUOUS:
            for candidate in resolution.candidates:
                if _has_established_semantic_state(
                    request.repository_id, candidate.subject,
                    store=store, bounds=bounds,
                ):
                    use_direct = True
                    break
        if not use_direct:
            orientation, _ = _resolve_contextual_subjects(
                request.repository_id, request.target,
                structural=structural, evidence=evidence,
                store=store, bounds=bounds,
            )
            if orientation.ambiguity is not m.ResolutionAmbiguity.NOT_FOUND:
                resolution = orientation
    if resolution.ambiguity is not m.ResolutionAmbiguity.RESOLVED:
        requirements = _answers.requirements_for_resolution(
            resolution, repository_id=request.repository_id,
            name_or_locator=request.target.name_or_locator,
        )
        if (
            resolution.ambiguity is m.ResolutionAmbiguity.AMBIGUOUS
            and resolution.bound_info.truncated
            and resolution.bound_info.truncated_category
            in ("inventory", "context")
        ):
            requirements = requirements + (
                m.ResolutionRequirement(
                    kind=m.ResolutionKind.INCOMPLETE_SEMANTIC_SCOPE,
                    subject_or_claim=None,
                    description=(
                        "path context not completely examined within "
                        "bounds; narrow the path or raise bounds"
                    ),
                    supporting_context=(),
                ),
            )
        return m.SemanticAnswer(
            answer_id=_answer_id(
                "ans", request.repository_id,
                request.target.name_or_locator or "unknown",
            ),
            intent=m.SemanticIntent.EXPLAIN,
            repository_state=state,
            subject_resolution=resolution,
            content=m.ExplainContent(),
            evidence=(),
            resolution_requirements=requirements,
            bound_info=_bound_info(bounds, 0, False, None),
            state_explanation=("returned assertions: none",),
        )
    subject = resolution.candidates[0].subject
    # S4 §5.4: question_selection and establish_baseline together rejected.
    if request.question_selection is not None and request.establish_baseline:
        raise ValueError(
            "question_selection and explain(establish_baseline=True) "
            "together are rejected; use one mode: baseline audit or "
            "narrowed question selection"
        )
    # S4: narrowed selection derives service-owned scope; anchors pass
    # verbatim as question_terms into bounded discovery. Effective slice
    # equals host slice verbatim for EXPLAIN/AUTHORITY (discriminator
    # empty). Full-scope supply rejected (selection carries only
    # slice/basis/anchors by type).
    _selection_anchors: tuple[str, ...] = ()
    _selected_scope: m.SemanticQuestionScope | None = None
    if request.question_selection is not None:
        from span.service.questions import derive_service_question as _derive

        _selected_scope, _selection_anchors = _derive(
            subject=subject,
            scope_root=subject.subject_id,
            question_class=m.SemanticQuestionClass.CQ_01,
            selection=request.question_selection,
            default_slice=m.QUESTION_CLASS_DEFAULT_SLICE[
                m.SemanticQuestionClass.CQ_01
            ],
            default_basis="EXPLAIN question-local",
        )
    if request.establish_baseline:
        if _baseline_sufficient(
            request.repository_id, subject.subject_id,
            store=store, evidence=evidence, bounds=bounds,
        ):
            return _compose_explain_answer(
                request.repository_id, subject, resolution,
                structural=structural, evidence=evidence, store=store,
                bounds=bounds, state=state, page_token=request.page_token,
                scope_root=subject.subject_id,
            )
        # Reissue recovery: never restart the audit while admitted work
        # exists — persisted coverage determines the next unit.
        nxt_cov = _next_baseline_pending(
            request.repository_id, subject,
            store=store, bounds=bounds,
        )
        if nxt_cov is not None:
            return _suspend_baseline_pending(
                request.repository_id, subject, nxt_cov,
                structural=structural, evidence=evidence, store=store,
                bounds=bounds, state=state, seeds=authority_seeds,
                resolution=resolution,
                continuations=continuations,
            )
        try:
            existing = store.load_all_question_coverages(
                request.repository_id, subject.subject_id,
                (subject.subject_id,),
            )
        except Exception:
            existing = ()
        audited = any(
            cov.question is not None
            and cov.question.question_class
            is m.SemanticQuestionClass.CQ_01
            and cov.question.subject == subject.subject_id
            for cov in existing
        )
        if audited:
            # Worklist exhausted but qualified (OPEN/similarly honest
            # states remain): serve the qualified answer, never a
            # redundant second audit.
            return _compose_explain_answer(
                request.repository_id, subject, resolution,
                structural=structural, evidence=evidence, store=store,
                bounds=bounds, state=state, page_token=request.page_token,
                scope_root=subject.subject_id,
            )
        task = prepare_interpretation_task(
            request.repository_id, subject, structural=structural,
            evidence=evidence, bounds=bounds, state=state,
            authority_seeds=authority_seeds,
            operation_intent=m.SemanticIntent.EXPLAIN,
            question_slice="",
            store=store,
            scope_root=subject.subject_id,
            establish_baseline=True,
        )
        return _suspend(
            op="explain", repository_id=request.repository_id,
            subject=subject, task=task, seeds=authority_seeds,
            bounds=bounds, state=state, resolution=resolution,
            continuations=continuations,
            operation_intent="EXPLAIN",
            question_slice=task.request.question_slice,
            establish_baseline=True,
        )
    claims, relationships, _, _ = _load_subject_state(
        request.repository_id, subject.subject_id,
        store=store, bounds=bounds,
    )
    # S4: selected-question path replaces claim-existence shortcut with
    # primary-question coverage. When selection present, use derived
    # scope; otherwise default question-local missing logic.
    if _selected_scope is not None:
        try:
            _existing = store.load_all_question_coverages(
                request.repository_id, _selected_scope.scope_root,
                (_selected_scope.subject,),
            )
        except Exception:
            _existing = ()
        _match = None
        for _cov in _existing:
            if _cov.question is None:
                continue
            _q = _cov.question
            if (
                _q.scope_root == _selected_scope.scope_root
                and _q.subject == _selected_scope.subject
                and _q.question_class == _selected_scope.question_class
                and _q.question_slice == _selected_scope.question_slice
            ):
                _match = _cov
                break
        if _match is None:
            task = prepare_interpretation_task(
                request.repository_id, subject, structural=structural,
                evidence=evidence, bounds=bounds, state=state,
                authority_seeds=authority_seeds,
                operation_intent=m.SemanticIntent.EXPLAIN,
                question_slice=_selected_scope.question_slice,
                store=store,
                scope_root=_selected_scope.scope_root,
                question_class=_selected_scope.question_class,
                materiality_basis=_selected_scope.materiality_basis,
                question_terms=_selection_anchors,
            )
            return _suspend(
                op="explain", repository_id=request.repository_id,
                subject=subject, task=task, seeds=authority_seeds,
                bounds=bounds, state=state, resolution=resolution,
                continuations=continuations,
                operation_intent="EXPLAIN",
                question_slice=_selected_scope.question_slice,
                root_question=_selected_scope,
                question_selection=request.question_selection,
            )
        # Existing coverage found: answer filtered to selected identity.
        import dataclasses as _dc

        from span.service.questions import (
            filter_views_by_scope as _filter_views,
        )

        _ans = _compose_explain_answer(
            request.repository_id, subject, resolution,
            structural=structural, evidence=evidence, store=store,
            bounds=bounds, state=state, page_token=request.page_token,
            scope_root=subject.subject_id,
            question_key=(
                f"{_selected_scope.question_class.value}:"
                f"{_selected_scope.question_slice}"
            ),
        )
        _filtered = _filter_views(
            _ans.content.question_coverage, _selected_scope
        )
        _content = _dc.replace(_ans.content, question_coverage=_filtered)
        return _dc.replace(_ans, content=_content)
    missing_question = _question_local_missing(
        request.repository_id, subject, m.SemanticIntent.EXPLAIN,
        store=store, evidence=evidence, bounds=bounds,
    )
    if missing_question is not None:
        task = prepare_interpretation_task(
            request.repository_id, subject, structural=structural,
            evidence=evidence, bounds=bounds, state=state,
            authority_seeds=authority_seeds,
            operation_intent=m.SemanticIntent.EXPLAIN,
            question_slice=missing_question.question_slice,
            store=store,
            scope_root=missing_question.scope_root,
            question_class=missing_question.question_class,
            materiality_basis=missing_question.materiality_basis,
        )
        return _suspend(
            op="explain", repository_id=request.repository_id,
            subject=subject, task=task, seeds=authority_seeds,
            bounds=bounds, state=state, resolution=resolution,
            continuations=continuations,
            operation_intent="EXPLAIN",
            question_slice=missing_question.question_slice,
        )
    return _compose_explain_answer(
        request.repository_id, subject, resolution,
        structural=structural, evidence=evidence, store=store,
        bounds=bounds, state=state, page_token=request.page_token,
        scope_root=subject.subject_id,
    )
