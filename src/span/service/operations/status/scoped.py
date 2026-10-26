"""Span service status operation (plan §11.8; v0.6 §14 Amendment A-01).

Currency and verification over stored semantics, with hook fast
path and resume. Verbatim from ``span.service_operations``; only the
module path changed.
"""

from __future__ import annotations


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
from span.service.bounds import (
    resolve_bounds as _resolve_bounds,
)
from span.service.repository import (
    _is_initialized,
    _uninitialized_answer,
)
from span.service.requests import (
    SemanticStatusRequest,
    StatusTargetError,
)
from span.service.resolution import (
    _resolve_query_subject,
    _resolve_scope_subjects,
    resolve_scope_frontier,
)
from span.ports.structural import StaleContinuationError
from span.service.operations.status.compose import (
    _compose_status_answer,
)
from span.service.operations.status.tokens import (
    _scope_cursor,
)
from span.service.operations.status.hooks import (
    _hook_fast,
)
from span.service.operations.status.repository import (
    _repository_status_page,
)
from span.service.operations.status.target import (
    _target_status_answer,
)


def _resolve_status_subjects(
    repository_id: str,
    target: m.SubjectSelector | m.EvidenceScope,
    *,
    structural: StructuralSource,
    store: SemanticStore,
    evidence: EvidenceSource,
    bounds: m.QueryBounds,
) -> tuple[tuple[m.Subject, ...], m.ResolutionAmbiguity, m.SubjectResolution | None]:
    """Resolve selector targets without discarding canonical candidates."""
    if isinstance(target, m.SubjectSelector):
        resolution = _resolve_query_subject(
            repository_id,
            target,
            structural=structural,
            store=store,
            bounds=bounds,
        )
        return (
            tuple(candidate.subject for candidate in resolution.candidates),
            resolution.ambiguity,
            resolution,
        )
    subjects, ambiguity = _resolve_scope_subjects(
        repository_id,
        target,
        structural=structural,
        store=store,
        bounds=bounds,
        evidence=evidence,
    )
    return subjects, ambiguity, None


def _unresolved_status_answer(
    repository_id: str,
    target: m.SubjectSelector | m.EvidenceScope,
    resolution: m.SubjectResolution | None,
    *,
    state: m.RepositoryState,
    bounds: m.QueryBounds,
) -> m.SemanticAnswer:
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
        answer_id=_answer_id("stt", repository_id, "scope"),
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


def status(
    request: SemanticStatusRequest,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationPort,
    authority_seeds: tuple[m.EvidenceRef, ...] = (),
) -> m.SemanticAnswer | m.HookStatusNotice:
    """Currency operation (plan §11.8; [design note I](docs/design-references.md#i) S2 observational).

    NORMAL performs the full bounded read-only status operation over
    existing knowledge plus live freshness qualifications. It never
    initiates interpretation, allocates continuations, or persists
    freshness. Unexamined subjects return explicit missing coverage
    with next-operation guidance. HOOK_FAST is read-only lifecycle
    observation returning a compact notice — never suspension, never
    writes. Claim/relationship targets resolve through the §5.5 ref
    lookup; answer envelopes are never persisted (StatusTargetError).

    Paging (plan I-39): `page_token` carries per-list offsets redeemed
    for single-subject and ref targets. A no-target request pages the
    persisted semantic-subject frontier; it never enumerates structural
    subjects.
    """
    bounds = _resolve_bounds(
        request.bounds, hook=request.mode is m.StatusMode.HOOK_FAST
    )
    if isinstance(request.target, m.TargetId):
        return _status_campaign(
            request,
            structural=structural,
            evidence=evidence,
            store=store,
            bounds=bounds,
            continuations=continuations,
        )
    if request.mode is m.StatusMode.HOOK_FAST:
        if isinstance(request.target, (m.ClaimRef, m.RelationshipRef)):
            # The hook contract observes subject selectors and evidence scopes;
            # a claim or relationship reference is not a subject scope.
            raise StatusTargetError(
                "hook status takes a subject selector or evidence scope, "
                "not a claim or relationship reference"
            )
        return _hook_fast(
            request.repository_id,
            request.target,
            structural=structural,
            evidence=evidence,
            store=store,
            bounds=bounds,
        )
    if isinstance(request.target, (m.ClaimRef, m.RelationshipRef)):
        return _status_reference(
            request,
            structural=structural,
            evidence=evidence,
            store=store,
            bounds=bounds,
            continuations=continuations,
        )
    state = structural.repository_state(request.repository_id)
    if not _is_initialized(request.repository_id, store=store):
        return _uninitialized_answer(
            m.SemanticIntent.STATUS, request.repository_id, bounds, state
        )
    if request.target is None:
        return _repository_status_page(
            request,
            evidence=evidence,
            store=store,
            bounds=bounds,
            state=state,
            continuations=continuations,
        )
    subjects, ambiguity, resolution = _resolve_status_subjects(
        request.repository_id,
        request.target,
        structural=structural,
        store=store,
        evidence=evidence,
        bounds=bounds,
    )
    if ambiguity is not m.ResolutionAmbiguity.RESOLVED or not subjects:
        return _unresolved_status_answer(
            request.repository_id,
            request.target,
            resolution,
            state=state,
            bounds=bounds,
        )
    # S2 §5.2 observational status: never suspend, never persist.
    # Unexamined subjects return explicit missing coverage with
    # next-operation guidance from _compose_status_answer; absent,
    # ambiguous, unexamined, stale, and unverifiable stay distinct.
    if isinstance(request.target, m.EvidenceScope):
        return _status_scope_page(
            request,
            structural=structural,
            evidence=evidence,
            store=store,
            bounds=bounds,
            state=state,
            continuations=continuations,
        )
    return _compose_status_answer(
        request.repository_id,
        subjects,
        structural=structural,
        evidence=evidence,
        store=store,
        bounds=bounds,
        state=state,
        continuations=continuations,
        page_token=request.page_token,
    )


