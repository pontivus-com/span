"""Span service status operation (plan §11.8; v0.6 §14 Amendment A-01).

Currency and verification over stored semantics, with hook fast
path and resume. Verbatim from ``span.service_operations``; only the
module path changed.
"""

from __future__ import annotations


from span.core import model as m
from span.ports.evidence import EvidenceSource
from span.ports.store import SemanticStore
from span.ports.continuation import ContinuationPort
from span.core.continuations import SuspendedOperation

from span.service.questions import (
    effective_question_view,
    live_question_requirement,
    match_live_question,
)


def _selector_text(selector: m.SubjectSelector) -> str:
    if selector.exact_subject_id is not None:
        return selector.exact_subject_id.canonical_locator
    if selector.name_or_locator is not None:
        return selector.name_or_locator
    return "the stored target"


def _recovery_detail(recovery: m.QuestionRecovery) -> tuple[str, str]:
    """Name the operation and the inputs that distinguish this recipe."""
    if isinstance(recovery, m.ExplainReplay):
        return (
            "explain",
            f"target '{_selector_text(recovery.target)}', "
            f"establish_baseline={str(recovery.establish_baseline).lower()}",
        )
    if isinstance(recovery, m.ImpactReplay):
        change = recovery.proposed_change
        detail = (
            f"target '{_selector_text(recovery.target)}', "
            f"change_kind={change.change_kind.value}"
        )
        if change.change_description:
            detail = f"{detail}, change_description={change.change_description!r}"
        return "impact", detail
    if isinstance(recovery, m.TraceReplay):
        if recovery.relationship_filter is None:
            filter_text = "ALL"
        elif not recovery.relationship_filter:
            filter_text = "NONE"
        else:
            filter_text = ",".join(kind.value for kind in recovery.relationship_filter)
        return (
            "trace",
            f"target '{_selector_text(recovery.target)}', "
            f"direction={recovery.direction.value}, "
            f"relationship_filter={filter_text}, "
            f"boundary_only={str(recovery.boundary_only).lower()}",
        )
    if isinstance(recovery, m.AuthorityReplay):
        return "authority", f"target '{_selector_text(recovery.target)}'"
    raise AssertionError(f"unknown recovery carrier: {type(recovery).__name__}")


def _pending_exchange_requirements(
    views: tuple[m.SemanticQuestionCoverageView, ...],
    continuations: ContinuationPort,
    *,
    recovery_operation: str | None = None,
) -> tuple[m.ResolutionRequirement, ...]:
    """Project persisted pending questions against live exchange records."""
    records = continuations.live_records()
    requirements: list[m.ResolutionRequirement] = []
    for view in views:
        if view.effective_disposition is not m.SemanticQuestionDisposition.PENDING:
            continue
        question = view.question
        live = match_live_question(records, question)
        if live is not None:
            requirements.append(live_question_requirement(live))
            continue
        subject = question.subject.canonical_locator
        if view.recovery is not None:
            operation, detail = _recovery_detail(view.recovery)
            description = (
                f"{question.question_class.value} '{question.question_slice}' "
                f"for '{subject}' has no live continuation in the current "
                f"continuation store; re-run {operation} with the persisted "
                f"recovery inputs ({detail}); do not synthesize a continuation"
            )
        elif recovery_operation is not None:
            description = (
                f"{question.question_class.value} '{question.question_slice}' "
                f"for '{subject}' has no live continuation in the current "
                f"continuation store; re-run the original {recovery_operation} "
                "request with the same target inputs; do not synthesize a "
                "continuation"
            )
        else:
            description = (
                f"{question.question_class.value} '{question.question_slice}' "
                f"for '{subject}' has no live continuation in the current "
                "continuation store and no recorded originating operation; "
                "recover it with refresh on this subject under the persisted "
                "question identity; do not synthesize a continuation"
            )
        requirements.append(
            m.ResolutionRequirement(
                kind=m.ResolutionKind.INCOMPLETE_SEMANTIC_SCOPE,
                subject_or_claim=question.subject,
                description=description,
                supporting_context=(),
            )
        )
    return tuple(requirements)


def _live_question_records(
    repository_id: str,
    subjects: tuple[m.Subject, ...] | None,
    continuations: ContinuationPort,
) -> tuple[SuspendedOperation, ...]:
    """Return live semantic records for the requested status scope."""
    subject_ids = (
        None if subjects is None else {subject.subject_id for subject in subjects}
    )
    return tuple(
        record
        for record in continuations.live_records()
        if record.repository_id == repository_id
        and record.request.question is not None
        and (subject_ids is None or record.request.question.subject in subject_ids)
    )


def _live_subject_requirements(
    repository_id: str,
    subjects: tuple[m.Subject, ...],
    continuations: ContinuationPort,
) -> tuple[m.ResolutionRequirement, ...]:
    """Project live question work even before its first persisted row."""
    return tuple(
        live_question_requirement(record)
        for record in _live_question_records(repository_id, subjects, continuations)
    )


def _repository_live_requirements(
    repository_id: str,
    continuations: ContinuationPort,
) -> tuple[m.ResolutionRequirement, ...]:
    """Expose first-time live semantic work in repository status."""
    return tuple(
        live_question_requirement(record)
        for record in _live_question_records(repository_id, None, continuations)
    )


