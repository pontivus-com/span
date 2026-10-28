"""Span questions: identity projection, slice derivation, and frontier."""

from __future__ import annotations

from collections.abc import Mapping

from span.core import freshness as _freshness
from span.core import model as m
from span.ports.evidence import EvidenceSource
from span.ports.store import SemanticStore
from span.service.discovery import _inventory_snapshot


from span.service.questions.slices import (
    _question_identity_key,
)


def filter_views_by_scope(
    views: tuple[m.SemanticQuestionCoverageView, ...],
    scope: m.SemanticQuestionScope | None,
) -> tuple[m.SemanticQuestionCoverageView, ...]:
    """Filter returned coverage by selected identity (S4 §5.4)."""
    if scope is None:
        return views
    key = _question_identity_key(scope)
    return (
        tuple(v for v in views if _question_identity_key(v.question) == key)
        or views[:0]
    )


def _discovery_currency(
    coverage: m.InterpretationCoverage,
    recorded: m.SemanticQuestionDisposition,
    *,
    evidence: EvidenceSource,
    store: SemanticStore,
    repository_id: str,
    precomputed_snapshots: Mapping[m.EvidenceScope, tuple[str, dict[str, str]]] | None,
) -> tuple[m.SemanticQuestionDisposition | None, m.Freshness | None]:
    """Evaluate the exact question's own discovery snapshot.

    The question's ``CoverageDependency`` snapshot (inventory membership plus
    seeds) is evaluated even when ``result_refs`` is empty, so OPEN and
    NOT_APPLICABLE with zero refs still track discovery movement. Returns the
    changed disposition and freshness, or ``(None, None)`` when current.
    """
    if coverage.question is None:
        return None, None
    try:
        dep_coverages = store.load_coverage_dependencies(
            repository_id, (coverage.question.subject,)
        )
    except Exception:
        dep_coverages = ()
    mine = [
        cov
        for cov in dep_coverages
        if cov.question is not None
        and _question_identity_key(cov.question)
        == _question_identity_key(coverage.question)
    ]
    if not mine:
        return None, None
    latest = mine[-1]
    try:
        scope = latest.discovery_scope
        precomputed_snapshot = (
            precomputed_snapshots.get(scope)
            if precomputed_snapshots is not None
            else None
        )
        inventory_fp, seed_map = _inventory_snapshot(
            repository_id,
            scope,
            evidence=evidence,
            seeds=tuple(
                (sf.locator, sf.evidence_id.value) for sf in latest.seed_fingerprints
            ),
            precomputed=precomputed_snapshot,
        )
        discovery = _freshness.classify_coverage(latest, inventory_fp, seed_map)
    except Exception:
        discovery = m.Freshness(
            state=m.FreshnessState.UNVERIFIABLE,
            reason="question discovery unevaluable",
        )
    if discovery.state is m.FreshnessState.CURRENT:
        return None, None
    changed_effective = (
        m.SemanticQuestionDisposition.PENDING
        if recorded
        in (
            m.SemanticQuestionDisposition.ANSWERED,
            m.SemanticQuestionDisposition.NOT_APPLICABLE,
            m.SemanticQuestionDisposition.OPEN,
        )
        else None
    )
    return changed_effective, m.Freshness(
        state=discovery.state,
        supporting_revision_or_fingerprint=(
            discovery.supporting_revision_or_fingerprint
        ),
        reason="question discovery scope changed; reassessment required",
    )


def effective_question_view(
    coverage: m.InterpretationCoverage,
    *,
    evidence: EvidenceSource | None = None,
    store: SemanticStore | None = None,
    repository_id: str = "",
    precomputed_snapshots: (
        Mapping[m.EvidenceScope, tuple[str, dict[str, str]]] | None
    ) = None,
    live_states: dict[str, m.FreshnessState] | None = None,
) -> m.SemanticQuestionCoverageView:
    recorded = coverage.disposition
    effective = recorded
    freshness = m.Freshness(
        state=m.FreshnessState.CURRENT, reason="question dependencies current"
    )
    requirements = tuple(coverage.resolution_requirements)
    # Result/premise check: any noncurrent result ref makes a recorded
    # ANSWERED/NOT_APPLICABLE noncurrent (effective PENDING).
    # S2 §5.2: a per-call live overlay (from _evaluate_current) overrides
    # stored freshness so the returned view agrees without a prior write.
    if store is not None and repository_id and coverage.result_refs:
        try:
            items = store.load_by_refs(repository_id, tuple(coverage.result_refs))
        except ValueError:
            items = ()
            effective = m.SemanticQuestionDisposition.PENDING
            freshness = m.Freshness(
                state=m.FreshnessState.UNVERIFIABLE,
                reason="question result unknown/retired",
            )
        else:
            for item in items:
                item_id = (
                    item.claim_id.value
                    if isinstance(item, m.SemanticClaim)
                    else item.relationship_id.value
                )
                live_state = (
                    live_states.get(item_id) if live_states is not None else None
                )
                state = live_state if live_state is not None else item.freshness.state
                if state is not m.FreshnessState.CURRENT:
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
    if (
        effective is not m.SemanticQuestionDisposition.PENDING
        and evidence is not None
        and store is not None
        and repository_id
    ):
        changed_effective, changed_freshness = _discovery_currency(
            coverage,
            recorded,
            evidence=evidence,
            store=store,
            repository_id=repository_id,
            precomputed_snapshots=precomputed_snapshots,
        )
        if changed_effective is not None:
            effective = changed_effective
        if changed_freshness is not None:
            freshness = changed_freshness
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
        recovery=coverage.recovery,
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
            coverage,
            evidence=evidence,
            store=store,
            repository_id=repository_id,
        )
        if (
            view.effective_disposition is m.SemanticQuestionDisposition.PENDING
            and coverage.disposition is not m.SemanticQuestionDisposition.PENDING
        ) or view.freshness.state is not m.FreshnessState.CURRENT:
            stale.append(coverage)
    return tuple(stale)
