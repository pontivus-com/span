"""Span scoped status composition (plan §11.8; v0.6 §14 Amendment A-01).

One page of one status scope: identity, live overlay, item selection, question
views, frontier accounting, the single leaf ceiling, and the cursor.
"""

from __future__ import annotations

import dataclasses as _dataclasses

from span.core import answers as _answers
from span.core import model as m
from span.ports.evidence import EvidenceSource
from span.ports.store import SemanticStore
from span.ports.structural import StructuralSource
from span.ports.continuation import ContinuationPort

from span.service.answers import (
    _answer_id,
    ANSWER_ASSEMBLER,
    _freshness_items_for,
    _next_service_offsets,
    _select_answer_items,
    coverage_counts_for,
    currency_literal,
    state_explanation_for,
)
from span.service.operations.status.delivery import (
    _Delivered,
    _delivered_state,
    _delivered_views,
    _page_identity,
)
from span.service.operations.status.coverage import (
    _coverage_entries_for_subjects,
    _scoped_report,
)
from span.service.operations.status.explanation import (
    _status_state_explanation,
)
from span.service.operations.status.tokens import (
    _format_question_token,
    _format_scope_token,
    _format_versioned_token,
)
from span.service.operations.status.requirements import (
    _live_question_records,
    _live_subject_requirements,
    _pending_exchange_requirements,
    _project_live_requirements,
    _project_pending_requirements,
)


@_dataclasses.dataclass
@_dataclasses.dataclass
@_dataclasses.dataclass
class _Selected:
    """The page's admitted items and the full leaves awaiting the ceiling."""

    claims: tuple[m.SemanticClaim, ...]
    relationships: tuple[m.SemanticRelationship, ...]
    conflicts: tuple[m.SemanticConflict, ...]
    changed: tuple[m.EvidenceDependency, ...]
    unresolved: list[m.ResolutionRequirement]
    verification: tuple[m.VerificationStatus, ...]
    truncated: bool
    category: str | None


@_dataclasses.dataclass
class _LeafPage:
    """The answer's leaves after the single ceiling, and its truncation."""

    views: tuple[m.SemanticQuestionCoverageView, ...]
    unresolved: tuple[m.ResolutionRequirement, ...]
    changed: tuple[m.EvidenceDependency, ...]
    verification: tuple[m.VerificationStatus, ...]
    truncated: bool
    category: str | None
    dropped: bool


def _select_delivered(
    delivered: _Delivered,
    *,
    bounds: m.QueryBounds,
) -> _Selected:
    """Admit items at the answer ceiling and collect the full leaf lists."""
    kept_claims, kept_rels, kept_conf, items_truncated, items_category = (
        _select_answer_items(
            delivered.claims,
            delivered.relationships,
            delivered.conflicts,
            bounds.max_results,
        )
    )
    kept_ids = {claim.claim_id.value for claim in kept_claims} | {
        relationship.relationship_id.value for relationship in kept_rels
    }
    changed_kept = tuple(
        dependency
        for dependency in delivered.changed
        if dependency.semantic_id.id.value in kept_ids
    )
    unresolved: list[m.ResolutionRequirement] = []
    for claim in kept_claims:
        unresolved.extend(_answers.requirements_for_claim(claim))
    for relationship in kept_rels:
        unresolved.extend(_answers.requirements_for_relationship(relationship))
    return _Selected(
        claims=kept_claims,
        relationships=kept_rels,
        conflicts=kept_conf,
        changed=changed_kept,
        unresolved=unresolved,
        verification=delivered.verification,
        truncated=items_truncated,
        category=items_category,
    )


def _frontier_section(
    repository_id: str,
    subjects: tuple[m.Subject, ...],
    *,
    scope: m.EvidenceScope | None,
    pending_requirements: tuple[m.ResolutionRequirement, ...],
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    continuations: ContinuationPort,
) -> tuple[tuple[m.ResolutionRequirement, ...], m.ScopedCoverageReport]:
    """One typed disposition per frontier subject, with projected requirements."""
    entries, requirements = _coverage_entries_for_subjects(
        repository_id,
        subjects,
        evidence=evidence,
        store=store,
        bounds=bounds,
    )
    requirements = _project_pending_requirements(requirements, pending_requirements)
    live_records = _live_question_records(repository_id, subjects, continuations)
    requirements = _project_live_requirements(entries, requirements, live_records)
    report = _scoped_report(
        entries,
        persisted_subject_count=(
            store.count_subjects_in_scope(repository_id, scope)
            if scope is not None
            else len(subjects)
        ),
    )
    return requirements, report


