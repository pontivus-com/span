"""Span service subject resolution + store-read plumbing (v0.6 §14 Amendment A-01).

Identity resolution over the structural source (observations only —
ambiguity is never overridden, names alone are never identity, §4.2)
plus subject-state and coverage-enumeration reads. Verbatim from
``span.service_operations``; only the module path changed.
"""

from __future__ import annotations

from span.core import model as m
from span.core import validation as _validation
from span.ports.evidence import EvidenceSource
from span.ports.store import SemanticStore
from span.ports.structural import StructuralDirection, StructuralSource
from span.service.discovery import check_inventory_identity
from span.shell import paging as _paging

__all__ = [
    "_load_all_coverages_or_defer",
    "_load_subject_state",
    "_has_established_semantic_state",
    "_resolve_contextual_subjects",
    "_resolve_exact_subject",
    "_resolve_query_subject",
    "_resolve_scope_subjects",
    "resolve_scope_frontier",
    "frontier_fingerprint",
    "_resolve_target_subjects",
]


def _load_all_coverages_or_defer(
    repository_id: str,
    scope_root: m.SubjectId | None,
    subject_ids: tuple[m.SubjectId, ...],
    *,
    store: SemanticStore,
    bounds: m.QueryBounds,
    purpose: str,
) -> tuple[m.InterpretationCoverage, ...]:
    """Unbounded coverage enumeration with bounds-safety deferral (B-03).

    Retirement and withdrawal fanout must see every owning question.
    When the total exceeds the operation bounds the owners cannot be
    safely enumerated, so the unit is rejected/deferred with an
    outstanding-scope requirement — never retired with an incomplete
    fanout, and nothing is partially mutated (raise precedes write).
    """
    try:
        total = store.count_question_coverages(repository_id, scope_root, subject_ids)
    except Exception:
        total = None
    if total is not None and total > bounds.max_results:
        raise _validation.InterpretationUnitRejected(
            (
                f"{purpose}: {total} owning questions exceed "
                f"bounds max_results={bounds.max_results}; deferred with "
                "outstanding scope — narrow the scope and resubmit",
            )
        )
    try:
        return store.load_all_question_coverages(repository_id, scope_root, subject_ids)
    except Exception:
        try:
            return store.load_question_coverages(
                repository_id, scope_root, subject_ids, bounds
            )
        except Exception:
            return ()


def _load_subject_state(
    repository_id: str,
    sid: m.SubjectId,
    *,
    store: SemanticStore,
    bounds: m.QueryBounds,
    direction: StructuralDirection = StructuralDirection.BOTH,
    page_token: str | None = None,
) -> tuple[
    tuple[m.SemanticClaim, ...],
    tuple[m.SemanticRelationship, ...],
    str | None,
    str | None,
]:
    """Load one subject's state window plus per-list next tokens.

    The answer-level token carries per-list offsets
    (``pgq:<digest>:<claims_skip>:<rels_skip>:<questions_skip>``); each load windows
    from its own offset, so every item is reachable exactly once across
    pages. The returned tokens are the raw store cursors (``None`` =
    exhausted).
    """
    claims_skip, rels_skip, _ = _paging.parse_service_token(page_token)
    claim_page = store.load_claims(
        repository_id,
        (sid,),
        tuple(m.ClaimKind),
        bounds,
        _paging.next_page_token(claims_skip) if claims_skip else None,
    )
    rel_page = store.load_relationships(
        repository_id,
        (sid,),
        tuple(m.RelationshipKind),
        direction,
        bounds,
        _paging.next_page_token(rels_skip) if rels_skip else None,
    )
    return (
        claim_page.items,
        rel_page.items,
        claim_page.bound_info.continuation_token,
        rel_page.bound_info.continuation_token,
    )


