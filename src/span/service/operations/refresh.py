"""Span service refresh operation (plan §9; v0.6 §14 Amendment A-01).

Explicit reassessment of stale/unverifiable semantics. Verbatim from
``span.service_operations``; only the module path changed.
"""

from __future__ import annotations

import dataclasses as _dataclasses

from span.core import answers as _answers
from span.core import model as m
from span.ports.evidence import EvidenceSource
from span.ports.interpretation import PendingInterpretation
from span.ports.store import SemanticStore
from span.ports.structural import StructuralSource
from span.shell.agent_exchange.continuations import ContinuationStore

from span.service.answers import (
    _answer_id,
    _bound_info,
    _conflicts_for,
    _freshness_items_for,
    _select_answer_items,
)
from span.service.bounds import (
    resolve_bounds as _resolve_bounds,
)
from span.service.freshness import (
    _refresh_view,
    coverage_check,
    preflight,
)
from span.service.interpretation import (
    _suspend,
    prepare_interpretation_task,
)
from span.service.questions import (
    _question_views_for_scope,
    _stale_question_scopes,
)
from span.service.refs import (
    _claim_ref,
    _relationship_ref,
)
from span.service.repository import (
    _is_initialized,
    _uninitialized_answer,
)
from span.service.requests import (
    RefreshScopeError,
    SemanticRefreshRequest,
)
from span.service.resolution import (
    _load_subject_state,
    _resolve_scope_subjects,
)

__all__ = [
    '_compose_refresh_answer',
    'refresh',
]

def _currency_note(
    currency: m.Freshness,
) -> m.ResolutionRequirement | None:
    """Unresolved note for a non-current provider refresh (G §4.8d).

    Pure projection: CURRENT yields no note; anything else yields one
    UNVERIFIABLE_FRESHNESS requirement carrying the provider's reason.
    """
    if currency.state is m.FreshnessState.CURRENT:
        return None
    return m.ResolutionRequirement(
        kind=m.ResolutionKind.UNVERIFIABLE_FRESHNESS,
        subject_or_claim=None,
        description=(
            f"structural index not refreshed: {currency.reason}; "
            f"scope reads stay UNVERIFIABLE where index "
            f"currency matters"
        ),
        supporting_context=(),
    )


def _compose_refresh_answer(
    repository_id: str,
    subjects: tuple[m.Subject, ...],
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    changed: tuple[m.EvidenceDependency, ...] = (),
    extra_unresolved: tuple[m.ResolutionRequirement, ...] = (),
) -> m.SemanticAnswer:
    reloaded_claims: list[m.SemanticClaim] = []
    reloaded_rels: list[m.SemanticRelationship] = []
    for subject in subjects:
        claims, relationships, _, _ = _load_subject_state(
            repository_id, subject.subject_id,
            store=store, bounds=bounds,
        )
        reloaded_claims.extend(claims)
        reloaded_rels.extend(relationships)
    claims_t, rels_t = tuple(reloaded_claims), tuple(reloaded_rels)
    claims_t, rels_t = _refresh_view(
        repository_id, claims_t, rels_t,
        evidence=evidence, store=store, bounds=bounds,
    )
    conflicts_all = _conflicts_for(
        repository_id, claims_t, rels_t, store=store
    )
    kept_claims, kept_rels, kept_conf, truncated, category = (
        _select_answer_items(
            claims_t, rels_t, conflicts_all, bounds.max_results
        )
    )
    scope_paths = tuple(
        s.subject_id.canonical_locator for s in subjects
    )
    views = _question_views_for_scope(
        repository_id, None,
        tuple(s.subject_id for s in subjects),
        store=store, bounds=bounds, evidence=evidence,
    )
    content = m.StatusContent(
        readiness=m.RepositoryReadiness.READY,
        freshness_items=_freshness_items_for(kept_claims, kept_rels),
        changed_dependencies=changed,
        verification_currency=(),
        refresh_scope=m.EvidenceScope(paths=scope_paths, evidence_refs=()),
        claims=kept_claims,
        relationships=kept_rels,
        conflicts=kept_conf,
        unresolved=tuple(
            req for c in kept_claims for req in _answers.requirements_for_claim(c)
        ) + tuple(
            req for r in kept_rels
            for req in _answers.requirements_for_relationship(r)
        ) + tuple(extra_unresolved),
        question_coverage=views,
    )
    evidence_refs = tuple(ref for c in kept_claims for ref in c.evidence)
    return m.SemanticAnswer(
        answer_id=_answer_id(
            "rfr", repository_id, ",".join(scope_paths)
        ),
        intent=m.SemanticIntent.STATUS,
        repository_state=state,
        subject_resolution=None,
        content=content,
        evidence=evidence_refs,
        resolution_requirements=content.unresolved,
        bound_info=_bound_info(
            bounds,
            len(kept_claims) + len(kept_rels) + len(kept_conf),
            truncated, category, None,
        ),
    )

