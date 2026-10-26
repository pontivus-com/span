"""Span service refresh operation (plan §9; v0.6 §14 Amendment A-01).

Explicit reassessment of stale/unverifiable semantics. Verbatim from
``span.service_operations``; only the module path changed.
"""

from __future__ import annotations

import dataclasses as _dataclasses

from span.core import answers as _answers
from span.core import model as m
from span.ports.evidence import EvidenceSource
from span.ports.store import SemanticStore
from span.ports.structural import StructuralSource
from span.ports.continuation import ContinuationPort

from span.service.answers import (
    _answer_id,
    ANSWER_ASSEMBLER,
)
from span.service.freshness import (
    coverage_check,
    preflight,
)
from span.service.questions import (
    _stale_question_scopes,
)
from span.service.refs import (
    _claim_ref,
    _relationship_ref,
)
from span.service.requests import (
    RefreshScopeError,
    SemanticRefreshRequest,
)
from span.service.resolution import (
    _load_subject_state,
    _resolve_query_subject,
    _resolve_scope_subjects,
)


from span.service.operations.refresh.answer import (
    _currency_note,
)


@_dataclasses.dataclass
class _RefreshScan:
    """The subjects one refresh call must reinterpret, and why."""

    affected: list[m.Subject]
    unassessed: list[m.Subject]
    changed: list[m.EvidenceDependency]
    currency_notes: list[m.ResolutionRequirement]


