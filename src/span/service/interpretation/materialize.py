"""One submitted unit: validate, derive, and persist."""

from __future__ import annotations
from span.core import model as m
from span.core import validation as _validation
from span.ports.evidence import EvidenceSource
from span.ports.store import SemanticStore
from span.service.refs import _item_ref
from span.service.interpretation.task import (
    InterpretationTask,
)
from span.service.interpretation.stages import (
    _CoverageInputs,
    _UnitDeps,
    _WriteInputs,
    _assemble_target_association,
    _derive_coverages,
    _prepare_unit,
    _resolve_target_mode,
    _submitted_coverages,
    _write_unit,
)


def _materialize_unit(
    task: InterpretationTask,
    result: m.SemanticInterpretationResult,
    *,
    store: SemanticStore,
    evidence: EvidenceSource,
    state: m.RepositoryState,
    extra_known_subjects: tuple[m.SubjectId, ...] = (),
    coverage: m.CoverageDependency,
    declared_complete: bool,
    retire_scope: tuple[m.SubjectId, ...],
    target_id: m.TargetId | None = None,
    target_association: m.TargetAssociation | None = None,
    current_inventory_ids: frozenset[str] = frozenset(),
    current_inventory_snapshot: dict[str, m.EvidenceRef] | None = None,
    correction_question: m.SemanticQuestionScope | None = None,
) -> None:
    """Validate and atomically materialize one submitted unit (§7.5, I-37).

    [design note B](docs/design-references.md#b): exact-question completion/retirement with shared-output
    safety, unassigned-output preservation, explicit withdrawals and
    entire-unit atomicity. Subject-wide omission is truncation, never
    withdrawal, for question-scoped writes.

    [design note H](docs/design-references.md#h) §6: when ``correction_question`` names the one nominated
    already-persisted original question of a fallback refresh unit, its
    explicit ANSWERED coverage derives/retires exactly like the bound
    question; otherwise non-bound coverages persist as submitted. The
    fallback bound question itself — which has no persisted row — is
    orchestration scaffolding only: it neither synthesizes nor persists
    its own coverage, so a successful correction leaves no synthetic
    pending question behind.
    """
    if len(result.claims) > task.request.bounds.max_candidate_claims:
        raise _validation.InterpretationUnitRejected(
            ("interpretation unit exceeds max_candidate_claims",)
        )
    if len(result.relationships) > task.request.bounds.max_candidate_relationships:
        raise _validation.InterpretationUnitRejected(
            ("interpretation unit exceeds max_candidate_relationships",)
        )
    prepared = _prepare_unit(
        task,
        result,
        _UnitDeps(
            store=store,
            evidence=evidence,
            state=state,
            extra_known_subjects=extra_known_subjects,
            retire_scope=retire_scope,
            correction_question=correction_question,
        ),
    )
    ctx = prepared.ctx
    result = prepared.result
    new_subject_ids = prepared.new_subject_ids
    claims = prepared.claims
    relationships = prepared.relationships
    verification_records = prepared.verification_records
    recorded = prepared.recorded
    fingerprints = prepared.fingerprints
    subjects = prepared.subjects
    validated_withdrawals = prepared.validated_withdrawals
    retires_claims = prepared.retires_claims
    retires_relationships = prepared.retires_relationships
    bound_question = prepared.bound_question
    bound_is_fallback_scaffolding = prepared.bound_is_fallback_scaffolding
    question_coverages_to_persist: list[m.InterpretationCoverage] = []
    reopened_coverages: list[m.InterpretationCoverage] = []
    submitted_coverages = _submitted_coverages(
        bound_question,
        bound_is_fallback_scaffolding,
        result,
        subjects,
    )
    question_coverages_to_persist, reopened_coverages = _derive_coverages(
        _CoverageInputs(
            task=task,
            result=result,
            store=store,
            ctx=ctx,
            claims=claims,
            relationships=relationships,
            subjects=subjects,
            bound_question=bound_question,
            bound_is_fallback_scaffolding=bound_is_fallback_scaffolding,
            validated_withdrawals=validated_withdrawals,
            correction_question=correction_question,
            retires_claims=retires_claims,
            retires_relationships=retires_relationships,
            fingerprints=fingerprints,
            submitted_coverages=submitted_coverages,
            question_coverages_to_persist=question_coverages_to_persist,
            reopened_coverages=reopened_coverages,
        )
    )
    dependencies = tuple(
        m.EvidenceDependency(
            semantic_id=_item_ref(item),
            evidence_ref=ref,
            observed_fingerprint=fingerprints[ref.evidence_id.value],
        )
        for item in (*claims, *relationships)
        for ref in item.evidence
    )
    all_coverages = tuple(question_coverages_to_persist) + tuple(reopened_coverages)
    effective_target_id = _resolve_target_mode(
        task,
        result,
        store=store,
        target_id=target_id,
        target_association=target_association,
        new_subject_ids=new_subject_ids,
    )
    updated_associations: tuple[m.TargetAssociation, ...] = ()
    if effective_target_id is not None and target_association is not None:
        # Every accepted target-mode submission refreshes TTL: the reconciled
        # association is persisted in the same batch even without new
        # proposals.
        updated_associations = (
            _assemble_target_association(
                task,
                result,
                store=store,
                target_association=target_association,
                new_subject_ids=new_subject_ids,
                question_coverages_to_persist=tuple(question_coverages_to_persist),
            ),
        )
    _write_unit(
        _WriteInputs(
            store=store,
            subjects=subjects,
            claims=claims,
            relationships=relationships,
            dependencies=dependencies,
            coverage=coverage,
            all_coverages=all_coverages,
            retires_claims=retires_claims,
            retires_relationships=retires_relationships,
            recorded=recorded,
            updated_associations=updated_associations,
            verification_records=verification_records,
        )
    )
