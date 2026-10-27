"""Span questions: identity projection, slice derivation, and frontier."""

from __future__ import annotations

import types as _types
from collections.abc import Mapping


from span.core import model as m
from span.ports.evidence import EvidenceSource
from span.ports.store import SemanticStore
from span.service.resolution import (
    _load_all_coverages_or_defer,
    _load_subject_state,
)


from span.service.questions.projection import (
    effective_question_view,
)


from span.service.questions.slices import (
    _question_identity_key,
)


def _question_coverage_for_scope(
    coverages: tuple[m.InterpretationCoverage, ...],
    scope: m.SemanticQuestionScope,
) -> m.InterpretationCoverage | None:
    """Return the persisted coverage for one complete question identity.

    Identity matches the store primary key (``_question_identity_key``), so a
    host-supplied ``materiality_basis`` difference cannot make the read path
    disagree with the row the store would overwrite.
    """
    key = _question_identity_key(scope)
    for coverage in coverages:
        question = coverage.question
        if question is not None and _question_identity_key(question) == key:
            return coverage
    return None


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


_REQUIRED_QUESTION_CLASS: Mapping[m.SemanticIntent, m.SemanticQuestionClass] = (
    _types.MappingProxyType(
        {
            m.SemanticIntent.EXPLAIN: m.SemanticQuestionClass.CQ_01,
            m.SemanticIntent.TRACE: m.SemanticQuestionClass.CQ_04,
            m.SemanticIntent.IMPACT: m.SemanticQuestionClass.CQ_08,
            m.SemanticIntent.AUTHORITY: m.SemanticQuestionClass.CQ_06,
            m.SemanticIntent.STATUS: m.SemanticQuestionClass.CQ_09,
        }
    )
)


def _question_local_missing(
    repository_id: str,
    subject: m.Subject,
    intent: m.SemanticIntent,
    *,
    store: SemanticStore,
    evidence: EvidenceSource | None,
    bounds: m.QueryBounds,
) -> m.SemanticQuestionScope | None:
    """Question-aware missing-state decision ([design note B](docs/design-references.md#b) B.7).

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
            repository_id,
            None,
            (sid,),
        )
    except Exception:
        try:
            coverages = store.load_question_coverages(
                repository_id,
                None,
                (sid,),
                bounds,
            )
        except Exception:
            coverages = ()
    mine = [
        cov
        for cov in coverages
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
                repository_id,
                sid,
                store=store,
                bounds=bounds,
            )
            if not claims and not relationships:
                return m.SemanticQuestionScope(
                    scope_root=sid,
                    subject=sid,
                    question_class=primary,
                    question_slice=m.QUESTION_CLASS_DEFAULT_SLICE[primary],
                    materiality_basis=f"{intent.value} question-local",
                )
        return None
    if not mine:
        # Nothing examined yet: examine primary.
        return m.SemanticQuestionScope(
            scope_root=sid,
            subject=sid,
            question_class=primary,
            question_slice=m.QUESTION_CLASS_DEFAULT_SLICE[primary],
            materiality_basis=f"{intent.value} question-local",
        )
    primary_covs = [
        coverage
        for coverage in mine
        if coverage.question is not None and coverage.question.question_class is primary
    ]
    if not primary_covs:
        # Claims of other questions never satisfy this unexamined one.
        return m.SemanticQuestionScope(
            scope_root=sid,
            subject=sid,
            question_class=primary,
            question_slice=m.QUESTION_CLASS_DEFAULT_SLICE[primary],
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
    suspended: frozenset[tuple[str, ...]] = frozenset(),
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
    — passed as ``suspended`` keys of the complete question identity — are
    excluded, so one question is never suspended twice concurrently.
    Root re-verification is preserved: once no pending binds, the
    stale root admits exactly as before.
    """
    sid = subject.subject_id
    try:
        coverages = _load_all_coverages_or_defer(
            repository_id,
            None,
            (sid,),
            store=store,
            bounds=bounds,
            purpose="stale question enumeration",
        )
    except Exception:
        return []
    pending: list[m.SemanticQuestionScope] = []
    stale: list[m.SemanticQuestionScope] = []
    for cov in coverages:
        if cov.question is None or cov.question.subject != sid:
            continue
        key = _question_identity_key(cov.question)
        if key in suspended:
            continue
        if cov.disposition is m.SemanticQuestionDisposition.PENDING:
            pending.append(cov.question)
            continue
        try:
            view = effective_question_view(
                cov,
                evidence=evidence,
                store=store,
                repository_id=repository_id,
            )
        except Exception:
            continue
        if (
            view.effective_disposition is m.SemanticQuestionDisposition.PENDING
            or view.freshness.state is not m.FreshnessState.CURRENT
        ):
            stale.append(cov.question)
    pending.sort(key=lambda q: (q.question_class.value, q.question_slice))
    stale.sort(key=lambda q: (q.question_class.value, q.question_slice))
    return pending + stale


def _question_views_for_scope(
    repository_id: str,
    scope_root: m.SubjectId | None,
    subject_ids: tuple[m.SubjectId, ...],
    *,
    store: SemanticStore,
    bounds: m.QueryBounds,
    evidence: EvidenceSource | None = None,
    live_states: dict[str, m.FreshnessState] | None = None,
) -> tuple[m.SemanticQuestionCoverageView, ...]:
    try:
        coverages = store.load_question_coverages(
            repository_id,
            scope_root,
            subject_ids,
            bounds,
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
                    cov,
                    evidence=evidence,
                    store=store,
                    repository_id=repository_id,
                    live_states=live_states,
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
    live_states: dict[str, m.FreshnessState] | None = None,
) -> tuple[tuple[m.SemanticQuestionCoverageView, ...], int, int]:
    """Return (kept views, shown count, remaining count) for paging."""
    from span.core import paging as _paging

    _, _, qskip = _paging.parse_service_token(page_token)
    all_views = _question_views_for_scope(
        repository_id,
        scope_root,
        subject_ids,
        store=store,
        bounds=bounds,
        evidence=evidence,
        live_states=live_states,
    )
    # Reserve budget: questions share max_results with claims/rels.
    # Simple policy: show up to remaining budget after caller slices
    # claims/rels; here return windowed slice, caller decides budget.
    kept = all_views[qskip : qskip + bounds.max_results]
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
            repository_id,
            subject,
            m.SemanticIntent.STATUS,
            store=store,
            evidence=evidence,
            bounds=bounds,
        )
        if missing is not None:
            return subject
    return None
