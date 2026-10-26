"""Span subject resolution, scope frontier, and store-read plumbing."""

from __future__ import annotations

from span.service.resolution.identity import (  # noqa: F401
    _subject_key,
    _make_not_found,
    _make_resolved,
    _make_ambiguous,
)

from span.service.resolution.loading import (  # noqa: F401
    _load_all_coverages_or_defer,
    _load_subject_state,
)

from span.service.resolution.selector import (  # noqa: F401
    _fallback_target_kind,
    _exact_candidates_resolution,
    _resolve_exact_subject,
    _resolve_query_subject,
)

from span.service.resolution.scope import (  # noqa: F401
    _inventory_subjects,
    _persisted_subjects_in_scope,
    _merged_scope_subjects,
    frontier_fingerprint,
    resolve_scope_frontier,
    _resolve_target_subjects,
    _resolve_scope_subjects,
)

from span.service.resolution.contextual import (  # noqa: F401
    _has_established_semantic_state,
    _bounded_path_inventory,
    _load_contextual_semantics,
    _direct_candidate_ids,
    _current_parents,
    _context_pair,
    _context_candidate_ids,
    _context_known_subjects,
    _single_context_resolution,
    _ancestor_chain,
    _common_ancestor_resolution,
    _resolve_contextual_subjects,
)

__all__ = [
    "_subject_key",
    "_make_not_found",
    "_make_resolved",
    "_make_ambiguous",
    "_load_all_coverages_or_defer",
    "_load_subject_state",
    "_fallback_target_kind",
    "_exact_candidates_resolution",
    "_resolve_exact_subject",
    "_resolve_query_subject",
    "_inventory_subjects",
    "_persisted_subjects_in_scope",
    "_merged_scope_subjects",
    "frontier_fingerprint",
    "resolve_scope_frontier",
    "_resolve_target_subjects",
    "_resolve_scope_subjects",
    "_has_established_semantic_state",
    "_bounded_path_inventory",
    "_load_contextual_semantics",
    "_direct_candidate_ids",
    "_current_parents",
    "_context_pair",
    "_context_candidate_ids",
    "_context_known_subjects",
    "_single_context_resolution",
    "_ancestor_chain",
    "_common_ancestor_resolution",
    "_resolve_contextual_subjects",
]
