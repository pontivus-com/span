"""Span service evidence discovery (plan §6.2, §8.4–§8.5; v0.6 §14 Amendment A-01).

Relevance only — nothing selected here carries authority (authority is
established solely by §6.3 validation in the core). Verbatim from
span.service_operations; only the module path changed.
"""

from __future__ import annotations

from span.core import model as m
from span.ports.evidence import EvidenceSource
from span.ports.structural import StructuralDirection, StructuralSource

__all__ = [
    "_inventory_snapshot",
    "discover_evidence",
    "_coverage_for_task",
    "_coverage_scope_snapshots",
    "_read_units_within_bytes",
    "enumerate_target_inventory",
    "check_inventory_identity",
]


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
    precomputed: tuple[tuple[tuple[str, str], ...], dict[str, str]] | None = None,
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

    ``precomputed`` accepts one shared (entries, fingerprints) pair —
    typically one walk per scope per status call whose seed union covers
    every coverage examined against that scope. Same bytes, no extra
    walks.
    """
    import hashlib as _hashlib

    if precomputed is not None:
        entries, fingerprints = precomputed
    else:
        entries, fingerprints = evidence.list_inventory_entries(
            repository_id,
            discovery_scope,
            tuple(loc for loc, _ in seeds),
        )
    pairs = sorted(eid for _, eid in entries)
    membership = _hashlib.sha256(repr(pairs).encode("utf-8")).hexdigest()
    return membership, {eid: fingerprints.get(loc, "") for loc, eid in seeds}


def discover_evidence(
    repository_id: str,
    subject: m.Subject,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    authority_seeds: tuple[m.EvidenceRef, ...] = (),
    question_terms: tuple[str, ...] = (),
    target_scope: m.EvidenceScope | None = None,
) -> m.EvidenceSelection:
    """Generic evidence discovery (plan §6.2 steps 1–6).

    Resolve (caller-supplied) → bounded structural context → directly
    referenced sources → explicit authority seeds → identity/term-anchored
    text search → §8-bounded set. Relevance only: nothing selected here
    carries authority (plan §6.1; authority is established only by §6.3
    validation in the core).
    """
    sid = subject.subject_id
    edges = structural.edges(repository_id, sid, (), StructuralDirection.BOTH, bounds)
    observations = [
        m.StructuralObservation(
            source_subject=edge.source,
            edge_kind=edge.kind,
            target_subject=edge.target,
            location=None,
            repository_state=state,
        )
        for edge in edges.items
    ]
    locations = structural.locations(repository_id, sid, bounds).items
    # J-1/S1.2: the bounded discovery scope is the exact search universe
    # for membership freshness and anchor matching — the subject's
    # current structural locations plus directly observed edge evidence
    # locations, unioned with the exact declared target boundary in
    # target mode (D-03 rule 1). Authority seeds stay separate direct
    # dependencies and never enlarge this scope.
    scope_paths = {
        loc.location.locator for loc in locations if loc.location is not None
    }
    scope_paths |= {
        edge.evidence.locator for edge in edges.items if edge.evidence is not None
    }
    scope_refs: tuple[m.EvidenceRef, ...] = ()
    if target_scope is not None and (target_scope.paths or target_scope.evidence_refs):
        # D-03 rule 1: target-mode discovery intersects the exact declared
        # target boundary. When the admitted area has no in-target
        # structural location, the declared (host-bounded) boundary is
        # the scope — never an automatic whole-repository default.
        target_paths = set(target_scope.paths)
        within = scope_paths & target_paths
        scope_paths = within if within else target_paths
        scope_refs = tuple(target_scope.evidence_refs)
    if not scope_paths and not scope_refs:
        # D-03 rule 3: semantic-only root fallback — the subject's own
        # path/prefix scope. A non-path locator yields a discovery-empty
        # root; its admitted questions must then carry explicit in-scope
        # evidence or remain UNVERIFIABLE (B-05), never a durable
        # negative fact.
        scope_paths = {sid.canonical_locator}
    discovery_scope = m.EvidenceScope(
        paths=tuple(sorted(scope_paths)), evidence_refs=scope_refs
    )
    observations.extend(
        m.StructuralObservation(
            source_subject=sid,
            edge_kind=None,
            target_subject=None,
            location=loc.location,
            repository_state=state,
        )
        for loc in locations
    )
    selection = evidence.select_evidence(
        repository_id, sid, tuple(observations), authority_seeds, bounds
    )
    anchors = [subject.display_name, sid.canonical_locator.rsplit("/", 1)[-1]]
    anchors.extend(question_terms)
    anchors = sorted({a for a in anchors if a})
    if not anchors:
        return m.EvidenceSelection(
            selected_refs=selection.selected_refs,
            bound_info=selection.bound_info,
            discovery_scope=discovery_scope,
        )
    inventory = evidence.inventory_evidence(repository_id, discovery_scope, bounds)
    selected = list(selection.selected_refs)
    seen = {ref.evidence_id.value for ref in selected}
    for item in inventory.items:
        if item.evidence_ref.evidence_id.value in seen:
            continue
        try:
            (unit,) = evidence.read_evidence((item.evidence_ref,), bounds)
        except ValueError:
            continue
        if any(anchor in unit.content for anchor in anchors):
            selected.append(item.evidence_ref)
            seen.add(item.evidence_ref.evidence_id.value)
        if len(selected) >= bounds.max_evidence_units:
            break
    kept = tuple(selected[: bounds.max_evidence_units])
    # Store-only fallback (Addendum B baseline roots): a subject with
    # no structural observations at all (registered semantic-only
    # root) would otherwise receive an empty task. Top up from the
    # deterministic path-prefix inventory under the subject locator —
    # the subsystem's own files, sorted — so the audit has material
    # to admit member questions from. Structural subjects never reach
    # here (they always carry location observations).
    truncated = len(kept) < len(selected)
    if not observations and len(kept) < bounds.max_evidence_units:
        prefix_page = evidence.inventory_evidence(
            repository_id,
            m.EvidenceScope(paths=(sid.canonical_locator,), evidence_refs=()),
            bounds,
        )
        for item in prefix_page.items:
            if len(kept) >= bounds.max_evidence_units:
                break
            if item.evidence_ref.evidence_id.value in seen:
                continue
            seen.add(item.evidence_ref.evidence_id.value)
            kept = kept + (item.evidence_ref,)
        truncated = truncated or prefix_page.bound_info.truncated
    return m.EvidenceSelection(
        selected_refs=kept,
        discovery_scope=discovery_scope,
        bound_info=m.BoundInfo(
            requested_max_results=bounds.max_evidence_units,
            requested_max_depth=0,
            returned_results=len(kept),
            truncated=truncated,
            truncated_category="discovery" if truncated else None,
            continuation_token=None,
        ),
    )


def _coverage_for_task(
    repository_id: str,
    subjects: tuple[m.SubjectId, ...],
    *,
    evidence: EvidenceSource,
    seeds: tuple[m.EvidenceRef, ...],
    question: m.SemanticQuestionScope | None = None,
    discovery_scope: m.EvidenceScope,
) -> m.CoverageDependency:
    """Build the discovery-coverage record for one unit (plan §8.5, J-1).

    ``discovery_scope`` is the exact scope used to construct the pending
    unit; the write path passes it verbatim and never re-derives it from
    final agent output. Current task coverage always carries the actual
    non-empty discovery scope; an empty scope is rejected rather than
    interpreted as repository-global coverage.
    """
    import datetime as _datetime

    if not discovery_scope.paths and not discovery_scope.evidence_refs:
        raise ValueError("task discovery scope must be non-empty for current coverage")
    inventory_fp, seed_map = _inventory_snapshot(
        repository_id,
        discovery_scope,
        evidence=evidence,
        seeds=tuple((seed.locator, seed.evidence_id.value) for seed in seeds),
    )
    return m.CoverageDependency(
        scope_subjects=subjects,
        discovery_scope=discovery_scope,
        inventory_fingerprint=inventory_fp,
        seed_fingerprints=tuple(
            m.SeedFingerprint(
                evidence_id=seed.evidence_id,
                locator=seed.locator,
                fingerprint=seed_map.get(seed.evidence_id.value, ""),
            )
            for seed in seeds
        ),
        observed_at=_datetime.datetime.now(_datetime.timezone.utc),
        question=question,
    )


def _coverage_scope_snapshots(
    repository_id: str,
    coverages: tuple[m.CoverageDependency, ...],
    *,
    evidence: EvidenceSource,
) -> dict[m.EvidenceScope, tuple[str, dict[str, str]]]:
    """One membership snapshot per distinct recorded discovery scope (J-1).

    Rows sharing a canonical scope share one metadata walk; seed
    locators are unioned within each scope and may resolve outside it.
    A deterministic efficiency projection, never a semantic cache.
    """
    seeds_by_scope: dict[m.EvidenceScope, list[tuple[str, str]]] = {}
    for cov in coverages:
        bucket = seeds_by_scope.setdefault(cov.discovery_scope, [])
        for sf in cov.seed_fingerprints:
            pair = (sf.locator, sf.evidence_id.value)
            if pair not in bucket:
                bucket.append(pair)
    return {
        scope: _inventory_snapshot(
            repository_id, scope, evidence=evidence, seeds=tuple(seeds)
        )
        for scope, seeds in seeds_by_scope.items()
    }


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