def _status_campaign(
    request: SemanticStatusRequest,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    continuations: ContinuationPort,
) -> m.SemanticAnswer:
    """Campaign readback is a NORMAL-only mode over one target handle."""
    if request.mode is m.StatusMode.HOOK_FAST:
        raise StatusTargetError("campaign status requires StatusMode.NORMAL")
    assert isinstance(request.target, m.TargetId)
    state = structural.repository_state(request.repository_id)
    if not _is_initialized(request.repository_id, store=store):
        return _uninitialized_answer(
            m.SemanticIntent.STATUS,
            request.repository_id,
            bounds,
            state,
        )
    return _target_status_answer(
        request.repository_id,
        request.target,
        evidence=evidence,
        store=store,
        bounds=bounds,
        state=state,
        continuations=continuations,
    )


def _status_reference(
    request: SemanticStatusRequest,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    continuations: ContinuationPort,
) -> m.SemanticAnswer:
    """A claim or relationship target resolves to its owning subject."""
    assert isinstance(request.target, (m.ClaimRef, m.RelationshipRef))
    try:
        (item,) = store.load_by_refs(request.repository_id, (request.target,))
    except ValueError as exc:
        raise StatusTargetError(str(exc)) from None
    state = structural.repository_state(request.repository_id)
    if not _is_initialized(request.repository_id, store=store):
        return _uninitialized_answer(
            m.SemanticIntent.STATUS,
            request.repository_id,
            bounds,
            state,
        )
    sid = item.subject if isinstance(item, m.SemanticClaim) else item.source
    subjects = store.load_subjects(request.repository_id, (sid,))
    if not subjects:
        raise StatusTargetError("referenced subject is not indexed")
    return _compose_status_answer(
        request.repository_id,
        subjects,
        structural=structural,
        evidence=evidence,
        store=store,
        bounds=bounds,
        state=state,
        continuations=continuations,
        page_token=request.page_token,
    )


def _compose_scope_window(
    request: SemanticStatusRequest,
    window: tuple[m.Subject, ...],
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    continuations: ContinuationPort,
    item_cursor: tuple[int, int, int],
    frontier_total: int,
    frontier_offset: int,
    frontier: str,
) -> m.SemanticAnswer:
    """One page of the exact scope, carrying its composite cursor."""
    assert isinstance(request.target, m.EvidenceScope)
    return _compose_status_answer(
        request.repository_id,
        window,
        structural=structural,
        evidence=evidence,
        store=store,
        bounds=bounds,
        state=state,
        continuations=continuations,
        page_token=request.page_token,
        scope=request.target,
        item_cursor=item_cursor,
        frontier_total=frontier_total,
        frontier_offset=frontier_offset,
        frontier=frontier,
    )


def _status_scope_page(
    request: SemanticStatusRequest,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    continuations: ContinuationPort,
) -> m.SemanticAnswer:
    """Page the exact scope frontier, cutting to one subject when needed."""
    assert isinstance(request.target, m.EvidenceScope)
    frontier_offset, claims_skip, rels_skip, questions_skip = _scope_cursor(
        request.page_token
    )
    item_cursor = (claims_skip, rels_skip, questions_skip)
    subjects, total, fingerprint = resolve_scope_frontier(
        request.repository_id,
        request.target,
        structural=structural,
        evidence=evidence,
        store=store,
        bounds=bounds,
        offset=frontier_offset,
    )
    if any(item_cursor):
        # A resumed item page names the subject the previous page stopped
        # inside; the frontier may not move until its lists are exhausted.
        if not subjects:
            raise StaleContinuationError(
                "stale listing continuation: the subject at this offset no "
                "longer exists; restart the listing from page one with "
                "page_token omitted"
            )
        window = subjects[:1]
    else:
        window = subjects
    answer = _compose_scope_window(
        request,
        window,
        structural=structural,
        evidence=evidence,
        store=store,
        bounds=bounds,
        state=state,
        continuations=continuations,
        item_cursor=item_cursor,
        frontier_total=total,
        frontier_offset=frontier_offset,
        frontier=fingerprint,
    )
    if len(window) > 1 and _page_cut_unresumable_items(answer):
        # A page that has to cut its own items cannot carry a cursor for them
        # while it also advances the frontier. Return one subject instead, so
        # the item position has somewhere to live.
        return _compose_scope_window(
            request,
            window[:1],
            structural=structural,
            evidence=evidence,
            store=store,
            bounds=bounds,
            state=state,
            continuations=continuations,
            item_cursor=(0, 0, 0),
            frontier_total=total,
            frontier_offset=frontier_offset,
            frontier=fingerprint,
        )
    return answer


def _page_cut_unresumable_items(answer: m.SemanticAnswer) -> bool:
    """Did this page cut content that a multi-subject cursor cannot name?

    A frontier cursor names a subject position. Only an item cursor names a
    claim, relationship, or question offset, and it can do that for exactly
    one subject. A page that cut anything but the frontier therefore has to
    shrink to one subject before its cursor can be honest.
    """
    bound = answer.bound_info
    if not bound.truncated:
        return False
    return bound.truncated_category not in (None, "semantic_subjects")
