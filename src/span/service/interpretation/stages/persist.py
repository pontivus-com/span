"""One submitted unit: validate, derive, and persist."""

from __future__ import annotations

import dataclasses as _dataclasses

from span.core import model as m
from span.core import validation as _validation
from span.ports.store import SemanticStore


from span.service.interpretation.task import (
    InterpretationTask,
    _member_diagnostics,
)


def _resolve_target_mode(
    task: InterpretationTask,
    result: m.SemanticInterpretationResult,
    *,
    store: SemanticStore,
    target_id: m.TargetId | None,
    target_association: m.TargetAssociation | None,
    new_subject_ids: list[m.SubjectId],
) -> m.TargetId | None:
    """Resolve the effective target and validate any proposed target question.

    Reuse is strict: a proposed target question must already be persisted
    canonically and its subject must resolve. New questions enter only through
    ``proposed_questions`` in the same unit.
    """
    # Target-mode state (same atomic batch). Question reuse and association
    # retention are the only agent-proposed target material; membership is
    # computed at admission and never submitted.
    effective_target_id = target_id if target_id is not None else task.request.target_id
    if result.proposed_target_questions and effective_target_id is None:
        raise _validation.InterpretationUnitRejected(
            tuple(
                _member_diagnostics(
                    "target_questions",
                    0,
                    None,
                    ("target proposals without target mode",),
                )
            )
        )
    if effective_target_id is not None:
        if target_association is None or (
            target_association.target_id != effective_target_id
        ):
            raise _validation.InterpretationUnitRejected(
                tuple(
                    _member_diagnostics(
                        "target_accounts",
                        0,
                        None,
                        ("target association does not resolve",),
                    )
                )
            )
        if result.proposed_target_questions:
            admitted_all = tuple(target_association.area_subjects) + tuple(
                new_subject_ids
            )
            validation_q = _validation.validate_target_questions(
                tuple(result.proposed_target_questions),
                admitted_area_ids=tuple(admitted_all),
            )
            if not validation_q.ok:
                raise _validation.InterpretationUnitRejected(
                    tuple(
                        _member_diagnostics(
                            "target_questions",
                            0,
                            None,
                            tuple(validation_q.diagnostics),
                        )
                    )
                )
            # Reuse is strict: each proposed question must already be
            # persisted canonically. New questions enter only through
            # proposed_questions in the same unit.
            for qq_index, qq in enumerate(result.proposed_target_questions):
                try:
                    persisted = store.load_all_question_coverages(
                        task.request.repository_id,
                        qq.scope_root,
                        (qq.subject,),
                    )
                except Exception:
                    persisted = ()
                if not any(
                    cov.question is not None
                    and cov.question.scope_root == qq.scope_root
                    and cov.question.subject == qq.subject
                    and cov.question.question_class == qq.question_class
                    and cov.question.question_slice == qq.question_slice
                    for cov in persisted
                ):
                    raise _validation.InterpretationUnitRejected(
                        tuple(
                            _member_diagnostics(
                                "target_questions",
                                qq_index,
                                qq.question_slice or None,
                                (
                                    "target question does not resolve to "
                                    "persisted coverage; use "
                                    "proposed_questions to "
                                    "create new PENDING coverage",
                                ),
                            )
                        )
                    )
                if not store.load_subjects(task.request.repository_id, (qq.subject,)):
                    raise _validation.InterpretationUnitRejected(
                        tuple(
                            _member_diagnostics(
                                "target_questions",
                                qq_index,
                                qq.subject.canonical_locator,
                                ("target question subject does not " "resolve",),
                            )
                        )
                    )
    return effective_target_id


