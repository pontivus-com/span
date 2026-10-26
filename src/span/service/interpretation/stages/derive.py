"""One submitted unit: validate, derive, and persist."""

from __future__ import annotations

import dataclasses as _dataclasses
from span.core import model as m
from span.core import requirements as _requirements
from span.core import validation as _validation
from span.ports.store import SemanticStore
from span.service.resolution import _load_all_coverages_or_defer
from span.service.interpretation.stages.render import (
    _FinalizeContext,
    _finalize_coverage,
)

from span.service.interpretation.coverage import (
    _coverage,
    _load_prior_question_coverage,
    _material_evidence_refs,
    _material_result_refs,
    _ordered_result_refs,
    _retire_replaced_outputs,
)
from span.service.interpretation.task import (
    InterpretationTask,
    _member_diagnostics,
)


def _reopen_shared_outputs(
    task: InterpretationTask,
    *,
    store: SemanticStore,
    validated_withdrawals: list[m.CandidateSemanticWithdrawal],
    bound_question: m.SemanticQuestionScope | None,
    correction_question: m.SemanticQuestionScope | None,
) -> list[m.InterpretationCoverage]:
    """Reopen every other question that depended on a withdrawn output.

    The reopened question keeps its own requirements and gains a stale-evidence
    requirement naming the actual withdrawal reason. Enumeration is unbounded;
    overflow defers by raising, so no partial fanout is written.
    """
    reopened_coverages: list[m.InterpretationCoverage] = []
    # Explicit withdrawal fanout: reopen all other referencing questions.
    # Enumeration is unbounded; overflow defers (raises, no partial
    # write) instead of retiring with an incomplete fanout.
    if validated_withdrawals:
        all_qcovs = _load_all_coverages_or_defer(
            task.request.repository_id,
            None,
            (),
            store=store,
            bounds=task.request.bounds,
            purpose="withdrawal fanout",
        )
        withdrawn_ids = {w.target.id.value for w in validated_withdrawals}
        withdrawn_reasons: dict[str, str] = {}
        for w in validated_withdrawals:
            withdrawn_reasons.setdefault(w.target.id.value, w.basis.summary)
        for other in all_qcovs:
            if other.question is None:
                continue
            if bound_question is not None and other.question == bound_question:
                continue
            if (
                correction_question is not None
                and other.question == correction_question
            ):
                # [design note H](docs/design-references.md#h) §6: the nominated original question is
                # answered by this same unit; its prior row is
                # superseded by the derived ANSWERED coverage above,
                # not reopened.
                continue
            other_ref_ids = {r.id.value for r in other.result_refs}
            if withdrawn_ids & other_ref_ids:
                # S8.3: reopen with the actual withdrawal reason
                # while preserving the dependent question's useful
                # original requirements.
                reasons = sorted(
                    {
                        withdrawn_reasons[rid]
                        for rid in other_ref_ids
                        if rid in withdrawn_reasons
                    }
                )
                reason = "; ".join(reasons) if reasons else "shared output withdrawn"
                reopened_coverages.append(
                    _coverage(
                        other.question,
                        subjects=other.subjects,
                        disposition=m.SemanticQuestionDisposition.PENDING,
                        evidence_scope=other.evidence_scope,
                        result_refs=other.result_refs,
                        disposition_basis=(
                            "reopened by explicit withdrawal in bound question"
                        ),
                        resolution_requirements=(
                            tuple(other.resolution_requirements)
                            + (
                                _requirements.stale_evidence(
                                    subject_or_claim=(other.question.subject),
                                    description=(
                                        "shared output withdrawn "
                                        f"({reason}); reassessment "
                                        "required"
                                    ),
                                    supporting_context=tuple(
                                        w.target
                                        for w in validated_withdrawals
                                        if w.target.id.value in other_ref_ids
                                    ),
                                ),
                            )
                        ),
                        question_evidence=other.question_evidence,
                    )
                )
    # Bound check: if fanout exceeds bounds, fail without partial.
    if len(reopened_coverages) > task.request.bounds.max_results:
        raise _validation.InterpretationUnitRejected(
            ("withdrawal fanout exceeds bounds; deferred",)
        )
    return reopened_coverages


