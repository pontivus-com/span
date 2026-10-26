"""Coverage, result refs, and question evidence derivation."""

from __future__ import annotations


from span.core import model as m
from span.core import requirements as _requirements
from span.ports.store import SemanticStore
from span.service.resolution import (
    _load_all_coverages_or_defer,
)


def _material_result_refs(
    claims: tuple[m.SemanticClaim, ...],
    relationships: tuple[m.SemanticRelationship, ...],
) -> tuple[m.ClaimRef | m.RelationshipRef, ...]:
    return tuple(m.ClaimRef(id=c.claim_id) for c in claims) + tuple(
        m.RelationshipRef(id=r.relationship_id) for r in relationships
    )


def _material_evidence_refs(
    claims: tuple[m.SemanticClaim, ...],
    relationships: tuple[m.SemanticRelationship, ...],
) -> tuple[m.EvidenceRef, ...]:
    """Evidence actually cited by this unit's materialized result."""
    refs: list[m.EvidenceRef] = []
    for item in (*claims, *relationships):
        refs.extend(item.evidence)
        if item.authority is not None:
            refs.append(item.authority.evidence_ref)
    return tuple(refs)


def _load_prior_question_coverage(
    repository_id: str,
    question: m.SemanticQuestionScope,
    *,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> m.InterpretationCoverage | None:
    """Load the exact persisted row for one canonical question identity."""
    try:
        rows = store.load_all_question_coverages(
            repository_id,
            question.scope_root,
            (question.subject,),
        )
    except Exception:
        try:
            rows = store.load_question_coverages(
                repository_id,
                question.scope_root,
                (question.subject,),
                bounds,
            )
        except Exception:
            rows = ()
    for row in rows:
        if row.question is not None and row.question == question:
            return row
    return None


def _ordered_result_refs(
    prior: tuple[m.ClaimRef | m.RelationshipRef, ...],
    new: tuple[m.ClaimRef | m.RelationshipRef, ...],
    withdrawn: frozenset[str],
) -> tuple[m.ClaimRef | m.RelationshipRef, ...]:
    """Stable prior-then-new union, minus explicitly withdrawn ids."""
    seen: set[str] = set()
    ordered: list[m.ClaimRef | m.RelationshipRef] = []
    for ref in (*prior, *new):
        rid = ref.id.value
        if rid in withdrawn or rid in seen:
            continue
        seen.add(rid)
        ordered.append(ref)
    return tuple(ordered)


def _derive_question_evidence(
    decision: m.SemanticQuestionDecision,
    *,
    canonical_refs: dict[str, m.EvidenceRef],
    fingerprints: dict[str, str],
    material_evidence: tuple[m.EvidenceRef, ...] = (),
    prior_evidence: tuple[m.QuestionEvidenceObservation, ...] = (),
) -> tuple[m.QuestionEvidenceObservation, ...]:
    """Derive one question's exact direct support.

    Only the agent's selected ``evidence_scope`` and (for ANSWERED/OPEN)
    evidence actually cited by this unit's materialized results are used.
    PENDING/OPEN retain prior direct support; NOT_APPLICABLE never
    manufactures direct evidence from task delivery.
    """
    disposition = decision.disposition
    selected = decision.evidence_scope.evidence_refs
    if disposition is m.SemanticQuestionDisposition.ANSWERED:
        ordered_refs = tuple(material_evidence) + tuple(selected)
        prior: tuple[m.QuestionEvidenceObservation, ...] = ()
    elif disposition is m.SemanticQuestionDisposition.OPEN:
        ordered_refs = tuple(selected) + tuple(material_evidence)
        prior = prior_evidence
    elif disposition is m.SemanticQuestionDisposition.PENDING:
        ordered_refs = tuple(selected)
        prior = prior_evidence
    else:  # NOT_APPLICABLE
        ordered_refs = tuple(selected)
        prior = ()

    seen: set[str] = set()
    observations: list[m.QuestionEvidenceObservation] = []

    def _add_ref(ref: m.EvidenceRef) -> None:
        eid = ref.evidence_id.value
        canonical = canonical_refs.get(eid)
        fingerprint = fingerprints.get(eid)
        if canonical is None or fingerprint is None or eid in seen:
            return
        seen.add(eid)
        observations.append(
            m.QuestionEvidenceObservation(
                evidence_ref=canonical,
                observed_fingerprint=fingerprint,
            )
        )

    def _add_prior(observation: m.QuestionEvidenceObservation) -> None:
        eid = observation.evidence_ref.evidence_id.value
        if eid in seen:
            return
        seen.add(eid)
        canonical = canonical_refs.get(eid)
        fingerprint = fingerprints.get(eid)
        if canonical is not None and fingerprint is not None:
            observations.append(
                m.QuestionEvidenceObservation(
                    evidence_ref=canonical,
                    observed_fingerprint=fingerprint,
                )
            )
        else:
            observations.append(observation)

    for ref in ordered_refs:
        _add_ref(ref)
    for observation in prior:
        _add_prior(observation)
    return tuple(observations)


def _coverage(
    question: m.SemanticQuestionScope,
    *,
    subjects: tuple[m.SubjectId, ...],
    disposition: m.SemanticQuestionDisposition,
    evidence_scope: m.EvidenceScope,
    disposition_basis: str,
    resolution_requirements: tuple[m.ResolutionRequirement, ...] = (),
    result_refs: tuple[m.ClaimRef | m.RelationshipRef, ...] = (),
    question_evidence: tuple[m.QuestionEvidenceObservation, ...] = (),
) -> m.InterpretationCoverage:
    """Construct one canonical coverage record.

    This is the only coverage writer: completion follows the disposition
    (``ANSWERED`` is complete), the slice follows the question identity, and
    every caller supplies only the fields it owns.
    """
    return m.InterpretationCoverage(
        subjects=subjects,
        question_slice=question.question_slice,
        evidence_scope=evidence_scope,
        declared_complete=(disposition is m.SemanticQuestionDisposition.ANSWERED),
        question=question,
        disposition=disposition,
        result_refs=result_refs,
        resolution_requirements=resolution_requirements,
        disposition_basis=disposition_basis,
        question_evidence=question_evidence,
    )


def _decision_coverage(
    question: m.SemanticQuestionScope,
    decision: m.SemanticQuestionDecision,
    *,
    subjects: tuple[m.SubjectId, ...],
) -> m.InterpretationCoverage:
    """Project one agent decision into the canonical coverage record.

    Only the agent-owned decision crosses the boundary: disposition,
    selected support scope, typed requirements, and basis. Identity,
    slice, completion, result refs, and evidence observations are
    Span-owned and filled by the materializer ([design note L](docs/design-references.md#l)).
    """
    return _coverage(
        question,
        subjects=subjects,
        disposition=decision.disposition,
        evidence_scope=decision.evidence_scope,
        disposition_basis=decision.disposition_basis,
        resolution_requirements=decision.resolution_requirements,
    )


def _retire_replaced_outputs(
    repository_id: str,
    question: m.SemanticQuestionScope,
    new_refs: set[str],
    *,
    store: SemanticStore,
    bounds: m.QueryBounds,
    retires_claims: list[m.ClaimRef],
    retires_relationships: list[m.RelationshipRef],
) -> None:
    """Retire prior unshared outputs replaced by a complete ANSWERED
    rewrite ([design note C](docs/design-references.md#c) C-05).

    PENDING/OPEN/NOT_APPLICABLE never authorize omission-based
    retirement; explicit withdrawals retire through the validated
    path. Shared outputs are preserved (their other owners reopen via
    withdrawal fanout); enumeration overflow defers via
    ``_load_all_coverages_or_defer`` instead of retiring blind.
    """
    try:
        prior_qcovs = store.load_all_question_coverages(
            repository_id,
            question.scope_root,
            (question.subject,),
        )
    except Exception:
        try:
            prior_qcovs = store.load_question_coverages(
                repository_id,
                question.scope_root,
                (question.subject,),
                bounds,
            )
        except Exception:
            prior_qcovs = ()
    old_refs: set[str] = set()
    for qc in prior_qcovs:
        if qc.question == question:
            old_refs.update(r.id.value for r in qc.result_refs)
    for oid in old_refs - new_refs:
        # Shared-output check across ALL questions (unbounded: a
        # bounded read could hide an owner and cause an unsafe
        # retirement). Deferral propagates: never retire with an
        # incomplete owner set.
        all_qcovs = _load_all_coverages_or_defer(
            repository_id,
            None,
            (),
            store=store,
            bounds=bounds,
            purpose="shared-output retirement check",
        )
        shared = False
        for other in all_qcovs:
            if other.question == question:
                continue
            if oid in {r.id.value for r in other.result_refs}:
                shared = True
                break
        if shared:
            continue
        # Unshared: retire.
        try:
            (old_item,) = store.load_by_refs(
                repository_id,
                (m.ClaimRef(id=m.ClaimId(oid)),),
            )
            if isinstance(old_item, m.SemanticClaim):
                retires_claims.append(m.ClaimRef(id=m.ClaimId(oid)))
            else:
                retires_relationships.append(
                    m.RelationshipRef(id=m.RelationshipId(oid))
                )
        except Exception:
            try:
                store.load_by_refs(
                    repository_id,
                    (m.RelationshipRef(id=m.RelationshipId(oid)),),
                )
                retires_relationships.append(
                    m.RelationshipRef(id=m.RelationshipId(oid))
                )
            except Exception:
                continue


def _first_admission_coverage(
    sid: m.SubjectId,
    member_refs: tuple[m.EvidenceRef, ...],
) -> m.InterpretationCoverage:
    """The service-owned PENDING CQ-01 seed for a newly admitted area.

    The seed asserts no area meaning; its discovery support is the canonical
    members assigned to the area. Deterministic admission and the submission
    path both create it here, so the seed has one owner.
    """
    seed_slice = m.QUESTION_CLASS_DEFAULT_SLICE[m.SemanticQuestionClass.CQ_01]
    seed_question = m.SemanticQuestionScope(
        scope_root=sid,
        subject=sid,
        question_class=m.SemanticQuestionClass.CQ_01,
        question_slice=seed_slice,
        materiality_basis="service-owned first-admission target seed",
    )
    return _coverage(
        seed_question,
        subjects=(sid,),
        disposition=m.SemanticQuestionDisposition.PENDING,
        evidence_scope=m.EvidenceScope(evidence_refs=member_refs),
        disposition_basis="service-owned first-admission target seed",
        resolution_requirements=(
            _requirements.incomplete_scope(
                subject_or_claim=sid,
                description=(
                    "service-owned first-admission target seed: establish this "
                    "admitted area's purpose and material questions for the "
                    "selected target."
                ),
                supporting_context=(),
            ),
        ),
    )
