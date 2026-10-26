"""Host-facing semantic target establishment ([design note D](docs/design-references.md#d)).

This operation owns only the deterministic boundary and frontier.  The
active host agent still performs semantic interpretation and submits the
canonical typed result through ``submit_interpretation``.  No model is
invoked here and no second semantic writer or progress store is introduced.
"""

from __future__ import annotations

import dataclasses as _dataclasses

from span.core import model as m
from span.ports.evidence import EvidenceSource
from span.ports.store import SemanticStore
from span.ports.structural import StructuralSource

from span.service.interpretation import (
    _first_admission_coverage,
)
from span.service.resolution import _resolve_target_subjects


def target_subjects(
    repository_id: str,
    target: m.EvidenceScope,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> tuple[m.Subject, ...]:
    """Enumerate bounded structural candidates in the exact target.

    These candidates make the exchange resumable; they are not semantic
    areas and their count is not a completion claim. The exact target is
    carried separately on each pending interpretation request.
    """
    return _resolve_target_subjects(
        repository_id,
        target,
        structural=structural,
        evidence=evidence,
        store=store,
        bounds=bounds,
    )


def _scope_root_locator(member_locators: tuple[str, ...]) -> str:
    """The one directory the admitted members are rooted at.

    Members that share no directory are rooted at the repository root.
    """
    if not member_locators:
        return "."
    parts = [member.split("/")[:-1] for member in member_locators]
    common = parts[0]
    for candidate in parts[1:]:
        limit = 0
        while (
            limit < len(common)
            and limit < len(candidate)
            and common[limit] == candidate[limit]
        ):
            limit += 1
        common = common[:limit]
    return "/".join(common) if common else "."


def _scope_area_subject(
    repository_id: str,
    member_locators: tuple[str, ...],
    subjects: tuple[m.Subject, ...],
) -> m.Subject:
    """The single area a target admits, computed from its own members.

    A target is one area, not one area per member. The area is the shallowest
    in-scope subject that contains another member (a package or directory).
    When the members are named directly and no container subject is indexed,
    the area is the directory the members share, represented as an ``OTHER``
    subject. Either way admission is deterministic and never selects an
    arbitrary member file as the area.
    """
    containers = [
        subject
        for subject in subjects
        if any(
            member.startswith(subject.subject_id.canonical_locator.rstrip("/") + "/")
            for member in member_locators
        )
    ]
    if containers:
        return min(
            containers,
            key=lambda subject: (
                subject.subject_id.canonical_locator.count("/"),
                len(subject.subject_id.canonical_locator),
                subject.subject_id.canonical_locator,
            ),
        )
    locator = _scope_root_locator(member_locators)
    return m.Subject(
        subject_id=m.SubjectId(
            repository_id=repository_id,
            subject_kind=m.SubjectKind.OTHER,
            canonical_locator=locator,
        ),
        display_name=locator,
        declared_kind=locator,
    )


def _deterministic_accounting(
    items: tuple[m.EvidenceInventoryItem, ...],
    existing: tuple[m.TargetInventoryAccount, ...],
    area: m.Subject,
) -> tuple[tuple[m.TargetInventoryAccount, ...], tuple[m.EvidenceRef, ...]]:
    """One assignment per inventory member, retaining an existing assignment.

    Membership is computable, so the agent is never asked for it. Returns the
    accounting and the area's member refs used by the first-admission seed.
    """
    prior = {acc.evidence_ref.evidence_id.value: acc for acc in existing}
    accounts: list[m.TargetInventoryAccount] = []
    member_refs: list[m.EvidenceRef] = []
    for item in items:
        evidence_id = item.evidence_ref.evidence_id.value
        retained = prior.get(evidence_id)
        if (
            retained is not None
            and retained.evidence_ref.locator == item.evidence_ref.locator
        ):
            accounts.append(retained)
            assigned = retained.assigned_area_subjects
        else:
            accounts.append(
                m.TargetInventoryAccount(
                    evidence_ref=item.evidence_ref,
                    assigned_area_subjects=(area.subject_id,),
                )
            )
            assigned = (area.subject_id,)
        if area.subject_id in assigned:
            member_refs.append(item.evidence_ref)
    return tuple(accounts), tuple(member_refs)


@_dataclasses.dataclass
class _TargetReconciliation:
    """What one target reconciliation decides to write, and nothing more."""

    association: m.TargetAssociation
    area: m.Subject | None
    seed_coverage: m.InterpretationCoverage | None


def _reconcile_target_association(
    repository_id: str,
    canonical_scope: m.EvidenceScope,
    canonical_objective: str,
    target_id: m.TargetId,
    *,
    subjects: tuple[m.Subject, ...],
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
) -> _TargetReconciliation:
    """Decide the association and first-admission seed; write nothing.

    Inventory membership is computed, never solicited: every member is
    assigned to the scope's area subject, and a first-admission CQ-01 seed is
    prepared when the area has no question coverage yet. Membership
    reconciliation only; content freshness for stable members stays with the
    evidence/coverage dependency machinery.
    """
    from span.service.discovery import enumerate_target_inventory

    items = enumerate_target_inventory(
        repository_id, canonical_scope, evidence=evidence, bounds=bounds
    )
    fingerprint = m.target_inventory_fingerprint(items)
    # Store failures propagate: a missing association is None, a broken
    # store is an error, never silent absence.
    existing = store.load_target_association(repository_id, target_id)
    prior_accounts = existing.inventory_accounting if existing is not None else ()
    prior_questions = existing.target_questions if existing is not None else ()

    area = (
        _scope_area_subject(
            repository_id,
            tuple(item.evidence_ref.locator for item in items),
            subjects,
        )
        if items or prior_accounts
        else None
    )
    if area is None:
        accounts = prior_accounts
        member_refs: tuple[m.EvidenceRef, ...] = ()
    else:
        present = {item.evidence_ref.evidence_id.value for item in items}
        by_id = {item.evidence_ref.evidence_id.value: item for item in items}
        for acc in prior_accounts:
            evidence_id = acc.evidence_ref.evidence_id.value
            if evidence_id not in present:
                continue
            current_ref = by_id[evidence_id].evidence_ref
            if (
                current_ref.locator != acc.evidence_ref.locator
                or current_ref.source_kind != acc.evidence_ref.source_kind
            ):
                raise ValueError(
                    f"persisted target identity conflicts with provider "
                    f"snapshot for {evidence_id!r}; reconciliation refused"
                )
        accounts, member_refs = _deterministic_accounting(items, prior_accounts, area)

    area_subjects = tuple(
        dict.fromkeys(sid for acc in accounts for sid in acc.assigned_area_subjects)
    )
    admitted = set(area_subjects)
    target_questions = tuple(
        question for question in prior_questions if question.scope_root in admitted
    )
    seed_coverage: m.InterpretationCoverage | None = None
    if area is not None and member_refs:
        current_questions = tuple(
            coverage.question
            for coverage in store.load_all_question_coverages(
                repository_id, area.subject_id, (area.subject_id,)
            )
            if coverage.question is not None
        )
        for question in current_questions:
            if question not in target_questions:
                target_questions = target_questions + (question,)
        if not current_questions:
            seed_coverage = _first_admission_coverage(area.subject_id, member_refs)
            target_questions = target_questions + (seed_coverage.question,)

    assoc = m.TargetAssociation(
        target_id=target_id,
        repository_id=repository_id,
        target_scope=canonical_scope,
        objective=canonical_objective,
        area_subjects=area_subjects,
        target_questions=target_questions,
        inventory_accounting=accounts,
        inventory_fingerprint=fingerprint,
        observed_repository_state_fingerprint=state.state_fingerprint,
    )
    return _TargetReconciliation(
        association=assoc,
        area=area,
        seed_coverage=seed_coverage,
    )


def _write_target_reconciliation(
    store: SemanticStore,
    reconciliation: _TargetReconciliation,
) -> None:
    """Persist one decided association and its seed in a single batch."""
    store.write_index_batch(
        m.CanonicalIndexBatch(
            subjects=(
                (reconciliation.area,) if reconciliation.area is not None else ()
            ),
            target_associations=(reconciliation.association,),
            coverage=(
                (reconciliation.seed_coverage,)
                if reconciliation.seed_coverage is not None
                else ()
            ),
        )
    )


def _ensure_target_association(
    repository_id: str,
    canonical_scope: m.EvidenceScope,
    canonical_objective: str,
    target_id: m.TargetId,
    *,
    subjects: tuple[m.Subject, ...],
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
) -> m.TargetAssociation:
    """Create or reconcile the target association deterministically.

    Decision and persistence are separate: the reconciliation computes the
    association and seed, and one batch write stores them atomically.
    """
    reconciliation = _reconcile_target_association(
        repository_id,
        canonical_scope,
        canonical_objective,
        target_id,
        subjects=subjects,
        evidence=evidence,
        store=store,
        bounds=bounds,
        state=state,
    )
    _write_target_reconciliation(store, reconciliation)
    return reconciliation.association
