"""Span service subject resolution + store-read plumbing (v0.6 §14 Amendment A-01).

Identity resolution over the structural source (observations only —
ambiguity is never overridden, names alone are never identity, §4.2)
plus subject-state and coverage-enumeration reads. Verbatim from
``span.service_operations``; only the module path changed.
"""

from __future__ import annotations

from span.core import model as m
from span.ports.evidence import EvidenceSource
from span.ports.store import SemanticStore
from span.ports.structural import StructuralDirection, StructuralSource
from span.service.discovery import check_inventory_identity


from span.service.resolution.identity import (
    _make_ambiguous,
    _make_not_found,
    _make_resolved,
    _subject_key,
)


def _has_established_semantic_state(
    repository_id: str,
    subject: m.Subject,
    *,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> bool:
    """True when the subject has persisted semantic state.

    Established means the exact SubjectId resolves from the store and
    carries at least one canonical claim, canonical relationship, or
    question coverage. A bare structural candidate or bare subject row
    with none of these does not block contextual path resolution.
    """
    sid = subject.subject_id
    found = store.load_subjects(repository_id, (sid,))
    if not found:
        return False
    claims = store.load_claims(repository_id, (sid,), (), bounds, None)
    if claims.items:
        return True
    rels = store.load_relationships(
        repository_id,
        (sid,),
        (),
        StructuralDirection.BOTH,
        bounds,
        None,
    )
    if rels.items:
        return True
    return store.count_question_coverages(repository_id, None, (sid,)) > 0


def _bounded_path_inventory(
    repository_id: str,
    path: str,
    *,
    evidence: EvidenceSource,
    bounds: m.QueryBounds,
) -> tuple[m.EvidenceInventoryItem, ...] | None:
    """Bounded exact-path evidence lookup; None means unproven.

    Uses inventory_evidence directly (per-page bound max_evidence_units)
    with a cumulative contextual ceiling of max_results distinct
    evidence identities. Paging branches on bound_info.truncated (a
    stray token with truncated=False is ignored); truncated=True
    without a continuation token, a non-advancing token, a token cycle
    (seen_tokens, same pattern as enumerate_target_inventory), an
    empty truncated page, a conflicting EvidenceId identity, or an
    over-ceiling distinct set all fail closed as unproven. Identical
    duplicate identities are collapsed per the stable-identity rule
    and never consume the budget twice. Never concludes from a
    first-N prefix.
    """
    scope = m.EvidenceScope(paths=(path,), evidence_refs=())
    raw: list[m.EvidenceInventoryItem] = []
    seen_tokens: set[str | None] = set()
    page_token: str | None = None
    deduped: tuple[m.EvidenceInventoryItem, ...] = ()
    fetches = 0
    while True:
        fetches += 1
        page = evidence.inventory_evidence(repository_id, scope, bounds, page_token)
        raw.extend(page.items)
        try:
            deduped = check_inventory_identity(tuple(raw))
        except ValueError:
            return None
        if len(deduped) > bounds.max_results:
            return None
        if not page.bound_info.truncated:
            break
        if fetches > bounds.max_results:
            return None
        nxt = page.bound_info.continuation_token
        if nxt is None or nxt in seen_tokens or nxt == page_token:
            return None
        if not page.items:
            return None
        seen_tokens.add(page_token)
        page_token = nxt
    return deduped


def _load_contextual_semantics(
    repository_id: str,
    evidence_id_values: tuple[str, ...],
    *,
    store: SemanticStore,
) -> tuple[tuple[m.SemanticClaim, ...], tuple[m.SemanticRelationship, ...]]:
    """Reverse lookup: evidence ids → deps → canonical items.

    Unknown refs fail closed per the store contract: a dependency
    pointing at a missing semantic record is corrupt state, and the
    lookup raises instead of resolving from a silently partial set.
    No unknown subject is manufactured.
    """
    if not evidence_id_values:
        return (), ()
    deps = store.load_evidence_records(repository_id, tuple(evidence_id_values))
    if not deps:
        return (), ()
    seen: set[tuple[str, str]] = set()
    refs: list[m.ClaimRef | m.RelationshipRef] = []
    for dep in deps:
        ref = dep.semantic_id
        key = (type(ref).__name__, ref.id.value)
        if key not in seen:
            seen.add(key)
            refs.append(ref)
    loaded = store.load_by_refs(repository_id, tuple(refs))
    claims = tuple(item for item in loaded if isinstance(item, m.SemanticClaim))
    rels = tuple(item for item in loaded if isinstance(item, m.SemanticRelationship))
    return claims, rels


def _direct_candidate_ids(
    claims: tuple[m.SemanticClaim, ...],
    rels: tuple[m.SemanticRelationship, ...],
) -> tuple[m.SubjectId, ...]:
    """Direct candidates: claim subjects + MEMBER_OF sources only.

    No fallback from arbitrary relationship endpoints: DEPENDS_ON,
    PRODUCES, CONSUMES, CARRIES, TRANSFORMS_TO, IMPLEMENTS,
    CROSSES_BOUNDARY and others never establish local context.
    """
    out: dict[tuple[str, str, str], m.SubjectId] = {}
    for claim in claims:
        out.setdefault(_subject_key(claim.subject), claim.subject)
    for rel in rels:
        if rel.kind is not m.RelationshipKind.MEMBER_OF:
            continue
        out.setdefault(_subject_key(rel.source), rel.source)
    return tuple(
        sorted(
            out.values(),
            key=lambda s: (
                s.subject_kind.value,
                s.canonical_locator,
                s.repository_id,
            ),
        )
    )


def _current_parents(
    repository_id: str,
    sid: m.SubjectId,
    *,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> tuple[m.SubjectId, ...] | None:
    """Distinct CURRENT parents via existing membership forms.

    Returns None when the parent set cannot be proven complete
    (truncated loads). STALE/UNVERIFIABLE membership — evaluated
    through the read-only _evaluate_current (direct + premise +
    coverage, never persisting) or stored non-current freshness —
    never proves a parent. Never calls preflight/coverage_check/
    _refresh_view here.
    """
    claim_page = store.load_claims(
        repository_id,
        (sid,),
        (m.ClaimKind.CAPABILITY_MEMBERSHIP,),
        bounds,
        None,
    )
    if claim_page.bound_info.truncated:
        return None
    rel_page = store.load_relationships(
        repository_id,
        (sid,),
        (m.RelationshipKind.MEMBER_OF,),
        StructuralDirection.DOWNSTREAM,
        bounds,
        None,
    )
    if rel_page.bound_info.truncated:
        return None
    member_claims = [
        c
        for c in claim_page.items
        if c.subject == sid and isinstance(c.value, m.CapabilityMembershipValue)
    ]
    member_rels = [
        r
        for r in rel_page.items
        if r.source == sid and r.kind is m.RelationshipKind.MEMBER_OF
    ]
    if not member_claims and not member_rels:
        return ()
    refs: list[m.ClaimRef | m.RelationshipRef] = [
        m.ClaimRef(id=c.claim_id) for c in member_claims
    ] + [m.RelationshipRef(id=r.relationship_id) for r in member_rels]
    items: list[m.SemanticClaim | m.SemanticRelationship] = [
        *member_claims,
        *member_rels,
    ]
    from span.service.freshness import _evaluate_current

    updates, _ = _evaluate_current(
        repository_id,
        tuple(refs),
        tuple(items),
        evidence=evidence,
        store=store,
        bounds=bounds,
    )
    bad: set[tuple[str, str]] = set()
    for update in updates:
        ref = update.semantic_id
        bad.add((type(ref).__name__, ref.id.value))
    parents: dict[tuple[str, str, str], m.SubjectId] = {}
    for claim in member_claims:
        if ("ClaimRef", claim.claim_id.value) in bad:
            continue
        if claim.freshness.state is not m.FreshnessState.CURRENT:
            continue
        value = claim.value
        if not isinstance(value, m.CapabilityMembershipValue):
            continue
        parents.setdefault(_subject_key(value.parent), value.parent)
    for rel in member_rels:
        if ("RelationshipRef", rel.relationship_id.value) in bad:
            continue
        if rel.freshness.state is not m.FreshnessState.CURRENT:
            continue
        parents.setdefault(_subject_key(rel.target), rel.target)
    return tuple(
        sorted(
            parents.values(),
            key=lambda s: (
                s.subject_kind.value,
                s.canonical_locator,
                s.repository_id,
            ),
        )
    )


def _context_pair(
    resolution: m.SubjectResolution,
) -> tuple[m.SubjectResolution, m.SubjectResolution]:
    """Orientation and trace-root resolutions are the same failure here."""
    return (resolution, resolution)


def _context_candidate_ids(
    repository_id: str,
    inventory: tuple[m.EvidenceInventoryItem, ...],
    selector: m.SubjectSelector,
    *,
    store: SemanticStore,
) -> tuple[tuple[m.SubjectId, ...], set[m.SubjectKind] | None]:
    """Direct candidates reached through the path's evidence, kind-filtered."""
    evidence_ids = tuple(
        dict.fromkeys(item.evidence_ref.evidence_id.value for item in inventory)
    )
    claims, relationships = _load_contextual_semantics(
        repository_id, evidence_ids, store=store
    )
    candidate_ids = _direct_candidate_ids(claims, relationships)
    allowed: set[m.SubjectKind] | None = (
        set(selector.expected_kinds) if selector.expected_kinds else None
    )
    if allowed is not None:
        candidate_ids = tuple(
            subject_id
            for subject_id in candidate_ids
            if subject_id.subject_kind in allowed
        )
    return candidate_ids, allowed


def _context_known_subjects(
    repository_id: str,
    candidate_ids: tuple[m.SubjectId, ...],
    *,
    store: SemanticStore,
) -> list[m.Subject] | None:
    """Load every candidate row; any missing row makes the set untrustworthy."""
    found = store.load_subjects(repository_id, candidate_ids)
    by_key = {_subject_key(subject.subject_id): subject for subject in found}
    if any(_subject_key(subject_id) not in by_key for subject_id in candidate_ids):
        # A referenced candidate has no canonical Subject row (claim /
        # relationship endpoints need not have one). The candidate set is
        # untrustworthy: fail closed as unproven, never collapse to the
        # surviving subset.
        return None
    return [by_key[_subject_key(subject_id)] for subject_id in candidate_ids]


def _single_context_resolution(
    local: m.Subject,
    allowed: set[m.SubjectKind] | None,
    *,
    repository_id: str,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> tuple[m.SubjectResolution, m.SubjectResolution]:
    """One direct candidate: orientation is it; trace root may promote to a parent."""
    orientation = _make_resolved(local, bounds)
    parents = _current_parents(
        repository_id,
        local.subject_id,
        evidence=evidence,
        store=store,
        bounds=bounds,
    )
    if parents is None:
        return (
            orientation,
            _make_ambiguous((), bounds, truncated=True, truncated_category="context"),
        )
    if not parents:
        return (orientation, _make_resolved(local, bounds))
    if allowed is not None:
        # Promotion must preserve the selector's kind constraint: a parent
        # outside expected_kinds can never become the trace subject. Narrow to
        # allowed parents first; with none allowed the local candidate stands.
        parents = tuple(parent for parent in parents if parent.subject_kind in allowed)
        if not parents:
            return (orientation, _make_resolved(local, bounds))
    if len(parents) == 1:
        loaded = store.load_subjects(repository_id, parents)
        if not loaded:
            return (
                orientation,
                _make_ambiguous(
                    (), bounds, truncated=True, truncated_category="context"
                ),
            )
        return (orientation, _make_resolved(loaded[0], bounds))
    if len(parents) > bounds.max_subjects or len(parents) > bounds.max_results:
        return (
            orientation,
            _make_ambiguous((), bounds, truncated=True, truncated_category="context"),
        )
    loaded = store.load_subjects(repository_id, parents)
    return (orientation, _make_ambiguous(loaded, bounds))


def _ancestor_chain(
    repository_id: str,
    start: m.SubjectId,
    *,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> tuple[list[m.SubjectId] | None, str | None]:
    """Walk one candidate's CURRENT-membership ancestry.

    Returns the chain (self first) or a failure reason: ``"bound"`` means the
    walk hit a depth/identity bound and must read truncated; ``"multi"`` means a
    subject had more than one current parent and is ambiguous, not truncated.
    """
    chain: list[m.SubjectId] = [start]
    seen: set[tuple[str, str, str]] = {_subject_key(start)}
    current = start
    while True:
        parents = _current_parents(
            repository_id,
            current,
            evidence=evidence,
            store=store,
            bounds=bounds,
        )
        if parents is None:
            return None, "bound"
        if not parents:
            return chain, None
        if len(parents) > 1:
            return None, "multi"
        if len(chain) - 1 >= bounds.max_depth:
            return None, "bound"
        parent = parents[0]
        key = _subject_key(parent)
        if key in seen or len(chain) + 1 > bounds.max_subjects:
            return None, "bound"
        chain.append(parent)
        seen.add(key)
        current = parent


def _common_ancestor_resolution(
    known: list[m.Subject],
    allowed: set[m.SubjectKind] | None,
    *,
    repository_id: str,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> tuple[m.SubjectResolution, m.SubjectResolution]:
    """Many direct candidates: resolve to their most-specific common ancestor."""
    chains: dict[tuple[str, str, str], list[m.SubjectId]] = {}
    for subject in known:
        sid = subject.subject_id
        chain, failure = _ancestor_chain(
            repository_id,
            sid,
            evidence=evidence,
            store=store,
            bounds=bounds,
        )
        if failure == "bound":
            return _context_pair(
                _make_ambiguous(
                    tuple(known), bounds, truncated=True, truncated_category="context"
                )
            )
        if failure is not None or chain is None:
            return _context_pair(_make_ambiguous(tuple(known), bounds))
        chains[_subject_key(sid)] = chain
    distinct: set[tuple[str, str, str]] = set()
    for chain in chains.values():
        distinct.update(_subject_key(sid) for sid in chain)
    if len(distinct) > bounds.max_subjects or len(distinct) > bounds.max_results:
        return _context_pair(
            _make_ambiguous(
                tuple(known), bounds, truncated=True, truncated_category="context"
            )
        )
    all_ids: list[m.SubjectId] = []
    for chain in chains.values():
        all_ids.extend(chain)
    loaded_all = store.load_subjects(repository_id, tuple(dict.fromkeys(all_ids)))
    loaded_by_key = {
        _subject_key(subject.subject_id): subject for subject in loaded_all
    }
    for chain in chains.values():
        for sid in chain:
            if _subject_key(sid) not in loaded_by_key:
                return _context_pair(
                    _make_ambiguous(
                        tuple(known),
                        bounds,
                        truncated=True,
                        truncated_category="context",
                    )
                )
    first_chain = next(iter(chains.values()))
    chain_sets = [{_subject_key(sid) for sid in chain} for chain in chains.values()]
    common: m.SubjectId | None = None
    for sid in first_chain:
        key = _subject_key(sid)
        if all(key in other for other in chain_sets):
            common = sid
            break
    if common is None:
        return _context_pair(_make_ambiguous(tuple(known), bounds))
    if allowed is not None and common.subject_kind not in allowed:
        # The common ancestor is outside the selector's kind constraint: it may
        # not resolve. Remain ambiguous over the allowed direct candidates.
        return _context_pair(_make_ambiguous(tuple(known), bounds))
    common_subject = loaded_by_key[_subject_key(common)]
    return _context_pair(_make_resolved(common_subject, bounds))


def _resolve_contextual_subjects(
    repository_id: str,
    selector: m.SubjectSelector,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> tuple[m.SubjectResolution, m.SubjectResolution]:
    """Contextual path → (orientation, trace-root) resolutions.

    Pure retrieval of established semantics: exact path inventory → reverse
    evidence deps → direct candidates (claims + MEMBER_OF) → CURRENT-membership
    chains → most-specific common ancestor. Never invents subjects, never remaps
    coverage, never persists.
    """
    _ = structural
    if selector.exact_subject_id is not None or not selector.name_or_locator:
        return _context_pair(_make_not_found(bounds))
    inventory = _bounded_path_inventory(
        repository_id,
        selector.name_or_locator,
        evidence=evidence,
        bounds=bounds,
    )
    if inventory is None:
        return _context_pair(
            _make_ambiguous((), bounds, truncated=True, truncated_category="inventory")
        )
    if not inventory:
        return _context_pair(_make_not_found(bounds))
    candidate_ids, allowed = _context_candidate_ids(
        repository_id, inventory, selector, store=store
    )
    if not candidate_ids:
        return _context_pair(_make_not_found(bounds))
    if len(candidate_ids) > bounds.max_subjects:
        return _context_pair(
            _make_ambiguous((), bounds, truncated=True, truncated_category="context")
        )
    known = _context_known_subjects(repository_id, candidate_ids, store=store)
    if known is None:
        return _context_pair(
            _make_ambiguous((), bounds, truncated=True, truncated_category="context")
        )
    if not known:
        return _context_pair(_make_not_found(bounds))
    if len(known) == 1:
        return _single_context_resolution(
            known[0],
            allowed,
            repository_id=repository_id,
            evidence=evidence,
            store=store,
            bounds=bounds,
        )
    return _common_ancestor_resolution(
        known,
        allowed,
        repository_id=repository_id,
        evidence=evidence,
        store=store,
        bounds=bounds,
    )
