"""Span answer assembly and service-cursor mechanics (plan §11)."""

from __future__ import annotations

from span.service.answers.cursor import (  # noqa: F401
    _answer_id,
    _bounds_key,
    _query_digest,
    _validate_service_token,
    _next_service_offsets,
    _next_service_token,
)

from span.service.answers.assembly import (  # noqa: F401
    ResponseBudget,
    _leaf_count,
    AnswerAssembler,
    ANSWER_ASSEMBLER,
    _recorded_conflicts,
    _conflicts_for,
    _select_answer_items,
    _freshness_items_for,
    currency_literal,
    verification_currencies_for,
    coverage_counts_for,
    _distribution_sentence,
    state_explanation_for,
)

__all__ = [
    "_answer_id",
    "_bounds_key",
    "_query_digest",
    "_validate_service_token",
    "_next_service_offsets",
    "_next_service_token",
    "ResponseBudget",
    "_leaf_count",
    "AnswerAssembler",
    "ANSWER_ASSEMBLER",
    "_recorded_conflicts",
    "_conflicts_for",
    "_select_answer_items",
    "_freshness_items_for",
    "currency_literal",
    "verification_currencies_for",
    "coverage_counts_for",
    "_distribution_sentence",
    "state_explanation_for",
]
