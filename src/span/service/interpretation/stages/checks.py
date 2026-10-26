"""One submitted unit: validate, derive, and persist."""

from __future__ import annotations

import dataclasses as _dataclasses


from span.core import model as m
from span.core import validation as _validation
from span.ports.evidence import EvidenceSource
from span.ports.store import SemanticStore
from span.service.refs import _item_ref, _ref_value
from span.service.resolution import (
    _load_subject_state,
)


from span.service.interpretation.task import (
    InterpretationTask,
    _member_diagnostics,
)

from span.service.interpretation.admission import (
    _admit_cited_evidence,
    _validation_context_for,
)


@_dataclasses.dataclass
class _AdmittedUnit:
    """Result of admitting evidence and validating one unit's candidates."""

    ctx: _validation.ValidationContext
    result: m.SemanticInterpretationResult
    new_subjects: list[m.Subject]
    new_subject_ids: list[m.SubjectId]
    claims: list[m.SemanticClaim]
    relationships: list[m.SemanticRelationship]
    verification_records: tuple[m.ExecutedVerification, ...]
    failures: list[str]


def _reload_full_sources(
    task: InterpretationTask,
    ctx: _validation.ValidationContext,
    *,
    evidence: EvidenceSource,
) -> _validation.ValidationContext:
    """Reload canonical full source for every excerpt-bearing task unit.

    A rejected reload is an actionable rejection with a live continuation; an
    excerpt never substitutes for the full source.
    """
    # S7 §5.7 full-source validation: excerpt-bearing task units must
    # load canonical full units before quote or content validation, even
    # when the ID is already in task fingerprints. Reuses per-submission
    # map to avoid duplicate reads. Fingerprints stay complete source.
    # A full unit that cannot be loaded is an actionable rejection with
    # a live continuation; an excerpt never substitutes for it.
    _full_contents = dict(ctx.evidence_contents)
    _full_refs = dict(ctx.evidence_refs)
    _reload_failures: list[str] = []
    for _unit in task.request.task_evidence.evidence_units:
        if _unit.content_range is None:
            continue
        _eid = _unit.evidence_ref.evidence_id.value
        _canonical_ref = _full_refs.get(_eid, _unit.evidence_ref)
        try:
            _full_units = evidence.read_evidence((_canonical_ref,), task.request.bounds)
        except ValueError as exc:
            _reload_failures.append(
                f"excerpt full-source reload failed for {_eid}: {exc}; "
                "re-check the source range and resubmit under the same "
                "continuation"
            )
            continue
        if len(_full_units) != 1:
            _reload_failures.append(
                f"excerpt full-source reload failed for {_eid}: "
                "unreadable; re-check the source range and resubmit "
                "under the same continuation"
            )
            continue
        _full_contents[_eid] = _full_units[0].content
    if _reload_failures:
        raise _validation.InterpretationUnitRejected(tuple(_reload_failures))
    ctx = _validation.ValidationContext(
        allowed_claim_kinds=ctx.allowed_claim_kinds,
        allowed_relationship_kinds=ctx.allowed_relationship_kinds,
        known_evidence_ids=ctx.known_evidence_ids,
        known_subject_ids=ctx.known_subject_ids,
        evidence_fingerprints=dict(ctx.evidence_fingerprints),
        evidence_contents=_full_contents,
        evidence_refs=_full_refs,
    )
    return ctx


