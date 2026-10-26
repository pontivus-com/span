"""One submitted unit: validate, derive, and persist."""

from __future__ import annotations

import dataclasses as _dataclasses

from span.core import model as m
from span.core import validation as _validation
from span.ports.evidence import EvidenceSource
from span.ports.store import SemanticStore


from span.service.interpretation.stages.checks import (
    _admit_and_validate,
    _validate_bound_question,
    _validate_premises_and_conflicts,
    _validate_withdrawals,
)

from span.service.interpretation.admission import _assign_candidate_keys


from span.service.interpretation.task import (
    InterpretationTask,
)


def _prepare_unit(
    task: InterpretationTask,
    result: m.SemanticInterpretationResult,
    deps: _UnitDeps,
) -> _PreparedUnit:
    """Validate one submission end to end before anything is derived or written.

    Admission, premise currency, withdrawals, and the bound-question command
    all fail here, so the derive stage only ever sees an accepted unit.
    """
    store = deps.store
    evidence = deps.evidence
    state = deps.state
    extra_known_subjects = deps.extra_known_subjects
    retire_scope = deps.retire_scope
    correction_question = deps.correction_question
    result = _assign_candidate_keys(result)
    admitted = _admit_and_validate(
        task,
        result,
        store=store,
        evidence=evidence,
        state=state,
        extra_known_subjects=extra_known_subjects,
    )
    ctx = admitted.ctx
    result = admitted.result
    new_subjects = admitted.new_subjects
    new_subject_ids = admitted.new_subject_ids
    claims = admitted.claims
    relationships = admitted.relationships
    verification_records = admitted.verification_records
    failures = admitted.failures
    recorded = _validate_premises_and_conflicts(
        task,
        result,
        store=store,
        ctx=ctx,
        claims=claims,
        relationships=relationships,
        failures=failures,
    )
    if failures:
        raise _validation.InterpretationUnitRejected(tuple(failures))
    # ctx fingerprints include addendum-A/F2 admitted established
    # evidence alongside task fingerprints.
    fingerprints = dict(ctx.evidence_fingerprints)
    subjects = tuple(task.request.subjects) + tuple(new_subjects)
    known_ids = {c.claim_id.value for c in claims} | {
        r.relationship_id.value for r in relationships
    }
    validated_withdrawals, retires_claims, retires_relationships = (
        _validate_withdrawals(
            task,
            result,
            store=store,
            ctx=ctx,
            known_ids=known_ids,
            retire_scope=retire_scope,
            correction_question=correction_question,
        )
    )
    bound_question, bound_is_fallback_scaffolding = _validate_bound_question(
        task,
        result,
        store=store,
        correction_question=correction_question,
    )
    return _PreparedUnit(
        ctx=ctx,
        result=result,
        new_subject_ids=new_subject_ids,
        claims=claims,
        relationships=relationships,
        verification_records=verification_records,
        recorded=recorded,
        fingerprints=fingerprints,
        subjects=subjects,
        validated_withdrawals=validated_withdrawals,
        retires_claims=retires_claims,
        retires_relationships=retires_relationships,
        bound_question=bound_question,
        bound_is_fallback_scaffolding=bound_is_fallback_scaffolding,
    )


@_dataclasses.dataclass
class _PreparedUnit:
    """Everything the derive and persist stages need after validation."""

    ctx: _validation.ValidationContext
    result: m.SemanticInterpretationResult
    new_subject_ids: list[m.SubjectId]
    claims: list[m.SemanticClaim]
    relationships: list[m.SemanticRelationship]
    verification_records: tuple[m.ExecutedVerification, ...]
    recorded: list[m.RecordedConflict]
    fingerprints: dict[str, str]
    subjects: tuple[m.Subject, ...]
    validated_withdrawals: list[m.CandidateSemanticWithdrawal]
    retires_claims: list[m.ClaimRef]
    retires_relationships: list[m.RelationshipRef]
    bound_question: m.SemanticQuestionScope | None
    bound_is_fallback_scaffolding: bool


@_dataclasses.dataclass
class _UnitDeps:
    """The stores and scopes one submission is validated against."""

    store: SemanticStore
    evidence: EvidenceSource
    state: m.RepositoryState
    extra_known_subjects: tuple[m.SubjectId, ...]
    retire_scope: tuple[m.SubjectId, ...]
    correction_question: m.SemanticQuestionScope | None
