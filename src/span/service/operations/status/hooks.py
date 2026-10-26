"""Span service status operation (plan §11.8; v0.6 §14 Amendment A-01).

Currency and verification over stored semantics, with hook fast
path and resume. Verbatim from ``span.service_operations``; only the
module path changed.
"""

from __future__ import annotations


from span.core import model as m
from span.ports.evidence import EvidenceSource
from span.ports.store import SemanticStore
from span.ports.structural import StructuralSource

from span.service.freshness import (
    _classify_current,
    _latest_coverages,
)
from span.service.refs import (
    _claim_ref,
    _relationship_ref,
)
from span.service.repository import (
    _is_initialized,
)
from span.service.resolution import (
    _load_subject_state,
    _resolve_scope_subjects,
    resolve_scope_frontier,
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