def _validate_bound_question(
    task: InterpretationTask,
    result: m.SemanticInterpretationResult,
    *,
    store: SemanticStore,
    correction_question: m.SemanticQuestionScope | None,
) -> tuple[m.SemanticQuestionScope | None, bool]:
    """Validate the bound-question command and detect fallback scaffolding.

    A bound question is answered only through ``question_decision``; additional
    questions are proposed. In a correction unit the bound question may be
    orchestration scaffolding with no persisted row, which changes what the
    retirement phase may synthesize.
    """
    # Question-scoped retirement: only exact bound question outputs retire,
    # and only when unshared. A bound question with no submitted coverages
    # synthesizes its own current-question coverage below so that every
    # materialization leaves durable question state (no silent unassessed
    # writes); PENDING-only synthesis claims no completion. [design note H](docs/design-references.md#h) §6
    # exception: in a correction-fallback unit (correction_question names
    # the one nominated original question while the bound question has no
    # persisted row and is therefore orchestration scaffolding), the
    # fallback bound question neither synthesizes nor persists its own
    # coverage — only the nominated original question persists.
    bound_question = task.request.question
    if bound_question is None and result.question_decision is not None:
        raise _validation.InterpretationUnitRejected(
            (
                "question_decision requires a bound question; mapping "
                "tasks submit additional questions through "
                "proposed_questions",
            )
        )
    if bound_question is not None:
        for index, proposed in enumerate(result.proposed_questions):
            if proposed.question == bound_question:
                raise _validation.InterpretationUnitRejected(
                    tuple(
                        _member_diagnostics(
                            "proposed_questions",
                            index,
                            bound_question.question_slice or None,
                            (
                                "the already-bound question must be answered "
                                "through question_decision; "
                                "proposed_questions is only for additional "
                                "questions or the explicit refresh-correction "
                                "nomination case",
                            ),
                        )
                    )
                )
    for index, proposed in enumerate(result.proposed_questions):
        if (
            proposed.decision.disposition is m.SemanticQuestionDisposition.ANSWERED
            and proposed.question != correction_question
        ):
            raise _validation.InterpretationUnitRejected(
                tuple(
                    _member_diagnostics(
                        "proposed_questions",
                        index,
                        proposed.question.question_slice or None,
                        (
                            "additional questions may be introduced as "
                            "PENDING, OPEN, or NOT_APPLICABLE; only the "
                            "currently bound question may be newly ANSWERED "
                            "in this interpretation unit",
                        ),
                    )
                )
            )
    bound_is_fallback_scaffolding = False
    if correction_question is not None and bound_question is not None:
        try:
            bound_existing = store.load_all_question_coverages(
                task.request.repository_id,
                bound_question.scope_root,
                (bound_question.subject,),
            )
        except Exception:
            bound_existing = ()
        bound_is_fallback_scaffolding = not any(
            cov.question is not None and cov.question == bound_question
            for cov in bound_existing
        )
    return bound_question, bound_is_fallback_scaffolding


def _validate_premises_and_conflicts(
    task: InterpretationTask,
    result: m.SemanticInterpretationResult,
    *,
    store: SemanticStore,
    ctx: _validation.ValidationContext,
    claims: list[m.SemanticClaim],
    relationships: list[m.SemanticRelationship],
    failures: list[str],
) -> list[m.RecordedConflict]:
    """Check duplicate candidates, premise currency, and declared conflicts.

    Premises must resolve to active same-repository items: a stale premise
    cannot support a newly current conclusion, and a cycle within the unit is
    rejected. Every conflict must name two candidates in this unit.
    """
    # B-03: duplicate substantive candidates fail; reordering is stable.
    seen_ids: set[str] = set()
    for item in (*claims, *relationships):
        iid = (
            item.claim_id.value
            if isinstance(item, m.SemanticClaim)
            else item.relationship_id.value
        )
        if iid in seen_ids:
            failures.append(f"duplicate substantive candidate: {iid}")
        seen_ids.add(iid)
    # B-05: premise refs must resolve to active same-repo items; stale
    # premises cannot support newly current conclusions; no self-refs/cycles.
    try:
        active_items = {
            _ref_value(r): r
            for r in (
                tuple(m.ClaimRef(id=c.claim_id) for c in claims)
                + tuple(m.RelationshipRef(id=r.relationship_id) for r in relationships)
            )
        }
        for item in (*claims, *relationships):
            for pref in item.basis.input_refs:
                if not isinstance(pref, (m.ClaimRef, m.RelationshipRef)):
                    continue
                pid = pref.id.value
                if pid in active_items and pid == (
                    item.claim_id.value
                    if isinstance(item, m.SemanticClaim)
                    else item.relationship_id.value
                ):
                    failures.append("semantic premise self-dependency")
                    continue
                if pid in seen_ids:
                    # Within-unit cycle: new items referencing each other.
                    failures.append(f"semantic premise cycle within unit: {pid}")
                    continue
                try:
                    (prior,) = store.load_by_refs(task.request.repository_id, (pref,))
                except ValueError:
                    failures.append(f"semantic premise does not resolve: {pid}")
                    continue
                if prior.freshness.state is not m.FreshnessState.CURRENT:
                    failures.append(
                        f"stale premise cannot support current conclusion: {pid}"
                    )
    except Exception as exc:
        # Port-conformance failure fails the unit closed: validation
        # never proceeds on unverified premises.
        failures.append(f"premise validation unavailable: {exc}")
    keys_in_result = frozenset(
        [c.candidate_key for c in result.claims]
        + [r.candidate_key for r in result.relationships]
    )
    key_to_ref: dict[str, m.ClaimRef | m.RelationshipRef] = {}
    for candidate, item in zip(result.claims, claims):
        key_to_ref[candidate.candidate_key] = m.ClaimRef(id=item.claim_id)
    for candidate, item in zip(result.relationships, relationships):
        key_to_ref[candidate.candidate_key] = m.RelationshipRef(id=item.relationship_id)
    recorded: list[m.RecordedConflict] = []
    for index, proposed in enumerate(result.candidate_conflicts):
        validation = _validation.validate_candidate_conflict(
            proposed, keys_in_result, ctx
        )
        if not validation.ok:
            failures.extend(
                _member_diagnostics(
                    "conflicts",
                    index,
                    f"{proposed.left_key}/{proposed.right_key}",
                    validation.diagnostics,
                )
            )
            continue
        left = key_to_ref[proposed.left_key]
        right = key_to_ref[proposed.right_key]
        left_item = next(
            item for item in (*claims, *relationships) if _item_ref(item) == left
        )
        recorded.append(
            m.RecordedConflict(
                subject=(
                    left_item.subject
                    if isinstance(left_item, m.SemanticClaim)
                    else left_item.source
                ),
                left=left,
                right=right,
                declared_precedence=proposed.candidate_precedence,
                basis=proposed.basis,
            )
        )
    return recorded


