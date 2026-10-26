"""Span service impact operation (plan §11.5; v0.6 §14 Amendment A-01).

Change-condition derivation and impact answers.
"""

from __future__ import annotations

from span.service.operations.impact.conditions import (  # noqa: F401
    _derive_change_conditions,
)

from span.service.operations.impact.frontier import (  # noqa: F401
    _ImpactQuestion,
    _impact_question,
    _has_recorded_impact_coverage,
    _impact_suspension,
    _impact_target_gate,
    _ImpactFrontier,
    _impact_frontier,
)

from span.service.operations.impact.answer import (  # noqa: F401
    _impact_items,
    _ImpactSelection,
    _select_impact,
    _compose_impact_answer,
)

from span.service.operations.impact.operation import (  # noqa: F401
    impact,
)

__all__ = [
    "_derive_change_conditions",
    "_compose_impact_answer",
    "impact",
]