def _validate_submitted_coverages(
    submitted_coverages: list[m.InterpretationCoverage],
    ctx: _validation.ValidationContext,
) -> None:
    """Validate every submitted coverage before any is derived or persisted.

    Identity is complete (scope root, subject, class, slice); a duplicate
    identity is ambiguous, not a merge. Slice, disposition, and evidence scope
    must satisfy the coverage contract.
    """

    # Validate submitted coverages; derive refs/evidence from validated
    # candidates and expressly selected support refs.
    seen_qidentities: set[tuple[str, ...]] = set()
    for qindex, submitted in enumerate(submitted_coverages):
        if submitted.question is None:
            raise _validation.InterpretationUnitRejected(
                tuple(
                    _member_diagnostics(
                        "question_coverages",
                        qindex,
                        None,
                        ("question coverage without question scope",),
                    )
                )
            )
        q = submitted.question
        ident = (
            q.scope_root.repository_id,
            q.scope_root.canonical_locator,
            q.scope_root.subject_kind.value,
            q.subject.canonical_locator,
            q.subject.subject_kind.value,
            q.question_class.value,
            q.question_slice,
        )
        if ident in seen_qidentities:
            raise _validation.InterpretationUnitRejected(
                tuple(
                    _member_diagnostics(
                        "question_coverages",
                        qindex,
                        q.question_slice or None,
                        ("duplicate question identity in submission",),
                    )
                )
            )
        seen_qidentities.add(ident)
        problem = _validation.validate_question_coverage(
            submitted,
            ctx,
            "question coverage",
        )
        if problem is not None:
            raise _validation.InterpretationUnitRejected(
                tuple(
                    _member_diagnostics(
                        "question_coverages",
                        qindex,
                        q.question_slice or None,
                        (problem,),
                    )
                )
            )
        if q.question_slice != submitted.question_slice:
            raise _validation.InterpretationUnitRejected(
                tuple(
                    _member_diagnostics(
                        "question_coverages",
                        qindex,
                        q.question_slice or None,
                        ("question_slice mismatch in coverage",),
                    )
                )
            )


def _derive_coverages(
    inputs: _CoverageInputs,
) -> tuple[list[m.InterpretationCoverage], list[m.InterpretationCoverage]]:
    """Derive canonical coverage from the compact command.

    Validates every submitted coverage, derives result refs and question
    evidence per disposition, retires replaced outputs for a complete
    replacement, and reopens shared outputs withdrawn from the bound question.
    """
    task = inputs.task
    if inputs.bound_question is None and not inputs.submitted_coverages:
        return inputs.question_coverages_to_persist, inputs.reopened_coverages
    _validate_submitted_coverages(inputs.submitted_coverages, inputs.ctx)
    deriver = _CoverageDeriver(
        repository_id=task.request.repository_id,
        bounds=task.request.bounds,
        store=inputs.store,
        context=_FinalizeContext(
            canonical_refs=inputs.ctx.evidence_refs,
            fingerprints=inputs.fingerprints,
            new_result_refs=_material_result_refs(inputs.claims, inputs.relationships),
            material_evidence=_material_evidence_refs(
                inputs.claims, inputs.relationships
            ),
            withdrawn_ids=frozenset(
                withdrawal.target.id.value
                for withdrawal in inputs.validated_withdrawals
            ),
        ),
    )
    has_material = bool(inputs.claims or inputs.relationships)
    current_qcov = _current_question_coverage(
        task=task,
        deriver=deriver,
        submitted_coverages=inputs.submitted_coverages,
        bound_question=inputs.bound_question,
        bound_is_fallback_scaffolding=inputs.bound_is_fallback_scaffolding,
        subjects=inputs.subjects,
        retires_claims=inputs.retires_claims,
        retires_relationships=inputs.retires_relationships,
        has_material=has_material,
    )
    nominated_qcov = _nominated_correction_coverage(
        task=task,
        deriver=deriver,
        submitted_coverages=inputs.submitted_coverages,
        correction_question=inputs.correction_question,
        retires_claims=inputs.retires_claims,
        retires_relationships=inputs.retires_relationships,
        has_material=has_material,
    )
    question_coverages_to_persist = _persistable_coverages(
        deriver=deriver,
        submitted_coverages=inputs.submitted_coverages,
        bound_question=inputs.bound_question,
        correction_question=inputs.correction_question,
        current_qcov=current_qcov,
        nominated_qcov=nominated_qcov,
    )
    reopened_coverages = _reopen_shared_outputs(
        task,
        store=inputs.store,
        validated_withdrawals=inputs.validated_withdrawals,
        bound_question=inputs.bound_question,
        correction_question=inputs.correction_question,
    )
    return question_coverages_to_persist, reopened_coverages


