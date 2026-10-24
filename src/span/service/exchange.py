"""Span service agent-exchange coordination (plan §11.12; v0.6 §14 Amendment A-01).

Interpretation submission and resume dispatch across the owning
operation modules. Owns no semantic predicate: validates via ``core``
and rebuilds answers via the owning op composers. Verbatim from
``span.service_operations``; only the module path changed.
"""

from __future__ import annotations

from span.core import model as m
from span.ports.evidence import EvidenceSource
from span.ports.interpretation import InterpretationUnavailable
from span.ports.interpretation import PendingInterpretation
from span.ports.store import SemanticStore
from span.ports.structural import StructuralSource
from span.shell.agent_exchange.continuations import ContinuationStore

from span.service.discovery import (
    _coverage_for_task,
)
from span.service.interpretation import (
    InterpretationTask,
    _materialize_unit,
    _next_baseline_pending,
    _suspend,
    _suspend_baseline_pending,
    prepare_interpretation_task,
)
from span.service.operations.authority import (
    _compose_authority_answer,
)
from span.service.operations.explain import (
    _compose_explain_answer,
)
from span.service.operations.impact import (
    _compose_impact_answer,
)
from span.service.operations.initialize_target import (
    _next_target_pending,
)
from span.service.operations.refresh import (
    _compose_refresh_answer,
)
from span.service.operations.trace import (
    _resume_trace,
)
from span.service.questions import (
    _stale_question_scopes,
)
from span.service.requests import (
    ChangeKind,
)
from span.service.resolution import (
    _resolve_exact_subject,
)

__all__ = [
    "submit_interpretation",
]


def _format_question_identity(question: m.SemanticQuestionScope) -> str:
    """Render the complete canonical question identity for diagnostics.

    Pure formatting over the same identity fields used by
    ``_question_identity``: no hashing, normalization, or paraphrase
    equivalence.
    """
    return (
        "("
        f"scope_root.repository_id={question.scope_root.repository_id}, "
        f"scope_root.subject_kind={question.scope_root.subject_kind.value}, "
        f"scope_root.canonical_locator="
        f"{question.scope_root.canonical_locator}, "
        f"subject.repository_id={question.subject.repository_id}, "
        f"subject.subject_kind={question.subject.subject_kind.value}, "
        f"subject.canonical_locator="
        f"{question.subject.canonical_locator}, "
        f"question_class={question.question_class.value}, "
        f"question_slice={question.question_slice}"
        ")"
    )