def _assemble_target_association(
    task: InterpretationTask,
    result: m.SemanticInterpretationResult,
    *,
    store: SemanticStore,
    target_association: m.TargetAssociation,
    new_subject_ids: list[m.SubjectId],
    question_coverages_to_persist: list[m.InterpretationCoverage],
) -> m.TargetAssociation:
    """Reconcile the persisted association with this unit's admitted questions.

    Area membership is derived from accounting; questions are kept only when
    their scope root is still admitted, then deduplicated by full identity.
    """
    new_area_union = tuple(
        dict.fromkeys(
            sid
            for acc in target_association.inventory_accounting
            for sid in acc.assigned_area_subjects
        )
    )
    admitted_set = set(new_area_union)
    kept_questions = tuple(
        q for q in target_association.target_questions if q.scope_root in admitted_set
    )
    added_scopes: list[m.SemanticQuestionScope] = []
    for cov_index, cov in enumerate(question_coverages_to_persist):
        if cov.question is not None:
            if cov.question.scope_root not in admitted_set:
                raise _validation.InterpretationUnitRejected(
                    tuple(
                        _member_diagnostics(
                            "question_coverages",
                            cov_index,
                            cov.question.question_slice or None,
                            ("question scope root is not an admitted " "target area",),
                        )
                    )
                )
            # §4C.6D amendment (answerability, 2026-10-11): a new
            # question anchored to nothing can never suspend or
            # answer — same fail-closed as the reuse path below.
            if cov.question.subject not in new_subject_ids:
                if not store.load_subjects(
                    task.request.repository_id, (cov.question.subject,)
                ):
                    raise _validation.InterpretationUnitRejected(
                        tuple(
                            _member_diagnostics(
                                "question_coverages",
                                cov_index,
                                cov.question.subject.canonical_locator,
                                ("target question subject does not " "resolve",),
                            )
                        )
                    )
            added_scopes.append(cov.question)
    for qq_index, qq in enumerate(result.proposed_target_questions):
        if qq.scope_root not in admitted_set:
            raise _validation.InterpretationUnitRejected(
                tuple(
                    _member_diagnostics(
                        "target_questions",
                        qq_index,
                        qq.question_slice or None,
                        ("question scope root is not an admitted " "target area",),
                    )
                )
            )
    added_scopes.extend(result.proposed_target_questions)
    combined = tuple(kept_questions) + tuple(added_scopes)
    # Deduplicate question identities deterministically (full
    # SubjectId identity: repository, locator, and kind).
    seen_q: set[tuple[str, str, str, str, str, str, str, str]] = set()
    deduped: list[m.SemanticQuestionScope] = []
    for q in combined:
        key = (
            q.scope_root.repository_id,
            q.scope_root.canonical_locator,
            q.scope_root.subject_kind.value,
            q.subject.repository_id,
            q.subject.canonical_locator,
            q.subject.subject_kind.value,
            q.question_class.value,
            q.question_slice,
        )
        if key not in seen_q:
            seen_q.add(key)
            deduped.append(q)
    updated = m.TargetAssociation(
        target_id=target_association.target_id,
        repository_id=target_association.repository_id,
        target_scope=target_association.target_scope,
        objective=target_association.objective,
        area_subjects=new_area_union,
        target_questions=tuple(deduped),
        inventory_accounting=target_association.inventory_accounting,
        inventory_fingerprint=target_association.inventory_fingerprint,
        observed_repository_state_fingerprint=(
            target_association.observed_repository_state_fingerprint
        ),
    )
    return updated


@_dataclasses.dataclass
class _WriteInputs:
    """The single atomic batch one unit writes."""

    store: SemanticStore
    subjects: tuple[m.Subject, ...]
    claims: list[m.SemanticClaim]
    relationships: list[m.SemanticRelationship]
    dependencies: tuple[m.EvidenceDependency, ...]
    coverage: m.CoverageDependency
    all_coverages: tuple[m.InterpretationCoverage, ...]
    retires_claims: list[m.ClaimRef]
    retires_relationships: list[m.RelationshipRef]
    recorded: list[m.RecordedConflict]
    updated_associations: tuple[m.TargetAssociation, ...]
    verification_records: tuple[m.ExecutedVerification, ...]


def _write_unit(inputs: _WriteInputs) -> None:
    """Write the unit's claims, coverage, retirements, and target state once."""
    store = inputs.store
    subjects = inputs.subjects
    claims = inputs.claims
    relationships = inputs.relationships
    dependencies = inputs.dependencies
    coverage = inputs.coverage
    all_coverages = inputs.all_coverages
    retires_claims = inputs.retires_claims
    retires_relationships = inputs.retires_relationships
    recorded = inputs.recorded
    updated_associations = inputs.updated_associations
    verification_records = inputs.verification_records
    # Deduplicate retirements: an explicit withdrawal and complete
    # replacement may name the same item; retiring twice must not
    # fail the batch on the second (already-moved) lookup.
    seen_retire_claims: set[str] = set()
    unique_retire_claims: list[m.ClaimRef] = []
    for ref in retires_claims:
        if ref.id.value not in seen_retire_claims:
            seen_retire_claims.add(ref.id.value)
            unique_retire_claims.append(ref)
    seen_retire_rels: set[str] = set()
    unique_retire_rels: list[m.RelationshipRef] = []
    for ref in retires_relationships:
        if ref.id.value not in seen_retire_rels:
            seen_retire_rels.add(ref.id.value)
            unique_retire_rels.append(ref)
    store.write_index_batch(
        m.CanonicalIndexBatch(
            subjects=subjects,
            claims=tuple(claims),
            relationships=tuple(relationships),
            evidence_dependencies=dependencies,
            coverage_dependencies=(coverage,),
            coverage=all_coverages,
            retires_claims=tuple(unique_retire_claims),
            retires_relationships=tuple(unique_retire_rels),
            conflicts=tuple(recorded),
            target_associations=updated_associations,
            verification_records=verification_records,
        )
    )
