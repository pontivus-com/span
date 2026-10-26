"""Span service subject resolution + store-read plumbing (v0.6 §14 Amendment A-01).

Identity resolution over the structural source (observations only —
ambiguity is never overridden, names alone are never identity, §4.2)
plus subject-state and coverage-enumeration reads. Verbatim from
``span.service_operations``; only the module path changed.
"""

from __future__ import annotations

from span.core import model as m
from span.ports.store import SemanticStore
from span.ports.structural import StructuralSource


from span.service.resolution.identity import (
    _subject_key,
)


def _fallback_target_kind(ref: m.EvidenceRef) -> m.SubjectKind:
    if ref.source_kind is m.EvidenceSourceKind.DOCUMENTATION:
        return m.SubjectKind.DOCUMENT
    if ref.source_kind is m.EvidenceSourceKind.TEST_VERIFICATION:
        return m.SubjectKind.TEST_OR_GATE
    if ref.source_kind is m.EvidenceSourceKind.CONFIGURATION:
        return m.SubjectKind.CONFIGURATION
    return m.SubjectKind.COMPONENT


def _exact_candidates_resolution(
    subjects: tuple[m.Subject, ...],
    *,
    bounds: m.QueryBounds,
    truncated: bool,
) -> m.SubjectResolution:
    """Assemble the exact-identity resolution for one candidate set.

    Exact stored locators defeat non-exact structural names; only multiple
    exact identities — or a truncated set — may remain ambiguous.
    """
    ordered = sorted(
        subjects,
        key=lambda subject: (
            subject.subject_id.subject_kind.value,
            subject.subject_id.canonical_locator,
        ),
    )
    kept = tuple(ordered[: bounds.max_subjects])
    truncated = truncated or len(ordered) > bounds.max_subjects
    candidates = tuple(
        m.SubjectCandidate(
            subject=subject,
            structural_evidence=(),
            rank_basis=m.CandidateRankBasis.EXACT_LOCATOR,
        )
        for subject in kept
    )
    return m.SubjectResolution(
        candidates=candidates,
        ambiguity=(
            m.ResolutionAmbiguity.RESOLVED
            if len(kept) == 1 and not truncated
            else m.ResolutionAmbiguity.AMBIGUOUS
        ),
        bound_info=m.BoundInfo(
            requested_max_results=bounds.max_subjects,
            requested_max_depth=0,
            returned_results=len(candidates),
            truncated=truncated,
            truncated_category="candidates" if truncated else None,
            continuation_token=None,
        ),
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
    """Query-time subject resolution ([design note A](docs/design-references.md#a) F1 as amended by I S1).

    Explicit ``exact_subject_id`` keeps the existing exact-ID path.
    Otherwise structural resolution and exact stored-locator matches for
    ``name_or_locator`` are merged by complete ``SubjectId`` with the §5.1
    exact-precedence rule: an exact stored locator defeats non-exact structural
    name candidates; only multiple exact identities may remain ambiguous.
    Stored lookup is exact string equality only, never normalization.
    Truncated sets never resolve. Structural-provider failure propagates; no
    stored fallback on that path. ``expected_kinds`` filtering is provider-owned
    on both paths.
    """
    resolution = structural.resolve_subject(repository_id, target, bounds)
    if target.exact_subject_id is not None:
        if resolution.ambiguity is m.ResolutionAmbiguity.RESOLVED:
            return resolution
        if resolution.ambiguity is m.ResolutionAmbiguity.NOT_FOUND:
            found = store.load_subjects(repository_id, (target.exact_subject_id,))
            if found:
                return _exact_candidates_resolution(
                    (found[0],), bounds=bounds, truncated=False
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
    stored_by_id = {
        _subject_key(subject.subject_id): subject for subject in stored_page.items
    }
    structural_exact = {
        _subject_key(candidate.subject.subject_id): candidate.subject
        for candidate in resolution.candidates
        if candidate.rank_basis is m.CandidateRankBasis.EXACT_LOCATOR
    }
    if not structural_exact:
        # Only non-exact structural candidates or NOT_FOUND: exact stored
        # identity wins; non-exact names never defeat it.
        return _exact_candidates_resolution(
            tuple(stored_by_id.values()),
            bounds=bounds,
            truncated=stored_page.bound_info.truncated,
        )
    # Both sides have exact identities: merge by complete SubjectId.
    merged: dict[tuple[str, str, str], m.Subject] = dict(structural_exact)
    for key, subject in stored_by_id.items():
        merged.setdefault(key, subject)
    return _exact_candidates_resolution(
        tuple(merged.values()),
        bounds=bounds,
        truncated=(stored_page.bound_info.truncated or resolution.bound_info.truncated),
    )