def _resolve_refresh_subjects(
    request: SemanticRefreshRequest,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> tuple[
    tuple[m.Subject, ...],
    m.SubjectResolution | None,
    m.ResolutionAmbiguity,
]:
    """Resolve the exact selector or the bounded scope to refresh."""
    if request.stale_only is False and not isinstance(
        request.target, m.SubjectSelector
    ):
        raise RefreshScopeError(
            "stale_only=false is an unchanged-source/current challenge "
            "and requires an exact SubjectSelector; EvidenceScope "
            "remains valid only for ordinary scoped stale refresh"
        )
    if isinstance(request.target, m.SubjectSelector):
        resolution = _resolve_query_subject(
            request.repository_id,
            request.target,
            structural=structural,
            store=store,
            bounds=bounds,
        )
        return (
            tuple(candidate.subject for candidate in resolution.candidates),
            resolution,
            resolution.ambiguity,
        )
    subjects, ambiguity = _resolve_scope_subjects(
        request.repository_id,
        request.target,
        structural=structural,
        store=store,
        bounds=bounds,
        evidence=evidence,
    )
    return subjects, None, ambiguity


def _unresolved_refresh_answer(
    repository_id: str,
    target: m.SubjectSelector | m.EvidenceScope,
    resolution: m.SubjectResolution | None,
    *,
    state: m.RepositoryState,
    bounds: m.QueryBounds,
) -> m.SemanticAnswer:
    """The answer when the requested refresh scope does not resolve."""
    requirements = (
        _answers.requirements_for_resolution(
            resolution,
            repository_id=repository_id,
            name_or_locator=(
                target.name_or_locator
                if isinstance(target, m.SubjectSelector)
                else None
            ),
        )
        if resolution is not None
        else ()
    )
    return ANSWER_ASSEMBLER.build(
        answer_id=_answer_id("rfr", repository_id, "scope"),
        intent=m.SemanticIntent.STATUS,
        repository_state=state,
        subject_resolution=resolution,
        content=m.StatusContent(
            resolved_mode=m.StatusResolvedMode.UNRESOLVED,
        ),
        evidence=(),
        resolution_requirements=requirements,
        bounds=bounds,
        withheld_category=None,
        continuation_token=None,
    )


def _expand_premise_dependents(
    repository_id: str,
    subjects: tuple[m.Subject, ...],
    stale_premise_ids: set[str],
    affected: list[m.Subject],
    *,
    store: SemanticStore,
) -> None:
    """Expand to semantically dependent subjects whose premises went stale.

    B-05/B-06: their own files may be unchanged; the stale premise still
    requires reassessment. Dependents outside the requested scope yield an
    outstanding-scope requirement rather than silent expansion.
    """
    if not stale_premise_ids:
        return
    try:
        premise_refs: list[m.ClaimRef | m.RelationshipRef] = [
            m.ClaimRef(id=m.ClaimId(premise_id))
            for premise_id in sorted(stale_premise_ids)
        ]
        try:
            dependents = store.load_premise_dependents(
                repository_id, tuple(premise_refs)
            )
        except Exception:
            dependents = ()
        # Also try relationship-shaped refs for the same ids.
        try:
            rel_refs = tuple(
                m.RelationshipRef(id=m.RelationshipId(premise_id))
                for premise_id in sorted(stale_premise_ids)
            )
            extra = store.load_premise_dependents(repository_id, rel_refs)
            dependents = tuple(dict.fromkeys((*dependents, *extra)))
        except Exception:
            pass
        if not dependents:
            return
        try:
            dep_items = store.load_by_refs(repository_id, tuple(dependents))
        except ValueError:
            dep_items = ()
        dep_subjects: set[str] = set()
        for item in dep_items:
            if isinstance(item, m.SemanticClaim):
                dep_subjects.add(item.subject.canonical_locator)
            else:
                dep_subjects.add(item.source.canonical_locator)
                dep_subjects.add(item.target.canonical_locator)
        for subject in subjects:
            if subject.subject_id.canonical_locator in dep_subjects:
                if subject not in affected:
                    affected.append(subject)
    except Exception:
        pass


def _collect_refresh_scope(
    request: SemanticRefreshRequest,
    subjects: tuple[m.Subject, ...],
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    continuations: ContinuationPort,
) -> _RefreshScan:
    """Refresh provider currency once, then classify every subject."""
    changed_deps: list[m.EvidenceDependency] = []
    # G §4.8d: exactly one provider currency refresh per refresh call, before
    # stale collection. Ordinary reads never reach here with a build; failures
    # degrade to an unresolved note, never raise.
    currency_notes: list[m.ResolutionRequirement] = []
    try:
        currency = structural.ensure_current(request.repository_id)
    except Exception:
        currency = m.Freshness(
            state=m.FreshnessState.UNVERIFIABLE,
            reason="structural provider currency check unavailable",
        )
    note = _currency_note(currency)
    if note is not None:
        currency_notes.append(note)
    stale_premise_ids: set[str] = set()
    unassessed: list[m.Subject] = []
    affected: list[m.Subject] = []
    suspended_keys = continuations.live_question_keys()
    for subject in subjects:
        admitted, is_unassessed, updates, changed = _refresh_subject_admission(
            request.repository_id,
            subject,
            stale_only=request.stale_only,
            evidence=evidence,
            store=store,
            bounds=bounds,
            suspended=suspended_keys,
        )
        if is_unassessed:
            unassessed.append(subject)
            continue
        if admitted:
            affected.append(subject)
            stale_premise_ids.update(update.semantic_id.id.value for update in updates)
            changed_deps.extend(changed)
    _expand_premise_dependents(
        request.repository_id,
        subjects,
        stale_premise_ids,
        affected,
        store=store,
    )
    return _RefreshScan(
        affected=affected,
        unassessed=unassessed,
        changed=changed_deps,
        currency_notes=currency_notes,
    )


def _refresh_subject_admission(
    repository_id: str,
    subject: m.Subject,
    *,
    stale_only: bool,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    suspended: frozenset[tuple[str, str, str, str]],
) -> tuple[bool, bool, tuple[m.FreshnessUpdate, ...], tuple[m.EvidenceDependency, ...]]:
    """Classify one subject for refresh without creating first coverage."""
    claims, relationships, _, _ = _load_subject_state(
        repository_id,
        subject.subject_id,
        store=store,
        bounds=bounds,
    )
    ids: tuple[m.ClaimRef | m.RelationshipRef, ...] = tuple(
        _claim_ref(c) for c in claims
    ) + tuple(_relationship_ref(r) for r in relationships)
    stale_questions = _stale_question_scopes(
        repository_id,
        subject,
        store=store,
        evidence=evidence,
        bounds=bounds,
        suspended=suspended,
    )
    try:
        coverages = store.load_all_question_coverages(
            repository_id, None, (subject.subject_id,)
        )
    except Exception:
        coverages = ()
    has_question = any(coverage.question is not None for coverage in coverages)
    if not stale_only and not has_question:
        # An explicit challenge reinterprets an existing question. Semantic
        # rows alone are not a question and must never authorize correction.
        return False, True, (), ()
    if not ids and not has_question:
        return False, True, (), ()
    dependencies = store.load_evidence_dependencies(repository_id, ids) if ids else ()
    updates = (
        preflight(
            repository_id,
            ids,
            evidence=evidence,
            store=store,
            bounds=bounds,
        )
        if ids
        else ()
    )
    coverage_updates = (
        coverage_check(
            repository_id,
            tuple(claims) + tuple(relationships),
            evidence=evidence,
            store=store,
        )
        if ids
        else ()
    )
    admitted = bool(updates or coverage_updates or stale_questions)
    if not stale_only and has_question:
        admitted = True
    changed = tuple(
        dependency
        for dependency in dependencies
        if dependency.semantic_id.id.value
        in {update.semantic_id.id.value for update in updates}
    )
    return admitted, False, updates, changed


def _correction_candidates(
    request: SemanticRefreshRequest,
    subject: m.Subject,
    *,
    store: SemanticStore,
) -> tuple[m.SemanticQuestionScope, ...]:
    """Persisted question identities an explicit challenge may nominate.

    [design note H](docs/design-references.md#h) §6: an explicit challenge with no stale scope still binds a
    fallback unit. The brief carries these identities so the agent can nominate
    exactly one already-persisted original question; the fallback binding alone
    never authorizes withdrawal of another question's outputs.
    """
    try:
        existing_coverages = store.load_all_question_coverages(
            request.repository_id,
            None,
            (subject.subject_id,),
        )
    except Exception:
        existing_coverages = ()
    seen_identities: set[tuple[str, ...]] = set()
    candidates: list[m.SemanticQuestionScope] = []
    for existing in existing_coverages:
        question = existing.question
        if question is None:
            continue
        if question.subject != subject.subject_id:
            continue
        identity = (
            question.scope_root.repository_id,
            question.scope_root.subject_kind.value,
            question.scope_root.canonical_locator,
            question.subject.subject_kind.value,
            question.subject.canonical_locator,
            question.question_class.value,
            question.question_slice,
        )
        if identity in seen_identities:
            continue
        seen_identities.add(identity)
        candidates.append(question)
    candidates.sort(
        key=lambda question: (question.question_class.value, question.question_slice)
    )
    return tuple(candidates)


def _bind_correction_brief(
    task: m.InterpretationTask,
    candidates: tuple[m.SemanticQuestionScope, ...],
) -> m.InterpretationTask:
    """Carry the challenged-question candidates and the one-nomination rule."""
    brief = task.request.brief
    return _dataclasses.replace(
        task,
        request=_dataclasses.replace(
            task.request,
            brief=_dataclasses.replace(
                brief,
                scope_boundaries=brief.scope_boundaries
                + tuple(
                    "challenged-question candidate "
                    f"{candidate.question_class.value} "
                    f"'{candidate.question_slice}' (scope root "
                    f"'{candidate.scope_root.canonical_locator}')"
                    for candidate in candidates
                ),
                submission_rules=brief.submission_rules
                + (
                    "Correction mode: nominate exactly one "
                    "already-persisted original question from the "
                    "challenged-question candidates via one "
                    "proposed_questions entry carrying that "
                    "exact scope; a second distinct non-bound "
                    "correction question rejects the unit.",
                ),
            ),
        ),
    )
