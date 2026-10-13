"""Span service question currency and enumeration (Addendum B; v0.6 §14 Amendment A-01).

Recorded-vs-effective disposition views, question-local missing-state
decisions, and stale-question enumeration. Delegates currency
classification to core.freshness and discovery snapshots to
discovery.py. Verbatim from span.service_operations; only the
module path changed.
"""

from __future__ import annotations

from span.core import freshness as _freshness
from span.core import model as m
from span.ports.evidence import EvidenceSource
from span.ports.store import SemanticStore
from span.service.discovery import _inventory_snapshot
from span.service.resolution import (
    _load_all_coverages_or_defer,
    _load_subject_state,
)

__all__ = [
    '_question_identity_key',
    'effective_question_view',
    'question_coverage_check',
    '_question_local_missing',
    '_missing_subjects',
    '_stale_question_scopes',
    '_question_views_for_scope',
    '_paged_question_views',
    '_question_class_for_intent',
    '_REQUIRED_QUESTION_CLASS',
]

def _question_identity_key(question: m.SemanticQuestionScope) -> tuple[str, ...]:
    return (
        "q",
        question.scope_root.repository_id,
        question.scope_root.subject_kind.value,
        question.scope_root.canonical_locator,
        question.subject.subject_kind.value,
        question.subject.canonical_locator,
        question.question_class.value,
        question.question_slice,
    )

def effective_question_view(
    coverage: m.InterpretationCoverage,
    *,
    evidence: EvidenceSource | None = None,
    store: SemanticStore | None = None,
    repository_id: str = "",
    precomputed_snapshot: tuple[
        tuple[tuple[str, str], ...], dict[str, str]
    ] | None = None,
) -> m.SemanticQuestionCoverageView:
    recorded = coverage.disposition
    effective = recorded
    freshness = m.Freshness(
        state=m.FreshnessState.CURRENT, reason="question dependencies current"
    )
    requirements = tuple(coverage.resolution_requirements)
    # Result/premise check: any noncurrent result ref makes a recorded
    # ANSWERED/NOT_APPLICABLE noncurrent (effective PENDING).
    if store is not None and repository_id and coverage.result_refs:
        try:
            items = store.load_by_refs(
                repository_id, tuple(coverage.result_refs)
            )
        except ValueError:
            items = ()
            effective = m.SemanticQuestionDisposition.PENDING
            freshness = m.Freshness(
                state=m.FreshnessState.UNVERIFIABLE,
                reason="question result unknown/retired",
            )
        else:
            for item in items:
                if item.freshness.state is not m.FreshnessState.CURRENT:
                    if recorded in (
                        m.SemanticQuestionDisposition.ANSWERED,
                        m.SemanticQuestionDisposition.NOT_APPLICABLE,
                    ):
                        effective = m.SemanticQuestionDisposition.PENDING
                    freshness = m.Freshness(
                        state=m.FreshnessState.STALE,
                        reason="question premise/result noncurrent",
                    )
                    break
    # Direct question-evidence check: recompute live fingerprints for
    # every QuestionEvidenceObservation. A changed/unreadable source
    # reopens the question even with zero result refs.
    if (
        effective is not m.SemanticQuestionDisposition.PENDING
        and evidence is not None
        and repository_id
        and coverage.question_evidence
    ):
        for obs in coverage.question_evidence:
            try:
                (unit,) = evidence.read_evidence(
                    (obs.evidence_ref,),
                    m.QueryBounds(50, 2, 8, 24, 96_000, 64, 64),
                )
                current_fp = unit.content_fingerprint
            except ValueError:
                current_fp = None
            if current_fp != obs.observed_fingerprint:
                if recorded in (
                    m.SemanticQuestionDisposition.ANSWERED,
                    m.SemanticQuestionDisposition.NOT_APPLICABLE,
                    m.SemanticQuestionDisposition.OPEN,
                ):
                    effective = m.SemanticQuestionDisposition.PENDING
                freshness = m.Freshness(
                    state=m.FreshnessState.STALE,
                    reason="question evidence changed since examination",
                )
                break
    # Discovery check for the exact question identity: the question's
    # own CoverageDependency snapshot (inventory membership + seeds)
    # is evaluated even when result_refs is empty, so OPEN and
    # NOT_APPLICABLE with zero refs still track discovery movement.
    if (
        effective is not m.SemanticQuestionDisposition.PENDING
        and evidence is not None
        and store is not None
        and repository_id
        and coverage.question is not None
    ):
        try:
            dep_coverages = store.load_coverage_dependencies(
                repository_id, (coverage.question.subject,)
            )
        except Exception:
            dep_coverages = ()
        mine = [
            cov for cov in dep_coverages
            if cov.question is not None
            and _question_identity_key(cov.question)
            == _question_identity_key(coverage.question)
        ]
        if mine:
            latest = mine[-1]
            try:
                inventory_fp, seed_map = _inventory_snapshot(
                    repository_id,
                    evidence=evidence,
                    seeds=tuple(
                        (sf.locator, sf.evidence_id.value)
                        for sf in latest.seed_fingerprints
                    ),
                    precomputed=precomputed_snapshot,
                )
                discovery = _freshness.classify_coverage(
                    latest, inventory_fp, seed_map
                )
            except Exception:
                discovery = m.Freshness(
                    state=m.FreshnessState.UNVERIFIABLE,
                    reason="question discovery unevaluable",
                )
            if discovery.state is not m.FreshnessState.CURRENT:
                if recorded in (
                    m.SemanticQuestionDisposition.ANSWERED,
                    m.SemanticQuestionDisposition.NOT_APPLICABLE,
                    m.SemanticQuestionDisposition.OPEN,
                ):
                    effective = m.SemanticQuestionDisposition.PENDING
                freshness = m.Freshness(
                    state=discovery.state,
                    supporting_revision_or_fingerprint=(
                        discovery.supporting_revision_or_fingerprint
                    ),
                    reason=(
                        "question discovery scope changed; reassessment "
                        "required"
                    ),
                )
    if recorded is m.SemanticQuestionDisposition.PENDING:
        effective = m.SemanticQuestionDisposition.PENDING
    if not coverage.question_evidence and not coverage.result_refs:
        # Zero-result questions rely on discovery snapshot; insufficient
        # snapshot is UNVERIFIABLE, never durable negative fact.
        if recorded is m.SemanticQuestionDisposition.NOT_APPLICABLE:
            freshness = m.Freshness(
                state=m.FreshnessState.UNVERIFIABLE,
                reason="negative determination without direct evidence",
            )
    question = coverage.question
    assert question is not None
    return m.SemanticQuestionCoverageView(
        question=question,
        recorded_disposition=recorded,
        effective_disposition=effective,
        freshness=freshness,
        resolution_requirements=requirements,
    )