def _leaf_ceiling(
    selected: _Selected,
    views: tuple[m.SemanticQuestionCoverageView, ...],
    *,
    single_subject_scope: bool,
    bounds: m.QueryBounds,
    truncated: bool,
    category: str | None,
) -> _LeafPage:
    """Fit every leaf to the one answer ceiling.

    Non-ref leaves take the remaining budget deterministically; a
    single-subject scope page is one atomic unit, so its requirements, changed
    dependencies, and verification travel with its claims instead of being cut
    where no cursor can name the position.
    """
    if single_subject_scope:
        return _LeafPage(
            views=views,
            unresolved=tuple(selected.unresolved),
            changed=selected.changed,
            verification=selected.verification,
            truncated=truncated,
            category=category,
            dropped=False,
        )
    unresolved = tuple(selected.unresolved)
    rest_budget = max(
        0,
        bounds.max_results - len(selected.conflicts) - len(selected.claims),
    )
    kept_unresolved = unresolved[:rest_budget]
    kept_changed = selected.changed[: max(0, rest_budget - len(kept_unresolved))]
    kept_ver = selected.verification[
        : max(0, rest_budget - len(kept_unresolved) - len(kept_changed))
    ]
    truncated = truncated or (
        len(kept_unresolved) + len(kept_changed) + len(kept_ver)
        < len(unresolved) + len(selected.changed) + len(selected.verification)
    )
    if category is None and truncated:
        category = "unresolved"
    fixed = len(selected.claims) + len(selected.relationships) + len(selected.conflicts)
    remaining = max(0, bounds.max_results - fixed)
    kept_views = views[:remaining]
    remaining -= len(kept_views)
    kept_unresolved = unresolved[:remaining]
    remaining -= len(kept_unresolved)
    kept_changed = kept_changed[:remaining]
    remaining -= len(kept_changed)
    kept_ver = kept_ver[:remaining]
    dropped = (
        len(kept_views) < len(views)
        or len(kept_unresolved) < len(unresolved)
        or len(kept_changed) < len(selected.changed)
        or len(kept_ver) < len(selected.verification)
    )
    if dropped and category is None:
        category = "unresolved"
    return _LeafPage(
        views=tuple(kept_views),
        unresolved=tuple(kept_unresolved),
        changed=tuple(kept_changed),
        verification=tuple(kept_ver),
        truncated=truncated,
        category=category,
        dropped=dropped,
    )


def _answer_cursor(
    *,
    digest: str,
    scope: m.EvidenceScope | None,
    subjects: tuple[m.Subject, ...],
    frontier: str,
    frontier_total: int | None,
    frontier_offset: int,
    next_items: tuple[int, int, int] | None,
    truncated: bool,
    category: str | None,
) -> tuple[str | None, bool, str | None]:
    """Compose the page's cursor and fold it back into truncation."""
    if scope is not None:
        if next_items is not None:
            # The page stopped inside one subject: the frontier must not
            # advance until that subject's lists are exhausted.
            return (
                _format_scope_token(digest + frontier, frontier_offset, *next_items),
                True,
                category or "claims",
            )
        progress = frontier_offset + len(subjects)
        if frontier_total is not None and progress < frontier_total:
            return (
                _format_scope_token(digest + frontier, progress),
                True,
                category or "semantic_subjects",
            )
        return None, truncated, category
    token: str | None = None
    if len(subjects) == 1 and next_items is not None:
        token = _format_question_token(digest, *next_items)
    progress = frontier_offset + len(subjects)
    if frontier_total is not None and progress < frontier_total:
        token = _format_versioned_token(digest + frontier, progress)
        truncated = True
        category = category or "semantic_subjects"
    return token, truncated, category