def _validate_withdrawals(
    task: InterpretationTask,
    result: m.SemanticInterpretationResult,
    *,
    store: SemanticStore,
    ctx: _validation.ValidationContext,
    known_ids: set[str],
    retire_scope: tuple[m.SubjectId, ...],
    correction_question: m.SemanticQuestionScope | None,
) -> tuple[
    list[m.CandidateSemanticWithdrawal],
    list[m.ClaimRef],
    list[m.RelationshipRef],
]:
    """Validate explicit withdrawals and split them into claim/relationship refs.

    Withdrawal scope is the bound question, or the whole retirement scope for a
    question-less unit, plus the nominated correction question when present.
    Omission is never a withdrawal.
    """
    # Explicit withdrawals (B-03): validated, source-grounded, never omission.
    all_result_ids = frozenset(known_ids)
    try:
        prior_refs_for_withdrawal: set[str] = set()
        if task.request.question is not None:
            bq = task.request.question
            try:
                existing_qcovs = store.load_all_question_coverages(
                    task.request.repository_id,
                    bq.scope_root,
                    (bq.subject,),
                )
            except Exception:
                try:
                    existing_qcovs = store.load_question_coverages(
                        task.request.repository_id,
                        bq.scope_root,
                        (bq.subject,),
                        task.request.bounds,
                    )
                except Exception:
                    existing_qcovs = ()
            for qc in existing_qcovs:
                if qc.question is None:
                    continue
                q = qc.question
                if (
                    q.scope_root == bq.scope_root
                    and q.subject == bq.subject
                    and q.question_class == bq.question_class
                    and q.question_slice == bq.question_slice
                ):
                    prior_refs_for_withdrawal.update(r.id.value for r in qc.result_refs)
        else:
            for sid in retire_scope:
                try:
                    lc, lr, _, _ = _load_subject_state(
                        task.request.repository_id,
                        sid,
                        store=store,
                        bounds=task.request.bounds,
                    )
                except Exception:
                    continue
                prior_refs_for_withdrawal.update(c.claim_id.value for c in lc)
                prior_refs_for_withdrawal.update(r.relationship_id.value for r in lr)
    except Exception:
        prior_refs_for_withdrawal = set()
    if correction_question is not None:
        # [design note H](docs/design-references.md#h) §6: the one nominated original question contributes
        # its prior outputs to withdrawal scope alongside the bound
        # question. New-unit ids are already in all_result_ids.
        try:
            nominated_qcovs = store.load_all_question_coverages(
                task.request.repository_id,
                correction_question.scope_root,
                (correction_question.subject,),
            )
        except Exception:
            nominated_qcovs = ()
        for qc in nominated_qcovs:
            if qc.question is None:
                continue
            if qc.question == correction_question:
                prior_refs_for_withdrawal.update(r.id.value for r in qc.result_refs)
    known_for_withdrawal = frozenset(all_result_ids | prior_refs_for_withdrawal)
    validated_withdrawals: list[m.CandidateSemanticWithdrawal] = []
    for index, withdrawal in enumerate(result.candidate_withdrawals):
        withdrawal_key = withdrawal.target.id.value
        problem = _validation.validate_candidate_withdrawal(
            withdrawal,
            ctx,
            known_for_withdrawal,
            "withdrawal",
        )
        if problem is not None:
            raise _validation.InterpretationUnitRejected(
                tuple(
                    _member_diagnostics(
                        "withdrawals",
                        index,
                        withdrawal_key,
                        (problem,),
                    )
                )
            )
        # Must name active item in bound question or shared-output set.
        # Local name is withdrawal-scoped: it must not shadow the
        # target-campaign `target_id` parameter used below.
        withdrawal_target_id = withdrawal.target.id.value
        try:
            store.load_by_refs(task.request.repository_id, (withdrawal.target,))
        except ValueError:
            raise _validation.InterpretationUnitRejected(
                tuple(
                    _member_diagnostics(
                        "withdrawals",
                        index,
                        withdrawal_target_id,
                        (f"withdrawal target unknown: " f"{withdrawal_target_id}",),
                    )
                )
            )
        validated_withdrawals.append(withdrawal)
    retires_claims: list[m.ClaimRef] = []
    retires_relationships: list[m.RelationshipRef] = []
    for withdrawal in validated_withdrawals:
        if isinstance(withdrawal.target, m.ClaimRef):
            retires_claims.append(withdrawal.target)
        else:
            retires_relationships.append(withdrawal.target)
    return validated_withdrawals, retires_claims, retires_relationships


