"""Span service status operation (plan §11.8; v0.6 §14 Amendment A-01).

Currency and verification over stored semantics, with hook fast
path and resume. Verbatim from ``span.service_operations``; only the
module path changed.
"""

from __future__ import annotations


from span.core import model as m


def _status_state_explanation(
    base: tuple[str, ...],
    content: m.StatusContent,
    requirements: tuple[m.ResolutionRequirement, ...],
) -> tuple[str, ...]:
    """Add status-only readiness, coverage, target, and authority qualifiers."""
    lines = list(base)
    if content.store_readiness is m.StoreReadiness.READY:
        lines.insert(
            0,
            "repository store_readiness: READY means the Span semantic store is "
            "available; semantic coverage and currency are reported separately",
        )
    report = content.coverage_report
    if isinstance(report, m.RepositoryCoverageReport):
        page = report.page
        totals = report.repository
        lines.append(
            "semantic coverage (page scope): "
            f"{page.current_subject_count} current, "
            f"{page.incomplete_subject_count} incomplete, "
            f"{page.stale_subject_count} stale, "
            f"{page.unverifiable_subject_count} unverifiable, "
            f"{page.unassessed_subject_count} unassessed subjects; "
            f"{totals.pending_question_count} persisted pending and "
            f"{totals.open_question_count} persisted open questions "
            "(repository counts)"
        )
    elif isinstance(report, m.ScopedCoverageReport):
        page = report.page
        lines.append(
            "semantic coverage (page scope): "
            f"{page.current_subject_count} current, "
            f"{page.incomplete_subject_count} incomplete, "
            f"{page.stale_subject_count} stale, "
            f"{page.unverifiable_subject_count} unverifiable, "
            f"{page.unassessed_subject_count} unassessed subjects; "
            f"{report.scope.persisted_subject_count} persisted subjects in scope"
        )
    if content.target_disposition is not None:
        lines.append("target disposition: " + content.target_disposition.value)
    if any(req.kind is m.ResolutionKind.MISSING_AUTHORITY for req in requirements):
        lines.append("governing authority remains unresolved for this result")
    return tuple(lines)
