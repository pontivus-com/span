"""Span service status operation (plan §11.8; v0.6 §14 Amendment A-01).

Currency and verification over stored semantics, with hook fast
path and resume. Verbatim from ``span.service_operations``; only the
module path changed.
"""

from __future__ import annotations

import dataclasses as _dataclasses


from span.core import model as m
from span.core import requirements as _requirements
from span.ports.evidence import EvidenceSource
from span.ports.store import SemanticStore
from span.ports.continuation import ContinuationPort

from span.service.answers import (
    _answer_id,
    ANSWER_ASSEMBLER,
    state_explanation_for,
)
from span.service.questions import (
    effective_question_view,
)
from span.service.operations.status.explanation import (
    _status_state_explanation,
)
from span.service.operations.status.requirements import (
    _target_live_requirements,
)


def _campaign_lifespan(association: m.TargetAssociation) -> m.HandleLifespan:
    """The handle exists, so it states its own retention and recovery."""
    return m.HandleLifespan(
        kind=m.HandleKind.DURABLE,
        scope=m.HandleScope.REPOSITORY,
        expires_at=association.expires_at,
        recovery=m.HandleRecovery.REINITIALIZE_TARGET,
    )


def _campaign_content(
    association: m.TargetAssociation | None,
    disposition: m.SemanticCoverageDisposition,
    total_count: int | None,
) -> m.StatusContent:
    """One campaign content shape; a handle lifespan exists only with a handle."""
    return m.StatusContent(
        resolved_mode=m.StatusResolvedMode.CAMPAIGN,
        target_association=association,
        target_disposition=disposition,
        target_total_count=total_count,
        target_handle_lifespan=(
            None if association is None else _campaign_lifespan(association)
        ),
    )


def _campaign_answer(
    repository_id: str,
    state: m.RepositoryState,
    bounds: m.QueryBounds,
    content: m.StatusContent,
    requirements: tuple[m.ResolutionRequirement, ...] = (),
) -> m.SemanticAnswer:
    """Build one campaign answer; every campaign branch shares this shape."""
    return ANSWER_ASSEMBLER.build(
        answer_id=_answer_id("stt", repository_id, "target"),
        intent=m.SemanticIntent.STATUS,
        repository_state=state,
        subject_resolution=None,
        content=content,
        evidence=(),
        resolution_requirements=requirements,
        bounds=bounds,
        withheld_category=None,
        continuation_token=None,
        state_explanation=_status_state_explanation(
            state_explanation_for((), (), bounds=(bounds.max_results, False)),
            content,
            requirements,
        ),
    )


def _missing_target_requirement() -> m.ResolutionRequirement:
    """Unknown and expired look the same in storage: name both and the recovery."""
    return _requirements.missing_semantic_coverage(
        subject_or_claim=None,
        description=(
            "campaign handle is unknown or expired; re-run "
            "initialize_target with the same target scope and objective"
        ),
        supporting_context=(),
    )


def _target_membership_stale_requirement() -> m.ResolutionRequirement:
    """Membership drift is distinct from semantic evidence freshness."""
    return _requirements.stale_evidence(
        subject_or_claim=None,
        description=(
            "STALE means target membership changed since "
            "campaign establishment. It is distinct from "
            "semantic evidence freshness. Re-run "
            "initialize_target for the same exact target "
            "and objective."
        ),
        supporting_context=(),
    )


def _target_unaccounted_requirement(
    target_id: m.TargetId,
    objective: str,
) -> m.ResolutionRequirement:
    """Unaccounted inventory with no live unit names its exact recovery."""
    return _requirements.incomplete_scope(
        subject_or_claim=None,
        description=(
            f"target '{target_id.value}' has unaccounted inventory "
            "and no live initialize_target continuation; rerun "
            "initialize_target with the same exact target scope and "
            f"objective '{objective}'; do not synthesize a "
            "continuation"
        ),
        supporting_context=(),
    )


