"""Span service status operation (plan §11.8; v0.6 §14 Amendment A-01).

Currency and verification over stored semantics, with hook fast
path and resume. Verbatim from ``span.service_operations``; only the
module path changed.
"""

from __future__ import annotations

import dataclasses as _dataclasses

from collections.abc import Mapping

from span.core import model as m
from span.core import requirements as _requirements
from span.ports.evidence import EvidenceSource
from span.ports.store import SemanticStore

from span.service.discovery import (
    _coverage_scope_snapshots,
    enumerate_target_inventory,
)
from span.service.freshness import (
    _classify_current,
)
from span.service.questions import (
    effective_question_view,
)
from span.service.refs import (
    _claim_ref,
    _relationship_ref,
)
from span.service.resolution import (
    _load_subject_state,
)


@_dataclasses.dataclass
class _QuestionScan:
    """One subject's question coverage, projected once for its report entry."""

    views: list[m.SemanticQuestionCoverageView]
    total: int
    pending: int
    open: int
    answered: int
    not_applicable: int
    stale_effective: int
    unverifiable: bool
    requirements: list[m.ResolutionRequirement]

    @property
    def remaining(self) -> int:
        return max(0, self.total - len(self.views))


def _scan_question_coverage(
    repository_id: str,
    subject: m.Subject,
    *,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    precomputed_snapshots: Mapping[m.EvidenceScope, tuple[str, dict[str, str]]] | None,
) -> _QuestionScan:
    """Project one subject's persisted question coverage and its requirements."""
    question_total = store.count_question_coverages(
        repository_id, None, (subject.subject_id,)
    )
    coverages = store.load_question_coverages(
        repository_id, None, (subject.subject_id,), bounds
    )
    views: list[m.SemanticQuestionCoverageView] = []
    for coverage in coverages:
        if coverage.question is None:
            continue
        views.append(
            effective_question_view(
                coverage,
                evidence=evidence,
                store=store,
                repository_id=repository_id,
                precomputed_snapshots=precomputed_snapshots,
            )
        )
    views.sort(
        key=lambda view: (
            view.question.question_class.value,
            view.question.question_slice,
        )
    )
    return _QuestionScan(
        views=views,
        total=question_total,
        pending=sum(
            view.effective_disposition is m.SemanticQuestionDisposition.PENDING
            for view in views
        ),
        open=sum(
            view.effective_disposition is m.SemanticQuestionDisposition.OPEN
            for view in views
        ),
        answered=sum(
            view.effective_disposition is m.SemanticQuestionDisposition.ANSWERED
            for view in views
        ),
        not_applicable=sum(
            view.effective_disposition is m.SemanticQuestionDisposition.NOT_APPLICABLE
            for view in views
        ),
        stale_effective=sum(
            view.freshness.state is m.FreshnessState.STALE for view in views
        ),
        unverifiable=any(
            view.freshness.state is m.FreshnessState.UNVERIFIABLE for view in views
        ),
        requirements=[
            requirement
            for view in views
            for requirement in view.resolution_requirements
        ],
    )


def _semantic_item_counts(
    claims: tuple[m.SemanticClaim, ...],
    relationships: tuple[m.SemanticRelationship, ...],
    updates: tuple[m.FreshnessUpdate, ...],
) -> tuple[int, int, int]:
    """Current, stale, and unverifiable counts over recorded plus live states."""
    freshness_by_id = {claim.claim_id.value: claim.freshness.state for claim in claims}
    freshness_by_id.update(
        {
            relationship.relationship_id.value: relationship.freshness.state
            for relationship in relationships
        }
    )
    freshness_by_id.update(
        {update.semantic_id.id.value: update.freshness.state for update in updates}
    )
    return (
        sum(state is m.FreshnessState.CURRENT for state in freshness_by_id.values()),
        sum(state is m.FreshnessState.STALE for state in freshness_by_id.values()),
        sum(
            state is m.FreshnessState.UNVERIFIABLE for state in freshness_by_id.values()
        ),
    )


def _entry_disposition(
    *,
    question: _QuestionScan,
    stale_items: int,
    unverifiable_items: int,
    truncated: bool,
) -> m.SemanticCoverageDisposition:
    """The one coverage precedence: UNVERIFIABLE → STALE → INCOMPLETE → others."""
    incomplete = bool(
        question.pending or question.open or question.remaining or truncated
    )
    if question.unverifiable or unverifiable_items:
        return m.SemanticCoverageDisposition.UNVERIFIABLE
    if question.stale_effective or stale_items:
        return m.SemanticCoverageDisposition.STALE
    if incomplete:
        return m.SemanticCoverageDisposition.INCOMPLETE
    if not question.views:
        return m.SemanticCoverageDisposition.UNASSESSED
    return m.SemanticCoverageDisposition.CURRENT


