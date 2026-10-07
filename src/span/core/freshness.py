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
