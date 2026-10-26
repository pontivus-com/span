"""Span service explain operation (plan §11.4; v0.6 §14 Amendment A-01).

Bounded semantic explanation with baseline establishment.
"""

from __future__ import annotations

from span.service.operations.explain.answer import (  # noqa: F401
    _baseline_answer,
    _compose_explain_answer,
)

from span.service.operations.explain.operation import (  # noqa: F401
    _explain_resolution,
    _unresolved_explain_answer,
    _selected_explain_scope,
    _explain_baseline,
    _explain_selected,
    _suspend_missing_explain_question,
    explain,
)

__all__ = [
    "_compose_explain_answer",
    "explain",
]
