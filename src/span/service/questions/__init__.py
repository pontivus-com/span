"""Span question identity, projection, and frontier mechanics (plan §11)."""

from __future__ import annotations

from span.service.questions.projection import (  # noqa: F401
    filter_views_by_scope,
    effective_question_view,
    question_coverage_check,
)

from span.service.questions.slices import (  # noqa: F401
    _question_identity_key,
    effective_trace_slice,
    effective_impact_slice,
    derive_service_question,
)

from span.service.questions.frontier import (  # noqa: F401
    _question_class_for_intent,
    _question_local_missing,
    _stale_question_scopes,
    _question_views_for_scope,
    _paged_question_views,
    _missing_subjects,
)

__all__ = [
    "filter_views_by_scope",
    "effective_question_view",
    "question_coverage_check",
    "_question_identity_key",
    "effective_trace_slice",
    "effective_impact_slice",
    "derive_service_question",
    "_question_class_for_intent",
    "_question_local_missing",
    "_stale_question_scopes",
    "_question_views_for_scope",
    "_paged_question_views",
    "_missing_subjects",
]
