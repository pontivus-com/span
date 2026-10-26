"""One submitted unit: validate, derive, and persist."""

from __future__ import annotations

import dataclasses as _dataclasses

from span.core import model as m
from span.core import validation as _validation


from span.service.interpretation.coverage import (
    _decision_coverage,
    _derive_question_evidence,
    _ordered_result_refs,
)

from span.service.interpretation.task import (
    _member_diagnostics,
)


@_dataclasses.dataclass
class _FinalizeContext:
    """The derived support one coverage may bind."""

    canonical_refs: dict[str, m.EvidenceRef]
    fingerprints: dict[str, str]
    new_result_refs: tuple[m.ClaimRef | m.RelationshipRef, ...]
    material_evidence: tuple[m.EvidenceRef, ...]
    withdrawn_ids: frozenset[str]


def _finalize_coverage(
    submitted: m.InterpretationCoverage,
    *,
    prior: m.InterpretationCoverage | None,
    owns_material: bool,
    context: _FinalizeContext,
) -> m.InterpretationCoverage:
    """Derive result refs, question evidence, and completion for one coverage.

    ``ANSWERED`` binds the new material and completes; ``OPEN`` and
    ``PENDING`` keep prior refs and add only the material this unit owns;
    ``NOT_APPLICABLE`` never owns result refs.
    """
    prior_refs = () if prior is None else prior.result_refs
    prior_evidence = () if prior is None else prior.question_evidence
    decision = m.SemanticQuestionDecision(
        disposition=submitted.disposition,
        evidence_scope=submitted.evidence_scope,
        resolution_requirements=submitted.resolution_requirements,
        disposition_basis=submitted.disposition_basis,
    )
    disposition = submitted.disposition
    if disposition is m.SemanticQuestionDisposition.ANSWERED:
        result_refs = context.new_result_refs
        question_evidence = _derive_question_evidence(
            decision,
            canonical_refs=context.canonical_refs,
            fingerprints=context.fingerprints,
            material_evidence=(context.material_evidence if owns_material else ()),
        )
    elif disposition is m.SemanticQuestionDisposition.OPEN:
        result_refs = _ordered_result_refs(
            prior_refs,
            context.new_result_refs if owns_material else (),
            context.withdrawn_ids,
        )
        question_evidence = _derive_question_evidence(
            decision,
            canonical_refs=context.canonical_refs,
            fingerprints=context.fingerprints,
            material_evidence=(context.material_evidence if owns_material else ()),
            prior_evidence=prior_evidence,
        )
    elif disposition is m.SemanticQuestionDisposition.PENDING:
        result_refs = _ordered_result_refs(
            prior_refs,
            (),
            context.withdrawn_ids,
        )
        question_evidence = _derive_question_evidence(
            decision,
            canonical_refs=context.canonical_refs,
            fingerprints=context.fingerprints,
            prior_evidence=prior_evidence,
        )
    else:  # NOT_APPLICABLE never owns semantic result refs.
        result_refs = ()
        question_evidence = _derive_question_evidence(
            decision,
            canonical_refs=context.canonical_refs,
            fingerprints=context.fingerprints,
        )
    return _dataclasses.replace(
        submitted,
        result_refs=result_refs,
        question_evidence=question_evidence,
    )


def _submitted_coverages(
    bound_question: m.SemanticQuestionScope | None,
    bound_is_fallback_scaffolding: bool,
    result: m.SemanticInterpretationResult,
    subjects: tuple[m.Subject, ...],
) -> list[m.InterpretationCoverage]:
    """Derive the submitted coverages from the compact command.

    An ``ANSWERED`` decision must assert something. Identity, subjects, slice,
    completion, result refs, and question evidence are never agent-supplied.
    """
    # Span derives the canonical persisted coverage from the compact
    # command. Identity, subjects, slice, completion, result refs, and
    # question evidence are never agent-supplied ([design note L](docs/design-references.md#l)).
    submitted_coverages: list[m.InterpretationCoverage] = []
    # I2: an ANSWERED decision must assert something. Accounting-only or empty
    # completions are not answers; NOT_APPLICABLE with a basis is the terminal
    # form for "no assertion is warranted".
    if (
        result.question_decision is not None
        and result.question_decision.disposition
        is m.SemanticQuestionDisposition.ANSWERED
        and not result.claims
        and not result.relationships
    ):
        raise _validation.InterpretationUnitRejected(
            tuple(
                _member_diagnostics(
                    "question_decision",
                    0,
                    bound_question.question_slice if bound_question else None,
                    (
                        "ANSWERED requires at least one claim or relationship; "
                        "use NOT_APPLICABLE with a basis when no assertion is "
                        "warranted",
                    ),
                )
            )
        )
    if (
        bound_question is not None
        and not bound_is_fallback_scaffolding
        and result.question_decision is not None
    ):
        submitted_coverages.append(
            _decision_coverage(
                bound_question,
                result.question_decision,
                subjects=tuple(s.subject_id for s in subjects),
            )
        )
    for proposed in result.proposed_questions:
        submitted_coverages.append(
            _decision_coverage(
                proposed.question,
                proposed.decision,
                subjects=(proposed.question.subject,),
            )
        )
    return submitted_coverages
