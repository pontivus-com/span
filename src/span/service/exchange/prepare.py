"""Resolve everything a submitted unit needs before ownership is taken."""

from __future__ import annotations

import dataclasses as _dataclasses

from span.core import model as m
from span.ports.evidence import EvidenceSource
from span.ports.store import SemanticStore
from span.ports.structural import StructuralSource
from span.core.continuations import SuspendedOperation

from span.service.interpretation import InterpretationTask
from span.service.resolution import (
    _resolve_exact_subject,
)

from span.service.exchange.identity import (
    _format_question_identity,
    _question_identity,
)


@_dataclasses.dataclass
class _TargetState:
    """Target-mode material resolved before the commit-critical section."""

    target_id: m.TargetId | None
    association: m.TargetAssociation | None
    inventory_ids: frozenset[str]
    inventory_snapshot: dict[str, m.EvidenceRef]

    @property
    def area_subjects(self) -> tuple[m.SubjectId, ...]:
        if self.association is None:
            return ()
        return self.association.area_subjects


@_dataclasses.dataclass
class _PreparedSubmission:
    """Everything resolved from the peeked record before ownership is taken."""

    task: InterpretationTask
    state: m.RepositoryState
    extra_known: tuple[m.SubjectId, ...]
    correction_question: m.SemanticQuestionScope | None
    target: _TargetState


