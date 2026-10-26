"""Span service trace operation (plan §11.6; v0.6 §14 Amendment A-01).

Bounded frontier expansion and trace answers.
"""

from __future__ import annotations

from span.service.operations.trace.drive import (  # noqa: F401
    _trace_endpoints,
    _TraceQuestion,
    _trace_question,
    _has_recorded_trace_coverage,
    _trace_frontier_suspension,
    _TraceWalk,
    _trace_walk,
    _trace_drive,
)

from span.service.operations.trace.answer import (  # noqa: F401
    _trace_live_view,
    _trace_context_refs,
    _trace_requirements,
    _compose_trace_answer,
)

from span.service.operations.trace.operation import (  # noqa: F401
    trace,
    _resume_trace,
)

__all__ = [
    "_trace_drive",
    "_compose_trace_answer",
    "_resume_trace",
    "trace",
]
