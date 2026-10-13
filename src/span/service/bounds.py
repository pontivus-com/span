"""Span service bounds policy (plan §5.1, v0.6 §14 Amendment A-01).

Service-level operational configuration and strict typed ingress
helpers for operation bounds. Verbatim from the former
``span.service`` module; only the module path changed.
"""

from span.core.model import QueryBounds, ServiceBoundsPolicy

__all__ = [
    "DEFAULT_SERVICE_BOUNDS_POLICY",
    "BoundsRejectedError",
    "resolve_bounds",
]


def _bounds(
    max_results: int,
    max_depth: int,
    max_subjects: int,
    max_evidence_units: int,
    max_evidence_bytes: int,
    max_candidate_claims: int,
    max_candidate_relationships: int,
) -> QueryBounds:
    return QueryBounds(
        max_results=max_results,
        max_depth=max_depth,
        max_subjects=max_subjects,
        max_evidence_units=max_evidence_units,
        max_evidence_bytes=max_evidence_bytes,
        max_candidate_claims=max_candidate_claims,
        max_candidate_relationships=max_candidate_relationships,
    )


#: Initial required policy (plan §5.1). Operational bounds, not semantic
#: thresholds: changeable only as a configuration/versioned product
#: decision, never per-call model judgment.
DEFAULT_SERVICE_BOUNDS_POLICY = ServiceBoundsPolicy(
    default_query_bounds=_bounds(
        max_results=50,
        max_depth=2,
        max_subjects=8,
        max_evidence_units=24,
        max_evidence_bytes=96_000,
        max_candidate_claims=64,
        max_candidate_relationships=64,
    ),
    maximum_query_bounds=_bounds(
        max_results=250,
        max_depth=6,
        max_subjects=32,
        max_evidence_units=96,
        max_evidence_bytes=384_000,
        max_candidate_claims=256,
        max_candidate_relationships=256,
    ),
    hook_fast_bounds=_bounds(
        max_results=25,
        max_depth=0,
        max_subjects=8,
        max_evidence_units=16,
        max_evidence_bytes=64_000,
        max_candidate_claims=1,
        max_candidate_relationships=1,
    ),
)


class BoundsRejectedError(ValueError):
    """User-supplied bounds above the maximum (plan §5.1: reject, never
    silently widen or clamp)."""


_BOUND_FIELDS: tuple[str, ...] = (
    "max_results",
    "max_depth",
    "max_subjects",
    "max_evidence_units",
    "max_evidence_bytes",
    "max_candidate_claims",
    "max_candidate_relationships",
)


def resolve_bounds(
    requested: QueryBounds | None,
    *,
    hook: bool,
    policy: ServiceBoundsPolicy = DEFAULT_SERVICE_BOUNDS_POLICY,
) -> QueryBounds:
    """Apply the §5.1 ingress rules for operation bounds.

    - omitted bounds use ``default_query_bounds``;
    - lifecycle hooks always use ``hook_fast_bounds``;
    - user-supplied bounds above ``maximum_query_bounds`` are rejected
      (never silently widened/clamped).
    """
    if hook:
        return policy.hook_fast_bounds
    if requested is None:
        return policy.default_query_bounds
    maximum = policy.maximum_query_bounds
    for field_name in _BOUND_FIELDS:
        if getattr(requested, field_name) > getattr(maximum, field_name):
            raise BoundsRejectedError(
                f"{field_name}={getattr(requested, field_name)} exceeds "
                f"maximum {getattr(maximum, field_name)}; "
                f"default when omitted is "
                f"{getattr(policy.default_query_bounds, field_name)}"
            )
    return requested