def submit_interpretation(
    continuation: str,
    result: m.SemanticInterpretationResult,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationStore,
) -> m.SemanticAnswer | PendingInterpretation:
    """Accept an agent's typed result and resume the operation (§11.12;
    Addendum H §4).

    Unknown or expired continuations yield InterpretationUnavailable
    at peek (the agent re-issues the original operation,
    idempotently); a token taken by a concurrent submitter yields it at
    acquire. Preparation runs on peeked state without
    holding ownership; single-commit ownership is acquired only for
    the commit-critical section (materialize + claim). Validation
    failure retains the live continuation; only a
    successful ``write_index_batch`` consumes it. Refresh resumes
    across remaining subjects, suspending again while affected work
    remains.
    """
    record = continuations.peek(continuation)
    if record is None:
        raise InterpretationUnavailable(
            f"unknown, expired, or in-flight continuation: {continuation}. Re-run the original operation; this token cannot be recovered."
        )
    bounds = record.bounds
    task = InterpretationTask(
        request=record.request,
        fingerprints=record.fingerprints,
        known_subject_ids=record.known_subject_ids,
        observations=(),
    )
    state = structural.repository_state(record.repository_id)
    extra_known: list[m.SubjectId] = []
    endpoints = []
    for candidate in result.relationships:
        endpoints.extend((candidate.source, candidate.target))
    endpoints.extend(candidate.subject for candidate in result.claims)
    # Addendum E §4C.4/E-13B/C: first admission of an already-persisted
    # area is a valid mapping-only submission. Assigned area subjects that
    # already resolve in the store join the unit scope exactly like
    # claim/relationship endpoints, so validation does not reject reusable
    # existing coverage as an unknown target area.
    for acc in result.proposed_target_inventory_accounting:
        endpoints.extend(acc.assigned_area_subjects)
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
    # Addendum H §6: a fallback refresh correction unit nominates exactly
    # one already-persisted original question through its submitted
    # coverage. The nominated subject/root join unit scope exactly like
    # the bound root above. A second distinct non-bound correction
    # question, or a nomination with no persisted row, rejects the unit.
    correction_question: m.SemanticQuestionScope | None = None
    if record.op == "refresh":
        from span.core.validation import (
            InterpretationUnitRejected as _CorrectionRejected,
        )

        def _question_identity(
            question: m.SemanticQuestionScope,
        ) -> tuple[str, ...]:
            return (
                question.scope_root.repository_id,
                question.scope_root.subject_kind.value,
                question.scope_root.canonical_locator,
                question.subject.subject_kind.value,
                question.subject.canonical_locator,
                question.question_class.value,
                question.question_slice,
            )

        nominated_by_identity: dict[tuple[str, ...], m.SemanticQuestionScope] = {}
        for submitted in result.proposed_questions:
            if request_question is not None and submitted.question == request_question:
                continue
            nominated_by_identity.setdefault(
                _question_identity(submitted.question), submitted.question
            )
        if len(nominated_by_identity) > 1:
            submitted = "; ".join(
                _format_question_identity(question)
                for question in nominated_by_identity.values()
            )
            raise _CorrectionRejected(
                (
                    "refresh correction admits exactly one persisted "
                    "original question per unit; conflicting submitted "
                    f"question identities: {submitted}; submit each "
                    "additional correction in its own refresh cycle",
                )
            )
        if nominated_by_identity:
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
                cov.question is not None and cov.question == correction_question
                for cov in persisted_rows
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
            for sid in (correction_question.scope_root, correction_question.subject):
                if sid not in task.known_subject_ids and sid not in extra_known:
                    if store.load_subjects(record.repository_id, (sid,)):
                        extra_known.append(sid)
    effective_target_id = (
        record.target_id if record.target_id is not None else task.request.target_id
    )
    has_target_proposals = bool(
        result.proposed_target_inventory_accounting or result.proposed_target_questions
    )
    target_assoc: m.TargetAssociation | None = None
    inventory_ids: frozenset[str] = frozenset()
    inventory_snapshot: dict[str, m.EvidenceRef] = {}
    target_items: tuple[m.EvidenceInventoryItem, ...] = (
        task.request.target_inventory_items
    )
    if effective_target_id is not None or has_target_proposals:
        try:
            target_assoc = (
                store.load_target_association(record.repository_id, effective_target_id)
                if effective_target_id is not None
                else None
            )
        except Exception:
            target_assoc = None
        if effective_target_id is not None and target_assoc is None:
            from span.core.validation import InterpretationUnitRejected as _Rejected

            raise _Rejected(("target association does not resolve",))
        scope_for_inventory = (
            target_assoc.target_scope
            if target_assoc is not None
            else record.target_scope
        )
        try:
            from span.service.discovery import enumerate_target_inventory

            inv_items = enumerate_target_inventory(
                record.repository_id,
                scope_for_inventory,
                evidence=evidence,
                bounds=bounds,
            )
            inventory_ids = frozenset(
                item.evidence_ref.evidence_id.value for item in inv_items
            )
            inventory_snapshot = {
                item.evidence_ref.evidence_id.value: item.evidence_ref
                for item in inv_items
            }
        except ValueError:
            inventory_ids = frozenset()
            inventory_snapshot = {}
        except Exception:
            inventory_ids = frozenset()
            inventory_snapshot = {}
        if target_assoc is not None:
            # §4C.6D amendment (answerability, 2026-10-11): admitted areas
            # join unit scope on target-bound submits, exactly like
            # mapping-assigned areas above — membership in the just-loaded
            # association is the authority, so no resolution round-trip.
            for area in target_assoc.area_subjects:
                if area not in task.known_subject_ids and area not in extra_known:
                    extra_known.append(area)
    # Commit-critical section: acquire single-commit ownership only
    # here, after all fallible preparation. Preparation above ran on
    # peeked state and holds nothing, so any exception there leaves the
    # token live with no in-flight mark to leak. From here to the claim
    # below is release-on-failure; only the claim path leaves non-live.
    record = continuations.acquire(continuation)
    if record is None:
        raise InterpretationUnavailable(
            f"unknown, expired, or in-flight continuation: {continuation}. Re-run the original operation; this token cannot be recovered."
        )
    try:
        _materialize_unit(
            task,
            result,
            store=store,
            evidence=evidence,
            state=state,
            extra_known_subjects=tuple(extra_known),
            coverage=_coverage_for_task(
                record.repository_id,
                tuple(s.subject_id for s in task.request.subjects),
                evidence=evidence,
                seeds=record.seeds,
                question=task.request.question,
                discovery_scope=task.request.discovery_scope,
            ),
            declared_complete=record.declared_complete,
            retire_scope=tuple(s.subject_id for s in task.request.subjects),
            target_id=effective_target_id,
            target_inventory_items=target_items,
            target_association=target_assoc,
            current_inventory_ids=inventory_ids,
            current_inventory_snapshot=inventory_snapshot,
            correction_question=correction_question,
        )
    except BaseException:
        continuations.release(continuation)
        raise
    # Successful commit consumes the token exactly once, before the
    # answer/next pending is exposed. Post-commit composition failure
    # therefore recovers via idempotent original-operation re-issue,
    # never via this continuation.
    continuations.claim(continuation)
    if record.op == "initialize_target":
        if effective_target_id is not None:
            return _next_target_pending(
                record.repository_id,
                record.remaining,
                record.scope,
                objective=record.objective,
                structural=structural,
                evidence=evidence,
                store=store,
                bounds=bounds,
                state=state,
                authority_seeds=record.seeds,
                continuations=continuations,
                target_scope=record.target_scope,
                target_id=record.target_id,
            )
        next_cov = _next_baseline_pending(
            record.repository_id,
            record.subject,
            store=store,
            bounds=bounds,
        )
        if next_cov is not None:
            return _suspend_baseline_pending(
                record.repository_id,
                record.subject,
                next_cov,
                structural=structural,
                evidence=evidence,
                store=store,
                bounds=bounds,
                state=state,
                seeds=record.seeds,
                resolution=record.resolution,
                continuations=continuations,
                op="initialize_target",
                scope=record.scope,
                remaining=record.remaining,
                objective=record.objective,
                target_scope=record.target_scope,
                target_id=record.target_id,
            )
        return _next_target_pending(
            record.repository_id,
            record.remaining,
            record.scope,
            objective=record.objective,
            structural=structural,
            evidence=evidence,
            store=store,
            bounds=bounds,
            state=state,
            authority_seeds=record.seeds,
            continuations=continuations,
            target_scope=record.target_scope,
            target_id=record.target_id,
        )
    if record.op == "refresh" and record.remaining:
        nxt, rest = record.remaining[0], record.remaining[1:]
        nxt_stale = _stale_question_scopes(
            record.repository_id,
            nxt,
            store=store,
            evidence=evidence,
            bounds=bounds,
            suspended=continuations.live_question_keys(),
        )
        nxt_scope = nxt_stale[0] if nxt_stale else None
        nxt_task = prepare_interpretation_task(
            record.repository_id,
            nxt,
            structural=structural,
            evidence=evidence,
            bounds=bounds,
            state=state,
            authority_seeds=record.seeds,
            operation_intent=m.SemanticIntent.STATUS,
            question_slice=(
                nxt_scope.question_slice
                if nxt_scope is not None
                else nxt.subject_id.canonical_locator
            ),
            store=store,
            scope_root=(
                nxt_scope.scope_root if nxt_scope is not None else nxt.subject_id
            ),
            question_class=(
                nxt_scope.question_class if nxt_scope is not None else None
            ),
            materiality_basis=(
                nxt_scope.materiality_basis if nxt_scope is not None else ""
            ),
        )
        return _suspend(
            op="refresh",
            repository_id=record.repository_id,
            subject=nxt,
            task=nxt_task,
            seeds=record.seeds,
            bounds=bounds,
            state=state,
            resolution=None,
            scope=record.scope,
            remaining=rest,
            changed=record.changed,
            continuations=continuations,
            operation_intent="STATUS",
            question_slice=nxt_task.request.question_slice,
            declared_complete=True,
        )
    if record.op == "explain":
        if record.establish_baseline:
            nxt_cov = _next_baseline_pending(
                record.repository_id,
                record.subject,
                store=store,
                bounds=bounds,
            )
            if nxt_cov is not None:
                return _suspend_baseline_pending(
                    record.repository_id,
                    record.subject,
                    nxt_cov,
                    structural=structural,
                    evidence=evidence,
                    store=store,
                    bounds=bounds,
                    state=state,
                    seeds=record.seeds,
                    resolution=record.resolution,
                    continuations=continuations,
                )
        _qkey = ""
        if record.request.question is not None:
            _qkey = (
                f"{record.request.question.question_class.value}:"
                f"{record.request.question.question_slice}"
            )
        return _compose_explain_answer(
            record.repository_id,
            record.subject,
            record.resolution,
            structural=structural,
            evidence=evidence,
            store=store,
            bounds=bounds,
            state=state,
            scope_root=record.subject.subject_id,
            question_key=_qkey,
        )
    if record.op == "authority":
        _qkey = ""
        if record.request.question is not None:
            _qkey = (
                f"{record.request.question.question_class.value}:"
                f"{record.request.question.question_slice}"
            )
        return _compose_authority_answer(
            record.repository_id,
            record.subject,
            record.resolution,
            structural=structural,
            evidence=evidence,
            store=store,
            bounds=bounds,
            state=state,
            question_key=_qkey,
        )
    if record.op == "trace":
        return _resume_trace(
            record,
            structural=structural,
            evidence=evidence,
            store=store,
            bounds=bounds,
            state=state,
            continuations=continuations,
        )
    if record.op == "impact":
        target = record.scope[0] if record.scope else record.subject
        resumed = record.suspended
        if record.subject.subject_id not in resumed:
            resumed = resumed + (record.subject.subject_id,)
        return _compose_impact_answer(
            record.repository_id,
            target,
            record.resolution,
            structural=structural,
            evidence=evidence,
            store=store,
            bounds=bounds,
            state=state,
            change_kind=(
                ChangeKind(record.change_kind)
                if record.change_kind is not None
                else ChangeKind.BEHAVIOR
            ),
            change_description=record.change_description,
            affected_assertions=record.affected_assertions,
            seeds=record.seeds,
            suspended=resumed,
            continuations=continuations,
            question_selection=record.question_selection,
            root_question=record.root_question,
        )
    return _compose_refresh_answer(
        record.repository_id,
        record.scope,
        structural=structural,
        evidence=evidence,
        store=store,
        bounds=bounds,
        state=state,
        changed=record.changed,
    )