@_dataclasses.dataclass
class _CampaignScan:
    """The campaign's accumulated flags, requirements, and live total."""

    disposition: m.SemanticCoverageDisposition
    requirements: tuple[m.ResolutionRequirement, ...]
    total_count: int | None


def _scan_campaign_questions(
    repository_id: str,
    association: m.TargetAssociation,
    *,
    evidence: EvidenceSource,
    store: SemanticStore,
) -> tuple[bool, bool, list[m.ResolutionRequirement]]:
    """Scan every admitted target question for gaps, staleness, or currency."""
    saw_unverifiable = False
    saw_stale = False
    saw_incomplete = False
    residual: list[m.ResolutionRequirement] = []
    questions_by_area: dict[m.SubjectId, list[m.SemanticQuestionScope]] = {}
    for question in association.target_questions:
        questions_by_area.setdefault(question.scope_root, []).append(question)
    for area in association.area_subjects:
        if area not in questions_by_area:
            saw_incomplete = True
    for question in association.target_questions:
        anchors = store.load_subjects(repository_id, (question.subject,))
        anchor_requirement = None
        if anchors is not None and not anchors:
            # §4C.6D amendment (answerability, 2026-10-11): an admitted
            # question with no established anchor can never suspend.
            # Name it instead of sinking it into silent INCOMPLETE.
            anchor_requirement = _requirements.missing_semantic_coverage(
                subject_or_claim=question.subject,
                description=(
                    "question subject anchor is not established: admit "
                    + question.subject.canonical_locator
                    + " as CandidateSubject on its structural entrypoint, "
                    "then re-kick initialize_target"
                ),
                supporting_context=(),
            )
        coverages = store.load_all_question_coverages(
            repository_id,
            question.scope_root,
            (question.subject,),
        )
        match = None
        for coverage in coverages:
            if coverage.question is None:
                continue
            if (
                coverage.question.scope_root == question.scope_root
                and coverage.question.subject == question.subject
                and coverage.question.question_class == question.question_class
                and coverage.question.question_slice == question.question_slice
            ):
                match = coverage
                break
        if match is None:
            saw_incomplete = True
            if anchor_requirement is not None:
                residual.append(anchor_requirement)
            continue
        # Canonical freshness: effective disposition + dependency state.
        view = effective_question_view(
            match,
            evidence=evidence,
            store=store,
            repository_id=repository_id,
        )
        if view.freshness.state is m.FreshnessState.UNVERIFIABLE:
            saw_unverifiable = True
        elif view.freshness.state is m.FreshnessState.STALE:
            saw_stale = True
        elif view.effective_disposition in (
            m.SemanticQuestionDisposition.PENDING,
            m.SemanticQuestionDisposition.OPEN,
        ):
            saw_incomplete = True
            residual.extend(view.resolution_requirements)
            if anchor_requirement is not None:
                residual.append(anchor_requirement)
        elif view.effective_disposition not in (
            m.SemanticQuestionDisposition.ANSWERED,
            m.SemanticQuestionDisposition.NOT_APPLICABLE,
        ):
            saw_incomplete = True
    return saw_unverifiable, saw_stale, residual if saw_incomplete else []


