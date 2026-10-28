"""Span service status operation (plan §11.8; v0.6 §14 Amendment A-01).

Currency and verification over stored semantics, with hook fast
path and resume.
"""

from __future__ import annotations

from span.service.operations.status.requirements import (  # noqa: F401
    _pending_exchange_requirements,
    _live_question_records,
    _live_subject_requirements,
    _repository_live_requirements,
    _project_pending_requirements,
    _is_generic_live_action,
    _project_live_requirements,
    _repository_pending_requirements,
    _target_live_requirements,
)

from span.service.operations.status.coverage import (  # noqa: F401
    _repository_coverage_entry,
    _coverage_entries_for_subjects,
    _repository_report,
    _scoped_report,
    _target_burden_aggregates,
    _derived_verification_status,
)

from span.service.operations.status.explanation import (  # noqa: F401
    _status_state_explanation,
)

from span.service.operations.status.repository import (  # noqa: F401
    _compose_repository_status_answer,
    _repository_status_page,
)

from span.service.operations.status.target import (  # noqa: F401
    _campaign_lifespan,
    _target_status_answer,
)

from span.service.operations.status.hooks import (  # noqa: F401
    _hook_fast,
)

from span.service.operations.status.compose import (  # noqa: F401
    _compose_status_answer,
)

from span.service.operations.status.scoped import (  # noqa: F401
    _scope_cursor,
    _resolve_status_subjects,
    _unresolved_status_answer,
    status,
    _page_cut_unresumable_items,
)

__all__ = [
    "_pending_exchange_requirements",
    "_live_question_records",
    "_live_subject_requirements",
    "_repository_live_requirements",
    "_project_pending_requirements",
    "_is_generic_live_action",
    "_project_live_requirements",
    "_repository_pending_requirements",
    "_target_live_requirements",
    "_repository_coverage_entry",
    "_coverage_entries_for_subjects",
    "_repository_report",
    "_scoped_report",
    "_target_burden_aggregates",
    "_derived_verification_status",
    "_status_state_explanation",
    "_compose_repository_status_answer",
    "_repository_status_page",
    "_campaign_lifespan",
    "_target_status_answer",
    "_hook_fast",
    "_compose_status_answer",
    "_scope_cursor",
    "_resolve_status_subjects",
    "_unresolved_status_answer",
    "status",
    "_page_cut_unresumable_items",
    "_page_cut_unresumable_items",
]
