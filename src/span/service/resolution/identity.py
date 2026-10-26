"""Span service subject resolution + store-read plumbing (v0.6 §14 Amendment A-01).

Identity resolution over the structural source (observations only —
ambiguity is never overridden, names alone are never identity, §4.2)
plus subject-state and coverage-enumeration reads. Verbatim from
``span.service_operations``; only the module path changed.
"""

from __future__ import annotations

from span.core import model as m


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