@_dataclasses.dataclass
class _CoverageDeriver:
    """Load prior coverage once and finalize coverages against unit support."""

    repository_id: str
    bounds: m.QueryBounds
    store: SemanticStore
    context: _FinalizeContext
    _prior_cache: dict[m.SemanticQuestionScope, m.InterpretationCoverage | None] = (
        _dataclasses.field(default_factory=dict)
    )

    def prior(
        self,
        question: m.SemanticQuestionScope,
    ) -> m.InterpretationCoverage | None:
        if question not in self._prior_cache:
            self._prior_cache[question] = _load_prior_question_coverage(
                self.repository_id,
                question,
                store=self.store,
                bounds=self.bounds,
            )
        return self._prior_cache[question]

    def finalize(
        self,
        submitted: m.InterpretationCoverage,
        *,
        owns_material: bool,
    ) -> m.InterpretationCoverage:
        return _finalize_coverage(
            submitted,
            prior=self.prior(submitted.question),
            owns_material=owns_material,
            context=self.context,
        )


def _require_answered_material(
    coverage: m.InterpretationCoverage,
    question: m.SemanticQuestionScope,
    *,
    has_material: bool,
) -> None:
    """An explicit ANSWERED coverage must assert something in this unit."""
    if coverage.disposition is not m.SemanticQuestionDisposition.ANSWERED:
        return
    if has_material:
        return
    raise _validation.InterpretationUnitRejected(
        tuple(
            _member_diagnostics(
                "question_coverages",
                0,
                question.question_slice or None,
                (
                    "explicit ANSWERED with zero "
                    "validated material; submit "
                    "PENDING/OPEN or add supported "
                    "candidates",
                ),
            )
        )
    )


def _current_question_coverage(
    *,
    task: InterpretationTask,
    deriver: _CoverageDeriver,
    submitted_coverages: list[m.InterpretationCoverage],
    bound_question: m.SemanticQuestionScope | None,
    bound_is_fallback_scaffolding: bool,
    subjects: tuple[m.Subject, ...],
    retires_claims: list[m.ClaimRef],
    retires_relationships: list[m.RelationshipRef],
    has_material: bool,
) -> m.InterpretationCoverage | None:
    """Derive the bound question's single persisted coverage.

    [design note C](docs/design-references.md#c) C-05 eliminates implied completion: an explicit submitted
    disposition is required for ANSWERED/NOT_APPLICABLE. Missing explicit
    coverage always synthesizes PENDING, never completion, so claims without a
    completion claim stay unassigned output. [design note H](docs/design-references.md#h) §6 correction-fallback
    case: the fallback bound question is scaffolding only — it neither adopts
    an explicitly submitted bound coverage nor synthesizes PENDING.
    """
    if bound_question is None or bound_is_fallback_scaffolding:
        return None
    is_current = [
        coverage
        for coverage in submitted_coverages
        if coverage.question is not None and coverage.question == bound_question
    ]
    if is_current:
        current_qcov = is_current[0]
        _require_answered_material(
            current_qcov,
            bound_question,
            has_material=has_material,
        )
        current_qcov = deriver.finalize(current_qcov, owns_material=True)
    else:
        current_qcov = _synthesized_pending_coverage(
            task=task,
            deriver=deriver,
            bound_question=bound_question,
            subjects=subjects,
        )
    if current_qcov.disposition is m.SemanticQuestionDisposition.ANSWERED:
        # [design note C](docs/design-references.md#c) C-05: only a complete replacement retires prior unshared
        # outputs. PENDING/OPEN/NOT_APPLICABLE never authorize omission-based
        # retirement; explicit withdrawals retire through their own path.
        _retire_replaced_outputs(
            task.request.repository_id,
            bound_question,
            {ref.id.value for ref in current_qcov.result_refs},
            store=deriver.store,
            bounds=task.request.bounds,
            retires_claims=retires_claims,
            retires_relationships=retires_relationships,
        )
    return current_qcov


