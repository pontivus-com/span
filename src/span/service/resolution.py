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
from span.shell import paging as _paging

__all__ = [
    "_load_all_coverages_or_defer",
    "_load_subject_state",
    "_resolve_exact_subject",
    "_resolve_query_subject",
    "_resolve_scope_subjects",
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
        total = store.count_question_coverages(
            repository_id, scope_root, subject_ids
        )
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
        return store.load_all_question_coverages(
            repository_id, scope_root, subject_ids
        )
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
    (``pg:<claims_skip>:<rels_skip>:<questions_skip>``); each load windows
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
    """Query-time subject resolution (addendum A, F1).

    Structural first; on NOT_FOUND with an exact identity, fall back
    to the stored subject record (registered semantic-only subjects
    live in the store, never in the structural source). Ambiguity is
    never overridden and name-only queries never reach the store
    (§4.2: names alone are never identity).
    """
    resolution = structural.resolve_subject(repository_id, target, bounds)
    if resolution.ambiguity is m.ResolutionAmbiguity.RESOLVED:
        return resolution
    if (
        resolution.ambiguity is m.ResolutionAmbiguity.NOT_FOUND
        and target.exact_subject_id is not None
    ):
        found = store.load_subjects(
            repository_id, (target.exact_subject_id,)
        )
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
                    repository_id, target, structural=structural,
                    evidence=evidence, store=store, bounds=bounds,
                ),
                m.ResolutionAmbiguity.RESOLVED,
            )
        subjects: list[m.Subject] = []
        paths = list(target.paths) + [
            ref.locator for ref in target.evidence_refs
        ]
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
        repository_id, target, structural=structural, store=store,
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

    This is deterministic boundary discovery only. It must not be read as
    one semantic subject per file or as proof of target understanding.
    """
    if not target.paths and not target.evidence_refs:
        raise ValueError("exact target scope must not be empty")
    items: list[m.EvidenceInventoryItem] = []
    page_token: str | None = None
    while True:
        page = evidence.inventory_evidence(
            repository_id, target, bounds, page_token
        )
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
                exact_subject_id=None, name_or_locator=locator,
                expected_kinds=(), retrieval_scope_hint=None,
            ),
            bounds,
        )
        subject = None
        if (
            resolution.ambiguity is m.ResolutionAmbiguity.RESOLVED
            and len(resolution.candidates) == 1
            and resolution.candidates[0].subject.subject_id.canonical_locator
            == locator
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
    target_paths = tuple(
        dict.fromkeys(
            (*target.paths, *(ref.locator for ref in target.evidence_refs))
        )
    )
    subject_token: str | None = None
    while True:
        page = store.load_repository_subjects(
            repository_id, bounds, offset=(
                int(subject_token[3:]) if subject_token else 0
            ),
        )
        for subject in page.items:
            locator = subject.subject_id.canonical_locator
            if any(
                locator == path or locator.startswith(path.rstrip("/") + "/")
                or locator.startswith(path.rstrip("/") + "#")
                for path in target_paths
            ):
                found[(subject.subject_id.subject_kind, locator)] = subject
        subject_token = page.bound_info.continuation_token
        if subject_token is None:
            break
    return tuple(
        found[key] for key in sorted(found, key=lambda pair: pair[1])
    )
