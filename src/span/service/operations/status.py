"""Span service status operation (plan §11.8; v0.6 §14 Amendment A-01).

Currency and verification over stored semantics, with hook fast
path and resume. Verbatim from ``span.service_operations``; only the
module path changed.
"""

from __future__ import annotations

from span.core import answers as _answers
from span.core import model as m
from span.ports.evidence import EvidenceSource
from span.ports.interpretation import PendingInterpretation
from span.ports.store import SemanticStore
from span.ports.structural import StructuralSource
from span.shell.agent_exchange.continuations import ContinuationStore
from span.shell.agent_exchange.continuations import SuspendedOperation

from span.service.answers import (
    _answer_id,
    _bound_info,
    _conflicts_for,
    _freshness_items_for,
    _next_service_token,
    _select_answer_items,
)
from span.service.bounds import (
    resolve_bounds as _resolve_bounds,
)
from span.service.freshness import (
    _classify_current,
    _latest_coverages,
    _refresh_view,
)
from span.service.interpretation import (
    _suspend,
    prepare_interpretation_task,
)
from span.service.questions import (
    effective_question_view,
    _missing_subjects,
    _paged_question_views,
    _question_local_missing,
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
    SemanticStatusRequest,
    StatusTargetError,
)
from span.service.resolution import (
    _load_subject_state,
    _resolve_scope_subjects,
)
from span.shell import paging as _paging

__all__ = [
    '_hook_fast',
    '_compose_status_answer',
    'status',
    '_resume_status',
]

