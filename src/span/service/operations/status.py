"""Span service status operation (plan §11.8; v0.6 §14 Amendment A-01).

Currency and verification over stored semantics, with hook fast
path and resume. Verbatim from ``span.service_operations``; only the
module path changed.
"""

from __future__ import annotations

from collections.abc import Mapping

from span.core import answers as _answers
from span.core import model as m
from span.ports.evidence import EvidenceSource
from span.ports.store import SemanticStore
from span.ports.structural import StructuralSource
from span.shell.agent_exchange.continuations import (
    ContinuationStore,
    SuspendedOperation,
)

from span.service.answers import (
    _answer_id,
    ANSWER_ASSEMBLER,
    _conflicts_for,
    _freshness_items_for,
    _next_service_token,
    _query_digest,
    _validate_service_token,
    _select_answer_items,
    coverage_counts_for,
    currency_literal,
    state_explanation_for,
)
from span.service.bounds import (
    resolve_bounds as _resolve_bounds,
)
from span.service.discovery import (
    _coverage_scope_snapshots,
    enumerate_target_inventory,
)
from span.service.freshness import (
    _classify_current,
    _evaluate_current,
    _latest_coverages,
)
from span.service.questions import (
    effective_question_view,
    _paged_question_views,
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
    _resolve_query_subject,
    _resolve_scope_subjects,
    resolve_scope_frontier,
)
from span.ports.structural import StaleContinuationError
from span.shell import paging as _paging


def _scope_page_offset(page_token: str | None) -> int:
    """Read the offset from a scope cursor without validating its version.

    The version binds the membership fingerprint, which is only known after
    the frontier is resolved; the offset is safe to read first.
    """
    if page_token is None:
        return 0
    if not page_token.startswith("pgv:"):
        raise StaleContinuationError(
            "page token is invalid for this request; restart pagination from "
            "the first page with page_token omitted"
        )
    body = page_token[len("pgv:") :]
    _, _, offset_text = body.rpartition(":")
    try:
        offset = int(offset_text)
    except ValueError:
        raise StaleContinuationError(
            "page token is invalid for this request; restart pagination from "
            "the first page with page_token omitted"
        ) from None
    if offset < 0:
        raise StaleContinuationError(
            "page token is invalid for this request; restart pagination from "
            "the first page with page_token omitted"
        )
    return offset


__all__ = [
    "_hook_fast",
    "_compose_status_answer",
    "status",
]


def _pending_exchange_requirements(
    repository_id: str,
    views: tuple[m.SemanticQuestionCoverageView, ...],
    continuations: ContinuationStore,
    *,
    recovery_operation: str | None = None,
) -> tuple[m.ResolutionRequirement, ...]:
    """Project persisted pending questions against live exchange records."""
    live = continuations.live_records()
    requirements: list[m.ResolutionRequirement] = []
    for view in views:
        if view.effective_disposition is not m.SemanticQuestionDisposition.PENDING:
            continue
        question = view.question
        matches = tuple(
            record
            for record in live
            if record.repository_id == repository_id
            and record.request.question is not None
            and record.request.question.scope_root == question.scope_root
            and record.request.question.subject == question.subject
            and record.request.question.question_class == question.question_class
            and record.request.question.question_slice == question.question_slice
        )
        subject = question.subject.canonical_locator
        if matches:
            operation = matches[0].op
            description = (
                f"{question.question_class.value} '{question.question_slice}' "
                f"for '{subject}' has a live {operation} interpretation unit; "
                f"continue with the continuation returned by that {operation} "
                "call and pass it unchanged"
            )
        elif recovery_operation is not None:
            description = (
                f"{question.question_class.value} '{question.question_slice}' "
                f"for '{subject}' has no live continuation in the current "
                f"continuation store; re-run the original {recovery_operation} "
                "request with the same target inputs; do not synthesize a "
                "continuation"
            )
        else:
            description = (
                f"{question.question_class.value} '{question.question_slice}' "
                f"for '{subject}' has no live continuation in the current "
                "continuation store; the persisted question identity does not "
                "record its originating operation; repeat the original "
                "idempotent request with the same inputs and do not synthesize "
                "a continuation"
            )
        requirements.append(
            m.ResolutionRequirement(
                kind=m.ResolutionKind.INCOMPLETE_SEMANTIC_SCOPE,
                subject_or_claim=question.subject,
                description=description,
                supporting_context=(),
            )
        )
    return tuple(requirements)


def _live_question_records(
    repository_id: str,
    subjects: tuple[m.Subject, ...] | None,
    continuations: ContinuationStore,
) -> tuple[SuspendedOperation, ...]:
    """Return live semantic records for the requested status scope."""
    subject_ids = (
        None if subjects is None else {subject.subject_id for subject in subjects}
    )
    return tuple(
        record
        for record in continuations.live_records()
        if record.repository_id == repository_id
        and record.request.question is not None
        and (subject_ids is None or record.request.question.subject in subject_ids)
    )


def _live_requirement(record: SuspendedOperation) -> m.ResolutionRequirement:
    """Project one live question without exposing its continuation token."""
    question = record.request.question
    assert question is not None
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


def _live_subject_requirements(
    repository_id: str,
    subjects: tuple[m.Subject, ...],
    continuations: ContinuationStore,
) -> tuple[m.ResolutionRequirement, ...]:
    """Project live question work even before its first persisted row."""
    return tuple(
        _live_requirement(record)
        for record in _live_question_records(repository_id, subjects, continuations)
    )


def _repository_live_requirements(
    repository_id: str,
    continuations: ContinuationStore,
) -> tuple[m.ResolutionRequirement, ...]:
    """Expose first-time live semantic work in repository status."""
    return tuple(
        _live_requirement(record)
        for record in _live_question_records(repository_id, None, continuations)
    )


def _project_pending_requirements(
    requirements: tuple[m.ResolutionRequirement, ...],
    pending_requirements: tuple[m.ResolutionRequirement, ...],
) -> tuple[m.ResolutionRequirement, ...]:
    """Replace generic pending continuation wording with exact recovery."""
    by_subject: dict[m.SubjectId, list[m.ResolutionRequirement]] = {}
    for requirement in pending_requirements:
        if isinstance(requirement.subject_or_claim, m.SubjectId):
            by_subject.setdefault(requirement.subject_or_claim, []).append(requirement)
    if not by_subject:
        return requirements

    kept: list[m.ResolutionRequirement] = []
    replaced: set[m.SubjectId] = set()
    for requirement in requirements:
        subject = requirement.subject_or_claim
        pending = by_subject.get(subject) if isinstance(subject, m.SubjectId) else None
        generic = (
            pending is not None
            and requirement.kind is m.ResolutionKind.INCOMPLETE_SEMANTIC_SCOPE
            and "continuation returned by the suspending operation"
            in requirement.description
        )
        if generic:
            if subject not in replaced:
                replaced.add(subject)
                kept.extend(pending)
            continue
        kept.append(requirement)

    for subject, pending in by_subject.items():
        if subject not in replaced:
            kept.extend(pending)
    return tuple(dict.fromkeys(kept))


def _is_generic_live_action(
    requirement: m.ResolutionRequirement,
    entry: m.SemanticCoverageEntry,
    operations: frozenset[str],
) -> bool:
    if requirement.subject_or_claim != entry.subject:
        return False
    if (
        entry.disposition is m.SemanticCoverageDisposition.UNASSESSED
        and "explain" in operations
        and requirement.kind is m.ResolutionKind.MISSING_SEMANTIC_COVERAGE
        and "run question-local explain" in requirement.description
    ):
        return True
    if "refresh" in operations and requirement.kind in (
        m.ResolutionKind.STALE_EVIDENCE,
        m.ResolutionKind.UNVERIFIABLE_FRESHNESS,
    ):
        return "exact SubjectSelector" in requirement.description
    return (
        requirement.kind is m.ResolutionKind.INCOMPLETE_SEMANTIC_SCOPE
        and "continuation returned by the suspending operation"
        in requirement.description
    )


