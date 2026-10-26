"""Span service initialize_target operation (plan §11.3; v0.6 §14 Amendment A-01).

Deterministic target admission and the campaign question frontier.
"""

from __future__ import annotations

from span.service.operations.initialize_target.admission import (  # noqa: F401
    target_subjects,
    _scope_root_locator,
    _scope_area_subject,
    _deterministic_accounting,
    _TargetReconciliation,
    _reconcile_target_association,
    _write_target_reconciliation,
    _ensure_target_association,
)

from span.service.operations.initialize_target.operation import (  # noqa: F401
    _target_question_needs_task,
    _target_question_pending,
    _baseline_candidates_pending,
    _next_target_pending,
    initialize_target,
)

__all__ = [
    "initialize_target",
    "_next_target_pending",
    "target_subjects",
]