def _synthesized_pending_coverage(
    *,
    task: InterpretationTask,
    deriver: _CoverageDeriver,
    bound_question: m.SemanticQuestionScope,
    subjects: tuple[m.Subject, ...],
) -> m.InterpretationCoverage:
    """Build the PENDING coverage a unit must not omit ([design note C](docs/design-references.md#c) C-05).

    Span-derived support: one question's direct evidence is only its selected
    support plus (for ANSWERED/OPEN) evidence cited by the materialized results
    that question owns. Task delivery alone is never a direct question
    dependency.
    """
    prior = deriver.prior(bound_question)
    return _coverage(
        bound_question,
        subjects=tuple(subject.subject_id for subject in subjects),
        disposition=m.SemanticQuestionDisposition.PENDING,
        evidence_scope=m.EvidenceScope(
            paths=(),
            evidence_refs=tuple(
                unit.evidence_ref for unit in task.request.task_evidence.evidence_units
            ),
        ),
        disposition_basis="synthesized pending: no explicit completion submitted",
        result_refs=_ordered_result_refs(
            () if prior is None else prior.result_refs,
            (),
            deriver.context.withdrawn_ids,
        ),
        resolution_requirements=(
            _requirements.missing_semantic_coverage(
                subject_or_claim=bound_question.subject,
                description=(
                    "question submitted without explicit "
                    "completion; examination pending"
                ),
                supporting_context=(),
            ),
        ),
        question_evidence=() if prior is None else prior.question_evidence,
    )


def _nominated_correction_coverage(
    *,
    task: InterpretationTask,
    deriver: _CoverageDeriver,
    submitted_coverages: list[m.InterpretationCoverage],
    correction_question: m.SemanticQuestionScope | None,
    retires_claims: list[m.ClaimRef],
    retires_relationships: list[m.RelationshipRef],
    has_material: bool,
) -> m.InterpretationCoverage | None:
    """Derive the one nominated original question of a fallback refresh unit.

    [design note H](docs/design-references.md#h) §6: it derives and retires exactly like the bound question. Any
    other non-bound coverage persists as submitted.
    """
    if correction_question is None:
        return None
    is_nominated = [
        coverage
        for coverage in submitted_coverages
        if coverage.question is not None and coverage.question == correction_question
    ]
    if not is_nominated:
        return None
    nominated_qcov = is_nominated[0]
    _require_answered_material(
        nominated_qcov,
        correction_question,
        has_material=has_material,
    )
    nominated_qcov = deriver.finalize(nominated_qcov, owns_material=True)
    if nominated_qcov.disposition is m.SemanticQuestionDisposition.ANSWERED:
        _retire_replaced_outputs(
            task.request.repository_id,
            correction_question,
            {ref.id.value for ref in nominated_qcov.result_refs},
            store=deriver.store,
            bounds=task.request.bounds,
            retires_claims=retires_claims,
            retires_relationships=retires_relationships,
        )
    return nominated_qcov


def _persistable_coverages(
    *,
    deriver: _CoverageDeriver,
    submitted_coverages: list[m.InterpretationCoverage],
    bound_question: m.SemanticQuestionScope | None,
    correction_question: m.SemanticQuestionScope | None,
    current_qcov: m.InterpretationCoverage | None,
    nominated_qcov: m.InterpretationCoverage | None,
) -> list[m.InterpretationCoverage]:
    """Assemble the unit's persisted coverages exactly once each.

    [design note C](docs/design-references.md#c) C-05: the bound question persists once, as the derived or
    synthesized current coverage — never the submitted original, whose empty
    refs are intent rather than examined output. The nominated correction
    question likewise persists once as its derived coverage. In the [design note H](docs/design-references.md#h)
    §6 fallback case the fallback bound question persists zero times.
    """
    persisted = [
        deriver.finalize(coverage, owns_material=False)
        for coverage in submitted_coverages
        if coverage.question is None
        or (
            (bound_question is None or coverage.question != bound_question)
            and (
                correction_question is None or coverage.question != correction_question
            )
        )
    ]
    if current_qcov is not None:
        persisted.append(current_qcov)
    if nominated_qcov is not None:
        persisted.append(nominated_qcov)
    return persisted


@_dataclasses.dataclass
class _CoverageInputs:
    """Everything the coverage derivation reads, and the lists it fills."""

    task: InterpretationTask
    result: m.SemanticInterpretationResult
    store: SemanticStore
    ctx: _validation.ValidationContext
    claims: list[m.SemanticClaim]
    relationships: list[m.SemanticRelationship]
    subjects: tuple[m.Subject, ...]
    bound_question: m.SemanticQuestionScope | None
    bound_is_fallback_scaffolding: bool
    validated_withdrawals: list[m.CandidateSemanticWithdrawal]
    correction_question: m.SemanticQuestionScope | None
    retires_claims: list[m.ClaimRef]
    retires_relationships: list[m.RelationshipRef]
    fingerprints: dict[str, str]
    submitted_coverages: list[m.InterpretationCoverage]
    question_coverages_to_persist: list[m.InterpretationCoverage]
    reopened_coverages: list[m.InterpretationCoverage]