def _scan_campaign(
    repository_id: str,
    target_id: m.TargetId,
    association: m.TargetAssociation,
    inventory: tuple[m.EvidenceInventoryItem, ...],
    *,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationPort,
) -> _CampaignScan:
    """Evaluate the whole campaign, then apply the one governing precedence.

    UNVERIFIABLE -> STALE -> INCOMPLETE -> CURRENT, accumulated across all
    members, areas, and questions. Membership staleness is the inventory
    fingerprint; content freshness for stable members is owned by the
    evidence/question/claim/relationship dependency machinery.
    """
    accounted = {
        account.evidence_ref.evidence_id.value: account
        for account in association.inventory_accounting
    }
    live_requirements = _target_live_requirements(
        repository_id,
        target_id,
        association,
        evidence=evidence,
        store=store,
        continuations=continuations,
    )
    live_mapping = any(
        record.repository_id == repository_id
        and record.target_id == target_id
        and record.request.question is None
        for record in continuations.live_records()
    )
    saw_incomplete = bool(live_requirements)
    residual: list[m.ResolutionRequirement] = list(live_requirements)
    unaccounted = any(
        item.evidence_ref.evidence_id.value not in accounted for item in inventory
    )
    if unaccounted:
        saw_incomplete = True
        if not live_mapping:
            residual.append(
                _target_unaccounted_requirement(target_id, association.objective)
            )
    saw_unverifiable, saw_stale, question_requirements = _scan_campaign_questions(
        repository_id,
        association,
        evidence=evidence,
        store=store,
    )
    if question_requirements:
        saw_incomplete = True
        residual.extend(question_requirements)
    if saw_unverifiable:
        disposition = m.SemanticCoverageDisposition.UNVERIFIABLE
    elif saw_stale:
        disposition = m.SemanticCoverageDisposition.STALE
    elif saw_incomplete:
        disposition = m.SemanticCoverageDisposition.INCOMPLETE
    else:
        disposition = m.SemanticCoverageDisposition.CURRENT
    requirements = tuple(residual) if saw_incomplete else ()
    if live_requirements:
        requirements = tuple(dict.fromkeys((*requirements, *live_requirements)))
    total_count = (
        None
        if disposition is m.SemanticCoverageDisposition.UNVERIFIABLE
        else len(inventory)
    )
    return _CampaignScan(
        disposition=disposition,
        requirements=requirements,
        total_count=total_count,
    )


def _target_status_answer(
    repository_id: str,
    target_id: m.TargetId,
    *,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    continuations: ContinuationPort,
) -> m.SemanticAnswer:
    """Campaign readback: absent → UNASSESSED, then UNVERIFIABLE→STALE→INCOMPLETE→CURRENT."""
    association = store.load_target_association(repository_id, target_id)
    if association is None:
        return _campaign_answer(
            repository_id,
            state,
            bounds,
            _campaign_content(
                None,
                m.SemanticCoverageDisposition.UNASSESSED,
                None,
            ),
            (_missing_target_requirement(),),
        )
    try:
        from span.service.discovery import enumerate_target_inventory

        inventory = enumerate_target_inventory(
            repository_id,
            association.target_scope,
            evidence=evidence,
            bounds=bounds,
        )
    except ValueError:
        # The provider refuses to establish the bounded live observation for
        # this scope. That is a fact about the repository, so the campaign
        # reads UNVERIFIABLE; any other failure is a defect and propagates
        # rather than borrowing a semantic status.
        return _campaign_answer(
            repository_id,
            state,
            bounds,
            _campaign_content(
                association,
                m.SemanticCoverageDisposition.UNVERIFIABLE,
                None,
            ),
        )
    if len(association.inventory_accounting) > bounds.max_results:
        # Bounded projection first: completeness cannot be proven within
        # bounds, even when membership also drifted.
        return _campaign_answer(
            repository_id,
            state,
            bounds,
            _campaign_content(
                association,
                m.SemanticCoverageDisposition.UNVERIFIABLE,
                None,
            ),
        )
    if m.target_inventory_fingerprint(inventory) != association.inventory_fingerprint:
        return _campaign_answer(
            repository_id,
            state,
            bounds,
            _campaign_content(
                association,
                m.SemanticCoverageDisposition.STALE,
                len(inventory),
            ),
            (_target_membership_stale_requirement(),),
        )
    scan = _scan_campaign(
        repository_id,
        target_id,
        association,
        inventory,
        evidence=evidence,
        store=store,
        continuations=continuations,
    )
    return _campaign_answer(
        repository_id,
        state,
        bounds,
        _campaign_content(association, scan.disposition, scan.total_count),
        scan.requirements,
    )