def question_coverage_check(
    repository_id: str,
    coverages: tuple[m.InterpretationCoverage, ...],
    *,
    evidence: EvidenceSource,
    store: SemanticStore,
) -> tuple[m.InterpretationCoverage, ...]:
    """Discovery freshness for question coverages incl. zero-result ones.

    For every question coverage (including OPEN/NOT_APPLICABLE with
    zero ``result_refs``), evaluate its exact-question discovery
    snapshot plus direct question evidence. Returns the coverages
    whose dependencies moved and therefore require reassessment
    (effective PENDING). Never infers sufficiency from empty refs.
    """
    stale: list[m.InterpretationCoverage] = []
    for coverage in coverages:
        if coverage.question is None:
            continue
        view = effective_question_view(
            coverage, evidence=evidence, store=store,
            repository_id=repository_id,
        )
        if (
            view.effective_disposition is m.SemanticQuestionDisposition.PENDING
            and coverage.disposition
            is not m.SemanticQuestionDisposition.PENDING
        ) or view.freshness.state is not m.FreshnessState.CURRENT:
            stale.append(coverage)
    return tuple(stale)

def _question_class_for_intent(
    intent: m.SemanticIntent, establish_baseline: bool = False
) -> m.SemanticQuestionClass:
    if establish_baseline:
        return m.SemanticQuestionClass.CQ_01
    if intent is m.SemanticIntent.TRACE:
        return m.SemanticQuestionClass.CQ_04
    if intent is m.SemanticIntent.IMPACT:
        return m.SemanticQuestionClass.CQ_08
    if intent is m.SemanticIntent.AUTHORITY:
        return m.SemanticQuestionClass.CQ_06
    if intent is m.SemanticIntent.STATUS:
        return m.SemanticQuestionClass.CQ_09
    return m.SemanticQuestionClass.CQ_01

