"""Span pure freshness classification (plan Phase 1.4, §9.2).

Compares stored supporting fingerprints against current evidence
fingerprints and classifies each item CURRENT, STALE, or UNVERIFIABLE.
No stored item may be presented as current without this verification
(plan I-10). All functions are pure.
"""

from __future__ import annotations

from collections.abc import Mapping as _Mapping

from span.core import model as m

__all__ = [
    "classify_dependency",
    "classify_all",
    "classify_coverage",
]


def classify_dependency(
    observed_fingerprint: str, current_fingerprint: str | None
) -> m.Freshness:
    """Classify one evidence dependency (pure, deterministic)."""
    if current_fingerprint is None:
        return m.Freshness(
            state=m.FreshnessState.UNVERIFIABLE,
            supporting_revision_or_fingerprint=observed_fingerprint,
            reason="current evidence fingerprint unavailable",
        )
    if current_fingerprint == observed_fingerprint:
        return m.Freshness(
            state=m.FreshnessState.CURRENT,
            supporting_revision_or_fingerprint=observed_fingerprint,
            reason="stored fingerprint matches current evidence fingerprint",
        )
    return m.Freshness(
        state=m.FreshnessState.STALE,
        supporting_revision_or_fingerprint=observed_fingerprint,
        reason="evidence fingerprint changed since indexing",
    )


def classify_all(
    dependencies: tuple[m.EvidenceDependency, ...],
    current: _Mapping[str, str | None],
) -> tuple[m.FreshnessUpdate, ...]:
    """Classify every dependency; one update per stale/unverifiable item.

    Current items need no update (their stored state already agrees).
    Keyed by evidence id; a missing key means unverifiable. Deterministic
    order follows the input dependency order.
    """
    updates: list[m.FreshnessUpdate] = []
    for dep in dependencies:
        freshness = classify_dependency(
            dep.observed_fingerprint, current.get(dep.evidence_ref.evidence_id.value)
        )
        if freshness.state is not m.FreshnessState.CURRENT:
            updates.append(
                m.FreshnessUpdate(semantic_id=dep.semantic_id, freshness=freshness)
            )
    return tuple(updates)


def classify_coverage(
    recorded: m.CoverageDependency,
    current_inventory_fingerprint: str | None,
    current_seed_fingerprints: _Mapping[str, str | None],
) -> m.Freshness:
    """Classify one discovery-coverage record (plan §8.5/§9.2 step 0).

    The recorded inventory fingerprint covers MEMBERSHIP (which sources
    existed at discovery): gained or lost sources — including a newly
    added authority document with no existing dependants — mean the
    discovery behind the covered conclusion may be incomplete. Content
    changes to already-known sources are classified per-item through
    direct dependencies instead, preserving MI-07 partial staleness:
    unrelated changes never invalidate unrelated assertions. Recorded
    authority seeds are compared by content: a moved or missing seed
    invalidates what explicitly relied on it.
    """
    if current_inventory_fingerprint is None:
        return m.Freshness(
            state=m.FreshnessState.UNVERIFIABLE,
            supporting_revision_or_fingerprint=recorded.inventory_fingerprint,
            reason="current evidence inventory fingerprint unavailable",
        )
    if current_inventory_fingerprint != recorded.inventory_fingerprint:
        return m.Freshness(
            state=m.FreshnessState.STALE,
            supporting_revision_or_fingerprint=recorded.inventory_fingerprint,
            reason="evidence inventory changed since discovery",
        )
    for seed in recorded.seed_fingerprints:
        current = current_seed_fingerprints.get(seed.evidence_id.value)
        if current is None:
            return m.Freshness(
                state=m.FreshnessState.UNVERIFIABLE,
                supporting_revision_or_fingerprint=recorded.inventory_fingerprint,
                reason=(
                    "authority seed fingerprint unavailable: " + seed.evidence_id.value
                ),
            )
        if current != seed.fingerprint:
            return m.Freshness(
                state=m.FreshnessState.STALE,
                supporting_revision_or_fingerprint=recorded.inventory_fingerprint,
                reason=(
                    "authority seed changed since discovery: " + seed.evidence_id.value
                ),
            )
    return m.Freshness(
        state=m.FreshnessState.CURRENT,
        supporting_revision_or_fingerprint=recorded.inventory_fingerprint,
        reason="discovery coverage matches current inventory and seeds",
    )