def _resolve_exact_subject(
    repository_id: str,
    sid: m.SubjectId,
    *,
    structural: StructuralSource,
    bounds: m.QueryBounds,
) -> m.Subject | None:
    """Resolve one known SubjectId to its full record (deterministic)."""
    resolution = structural.resolve_subject(
        repository_id,
        m.SubjectSelector(
            exact_subject_id=sid,
            name_or_locator=None,
            expected_kinds=(),
            retrieval_scope_hint=None,
        ),
        bounds,
    )
    if resolution.ambiguity is m.ResolutionAmbiguity.RESOLVED:
        return resolution.candidates[0].subject
    return None


def _resolve_query_subject(
    repository_id: str,
    target: m.SubjectSelector,
    *,
    structural: StructuralSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> m.SubjectResolution:
    """Query-time subject resolution (Addendum A F1 as amended by I S1).

    Explicit ``exact_subject_id`` keeps the existing exact-ID path.
    Otherwise structural resolution and exact stored-locator matches for
    ``name_or_locator`` are merged by complete ``SubjectId`` with the
    §5.1 exact-precedence rule: an exact stored locator defeats
    non-exact structural name candidates; only multiple exact
    identities may remain ambiguous. Stored lookup is exact string
    equality only, never normalization. Truncated sets never resolve.
    Structural-provider failure propagates; no stored fallback on that
    path. ``expected_kinds`` filtering is provider-owned on both paths.
    """
    resolution = structural.resolve_subject(repository_id, target, bounds)
    if target.exact_subject_id is not None:
        if resolution.ambiguity is m.ResolutionAmbiguity.RESOLVED:
            return resolution
        if resolution.ambiguity is m.ResolutionAmbiguity.NOT_FOUND:
            found = store.load_subjects(repository_id, (target.exact_subject_id,))
            if found:
                return m.SubjectResolution(
                    candidates=(
                        m.SubjectCandidate(
                            subject=found[0],
                            structural_evidence=(),
                            rank_basis=m.CandidateRankBasis.EXACT_LOCATOR,
                        ),
                    ),
                    ambiguity=m.ResolutionAmbiguity.RESOLVED,
                    bound_info=m.BoundInfo(
                        requested_max_results=bounds.max_subjects,
                        requested_max_depth=0,
                        returned_results=1,
                        truncated=False,
                        truncated_category=None,
                        continuation_token=None,
                    ),
                )
        return resolution
    query = target.name_or_locator
    if not query:
        return resolution
    stored_page = store.load_subjects_by_locator(
        repository_id, query, target.expected_kinds, bounds
    )
    if not stored_page.items:
        return resolution
    stored_by_id: dict[tuple[str, str, str], m.Subject] = {}
    for subject in stored_page.items:
        sid = subject.subject_id
        stored_by_id[
            (sid.repository_id, sid.subject_kind.value, sid.canonical_locator)
        ] = subject
    structural_exact: dict[tuple[str, str, str], m.Subject] = {}
    for candidate in resolution.candidates:
        if candidate.rank_basis is m.CandidateRankBasis.EXACT_LOCATOR:
            sid = candidate.subject.subject_id
            structural_exact[
                (
                    sid.repository_id,
                    sid.subject_kind.value,
                    sid.canonical_locator,
                )
            ] = candidate.subject
    if not structural_exact:
        # Only non-exact structural candidates or NOT_FOUND: exact stored
        # identity wins; non-exact names never defeat it.
        combined = sorted(
            stored_by_id.values(),
            key=lambda s: (
                s.subject_id.subject_kind.value,
                s.subject_id.canonical_locator,
            ),
        )
        truncated = stored_page.bound_info.truncated
        if len(combined) > bounds.max_subjects:
            truncated = True
        kept = tuple(combined[: bounds.max_subjects])
        candidates = tuple(
            m.SubjectCandidate(
                subject=subject,
                structural_evidence=(),
                rank_basis=m.CandidateRankBasis.EXACT_LOCATOR,
            )
            for subject in kept
        )
        if len(kept) == 1 and not truncated:
            return m.SubjectResolution(
                candidates=candidates,
                ambiguity=m.ResolutionAmbiguity.RESOLVED,
                bound_info=m.BoundInfo(
                    requested_max_results=bounds.max_subjects,
                    requested_max_depth=0,
                    returned_results=len(candidates),
                    truncated=False,
                    truncated_category=None,
                    continuation_token=None,
                ),
            )
        return m.SubjectResolution(
            candidates=candidates,
            ambiguity=m.ResolutionAmbiguity.AMBIGUOUS,
            bound_info=m.BoundInfo(
                requested_max_results=bounds.max_subjects,
                requested_max_depth=0,
                returned_results=len(candidates),
                truncated=truncated,
                truncated_category="candidates" if truncated else None,
                continuation_token=None,
            ),
        )
    # Both sides have exact identities: merge by complete SubjectId.
    merged: dict[tuple[str, str, str], m.Subject] = dict(structural_exact)
    for key, subject in stored_by_id.items():
        merged.setdefault(key, subject)
    combined = list(merged.values())
    combined.sort(
        key=lambda s: (
            s.subject_id.subject_kind.value,
            s.subject_id.canonical_locator,
        )
    )
    truncated = stored_page.bound_info.truncated or resolution.bound_info.truncated
    if len(combined) > bounds.max_subjects:
        truncated = True
    kept = tuple(combined[: bounds.max_subjects])
    candidates = tuple(
        m.SubjectCandidate(
            subject=subject,
            structural_evidence=(),
            rank_basis=m.CandidateRankBasis.EXACT_LOCATOR,
        )
        for subject in kept
    )
    if len(kept) == 1 and not truncated:
        ambiguity = m.ResolutionAmbiguity.RESOLVED
    else:
        ambiguity = m.ResolutionAmbiguity.AMBIGUOUS
    return m.SubjectResolution(
        candidates=candidates,
        ambiguity=ambiguity,
        bound_info=m.BoundInfo(
            requested_max_results=bounds.max_subjects,
            requested_max_depth=0,
            returned_results=len(candidates),
            truncated=truncated,
            truncated_category="candidates" if truncated else None,
            continuation_token=None,
        ),
    )


def _resolve_scope_subjects(
    repository_id: str,
    target: m.SubjectSelector | m.EvidenceScope,
    *,
    structural: StructuralSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    evidence: EvidenceSource | None = None,
) -> tuple[tuple[m.Subject, ...], m.ResolutionAmbiguity]:
    if isinstance(target, m.EvidenceScope):
        if evidence is not None:
            return (
                _resolve_target_subjects(
                    repository_id,
                    target,
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    bounds=bounds,
                ),
                m.ResolutionAmbiguity.RESOLVED,
            )
        subjects: list[m.Subject] = []
        paths = list(target.paths) + [ref.locator for ref in target.evidence_refs]
        for path in dict.fromkeys(paths):
            resolution = structural.resolve_subject(
                repository_id,
                m.SubjectSelector(
                    exact_subject_id=None,
                    name_or_locator=path,
                    expected_kinds=(),
                    retrieval_scope_hint=None,
                ),
                bounds,
            )
            subjects.extend(c.subject for c in resolution.candidates)
        seen: set[str] = set()
        unique = []
        for subject in subjects:
            key = subject.subject_id.canonical_locator
            if key not in seen:
                seen.add(key)
                unique.append(subject)
        return tuple(unique), m.ResolutionAmbiguity.RESOLVED
    resolution = _resolve_query_subject(
        repository_id,
        target,
        structural=structural,
        store=store,
        bounds=bounds,
    )
    return (
        tuple(c.subject for c in resolution.candidates),
        resolution.ambiguity,
    )


def _fallback_target_kind(ref: m.EvidenceRef) -> m.SubjectKind:
    if ref.source_kind is m.EvidenceSourceKind.DOCUMENTATION:
        return m.SubjectKind.DOCUMENT
    if ref.source_kind is m.EvidenceSourceKind.TEST_VERIFICATION:
        return m.SubjectKind.TEST_OR_GATE
    if ref.source_kind is m.EvidenceSourceKind.CONFIGURATION:
        return m.SubjectKind.CONFIGURATION
    return m.SubjectKind.COMPONENT


def _inventory_subjects(
    repository_id: str,
    scope: m.EvidenceScope,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    bounds: m.QueryBounds,
) -> dict[tuple[m.SubjectKind, str], m.Subject]:
    """One subject per evidence-inventory item in the scope.

    Structural resolution first; a fallback subject when the provider knows the
    file but no semantic subject exists for it yet.
    """
    items: list[m.EvidenceInventoryItem] = []
    page_token: str | None = None
    while True:
        page = evidence.inventory_evidence(repository_id, scope, bounds, page_token)
        items.extend(page.items)
        next_token = page.bound_info.continuation_token
        if next_token is None:
            break
        if not page.items or next_token == page_token:
            raise ValueError("target evidence inventory did not advance")
        page_token = next_token
    found: dict[tuple[m.SubjectKind, str], m.Subject] = {}
    for item in items:
        locator = item.evidence_ref.locator
        resolution = structural.resolve_subject(
            repository_id,
            m.SubjectSelector(
                exact_subject_id=None,
                name_or_locator=locator,
                expected_kinds=(),
                retrieval_scope_hint=None,
            ),
            bounds,
        )
        subject = None
        if (
            resolution.ambiguity is m.ResolutionAmbiguity.RESOLVED
            and len(resolution.candidates) == 1
            and resolution.candidates[0].subject.subject_id.canonical_locator == locator
        ):
            subject = resolution.candidates[0].subject
        if subject is None:
            subject = m.Subject(
                subject_id=m.SubjectId(
                    repository_id=repository_id,
                    subject_kind=_fallback_target_kind(item.evidence_ref),
                    canonical_locator=locator,
                ),
                display_name=locator.rsplit("/", 1)[-1],
                declared_kind=None,
            )
        found[(subject.subject_id.subject_kind, locator)] = subject
    return found


def _persisted_subjects_in_scope(
    repository_id: str,
    scope: m.EvidenceScope,
    *,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> tuple[m.Subject, ...]:
    """Every persisted subject in the scope, by keyset pages.

    This is the query that replaced the repository-wide subject scan: the
    store filters in SQL on the scope predicate.
    """
    subjects: list[m.Subject] = []
    after: tuple[str, str] | None = None
    while True:
        page = store.load_subjects_in_scope(repository_id, scope, bounds, after)
        subjects.extend(page.items)
        if not page.bound_info.truncated or not page.items:
            break
        last = page.items[-1].subject_id
        after = (last.canonical_locator, last.subject_kind.value)
    return tuple(subjects)


def _merged_scope_subjects(
    repository_id: str,
    scope: m.EvidenceScope,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> tuple[m.Subject, ...]:
    """The scope frontier: persisted subjects plus evidence-derived ones.

    Persisted subjects win over a fallback for the same locator. Ordered by
    ``(locator, kind)`` so a page boundary is deterministic.
    """
    found = _inventory_subjects(
        repository_id, scope, structural=structural, evidence=evidence, bounds=bounds
    )
    for subject in _persisted_subjects_in_scope(
        repository_id, scope, store=store, bounds=bounds
    ):
        sid = subject.subject_id
        found[(sid.subject_kind, sid.canonical_locator)] = subject
    return tuple(
        found[key] for key in sorted(found, key=lambda pair: (pair[1], pair[0].value))
    )


def frontier_fingerprint(subjects: tuple[m.Subject, ...]) -> str:
    """Membership fingerprint binding a continuation to the exact frontier."""
    import hashlib as _hashlib

    payload = "\x00".join(
        f"{subject.subject_id.subject_kind.value}:"
        f"{subject.subject_id.canonical_locator}"
        for subject in subjects
    )
    return _hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def resolve_scope_frontier(
    repository_id: str,
    scope: m.EvidenceScope,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    offset: int = 0,
) -> tuple[tuple[m.Subject, ...], int, str]:
    """One frontier page plus the total and the membership fingerprint.

    ``offset`` is a position in the ordered frontier. The fingerprint lets the
    caller bind a continuation to the membership it was issued against, so a
    changed scope restarts instead of silently skipping.
    """
    if offset < 0:
        raise ValueError("scope offset must be non-negative")
    merged = _merged_scope_subjects(
        repository_id,
        scope,
        structural=structural,
        evidence=evidence,
        store=store,
        bounds=bounds,
    )
    page = merged[offset : offset + bounds.max_subjects]
    return tuple(page), len(merged), frontier_fingerprint(merged)


def _resolve_target_subjects(
    repository_id: str,
    target: m.EvidenceScope,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> tuple[m.Subject, ...]:
    """Enumerate current structural/evidence candidates in the exact scope.

    Exhaustive by design: ``initialize_target`` needs the whole boundary. A
    scoped read uses ``resolve_scope_frontier`` instead, which pages it.
    """
    if not target.paths and not target.evidence_refs:
        raise ValueError("exact target scope must not be empty")
    return _merged_scope_subjects(
        repository_id,
        target,
        structural=structural,
        evidence=evidence,
        store=store,
        bounds=bounds,
    )


def _subject_key(sid: m.SubjectId) -> tuple[str, str, str]:
    """Complete identity key: repository + kind + locator (§4.2)."""
    return (
        sid.repository_id,
        sid.subject_kind.value,
        sid.canonical_locator,
    )


def _make_not_found(bounds: m.QueryBounds) -> m.SubjectResolution:
    return m.SubjectResolution(
        candidates=(),
        ambiguity=m.ResolutionAmbiguity.NOT_FOUND,
        bound_info=m.BoundInfo(
            requested_max_results=bounds.max_subjects,
            requested_max_depth=0,
            returned_results=0,
            truncated=False,
            truncated_category=None,
            continuation_token=None,
        ),
    )


def _make_resolved(subject: m.Subject, bounds: m.QueryBounds) -> m.SubjectResolution:
    # Contextual candidates are reached through evidence linkage, not
    # an exact locator match: report the truthful non-exact basis.
    return m.SubjectResolution(
        candidates=(
            m.SubjectCandidate(
                subject=subject,
                structural_evidence=(),
                rank_basis=m.CandidateRankBasis.STRUCTURAL_PROXIMITY,
            ),
        ),
        ambiguity=m.ResolutionAmbiguity.RESOLVED,
        bound_info=m.BoundInfo(
            requested_max_results=bounds.max_subjects,
            requested_max_depth=0,
            returned_results=1,
            truncated=False,
            truncated_category=None,
            continuation_token=None,
        ),
    )


def _make_ambiguous(
    subjects: tuple[m.Subject, ...],
    bounds: m.QueryBounds,
    *,
    truncated: bool = False,
    truncated_category: str | None = None,
) -> m.SubjectResolution:
    ordered = sorted(
        subjects,
        key=lambda s: (
            s.subject_id.subject_kind.value,
            s.subject_id.canonical_locator,
        ),
    )
    return m.SubjectResolution(
        candidates=tuple(
            m.SubjectCandidate(
                subject=subject,
                structural_evidence=(),
                rank_basis=(m.CandidateRankBasis.STRUCTURAL_PROXIMITY),
            )
            for subject in ordered
        ),
        ambiguity=m.ResolutionAmbiguity.AMBIGUOUS,
        bound_info=m.BoundInfo(
            requested_max_results=bounds.max_subjects,
            requested_max_depth=0,
            returned_results=len(ordered),
            truncated=truncated,
            truncated_category=(truncated_category if truncated else None),
            continuation_token=None,
        ),
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
        parent = claim.value.parent
        parents.setdefault(_subject_key(parent), parent)
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

    Pure retrieval of established semantics: exact path inventory →
    reverse evidence deps → direct candidates (claims + MEMBER_OF) →
    CURRENT-membership chains → most-specific common ancestor.
    Never invents subjects, never remaps coverage, never persists.
    """
    _ = structural
    if selector.exact_subject_id is not None:
        return (
            _make_not_found(bounds),
            _make_not_found(bounds),
        )
    query = selector.name_or_locator
    if not query:
        return (
            _make_not_found(bounds),
            _make_not_found(bounds),
        )
    inventory = _bounded_path_inventory(
        repository_id,
        query,
        evidence=evidence,
        bounds=bounds,
    )
    if inventory is None:
        ambiguous = _make_ambiguous(
            (), bounds, truncated=True, truncated_category="inventory"
        )
        return (ambiguous, ambiguous)
    if not inventory:
        return (
            _make_not_found(bounds),
            _make_not_found(bounds),
        )
    evidence_ids = tuple(
        dict.fromkeys(item.evidence_ref.evidence_id.value for item in inventory)
    )
    claims, rels = _load_contextual_semantics(repository_id, evidence_ids, store=store)
    candidate_ids = _direct_candidate_ids(claims, rels)
    allowed: set[m.SubjectKind] | None = (
        set(selector.expected_kinds) if selector.expected_kinds else None
    )
    if allowed is not None:
        candidate_ids = tuple(
            sid for sid in candidate_ids if sid.subject_kind in allowed
        )
    if not candidate_ids:
        return (
            _make_not_found(bounds),
            _make_not_found(bounds),
        )
    if len(candidate_ids) > bounds.max_subjects:
        ambiguous = _make_ambiguous(
            (), bounds, truncated=True, truncated_category="context"
        )
        return (ambiguous, ambiguous)
    found = store.load_subjects(repository_id, candidate_ids)
    by_key = {_subject_key(s.subject_id): s for s in found}
    if any(_subject_key(sid) not in by_key for sid in candidate_ids):
        # A referenced candidate has no canonical Subject row (claim /
        # relationship endpoints need not have one). The candidate set
        # is untrustworthy: fail closed as unproven, never collapse to
        # the surviving subset.
        ambiguous = _make_ambiguous(
            (), bounds, truncated=True, truncated_category="context"
        )
        return (ambiguous, ambiguous)
    known: list[m.Subject] = [by_key[_subject_key(sid)] for sid in candidate_ids]
    if not known:
        return (
            _make_not_found(bounds),
            _make_not_found(bounds),
        )
    if len(known) == 1:
        local = known[0]
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
                _make_ambiguous(
                    (),
                    bounds,
                    truncated=True,
                    truncated_category="context",
                ),
            )
        if not parents:
            return (orientation, _make_resolved(local, bounds))
        if allowed is not None:
            # Promotion must preserve the selector's kind constraint:
            # a parent outside expected_kinds can never become the
            # trace subject. Narrow to allowed parents first; with none
            # allowed the local candidate stands.
            parents = tuple(p for p in parents if p.subject_kind in allowed)
            if not parents:
                return (orientation, _make_resolved(local, bounds))
        if len(parents) == 1:
            loaded = store.load_subjects(repository_id, parents)
            if not loaded:
                return (
                    orientation,
                    _make_ambiguous(
                        (),
                        bounds,
                        truncated=True,
                        truncated_category="context",
                    ),
                )
            return (orientation, _make_resolved(loaded[0], bounds))
        if len(parents) > bounds.max_subjects or len(parents) > bounds.max_results:
            return (
                orientation,
                _make_ambiguous(
                    (),
                    bounds,
                    truncated=True,
                    truncated_category="context",
                ),
            )
        loaded = store.load_subjects(repository_id, parents)
        return (orientation, _make_ambiguous(loaded, bounds))
    chains: dict[tuple[str, str, str], list[m.SubjectId]] = {}
    for subject in known:
        sid = subject.subject_id
        chain: list[m.SubjectId] = [sid]
        seen: set[tuple[str, str, str]] = {_subject_key(sid)}
        current = sid
        failed: str | None = None
        while True:
            if len(chain) - 1 >= bounds.max_depth:
                parents = _current_parents(
                    repository_id,
                    current,
                    evidence=evidence,
                    store=store,
                    bounds=bounds,
                )
                if parents is None or parents:
                    failed = "bound"
                    break
                break
            parents = _current_parents(
                repository_id,
                current,
                evidence=evidence,
                store=store,
                bounds=bounds,
            )
            if parents is None:
                failed = "bound"
                break
            if not parents:
                break
            if len(parents) > 1:
                failed = "multi"
                break
            parent = parents[0]
            key = _subject_key(parent)
            if key in seen:
                failed = "bound"
                break
            if len(chain) + 1 > bounds.max_subjects:
                failed = "bound"
                break
            chain.append(parent)
            seen.add(key)
            current = parent
        if failed == "bound":
            ambiguous = _make_ambiguous(
                tuple(known),
                bounds,
                truncated=True,
                truncated_category="context",
            )
            return (ambiguous, ambiguous)
        if failed is not None:
            ambiguous = _make_ambiguous(tuple(known), bounds)
            return (ambiguous, ambiguous)
        chains[_subject_key(sid)] = chain
    distinct: set[tuple[str, str, str]] = set()
    for chain in chains.values():
        distinct.update(_subject_key(sid) for sid in chain)
    if len(distinct) > bounds.max_subjects or len(distinct) > bounds.max_results:
        return (
            _make_ambiguous(
                tuple(known),
                bounds,
                truncated=True,
                truncated_category="context",
            ),
            _make_ambiguous(
                tuple(known),
                bounds,
                truncated=True,
                truncated_category="context",
            ),
        )
    all_ids: list[m.SubjectId] = []
    for chain in chains.values():
        all_ids.extend(chain)
    loaded_all = store.load_subjects(
        repository_id,
        tuple(
            dict.fromkeys(
                all_ids,  # type: ignore[arg-type]
            )
        ),
    )
    # NOTE: dict.fromkeys over SubjectId preserves first occurrence;
    # reload by key below for chain membership checks.
    loaded_by_key = {_subject_key(s.subject_id): s for s in loaded_all}
    for chain in chains.values():
        for sid in chain:
            if _subject_key(sid) not in loaded_by_key:
                ambiguous = _make_ambiguous(
                    tuple(known),
                    bounds,
                    truncated=True,
                    truncated_category="context",
                )
                return (ambiguous, ambiguous)
    first_chain = next(iter(chains.values()))
    chain_sets = [{_subject_key(sid) for sid in chain} for chain in chains.values()]
    common: m.SubjectId | None = None
    for sid in first_chain:
        key = _subject_key(sid)
        if all(key in other for other in chain_sets):
            common = sid
            break
    if common is None:
        return (
            _make_ambiguous(tuple(known), bounds),
            _make_ambiguous(tuple(known), bounds),
        )
    if allowed is not None and common.subject_kind not in allowed:
        # The common ancestor is outside the selector's kind
        # constraint: it may not resolve. Remain ambiguous over the
        # allowed direct candidates instead.
        return (
            _make_ambiguous(tuple(known), bounds),
            _make_ambiguous(tuple(known), bounds),
        )
    common_subject = loaded_by_key[_subject_key(common)]
    resolved = _make_resolved(common_subject, bounds)
    return (resolved, resolved)
