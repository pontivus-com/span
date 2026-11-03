"""Server-owned operational bounds (FD-54, technical design §13).

These are finite service limits, not semantic thresholds and not caller
choices. The composition boundary applies them; no public request carries a
response budget or a traversal bound.
"""

from span.core.model import QueryBounds, ServiceBoundsPolicy

__all__ = ["DEFAULT_SERVICE_BOUNDS_POLICY"]


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
    # O-3: largest wire result observed delivered inline on the smaller of the
    # two supported hosts (OpenCode); Codex inlined 62,589 bytes. A per-host
    # install may raise it up to that host's measured value.
    max_response_bytes=51_133,
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
