"""Span service currency orchestration (plan §9.2, §8.5; v0.6 §14 Amendment A-01).

Effectful preflight around the pure core.freshness classifiers:
direct-evidence checks, bounded transitive premise walks, and
discovery-coverage comparison. Truncation yields UNVERIFIABLE, never
silent green. Sole store.mark_freshness writer. Verbatim from
span.service_operations; only the module path changed.
"""

from __future__ import annotations

import dataclasses as _dataclasses
from collections.abc import Mapping

from span.core import freshness as _freshness
from span.core import model as m
from span.ports.evidence import EvidenceSource
from span.ports.store import SemanticStore
from span.service.discovery import _coverage_scope_snapshots
from span.service.freshness.premise import _premise_preflight
from span.service.refs import _claim_ref, _ref_value, _relationship_ref


def preflight(
    repository_id: str,
    semantic_ids: tuple[m.ClaimRef | m.RelationshipRef, ...],
    *,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> tuple[m.FreshnessUpdate, ...]:
    """Query freshness preflight (plan §9.2 steps 1–4, [design note B](docs/design-references.md#b) B-05).

    Direct evidence plus bounded transitive semantic-premise walk with
    cycle detection. Truncation yields UNVERIFIABLE, never silent green.
    Effectful wrapper over the non-writing evaluator: classifies via
    _evaluate_current with empty item set for coverage, then persists.
    """
    if not semantic_ids:
        return ()
    updates, _ = _classify_current(
        repository_id,
        semantic_ids,
        evidence=evidence,
        store=store,
        bounds=bounds,
    )
    live: dict[str, m.FreshnessState] = {
        u.semantic_id.id.value: u.freshness.state for u in updates
    }
    premise_updates = _premise_preflight(
        repository_id,
        semantic_ids,
        store=store,
        bounds=bounds,
        live_states=live,
    )
    merged: dict[str, m.FreshnessUpdate] = {}
    for update in (*updates, *premise_updates):
        merged[update.semantic_id.id.value] = update
    final = tuple(merged.values())
    if final:
        store.mark_freshness(final)
    return final


def _latest_coverages(
    coverages: tuple[m.CoverageDependency, ...],
) -> tuple[m.CoverageDependency, ...]:
    """Deduplicate coverage history: latest record per subject scope wins.

    This function serves ITEM-level freshness only (`coverage_check`):
    an item's bytes are current when the newest discovery snapshot for
    its subject scope matches current state, regardless of which
    question recorded that snapshot. A refresh under any question
    heals item marks for its scope.

    Question-level currency is deliberately NOT derived here: each
    question's own snapshot is evaluated by exact question identity in
    `effective_question_view`/`question_coverage_check`, so a refresh
    under one question never makes another question current. The
    optional question tag on rows is the audit trail of which
    question refreshed discovery, not an item-freshness partition —
    partitioning items by question would let one outdated snapshot
    poison freshly established items indefinitely.
    """
    latest: dict[tuple[str, ...], m.CoverageDependency] = {}
    for coverage in coverages:
        key = tuple(sorted(s.canonical_locator for s in coverage.scope_subjects))
        latest[key] = coverage
    return tuple(latest.values())


def _classify_coverage_updates(
    repository_id: str,
    items: tuple[m.SemanticClaim | m.SemanticRelationship, ...],
    *,
    evidence: EvidenceSource,
    store: SemanticStore,
) -> tuple[m.FreshnessUpdate, ...]:
    """Non-writing classification portion of coverage_check (S2 §5.2).

    Same discovery comparison as coverage_check without persistence.
    Existing effectful paths call this routine then persist explicitly.
    """
    if not items:
        return ()
    scope_subjects = tuple(
        dict.fromkeys(
            item.subject if isinstance(item, m.SemanticClaim) else item.source
            for item in items
        )
    )
    coverages = store.load_coverage_dependencies(repository_id, scope_subjects)
    if not coverages:
        return ()
    snapshots = _coverage_scope_snapshots(repository_id, coverages, evidence=evidence)
    updates: list[m.FreshnessUpdate] = []
    for coverage in _latest_coverages(coverages):
        inventory_fp, seed_map = snapshots[coverage.discovery_scope]
        freshness = _freshness.classify_coverage(coverage, inventory_fp, seed_map)
        if freshness.state is m.FreshnessState.CURRENT:
            continue
        covered = {s.canonical_locator for s in coverage.scope_subjects}
        for item in items:
            locator = (
                item.subject.canonical_locator
                if isinstance(item, m.SemanticClaim)
                else item.source.canonical_locator
            )
            if locator not in covered:
                continue
            ref = (
                m.ClaimRef(id=item.claim_id)
                if isinstance(item, m.SemanticClaim)
                else m.RelationshipRef(id=item.relationship_id)
            )
            updates.append(m.FreshnessUpdate(semantic_id=ref, freshness=freshness))
    return tuple(updates)


def coverage_check(
    repository_id: str,
    items: tuple[m.SemanticClaim | m.SemanticRelationship, ...],
    *,
    evidence: EvidenceSource,
    store: SemanticStore,
) -> tuple[m.FreshnessUpdate, ...]:
    """Discovery-coverage freshness (plan §9.2 step 0, §8.5).

    Compares recorded inventory/seed fingerprints against current state.
    A moved inventory fingerprint — including a newly added authority
    with no existing dependants — marks covered items stale. Persists
    non-current classifications and returns the applied updates.

    Item-scoped by signature: with zero items there is nothing to
    mark, so this path returns early. Zero-result (OPEN /
    NOT_APPLICABLE) question freshness is owned instead by
    `question_coverage_check` plus per-question discovery evaluation
    in `effective_question_view`, which refresh and every answer
    composition consult even when `result_refs` is empty. An empty
    item list alone never proves currentness anywhere.
    """
    if not items:
        return ()
    scope_subjects = tuple(
        dict.fromkeys(
            item.subject if isinstance(item, m.SemanticClaim) else item.source
            for item in items
        )
    )
    coverages = store.load_coverage_dependencies(repository_id, scope_subjects)
    if not coverages:
        return ()
    snapshots = _coverage_scope_snapshots(repository_id, coverages, evidence=evidence)
    updates: list[m.FreshnessUpdate] = []
    for coverage in _latest_coverages(coverages):
        inventory_fp, seed_map = snapshots[coverage.discovery_scope]
        freshness = _freshness.classify_coverage(coverage, inventory_fp, seed_map)
        if freshness.state is m.FreshnessState.CURRENT:
            continue
        covered = {s.canonical_locator for s in coverage.scope_subjects}
        for item in items:
            locator = (
                item.subject.canonical_locator
                if isinstance(item, m.SemanticClaim)
                else item.source.canonical_locator
            )
            if locator not in covered:
                continue
            ref = (
                m.ClaimRef(id=item.claim_id)
                if isinstance(item, m.SemanticClaim)
                else m.RelationshipRef(id=item.relationship_id)
            )
            updates.append(m.FreshnessUpdate(semantic_id=ref, freshness=freshness))
    updates_t = tuple(updates)
    if updates_t:
        store.mark_freshness(updates_t)
    return updates_t


def _evaluate_current(
    repository_id: str,
    semantic_ids: tuple[m.ClaimRef | m.RelationshipRef, ...],
    items: tuple[m.SemanticClaim | m.SemanticRelationship, ...],
    *,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> tuple[
    tuple[m.FreshnessUpdate, ...],
    tuple[m.EvidenceDependency, ...],
]:
    """Non-writing freshness evaluation for observation (S2 §5.2).

    Combines direct evidence, bounded transitive premise evaluation
    with a per-call live overlay, and coverage/discovery classification.
    Reuses _classify_current; no new freshness algorithm. Existing
    effectful preflight/view paths call this routine then persist
    explicitly. Status calls this evaluator and projects returned
    freshness onto answer items only. Preserves precedence and reason
    semantics; no numeric severity order.
    """
    direct_updates, dependencies = _classify_current(
        repository_id,
        semantic_ids,
        evidence=evidence,
        store=store,
        bounds=bounds,
    )
    live: dict[str, m.FreshnessState] = {}
    for update in direct_updates:
        live[update.semantic_id.id.value] = update.freshness.state
    # Reached premise evidence joins the live map so a source changed
    # before any other operation marks its premise stale.
    try:
        premise_deps = store.load_evidence_dependencies(repository_id, semantic_ids)
    except Exception:
        premise_deps = ()
    if premise_deps:
        premise_refs = tuple(dict.fromkeys(dep.evidence_ref for dep in premise_deps))
        try:
            premise_page = evidence.inventory_evidence(
                repository_id,
                m.EvidenceScope(paths=(), evidence_refs=premise_refs),
                bounds,
            )
            for item in premise_page.items:
                live.setdefault(
                    item.evidence_ref.evidence_id.value,
                    m.FreshnessState.CURRENT,
                )
        except Exception:
            pass
    premise_updates = _premise_preflight(
        repository_id,
        semantic_ids,
        store=store,
        bounds=bounds,
        live_states=live,
    )
    coverage_updates = _classify_coverage_updates(
        repository_id,
        items,
        evidence=evidence,
        store=store,
    )
    merged: dict[str, m.FreshnessUpdate] = {}
    for update in (*direct_updates, *premise_updates, *coverage_updates):
        # Precedence is first-noncurrent wins in direct→premise→coverage
        # order; STALE/UNVERIFIABLE never overwrite each other silently
        # beyond that deterministic order.
        if update.semantic_id.id.value not in merged:
            merged[update.semantic_id.id.value] = update
    return tuple(merged.values()), dependencies


def _refresh_view(
    repository_id: str,
    claims: tuple[m.SemanticClaim, ...],
    relationships: tuple[m.SemanticRelationship, ...],
    *,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> tuple[tuple[m.SemanticClaim, ...], tuple[m.SemanticRelationship, ...]]:
    # Effectful view path: evaluate via the non-writing routine, then
    # perform the existing explicit persistence. Status never calls this.
    ids: tuple[m.ClaimRef | m.RelationshipRef, ...] = tuple(
        _claim_ref(c) for c in claims
    ) + tuple(_relationship_ref(r) for r in relationships)
    items = tuple(claims) + tuple(relationships)
    updates, _ = _evaluate_current(
        repository_id,
        ids,
        items,
        evidence=evidence,
        store=store,
        bounds=bounds,
    )
    if updates:
        store.mark_freshness(updates)
    if not updates:
        return claims, relationships
    by_id = {_ref_value(update.semantic_id): update.freshness for update in updates}
    return with_freshness(claims, relationships, by_id)


def with_freshness(
    claims: tuple[m.SemanticClaim, ...],
    relationships: tuple[m.SemanticRelationship, ...],
    freshness_by_id: Mapping[str, m.Freshness],
) -> tuple[
    tuple[m.SemanticClaim, ...],
    tuple[m.SemanticRelationship, ...],
]:
    """Overlay one freshness map onto canonical items by identity.

    The one projection used by every caller that shows live currency: items
    without an entry pass through unchanged, so recorded state is never invented
    or downgraded. The item carrier itself is preserved
    (``dataclasses.replace``), never rebuilt field by field.
    """
    return (
        tuple(
            (
                _dataclasses.replace(
                    claim, freshness=freshness_by_id[claim.claim_id.value]
                )
                if claim.claim_id.value in freshness_by_id
                else claim
            )
            for claim in claims
        ),
        tuple(
            (
                _dataclasses.replace(
                    relationship,
                    freshness=freshness_by_id[relationship.relationship_id.value],
                )
                if relationship.relationship_id.value in freshness_by_id
                else relationship
            )
            for relationship in relationships
        ),
    )


def _classify_current(
    repository_id: str,
    semantic_ids: tuple[m.ClaimRef | m.RelationshipRef, ...],
    *,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> tuple[tuple[m.FreshnessUpdate, ...], tuple[m.EvidenceDependency, ...]]:
    """Classify without persisting (read-only half of preflight).

    Hook paths use this directly: HOOK_FAST is read-only with respect
    to semantic truth and must never mark freshness.
    """
    if not semantic_ids:
        return (), ()
    dependencies = store.load_evidence_dependencies(repository_id, semantic_ids)
    refs = tuple(dict.fromkeys(dep.evidence_ref for dep in dependencies))
    current: dict[str, str | None] = {}
    if refs:
        page = evidence.inventory_evidence(
            repository_id,
            m.EvidenceScope(paths=(), evidence_refs=refs),
            bounds,
        )
        for item in page.items:
            current[item.evidence_ref.evidence_id.value] = item.content_fingerprint
    return _freshness.classify_all(dependencies, current), dependencies