def _expand_cited_scope(
    record: SuspendedOperation,
    task: InterpretationTask,
    result: m.SemanticInterpretationResult,
    *,
    structural: StructuralSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> list[m.SubjectId]:
    """Join cited endpoints and the run's own question root to unit scope."""
    extra_known: list[m.SubjectId] = []
    endpoints: list[m.SubjectId] = []
    for candidate in result.relationships:
        endpoints.extend((candidate.source, candidate.target))
    endpoints.extend(candidate.subject for candidate in result.claims)
    for endpoint in endpoints:
        if endpoint in task.known_subject_ids or endpoint in extra_known:
            continue
        if (
            _resolve_exact_subject(
                record.repository_id,
                endpoint,
                structural=structural,
                bounds=bounds,
            )
            is not None
        ):
            extra_known.append(endpoint)
            continue
        # Registered semantic-only subjects live in the store, not the
        # structural source: previously indexed identities join the unit
        # scope exactly like structurally resolved ones (§4.11).
        if store.load_subjects(record.repository_id, (endpoint,)):
            extra_known.append(endpoint)
    request_question = task.request.question
    if request_question is not None:
        # §4C.6D amendment (answerability, 2026-10-11, refresh seam): the
        # run's own suspended question root joins unit scope when persisted.
        # The run is already about that question (initialize_target,
        # explain, and refresh suspensions alike), so no foreign scope can
        # smuggle in through it. Store-only: never structurally guessed.
        root = request_question.scope_root
        if root not in task.known_subject_ids and root not in extra_known:
            if store.load_subjects(record.repository_id, (root,)):
                extra_known.append(root)
    return extra_known


def _resolve_correction_question(
    record: SuspendedOperation,
    result: m.SemanticInterpretationResult,
    task: InterpretationTask,
    *,
    store: SemanticStore,
    extra_known: list[m.SubjectId],
) -> m.SemanticQuestionScope | None:
    """Resolve the one nominated original question of a refresh correction.

    [design note H](docs/design-references.md#h) §6: a fallback refresh correction unit nominates exactly one
    already-persisted original question through its submitted coverage. The
    nominated subject/root join unit scope exactly like the bound root. A
    second distinct non-bound correction question, or a nomination with no
    persisted row, rejects the unit.
    """
    if record.op != "refresh":
        return None
    from span.core.validation import (
        InterpretationUnitRejected as _CorrectionRejected,
    )

    request_question = task.request.question
    nominated_by_identity: dict[tuple[str, ...], m.SemanticQuestionScope] = {}
    for submitted in result.proposed_questions:
        if request_question is not None and submitted.question == request_question:
            continue
        nominated_by_identity.setdefault(
            _question_identity(submitted.question), submitted.question
        )
    if len(nominated_by_identity) > 1:
        conflicting = "; ".join(
            _format_question_identity(question)
            for question in nominated_by_identity.values()
        )
        raise _CorrectionRejected(
            (
                "refresh correction admits exactly one persisted "
                "original question per unit; conflicting submitted "
                f"question identities: {conflicting}; submit each "
                "additional correction in its own refresh cycle",
            )
        )
    if not nominated_by_identity:
        return None
    correction_question = next(iter(nominated_by_identity.values()))
    try:
        persisted_rows = store.load_all_question_coverages(
            record.repository_id,
            correction_question.scope_root,
            (correction_question.subject,),
        )
    except Exception:
        persisted_rows = ()
    if not any(
        coverage.question is not None and coverage.question == correction_question
        for coverage in persisted_rows
    ):
        raise _CorrectionRejected(
            (
                "correction question is not an exact persisted "
                "SemanticQuestionScope; submitted question identity: "
                f"{_format_question_identity(correction_question)}; "
                "reuse exactly one identity exposed by the "
                "PendingInterpretation correction brief or "
                "status/explain question coverage",
            )
        )
    for subject_id in (correction_question.scope_root, correction_question.subject):
        if subject_id not in task.known_subject_ids and subject_id not in extra_known:
            if store.load_subjects(record.repository_id, (subject_id,)):
                extra_known.append(subject_id)
    return correction_question


def _enumerate_inventory(
    repository_id: str,
    scope: m.EvidenceScope,
    *,
    evidence: EvidenceSource,
    bounds: m.QueryBounds,
) -> tuple[frozenset[str], dict[str, m.EvidenceRef]]:
    """Enumerate current target inventory, or report it as unavailable.

    Unenumerable inventory yields no current membership rather than a partial
    or guessed one; the unit's own evidence still decides admission.
    """
    try:
        from span.service.discovery import enumerate_target_inventory

        items = enumerate_target_inventory(
            repository_id,
            scope,
            evidence=evidence,
            bounds=bounds,
        )
        return (
            frozenset(item.evidence_ref.evidence_id.value for item in items),
            {item.evidence_ref.evidence_id.value: item.evidence_ref for item in items},
        )
    except Exception:
        return frozenset(), {}


def _load_target_state(
    record: SuspendedOperation,
    result: m.SemanticInterpretationResult,
    *,
    store: SemanticStore,
    evidence: EvidenceSource,
    bounds: m.QueryBounds,
) -> _TargetState:
    """Load the association and current inventory a target unit writes into."""
    effective_target_id = (
        record.target_id if record.target_id is not None else record.request.target_id
    )
    if effective_target_id is None and not result.proposed_target_questions:
        return _TargetState(
            target_id=None,
            association=None,
            inventory_ids=frozenset(),
            inventory_snapshot={},
        )
    try:
        association = (
            store.load_target_association(record.repository_id, effective_target_id)
            if effective_target_id is not None
            else None
        )
    except Exception:
        association = None
    if effective_target_id is not None and association is None:
        from span.core.validation import InterpretationUnitRejected as _Rejected

        raise _Rejected(("target association does not resolve",))
    scope = association.target_scope if association is not None else record.target_scope
    inventory_ids, inventory_snapshot = _enumerate_inventory(
        record.repository_id,
        scope,
        evidence=evidence,
        bounds=bounds,
    )
    return _TargetState(
        target_id=effective_target_id,
        association=association,
        inventory_ids=inventory_ids,
        inventory_snapshot=inventory_snapshot,
    )


def _prepare_submission(
    record: SuspendedOperation,
    result: m.SemanticInterpretationResult,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
) -> _PreparedSubmission:
    """Resolve everything fallible from the peeked record before ownership.

    Preparation runs on peeked state and holds nothing, so any exception here
    leaves the token live with no in-flight mark to leak.
    """
    task = InterpretationTask(
        request=record.request,
        fingerprints=record.fingerprints,
        known_subject_ids=record.known_subject_ids,
        observations=(),
    )
    bounds = record.bounds
    state = structural.repository_state(record.repository_id)
    extra_known = _expand_cited_scope(
        record,
        task,
        result,
        structural=structural,
        store=store,
        bounds=bounds,
    )
    correction_question = _resolve_correction_question(
        record,
        result,
        task,
        store=store,
        extra_known=extra_known,
    )
    target = _load_target_state(
        record,
        result,
        store=store,
        evidence=evidence,
        bounds=bounds,
    )
    # §4C.6D amendment (answerability, 2026-10-11): admitted areas join unit
    # scope on target-bound submits, exactly like cited areas above —
    # membership in the just-loaded association is the authority, so no
    # resolution round-trip.
    for area in target.area_subjects:
        if area not in task.known_subject_ids and area not in extra_known:
            extra_known.append(area)
    return _PreparedSubmission(
        task=task,
        state=state,
        extra_known=tuple(extra_known),
        correction_question=correction_question,
        target=target,
    )
