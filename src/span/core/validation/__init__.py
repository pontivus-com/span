"""Public validation surface (re-exported)."""

from __future__ import annotations

from span.core.validation.context import (  # noqa: F401
    ValidationContext,
    CandidateValidation,
    InterpretationUnitRejected,
    FREE_TEXT_FIELDS,
    deterministic_claim_id,
    deterministic_relationship_id,
)
from span.core.validation.rules import (  # noqa: F401
    validate_candidate_claim,
    validate_candidate_relationship,
    validate_candidate_subject,
    validate_candidate_conflict,
    validate_question_coverage,
    validate_candidate_withdrawal,
    validate_target_questions,
    materialize_claim,
    materialize_relationship,
    find_conflicts,
    validate_verification_records,
)

__all__ = [
    "ValidationContext",
    "CandidateValidation",
    "InterpretationUnitRejected",
    "FREE_TEXT_FIELDS",
    "validate_candidate_claim",
    "validate_candidate_relationship",
    "validate_candidate_subject",
    "validate_candidate_conflict",
    "validate_question_coverage",
    "validate_candidate_withdrawal",
    "validate_target_questions",
    "materialize_claim",
    "materialize_relationship",
    "find_conflicts",
    "deterministic_claim_id",
    "deterministic_relationship_id",
]