def _compose_status_answer(
    repository_id: str,
    subjects: tuple[m.Subject, ...],
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    continuations: ContinuationPort,
    page_token: str | None = None,
    scope: m.EvidenceScope | None = None,
    item_cursor: tuple[int, int, int] = (0, 0, 0),
    frontier_total: int | None = None,
    frontier_offset: int = 0,
    frontier: str = "",
) -> m.SemanticAnswer:
    """Compose one bounded status page over the resolved scope."""
    identity = _page_identity(
        repository_id,
        subjects,
        bounds=bounds,
        page_token=page_token,
        scope=scope,
        item_cursor=item_cursor,
        frontier=frontier,
    )
    delivered = _delivered_state(
        repository_id,
        subjects,
        evidence=evidence,
        store=store,
        bounds=bounds,
        state=state,
        page_token=identity.subject_page_token,
    )
    single_subject_scope = scope is not None and len(subjects) == 1
    selected = _select_delivered(delivered, bounds=bounds)
    views, shown, remaining = _delivered_views(
        repository_id,
        subjects,
        evidence=evidence,
        store=store,
        bounds=bounds,
        live_states=delivered.live_states,
        subject_page_token=identity.subject_page_token,
    )
    next_items: tuple[int, int, int] | None = None
    if len(subjects) == 1:
        next_items = _next_service_offsets(
            identity.subject_page_token,
            selected.claims,
            selected.relationships,
            delivered.claims,
            delivered.relationships,
            delivered.claims_token,
            delivered.relationships_token,
            questions_skip=shown,
            questions_remaining=remaining,
        )
    truncated = selected.truncated
    category = selected.category
    if remaining > 0:
        truncated = True
        category = category or "question_coverage"
    pending_requirements = tuple(
        dict.fromkeys(
            (
                *_pending_exchange_requirements(views, continuations),
                *_live_subject_requirements(repository_id, subjects, continuations),
            )
        )
    )
    frontier_requirements, frontier_report = _frontier_section(
        repository_id,
        subjects,
        scope=scope,
        pending_requirements=pending_requirements,
        evidence=evidence,
        store=store,
        bounds=bounds,
        continuations=continuations,
    )
    if scope is not None and any(item_cursor):
        # The coverage entry repeats while one subject's lists page; its
        # requirements were delivered with that subject's first page.
        unresolved = tuple(dict.fromkeys((*selected.unresolved, *pending_requirements)))
    else:
        unresolved = tuple(
            dict.fromkeys(
                (
                    *selected.unresolved,
                    *pending_requirements,
                    *frontier_requirements,
                )
            )
        )
    selected = _dataclasses.replace(selected, unresolved=list(unresolved))
    leaves = _leaf_ceiling(
        selected,
        views,
        single_subject_scope=single_subject_scope,
        bounds=bounds,
        truncated=truncated,
        category=category,
    )
    token, truncated, category = _answer_cursor(
        digest=identity.digest,
        scope=scope,
        subjects=subjects,
        frontier=frontier,
        frontier_total=frontier_total,
        frontier_offset=frontier_offset,
        next_items=next_items,
        truncated=leaves.truncated,
        category=leaves.category,
    )
    if leaves.dropped:
        truncated = True
    content = _status_content(selected, leaves, delivered, frontier_report)
    return _scoped_answer(
        repository_id,
        subjects,
        selected=selected,
        state=state,
        bounds=bounds,
        content=content,
        leaves=leaves,
        category=category,
        token=token,
        truncated=truncated,
    )


def _status_content(
    selected: _Selected,
    leaves: _LeafPage,
    delivered: _Delivered,
    frontier_report: m.ScopedCoverageReport,
) -> m.StatusContent:
    """One scoped status content: items, leaves, and the frontier report."""
    return m.StatusContent(
        resolved_mode=m.StatusResolvedMode.SCOPED,
        store_readiness=m.StoreReadiness.READY,
        freshness_items=_freshness_items_for(selected.claims, selected.relationships),
        changed_dependencies=leaves.changed,  # type: ignore[arg-type]
        verification_status=leaves.verification,  # type: ignore[arg-type]
        refresh_scope=m.EvidenceScope(
            paths=tuple(sorted(delivered.stale_evidence)), evidence_refs=()
        ),
        claims=selected.claims,
        relationships=selected.relationships,
        conflicts=selected.conflicts,
        question_coverage=leaves.views,
        coverage_report=frontier_report,
    )


def _scoped_answer(
    repository_id: str,
    subjects: tuple[m.Subject, ...],
    *,
    state: m.RepositoryState,
    bounds: m.QueryBounds,
    content: m.StatusContent,
    selected: _Selected,
    leaves: _LeafPage,
    category: str | None,
    token: str | None,
    truncated: bool,
) -> m.SemanticAnswer:
    """Build the one scoped status answer envelope."""
    return ANSWER_ASSEMBLER.build(
        answer_id=_answer_id(
            "stt",
            repository_id,
            ",".join(subject.subject_id.canonical_locator for subject in subjects)
            or "scope",
        ),
        intent=m.SemanticIntent.STATUS,
        repository_state=state,
        subject_resolution=None,
        content=content,
        evidence=tuple(ref for claim in selected.claims for ref in claim.evidence),
        resolution_requirements=leaves.unresolved,
        bounds=bounds,
        withheld_category=category,
        continuation_token=token,
        state_explanation=_status_state_explanation(
            state_explanation_for(
                tuple(selected.claims),
                tuple(selected.relationships),
                coverage=coverage_counts_for(leaves.views),
                bounds=(bounds.max_results, truncated),
                derived_currencies=tuple(
                    sorted(
                        {
                            currency_literal(status.currency)
                            for status in leaves.verification
                        }
                    )
                ),
            ),
            content,
            leaves.unresolved,
        ),
    )