def _entry_fallback_requirement(
    subject: m.Subject,
    disposition: m.SemanticCoverageDisposition,
) -> m.ResolutionRequirement:
    """Every non-current entry carries one actionable canonical requirement."""
    # [design note G](docs/design-references.md#g) §4.2c fallback: read-time projection only; never persisted;
    # never invents an objective.
    locator = subject.subject_id.canonical_locator
    if disposition is m.SemanticCoverageDisposition.STALE:
        kind = m.ResolutionKind.STALE_EVIDENCE
        description = (
            "subject has stale semantic items; refresh the "
            f"stale scope with an exact SubjectSelector for "
            f"'{locator}' (use status to confirm the scope)"
        )
    elif disposition is m.SemanticCoverageDisposition.UNVERIFIABLE:
        kind = m.ResolutionKind.UNVERIFIABLE_FRESHNESS
        description = (
            "subject freshness cannot be established; refresh "
            f"with an exact SubjectSelector for '{locator}'; "
            "an UNVERIFIABLE empty result proves nothing"
        )
    elif disposition is m.SemanticCoverageDisposition.UNASSESSED:
        kind = m.ResolutionKind.MISSING_SEMANTIC_COVERAGE
        description = (
            "no adopted question coverage is persisted for this "
            f"semantic subject; run question-local explain for "
            f"'{locator}'; a continuation exists only after "
            "that operation suspends"
        )
    else:
        kind = m.ResolutionKind.INCOMPLETE_SEMANTIC_SCOPE
        description = (
            "subject work is incomplete; continue the pending "
            f"questions for '{locator}' within bounds through "
            "the continuation returned by the suspending "
            "operation; pass the returned continuation unchanged"
        )
    return _requirements.requirement(
        kind=kind,
        subject_or_claim=subject.subject_id,
        description=description,
        supporting_context=(),
    )


def _ghost_requirement(
    repository_id: str,
    subject: m.Subject,
    *,
    evidence: EvidenceSource,
    bounds: m.QueryBounds,
    has_records: bool,
) -> m.ResolutionRequirement | None:
    """G-16: a recorded path-like subject absent from inventory is a ghost.

    Provider-agnostic inventory membership — never filesystem walks. Inventory
    failure must not fake a ghost, so a provider error propagates instead of
    reading as presence.
    """
    locator = subject.subject_id.canonical_locator
    file_part = locator.split("#", 1)[0]
    basename = file_part.rsplit("/", 1)[-1]
    suffix = basename.rsplit(".", 1)[-1] if "." in basename else ""
    # Path-like (slash plus short file suffix) with persisted records:
    # pure-UNASSESSED subjects keep UNASSESSED, and semantic-only identifiers
    # without file shape never qualify.
    if not ("/" in file_part and suffix.isalnum() and 1 <= len(suffix) <= 8):
        return None
    if not has_records:
        return None
    present = evidence.inventory_evidence(
        repository_id,
        m.EvidenceScope(paths=(file_part,), evidence_refs=()),
        bounds,
    )
    if any(item.evidence_ref.locator == file_part for item in present.items):
        return None
    return _requirements.unverifiable_freshness(
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
    current_count, stale_count, unverifiable_count = _semantic_item_counts(
        claims, relationships, updates
    )
    question = _scan_question_coverage(
        repository_id,
        subject,
        evidence=evidence,
        store=store,
        bounds=bounds,
        precomputed_snapshots=precomputed_snapshots,
    )
    truncated = bool(claim_token or rel_token or question.remaining)
    requirements = list(question.requirements)
    if not question.views and question.total == 0:
        requirements.append(
            _entry_fallback_requirement(
                subject, m.SemanticCoverageDisposition.UNASSESSED
            )
        )
    if truncated:
        requirements.append(
            _requirements.incomplete_scope(
                subject_or_claim=subject.subject_id,
                description=(
                    "repository semantic coverage is bounded; remaining "
                    "items or questions require a narrower page"
                ),
                supporting_context=(),
            )
        )
    requirements = list(dict.fromkeys(requirements))
    disposition = _entry_disposition(
        question=question,
        stale_items=stale_count,
        unverifiable_items=unverifiable_count,
        truncated=truncated,
    )
    if not requirements and disposition is not (m.SemanticCoverageDisposition.CURRENT):
        requirements.append(_entry_fallback_requirement(subject, disposition))
    ghost = _ghost_requirement(
        repository_id,
        subject,
        evidence=evidence,
        bounds=bounds,
        has_records=bool(semantic_ids or question.total),
    )
    if ghost is not None:
        disposition = m.SemanticCoverageDisposition.UNVERIFIABLE
        requirements.append(ghost)
    return (
        m.SemanticCoverageEntry(
            subject=subject.subject_id,
            disposition=disposition,
            semantic_item_count=len(semantic_ids),
            current_item_count=current_count,
            stale_item_count=stale_count,
            unverifiable_item_count=unverifiable_count,
            question_count=len(question.views),
            answered_question_count=question.answered,
            pending_question_count=question.pending,
            open_question_count=question.open,
            not_applicable_question_count=question.not_applicable,
            stale_effective_question_count=question.stale_effective,
            truncated=truncated,
        ),
        tuple(requirements),
    )


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
    """Read persisted target burden and bounded live unaccounted members.

    Membership is persisted per association, so both totals are derived from
    the associations themselves; only the live-unaccounted projection needs
    the provider.
    """
    associations = store.load_active_target_associations(repository_id)
    accounts = [
        account
        for association in associations
        for account in association.inventory_accounting
    ]
    accounted = sum(1 for account in accounts if account.assigned_area_subjects)
    unresolved = sum(1 for account in accounts if not account.assigned_area_subjects)
    observed_unaccounted = 0
    live_unaccounted: int | None
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
            observed_unaccounted += sum(
                item.evidence_ref.evidence_id.value not in accounted_ids
                for item in inventory
            )
        live_unaccounted = observed_unaccounted
    except ValueError:
        # A provider cannot establish the bounded live observation. Preserve
        # the exact persisted burden and mark the live projection unknown.
        live_unaccounted = None
    return accounted, unresolved, live_unaccounted


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
