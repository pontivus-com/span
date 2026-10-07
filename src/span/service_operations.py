"""Span §11.10 service request contracts and agent-exchange operations.

Request contracts are frozen dataclasses (strict typed ingress, I-02).
Span never invokes a model or provider: when stored/current semantics
are insufficient, operations suspend with a ``PendingInterpretation``
(plan §11.12); the invoking agent submits the typed result; Span
validates/materializes and the operation resumes. Trace/status/impact
behavior arrives in its owning phase (Phase 3); transport in Phase 4.
"""

from __future__ import annotations

import enum as _enum
from dataclasses import dataclass as _dataclass

from span.core import answers as _answers
from span.core import freshness as _freshness
from span.core import model as m
from span.core import validation as _validation
from span.ports.evidence import EvidenceSource
from span.ports.interpretation import (
    InterpretationIngressFailure,
    InterpretationUnavailable,
    PendingInterpretation,
)
from span.ports.store import SemanticStore
from span.ports.structural import StructuralDirection, StructuralSource
from span.service import (
    DEFAULT_SERVICE_BOUNDS_POLICY,
    resolve_bounds as _resolve_bounds,
)
from span.shell.agent_exchange.continuations import (
    ContinuationStore,
    SuspendedOperation,
)

__all__ = [
    "ChangeKind",
    "SemanticExplainRequest",
    "SemanticImpactRequest",
    "SemanticTraceRequest",
    "SemanticAuthorityRequest",
    "SemanticStatusRequest",
    "SemanticRefreshRequest",
    "SemanticSubmitInterpretationRequest",
    "SemanticInitializeRepositoryRequest",
    "SemanticInitializeRepositoryResult",
    "AuthorityTargetError",
    "RefreshScopeError",
    "InterpretationUnitRejected",
    "preflight",
    "discover_evidence",
    "prepare_interpretation_task",
    "submit_interpretation",
    "reissue_interpretation",
    "explain",
    "authority",
    "refresh",
    "trace",
    "status",
    "impact",
    "StatusTargetError",
    "initialize_repository",
]

InterpretationUnitRejected = _validation.InterpretationUnitRejected


class ChangeKind(_enum.Enum):
    CONTRACT = "CONTRACT"
    BEHAVIOR = "BEHAVIOR"
    REPRESENTATION = "REPRESENTATION"
    OWNERSHIP = "OWNERSHIP"
    CONFIGURATION = "CONFIGURATION"
    LIFECYCLE = "LIFECYCLE"
    OTHER = "OTHER"


@_dataclass(frozen=True)
class SemanticExplainRequest:
    repository_id: str
    target: m.SubjectSelector
    bounds: m.QueryBounds


@_dataclass(frozen=True)
class SemanticImpactRequest:
    repository_id: str
    target: m.SubjectSelector
    change_kind: ChangeKind
    change_description: str | None
    bounds: m.QueryBounds


@_dataclass(frozen=True)
class SemanticTraceRequest:
    repository_id: str
    target: m.SubjectSelector
    direction: StructuralDirection
    relationship_filter: tuple[m.RelationshipKind, ...] | None
    boundary_only: bool
    bounds: m.QueryBounds


@_dataclass(frozen=True)
class SemanticAuthorityRequest:
    repository_id: str
    target: m.SubjectSelector | m.ClaimRef
    bounds: m.QueryBounds


@_dataclass(frozen=True)
class SemanticStatusRequest:
    repository_id: str
    target: (
        m.SubjectSelector
        | m.ClaimRef
        | m.RelationshipRef
        | m.AnswerRef
        | m.EvidenceScope
        | None
    )
    bounds: m.QueryBounds
    mode: m.StatusMode = m.StatusMode.NORMAL


@_dataclass(frozen=True)
class SemanticRefreshRequest:
    repository_id: str
    target: m.SubjectSelector | m.EvidenceScope | None
    bounds: m.QueryBounds
    stale_only: bool = True


@_dataclass(frozen=True)
class SemanticSubmitInterpretationRequest:
    continuation: str
    result: m.SemanticInterpretationResult


@_dataclass(frozen=True)
class SemanticInitializeRepositoryRequest:
    repository_locator: str
    structural_provider_config: str
    authority_seeds: tuple[m.EvidenceRef, ...] = ()


@_dataclass(frozen=True)
class SemanticInitializeRepositoryResult:
    repository_id: str
    readiness: m.RepositoryReadiness
    structural_source_status: str
    evidence_inventory_status: str
    semantic_store_status: str
    warnings: tuple[str, ...]
    bound_info: m.BoundInfo


class AuthorityTargetError(ValueError):
    """ClaimRef-target authority requires the Phase 3 subject-scoped
    claim lookup; Phase 1 serves selector targets."""


class RefreshScopeError(ValueError):
    """Repo-wide refresh (target None) requires indexed-subject
    enumeration, which arrives with the Phase 3 query surface."""


def _answer_id(prefix: str, request_part: str, subject_part: str) -> m.AnswerId:
    import hashlib as _hashlib

    digest = _hashlib.sha256(
        f"{prefix}:{request_part}:{subject_part}".encode("utf-8")
    ).hexdigest()[:16]
    return m.AnswerId(f"{prefix}-{digest}")


