"""Span service status operation (plan §11.8; v0.6 §14 Amendment A-01).

Currency and verification over stored semantics, with hook fast
path and resume. Verbatim from ``span.service_operations``; only the
module path changed.
"""

from __future__ import annotations


from span.core import model as m
from span.core.paging import INVALID_PAGE_TOKEN_MESSAGE
from span.ports.evidence import EvidenceSource
from span.ports.store import SemanticStore
from span.ports.continuation import ContinuationPort

from span.service.answers import (
    _answer_id,
    ANSWER_ASSEMBLER,
    _query_digest,
    _validate_service_token,
    state_explanation_for,
)
from span.service.requests import (
    SemanticStatusRequest,
    StatusTargetError,
)
from span.service.operations.status.tokens import (
    _format_service_token,
    _parse_service_token_bound,
)
from span.service.operations.status.coverage import (
    _coverage_entries_for_subjects,
    _repository_report,
    _target_burden_aggregates,
)
from span.service.operations.status.explanation import (
    _status_state_explanation,
)
from span.service.operations.status.requirements import (
    _live_question_records,
    _project_live_requirements,
    _project_pending_requirements,
    _repository_live_requirements,
    _repository_pending_requirements,
)


def _rank_coverage_entries(
    entries: tuple[m.SemanticCoverageEntry, ...],
) -> tuple[m.SemanticCoverageEntry, ...]:
    """Within-page display order only ([design note G](docs/design-references.md#g) §4.2b).

    Deterministic by coverage rank, then open and pending counts, then locator
    and kind. Pagination stays locator order; truncation follows retention.
    """
    rank = {
        m.SemanticCoverageDisposition.STALE: 0,
        m.SemanticCoverageDisposition.UNVERIFIABLE: 1,
        m.SemanticCoverageDisposition.INCOMPLETE: 2,
        m.SemanticCoverageDisposition.UNASSESSED: 3,
        m.SemanticCoverageDisposition.CURRENT: 4,
    }
    return tuple(
        sorted(
            entries,
            key=lambda entry: (
                rank[entry.disposition],
                -entry.open_question_count,
                -entry.pending_question_count,
                entry.subject.canonical_locator,
                entry.subject.subject_kind.value,
            ),
        )
    )


def _admit_entries_to_ceiling(
    entries: tuple[m.SemanticCoverageEntry, ...],
    requirements: tuple[m.ResolutionRequirement, ...],
    pending_requirements: tuple[m.ResolutionRequirement, ...],
    live_requirements: tuple[m.ResolutionRequirement, ...],
    max_results: int,
) -> tuple[
    tuple[m.SemanticCoverageEntry, ...],
    tuple[m.ResolutionRequirement, ...],
    bool,
]:
    """Admit whole entry units while their requirements fit the ceiling.

    A requirement belongs to the entry it describes. Building every entry and
    slicing the flattened requirement list afterwards was silent: the entries
    it cut never came back on the next page.
    """
    by_subject: dict[m.SubjectId, list[m.ResolutionRequirement]] = {}
    for requirement in (*requirements, *pending_requirements):
        if isinstance(requirement.subject_or_claim, m.SubjectId):
            by_subject.setdefault(requirement.subject_or_claim, []).append(requirement)
    remaining = max(0, max_results - len(live_requirements))
    kept_entries: list[m.SemanticCoverageEntry] = []
    kept_requirements: list[m.ResolutionRequirement] = list(live_requirements)
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
    return (
        tuple(kept_entries),
        tuple(dict.fromkeys(kept_requirements)),
        len(kept_entries) < len(entries),
    )


def _compose_repository_status_answer(
    repository_id: str,
    *,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    continuations: ContinuationPort,
    subject_offset: int = 0,
    mode: str = "NORMAL",
    page_token: str | None = None,
) -> m.SemanticAnswer:
    """Report persisted semantic coverage without structural enumeration."""
    digest = _query_digest(
        "STATUS", repository_id, "repository", f"mode:{mode}", bounds
    )
    _validate_service_token(page_token, digest)
    subject_page = store.load_repository_subjects(repository_id, bounds, subject_offset)
    entries, requirements = _coverage_entries_for_subjects(
        repository_id,
        subject_page.items,
        evidence=evidence,
        store=store,
        bounds=bounds,
    )
    live_records = _live_question_records(repository_id, None, continuations)
    pending_requirements = _repository_pending_requirements(
        repository_id,
        entries,
        evidence=evidence,
        store=store,
        continuations=continuations,
    )
    requirements = _project_pending_requirements(requirements, pending_requirements)
    requirements = _project_live_requirements(entries, requirements, live_records)
    dispositions = store.count_question_dispositions(repository_id)
    (
        target_accounted,
        target_unresolved,
        target_live_unaccounted,
    ) = _target_burden_aggregates(
        repository_id, evidence=evidence, store=store, bounds=bounds
    )
    live_requirements = _repository_live_requirements(repository_id, continuations)
    entries, requirements, page_cut = _admit_entries_to_ceiling(
        entries,
        requirements,
        pending_requirements,
        live_requirements,
        bounds.max_results,
    )
    entries = _rank_coverage_entries(entries)
    report = _repository_report(
        entries,
        persisted_subject_count=store.count_repository_subjects(repository_id),
        question_counts=(
            dispositions.get("PENDING", 0),
            dispositions.get("OPEN", 0),
        ),
        target_counts=(
            store.count_target_associations(repository_id),
            target_accounted,
            target_unresolved,
            target_live_unaccounted,
        ),
    )
    # Answer-level truncation describes the answer. An entry that reports its
    # own scan was cut carries ``entry.truncated``; folding that into the
    # answer produced ``truncated: true`` with no answer cursor, which is the
    # non-resumable shape this release removes. ``oversized_unit`` does not set
    # truncation: the unit was emitted whole, so nothing was withheld; the
    # ceiling breach is visible in the count.
    truncated = subject_page.bound_info.truncated or page_cut
    next_token = None
    if truncated:
        next_token = _format_service_token(
            subject_offset + len(entries),
            None,
            0,
            query_digest=digest,
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
    continuations: ContinuationPort,
) -> m.SemanticAnswer:
    """Resolve the normal no-target repository report page."""
    try:
        token_digest, subject_skip, rel_skip, question_skip = (
            _parse_service_token_bound(request.page_token)
        )
    except ValueError as exc:
        raise StatusTargetError(str(exc)) from None
    if rel_skip or question_skip:
        raise StatusTargetError(INVALID_PAGE_TOKEN_MESSAGE)
    expected = _query_digest(
        "STATUS",
        request.repository_id,
        "repository",
        f"mode:{request.mode.value}",
        bounds,
    )
    if request.page_token is not None and token_digest != expected:
        raise StatusTargetError(INVALID_PAGE_TOKEN_MESSAGE)
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
