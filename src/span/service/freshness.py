"""Span service currency orchestration (plan §9.2, §8.5; v0.6 §14 Amendment A-01).

Effectful preflight around the pure core.freshness classifiers:
direct-evidence checks, bounded transitive premise walks, and
discovery-coverage comparison. Truncation yields UNVERIFIABLE, never
silent green. Sole store.mark_freshness writer. Verbatim from
span.service_operations; only the module path changed.
"""

from __future__ import annotations

from span.core import freshness as _freshness
from span.core import model as m
from span.ports.evidence import EvidenceSource
from span.ports.store import SemanticStore
from span.service.discovery import _coverage_scope_snapshots
from span.service.refs import _claim_ref, _ref_value, _relationship_ref

__all__ = [
    "preflight",
    "_premise_preflight",
    "_classify_current",
    "_classify_coverage_updates",
    "_evaluate_current",
    "coverage_check",
    "_latest_coverages",
    "_refresh_view",
]


def preflight(
    repository_id: str,
    semantic_ids: tuple[m.ClaimRef | m.RelationshipRef, ...],
    *,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> tuple[m.FreshnessUpdate, ...]:
    """Query freshness preflight (plan §9.2 steps 1–4, Addendum B B-05).

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


def _premise_preflight(
    repository_id: str,
    semantic_ids: tuple[m.ClaimRef | m.RelationshipRef, ...],
    *,
    store: SemanticStore,
    bounds: m.QueryBounds,
    max_depth: int = 6,
    live_states: dict[str, m.FreshnessState] | None = None,
) -> tuple[m.FreshnessUpdate, ...]:
    """Bounded transitive premise walk with path-based cycle detection.

    A cycle is reported only when a premise chain leads back to an
    item already on the CURRENT traversal path (true circularity).
    Merely visiting the same premise from two roots (diamond or
    sibling order) is not a cycle. Truncation yields UNVERIFIABLE,
    never silent green.

    ``live_states`` carries per-call live classifications for reached
    premise evidence (S2 §5.2): premises with live direct evidence use
    the live state, not stored freshness. A source can change before
    any other operation marks its premise stale.
    """
    updates: dict[str, m.FreshnessUpdate] = {}
    clean: set[str] = set()

    def _mark(
        rid: str,
        ref: m.ClaimRef | m.RelationshipRef,
        state: m.FreshnessState,
        reason: str,
    ) -> None:
        updates.setdefault(
            rid,
            m.FreshnessUpdate(
                semantic_id=ref, freshness=m.Freshness(state, reason=reason)
            ),
        )

    def _premise_update_state(pid: str) -> m.FreshnessState | None:
        update = updates.get(pid)
        return update.freshness.state if update is not None else None

    def _visit(
        ref: m.ClaimRef | m.RelationshipRef,
        path: tuple[str, ...],
        depth: int,
    ) -> bool:
        """Walk one subtree; True iff fully explored (no truncation)."""
        rid = ref.id.value
        if rid in clean or rid in updates:
            return True
        if depth >= max_depth:
            return False
        try:
            (item,) = store.load_by_refs(repository_id, (ref,))
        except ValueError:
            _mark(
                rid,
                ref,
                m.FreshnessState.UNVERIFIABLE,
                "premise unknown/retired; reassessment required",
            )
            return True
        premises = [
            pref
            for pref in item.basis.input_refs
            if isinstance(pref, (m.ClaimRef, m.RelationshipRef))
        ]
        if not premises:
            clean.add(rid)
            return True
        complete = True
        for pref in premises:
            pid = pref.id.value
            if pid == rid or pid in path:
                _mark(
                    rid,
                    ref,
                    m.FreshnessState.UNVERIFIABLE,
                    "premise cycle; unverifiable until reconciled",
                )
                continue
            if not _visit(pref, path + (rid,), depth + 1):
                complete = False
                continue
            state = _premise_update_state(pid)
            if state is None and live_states is not None:
                state = live_states.get(pid)
            if state is None:
                try:
                    (premise,) = store.load_by_refs(repository_id, (pref,))
                except ValueError:
                    _mark(
                        rid,
                        ref,
                        m.FreshnessState.STALE,
                        "premise retired/unknown; dependent reassessment " "required",
                    )
                    continue
                state = premise.freshness.state
            if state is m.FreshnessState.UNVERIFIABLE:
                _mark(
                    rid,
                    ref,
                    m.FreshnessState.UNVERIFIABLE,
                    "upstream premise unverifiable; dependent " "reassessment required",
                )
            elif state is not m.FreshnessState.CURRENT:
                _mark(
                    rid,
                    ref,
                    m.FreshnessState.STALE,
                    "upstream premise noncurrent; dependent reassessment " "required",
                )
        if complete and rid not in updates:
            clean.add(rid)
        return complete

    for ref in semantic_ids:
        if not _visit(ref, (), 0):
            _mark(
                ref.id.value,
                ref,
                m.FreshnessState.UNVERIFIABLE,
                "premise frontier truncated; outstanding scope",
            )
        if len(clean) + len(updates) > bounds.max_results * 4 + len(semantic_ids):
            _mark(
                ref.id.value,
                ref,
                m.FreshnessState.UNVERIFIABLE,
                "premise frontier truncated; outstanding scope",
            )
            break
    return tuple(updates.values())


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
    by_id = {_ref_value(u.semantic_id): u.freshness for u in updates}

    def _with_freshness_claim(claim: m.SemanticClaim) -> m.SemanticClaim:
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

    def _with_freshness_rel(
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

    return (
        tuple(_with_freshness_claim(c) for c in claims),
        tuple(_with_freshness_rel(r) for r in relationships),
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