def _project_pending_requirements(
    requirements: tuple[m.ResolutionRequirement, ...],
    pending_requirements: tuple[m.ResolutionRequirement, ...],
) -> tuple[m.ResolutionRequirement, ...]:
    """Replace generic pending continuation wording with exact recovery."""
    by_subject: dict[m.SubjectId, list[m.ResolutionRequirement]] = {}
    for requirement in pending_requirements:
        if isinstance(requirement.subject_or_claim, m.SubjectId):
            by_subject.setdefault(requirement.subject_or_claim, []).append(requirement)
    if not by_subject:
        return requirements

    kept: list[m.ResolutionRequirement] = []
    replaced: set[m.SubjectId] = set()
    for requirement in requirements:
        subject = requirement.subject_or_claim
        if not isinstance(subject, m.SubjectId):
            kept.append(requirement)
            continue
        pending = by_subject.get(subject)
        generic = pending is not None and (
            requirement.kind is m.ResolutionKind.INCOMPLETE_SEMANTIC_SCOPE
            and "continuation returned by the suspending operation"
            in requirement.description
        )
        if generic:
            assert pending is not None
            if subject not in replaced:
                replaced.add(subject)
                kept.extend(pending)
            continue
        kept.append(requirement)

    for subject, pending in by_subject.items():
        if subject not in replaced:
            kept.extend(pending)
    return tuple(dict.fromkeys(kept))


def _is_generic_live_action(
    requirement: m.ResolutionRequirement,
    entry: m.SemanticCoverageEntry,
    operations: frozenset[str],
) -> bool:
    if requirement.subject_or_claim != entry.subject:
        return False
    if (
        entry.disposition is m.SemanticCoverageDisposition.UNASSESSED
        and "explain" in operations
        and requirement.kind is m.ResolutionKind.MISSING_SEMANTIC_COVERAGE
        and "run question-local explain" in requirement.description
    ):
        return True
    if "refresh" in operations and requirement.kind in (
        m.ResolutionKind.STALE_EVIDENCE,
        m.ResolutionKind.UNVERIFIABLE_FRESHNESS,
    ):
        return "exact SubjectSelector" in requirement.description
    return (
        requirement.kind is m.ResolutionKind.INCOMPLETE_SEMANTIC_SCOPE
        and "continuation returned by the suspending operation"
        in requirement.description
    )


def _project_live_requirements(
    entries: tuple[m.SemanticCoverageEntry, ...],
    requirements: tuple[m.ResolutionRequirement, ...],
    live_records: tuple[SuspendedOperation, ...],
) -> tuple[m.ResolutionRequirement, ...]:
    """Replace generic status actions when their owning operation is live."""
    by_subject: dict[m.SubjectId, list[SuspendedOperation]] = {}
    for record in live_records:
        question = record.request.question
        assert question is not None
        by_subject.setdefault(question.subject, []).append(record)
    if not by_subject:
        return requirements

    entry_by_subject = {entry.subject: entry for entry in entries}
    kept: list[m.ResolutionRequirement] = []
    replaced: set[m.SubjectId] = set()
    for requirement in requirements:
        subject = requirement.subject_or_claim
        if not isinstance(subject, m.SubjectId):
            kept.append(requirement)
            continue
        live = by_subject.get(subject)
        entry = entry_by_subject.get(subject)
        if live and entry is not None:
            operations = frozenset(record.op for record in live)
            if _is_generic_live_action(requirement, entry, operations):
                if subject not in replaced:
                    replaced.add(subject)
                    kept.extend(live_question_requirement(record) for record in live)
                continue
        kept.append(requirement)

    for subject, live in by_subject.items():
        if subject not in replaced:
            kept.extend(live_question_requirement(record) for record in live)
    return tuple(dict.fromkeys(kept))


def _repository_pending_requirements(
    repository_id: str,
    entries: tuple[m.SemanticCoverageEntry, ...],
    *,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationPort,
) -> tuple[m.ResolutionRequirement, ...]:
    """Project pending coverage for the subjects on one repository page."""
    subjects = tuple(entry.subject for entry in entries)
    coverages = store.load_all_question_coverages(repository_id, None, ())
    views = tuple(
        effective_question_view(
            coverage,
            evidence=evidence,
            store=store,
            repository_id=repository_id,
        )
        for coverage in coverages
        if coverage.question is not None
        and coverage.question.subject in subjects
        and coverage.disposition is m.SemanticQuestionDisposition.PENDING
    )
    return _pending_exchange_requirements(views, continuations)


def _target_live_requirements(
    repository_id: str,
    target_id: m.TargetId,
    association: m.TargetAssociation,
    *,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationPort,
) -> tuple[m.ResolutionRequirement, ...]:
    """Project live target-mapping and target-question exchange state."""
    requirements: list[m.ResolutionRequirement] = []
    for record in continuations.live_records():
        if record.repository_id != repository_id or record.target_id != target_id:
            continue
        if record.request.question is not None:
            continue
        requirements.append(
            m.ResolutionRequirement(
                kind=m.ResolutionKind.INCOMPLETE_SEMANTIC_SCOPE,
                subject_or_claim=record.subject.subject_id,
                description=(
                    f"target '{target_id.value}' has a live initialize_target "
                    "unit; continue with the continuation returned by that "
                    "initialize_target call and pass it unchanged"
                ),
                supporting_context=(),
            )
        )
    pending_views: list[m.SemanticQuestionCoverageView] = []
    for question in association.target_questions:
        coverages = store.load_all_question_coverages(
            repository_id, question.scope_root, (question.subject,)
        )
        pending_views.extend(
            effective_question_view(
                coverage,
                evidence=evidence,
                store=store,
                repository_id=repository_id,
            )
            for coverage in coverages
            if coverage.question == question
            and coverage.disposition is m.SemanticQuestionDisposition.PENDING
        )
    requirements.extend(
        _pending_exchange_requirements(
            tuple(pending_views),
            continuations,
            recovery_operation="initialize_target",
        )
    )
    return tuple(dict.fromkeys(requirements))