def refresh(
    request: SemanticRefreshRequest,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationStore,
    authority_seeds: tuple[m.EvidenceRef, ...] = (),
) -> m.SemanticAnswer | PendingInterpretation:
    """Explicit synchronization (plan §9.5, Addendum B B-06).

    Identifies stale/unverifiable dependencies — including semantic
    premise dependents via the reverse lookup — and reinterprets only
    affected semantic units. Never expands into a baseline audit.
    """
    bounds = _resolve_bounds(request.bounds, hook=False)
    state = structural.repository_state(request.repository_id)
    if not _is_initialized(request.repository_id, store=store):
        return _uninitialized_answer(
            m.SemanticIntent.STATUS, request.repository_id, bounds, state
        )
    if request.target is None:
        raise RefreshScopeError(
            "refresh needs an exact scope: pass a SubjectSelector for "
            "the stale subject or a known EvidenceScope, and use status "
            "to find the stale scope; repo-wide refresh without "
            "enumeration is rejected"
        )
    subjects, ambiguity = _resolve_scope_subjects(
        request.repository_id, request.target,
        structural=structural, store=store, bounds=bounds,
        evidence=evidence,
    )
    if ambiguity is not m.ResolutionAmbiguity.RESOLVED or not subjects:
        requirements = ()
        if ambiguity is m.ResolutionAmbiguity.AMBIGUOUS:
            requirements = (
                m.ResolutionRequirement(
                    kind=m.ResolutionKind.AMBIGUOUS_IDENTITY,
                    subject_or_claim=None,
                    description="refresh target is ambiguous",
                    supporting_context=(),
                ),
            )
        return m.SemanticAnswer(
            answer_id=_answer_id(
                "rfr", request.repository_id, "scope"
            ),
            intent=m.SemanticIntent.STATUS,
            repository_state=state,
            subject_resolution=None,
            content=m.StatusContent(),
            evidence=(),
            resolution_requirements=requirements,
            bound_info=_bound_info(bounds, 0, False, None),
        )
    affected: list[m.Subject] = []
    changed_deps: list[m.EvidenceDependency] = []
    # G §4.8d: exactly one provider currency refresh per refresh call,
    # before stale collection. Ordinary reads never reach here with a
    # build; failures degrade to an unresolved note, never raise.
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
    # Collect stale premise ids first for dependent expansion.
    stale_premise_ids: set[str] = set()
    subject_items: dict[str, tuple[
        object,
        tuple[m.ClaimRef | m.RelationshipRef, ...],
    ]] = {}
    for subject in subjects:
        claims, relationships, _, _ = _load_subject_state(
            request.repository_id, subject.subject_id,
            store=store, bounds=bounds,
        )
        ids: tuple[m.ClaimRef | m.RelationshipRef, ...] = tuple(
            _claim_ref(c) for c in claims
        ) + tuple(_relationship_ref(r) for r in relationships)
        subject_items[subject.subject_id.canonical_locator] = (
            subject, ids,
        )
        if not ids:
            affected.append(subject)
            continue
        dependencies = store.load_evidence_dependencies(
            request.repository_id, ids
        )
        updates = preflight(
            request.repository_id, ids, evidence=evidence,
            store=store, bounds=bounds,
        )
        coverage_updates = coverage_check(
            request.repository_id, tuple(claims) + tuple(relationships),
            evidence=evidence, store=store,
        )
        # B.4/B-06: stale persisted questions — including zero-result
        # OPEN/NOT_APPLICABLE whose discovery/evidence moved — mark the
        # subject affected even when no item update fired above.
        stale_questions = _stale_question_scopes(
            request.repository_id, subject,
            store=store, evidence=evidence, bounds=bounds,
            suspended=continuations.live_question_keys(),
        )
        if updates or coverage_updates or stale_questions:
            if updates:
                updated = {u.semantic_id.id.value for u in updates}
                stale_premise_ids.update(updated)
                changed_deps.extend(
                    dep for dep in dependencies
                    if dep.semantic_id.id.value in updated
                )
            affected.append(subject)
        elif not request.stale_only:
            affected.append(subject)
    # B-05/B-06: expand to semantically dependent questions whose
    # premises went stale, even when their own files are unchanged.
    if stale_premise_ids:
        try:
            premise_refs: list[m.ClaimRef | m.RelationshipRef] = []
            for pid in sorted(stale_premise_ids):
                # Kind unknown here; try both via load_by_refs shape.
                premise_refs.append(m.ClaimRef(id=m.ClaimId(pid)))
            dependents: tuple[m.ClaimRef | m.RelationshipRef, ...] = ()
            try:
                dependents = store.load_premise_dependents(
                    request.repository_id, tuple(premise_refs),
                )
            except Exception:
                dependents = ()
            # Also try relationship-shaped refs for the same ids.
            try:
                rel_refs = tuple(
                    m.RelationshipRef(id=m.RelationshipId(pid))
                    for pid in sorted(stale_premise_ids)
                )
                extra = store.load_premise_dependents(
                    request.repository_id, rel_refs,
                )
                dependents = tuple(dict.fromkeys((*dependents, *extra)))
            except Exception:
                pass
            if dependents:
                dep_ids = {d.id.value for d in dependents}
                try:
                    dep_items = store.load_by_refs(
                        request.repository_id, tuple(dependents),
                    )
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
                # Dependents outside the requested scope yield a requirement
                # via outstanding-scope rather than silent expansion.
                _ = dep_ids
        except Exception:
            pass
    if not affected:
        return _compose_refresh_answer(
            request.repository_id, subjects, structural=structural,
            evidence=evidence, store=store, bounds=bounds, state=state,
            changed=tuple(changed_deps),
            extra_unresolved=tuple(currency_notes),
        )
    first, rest = affected[0], affected[1:]
    # B.3/B-06: refresh re-examines under the persisted stale question
    # scope — never a fresh generic question and never a silent
    # baseline expansion. Only subjects with no persisted questions
    # fall back to a STATUS question-local unit.
    first_stale = _stale_question_scopes(
        request.repository_id, first,
        store=store, evidence=evidence, bounds=bounds,
        suspended=continuations.live_question_keys(),
    )
    first_scope = first_stale[0] if first_stale else None
    # Addendum H §6: an explicit challenge (`stale_only=False`) with no
    # stale scope still binds a fallback unit. The brief then carries the
    # subject's persisted question identities so the agent can nominate
    # exactly one already-persisted original question in its submission;
    # the fallback binding alone never authorizes withdrawal of another
    # question's outputs.
    correction_candidates: tuple[m.SemanticQuestionScope, ...] = ()
    if first_scope is None and not request.stale_only:
        try:
            existing_coverages = store.load_all_question_coverages(
                request.repository_id, None, (first.subject_id,),
            )
        except Exception:
            existing_coverages = ()
        seen_identities: set[tuple[str, ...]] = set()
        candidates: list[m.SemanticQuestionScope] = []
        for existing in existing_coverages:
            if existing.question is None:
                continue
            if existing.question.subject != first.subject_id:
                continue
            identity = (
                existing.question.scope_root.repository_id,
                existing.question.scope_root.subject_kind.value,
                existing.question.scope_root.canonical_locator,
                existing.question.subject.subject_kind.value,
                existing.question.subject.canonical_locator,
                existing.question.question_class.value,
                existing.question.question_slice,
            )
            if identity in seen_identities:
                continue
            seen_identities.add(identity)
            candidates.append(existing.question)
        candidates.sort(
            key=lambda q: (q.question_class.value, q.question_slice)
        )
        correction_candidates = tuple(candidates)
    task = prepare_interpretation_task(
        request.repository_id, first, structural=structural,
        evidence=evidence, bounds=bounds, state=state,
        authority_seeds=authority_seeds,
        operation_intent=m.SemanticIntent.STATUS,
        question_slice=(
            first_scope.question_slice if first_scope is not None
            else first.subject_id.canonical_locator
        ),
        store=store,
        scope_root=(
            first_scope.scope_root if first_scope is not None
            else first.subject_id
        ),
        question_class=(
            first_scope.question_class if first_scope is not None else None
        ),
        materiality_basis=(
            first_scope.materiality_basis if first_scope is not None else ""
        ),
    )
    if correction_candidates:
        brief = task.request.brief
        task = _dataclasses.replace(
            task,
            request=_dataclasses.replace(
                task.request,
                brief=_dataclasses.replace(
                    brief,
                    scope_boundaries=brief.scope_boundaries + tuple(
                        "challenged-question candidate "
                        f"{candidate.question_class.value} "
                        f"'{candidate.question_slice}' (scope root "
                        f"'{candidate.scope_root.canonical_locator}')"
                        for candidate in correction_candidates
                    ),
                    submission_rules=brief.submission_rules + (
                        "Correction mode: nominate exactly one "
                        "already-persisted original question from the "
                        "challenged-question candidates via one "
                        "proposed_question_coverages entry carrying that "
                        "exact scope; a second distinct non-bound "
                        "correction question rejects the unit.",
                    ),
                ),
            ),
        )
    return _suspend(
        op="refresh", repository_id=request.repository_id, subject=first,
        task=task, seeds=authority_seeds, bounds=bounds, state=state,
        resolution=None, scope=subjects, remaining=rest,
        changed=tuple(changed_deps), continuations=continuations,
        operation_intent="STATUS",
        question_slice=task.request.question_slice,
        declared_complete=True,
    )