def _project_live_requirements(
    entries: tuple[m.SemanticCoverageEntry, ...],
    requirements: tuple[m.ResolutionRequirement, ...],
    live_records: tuple[SuspendedOperation, ...],
) -> tuple[m.ResolutionRequirement, ...]:
    """Replace generic status actions when their owning operation is live."""
    by_subject: dict[m.SubjectId, list[SuspendedOperation]] = {}
    for record in live_records:
        question = record.request.question
        assert question is not None
        by_subject.setdefault(question.subject, []).append(record)
    if not by_subject:
        return requirements

    entry_by_subject = {entry.subject: entry for entry in entries}
    kept: list[m.ResolutionRequirement] = []
    replaced: set[m.SubjectId] = set()
    for requirement in requirements:
        subject = requirement.subject_or_claim
        if not isinstance(subject, m.SubjectId):
            kept.append(requirement)
            continue
        live = by_subject.get(subject)
        entry = entry_by_subject.get(subject)
        if live and entry is not None:
            operations = frozenset(record.op for record in live)
            if _is_generic_live_action(requirement, entry, operations):
                if subject not in replaced:
                    replaced.add(subject)
                    kept.extend(_live_requirement(record) for record in live)
                continue
        kept.append(requirement)

    for subject, live in by_subject.items():
        if subject not in replaced:
            kept.extend(_live_requirement(record) for record in live)
    return tuple(dict.fromkeys(kept))


def _status_state_explanation(
    base: tuple[str, ...],
    content: m.StatusContent,
    requirements: tuple[m.ResolutionRequirement, ...],
) -> tuple[str, ...]:
    """Add status-only readiness, coverage, target, and authority qualifiers."""
    lines = list(base)
    if content.store_readiness is m.StoreReadiness.READY:
        lines.insert(
            0,
            "repository store_readiness: READY means the Span semantic store is "
            "available; semantic coverage and currency are reported separately",
        )
    report = content.coverage_report
    if isinstance(report, m.RepositoryCoverageReport):
        page = report.page
        totals = report.repository
        lines.append(
            "semantic coverage (page scope): "
            f"{page.current_subject_count} current, "
            f"{page.incomplete_subject_count} incomplete, "
            f"{page.stale_subject_count} stale, "
            f"{page.unverifiable_subject_count} unverifiable, "
            f"{page.unassessed_subject_count} unassessed subjects; "
            f"{totals.pending_question_count} persisted pending and "
            f"{totals.open_question_count} persisted open questions "
            "(repository counts)"
        )
    elif isinstance(report, m.ScopedCoverageReport):
        page = report.page
        lines.append(
            "semantic coverage (page scope): "
            f"{page.current_subject_count} current, "
            f"{page.incomplete_subject_count} incomplete, "
            f"{page.stale_subject_count} stale, "
            f"{page.unverifiable_subject_count} unverifiable, "
            f"{page.unassessed_subject_count} unassessed subjects; "
            f"{report.scope.persisted_subject_count} persisted subjects in scope"
        )
    if content.target_disposition is not None:
        lines.append("target disposition: " + content.target_disposition.value)
    if any(req.kind is m.ResolutionKind.MISSING_AUTHORITY for req in requirements):
        lines.append("governing authority remains unresolved for this result")
    return tuple(lines)


def _repository_pending_requirements(
    repository_id: str,
    entries: tuple[m.SemanticCoverageEntry, ...],
    *,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationStore,
) -> tuple[m.ResolutionRequirement, ...]:
    """Project pending coverage for the subjects on one repository page."""
    subjects = tuple(entry.subject for entry in entries)
    coverages = store.load_all_question_coverages(repository_id, None, ())
    views = tuple(
        effective_question_view(
            coverage,
            evidence=evidence,
            store=store,
            repository_id=repository_id,
        )
        for coverage in coverages
        if coverage.question is not None
        and coverage.question.subject in subjects
        and coverage.disposition is m.SemanticQuestionDisposition.PENDING
    )
    return _pending_exchange_requirements(repository_id, views, continuations)


def _target_live_requirements(
    repository_id: str,
    target_id: m.TargetId,
    association: m.TargetAssociation,
    *,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationStore,
) -> tuple[m.ResolutionRequirement, ...]:
    """Project live target-mapping and target-question exchange state."""
    requirements: list[m.ResolutionRequirement] = []
    for record in continuations.live_records():
        if record.repository_id != repository_id or record.target_id != target_id:
            continue
        if record.request.question is not None:
            continue
        requirements.append(
            m.ResolutionRequirement(
                kind=m.ResolutionKind.INCOMPLETE_SEMANTIC_SCOPE,
                subject_or_claim=record.subject.subject_id,
                description=(
                    f"target '{target_id.value}' has a live initialize_target "
                    "mapping unit; continue with the continuation returned "
                    "by that initialize_target call and pass it unchanged"
                ),
                supporting_context=(),
            )
        )
    pending_views: list[m.SemanticQuestionCoverageView] = []
    for question in association.target_questions:
        coverages = store.load_all_question_coverages(
            repository_id, question.scope_root, (question.subject,)
        )
        pending_views.extend(
            effective_question_view(
                coverage,
                evidence=evidence,
                store=store,
                repository_id=repository_id,
            )
            for coverage in coverages
            if coverage.question == question
            and coverage.disposition is m.SemanticQuestionDisposition.PENDING
        )
    requirements.extend(
        _pending_exchange_requirements(
            repository_id,
            tuple(pending_views),
            continuations,
            recovery_operation="initialize_target",
        )
    )
    return tuple(dict.fromkeys(requirements))


def _resolve_status_subjects(
    repository_id: str,
    target: m.SubjectSelector | m.EvidenceScope,
    *,
    structural: StructuralSource,
    store: SemanticStore,
    evidence: EvidenceSource,
    bounds: m.QueryBounds,
) -> tuple[tuple[m.Subject, ...], m.ResolutionAmbiguity, m.SubjectResolution | None]:
    """Resolve selector targets without discarding canonical candidates."""
    if isinstance(target, m.SubjectSelector):
        resolution = _resolve_query_subject(
            repository_id,
            target,
            structural=structural,
            store=store,
            bounds=bounds,
        )
        return (
            tuple(candidate.subject for candidate in resolution.candidates),
            resolution.ambiguity,
            resolution,
        )
    subjects, ambiguity = _resolve_scope_subjects(
        repository_id,
        target,
        structural=structural,
        store=store,
        bounds=bounds,
        evidence=evidence,
    )
    return subjects, ambiguity, None