def _admit_and_validate(
    task: InterpretationTask,
    result: m.SemanticInterpretationResult,
    *,
    store: SemanticStore,
    evidence: EvidenceSource,
    state: m.RepositoryState,
    extra_known_subjects: tuple[m.SubjectId, ...],
) -> _AdmittedUnit:
    """Admit cited evidence, then validate and materialize every candidate.

    Full-source reload runs first so quote and content checks never rest on an
    excerpt. Candidate subjects are validated before claims so a claim may
    reference a subject the same unit admits.
    """
    ctx = _validation_context_for(task, extra_known_subjects)
    ctx = _reload_full_sources(task, ctx, evidence=evidence)
    ctx, result, evidence_problems = _admit_cited_evidence(
        task.request.repository_id,
        result,
        ctx,
        evidence=evidence,
        bounds=task.request.bounds,
    )
    failures: list[str] = []
    failures.extend(evidence_problems)
    new_subjects: list[m.Subject] = []
    new_subject_ids: list[m.SubjectId] = []
    for index, proposed in enumerate(result.candidate_subjects):
        validation = _validation.validate_candidate_subject(proposed, ctx)
        if not validation.ok:
            failures.extend(
                _member_diagnostics(
                    "candidate_subjects",
                    index,
                    proposed.provisional_locator or None,
                    validation.diagnostics,
                )
            )
            continue
        sid = m.SubjectId(
            repository_id=task.request.repository_id,
            subject_kind=proposed.kind,
            canonical_locator=proposed.provisional_locator,
        )
        existing = store.load_subjects(task.request.repository_id, (sid,))
        if existing:
            new_subjects.append(existing[0])
        else:
            new_subjects.append(
                m.Subject(
                    subject_id=sid,
                    display_name=proposed.display_name,
                    declared_kind=proposed.declared_kind,
                )
            )
        new_subject_ids.append(sid)
    if new_subject_ids:
        ctx = _validation.ValidationContext(
            allowed_claim_kinds=ctx.allowed_claim_kinds,
            allowed_relationship_kinds=ctx.allowed_relationship_kinds,
            known_evidence_ids=ctx.known_evidence_ids,
            known_subject_ids=(ctx.known_subject_ids + tuple(new_subject_ids)),
            evidence_fingerprints=ctx.evidence_fingerprints,
            evidence_contents=ctx.evidence_contents,
            evidence_refs=ctx.evidence_refs,
        )
    claims: list[m.SemanticClaim] = []
    for index, candidate in enumerate(result.claims):
        validation = _validation.validate_candidate_claim(candidate, ctx)
        if not validation.ok:
            failures.extend(
                _member_diagnostics(
                    "claims",
                    index,
                    candidate.candidate_key or None,
                    validation.diagnostics,
                )
            )
            continue
        claims.append(_validation.materialize_claim(candidate, validation, state))
    relationships: list[m.SemanticRelationship] = []
    for index, candidate in enumerate(result.relationships):
        validation = _validation.validate_candidate_relationship(candidate, ctx)
        if not validation.ok:
            failures.extend(
                _member_diagnostics(
                    "relationships",
                    index,
                    candidate.candidate_key or None,
                    validation.diagnostics,
                )
            )
            continue
        relationships.append(
            _validation.materialize_relationship(candidate, validation, state)
        )
    try:
        verification_records = _validation.validate_verification_records(
            task.request.repository_id, result, tuple(claims)
        )
    except ValueError as exc:
        failures.append(f"verification_records: {exc}")
        verification_records = ()
    return _AdmittedUnit(
        ctx=ctx,
        result=result,
        new_subjects=new_subjects,
        new_subject_ids=new_subject_ids,
        claims=claims,
        relationships=relationships,
        verification_records=verification_records,
        failures=failures,
    )