_REQUIRED_QUESTION_CLASS: dict[m.SemanticIntent, m.SemanticQuestionClass] = {
    m.SemanticIntent.EXPLAIN: m.SemanticQuestionClass.CQ_01,
    m.SemanticIntent.TRACE: m.SemanticQuestionClass.CQ_04,
    m.SemanticIntent.IMPACT: m.SemanticQuestionClass.CQ_08,
    m.SemanticIntent.AUTHORITY: m.SemanticQuestionClass.CQ_06,
    m.SemanticIntent.STATUS: m.SemanticQuestionClass.CQ_09,
}

def _question_local_missing(
    repository_id: str,
    subject: m.Subject,
    intent: m.SemanticIntent,
    *,
    store: SemanticStore,
    evidence: EvidenceSource | None,
    bounds: m.QueryBounds,
) -> m.SemanticQuestionScope | None:
    """Question-aware missing-state decision (Addendum B B.7).

    Returns the bounded question to examine next, or None when the
    operation may answer from stored/current semantics (possibly
    qualified). Claim/relationship existence alone never counts as
    examined: the operation's primary question class needs recorded
    ANSWERED/NOT_APPLICABLE/OPEN/PENDING coverage. Recorded-but-
    noncurrent answers are served as qualified noncurrent views on
    reads (reassessment belongs to explicit refresh), never
    manufactured inline — except recorded PENDING with no stored
    semantics, which still needs its first examination.
    """
    sid = subject.subject_id
    try:
        coverages = store.load_all_question_coverages(
            repository_id, None, (sid,),
        )
    except Exception:
        try:
            coverages = store.load_question_coverages(
                repository_id, None, (sid,), bounds,
            )
        except Exception:
            coverages = ()
    mine = [
        cov for cov in coverages
        if cov.question is not None and cov.question.subject == sid
    ]
    primary = _REQUIRED_QUESTION_CLASS[intent]
    if intent is m.SemanticIntent.STATUS:
        # STATUS is a read path (currency/verification over stored
        # semantics): it suspends only for a totally unexamined
        # subject (no coverages and no stored claims/relationships).
        # Stale-but-examined state is reported as qualified
        # noncurrent views; reassessment belongs to explicit refresh.
        if not mine:
            claims, relationships, _, _ = _load_subject_state(
                repository_id, sid, store=store, bounds=bounds,
            )
            if not claims and not relationships:
                return m.SemanticQuestionScope(
                    scope_root=sid,
                    subject=sid,
                    question_class=primary,
                    question_slice=sid.canonical_locator,
                    materiality_basis=f"{intent.value} question-local",
                )
        return None
    if not mine:
        # Nothing examined (legacy claims or not): examine primary.
        return m.SemanticQuestionScope(
            scope_root=sid,
            subject=sid,
            question_class=primary,
            question_slice=sid.canonical_locator,
            materiality_basis=f"{intent.value} question-local",
        )
    primary_covs = [
        cov for cov in mine
        if cov.question.question_class is primary
    ]
    if not primary_covs:
        # Claims of other questions never satisfy this unexamined one.
        return m.SemanticQuestionScope(
            scope_root=sid,
            subject=sid,
            question_class=primary,
            question_slice=sid.canonical_locator,
            materiality_basis=f"{intent.value} question-local",
        )
    for cov in primary_covs:
        if (
            cov.disposition is m.SemanticQuestionDisposition.PENDING
            and cov.question is not None
        ):
            return cov.question
    return None