def _unresolved_status_answer(
    repository_id: str,
    target: m.SubjectSelector | m.EvidenceScope,
    resolution: m.SubjectResolution | None,
    *,
    state: m.RepositoryState,
    bounds: m.QueryBounds,
) -> m.SemanticAnswer:
    requirements = (
        _answers.requirements_for_resolution(
            resolution,
            repository_id=repository_id,
            name_or_locator=(
                target.name_or_locator
                if isinstance(target, m.SubjectSelector)
                else None
            ),
        )
        if resolution is not None
        else ()
    )
    return ANSWER_ASSEMBLER.build(
        answer_id=_answer_id("stt", repository_id, "scope"),
        intent=m.SemanticIntent.STATUS,
        repository_state=state,
        subject_resolution=resolution,
        content=m.StatusContent(
            resolved_mode=m.StatusResolvedMode.UNRESOLVED,
        ),
        evidence=(),
        resolution_requirements=requirements,
        bounds=bounds,
        withheld_category=None,
        continuation_token=None,
    )


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
            store_readiness=m.StoreReadiness.UNAVAILABLE,
            recommended_action="verify repository availability",
        )
    if not _is_initialized(repository_id, store=store):
        return m.HookStatusNotice(
            store_readiness=m.StoreReadiness.UNINITIALIZED,
            recommended_action=(
                "run initialize_repository in a dedicated " "setup session"
            ),
        )
    if target is None:
        return m.HookStatusNotice(store_readiness=m.StoreReadiness.READY)
    if (
        isinstance(target, m.EvidenceScope)
        and not target.paths
        and not target.evidence_refs
    ):
        # Empty event scope carries no subjects. Hooks stay silent
        # (I-32); strict empty-scope rejection lives on NORMAL paths.
        subjects: tuple[m.Subject, ...] = ()
    elif isinstance(target, m.EvidenceScope):
        # One bounded frontier page. Hooks never allocate a continuation, so
        # the remainder is deliberately unseen (I-32 silence): work is
        # proportional to the page, not to the scope.
        subjects, _total, _fingerprint = resolve_scope_frontier(
            repository_id,
            target,
            structural=structural,
            evidence=evidence,
            store=store,
            bounds=bounds,
        )
    else:
        # A selector resolves its own candidates, already bounded by
        # ``max_subjects``.
        subjects, _ = _resolve_scope_subjects(
            repository_id,
            target,
            structural=structural,
            store=store,
            bounds=bounds,
            evidence=evidence,
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
        # SPMCP-05: name the exact resolution path and scope. A refresh
        # never accepts a bare count or an invented scope.
        locators = ", ".join(sorted(sid.canonical_locator for sid in affected))
        action = (
            f"run refresh with an exact SubjectSelector for: {locators} "
            f"({stale} stale, {unverifiable} unverifiable items)"
        )
    return m.HookStatusNotice(
        store_readiness=m.StoreReadiness.READY,
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
    precomputed_snapshots: (
        Mapping[m.EvidenceScope, tuple[str, dict[str, str]]] | None
    ) = None,
) -> tuple[m.SemanticCoverageEntry, tuple[m.ResolutionRequirement, ...]]:
    """Build one report entry from persisted semantic state only.

    G-16: path-like subjects absent from the evidence inventory read
    UNVERIFIABLE with an absence requirement, regardless of stale
    priors (a deleted file's old claims verify nothing).
    """
    claims, relationships, claim_token, rel_token = _load_subject_state(
        repository_id, subject.subject_id, store=store, bounds=bounds
    )
    semantic_ids: tuple[m.ClaimRef | m.RelationshipRef, ...] = tuple(
        _claim_ref(claim) for claim in claims
    ) + tuple(_relationship_ref(rel) for rel in relationships)
    updates, _ = _classify_current(
        repository_id,
        semantic_ids,
        evidence=evidence,
        store=store,
        bounds=bounds,
    )
    freshness_by_id = {claim.claim_id.value: claim.freshness.state for claim in claims}
    freshness_by_id.update(
        {rel.relationship_id.value: rel.freshness.state for rel in relationships}
    )
    freshness_by_id.update(
        {update.semantic_id.id.value: update.freshness.state for update in updates}
    )
    current_count = sum(
        state is m.FreshnessState.CURRENT for state in freshness_by_id.values()
    )
    stale_count = sum(
        state is m.FreshnessState.STALE for state in freshness_by_id.values()
    )
    unverifiable_count = sum(
        state is m.FreshnessState.UNVERIFIABLE for state in freshness_by_id.values()
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
                coverage,
                evidence=evidence,
                store=store,
                repository_id=repository_id,
                precomputed_snapshots=precomputed_snapshots,
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
        view.effective_disposition is m.SemanticQuestionDisposition.NOT_APPLICABLE
        for view in question_views
    )
    stale_effective_question_count = sum(
        view.freshness.state is m.FreshnessState.STALE for view in question_views
    )
    question_unverifiable = any(
        view.freshness.state is m.FreshnessState.UNVERIFIABLE for view in question_views
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
                    "semantic subject; run question-local explain for "
                    f"'{subject.subject_id.canonical_locator}'; a "
                    "continuation exists only after that operation "
                    "suspends"
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
    incomplete = bool(pending_count or open_count or question_remaining or truncated)
    if question_unverifiable or unverifiable_count:
        disposition = m.SemanticCoverageDisposition.UNVERIFIABLE
    elif stale_effective_question_count or stale_count:
        disposition = m.SemanticCoverageDisposition.STALE
    elif incomplete:
        disposition = m.SemanticCoverageDisposition.INCOMPLETE
    elif not question_views:
        disposition = m.SemanticCoverageDisposition.UNASSESSED
    else:
        disposition = m.SemanticCoverageDisposition.CURRENT
    if not requirements and disposition is not (m.SemanticCoverageDisposition.CURRENT):
        # Addendum G §4.2c fallback: every non-current repository entry
        # carries one actionable canonical requirement. Read-time
        # projection only; never persisted; never invents an objective.
        locator = subject.subject_id.canonical_locator
        if disposition is m.SemanticCoverageDisposition.STALE:
            requirements.append(
                m.ResolutionRequirement(
                    kind=m.ResolutionKind.STALE_EVIDENCE,
                    subject_or_claim=subject.subject_id,
                    description=(
                        "subject has stale semantic items; refresh the "
                        f"stale scope with an exact SubjectSelector for "
                        f"'{locator}' (use status to confirm the scope)"
                    ),
                    supporting_context=(),
                )
            )
        elif disposition is m.SemanticCoverageDisposition.UNVERIFIABLE:
            requirements.append(
                m.ResolutionRequirement(
                    kind=m.ResolutionKind.UNVERIFIABLE_FRESHNESS,
                    subject_or_claim=subject.subject_id,
                    description=(
                        "subject freshness cannot be established; refresh "
                        f"with an exact SubjectSelector for '{locator}'; "
                        "an UNVERIFIABLE empty result proves nothing"
                    ),
                    supporting_context=(),
                )
            )
        elif disposition is m.SemanticCoverageDisposition.UNASSESSED:
            requirements.append(
                m.ResolutionRequirement(
                    kind=m.ResolutionKind.MISSING_SEMANTIC_COVERAGE,
                    subject_or_claim=subject.subject_id,
                    description=(
                        "no adopted question coverage is persisted for this "
                        f"semantic subject; run question-local explain for "
                        f"'{locator}'; a continuation exists only after "
                        "that operation suspends"
                    ),
                    supporting_context=(),
                )
            )
        else:
            requirements.append(
                m.ResolutionRequirement(
                    kind=m.ResolutionKind.INCOMPLETE_SEMANTIC_SCOPE,
                    subject_or_claim=subject.subject_id,
                    description=(
                        "subject work is incomplete; continue the pending "
                        f"questions for '{locator}' within bounds through "
                        "the continuation returned by the suspending "
                        "operation; pass the returned continuation unchanged"
                    ),
                    supporting_context=(),
                )
            )
    locator = subject.subject_id.canonical_locator
    file_part = locator.split("#", 1)[0]
    basename = file_part.rsplit("/", 1)[-1]
    suffix = basename.rsplit(".", 1)[-1] if "." in basename else ""
    # Path-like (slash plus short file suffix) with persisted records:
    # pure-UNASSESSED subjects keep UNASSESSED, and semantic-only
    # identifiers without file shape never qualify.
    if (
        "/" in file_part
        and suffix.isalnum()
        and 1 <= len(suffix) <= 8
        and (semantic_ids or question_total)
    ):
        # G-16 ghost rule: a recorded path-like subject absent from the
        # evidence inventory reads UNVERIFIABLE with an explicit
        # absence requirement (restore, re-anchor, or retire the
        # record). Provider-agnostic inventory membership — never
        # filesystem walks. Inventory failure must not fake a ghost, so
        # a provider error propagates instead of reading as presence.
        present = evidence.inventory_evidence(
            repository_id,
            m.EvidenceScope(paths=(file_part,), evidence_refs=()),
            bounds,
        )
        ghost = not any(
            item.evidence_ref.locator == file_part for item in present.items
        )
        if ghost:
            disposition = m.SemanticCoverageDisposition.UNVERIFIABLE
            requirements.append(
                m.ResolutionRequirement(
                    kind=m.ResolutionKind.UNVERIFIABLE_FRESHNESS,
                    subject_or_claim=subject.subject_id,
                    description=(
                        f"recorded path '{file_part}' is absent from "
                        "the evidence inventory; restore the file, "
                        "re-anchor the subject to its moved location, "
                        "or retire the record — an UNVERIFIABLE empty "
                        "result proves nothing"
                    ),
                    supporting_context=(),
                )
            )
    entry = m.SemanticCoverageEntry(
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
        stale_effective_question_count=stale_effective_question_count,
        truncated=truncated,
    )
    return entry, tuple(requirements)


def _coverage_entries_for_subjects(
    repository_id: str,
    subjects: tuple[m.Subject, ...],
    *,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> tuple[tuple[m.SemanticCoverageEntry, ...], tuple[m.ResolutionRequirement, ...]]:
    """One coverage entry per frontier subject, and the page-level requirements."""
    # J-1/S1.5: group loaded dependencies by exact recorded discovery
    # scope. Each distinct scope receives one fresh membership walk.
    # Current persisted coverage always records a non-empty discovery
    # scope; an empty scope means whole-repository inventory only.
    # Snapshots are scoped to this status call and never shared across
    # operations. A store or provider failure here publishes no status:
    # an unread obligation would otherwise read as an absent one.
    coverages = store.load_coverage_dependencies(
        repository_id,
        tuple(s.subject_id for s in subjects),
    )
    scope_snapshots = _coverage_scope_snapshots(
        repository_id, coverages, evidence=evidence
    )
    built = tuple(
        _repository_coverage_entry(
            repository_id,
            subject,
            evidence=evidence,
            store=store,
            bounds=bounds,
            precomputed_snapshots=scope_snapshots,
        )
        for subject in subjects
    )
    return (
        tuple(entry for entry, _requirements in built),
        tuple(
            requirement
            for _entry, requirements in built
            for requirement in requirements
        ),
    )


def _repository_report(
    entries: tuple[m.SemanticCoverageEntry, ...],
    *,
    persisted_subject_count: int,
    question_counts: tuple[int, int] = (0, 0),
    target_counts: tuple[int, int, int, int | None] = (0, 0, 0, 0),
) -> m.RepositoryCoverageReport:
    """Repository coverage: exact totals in ``repository``, page in ``page``."""
    pending_question_count, open_question_count = question_counts
    (
        active_target_association_count,
        persisted_target_accounted_count,
        persisted_target_unresolved_count,
        bounded_live_target_unaccounted_count,
    ) = target_counts
    return m.RepositoryCoverageReport(
        repository=m.RepositoryTotals(
            persisted_subject_count=persisted_subject_count,
            pending_question_count=pending_question_count,
            open_question_count=open_question_count,
            active_target_association_count=active_target_association_count,
            persisted_target_accounted_count=persisted_target_accounted_count,
            persisted_target_unresolved_count=persisted_target_unresolved_count,
            bounded_live_target_unaccounted_count=(
                bounded_live_target_unaccounted_count
            ),
        ),
        page=m.CoveragePage(entries=entries),
    )


def _scoped_report(
    entries: tuple[m.SemanticCoverageEntry, ...],
    *,
    persisted_subject_count: int,
) -> m.ScopedCoverageReport:
    """Scoped coverage: scope totals in ``scope``, page in ``page``.

    No repository-global field exists on this type, so a scoped answer cannot
    publish one even by mistake.
    """
    return m.ScopedCoverageReport(
        scope=m.ScopeTotals(persisted_subject_count=persisted_subject_count),
        page=m.CoveragePage(entries=entries),
    )


def _target_burden_aggregates(
    repository_id: str,
    *,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> tuple[int, int, int | None]:
    """Read persisted target burden and bounded live unaccounted members."""
    accounted, unresolved = store.count_target_inventory_outcomes(repository_id)
    associations = store.load_active_target_associations(repository_id)
    live_unaccounted = 0
    try:
        for association in associations:
            inventory = enumerate_target_inventory(
                repository_id,
                association.target_scope,
                evidence=evidence,
                bounds=bounds,
            )
            accounted_ids = {
                item.evidence_ref.evidence_id.value
                for item in association.inventory_accounting
            }
            live_unaccounted += sum(
                item.evidence_ref.evidence_id.value not in accounted_ids
                for item in inventory
            )
    except ValueError:
        # A provider cannot establish the bounded live observation. Preserve
        # the exact persisted burden and mark the live projection unknown.
        live_unaccounted = None
    return accounted, unresolved, live_unaccounted


def _compose_repository_status_answer(
    repository_id: str,
    *,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    continuations: ContinuationStore,
    subject_offset: int = 0,
    mode: str = "NORMAL",
    page_token: str | None = None,
) -> m.SemanticAnswer:
    """Report persisted semantic coverage without structural enumeration."""
    _digest = _query_digest(
        "STATUS", repository_id, "repository", f"mode:{mode}", bounds
    )
    _validate_service_token(page_token, _digest)
    subject_page = store.load_repository_subjects(repository_id, bounds, subject_offset)
    entries, requirements = _coverage_entries_for_subjects(
        repository_id,
        subject_page.items,
        evidence=evidence,
        store=store,
        bounds=bounds,
    )
    live_records = _live_question_records(repository_id, None, continuations)
    repository_pending_requirements = _repository_pending_requirements(
        repository_id,
        entries,
        evidence=evidence,
        store=store,
        continuations=continuations,
    )
    requirements = _project_pending_requirements(
        requirements, repository_pending_requirements
    )
    requirements = _project_live_requirements(entries, requirements, live_records)
    _qdisp = store.count_question_dispositions(repository_id)
    (
        persisted_target_accounted_count,
        persisted_target_unresolved_count,
        bounded_live_target_unaccounted_count,
    ) = _target_burden_aggregates(
        repository_id, evidence=evidence, store=store, bounds=bounds
    )

    # A requirement belongs to the entry it describes. Admit entries while
    # their requirements fit the answer's ceiling instead of building every
    # entry and slicing the flattened requirement list afterwards: that slice
    # was silent, and the entries it cut never came back on the next page.
    by_subject: dict[m.SubjectId, list[m.ResolutionRequirement]] = {}
    for requirement in (*requirements, *repository_pending_requirements):
        if isinstance(requirement.subject_or_claim, m.SubjectId):
            by_subject.setdefault(requirement.subject_or_claim, []).append(requirement)

    repository_live_requirements = _repository_live_requirements(
        repository_id, continuations
    )
    remaining = max(0, bounds.max_results - len(repository_live_requirements))
    kept_entries: list[m.SemanticCoverageEntry] = []
    kept_requirements: list[m.ResolutionRequirement] = list(
        repository_live_requirements
    )
    for entry in entries:
        unit = by_subject.get(entry.subject, [])
        if len(unit) > remaining and kept_entries:
            break
        # One atomic unit alone exceeds the ceiling. It is emitted whole — an
        # item is never separated from its requirements — and the caller learns
        # the ceiling could not hold it. Declared in D1.
        kept_entries.append(entry)
        kept_requirements.extend(unit)
        remaining -= len(unit)
    page_cut = len(kept_entries) < len(entries)

    entries = tuple(kept_entries)
    requirements = tuple(dict.fromkeys(kept_requirements))
    # Addendum G §4.2b within-page display order only: deterministic by
    # (coverage-rank, open desc, pending desc, locator, kind). Pagination
    # stays locator order; truncation follows retention priority.
    _rank = {
        m.SemanticCoverageDisposition.STALE: 0,
        m.SemanticCoverageDisposition.UNVERIFIABLE: 1,
        m.SemanticCoverageDisposition.INCOMPLETE: 2,
        m.SemanticCoverageDisposition.UNASSESSED: 3,
        m.SemanticCoverageDisposition.CURRENT: 4,
    }
    entries = tuple(
        sorted(
            entries,
            key=lambda e: (
                _rank[e.disposition],
                -e.open_question_count,
                -e.pending_question_count,
                e.subject.canonical_locator,
                e.subject.subject_kind.value,
            ),
        )
    )
    report = _repository_report(
        entries,
        persisted_subject_count=store.count_repository_subjects(repository_id),
        question_counts=(
            _qdisp.get("PENDING", 0),
            _qdisp.get("OPEN", 0),
        ),
        target_counts=(
            store.count_target_associations(repository_id),
            persisted_target_accounted_count,
            persisted_target_unresolved_count,
            bounded_live_target_unaccounted_count,
        ),
    )
    # Answer-level truncation describes the answer. An entry that reports its
    # own scan was cut carries ``entry.truncated``; folding that into the
    # answer produced ``truncated: true`` with no answer cursor, which is the
    # non-resumable shape this release removes.
    # ``oversized_unit`` does not set truncation: the unit was emitted whole,
    # so nothing was withheld. The ceiling breach is visible in the count.
    truncated = subject_page.bound_info.truncated or page_cut
    next_token = None
    if subject_page.bound_info.truncated or page_cut:
        next_token = _paging.format_service_token(
            subject_offset + len(entries),
            None,
            0,
            query_digest=_digest,
        )
    category = (
        subject_page.bound_info.truncated_category
        if subject_page.bound_info.truncated
        else "semantic_frontier" if page_cut else None
    )
    content = m.StatusContent(
        resolved_mode=m.StatusResolvedMode.REPOSITORY,
        store_readiness=m.StoreReadiness.READY,
        coverage_report=report,
    )
    return ANSWER_ASSEMBLER.build(
        answer_id=_answer_id(
            "stt",
            repository_id,
            f"repository-coverage:{subject_offset}",
        ),
        intent=m.SemanticIntent.STATUS,
        repository_state=state,
        subject_resolution=None,
        content=content,
        evidence=(),
        resolution_requirements=requirements,
        bounds=bounds,
        withheld_category=category,
        continuation_token=next_token,
        state_explanation=_status_state_explanation(
            state_explanation_for((), (), bounds=(bounds.max_results, truncated)),
            content,
            requirements,
        ),
    )


def _repository_status_page(
    request: SemanticStatusRequest,
    *,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    continuations: ContinuationStore,
) -> m.SemanticAnswer:
    """Resolve the normal no-target repository report page."""
    try:
        token_digest, subject_skip, rel_skip, question_skip = (
            _paging.parse_service_token_bound(request.page_token)
        )
    except ValueError as exc:
        raise StatusTargetError(str(exc)) from None
    if rel_skip or question_skip:
        raise StatusTargetError(
            "page token is invalid for this request; restart pagination "
            "from the first page with page_token omitted"
        )
    expected = _query_digest(
        "STATUS",
        request.repository_id,
        "repository",
        f"mode:{request.mode.value}",
        bounds,
    )
    if request.page_token is not None and token_digest != expected:
        raise StatusTargetError(
            "page token is invalid for this request; restart pagination "
            "from the first page with page_token omitted"
        )
    return _compose_repository_status_answer(
        request.repository_id,
        evidence=evidence,
        store=store,
        bounds=bounds,
        state=state,
        continuations=continuations,
        subject_offset=subject_skip,
        mode=request.mode.value,
        page_token=request.page_token,
    )


def _campaign_lifespan(association: m.TargetAssociation) -> m.HandleLifespan:
    """The handle exists, so it states its own retention and recovery."""
    return m.HandleLifespan(
        kind=m.HandleKind.DURABLE,
        scope=m.HandleScope.REPOSITORY,
        expires_at=association.expires_at,
        recovery=m.HandleRecovery.REINITIALIZE_TARGET,
    )


def _target_status_answer(
    repository_id: str,
    target_id: m.TargetId,
    *,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    continuations: ContinuationStore,
) -> m.SemanticAnswer:
    """Campaign readback: absent → UNASSESSED, then UNVERIFIABLE→STALE→INCOMPLETE→CURRENT."""
    assoc = store.load_target_association(repository_id, target_id)
    if assoc is None:
        # Unknown and expired look the same in storage: the row is reaped. Say
        # both and name the recovery instead of reporting a bare UNASSESSED.
        expired_requirement = m.ResolutionRequirement(
            kind=m.ResolutionKind.MISSING_SEMANTIC_COVERAGE,
            subject_or_claim=None,
            description=(
                "campaign handle is unknown or expired; re-run "
                "initialize_target with the same target scope and objective"
            ),
            supporting_context=(),
        )
        content = m.StatusContent(
            resolved_mode=m.StatusResolvedMode.CAMPAIGN,
            target_association=None,
            target_disposition=m.SemanticCoverageDisposition.UNASSESSED,
            target_total_count=None,
            target_accounted_count=None,
            target_unaccounted_count=None,
        )
        return ANSWER_ASSEMBLER.build(
            answer_id=_answer_id("stt", repository_id, "target"),
            intent=m.SemanticIntent.STATUS,
            repository_state=state,
            subject_resolution=None,
            content=content,
            evidence=(),
            resolution_requirements=(expired_requirement,),
            bounds=bounds,
            withheld_category=None,
            continuation_token=None,
            state_explanation=_status_state_explanation(
                state_explanation_for((), (), bounds=(bounds.max_results, False)),
                content,
                (),
            ),
        )
    try:
        from span.service.discovery import enumerate_target_inventory

        inv_items = enumerate_target_inventory(
            repository_id,
            assoc.target_scope,
            evidence=evidence,
            bounds=bounds,
        )
    except ValueError:
        # The provider refuses to establish the bounded live observation
        # for this scope. That is a fact about the repository, so the
        # campaign reads UNVERIFIABLE; any other failure is a defect and
        # propagates rather than borrowing a semantic status.
        content = m.StatusContent(
            resolved_mode=m.StatusResolvedMode.CAMPAIGN,
            target_association=assoc,
            target_disposition=m.SemanticCoverageDisposition.UNVERIFIABLE,
            target_total_count=None,
            target_accounted_count=None,
            target_unaccounted_count=None,
            target_handle_lifespan=_campaign_lifespan(assoc),
        )
        return ANSWER_ASSEMBLER.build(
            answer_id=_answer_id("stt", repository_id, "target"),
            intent=m.SemanticIntent.STATUS,
            repository_state=state,
            subject_resolution=None,
            content=content,
            evidence=(),
            resolution_requirements=(),
            bounds=bounds,
            withheld_category=None,
            continuation_token=None,
            state_explanation=_status_state_explanation(
                state_explanation_for((), (), bounds=(bounds.max_results, False)),
                content,
                (),
            ),
        )
    current_fp = m.target_inventory_fingerprint(inv_items)
    if len(assoc.inventory_accounting) > bounds.max_results:
        # Bounded projection first (governing precedence UNVERIFIABLE
        # → STALE → INCOMPLETE → CURRENT): completeness cannot be
        # proven within bounds, even when membership also drifted.
        content = m.StatusContent(
            resolved_mode=m.StatusResolvedMode.CAMPAIGN,
            target_association=assoc,
            target_disposition=m.SemanticCoverageDisposition.UNVERIFIABLE,
            target_total_count=None,
            target_accounted_count=None,
            target_unaccounted_count=None,
            target_handle_lifespan=_campaign_lifespan(assoc),
        )
        return ANSWER_ASSEMBLER.build(
            answer_id=_answer_id("stt", repository_id, "target"),
            intent=m.SemanticIntent.STATUS,
            repository_state=state,
            subject_resolution=None,
            content=content,
            evidence=(),
            resolution_requirements=(),
            bounds=bounds,
            withheld_category=None,
            continuation_token=None,
            state_explanation=_status_state_explanation(
                state_explanation_for((), (), bounds=(bounds.max_results, False)),
                content,
                (),
            ),
        )
    if current_fp != assoc.inventory_fingerprint:
        current_ids = {item.evidence_ref.evidence_id.value for item in inv_items}
        accounted_now = sum(
            1
            for acc in assoc.inventory_accounting
            if acc.evidence_ref.evidence_id.value in current_ids
        )
        content = m.StatusContent(
            resolved_mode=m.StatusResolvedMode.CAMPAIGN,
            target_association=assoc,
            target_disposition=m.SemanticCoverageDisposition.STALE,
            target_total_count=len(inv_items),
            target_accounted_count=accounted_now,
            target_unaccounted_count=len(inv_items) - accounted_now,
            target_handle_lifespan=_campaign_lifespan(assoc),
        )
        return ANSWER_ASSEMBLER.build(
            answer_id=_answer_id("stt", repository_id, "target"),
            intent=m.SemanticIntent.STATUS,
            repository_state=state,
            subject_resolution=None,
            content=content,
            evidence=(),
            resolution_requirements=(
                m.ResolutionRequirement(
                    kind=m.ResolutionKind.STALE_EVIDENCE,
                    subject_or_claim=None,
                    description=(
                        "STALE means target membership changed since "
                        "campaign establishment. It is distinct from "
                        "semantic evidence freshness. Re-run "
                        "initialize_target for the same exact target "
                        "and objective."
                    ),
                    supporting_context=(),
                ),
            ),
            bounds=bounds,
            withheld_category=None,
            continuation_token=None,
            state_explanation=_status_state_explanation(
                state_explanation_for((), (), bounds=(bounds.max_results, False)),
                content,
                (),
            ),
        )
    accounted = {
        acc.evidence_ref.evidence_id.value: acc for acc in assoc.inventory_accounting
    }
    # Global precedence: evaluate the whole campaign, then apply
    # UNVERIFIABLE -> STALE -> INCOMPLETE -> CURRENT. Everything below
    # accumulates flags across all members, areas, and questions.
    # Membership staleness is the inventory fingerprint above; content
    # freshness for stable members is owned exclusively by the existing
    # evidence/question/claim/relationship dependency machinery below
    # (§§4C.6B/4C.6E). Target accounting carries no content fingerprint.
    saw_unverifiable = False
    saw_stale = False
    saw_incomplete = False
    residual: list[m.ResolutionRequirement] = []
    live_requirements = _target_live_requirements(
        repository_id,
        target_id,
        assoc,
        evidence=evidence,
        store=store,
        continuations=continuations,
    )
    residual.extend(live_requirements)
    live_mapping = any(
        record.repository_id == repository_id
        and record.target_id == target_id
        and record.request.question is None
        for record in continuations.live_records()
    )
    saw_incomplete = bool(live_requirements)
    unaccounted = False
    for item in inv_items:
        eid = item.evidence_ref.evidence_id.value
        if eid not in accounted:
            saw_incomplete = True
            unaccounted = True
            continue
        if accounted[eid].resolution_requirements:
            saw_incomplete = True
            residual.extend(accounted[eid].resolution_requirements)
    if unaccounted and not live_mapping:
        residual.append(
            m.ResolutionRequirement(
                kind=m.ResolutionKind.INCOMPLETE_SEMANTIC_SCOPE,
                subject_or_claim=None,
                description=(
                    f"target '{target_id.value}' has unaccounted inventory "
                    "and no live initialize_target continuation; rerun "
                    "initialize_target with the same exact target scope and "
                    f"objective '{assoc.objective}'; do not synthesize a "
                    "continuation"
                ),
                supporting_context=(),
            )
        )
    questions_by_area: dict[m.SubjectId, list[m.SemanticQuestionScope]] = {}
    for q in assoc.target_questions:
        questions_by_area.setdefault(q.scope_root, []).append(q)
    for area in assoc.area_subjects:
        if area not in questions_by_area:
            saw_incomplete = True
    for q in assoc.target_questions:
        anchors = store.load_subjects(repository_id, (q.subject,))
        anchor_requirement = None
        if anchors is not None and not anchors:
            # §4C.6D amendment (answerability, 2026-10-11): an admitted
            # question with no established anchor can never suspend.
            # Name it instead of sinking it into silent INCOMPLETE.
            anchor_requirement = m.ResolutionRequirement(
                kind=m.ResolutionKind.MISSING_SEMANTIC_COVERAGE,
                subject_or_claim=q.subject,
                description=(
                    "question subject anchor is not established: admit "
                    + q.subject.canonical_locator
                    + " as CandidateSubject on its structural entrypoint, "
                    "then re-kick initialize_target"
                ),
                supporting_context=(),
            )
        coverages = store.load_all_question_coverages(
            repository_id,
            q.scope_root,
            (q.subject,),
        )
        match = None
        for cov in coverages:
            if cov.question is None:
                continue
            if (
                cov.question.scope_root == q.scope_root
                and cov.question.subject == q.subject
                and cov.question.question_class == q.question_class
                and cov.question.question_slice == q.question_slice
            ):
                match = cov
                break
        if match is None:
            saw_incomplete = True
            if anchor_requirement is not None:
                residual.append(anchor_requirement)
            continue
        # Canonical freshness: effective disposition + dependency state.
        view = effective_question_view(
            match,
            evidence=evidence,
            store=store,
            repository_id=repository_id,
        )
        if view.freshness.state is m.FreshnessState.UNVERIFIABLE:
            saw_unverifiable = True
        elif view.freshness.state is m.FreshnessState.STALE:
            saw_stale = True
        elif view.effective_disposition in (
            m.SemanticQuestionDisposition.PENDING,
            m.SemanticQuestionDisposition.OPEN,
        ):
            saw_incomplete = True
            residual.extend(view.resolution_requirements)
            if anchor_requirement is not None:
                residual.append(anchor_requirement)
        elif view.effective_disposition not in (
            m.SemanticQuestionDisposition.ANSWERED,
            m.SemanticQuestionDisposition.NOT_APPLICABLE,
        ):
            saw_incomplete = True
    if saw_unverifiable:
        disposition = m.SemanticCoverageDisposition.UNVERIFIABLE
    elif saw_stale:
        disposition = m.SemanticCoverageDisposition.STALE
    elif saw_incomplete:
        disposition = m.SemanticCoverageDisposition.INCOMPLETE
    else:
        disposition = m.SemanticCoverageDisposition.CURRENT
    if disposition is m.SemanticCoverageDisposition.UNVERIFIABLE:
        total_count = accounted_count = unaccounted_count = None
    else:
        current_ids = {item.evidence_ref.evidence_id.value for item in inv_items}
        total_count = len(inv_items)
        accounted_count = sum(1 for eid in accounted if eid in current_ids)
        unaccounted_count = total_count - accounted_count
    content = m.StatusContent(
        resolved_mode=m.StatusResolvedMode.CAMPAIGN,
        target_association=assoc,
        target_disposition=disposition,
        target_total_count=total_count,
        target_accounted_count=accounted_count,
        target_unaccounted_count=unaccounted_count,
        target_handle_lifespan=_campaign_lifespan(assoc),
    )
    requirements = tuple(residual) if saw_incomplete else ()
    if live_requirements:
        requirements = tuple(dict.fromkeys((*requirements, *live_requirements)))
    return ANSWER_ASSEMBLER.build(
        answer_id=_answer_id("stt", repository_id, "target"),
        intent=m.SemanticIntent.STATUS,
        repository_state=state,
        subject_resolution=None,
        content=content,
        evidence=(),
        resolution_requirements=requirements,
        bounds=bounds,
        withheld_category=None,
        continuation_token=None,
        state_explanation=_status_state_explanation(
            state_explanation_for((), (), bounds=(bounds.max_results, False)),
            content,
            requirements,
        ),
    )


def _derived_verification_status(
    repository_id: str,
    state: m.RepositoryState,
    claim: m.SemanticClaim,
    *,
    store: SemanticStore,
) -> m.VerificationStatus:
    """Project one verification link's currency from its execution record.

    The record key is the evaluated scope of the link's own evidence, so
    the read agrees with the write by construction. No record → UNKNOWN;
    a record from another revision → STALE; otherwise the exit status
    decides PASS or FAIL.
    """
    link = claim.value
    assert isinstance(link, m.VerificationValue)
    scope = m.EvidenceScope(
        paths=tuple(sorted({ref.locator for ref in claim.evidence})),
        evidence_refs=(),
    )
    record = store.load_verification_record(
        repository_id,
        link.verification_ref,
        m.evidence_scope_fingerprint(scope),
    )
    if record is None:
        currency = m.DerivedCurrency.UNKNOWN
    elif record.observed_revision != state.revision_id:
        currency = m.DerivedCurrency.STALE
    elif record.exit_status == 0:
        currency = m.DerivedCurrency.CURRENT_PASS
    else:
        currency = m.DerivedCurrency.CURRENT_FAIL
    return m.VerificationStatus(
        verification_ref=link.verification_ref,
        kind=link.kind,
        currency=currency,
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
    continuations: ContinuationStore,
    page_token: str | None = None,
    scope: m.EvidenceScope | None = None,
    frontier_total: int | None = None,
    frontier_offset: int = 0,
    frontier: str = "",
) -> m.SemanticAnswer:
    if len(subjects) == 1:
        _sid = subjects[0].subject_id
        _target_key = f"{_sid.subject_kind.value}:{_sid.canonical_locator}"
    else:
        _target_key = "scope:" + ",".join(
            sorted(
                f"{s.subject_id.subject_kind.value}:"
                f"{s.subject_id.canonical_locator}"
                for s in subjects
            )
        )
    _digest = _query_digest("STATUS", repository_id, _target_key, "", bounds)
    if page_token is not None and page_token.startswith("pgv:"):
        # A frontier cursor binds the exact membership; drift restarts.
        if not frontier:
            raise StaleContinuationError(
                "page token is invalid for this request; restart pagination "
                "from the first page with page_token omitted"
            )
        try:
            _paging.parse_versioned_token(page_token, version=_digest + frontier)
        except ValueError as exc:
            raise StaleContinuationError(str(exc)) from None
    else:
        _validate_service_token(page_token, _digest)
    all_claims: list[m.SemanticClaim] = []
    all_rels: list[m.SemanticRelationship] = []
    first_claims_token: str | None = None
    first_rels_token: str | None = None
    for position, subject in enumerate(subjects):
        claims, relationships, tok_c, tok_r = _load_subject_state(
            repository_id,
            subject.subject_id,
            store=store,
            bounds=bounds,
            page_token=page_token if len(subjects) == 1 else None,
        )
        all_claims.extend(claims)
        all_rels.extend(relationships)
        if position == 0:
            first_claims_token, first_rels_token = tok_c, tok_r
    # S2 §5.2 read-only route: evaluate via the non-persisting
    # classifier (direct + premise live overlay + discovery) and project
    # returned freshness onto answer items only. No preflight, no
    # coverage_check persistence, no _refresh_view store writes.
    pre_ids: tuple[m.ClaimRef | m.RelationshipRef, ...] = tuple(
        _claim_ref(c) for c in all_claims
    ) + tuple(_relationship_ref(r) for r in all_rels)
    all_items = tuple(all_claims) + tuple(all_rels)
    updates, dependencies = _evaluate_current(
        repository_id,
        pre_ids,
        all_items,
        evidence=evidence,
        store=store,
        bounds=bounds,
    )
    live_states: dict[str, m.FreshnessState] = {
        u.semantic_id.id.value: u.freshness.state for u in updates
    }
    updated_ids = set(live_states)
    # Items without updates are CURRENT in the live overlay.
    for ref in pre_ids:
        live_states.setdefault(ref.id.value, m.FreshnessState.CURRENT)
    changed = tuple(
        dep for dep in dependencies if dep.semantic_id.id.value in updated_ids
    )
    stale_evidence = {
        dep.evidence_ref.locator
        for dep in dependencies
        if dep.semantic_id.id.value in updated_ids
    }
    by_id = {u.semantic_id.id.value: u.freshness for u in updates}

    def _with_live_claim(claim: m.SemanticClaim) -> m.SemanticClaim:
        freshness = by_id.get(claim.claim_id.value)
        if freshness is None:
            return claim
        return m.SemanticClaim(
            claim_id=claim.claim_id,
            subject=claim.subject,
            kind=claim.kind,
            value=claim.value,
            assertion_nature=claim.assertion_nature,
            evidence=claim.evidence,
            authority=claim.authority,
            trust=claim.trust,
            freshness=freshness,
            basis=claim.basis,
        )

    def _with_live_rel(
        rel: m.SemanticRelationship,
    ) -> m.SemanticRelationship:
        freshness = by_id.get(rel.relationship_id.value)
        if freshness is None:
            return rel
        return m.SemanticRelationship(
            relationship_id=rel.relationship_id,
            source=rel.source,
            kind=rel.kind,
            target=rel.target,
            assertion_nature=rel.assertion_nature,
            evidence=rel.evidence,
            authority=rel.authority,
            trust=rel.trust,
            freshness=freshness,
            basis=rel.basis,
        )

    claims_t = tuple(_with_live_claim(c) for c in all_claims)
    rels_t = tuple(_with_live_rel(r) for r in all_rels)
    verification_all = tuple(
        _derived_verification_status(repository_id, state, claim, store=store)
        for claim in claims_t
        if claim.kind is m.ClaimKind.VERIFICATION
        and isinstance(claim.value, m.VerificationValue)
    )
    conflicts_all = _conflicts_for(
        repository_id, tuple(claims_t), tuple(rels_t), store=store
    )
    kept_claims, kept_rels, kept_conf, items_truncated, items_category = (
        _select_answer_items(claims_t, rels_t, conflicts_all, bounds.max_results)
    )
    kept_ids = {c.claim_id.value for c in kept_claims} | {
        r.relationship_id.value for r in kept_rels
    }
    changed_kept = tuple(dep for dep in changed if dep.semantic_id.id.value in kept_ids)
    unresolved: list[m.ResolutionRequirement] = []
    for claim in kept_claims:
        unresolved.extend(_answers.requirements_for_claim(claim))
    for rel in kept_rels:
        unresolved.extend(_answers.requirements_for_relationship(rel))
    # Non-ref lists (evidence pointers and values, never semantic refs)
    # take the remaining budget deterministically.
    rest_budget = max(0, bounds.max_results - len(kept_conf) - len(kept_claims))
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
            repository_id,
            subjects[0].subject_id,
            tuple(s.subject_id for s in subjects),
            store=store,
            bounds=bounds,
            page_token=page_token,
            evidence=evidence,
            live_states=live_states,
        )
        token: str | None = _next_service_token(
            page_token,
            kept_claims,
            kept_rels,
            claims_t,
            rels_t,
            first_claims_token,
            first_rels_token,
            questions_skip=qshown,
            questions_remaining=qremaining,
            query_digest=_digest,
        )
    else:
        views, _, qremaining = _paged_question_views(
            repository_id,
            None,
            tuple(s.subject_id for s in subjects),
            store=store,
            bounds=bounds,
            page_token=None,
            evidence=evidence,
            live_states=live_states,
        )
        token = None
    if qremaining > 0:
        truncated = True
        category = category or "question_coverage"
    pending_requirements = tuple(
        dict.fromkeys(
            (
                *_pending_exchange_requirements(repository_id, views, continuations),
                *_live_subject_requirements(repository_id, subjects, continuations),
            )
        )
    )
    # Whole-frontier accounting for the exact scope (Addendum E E-13):
    # one typed disposition per frontier subject, UNASSESSED where no
    # coverage was adopted. Read-time projection over persisted state;
    # no new store, no second writer. Answer-level unresolved/truncation
    # math below is unchanged.
    frontier_entries, frontier_requirements = _coverage_entries_for_subjects(
        repository_id,
        subjects,
        evidence=evidence,
        store=store,
        bounds=bounds,
    )
    frontier_requirements = _project_pending_requirements(
        frontier_requirements, pending_requirements
    )
    live_records = _live_question_records(repository_id, subjects, continuations)
    frontier_requirements = _project_live_requirements(
        frontier_entries, frontier_requirements, live_records
    )
    frontier_report = _scoped_report(
        frontier_entries,
        persisted_subject_count=(
            store.count_subjects_in_scope(repository_id, scope)
            if scope is not None
            else len(subjects)
        ),
    )
    unresolved = tuple(
        dict.fromkeys((*unresolved, *pending_requirements, *frontier_requirements))
    )
    # One ceiling over the answer's leaves. Item-shaped leaves were selected
    # against max_results already; everything else is fitted to what remains.
    # A claim or relationship carries one freshness item, so each costs two.
    fixed = len(kept_claims) + len(kept_rels) + len(kept_conf)
    remaining = max(0, bounds.max_results - fixed)
    kept_views = views[:remaining]
    remaining -= len(kept_views)
    kept_unresolved = unresolved[:remaining]
    remaining -= len(kept_unresolved)
    kept_changed = kept_changed[:remaining]
    remaining -= len(kept_changed)
    kept_ver = kept_ver[:remaining]
    leaves_dropped = (
        len(kept_views) < len(views)
        or len(kept_unresolved) < len(unresolved)
        or len(kept_changed) < len(changed_kept)
        or len(kept_ver) < len(verification_all)
    )
    if leaves_dropped and category is None:
        category = "unresolved"
    progress = frontier_offset + len(subjects)
    frontier_truncated = frontier_total is not None and progress < frontier_total
    if frontier_truncated:
        truncated = True
        category = category or "semantic_subjects"
        token = _paging.format_versioned_token(_digest + frontier, progress)
    if leaves_dropped:
        truncated = True
    content = m.StatusContent(
        resolved_mode=m.StatusResolvedMode.SCOPED,
        store_readiness=m.StoreReadiness.READY,
        freshness_items=_freshness_items_for(kept_claims, kept_rels),
        changed_dependencies=kept_changed,  # type: ignore[arg-type]
        verification_status=kept_ver,  # type: ignore[arg-type]
        refresh_scope=m.EvidenceScope(
            paths=tuple(sorted(stale_evidence)), evidence_refs=()
        ),
        claims=kept_claims,
        relationships=kept_rels,
        conflicts=kept_conf,
        question_coverage=kept_views,
        coverage_report=frontier_report,
    )
    return ANSWER_ASSEMBLER.build(
        answer_id=_answer_id(
            "stt",
            repository_id,
            ",".join(s.subject_id.canonical_locator for s in subjects) or "scope",
        ),
        intent=m.SemanticIntent.STATUS,
        repository_state=state,
        subject_resolution=None,
        content=content,
        evidence=tuple(ref for c in kept_claims for ref in c.evidence),
        resolution_requirements=kept_unresolved,
        bounds=bounds,
        withheld_category=category,
        continuation_token=token,
        state_explanation=_status_state_explanation(
            state_explanation_for(
                tuple(kept_claims),
                tuple(kept_rels),
                coverage=coverage_counts_for(kept_views),
                bounds=(bounds.max_results, truncated),
                derived_currencies=tuple(
                    sorted({currency_literal(status.currency) for status in kept_ver})
                ),
            ),
            content,
            kept_unresolved,
        ),
    )


def status(
    request: SemanticStatusRequest,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationStore,
    authority_seeds: tuple[m.EvidenceRef, ...] = (),
) -> m.SemanticAnswer | m.HookStatusNotice:
    """Currency operation (plan §11.8; Addendum I S2 observational).

    NORMAL performs the full bounded read-only status operation over
    existing knowledge plus live freshness qualifications. It never
    initiates interpretation, allocates continuations, or persists
    freshness. Unexamined subjects return explicit missing coverage
    with next-operation guidance. HOOK_FAST is read-only lifecycle
    observation returning a compact notice — never suspension, never
    writes. Claim/relationship targets resolve through the §5.5 ref
    lookup; answer envelopes are never persisted (StatusTargetError).

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
    bounds = _resolve_bounds(
        request.bounds, hook=request.mode is m.StatusMode.HOOK_FAST
    )
    if isinstance(request.target, m.TargetId):
        if request.mode is m.StatusMode.HOOK_FAST:
            raise StatusTargetError("campaign status requires StatusMode.NORMAL")
        state = structural.repository_state(request.repository_id)
        if not _is_initialized(request.repository_id, store=store):
            return _uninitialized_answer(
                m.SemanticIntent.STATUS,
                request.repository_id,
                bounds,
                state,
            )
        return _target_status_answer(
            request.repository_id,
            request.target,
            evidence=evidence,
            store=store,
            bounds=bounds,
            state=state,
            continuations=continuations,
        )
    if request.mode is m.StatusMode.HOOK_FAST:
        return _hook_fast(
            request.repository_id,
            request.target,
            structural=structural,
            evidence=evidence,
            store=store,
            bounds=bounds,
        )
    if isinstance(request.target, (m.ClaimRef, m.RelationshipRef)):
        try:
            (item,) = store.load_by_refs(request.repository_id, (request.target,))
        except ValueError as exc:
            raise StatusTargetError(str(exc)) from None
        state = structural.repository_state(request.repository_id)
        if not _is_initialized(request.repository_id, store=store):
            return _uninitialized_answer(
                m.SemanticIntent.STATUS,
                request.repository_id,
                bounds,
                state,
            )
        sid = item.subject if isinstance(item, m.SemanticClaim) else item.source
        subjects = store.load_subjects(request.repository_id, (sid,))
        if not subjects:
            raise StatusTargetError("referenced subject is not indexed")
        return _compose_status_answer(
            request.repository_id,
            subjects,
            structural=structural,
            evidence=evidence,
            store=store,
            bounds=bounds,
            state=state,
            continuations=continuations,
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
            continuations=continuations,
        )
    subjects, ambiguity, resolution = _resolve_status_subjects(
        request.repository_id,
        request.target,
        structural=structural,
        store=store,
        evidence=evidence,
        bounds=bounds,
    )
    if ambiguity is not m.ResolutionAmbiguity.RESOLVED or not subjects:
        return _unresolved_status_answer(
            request.repository_id,
            request.target,
            resolution,
            state=state,
            bounds=bounds,
        )
    # S2 §5.2 observational status: never suspend, never persist.
    # Unexamined subjects return explicit missing coverage with
    # next-operation guidance from _compose_status_answer; absent,
    # ambiguous, unexamined, stale, and unverifiable stay distinct.
    if isinstance(request.target, m.EvidenceScope):
        offset = 0
        if request.page_token is not None and request.page_token.startswith("pgv:"):
            offset = _scope_page_offset(request.page_token)
        subjects, total, fingerprint = resolve_scope_frontier(
            request.repository_id,
            request.target,
            structural=structural,
            evidence=evidence,
            store=store,
            bounds=bounds,
            offset=offset,
        )
        return _compose_status_answer(
            request.repository_id,
            subjects,
            structural=structural,
            evidence=evidence,
            store=store,
            bounds=bounds,
            state=state,
            continuations=continuations,
            page_token=request.page_token,
            scope=request.target,
            frontier_total=total,
            frontier_offset=offset,
            frontier=fingerprint,
        )
    return _compose_status_answer(
        request.repository_id,
        subjects,
        structural=structural,
        evidence=evidence,
        store=store,
        bounds=bounds,
        state=state,
        continuations=continuations,
        page_token=request.page_token,
    )
