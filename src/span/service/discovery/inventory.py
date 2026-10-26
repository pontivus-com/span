"""Span service evidence discovery (plan §6.2, §8.4–§8.5; v0.6 §14 Amendment A-01).

Relevance only — nothing selected here carries authority (authority is
established solely by §6.3 validation in the core). Verbatim from
span.service_operations; only the module path changed.
"""

from __future__ import annotations

from span.core import model as m
from span.ports.evidence import EvidenceSource


def check_inventory_identity(
    items: tuple[m.EvidenceInventoryItem, ...],
) -> tuple[m.EvidenceInventoryItem, ...]:
    """Enforce provider stable-identity: dedupe identical, fail on conflict."""
    by_id: dict[str, m.EvidenceInventoryItem] = {}
    for item in items:
        ref = item.evidence_ref
        key = ref.evidence_id.value
        if key in by_id:
            prev = by_id[key].evidence_ref
            if prev.locator != ref.locator or prev.source_kind != ref.source_kind:
                raise ValueError(f"conflicting provider identity for {key!r}")
            continue
        by_id[key] = item
    return tuple(by_id[k] for k in sorted(by_id))


def enumerate_target_inventory(
    repository_id: str,
    scope: m.EvidenceScope,
    *,
    evidence: EvidenceSource,
    bounds: m.QueryBounds,
) -> tuple[m.EvidenceInventoryItem, ...]:
    """Fully enumerate exact-target inventory across all pages.

    Raises ValueError on truncation without continuation progress or on
    conflicting provider identity. Callers map this to UNVERIFIABLE.
    """
    items: list[m.EvidenceInventoryItem] = []
    seen_tokens: set[str | None] = set()
    page_token: str | None = None
    while True:
        page = evidence.inventory_evidence(repository_id, scope, bounds, page_token)
        items.extend(page.items)
        if not page.bound_info.truncated:
            break
        nxt = page.bound_info.continuation_token
        if nxt is None or nxt in seen_tokens:
            raise ValueError("target inventory truncated without continuation progress")
        seen_tokens.add(page_token)
        page_token = nxt
    return check_inventory_identity(tuple(items))


def _inventory_snapshot(
    repository_id: str,
    discovery_scope: m.EvidenceScope,
    *,
    evidence: EvidenceSource,
    seeds: tuple[tuple[str, str], ...] = (),
    precomputed: tuple[str, dict[str, str]] | None = None,
) -> tuple[str, dict[str, str]]:
    """Inventory snapshot plus per-seed map (plan §8.5, J-1).

    Membership is enumerated over ``discovery_scope`` only. An empty
    scope enumerates the repository inventory, which is meaningful for
    initialization and inventory operations; persisted task coverage
    requires a non-empty scope. The combined fingerprint covers
    FROM-THAT-SCOPE membership,
    not content: newly added in-scope sources are visible even with no
    existing dependants, while content changes to known sources stay
    per-item through direct dependencies (MI-07 partial staleness).
    Seed content fingerprints come from the same metadata walk and may
    resolve outside the scope without enlarging membership.

    ``precomputed`` accepts one shared (membership, seed map) pair — typically
    one walk per scope per status call whose seed union covers every coverage
    examined against that scope. Same bytes, no extra walks.
    """
    import hashlib as _hashlib

    if precomputed is not None:
        # One walk per scope: the caller already produced this scope's
        # membership fingerprint and per-seed map.
        return precomputed
    entries, fingerprints = evidence.list_inventory_entries(
        repository_id,
        discovery_scope,
        tuple(loc for loc, _ in seeds),
    )
    pairs = sorted(eid for _, eid in entries)
    membership = _hashlib.sha256(repr(pairs).encode("utf-8")).hexdigest()
    return membership, {eid: fingerprints.get(loc, "") for loc, eid in seeds}


def _read_units_within_bytes(
    evidence: EvidenceSource,
    refs: tuple[m.EvidenceRef, ...],
    bounds: m.QueryBounds,
) -> tuple[m.EvidenceUnit, ...]:
    """Read selected refs without breaching the byte budget (§8.4).

    Discovery counts units; the byte budget is enforced here by keeping
    refs that fit and stopping before the first ref that would breach
    it — a selection decision, never a silent bounds widening.
    Oversized singles are skipped (they could never be delivered);
    if nothing fits, the unit fails closed with an actionable message
    instead of dying mid-read.
    """
    units: list[m.EvidenceUnit] = []
    total = 0
    first_failure: str | None = None
    for ref in refs:
        if len(units) >= bounds.max_evidence_units:
            break
        try:
            (unit,) = evidence.read_evidence((ref,), bounds)
        except ValueError as exc:
            # One unreadable ref is skipped so the rest of the selection can
            # still be delivered; its reason is kept for the fail-closed case.
            if first_failure is None:
                first_failure = str(exc)
            continue
        size = len(unit.content.encode("utf-8"))
        if units and total + size > bounds.max_evidence_bytes:
            break
        units.append(unit)
        total += size
    if not units:
        if not refs:
            return ()
        # The provider already names the exact budget that failed; reporting
        # the cause keeps "raise the bound" visible next to "narrow the target".
        if first_failure:
            raise ValueError(f"{first_failure}; raise the bounds or narrow the target")
        raise ValueError(
            "no evidence unit fits the requested bounds; "
            "raise the bounds or narrow the target"
        )
    return tuple(units)