def _hook_fast(
    repository_id: str,
    target: m.SubjectSelector | m.EvidenceScope | None,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> m.HookStatusNotice:
    """Bounded read-only lifecycle check (plan §11.8 HOOK_FAST).

    Never writes semantic state, discovers evidence, interprets,
    expands reach, initializes, rebuilds, or refreshes. Unresolvable
    paths contribute nothing (I-32 silence).
    """
    try:
        structural.repository_state(repository_id)
    except Exception:
        return m.HookStatusNotice(
            readiness=m.RepositoryReadiness.UNAVAILABLE,
            recommended_action="verify repository availability",
        )
    if not _is_initialized(repository_id, store=store):
        return m.HookStatusNotice(
            readiness=m.RepositoryReadiness.UNINITIALIZED,
            recommended_action=(
                "run initialize_repository in a dedicated "
                "setup session"
            ),
        )
    if target is None:
        return m.HookStatusNotice(
            readiness=m.RepositoryReadiness.READY
        )
    subjects, _ = _resolve_scope_subjects(
        repository_id, target, structural=structural, store=store,
        bounds=bounds, evidence=evidence,
    )
    affected: list[m.SubjectId] = []
    stale = 0
    unverifiable = 0
    for subject in subjects:
        claims, relationships, _, _ = _load_subject_state(
            repository_id, subject.subject_id, store=store, bounds=bounds
        )
        ids: tuple[m.ClaimRef | m.RelationshipRef, ...] = tuple(
            _claim_ref(c) for c in claims
        ) + tuple(_relationship_ref(r) for r in relationships)
        if not ids:
            continue
        updates, _ = _classify_current(
            repository_id, ids, evidence=evidence, store=store, bounds=bounds
        )
        if updates:
            affected.append(subject.subject_id)
            for update in updates:
                if update.freshness.state is m.FreshnessState.STALE:
                    stale += 1
                else:
                    unverifiable += 1
    # Seed reliance is explicit: a moved or missing authority seed
    # marks its scope stale even with quiet direct dependencies.
    # Inventory-membership changes alone stay silent here (I-32: a new
    # file has no dependants); queries surface them via coverage.
    coverages = store.load_coverage_dependencies(
        repository_id,
        tuple(s.subject_id for s in subjects),
    )
    coverages = _latest_coverages(coverages)
    seed_refs = tuple(
        dict.fromkeys(
            m.EvidenceRef(
                evidence_id=seed.evidence_id,
                repository_id=repository_id,
                source_kind=m.EvidenceSourceKind.USER_PROJECT_CONFIG,
                locator=seed.locator or seed.evidence_id.value,
            )
            for coverage in coverages
            for seed in coverage.seed_fingerprints
        )
    )
    seed_current: dict[str, str | None] = {}
    if seed_refs:
        seed_page = evidence.inventory_evidence(
            repository_id,
            m.EvidenceScope(paths=(), evidence_refs=seed_refs),
            bounds,
        )
        seed_current = {
            item.evidence_ref.evidence_id.value: item.content_fingerprint
            for item in seed_page.items
        }
    for coverage in coverages:
        if not coverage.seed_fingerprints:
            continue
        seed_moved = any(
            seed_current.get(seed.evidence_id.value) != seed.fingerprint
            for seed in coverage.seed_fingerprints
        )
        if not seed_moved:
            continue
        for sid in coverage.scope_subjects:
            if sid not in affected:
                affected.append(sid)
            claims, relationships, _, _ = _load_subject_state(
                repository_id, sid, store=store, bounds=bounds
            )
            stale += len(claims) + len(relationships)
    action = None
    if stale or unverifiable:
        action = (
            f"run refresh: {stale} stale, "
            f"{unverifiable} unverifiable items"
        )
    return m.HookStatusNotice(
        readiness=m.RepositoryReadiness.READY,
        affected_count=len(affected),
        stale_count=stale,
        unverifiable_count=unverifiable,
        affected_subject_ids=tuple(affected),
        recommended_action=action,
    )


def _repository_coverage_entry(
    repository_id: str,
    subject: m.Subject,
    *,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> m.SemanticCoverageEntry:
    """Build one report entry from persisted semantic state only."""
    claims, relationships, claim_token, rel_token = _load_subject_state(
        repository_id, subject.subject_id, store=store, bounds=bounds
    )
    semantic_ids: tuple[m.ClaimRef | m.RelationshipRef, ...] = tuple(
        _claim_ref(claim) for claim in claims
    ) + tuple(_relationship_ref(rel) for rel in relationships)
    updates, _ = _classify_current(
        repository_id, semantic_ids, evidence=evidence, store=store,
        bounds=bounds,
    )
    freshness_by_id = {
        claim.claim_id.value: claim.freshness.state for claim in claims
    }
    freshness_by_id.update(
        {
            rel.relationship_id.value: rel.freshness.state
            for rel in relationships
        }
    )
    freshness_by_id.update(
        {update.semantic_id.id.value: update.freshness.state for update in updates}
    )
    current_count = sum(
        state is m.FreshnessState.CURRENT
        for state in freshness_by_id.values()
    )
    stale_count = sum(
        state is m.FreshnessState.STALE
        for state in freshness_by_id.values()
    )
    unverifiable_count = sum(
        state is m.FreshnessState.UNVERIFIABLE
        for state in freshness_by_id.values()
    )

    question_views: list[m.SemanticQuestionCoverageView] = []
    question_total = store.count_question_coverages(
        repository_id, None, (subject.subject_id,)
    )
    coverages = store.load_question_coverages(
        repository_id, None, (subject.subject_id,), bounds
    )
    for coverage in coverages:
        if coverage.question is None:
            continue
        question_views.append(
            effective_question_view(
                coverage, evidence=evidence, store=store,
                repository_id=repository_id,
            )
        )
    question_views.sort(
        key=lambda view: (
            view.question.question_class.value,
            view.question.question_slice,
        )
    )
    question_count = len(question_views)
    question_remaining = max(0, question_total - question_count)
    pending_count = sum(
        view.effective_disposition is m.SemanticQuestionDisposition.PENDING
        for view in question_views
    )
    open_count = sum(
        view.effective_disposition is m.SemanticQuestionDisposition.OPEN
        for view in question_views
    )
    answered_count = sum(
        view.effective_disposition is m.SemanticQuestionDisposition.ANSWERED
        for view in question_views
    )
    not_applicable_count = sum(
        view.effective_disposition
        is m.SemanticQuestionDisposition.NOT_APPLICABLE
        for view in question_views
    )
    question_stale = any(
        view.freshness.state is m.FreshnessState.STALE
        for view in question_views
    )
    question_unverifiable = any(
        view.freshness.state is m.FreshnessState.UNVERIFIABLE
        for view in question_views
    )
    requirements: list[m.ResolutionRequirement] = [
        requirement
        for view in question_views
        for requirement in view.resolution_requirements
    ]
    truncated = bool(claim_token or rel_token or question_remaining)
    if not question_views and question_total == 0:
        requirements.append(
            m.ResolutionRequirement(
                kind=m.ResolutionKind.MISSING_SEMANTIC_COVERAGE,
                subject_or_claim=subject.subject_id,
                description=(
                    "no adopted question coverage is persisted for this "
                    "semantic subject"
                ),
                supporting_context=(),
            )
        )
    if truncated:
        requirements.append(
            m.ResolutionRequirement(
                kind=m.ResolutionKind.INCOMPLETE_SEMANTIC_SCOPE,
                subject_or_claim=subject.subject_id,
                description=(
                    "repository semantic coverage is bounded; remaining "
                    "items or questions require a narrower page"
                ),
                supporting_context=(),
            )
        )
    requirements = list(dict.fromkeys(requirements))
    incomplete = bool(
        pending_count or open_count or question_remaining or truncated
    )
    if question_unverifiable or unverifiable_count:
        disposition = m.SemanticCoverageDisposition.UNVERIFIABLE
    elif question_stale or stale_count:
        disposition = m.SemanticCoverageDisposition.STALE
    elif incomplete:
        disposition = m.SemanticCoverageDisposition.INCOMPLETE
    elif not question_views:
        disposition = m.SemanticCoverageDisposition.UNASSESSED
    else:
        disposition = m.SemanticCoverageDisposition.CURRENT
    return m.SemanticCoverageEntry(
        subject=subject.subject_id,
        disposition=disposition,
        semantic_item_count=len(semantic_ids),
        current_item_count=current_count,
        stale_item_count=stale_count,
        unverifiable_item_count=unverifiable_count,
        question_count=question_count,
        answered_question_count=answered_count,
        pending_question_count=pending_count,
        open_question_count=open_count,
        not_applicable_question_count=not_applicable_count,
        resolution_requirements=tuple(requirements[:bounds.max_results]),
        truncated=truncated,
    )


def _coverage_entries_for_subjects(
    repository_id: str,
    subjects: tuple[m.Subject, ...],
    *,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> tuple[m.SemanticCoverageEntry, ...]:
    """One coverage entry per frontier subject from persisted state only."""
    return tuple(
        _repository_coverage_entry(
            repository_id, subject, evidence=evidence, store=store,
            bounds=bounds,
        )
        for subject in subjects
    )


def _coverage_report(
    entries: tuple[m.SemanticCoverageEntry, ...],
    *,
    persisted_subject_count: int,
    returned_subject_count: int,
) -> m.SemanticCoverageReport:
    counts = {
        disposition: sum(
            entry.disposition is disposition for entry in entries
        )
        for disposition in m.SemanticCoverageDisposition
    }
    return m.SemanticCoverageReport(
        entries=entries,
        persisted_subject_count=persisted_subject_count,
        returned_subject_count=returned_subject_count,
        current_subject_count=counts[m.SemanticCoverageDisposition.CURRENT],
        incomplete_subject_count=counts[
            m.SemanticCoverageDisposition.INCOMPLETE
        ],
        stale_subject_count=counts[m.SemanticCoverageDisposition.STALE],
        unverifiable_subject_count=counts[
            m.SemanticCoverageDisposition.UNVERIFIABLE
        ],
        unassessed_subject_count=counts[
            m.SemanticCoverageDisposition.UNASSESSED
        ],
    )


def _compose_repository_status_answer(
    repository_id: str,
    *,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    subject_offset: int = 0,
) -> m.SemanticAnswer:
    """Report persisted semantic coverage without structural enumeration."""
    subject_page = store.load_repository_subjects(
        repository_id, bounds, subject_offset
    )
    entries = _coverage_entries_for_subjects(
        repository_id, subject_page.items, evidence=evidence, store=store,
        bounds=bounds,
    )
    report = _coverage_report(
        entries,
        persisted_subject_count=store.count_repository_subjects(
            repository_id
        ),
        returned_subject_count=len(entries),
    )
    requirements = tuple(
        requirement
        for entry in entries
        for requirement in entry.resolution_requirements
    )[:bounds.max_results]
    truncated = subject_page.bound_info.truncated or any(
        entry.truncated for entry in entries
    )
    next_token = None
    if subject_page.bound_info.truncated:
        next_token = _paging.format_service_token(
            subject_offset + len(entries), None, 0
        )
    category = (
        subject_page.bound_info.truncated_category
        if subject_page.bound_info.truncated
        else "semantic_frontier" if truncated else None
    )
    returned = len(entries) + len(requirements)
    return m.SemanticAnswer(
        answer_id=_answer_id(
            "stt", repository_id,
            f"repository-coverage:{subject_offset}",
        ),
        intent=m.SemanticIntent.STATUS,
        repository_state=state,
        subject_resolution=None,
        content=m.StatusContent(
            readiness=m.RepositoryReadiness.READY,
            unresolved=requirements,
            coverage_report=report,
        ),
        evidence=(),
        resolution_requirements=requirements,
        bound_info=_bound_info(
            bounds, returned, truncated, category, next_token
        ),
    )


def _repository_status_page(
    request: SemanticStatusRequest,
    *,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
) -> m.SemanticAnswer:
    """Resolve the normal no-target repository report page."""
    try:
        subject_skip, rel_skip, question_skip = (
            _paging.parse_service_token(request.page_token)
        )
    except ValueError as exc:
        raise StatusTargetError(str(exc)) from None
    if rel_skip or question_skip:
        raise StatusTargetError(
            "repository status page tokens use the subject offset only"
        )
    return _compose_repository_status_answer(
        request.repository_id,
        evidence=evidence,
        store=store,
        bounds=bounds,
        state=state,
        subject_offset=subject_skip,
    )

def _compose_status_answer(
    repository_id: str,
    subjects: tuple[m.Subject, ...],
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    page_token: str | None = None,
) -> m.SemanticAnswer:
    all_claims: list[m.SemanticClaim] = []
    all_rels: list[m.SemanticRelationship] = []
    first_claims_token: str | None = None
    first_rels_token: str | None = None
    for position, subject in enumerate(subjects):
        claims, relationships, tok_c, tok_r = _load_subject_state(
            repository_id, subject.subject_id, store=store, bounds=bounds,
            page_token=page_token if len(subjects) == 1 else None,
        )
        all_claims.extend(claims)
        all_rels.extend(relationships)
        if position == 0:
            first_claims_token, first_rels_token = tok_c, tok_r
    # Classify before the view persists anything: _refresh_view marks
    # state, after which a second classification would always report
    # clean and changed_dependencies would always be empty.
    pre_ids: tuple[m.ClaimRef | m.RelationshipRef, ...] = tuple(
        _claim_ref(c) for c in all_claims
    ) + tuple(_relationship_ref(r) for r in all_rels)
    updates, dependencies = _classify_current(
        repository_id, pre_ids, evidence=evidence, store=store, bounds=bounds
    )
    updated_ids = {u.semantic_id.id.value for u in updates}
    changed = tuple(
        dep for dep in dependencies if dep.semantic_id.id.value in updated_ids
    )
    stale_evidence = {
        dep.evidence_ref.locator
        for dep in dependencies
        if dep.semantic_id.id.value in updated_ids
    }
    claims_t, rels_t = _refresh_view(
        repository_id, tuple(all_claims), tuple(all_rels),
        evidence=evidence, store=store, bounds=bounds,
    )
    verification_all = tuple(
        claim.value
        for claim in claims_t
        if claim.kind is m.ClaimKind.VERIFICATION
        and isinstance(claim.value, m.VerificationValue)
    )
    conflicts_all = _conflicts_for(
        repository_id, tuple(claims_t), tuple(rels_t), store=store
    )
    kept_claims, kept_rels, kept_conf, items_truncated, items_category = (
        _select_answer_items(
            claims_t, rels_t, conflicts_all, bounds.max_results
        )
    )
    kept_ids = {c.claim_id.value for c in kept_claims} | {
        r.relationship_id.value for r in kept_rels
    }
    changed_kept = tuple(
        dep for dep in changed
        if dep.semantic_id.id.value in kept_ids
    )
    unresolved: list[m.ResolutionRequirement] = []
    for claim in kept_claims:
        unresolved.extend(_answers.requirements_for_claim(claim))
    for rel in kept_rels:
        unresolved.extend(_answers.requirements_for_relationship(rel))
    # Non-ref lists (evidence pointers and values, never semantic refs)
    # take the remaining budget deterministically.
    rest_budget = max(
        0, bounds.max_results - len(kept_conf) - len(kept_claims)
    )
    kept_unresolved = tuple(unresolved[:rest_budget])
    kept_changed = changed_kept[: max(0, rest_budget - len(kept_unresolved))]
    kept_ver = verification_all[
        : max(0, rest_budget - len(kept_unresolved) - len(kept_changed))
    ]
    truncated = items_truncated or (
        len(kept_unresolved) + len(kept_changed) + len(kept_ver)
        < len(unresolved) + len(changed_kept) + len(verification_all)
    )
    category = items_category
    if category is None and truncated:
        category = "unresolved"
    if len(subjects) == 1:
        views, qshown, qremaining = _paged_question_views(
            repository_id, subjects[0].subject_id,
            tuple(s.subject_id for s in subjects),
            store=store, bounds=bounds, page_token=page_token,
            evidence=evidence,
        )
        token: str | None = _next_service_token(
            page_token, kept_claims, kept_rels, claims_t, rels_t,
            first_claims_token, first_rels_token,
            questions_skip=qshown,
            questions_remaining=qremaining,
        )
    else:
        views, _, qremaining = _paged_question_views(
            repository_id, None,
            tuple(s.subject_id for s in subjects),
            store=store, bounds=bounds, page_token=None,
            evidence=evidence,
        )
        token = None
    if qremaining > 0:
        truncated = True
        category = category or "question_coverage"
    # Whole-frontier accounting for the exact scope (Addendum E E-13):
    # one typed disposition per frontier subject, UNASSESSED where no
    # coverage was adopted. Read-time projection over persisted state;
    # no new store, no second writer. Answer-level unresolved/truncation
    # math below is unchanged.
    frontier_entries = _coverage_entries_for_subjects(
        repository_id, subjects, evidence=evidence, store=store,
        bounds=bounds,
    )
    frontier_report = _coverage_report(
        frontier_entries,
        persisted_subject_count=sum(
            1 for entry in frontier_entries
            if entry.semantic_item_count or entry.question_count
        ),
        returned_subject_count=len(frontier_entries),
    )
    content = m.StatusContent(
        readiness=m.RepositoryReadiness.READY,
        freshness_items=_freshness_items_for(kept_claims, kept_rels),
        changed_dependencies=kept_changed,  # type: ignore[arg-type]
        verification_currency=kept_ver,  # type: ignore[arg-type]
        refresh_scope=m.EvidenceScope(
            paths=tuple(sorted(stale_evidence)), evidence_refs=()
        ),
        claims=kept_claims,
        relationships=kept_rels,
        conflicts=kept_conf,
        unresolved=tuple(unresolved),
        question_coverage=views,
        coverage_report=frontier_report,
    )
    returned = (
        len(kept_conf) + len(unresolved) + len(kept_claims)
        + len(kept_changed) + len(kept_ver)
    )
    return m.SemanticAnswer(
        answer_id=_answer_id(
            "stt", repository_id,
            ",".join(
                s.subject_id.canonical_locator for s in subjects
            ) or "scope",
        ),
        intent=m.SemanticIntent.STATUS,
        repository_state=state,
        subject_resolution=None,
        content=content,
        evidence=tuple(ref for c in kept_claims for ref in c.evidence),
        resolution_requirements=tuple(unresolved),
        bound_info=_bound_info(bounds, returned, truncated, category, token),
    )

def status(
    request: SemanticStatusRequest,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationStore,
    authority_seeds: tuple[m.EvidenceRef, ...] = (),
) -> m.SemanticAnswer | PendingInterpretation | m.HookStatusNotice:
    """Currency operation (plan §11.8).

    NORMAL performs the full bounded status operation, suspending via
    §11.12 when subject interpretation is missing. HOOK_FAST is read-only
    lifecycle observation returning a compact notice — never suspension,
    never writes. Claim/relationship targets resolve through the §5.5
    ref lookup; answer envelopes are never persisted (StatusTargetError).

    Paging (plan I-39): `page_token` carries per-list offsets redeemed
    for single-subject and ref targets. A no-target request pages the
    persisted semantic-subject frontier; it never enumerates structural
    subjects.
    """
    if isinstance(request.target, m.AnswerRef):
        raise StatusTargetError(
            "answer envelopes are not persisted; status serves "
            "subject, claim, relationship, and evidence-scope targets"
        )
    bounds = _resolve_bounds(request.bounds, hook=False)
    if request.mode is m.StatusMode.HOOK_FAST:
        return _hook_fast(
            request.repository_id, request.target,
            structural=structural, evidence=evidence, store=store,
            bounds=bounds,
        )
    if isinstance(request.target, (m.ClaimRef, m.RelationshipRef)):
        try:
            (item,) = store.load_by_refs(
                request.repository_id, (request.target,)
            )
        except ValueError as exc:
            raise StatusTargetError(str(exc)) from None
        state = structural.repository_state(request.repository_id)
        if not _is_initialized(request.repository_id, store=store):
            return _uninitialized_answer(
                m.SemanticIntent.STATUS, request.repository_id,
                bounds, state,
            )
        sid = (
            item.subject
            if isinstance(item, m.SemanticClaim)
            else item.source
        )
        subjects = store.load_subjects(request.repository_id, (sid,))
        if not subjects:
            raise StatusTargetError("referenced subject is not indexed")
        return _compose_status_answer(
            request.repository_id, subjects, structural=structural,
            evidence=evidence, store=store, bounds=bounds, state=state,
            page_token=request.page_token,
        )
    state = structural.repository_state(request.repository_id)
    if not _is_initialized(request.repository_id, store=store):
        return _uninitialized_answer(
            m.SemanticIntent.STATUS, request.repository_id, bounds, state
        )
    if request.target is None:
        return _repository_status_page(
            request,
            evidence=evidence,
            store=store,
            bounds=bounds,
            state=state,
        )
    subjects, ambiguity = _resolve_scope_subjects(
        request.repository_id, request.target,
        structural=structural, store=store, bounds=bounds,
        evidence=evidence,
    )
    # E-03: an exact-target status that suspends must carry the user boundary
    # in every pending task, exactly like target-establishment units.
    scope_target = (
        request.target
        if isinstance(request.target, m.EvidenceScope)
        else m.EvidenceScope()
    )
    if ambiguity is not m.ResolutionAmbiguity.RESOLVED or not subjects:
        requirements: tuple[m.ResolutionRequirement, ...] = ()
        if ambiguity is m.ResolutionAmbiguity.AMBIGUOUS:
            requirements = (
                m.ResolutionRequirement(
                    kind=m.ResolutionKind.AMBIGUOUS_IDENTITY,
                    subject_or_claim=None,
                    description="status target is ambiguous",
                    supporting_context=(),
                ),
            )
        return m.SemanticAnswer(
            answer_id=_answer_id(
                "stt", request.repository_id, "scope"
            ),
            intent=m.SemanticIntent.STATUS,
            repository_state=state,
            subject_resolution=None,
            content=m.StatusContent(),
            evidence=(),
            resolution_requirements=requirements,
            bound_info=_bound_info(bounds, 0, False, None),
        )
    missing = _missing_subjects(
        request.repository_id, subjects, store=store, bounds=bounds,
        suspended=(), evidence=evidence,
    )
    if missing is not None:
        needed = _question_local_missing(
            request.repository_id, missing, m.SemanticIntent.STATUS,
            store=store, evidence=evidence, bounds=bounds,
        )
        task = prepare_interpretation_task(
            request.repository_id, missing, structural=structural,
            evidence=evidence, bounds=bounds, state=state,
            authority_seeds=authority_seeds,
            operation_intent=m.SemanticIntent.STATUS,
            question_slice=(
                needed.question_slice if needed is not None
                else missing.subject_id.canonical_locator
            ),
            store=store,
            scope_root=(
                needed.scope_root if needed is not None
                else missing.subject_id
            ),
            question_class=(
                needed.question_class if needed is not None else None
            ),
            materiality_basis=(
                needed.materiality_basis if needed is not None else ""
            ),
            target_scope=scope_target,
        )
        return _suspend(
            op="status", repository_id=request.repository_id,
            subject=missing, task=task, seeds=authority_seeds,
            bounds=bounds, state=state, resolution=None, scope=subjects,
            suspended=(missing.subject_id.canonical_locator,),
            continuations=continuations,
            operation_intent="STATUS",
            question_slice=task.request.question_slice,
            target_scope=scope_target,
        )
    return _compose_status_answer(
        request.repository_id, subjects, structural=structural,
        evidence=evidence, store=store, bounds=bounds, state=state,
        page_token=request.page_token,
    )

def _resume_status(
    record: SuspendedOperation,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    continuations: ContinuationStore,
) -> m.SemanticAnswer | PendingInterpretation:
    suspended = record.suspended + (
        record.subject.subject_id.canonical_locator,
    )
    missing = _missing_subjects(
        record.repository_id, record.scope, store=store, bounds=bounds,
        suspended=suspended, evidence=evidence,
    )
    if missing is not None:
        needed = _question_local_missing(
            record.repository_id, missing, m.SemanticIntent.STATUS,
            store=store, evidence=evidence, bounds=bounds,
        )
        task = prepare_interpretation_task(
            record.repository_id, missing, structural=structural,
            evidence=evidence, bounds=bounds, state=state,
            authority_seeds=record.seeds,
            operation_intent=m.SemanticIntent.STATUS,
            question_slice=(
                needed.question_slice if needed is not None
                else missing.subject_id.canonical_locator
            ),
            store=store,
            scope_root=(
                needed.scope_root if needed is not None
                else missing.subject_id
            ),
            question_class=(
                needed.question_class if needed is not None else None
            ),
            materiality_basis=(
                needed.materiality_basis if needed is not None else ""
            ),
            target_scope=record.target_scope,
        )
        return _suspend(
            op="status", repository_id=record.repository_id,
            subject=missing, task=task, seeds=record.seeds,
            bounds=bounds, state=state, resolution=None,
            scope=record.scope, suspended=suspended,
            continuations=continuations,
            operation_intent="STATUS",
            question_slice=task.request.question_slice,
            target_scope=record.target_scope,
        )
    return _compose_status_answer(
        record.repository_id, record.scope, structural=structural,
        evidence=evidence, store=store, bounds=bounds, state=state,
    )
