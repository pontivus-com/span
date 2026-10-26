"""Service currency orchestration: query, premise walk, and projection."""

from __future__ import annotations

from span.service.freshness.classify import (  # noqa: F401
    _classify_coverage_updates,
    _classify_current,
    _evaluate_current,
    _latest_coverages,
    _refresh_view,
    coverage_check,
    preflight,
    with_freshness,
)
from span.service.freshness.premise import _premise_preflight  # noqa: F401

__all__ = [
    "preflight",
    "_premise_preflight",
    "_classify_current",
    "_classify_coverage_updates",
    "_evaluate_current",
    "coverage_check",
    "_latest_coverages",
    "_refresh_view",
    "with_freshness",
]