def preflight(
    repository_id: str,
    semantic_ids: tuple[m.ClaimId | m.RelationshipId, ...],
    *,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> tuple[m.FreshnessUpdate, ...]:
    """Query freshness preflight (plan §9.2 steps 1–4).

    Loads evidence dependencies, obtains current fingerprints, compares
    against stored supporting state, classifies each item, and persists
    non-current classifications. Returns the applied updates.
    """
    if not semantic_ids:
        return ()
    updates, _ = _classify_current(
        repository_id, semantic_ids, evidence=evidence,
        store=store, bounds=bounds,
    )
    if updates:
        store.mark_freshness(updates)
    return updates


def discover_evidence(
    repository_id: str,
    subject: m.Subject,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    authority_seeds: tuple[m.EvidenceRef, ...] = (),
    question_terms: tuple[str, ...] = (),
) -> m.EvidenceSelection:
    """Generic evidence discovery (plan §6.2 steps 1–6).

    Resolve (caller-supplied) → bounded structural context → directly
    referenced sources → explicit authority seeds → identity/term-anchored
    text search → §8-bounded set. Relevance only: nothing selected here
    carries authority (plan §6.1; authority is established only by §6.3
    validation in the core).
    """
    sid = subject.subject_id
    edges = structural.edges(
        repository_id, sid, (), StructuralDirection.BOTH, bounds
    )
    observations = [
        m.StructuralObservation(
            source_subject=edge.source,
            edge_kind=edge.kind,
            target_subject=edge.target,
            location=None,
            repository_state=state,
        )
        for edge in edges.items
    ]
    locations = structural.locations(repository_id, sid, bounds).items
    observations.extend(
        m.StructuralObservation(
            source_subject=sid,
            edge_kind=None,
            target_subject=None,
            location=loc.location,
            repository_state=state,
        )
        for loc in locations
    )
    selection = evidence.select_evidence(
        repository_id, sid, tuple(observations), authority_seeds, bounds
    )
    anchors = [subject.display_name, sid.canonical_locator.rsplit("/", 1)[-1]]
    anchors.extend(question_terms)
    anchors = sorted({a for a in anchors if a})
    if not anchors:
        return selection
    inventory = evidence.inventory_evidence(
        repository_id, m.EvidenceScope(paths=(), evidence_refs=()), bounds
    )
    selected = list(selection.selected_refs)
    seen = {ref.evidence_id.value for ref in selected}
    for item in inventory.items:
        if item.evidence_ref.evidence_id.value in seen:
            continue
        try:
            (unit,) = evidence.read_evidence((item.evidence_ref,), bounds)
        except ValueError:
            continue
        if any(anchor in unit.content for anchor in anchors):
            selected.append(item.evidence_ref)
            seen.add(item.evidence_ref.evidence_id.value)
        if len(selected) >= bounds.max_evidence_units:
            break
    kept = tuple(selected[: bounds.max_evidence_units])
    return m.EvidenceSelection(
        selected_refs=kept,
        bound_info=m.BoundInfo(
            requested_max_results=bounds.max_evidence_units,
            requested_max_depth=0,
            returned_results=len(kept),
            truncated=len(kept) < len(selected),
            truncated_category="discovery" if len(kept) < len(selected) else None,
            continuation_token=None,
        ),
    )


@_dataclass(frozen=True)
class InterpretationTask:
    """Prepared bounded interpretation task (Span side, pre-suspension)."""

    request: m.SemanticInterpretationRequest
    fingerprints: tuple[tuple[str, str], ...]
    known_subject_ids: tuple[m.SubjectId, ...]
    observations: tuple[m.StructuralObservation, ...]


def prepare_interpretation_task(
    repository_id: str,
    subject: m.Subject,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    authority_seeds: tuple[m.EvidenceRef, ...] = (),
) -> InterpretationTask:
    """Build the bounded task for the invoking agent (§8.3/§11.12).

    Discovers evidence, reads bounded units, and assembles the typed
    request plus the validation context inputs. Performs no
    interpretation and no persistence.
    """
    sid = subject.subject_id
    edges = structural.edges(
        repository_id, sid, (), StructuralDirection.BOTH, bounds
    )
    observations = [
        m.StructuralObservation(
            source_subject=edge.source,
            edge_kind=edge.kind,
            target_subject=edge.target,
            location=None,
            repository_state=state,
        )
        for edge in edges.items
    ]
    locations = structural.locations(repository_id, sid, bounds).items
    observations.extend(
        m.StructuralObservation(
            source_subject=sid,
            edge_kind=None,
            target_subject=None,
            location=loc.location,
            repository_state=state,
        )
        for loc in locations
    )
    selection = discover_evidence(
        repository_id, subject, structural=structural, evidence=evidence,
        bounds=bounds, state=state, authority_seeds=authority_seeds,
    )
    units = evidence.read_evidence(selection.selected_refs, bounds)
    fingerprints = tuple(
        (unit.evidence_ref.evidence_id.value, unit.content_fingerprint)
        for unit in units
    )
    known_subjects = (sid,) + tuple(
        obs.target_subject
        for obs in observations
        if obs.target_subject is not None
    ) + tuple(obs.source_subject for obs in observations)
    request = m.SemanticInterpretationRequest(
        repository_id=repository_id,
        subjects=(subject,),
        evidence_units=units,
        structural_observations=tuple(observations),
        allowed_claim_kinds=tuple(m.ClaimKind),
        allowed_relationship_kinds=tuple(m.RelationshipKind),
        identity_bindings=(sid,),
        bounds=bounds,
    )
    if len(request.subjects) > bounds.max_subjects:
        raise _validation.InterpretationUnitRejected(
            ("interpretation unit exceeds max_subjects",)
        )
    return InterpretationTask(
        request=request,
        fingerprints=fingerprints,
        known_subject_ids=known_subjects,
        observations=tuple(observations),
    )


def _validation_context_for(
    task: InterpretationTask,
    extra_known: tuple[m.SubjectId, ...] = (),
) -> _validation.ValidationContext:
    return _validation.ValidationContext(
        allowed_claim_kinds=tuple(m.ClaimKind),
        allowed_relationship_kinds=tuple(m.RelationshipKind),
        known_evidence_ids=frozenset(eid for eid, _ in task.fingerprints),
        known_subject_ids=task.known_subject_ids + extra_known,
        evidence_fingerprints=dict(task.fingerprints),
    )


def _materialize_unit(
    task: InterpretationTask,
    result: m.SemanticInterpretationResult,
    *,
    store: SemanticStore,
    state: m.RepositoryState,
    extra_known_subjects: tuple[m.SubjectId, ...] = (),
) -> None:
    """Validate and atomically materialize one submitted unit (§7.5).

    Any validation failure rejects the entire unit — no candidate-level
    salvage. Submitted content exceeding §8.4 cardinality bounds is a
    unit failure, not a silent truncation.

    ``extra_known_subjects`` are evidence-declared relationship
    endpoints the service resolved exactly through the structural
    source: resolvable identities join the unit scope (§8.4 explicitly
    related subjects); unresolvable ones stay rejected. The core rule
    itself (§4.2 run-bound scope) is unchanged.
    """
    if len(result.claims) > task.request.bounds.max_candidate_claims:
        raise _validation.InterpretationUnitRejected(
            ("interpretation unit exceeds max_candidate_claims",)
        )
    if len(result.relationships) > task.request.bounds.max_candidate_relationships:
        raise _validation.InterpretationUnitRejected(
            ("interpretation unit exceeds max_candidate_relationships",)
        )
    ctx = _validation_context_for(task, extra_known_subjects)
    failures: list[str] = []
    claims: list[m.SemanticClaim] = []
    for candidate in result.claims:
        validation = _validation.validate_candidate_claim(candidate, ctx)
        if not validation.ok:
            failures.extend(validation.diagnostics)
            continue
        claims.append(
            _validation.materialize_claim(candidate, validation, state)
        )
    relationships: list[m.SemanticRelationship] = []
    for candidate in result.relationships:
        validation = _validation.validate_candidate_relationship(candidate, ctx)
        if not validation.ok:
            failures.extend(validation.diagnostics)
            continue
        relationships.append(
            _validation.materialize_relationship(candidate, validation, state)
        )
    if failures:
        raise _validation.InterpretationUnitRejected(tuple(failures))
    fingerprints = dict(task.fingerprints)
    subject = task.request.subjects[0]
    dependencies = tuple(
        m.EvidenceDependency(
            semantic_id=item.claim_id if isinstance(item, m.SemanticClaim) else item.relationship_id,
            evidence_ref=ref,
            observed_fingerprint=fingerprints[ref.evidence_id.value],
        )
        for item in (*claims, *relationships)
        for ref in item.evidence
    )
    store.write_index_batch(
        m.CanonicalIndexBatch(
            subjects=(subject,),
            claims=tuple(claims),
            relationships=tuple(relationships),
            evidence_dependencies=dependencies,
        )
    )


def _suspend(
    *,
    op: str,
    repository_id: str,
    subject: m.Subject,
    task: InterpretationTask,
    seeds: tuple[m.EvidenceRef, ...],
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    resolution: m.SubjectResolution | None,
    scope: tuple[m.Subject, ...] = (),
    remaining: tuple[m.Subject, ...] = (),
    changed: tuple[m.EvidenceDependency, ...] = (),
    suspended: tuple[str, ...] = (),
    change_kind: str | None = None,
    change_description: str | None = None,
    trace_direction: str | None = None,
    trace_filter: tuple[m.RelationshipKind, ...] = (),
    trace_filter_set: bool = False,
    trace_boundary: bool = False,
    continuations: ContinuationStore,
) -> PendingInterpretation:
    token = continuations.pend(
        SuspendedOperation(
            op=op,
            repository_id=repository_id,
            subject=subject,
            scope=scope,
            remaining=remaining,
            changed=changed,
            resolution=resolution,
            request=task.request,
            fingerprints=task.fingerprints,
            known_subject_ids=task.known_subject_ids,
            seeds=seeds,
            bounds=bounds,
            state=state,
            suspended=suspended,
            change_kind=change_kind,
            change_description=change_description,
            trace_direction=trace_direction,
            trace_filter=trace_filter,
            trace_filter_set=trace_filter_set,
            trace_boundary=trace_boundary,
        )
    )
    return PendingInterpretation(continuation=token, request=task.request)


def submit_interpretation(
    continuation: str,
    result: m.SemanticInterpretationResult,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationStore,
) -> m.SemanticAnswer | PendingInterpretation:
    """Accept an agent's typed result and resume the operation (§11.12).

    Unknown or expired continuations yield InterpretationUnavailable
    (the agent re-issues the original operation, idempotently).
    Validation failure rejects the unit with no reissue (§7.5); the
    continuation is already consumed. Refresh resumes across remaining
    subjects, suspending again while affected work remains.
    """
    record = continuations.claim(continuation)
    if record is None:
        raise InterpretationUnavailable(
            f"unknown or expired continuation: {continuation}"
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
    for candidate in result.relationships:
        for endpoint in (candidate.source, candidate.target):
            if endpoint in task.known_subject_ids or endpoint in extra_known:
                continue
            if (
                _resolve_exact_subject(
                    record.repository_id, endpoint,
                    structural=structural, bounds=bounds,
                )
                is not None
            ):
                extra_known.append(endpoint)
    _materialize_unit(
        task, result, store=store, state=state,
        extra_known_subjects=tuple(extra_known),
    )
    if record.op == "refresh" and record.remaining:
        nxt, rest = record.remaining[0], record.remaining[1:]
        nxt_task = prepare_interpretation_task(
            record.repository_id, nxt, structural=structural,
            evidence=evidence, bounds=bounds, state=state,
            authority_seeds=record.seeds,
        )
        return _suspend(
            op="refresh", repository_id=record.repository_id, subject=nxt,
            task=nxt_task, seeds=record.seeds, bounds=bounds, state=state,
            resolution=None, scope=record.scope, remaining=rest,
            changed=record.changed, continuations=continuations,
        )
    if record.op == "explain":
        return _compose_explain_answer(
            record.repository_id, record.subject, record.resolution,
            structural=structural, evidence=evidence, store=store,
            bounds=bounds, state=state,
        )
    if record.op == "authority":
        return _compose_authority_answer(
            record.repository_id, record.subject, record.resolution,
            structural=structural, evidence=evidence, store=store,
            bounds=bounds, state=state,
        )
    if record.op == "trace":
        return _resume_trace(
            record, structural=structural, evidence=evidence, store=store,
            bounds=bounds, state=state, continuations=continuations,
        )
    if record.op == "status":
        return _resume_status(
            record, structural=structural, evidence=evidence, store=store,
            bounds=bounds, state=state, continuations=continuations,
        )
    if record.op == "impact":
        target = record.scope[0] if record.scope else record.subject
        return _compose_impact_answer(
            record.repository_id, target, record.resolution,
            structural=structural, evidence=evidence, store=store,
            bounds=bounds, state=state,
            change_kind=(
                ChangeKind(record.change_kind)
                if record.change_kind is not None
                else ChangeKind.BEHAVIOR
            ),
            change_description=record.change_description,
            seeds=record.seeds,
            suspended=record.suspended + (
                record.subject.subject_id.canonical_locator,
            ),
            continuations=continuations,
        )
    return _compose_refresh_answer(
        record.repository_id, record.scope,
        structural=structural, evidence=evidence, store=store,
        bounds=bounds, state=state,
        changed=record.changed,
    )


def reissue_interpretation(
    continuation: str,
    *,
    continuations: ContinuationStore,
) -> PendingInterpretation:
    """Reissue the identical bounded task once on ingress failure (§7.4).

    Consumes the continuation; a second failure abandons the exchange
    (InterpretationIngressFailure). Semantic validation failure never
    reaches here — it rejects the unit via submit (§7.5).
    """
    record = continuations.claim(continuation)
    if record is None:
        raise InterpretationUnavailable(
            f"unknown or expired continuation: {continuation}"
        )
    if record.reissues >= 1:
        raise InterpretationIngressFailure(
            "interpretation task reissue exhausted; continuation abandoned"
        )
    token = continuations.pend(
        SuspendedOperation(
            op=record.op,
            repository_id=record.repository_id,
            subject=record.subject,
            scope=record.scope,
            remaining=record.remaining,
            changed=record.changed,
            resolution=record.resolution,
            request=record.request,
            fingerprints=record.fingerprints,
            known_subject_ids=record.known_subject_ids,
            seeds=record.seeds,
            bounds=record.bounds,
            state=record.state,
            reissues=record.reissues + 1,
        )
    )
    return PendingInterpretation(
        continuation=token, request=record.request
    )


def _load_subject_state(
    repository_id: str,
    sid: m.SubjectId,
    *,
    store: SemanticStore,
    bounds: m.QueryBounds,
    direction: StructuralDirection = StructuralDirection.BOTH,
) -> tuple[tuple[m.SemanticClaim, ...], tuple[m.SemanticRelationship, ...]]:
    claims = store.load_claims(
        repository_id, (sid,), tuple(m.ClaimKind), bounds
    ).items
    relationships = store.load_relationships(
        repository_id,
        (sid,),
        tuple(m.RelationshipKind),
        direction,
        bounds,
    ).items
    return claims, relationships


def _refresh_view(
    repository_id: str,
    claims: tuple[m.SemanticClaim, ...],
    relationships: tuple[m.SemanticRelationship, ...],
    *,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> tuple[tuple[m.SemanticClaim, ...], tuple[m.SemanticRelationship, ...]]:
    ids: tuple[m.ClaimId | m.RelationshipId, ...] = tuple(
        c.claim_id for c in claims
    ) + tuple(r.relationship_id for r in relationships)
    updates = preflight(
        repository_id, ids, evidence=evidence, store=store, bounds=bounds
    )
    if not updates:
        return claims, relationships
    by_id = {u.semantic_id.value: u.freshness for u in updates}

    def _with_freshness_claim(claim: m.SemanticClaim) -> m.SemanticClaim:
        freshness = by_id.get(claim.claim_id.value)
        if freshness is None:
            return claim
        return m.SemanticClaim(
            claim_id=claim.claim_id, subject=claim.subject, kind=claim.kind,
            value=claim.value, evidence=claim.evidence,
            authority=claim.authority, trust=claim.trust,
            freshness=freshness, basis=claim.basis,
        )

    def _with_freshness_rel(
        rel: m.SemanticRelationship,
    ) -> m.SemanticRelationship:
        freshness = by_id.get(rel.relationship_id.value)
        if freshness is None:
            return rel
        return m.SemanticRelationship(
            relationship_id=rel.relationship_id, source=rel.source,
            kind=rel.kind, target=rel.target, evidence=rel.evidence,
            authority=rel.authority, trust=rel.trust,
            freshness=freshness, basis=rel.basis,
        )

    return (
        tuple(_with_freshness_claim(c) for c in claims),
        tuple(_with_freshness_rel(r) for r in relationships),
    )


def _bound_info(
    bounds: m.QueryBounds,
    returned: int,
    truncated: bool,
    category: str | None,
    token: str | None = None,
) -> m.BoundInfo:
    return m.BoundInfo(
        requested_max_results=bounds.max_results,
        requested_max_depth=bounds.max_depth,
        returned_results=returned,
        truncated=truncated,
        truncated_category=category,
        continuation_token=token,
    )


def _compose_explain_answer(
    repository_id: str,
    subject: m.Subject,
    resolution: m.SubjectResolution | None,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
) -> m.SemanticAnswer:
    sid = subject.subject_id
    claims, relationships = _load_subject_state(
        repository_id, sid, store=store, bounds=bounds
    )
    claims, relationships = _refresh_view(
        repository_id, claims, relationships,
        evidence=evidence, store=store, bounds=bounds,
    )
    conflicts = _validation.find_conflicts(claims, relationships)
    locations = structural.locations(
        repository_id, sid, bounds
    ).items
    requirements: list[m.ResolutionRequirement] = []
    if resolution is not None:
        requirements.extend(_answers.requirements_for_resolution(resolution))
    for claim in claims:
        requirements.extend(_answers.requirements_for_claim(claim))
    (kept_claims, kept_rels, kept_locs), truncated, category, token = (
        _answers.truncate_fields(
            ((claims, "claims"), (relationships, "relationships"),
             (locations, "locations")),
            bounds.max_results,
        )
    )
    content = m.ExplainContent(
        claims=kept_claims,  # type: ignore[arg-type]
        relationships=kept_rels,  # type: ignore[arg-type]
        implementation_locations=kept_locs,  # type: ignore[arg-type]
        conflicts=conflicts,
    )
    returned = len(kept_claims) + len(kept_rels) + len(kept_locs)
    return m.SemanticAnswer(
        answer_id=_answer_id(
            "ans", repository_id, sid.canonical_locator
        ),
        intent=m.SemanticIntent.EXPLAIN,
        repository_state=state,
        subject_resolution=resolution,
        content=content,
        evidence=tuple(ref for c in kept_claims for ref in c.evidence),
        resolution_requirements=tuple(requirements),
        bound_info=_bound_info(bounds, returned, truncated, category),
    )


def explain(
    request: SemanticExplainRequest,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationStore,
    authority_seeds: tuple[m.EvidenceRef, ...] = (),
) -> m.SemanticAnswer | PendingInterpretation:
    """Orientation operation (plan §11.4).

    Returns an answer from stored/current semantics, or suspends with a
    pending-interpretation envelope when interpretation is missing
    (§11.12). Never interprets inline.
    """
    bounds = _resolve_bounds(request.bounds, hook=False)
    state = structural.repository_state(request.repository_id)
    resolution = structural.resolve_subject(
        request.repository_id, request.target, bounds
    )
    if resolution.ambiguity is not m.ResolutionAmbiguity.RESOLVED:
        requirements = _answers.requirements_for_resolution(resolution)
        return m.SemanticAnswer(
            answer_id=_answer_id(
                "ans", request.repository_id,
                request.target.name_or_locator or "unknown",
            ),
            intent=m.SemanticIntent.EXPLAIN,
            repository_state=state,
            subject_resolution=resolution,
            content=m.ExplainContent(),
            evidence=(),
            resolution_requirements=requirements,
            bound_info=_bound_info(bounds, 0, False, None),
        )
    subject = resolution.candidates[0].subject
    claims, relationships = _load_subject_state(
        request.repository_id, subject.subject_id,
        store=store, bounds=bounds,
    )
    if not claims and not relationships:
        task = prepare_interpretation_task(
            request.repository_id, subject, structural=structural,
            evidence=evidence, bounds=bounds, state=state,
            authority_seeds=authority_seeds,
        )
        return _suspend(
            op="explain", repository_id=request.repository_id,
            subject=subject, task=task, seeds=authority_seeds,
            bounds=bounds, state=state, resolution=resolution,
            continuations=continuations,
        )
    return _compose_explain_answer(
        request.repository_id, subject, resolution,
        structural=structural, evidence=evidence, store=store,
        bounds=bounds, state=state,
    )


def _compose_authority_answer(
    repository_id: str,
    subject: m.Subject,
    resolution: m.SubjectResolution | None,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
) -> m.SemanticAnswer:
    sid = subject.subject_id
    claims, relationships = _load_subject_state(
        repository_id, sid, store=store, bounds=bounds
    )
    claims, relationships = _refresh_view(
        repository_id, claims, relationships,
        evidence=evidence, store=store, bounds=bounds,
    )
    bindings = tuple(
        claim.authority for claim in claims if claim.authority is not None
    ) + tuple(
        rel.authority for rel in relationships if rel.authority is not None
    )
    supersession = tuple(
        m.RelationshipRef(id=rel.relationship_id)
        for rel in relationships
        if rel.kind is m.RelationshipKind.SUPERSEDES
    )
    precedence = tuple(
        binding.declared_precedence
        for binding in bindings
        if binding.declared_precedence is not None
    )
    conflicts = _validation.find_conflicts(claims, relationships)
    requirements = (
        list(_answers.requirements_for_resolution(resolution))
        if resolution is not None
        else []
    )
    for claim in claims:
        requirements.extend(_answers.requirements_for_claim(claim))
    unresolved_all = tuple(
        r for r in requirements
        if r.kind is m.ResolutionKind.MISSING_AUTHORITY
    )
    (kept_conflicts, kept_unresolved, kept_bindings, kept_super, kept_prec), truncated, category, token = (
        _answers.truncate_fields(
            (
                (conflicts, "conflicts"),
                (unresolved_all, "unresolved"),
                (bindings, "bindings"),
                (supersession, "supersession"),
                (precedence, "precedence"),
            ),
            bounds.max_results,
        )
    )
    content = m.AuthorityContent(
        governing_bindings=kept_bindings,  # type: ignore[arg-type]
        supersession=kept_super,  # type: ignore[arg-type]
        precedence=kept_prec,  # type: ignore[arg-type]
        conflicts=kept_conflicts,  # type: ignore[arg-type]
        unresolved=kept_unresolved,  # type: ignore[arg-type]
    )
    return m.SemanticAnswer(
        answer_id=_answer_id(
            "aut", repository_id, sid.canonical_locator
        ),
        intent=m.SemanticIntent.AUTHORITY,
        repository_state=state,
        subject_resolution=resolution,
        content=content,
        evidence=tuple(
            binding.evidence_ref for binding in kept_bindings
        ),
        resolution_requirements=tuple(requirements),
        bound_info=_bound_info(
            bounds, len(kept_bindings), truncated, category, token
        ),
    )


def authority(
    request: SemanticAuthorityRequest,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationStore,
    authority_seeds: tuple[m.EvidenceRef, ...] = (),
) -> m.SemanticAnswer | PendingInterpretation:
    """Authority/evidence operation (plan §11.7): governing sources,
    kind/status/applicability, supersession/precedence, conflicts
    side-by-side, missing authority as unresolved. Authority is never
    inferred — only explicit bindings are returned. Suspends via §11.12
    when interpretation is missing; never interprets inline."""
    if isinstance(request.target, m.ClaimRef):
        raise AuthorityTargetError(
            "ClaimRef targets require the Phase 3 subject-scoped lookup"
        )
    bounds = _resolve_bounds(request.bounds, hook=False)
    state = structural.repository_state(request.repository_id)
    resolution = structural.resolve_subject(
        request.repository_id, request.target, bounds
    )
    if resolution.ambiguity is not m.ResolutionAmbiguity.RESOLVED:
        requirements = _answers.requirements_for_resolution(resolution)
        return m.SemanticAnswer(
            answer_id=_answer_id(
                "aut", request.repository_id,
                request.target.name_or_locator or "unknown",
            ),
            intent=m.SemanticIntent.AUTHORITY,
            repository_state=state,
            subject_resolution=resolution,
            content=m.AuthorityContent(),
            evidence=(),
            resolution_requirements=requirements,
            bound_info=_bound_info(bounds, 0, False, None),
        )
    subject = resolution.candidates[0].subject
    claims, relationships = _load_subject_state(
        request.repository_id, subject.subject_id,
        store=store, bounds=bounds,
    )
    if not claims and not relationships:
        task = prepare_interpretation_task(
            request.repository_id, subject, structural=structural,
            evidence=evidence, bounds=bounds, state=state,
            authority_seeds=authority_seeds,
        )
        return _suspend(
            op="authority", repository_id=request.repository_id,
            subject=subject, task=task, seeds=authority_seeds,
            bounds=bounds, state=state, resolution=resolution,
            continuations=continuations,
        )
    return _compose_authority_answer(
        request.repository_id, subject, resolution,
        structural=structural, evidence=evidence, store=store,
        bounds=bounds, state=state,
    )


# ---------------------------------------------------------------------------
# Explicit refresh (plan §9.5)
# ---------------------------------------------------------------------------

def _resolve_scope_subjects(
    repository_id: str,
    target: m.SubjectSelector | m.EvidenceScope,
    *,
    structural: StructuralSource,
    bounds: m.QueryBounds,
) -> tuple[tuple[m.Subject, ...], m.ResolutionAmbiguity]:
    if isinstance(target, m.EvidenceScope):
        subjects: list[m.Subject] = []
        paths = list(target.paths) + [
            ref.locator for ref in target.evidence_refs
        ]
        for path in dict.fromkeys(paths):
            resolution = structural.resolve_subject(
                repository_id,
                m.SubjectSelector(
                    exact_subject_id=None,
                    name_or_locator=path,
                    expected_kinds=(),
                    retrieval_scope_hint=None,
                ),
                bounds,
            )
            subjects.extend(c.subject for c in resolution.candidates)
        seen: set[str] = set()
        unique = []
        for subject in subjects:
            key = subject.subject_id.canonical_locator
            if key not in seen:
                seen.add(key)
                unique.append(subject)
        return tuple(unique), m.ResolutionAmbiguity.RESOLVED
    resolution = structural.resolve_subject(repository_id, target, bounds)
    return (
        tuple(c.subject for c in resolution.candidates),
        resolution.ambiguity,
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
) -> m.SemanticAnswer:
    reloaded_claims: list[m.SemanticClaim] = []
    reloaded_rels: list[m.SemanticRelationship] = []
    for subject in subjects:
        claims, relationships = _load_subject_state(
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
    freshness_items: tuple[m.ClaimRef | m.RelationshipRef, ...] = tuple(
        [m.ClaimRef(id=c.claim_id) for c in claims_t]
        + [m.RelationshipRef(id=r.relationship_id) for r in rels_t]
    )
    scope_paths = tuple(
        s.subject_id.canonical_locator for s in subjects
    )
    content = m.StatusContent(
        freshness_items=freshness_items,
        changed_dependencies=changed,
        verification_currency=(),
        refresh_scope=m.EvidenceScope(paths=scope_paths, evidence_refs=()),
        conflicts=_validation.find_conflicts(claims_t, rels_t),
        unresolved=tuple(
            req for c in claims_t for req in _answers.requirements_for_claim(c)
        ),
    )
    evidence_refs = tuple(ref for c in claims_t for ref in c.evidence)
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
            bounds, len(freshness_items), False, None
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
    """Explicit synchronization (plan §9.5).

    Identifies stale/unverifiable dependencies and reinterprets only
    affected semantic units — suspending per unit via §11.12 and chaining
    continuations while affected work remains. Validation/materialization
    is atomic per unit; failed prior items stay preserved as
    stale/unverifiable; unaffected current items are unchanged. Reports
    as a STATUS-intent answer over StatusContent (no new result type is
    invented: refresh is a lifecycle operation, §11.3).
    """
    bounds = _resolve_bounds(request.bounds, hook=False)
    state = structural.repository_state(request.repository_id)
    if request.target is None:
        raise RefreshScopeError(
            "repo-wide refresh requires Phase 3 subject enumeration"
        )
    subjects, ambiguity = _resolve_scope_subjects(
        request.repository_id, request.target,
        structural=structural, bounds=bounds,
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
    for subject in subjects:
        claims, relationships = _load_subject_state(
            request.repository_id, subject.subject_id,
            store=store, bounds=bounds,
        )
        ids: tuple[m.ClaimId | m.RelationshipId, ...] = tuple(
            c.claim_id for c in claims
        ) + tuple(r.relationship_id for r in relationships)
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
        if updates:
            updated = {u.semantic_id.value for u in updates}
            changed_deps.extend(
                dep for dep in dependencies
                if dep.semantic_id.value in updated
            )
            affected.append(subject)
        elif not request.stale_only:
            affected.append(subject)
    if not affected:
        return _compose_refresh_answer(
            request.repository_id, subjects, structural=structural,
            evidence=evidence, store=store, bounds=bounds, state=state,
            changed=tuple(changed_deps),
        )
    first, rest = affected[0], affected[1:]
    task = prepare_interpretation_task(
        request.repository_id, first, structural=structural,
        evidence=evidence, bounds=bounds, state=state,
        authority_seeds=authority_seeds,
    )
    return _suspend(
        op="refresh", repository_id=request.repository_id, subject=first,
        task=task, seeds=authority_seeds, bounds=bounds, state=state,
        resolution=None, scope=subjects, remaining=rest,
        changed=tuple(changed_deps), continuations=continuations,
    )


# ---------------------------------------------------------------------------
# Explicit offline bootstrap (plan §11.1)
# ---------------------------------------------------------------------------

def initialize_repository(
    request: SemanticInitializeRepositoryRequest,
    *,
    repository_id: str,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds | None = None,
) -> SemanticInitializeRepositoryResult:
    """Explicit offline bootstrap lifecycle (plan §11.1).

    Assigns identity (caller-held, derived at source construction),
    establishes current repository state, verifies the structural
    source, builds the evidence inventory/fingerprint index, records
    authority seeds (caller-held session config in v0.5 — the §10.2
    schema carries no config table), and initializes the semantic
    store schema. Performs NO agent semantic interpretation: there is
    no interpretation input by construction.

    Repository-state metadata persistence (§10.2) arrives with the
    status/baseline flow that consumes it (Phase 3+); every status and
    preflight in v0.5 reads live state instead.
    """
    if not request.repository_locator:
        raise ValueError("repository_locator must be non-empty")
    policy_bounds = bounds or DEFAULT_SERVICE_BOUNDS_POLICY.maximum_query_bounds
    state = structural.repository_state(repository_id)
    inventory = evidence.inventory_evidence(
        repository_id,
        m.EvidenceScope(paths=(), evidence_refs=()),
        policy_bounds,
    )
    warnings: list[str] = []
    if inventory.bound_info.truncated:
        warnings.append(
            "evidence inventory truncated by maximum bounds; "
            "remaining sources discovered on demand"
        )
    if state.dirty:
        warnings.append(
            "working tree dirty; fingerprints track actual content read"
        )
    version = store.schema_version()
    readiness = (
        m.RepositoryReadiness.DEGRADED if warnings and inventory.bound_info.truncated
        else m.RepositoryReadiness.READY
    )
    return SemanticInitializeRepositoryResult(
        repository_id=repository_id,
        readiness=readiness,
        structural_source_status="ready",
        evidence_inventory_status=(
            f"ready:{inventory.bound_info.returned_results}items"
            if not inventory.bound_info.truncated
            else f"degraded:truncated-at-{inventory.bound_info.returned_results}"
        ),
        semantic_store_status=f"ready:schema-{version.value}",
        warnings=tuple(warnings),
        bound_info=inventory.bound_info,
    )


# ---------------------------------------------------------------------------
# Phase 3 — trace / status / impact (plan §11.6, §11.8, §11.5)
# ---------------------------------------------------------------------------

class StatusTargetError(ValueError):
    """Claim/relationship/answer-ref targets require indexed-identity
    lookup, which v0.5 does not provide: answers are never persisted as
    second authority (§11.10), and the store port has no by-id load.
    Status serves selector, evidence-scope, and None targets."""


def _resolve_exact_subject(
    repository_id: str,
    sid: m.SubjectId,
    *,
    structural: StructuralSource,
    bounds: m.QueryBounds,
) -> m.Subject | None:
    """Resolve one known SubjectId to its full record (deterministic)."""
    resolution = structural.resolve_subject(
        repository_id,
        m.SubjectSelector(
            exact_subject_id=sid,
            name_or_locator=None,
            expected_kinds=(),
            retrieval_scope_hint=None,
        ),
        bounds,
    )
    if resolution.ambiguity is m.ResolutionAmbiguity.RESOLVED:
        return resolution.candidates[0].subject
    return None


def _trace_endpoints(
    current: str,
    *,
    rel: m.SemanticRelationship | None = None,
    edge: m.StructuralEdge | None = None,
    direction: StructuralDirection,
) -> list[m.SubjectId]:
    """Traversal endpoints for one path segment under a direction."""
    if rel is not None:
        if direction is StructuralDirection.DOWNSTREAM:
            return [rel.target] if rel.source.canonical_locator == current else []
        if direction is StructuralDirection.UPSTREAM:
            return [rel.source] if rel.target.canonical_locator == current else []
        return [rel.source, rel.target]
    assert edge is not None
    if direction is StructuralDirection.DOWNSTREAM:
        return [edge.target] if edge.source.canonical_locator == current else []
    if direction is StructuralDirection.UPSTREAM:
        return [edge.source] if edge.target.canonical_locator == current else []
    return [edge.source, edge.target]


def _trace_drive(
    repository_id: str,
    target: m.Subject,
    resolution: m.SubjectResolution | None,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationStore,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    direction: StructuralDirection,
    relationship_filter: tuple[m.RelationshipKind, ...] | None,
    boundary_only: bool,
    seeds: tuple[m.EvidenceRef, ...],
    suspended: tuple[str, ...],
) -> m.SemanticAnswer | PendingInterpretation:
    """Bounded iterative frontier expansion (plan §8.6) with suspension.

    Expands one deterministic frontier at a time. The first subject with
    no semantic state that was not already suspended suspends the
    operation (§11.12); resume restarts the deterministic walk, so each
    subject is requested at most once and the walk always terminates.
    """
    kinds = (
        tuple(relationship_filter)
        if relationship_filter is not None
        else tuple(m.RelationshipKind)
    )
    if boundary_only:
        kinds = tuple(
            k for k in kinds if k is m.RelationshipKind.CROSSES_BOUNDARY
        )
    visited: list[str] = []
    rels: list[m.SemanticRelationship] = []
    claims: list[m.SemanticClaim] = []
    sedges: list[m.StructuralEdge] = []
    queue: list[tuple[m.SubjectId, int]] = [(target.subject_id, 0)]
    truncated_walk = False
    while queue and len(rels) + len(sedges) < bounds.max_results:
        sid, depth = queue.pop(0)
        locator = sid.canonical_locator
        if locator in visited:
            continue
        visited.append(locator)
        loaded_claims, loaded_rels = _load_subject_state(
            repository_id, sid, store=store, bounds=bounds,
            direction=direction,
        )
        if not loaded_claims and not loaded_rels and locator not in suspended:
            full = _resolve_exact_subject(
                repository_id, sid, structural=structural, bounds=bounds
            )
            if full is not None:
                task = prepare_interpretation_task(
                    repository_id, full, structural=structural,
                    evidence=evidence, bounds=bounds, state=state,
                    authority_seeds=seeds,
                )
                return _suspend(
                    op="trace", repository_id=repository_id, subject=full,
                    task=task, seeds=seeds, bounds=bounds, state=state,
                    resolution=resolution, scope=(target,),
                    suspended=suspended + (locator,),
                    trace_direction=direction.value,
                    trace_filter=tuple(relationship_filter)
                    if relationship_filter is not None
                    else (),
                    trace_filter_set=relationship_filter is not None,
                    trace_boundary=boundary_only,
                    continuations=continuations,
                )
        for claim in loaded_claims:
            claims.append(claim)
        for rel in loaded_rels:
            if rel.kind in kinds:
                rels.append(rel)
        if depth >= bounds.max_depth:
            continue
        page = structural.edges(
            repository_id, sid, (), direction, bounds
        )
        for edge in page.items:
            sedges.append(edge)
            for endpoint in _trace_endpoints(
                locator, edge=edge, direction=direction
            ):
                queue.append((endpoint, depth + 1))
        for rel in loaded_rels:
            for endpoint in _trace_endpoints(
                locator, rel=rel, direction=direction
            ):
                queue.append((endpoint, depth + 1))
    if queue:
        truncated_walk = True
    return _compose_trace_answer(
        repository_id, target, resolution,
        structural=structural, evidence=evidence, store=store,
        bounds=bounds, state=state,
        relationships=tuple(rels), claims=tuple(claims),
        structural_edges=tuple(sedges[: bounds.max_results]),
        truncated_walk=truncated_walk,
    )


def _compose_trace_answer(
    repository_id: str,
    subject: m.Subject,
    resolution: m.SubjectResolution | None,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    relationships: tuple[m.SemanticRelationship, ...],
    claims: tuple[m.SemanticClaim, ...],
    structural_edges: tuple[m.StructuralEdge, ...],
    truncated_walk: bool,
) -> m.SemanticAnswer:
    ids: tuple[m.ClaimId | m.RelationshipId, ...] = tuple(
        c.claim_id for c in claims
    ) + tuple(r.relationship_id for r in relationships)
    updates = preflight(
        repository_id, ids, evidence=evidence, store=store, bounds=bounds
    )
    fresh_by_id = {u.semantic_id.value: u.freshness for u in updates}

    def _fresh_claim(claim: m.SemanticClaim) -> m.SemanticClaim:
        freshness = fresh_by_id.get(claim.claim_id.value)
        if freshness is None:
            return claim
        return m.SemanticClaim(
            claim_id=claim.claim_id, subject=claim.subject, kind=claim.kind,
            value=claim.value, evidence=claim.evidence,
            authority=claim.authority, trust=claim.trust,
            freshness=freshness, basis=claim.basis,
        )

    def _fresh_rel(rel: m.SemanticRelationship) -> m.SemanticRelationship:
        freshness = fresh_by_id.get(rel.relationship_id.value)
        if freshness is None:
            return rel
        return m.SemanticRelationship(
            relationship_id=rel.relationship_id, source=rel.source,
            kind=rel.kind, target=rel.target, evidence=rel.evidence,
            authority=rel.authority, trust=rel.trust,
            freshness=freshness, basis=rel.basis,
        )

    claims = tuple(_fresh_claim(c) for c in claims)
    relationships = tuple(_fresh_rel(r) for r in relationships)
    conflicts = _validation.find_conflicts(claims, relationships)
    boundary_ids: list[m.SubjectId] = []
    lifecycle_ids: list[m.ClaimId | m.RelationshipId] = []
    for claim in claims:
        if claim.kind is m.ClaimKind.LIFECYCLE_STATE:
            lifecycle_ids.append(claim.claim_id)
    for rel in relationships:
        if rel.kind in (
            m.RelationshipKind.TRANSITIONS_TO,
            m.RelationshipKind.PERSISTS_AT,
        ):
            lifecycle_ids.append(rel.relationship_id)
        if rel.kind is m.RelationshipKind.CROSSES_BOUNDARY:
            boundary_ids.extend((rel.source, rel.target))
    if boundary_ids:
        loaded = store.load_subjects(
            repository_id, tuple(dict.fromkeys(boundary_ids))
        )
        boundary_ids = [
            s.subject_id
            for s in loaded
            if s.subject_id.subject_kind is m.SubjectKind.BOUNDARY
        ] + [i for i in boundary_ids]
        seen: set[str] = set()
        deduped = []
        for i in boundary_ids:
            if i.canonical_locator not in seen:
                seen.add(i.canonical_locator)
                deduped.append(i)
        boundary_ids = deduped
    requirements: list[m.ResolutionRequirement] = []
    if resolution is not None:
        requirements.extend(_answers.requirements_for_resolution(resolution))
    for rel in relationships:
        requirements.extend(_answers.requirements_for_relationship(rel))
    for claim in claims:
        requirements.extend(_answers.requirements_for_claim(claim))
    (kept_conflicts, kept_rels, kept_life, kept_boundary, kept_edges), truncated, category, token = (
        _answers.truncate_fields(
            (
                (conflicts, "conflicts"),
                (relationships, "relationships"),
                (tuple(lifecycle_ids), "lifecycle_context"),
                (tuple(boundary_ids), "boundary_context"),
                (structural_edges, "structural_edges"),
            ),
            bounds.max_results,
        )
    )
    content = m.TraceContent(
        relationships=kept_rels,  # type: ignore[arg-type]
        structural_edges=kept_edges,  # type: ignore[arg-type]
        boundary_context=kept_boundary,  # type: ignore[arg-type]
        lifecycle_context=kept_life,  # type: ignore[arg-type]
        conflicts=kept_conflicts,  # type: ignore[arg-type]
    )
    returned = (
        len(kept_conflicts) + len(kept_rels) + len(kept_life)
        + len(kept_boundary) + len(kept_edges)
    )
    return m.SemanticAnswer(
        answer_id=_answer_id(
            "trc", repository_id, subject.subject_id.canonical_locator
        ),
        intent=m.SemanticIntent.TRACE,
        repository_state=state,
        subject_resolution=resolution,
        content=content,
        evidence=tuple(ref for r in kept_rels for ref in r.evidence),
        resolution_requirements=tuple(requirements),
        bound_info=_bound_info(
            bounds, returned, truncated or truncated_walk,
            category or ("walk" if truncated_walk else None), token,
        ),
    )


def trace(
    request: SemanticTraceRequest,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationStore,
    authority_seeds: tuple[m.EvidenceRef, ...] = (),
) -> m.SemanticAnswer | PendingInterpretation:
    """Context operation (plan §11.6): producers/carriers/consumers,
    explicit semantic-vs-structural path segments, boundary crossings,
    representations/contracts, transformation owners, lifecycle
    transitions and persistence points. Structural paths stay possible
    routes — never runtime facts or authority. Suspends via §11.12 when
    frontier interpretation is missing; never interprets inline."""
    bounds = _resolve_bounds(request.bounds, hook=False)
    state = structural.repository_state(request.repository_id)
    resolution = structural.resolve_subject(
        request.repository_id, request.target, bounds
    )
    if resolution.ambiguity is not m.ResolutionAmbiguity.RESOLVED:
        requirements = _answers.requirements_for_resolution(resolution)
        return m.SemanticAnswer(
            answer_id=_answer_id(
                "trc", request.repository_id,
                request.target.name_or_locator or "unknown",
            ),
            intent=m.SemanticIntent.TRACE,
            repository_state=state,
            subject_resolution=resolution,
            content=m.TraceContent(),
            evidence=(),
            resolution_requirements=requirements,
            bound_info=_bound_info(bounds, 0, False, None),
        )
    return _trace_drive(
        request.repository_id, resolution.candidates[0].subject, resolution,
        structural=structural, evidence=evidence, store=store,
        continuations=continuations, bounds=bounds, state=state,
        direction=request.direction,
        relationship_filter=request.relationship_filter,
        boundary_only=request.boundary_only,
        seeds=authority_seeds, suspended=(),
    )


def _resume_trace(
    record: SuspendedOperation,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    continuations: ContinuationStore,
) -> m.SemanticAnswer | PendingInterpretation:
    target = record.scope[0] if record.scope else record.subject
    return _trace_drive(
        record.repository_id, target, record.resolution,
        structural=structural, evidence=evidence, store=store,
        continuations=continuations, bounds=bounds, state=state,
        direction=StructuralDirection(record.trace_direction or "BOTH"),
        relationship_filter=(
            record.trace_filter if record.trace_filter_set else None
        ),
        boundary_only=record.trace_boundary,
        seeds=record.seeds,
        suspended=record.suspended + (
            record.subject.subject_id.canonical_locator,
        ),
    )


# ---------------------------------------------------------------------------
# Phase 3 — status (plan §11.8)
# ---------------------------------------------------------------------------

def _classify_current(
    repository_id: str,
    semantic_ids: tuple[m.ClaimId | m.RelationshipId, ...],
    *,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> tuple[tuple[m.FreshnessUpdate, ...], tuple[m.EvidenceDependency, ...]]:
    """Classify without persisting (read-only half of preflight).

    Hook paths use this directly: HOOK_FAST is read-only with respect
    to semantic truth and must never mark freshness.
    """
    if not semantic_ids:
        return (), ()
    dependencies = store.load_evidence_dependencies(
        repository_id, semantic_ids
    )
    refs = tuple(dict.fromkeys(dep.evidence_ref for dep in dependencies))
    current: dict[str, str | None] = {}
    if refs:
        page = evidence.inventory_evidence(
            repository_id,
            m.EvidenceScope(paths=(), evidence_refs=refs),
            bounds,
        )
        for item in page.items:
            current[item.evidence_ref.evidence_id.value] = (
                item.content_fingerprint
            )
    return _freshness.classify_all(dependencies, current), dependencies


def _hook_fast(
    repository_id: str,
    target: m.SubjectSelector | m.EvidenceScope | None,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> m.HookStatusNotice:
    """Bounded read-only lifecycle check (plan §11.8 HOOK_FAST).

    Never writes semantic state, discovers evidence, interprets,
    expands reach, initializes, rebuilds, or refreshes. Unresolvable
    paths contribute nothing (I-32 silence).
    """
    try:
        structural.repository_state(repository_id)
    except Exception:
        return m.HookStatusNotice(
            readiness=m.RepositoryReadiness.UNAVAILABLE,
            recommended_action="verify repository availability",
        )
    if target is None:
        return m.HookStatusNotice(
            readiness=m.RepositoryReadiness.READY
        )
    subjects, _ = _resolve_scope_subjects(
        repository_id, target, structural=structural, bounds=bounds
    )
    affected: list[m.SubjectId] = []
    stale = 0
    unverifiable = 0
    for subject in subjects:
        claims, relationships = _load_subject_state(
            repository_id, subject.subject_id, store=store, bounds=bounds
        )
        ids: tuple[m.ClaimId | m.RelationshipId, ...] = tuple(
            c.claim_id for c in claims
        ) + tuple(r.relationship_id for r in relationships)
        if not ids:
            continue
        updates, _ = _classify_current(
            repository_id, ids, evidence=evidence, store=store, bounds=bounds
        )
        if updates:
            affected.append(subject.subject_id)
            for update in updates:
                if update.freshness.state is m.FreshnessState.STALE:
                    stale += 1
                else:
                    unverifiable += 1
    action = None
    if stale or unverifiable:
        action = (
            f"run span_refresh: {stale} stale, "
            f"{unverifiable} unverifiable items"
        )
    return m.HookStatusNotice(
        readiness=m.RepositoryReadiness.READY,
        affected_count=len(affected),
        stale_count=stale,
        unverifiable_count=unverifiable,
        affected_subject_ids=tuple(affected),
        recommended_action=action,
    )


def _compose_status_answer(
    repository_id: str,
    subjects: tuple[m.Subject, ...],
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
) -> m.SemanticAnswer:
    all_claims: list[m.SemanticClaim] = []
    all_rels: list[m.SemanticRelationship] = []
    for subject in subjects:
        claims, relationships = _load_subject_state(
            repository_id, subject.subject_id, store=store, bounds=bounds
        )
        all_claims.extend(claims)
        all_rels.extend(relationships)
    # Classify before the view persists anything: _refresh_view marks
    # state, after which a second classification would always report
    # clean and changed_dependencies would always be empty.
    pre_ids: tuple[m.ClaimId | m.RelationshipId, ...] = tuple(
        c.claim_id for c in all_claims
    ) + tuple(r.relationship_id for r in all_rels)
    updates, dependencies = _classify_current(
        repository_id, pre_ids, evidence=evidence, store=store, bounds=bounds
    )
    updated_ids = {u.semantic_id.value for u in updates}
    changed = tuple(
        dep for dep in dependencies if dep.semantic_id.value in updated_ids
    )
    stale_evidence = {
        dep.evidence_ref.locator
        for dep in dependencies
        if dep.semantic_id.value in updated_ids
    }
    claims_t, rels_t = _refresh_view(
        repository_id, tuple(all_claims), tuple(all_rels),
        evidence=evidence, store=store, bounds=bounds,
    )
    verification = tuple(
        claim.value
        for claim in claims_t
        if claim.kind is m.ClaimKind.VERIFICATION
        and isinstance(claim.value, m.VerificationValue)
    )
    conflicts = _validation.find_conflicts(claims_t, rels_t)
    unresolved: list[m.ResolutionRequirement] = []
    for claim in claims_t:
        unresolved.extend(_answers.requirements_for_claim(claim))
    for rel in rels_t:
        unresolved.extend(_answers.requirements_for_relationship(rel))
    freshness_items: tuple[m.ClaimRef | m.RelationshipRef, ...] = tuple(
        [m.ClaimRef(id=c.claim_id) for c in claims_t]
        + [m.RelationshipRef(id=r.relationship_id) for r in rels_t]
    )
    (kept_conflicts, kept_unresolved, kept_items, kept_changed, kept_ver), truncated, category, token = (
        _answers.truncate_fields(
            (
                (conflicts, "conflicts"),
                (tuple(unresolved), "unresolved"),
                (freshness_items, "freshness_items"),
                (changed, "changed_dependencies"),
                (verification, "verification_currency"),
            ),
            bounds.max_results,
        )
    )
    content = m.StatusContent(
        freshness_items=kept_items,  # type: ignore[arg-type]
        changed_dependencies=kept_changed,  # type: ignore[arg-type]
        verification_currency=kept_ver,  # type: ignore[arg-type]
        refresh_scope=m.EvidenceScope(
            paths=tuple(sorted(stale_evidence)), evidence_refs=()
        ),
        conflicts=kept_conflicts,  # type: ignore[arg-type]
        unresolved=kept_unresolved,  # type: ignore[arg-type]
    )
    returned = (
        len(kept_conflicts) + len(kept_unresolved) + len(kept_items)
        + len(kept_changed) + len(kept_ver)
    )
    return m.SemanticAnswer(
        answer_id=_answer_id(
            "stt", repository_id,
            ",".join(
                s.subject_id.canonical_locator for s in subjects
            ) or "scope",
        ),
        intent=m.SemanticIntent.STATUS,
        repository_state=state,
        subject_resolution=None,
        content=content,
        evidence=tuple(ref for c in claims_t for ref in c.evidence),
        resolution_requirements=tuple(unresolved),
        bound_info=_bound_info(bounds, returned, truncated, category, token),
    )


def status(
    request: SemanticStatusRequest,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationStore,
    authority_seeds: tuple[m.EvidenceRef, ...] = (),
) -> m.SemanticAnswer | PendingInterpretation | m.HookStatusNotice:
    """Currency operation (plan §11.8).

    NORMAL performs the full bounded status operation, suspending via
    §11.12 when subject interpretation is missing. HOOK_FAST is read-only
    lifecycle observation returning a compact notice — never suspension,
    never writes. Claim/relationship/answer-ref targets require lookup
    v0.5 does not provide (StatusTargetError).
    """
    if isinstance(
        request.target, (m.ClaimRef, m.RelationshipRef, m.AnswerRef)
    ):
        raise StatusTargetError(
            "claim/relationship/answer-ref targets require "
            "indexed-identity lookup unavailable in v0.5"
        )
    bounds = _resolve_bounds(request.bounds, hook=False)
    if request.mode is m.StatusMode.HOOK_FAST:
        return _hook_fast(
            request.repository_id, request.target,
            structural=structural, evidence=evidence, store=store,
            bounds=bounds,
        )
    state = structural.repository_state(request.repository_id)
    if request.target is None:
        return m.SemanticAnswer(
            answer_id=_answer_id(
                "stt", request.repository_id, "readiness"
            ),
            intent=m.SemanticIntent.STATUS,
            repository_state=state,
            subject_resolution=None,
            content=m.StatusContent(),
            evidence=(),
            resolution_requirements=(),
            bound_info=_bound_info(bounds, 0, False, None),
        )
    subjects, ambiguity = _resolve_scope_subjects(
        request.repository_id, request.target,
        structural=structural, bounds=bounds,
    )
    if ambiguity is not m.ResolutionAmbiguity.RESOLVED or not subjects:
        requirements: tuple[m.ResolutionRequirement, ...] = ()
        if ambiguity is m.ResolutionAmbiguity.AMBIGUOUS:
            requirements = (
                m.ResolutionRequirement(
                    kind=m.ResolutionKind.AMBIGUOUS_IDENTITY,
                    subject_or_claim=None,
                    description="status target is ambiguous",
                    supporting_context=(),
                ),
            )
        return m.SemanticAnswer(
            answer_id=_answer_id(
                "stt", request.repository_id, "scope"
            ),
            intent=m.SemanticIntent.STATUS,
            repository_state=state,
            subject_resolution=None,
            content=m.StatusContent(),
            evidence=(),
            resolution_requirements=requirements,
            bound_info=_bound_info(bounds, 0, False, None),
        )
    missing = _missing_subjects(
        request.repository_id, subjects, store=store, bounds=bounds,
        suspended=(),
    )
    if missing is not None:
        task = prepare_interpretation_task(
            request.repository_id, missing, structural=structural,
            evidence=evidence, bounds=bounds, state=state,
            authority_seeds=authority_seeds,
        )
        return _suspend(
            op="status", repository_id=request.repository_id,
            subject=missing, task=task, seeds=authority_seeds,
            bounds=bounds, state=state, resolution=None, scope=subjects,
            suspended=(missing.subject_id.canonical_locator,),
            continuations=continuations,
        )
    return _compose_status_answer(
        request.repository_id, subjects, structural=structural,
        evidence=evidence, store=store, bounds=bounds, state=state,
    )


def _missing_subjects(
    repository_id: str,
    subjects: tuple[m.Subject, ...],
    *,
    store: SemanticStore,
    bounds: m.QueryBounds,
    suspended: tuple[str, ...],
) -> m.Subject | None:
    """First subject with no semantic state not already suspended."""
    for subject in subjects:
        if subject.subject_id.canonical_locator in suspended:
            continue
        claims, relationships = _load_subject_state(
            repository_id, subject.subject_id, store=store, bounds=bounds
        )
        if not claims and not relationships:
            return subject
    return None


def _resume_status(
    record: SuspendedOperation,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    continuations: ContinuationStore,
) -> m.SemanticAnswer | PendingInterpretation:
    suspended = record.suspended + (
        record.subject.subject_id.canonical_locator,
    )
    missing = _missing_subjects(
        record.repository_id, record.scope, store=store, bounds=bounds,
        suspended=suspended,
    )
    if missing is not None:
        task = prepare_interpretation_task(
            record.repository_id, missing, structural=structural,
            evidence=evidence, bounds=bounds, state=state,
            authority_seeds=record.seeds,
        )
        return _suspend(
            op="status", repository_id=record.repository_id,
            subject=missing, task=task, seeds=record.seeds,
            bounds=bounds, state=state, resolution=None,
            scope=record.scope, suspended=suspended,
            continuations=continuations,
        )
    return _compose_status_answer(
        record.repository_id, record.scope, structural=structural,
        evidence=evidence, store=store, bounds=bounds, state=state,
    )


# ---------------------------------------------------------------------------
# Phase 3 — impact (plan §11.5, §11.5.1)
# ---------------------------------------------------------------------------

def _derive_change_conditions(
    change_kind: ChangeKind,
    target: m.Subject,
    claims: tuple[m.SemanticClaim, ...],
    relationships: tuple[m.SemanticRelationship, ...],
) -> tuple[m.ChangeCondition, ...]:
    """Deterministic ChangeCondition derivation (plan §11.5.1).

    Dimension flags, never severity/confidence/approval scores. Presence
    rows fire on established canonical state; kind-gated rows additionally
    require the stated change_kind. `OTHER` suppresses kind-gated rows
    only — independently established dimensions still apply.
    """
    sid = target.subject_id
    established_claim_kinds = {
        c.kind
        for c in claims
        if c.trust is m.TrustState.ESTABLISHED
    }
    rel_kinds = {r.kind for r in relationships}
    has_kind = change_kind is not ChangeKind.OTHER
    conditions: list[m.ChangeCondition] = []
    if any(
        c.authority is not None
        and c.authority.status is m.AuthorityStatus.ACCEPTED
        and c.freshness.state is m.FreshnessState.CURRENT
        for c in claims
    ) or m.RelationshipKind.GOVERNED_BY in rel_kinds:
        conditions.append(m.ChangeCondition.AUTHORITY_CHANGE)
    if has_kind and change_kind is ChangeKind.OWNERSHIP:
        conditions.append(m.ChangeCondition.OWNERSHIP_CHANGE)
    if (
        has_kind
        and change_kind is ChangeKind.REPRESENTATION
        and (
            m.ClaimKind.REPRESENTATION_CONTRACT in established_claim_kinds
            or m.RelationshipKind.REPRESENTS_AS in rel_kinds
        )
    ):
        conditions.append(m.ChangeCondition.CANONICAL_REPRESENTATION_CHANGE)
    if m.RelationshipKind.CROSSES_BOUNDARY in rel_kinds or (
        sid.subject_kind is m.SubjectKind.BOUNDARY
    ):
        conditions.append(m.ChangeCondition.BOUNDARY_CHANGE)
    if sid.subject_kind is m.SubjectKind.CONTRACT and any(
        c.authority is not None
        and c.authority.status is m.AuthorityStatus.ACCEPTED
        and c.authority.applicability.description
        for c in claims
        if c.kind is m.ClaimKind.REPRESENTATION_CONTRACT
        or c.kind is m.ClaimKind.PURPOSE
    ):
        conditions.append(m.ChangeCondition.PUBLIC_CONTRACT_CHANGE)
    if m.ClaimKind.INVARIANT_CONSTRAINT in established_claim_kinds:
        conditions.append(m.ChangeCondition.INVARIANT_CHANGE)
    if (
        has_kind
        and change_kind is ChangeKind.CONFIGURATION
        or m.ClaimKind.CONFIGURATION_ENVIRONMENT in established_claim_kinds
        or m.RelationshipKind.CONFIGURED_BY in rel_kinds
    ):
        conditions.append(m.ChangeCondition.CONFIGURATION_CHANGE)
    if (
        has_kind
        and change_kind is ChangeKind.LIFECYCLE
        or m.ClaimKind.LIFECYCLE_STATE in established_claim_kinds
        or m.RelationshipKind.TRANSITIONS_TO in rel_kinds
        or m.RelationshipKind.PERSISTS_AT in rel_kinds
    ):
        conditions.append(m.ChangeCondition.LIFECYCLE_CHANGE)
    if m.ClaimKind.VERIFICATION in established_claim_kinds or (
        m.RelationshipKind.VERIFIED_BY in rel_kinds
    ):
        conditions.append(m.ChangeCondition.VERIFICATION_CHANGE)
    order = {condition: n for n, condition in enumerate(m.ChangeCondition)}
    return tuple(sorted(set(conditions), key=order.__getitem__))


def _compose_impact_answer(
    repository_id: str,
    subject: m.Subject,
    resolution: m.SubjectResolution | None,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationStore,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    change_kind: ChangeKind,
    change_description: str | None,
    seeds: tuple[m.EvidenceRef, ...],
    suspended: tuple[str, ...],
) -> m.SemanticAnswer | PendingInterpretation:
    # change_description is carried on suspend/resume for agent context but
    # never text-mined: proposal-content inference would violate AP-01.
    sid = subject.subject_id
    claims, relationships = _load_subject_state(
        repository_id, sid, store=store, bounds=bounds
    )
    if not claims and not relationships:
        if sid.canonical_locator not in suspended:
            full = _resolve_exact_subject(
                repository_id, sid, structural=structural, bounds=bounds
            )
            if full is not None:
                task = prepare_interpretation_task(
                    repository_id, full, structural=structural,
                    evidence=evidence, bounds=bounds, state=state,
                    authority_seeds=seeds,
                )
                return _suspend(
                    op="impact", repository_id=repository_id,
                    subject=full, task=task, seeds=seeds,
                    bounds=bounds, state=state, resolution=resolution,
                    scope=(subject,),
                    suspended=suspended + (sid.canonical_locator,),
                    change_kind=change_kind.value,
                    change_description=change_description,
                    continuations=continuations,
                )
        claims, relationships = (), ()
    claims, relationships = _refresh_view(
        repository_id, claims, relationships,
        evidence=evidence, store=store, bounds=bounds,
    )
    try:
        reach = structural.reach(
            repository_id, sid, (), StructuralDirection.BOTH,
            bounds.max_depth, bounds,
        )
    except ValueError:
        reach = None
    visited: list[m.SubjectId] = [sid]
    via_edge: dict[str, m.StructuralEdge | None] = {
        sid.canonical_locator: None
    }
    if reach is not None:
        for node in reach.items:
            locator = node.subject.canonical_locator
            if locator not in [v.canonical_locator for v in visited]:
                if len(visited) >= bounds.max_subjects:
                    break
                visited.append(node.subject)
                via_edge[locator] = node.via
    node_claims: dict[str, tuple[m.SemanticClaim, ...]] = {}
    node_rels: dict[str, tuple[m.SemanticRelationship, ...]] = {}
    for visited_id in visited:
        locator = visited_id.canonical_locator
        if locator == sid.canonical_locator:
            node_claims[locator] = claims
            node_rels[locator] = relationships
            continue
        loaded_c, loaded_r = _load_subject_state(
            repository_id, visited_id, store=store, bounds=bounds
        )
        if not loaded_c and not loaded_r and locator not in suspended:
            full = _resolve_exact_subject(
                repository_id, visited_id, structural=structural,
                bounds=bounds,
            )
            if full is not None:
                task = prepare_interpretation_task(
                    repository_id, full, structural=structural,
                    evidence=evidence, bounds=bounds, state=state,
                    authority_seeds=seeds,
                )
                return _suspend(
                    op="impact", repository_id=repository_id,
                    subject=full, task=task, seeds=seeds,
                    bounds=bounds, state=state, resolution=resolution,
                    scope=(subject,),
                    suspended=suspended + (locator,),
                    change_kind=change_kind.value,
                    change_description=change_description,
                    continuations=continuations,
                )
        node_claims[locator] = loaded_c
        node_rels[locator] = loaded_r
    target_rels = [
        r for r in relationships
        if r.source == sid or r.target == sid
    ]
    conditions = _derive_change_conditions(
        change_kind, subject, claims, tuple(target_rels)
    )
    items: list[m.ImpactItem] = []
    for visited_id in visited:
        locator = visited_id.canonical_locator
        if locator == sid.canonical_locator:
            continue
        claims_here = node_claims[locator]
        rels_here = node_rels[locator]
        linking = [
            r for r in list(rels_here) + target_rels
            if (r.source == sid and r.target == visited_id)
            or (r.target == sid and r.source == visited_id)
        ]
        established = [r for r in linking if r.trust is m.TrustState.ESTABLISHED]
        questionable = [
            i for i in (*claims_here, *rels_here)
            if i.freshness.state is not m.FreshnessState.CURRENT
            or i.trust
            in (
                m.TrustState.UNRESOLVED,
                m.TrustState.AMBIGUOUS,
                m.TrustState.CONFLICTED,
                m.TrustState.PARTIAL,
            )
        ]
        edge = via_edge.get(locator)
        if questionable:
            establishment = m.ImpactEstablishment.PARTIAL_OR_UNRESOLVED
            basis = m.SemanticBasis(
                derivation=m.DerivationKind.DERIVED_JOIN,
                summary=(
                    "dependent semantic state is stale, unverifiable, "
                    "or unresolved"
                ),
                input_refs=tuple(
                    (i.claim_id if isinstance(i, m.SemanticClaim)
                     else i.relationship_id)
                    for i in questionable
                ),
            )
        elif established:
            establishment = m.ImpactEstablishment.SEMANTICALLY_ESTABLISHED
            basis = m.SemanticBasis(
                derivation=m.DerivationKind.DERIVED_JOIN,
                summary=(
                    f"{len(established)} established canonical "
                    f"relationship(s) connect the change target to "
                    f"this subject"
                ),
                input_refs=tuple(
                    r.relationship_id for r in established
                ),
            )
        else:
            establishment = m.ImpactEstablishment.STRUCTURAL_POSSIBILITY
            basis = m.SemanticBasis(
                derivation=m.DerivationKind.STRUCTURAL_OBSERVATION,
                summary=(
                    "structural reach only; no canonical relationship "
                    "established"
                ),
                input_refs=(),
            )
        items.append(
            m.ImpactItem(
                subject=visited_id,
                establishment=establishment,
                basis=basis,
                structural_evidence=(edge,) if edge is not None else (),
                relevant_claims=tuple(
                    c.claim_id for c in claims_here
                ),
                relevant_relationships=tuple(
                    r.relationship_id
                    for r in list(rels_here) + established
                ),
            )
        )
    target_context: tuple[m.ClaimId | m.RelationshipId, ...] = tuple(
        [c.claim_id for c in claims]
        + [r.relationship_id for r in relationships]
    )
    verification: tuple[m.ClaimId | m.RelationshipId, ...] = tuple(
        [c.claim_id for c in claims if c.kind is m.ClaimKind.VERIFICATION]
        + [
            r.relationship_id
            for r in relationships
            if r.kind is m.RelationshipKind.VERIFIED_BY
        ]
    )
    all_claims = list(claims) + [
        c for loc, cs in node_claims.items()
        for c in cs
        if loc != sid.canonical_locator
    ]
    all_rels = list(relationships) + [
        r for loc, rs in node_rels.items()
        for r in rs
        if loc != sid.canonical_locator
    ]
    conflicts = _validation.find_conflicts(tuple(all_claims), tuple(all_rels))
    unresolved: list[m.ResolutionRequirement] = []
    if resolution is not None:
        unresolved.extend(_answers.requirements_for_resolution(resolution))
    for claim in all_claims:
        unresolved.extend(_answers.requirements_for_claim(claim))
    for rel in all_rels:
        unresolved.extend(_answers.requirements_for_relationship(rel))
    (kept_conflicts, kept_unresolved, kept_items, kept_context, kept_ver, kept_conds), truncated, category, token = (
        _answers.truncate_fields(
            (
                (conflicts, "conflicts"),
                (tuple(unresolved), "unresolved"),
                (tuple(items), "impacts"),
                (target_context, "target_context"),
                (verification, "verification"),
                (conditions, "change_conditions"),
            ),
            bounds.max_results,
        )
    )
    content = m.ImpactContent(
        target_context=kept_context,  # type: ignore[arg-type]
        change_conditions=kept_conds,  # type: ignore[arg-type]
        impacts=kept_items,  # type: ignore[arg-type]
        verification=kept_ver,  # type: ignore[arg-type]
        conflicts=kept_conflicts,  # type: ignore[arg-type]
        unresolved=kept_unresolved,  # type: ignore[arg-type]
    )
    returned = (
        len(kept_conflicts) + len(kept_unresolved) + len(kept_items)
        + len(kept_context) + len(kept_ver) + len(kept_conds)
    )
    return m.SemanticAnswer(
        answer_id=_answer_id(
            "imp", repository_id,
            f"{sid.canonical_locator}:{change_kind.value}",
        ),
        intent=m.SemanticIntent.IMPACT,
        repository_state=state,
        subject_resolution=resolution,
        content=content,
        evidence=tuple(ref for c in claims for ref in c.evidence),
        resolution_requirements=tuple(unresolved),
        bound_info=_bound_info(bounds, returned, truncated, category, token),
    )


def impact(
    request: SemanticImpactRequest,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationStore,
    authority_seeds: tuple[m.EvidenceRef, ...] = (),
) -> m.SemanticAnswer | PendingInterpretation:
    """Pre-change semantic brief (plan §11.5, task 3.8).

    Composes already-established CQ/F information for a proposed
    material change: identity/purpose/responsibility, owner/custodian,
    governing authority and invariants, boundary/representation context,
    derived ChangeConditions (§11.5.1), established vs structural-only
    downstream impacts, verification currency, conflicts/staleness, and
    requirements. Suspends via §11.12 when interpretation is missing;
    never interprets inline, never invents authority or severity.
    """
    bounds = _resolve_bounds(request.bounds, hook=False)
    state = structural.repository_state(request.repository_id)
    resolution = structural.resolve_subject(
        request.repository_id, request.target, bounds
    )
    if resolution.ambiguity is not m.ResolutionAmbiguity.RESOLVED:
        requirements = _answers.requirements_for_resolution(resolution)
        return m.SemanticAnswer(
            answer_id=_answer_id(
                "imp", request.repository_id,
                request.target.name_or_locator or "unknown",
            ),
            intent=m.SemanticIntent.IMPACT,
            repository_state=state,
            subject_resolution=resolution,
            content=m.ImpactContent(),
            evidence=(),
            resolution_requirements=requirements,
            bound_info=_bound_info(bounds, 0, False, None),
        )
    if request.change_kind is ChangeKind.OTHER and not request.change_description:
        raise ValueError(
            "change_kind OTHER requires a change_description (§11.10)"
        )
    return _compose_impact_answer(
        request.repository_id, resolution.candidates[0].subject, resolution,
        structural=structural, evidence=evidence, store=store,
        continuations=continuations, bounds=bounds, state=state,
        change_kind=request.change_kind,
        change_description=request.change_description,
        seeds=authority_seeds, suspended=(),
    )