def _stale_question_scopes(
    repository_id: str,
    subject: m.Subject,
    *,
    store: SemanticStore,
    evidence: EvidenceSource,
    bounds: m.QueryBounds,
    suspended: frozenset[tuple[str, str, str, str]] = frozenset(),
) -> list[m.SemanticQuestionScope]:
    """Persisted questions requiring reassessment, deterministic order.

    Recorded ANSWERED/NOT_APPLICABLE/OPEN whose effective disposition
    is PENDING or whose freshness is noncurrent (changed evidence,
    moved discovery, retired/stale premises or results). Refresh
    re-examines under these persisted identities (B.3/B-06).

    G-15: recorded-PENDING questions are included too (previously
    skipped), so refresh resumes specific admitted work instead of
    re-deriving the root question while pendings starve. Ordering
    puts recorded-PENDING first (unexamined work before
    re-verification), then the rest by (class, slice). Entries whose
    question already has a live (unexpired, unclaimed) continuation
    — passed as ``suspended`` keys of
    (repository_id, subject locator, class value, slice) — are
    excluded, so one question is never suspended twice concurrently.
    Root re-verification is preserved: once no pending binds, the
    stale root admits exactly as before.
    """
    sid = subject.subject_id
    try:
        coverages = _load_all_coverages_or_defer(
            repository_id, None, (sid,),
            store=store, bounds=bounds,
            purpose="stale question enumeration",
        )
    except Exception:
        return []
    pending: list[m.SemanticQuestionScope] = []
    stale: list[m.SemanticQuestionScope] = []
    for cov in coverages:
        if cov.question is None or cov.question.subject != sid:
            continue
        key = (
            repository_id,
            cov.question.subject.canonical_locator,
            cov.question.question_class.value,
            cov.question.question_slice,
        )
        if key in suspended:
            continue
        if cov.disposition is m.SemanticQuestionDisposition.PENDING:
            pending.append(cov.question)
            continue
        try:
            view = effective_question_view(
                cov, evidence=evidence, store=store,
                repository_id=repository_id,
            )
        except Exception:
            continue
        if (
            view.effective_disposition
            is m.SemanticQuestionDisposition.PENDING
            or view.freshness.state is not m.FreshnessState.CURRENT
        ):
            stale.append(cov.question)
    pending.sort(
        key=lambda q: (q.question_class.value, q.question_slice)
    )
    stale.sort(
        key=lambda q: (q.question_class.value, q.question_slice)
    )
    return pending + stale

def _question_views_for_scope(
    repository_id: str,
    scope_root: m.SubjectId | None,
    subject_ids: tuple[m.SubjectId, ...],
    *,
    store: SemanticStore,
    bounds: m.QueryBounds,
    evidence: EvidenceSource | None = None,
) -> tuple[m.SemanticQuestionCoverageView, ...]:
    try:
        coverages = store.load_question_coverages(
            repository_id, scope_root, subject_ids, bounds,
        )
    except Exception:
        return ()
    views: list[m.SemanticQuestionCoverageView] = []
    for cov in coverages:
        if cov.question is None:
            continue
        try:
            views.append(
                effective_question_view(
                    cov, evidence=evidence, store=store,
                    repository_id=repository_id,
                )
            )
        except Exception:
            continue
    views.sort(
        key=lambda v: (
            v.question.question_class.value,
            v.question.subject.canonical_locator,
            v.question.question_slice,
        )
    )
    return tuple(views)

def _paged_question_views(
    repository_id: str,
    scope_root: m.SubjectId | None,
    subject_ids: tuple[m.SubjectId, ...],
    *,
    store: SemanticStore,
    bounds: m.QueryBounds,
    page_token: str | None = None,
    evidence: EvidenceSource | None = None,
) -> tuple[tuple[m.SemanticQuestionCoverageView, ...], int, int]:
    """Return (kept views, shown count, remaining count) for paging."""
    from span.shell import paging as _paging

    try:
        _, _, qskip = _paging.parse_service_token(page_token)
    except ValueError:
        qskip = 0
    all_views = _question_views_for_scope(
        repository_id, scope_root, subject_ids,
        store=store, bounds=bounds, evidence=evidence,
    )
    # Reserve budget: questions share max_results with claims/rels.
    # Simple policy: show up to remaining budget after caller slices
    # claims/rels; here return windowed slice, caller decides budget.
    kept = all_views[qskip:qskip + bounds.max_results]
    remaining = max(0, len(all_views) - (qskip + len(kept)))
    return kept, len(kept), remaining

def _missing_subjects(
    repository_id: str,
    subjects: tuple[m.Subject, ...],
    *,
    store: SemanticStore,
    bounds: m.QueryBounds,
    suspended: tuple[str, ...],
    evidence: EvidenceSource | None = None,
) -> m.Subject | None:
    """First subject with unexamined question-local state (B.7).

    Question-aware: a subject is missing when its STATUS primary
    question (CQ_09) or any admitted PENDING question lacks
    effective-current coverage — never merely when claims are absent.
    """
    for subject in subjects:
        if subject.subject_id.canonical_locator in suspended:
            continue
        missing = _question_local_missing(
            repository_id, subject, m.SemanticIntent.STATUS,
            store=store, evidence=evidence, bounds=bounds,
        )
        if missing is not None:
            return subject
    return None
