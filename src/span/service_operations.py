"""Span §11.10 service request contracts and agent-exchange operations.

Request contracts are frozen dataclasses (strict typed ingress, I-02).
Span never invokes a model or provider: when stored/current semantics
are insufficient, operations suspend with a ``PendingInterpretation``
(plan §11.12); the invoking agent submits the typed result; Span
validates/materializes and the operation resumes. Trace/status/impact
behavior arrives in its owning phase (Phase 3); transport in Phase 4.
"""

from __future__ import annotations

import dataclasses as _dataclasses
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
from span.shell import paging as _paging
from span.shell.agent_exchange.continuations import (
    ContinuationStore,
    SuspendedOperation,
)

__all__ = [
    "ChangeKind",
    "ProposedChange",
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
    "coverage_check",
    "question_coverage_check",
    "effective_question_view",
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

#: Canonical change vocabulary lives in the core model (single carrier);
#: re-exported here for service consumers (plan §11.10, I-04).
ChangeKind = m.ChangeKind
ProposedChange = m.ProposedChange


@_dataclass(frozen=True)
class SemanticExplainRequest:
    repository_id: str
    target: m.SubjectSelector
    bounds: m.QueryBounds
    page_token: str | None = None
    establish_baseline: bool = False


@_dataclass(frozen=True)
class SemanticImpactRequest:
    repository_id: str
    target: m.SubjectSelector
    change_kind: ChangeKind
    change_description: str | None
    bounds: m.QueryBounds
    affected_assertions: tuple[m.ClaimRef | m.RelationshipRef, ...] = ()
    page_token: str | None = None


@_dataclass(frozen=True)
class SemanticTraceRequest:
    repository_id: str
    target: m.SubjectSelector
    direction: StructuralDirection
    relationship_filter: tuple[m.RelationshipKind, ...] | None
    boundary_only: bool
    bounds: m.QueryBounds
    page_token: str | None = None


@_dataclass(frozen=True)
class SemanticAuthorityRequest:
    repository_id: str
    target: m.SubjectSelector | m.ClaimRef
    bounds: m.QueryBounds
    page_token: str | None = None


@_dataclass(frozen=True)
class SemanticStatusRequest:
    repository_id: str
    target: (
        m.SubjectSelector
        | m.ClaimRef
        | m.RelationshipRef
        | m.EvidenceScope
        | None
    )
    bounds: m.QueryBounds
    mode: m.StatusMode = m.StatusMode.NORMAL
    page_token: str | None = None


@_dataclass(frozen=True)
class SemanticRefreshRequest:
    repository_id: str
    target: m.SubjectSelector | m.EvidenceScope | None
    bounds: m.QueryBounds
    stale_only: bool = True
    page_token: str | None = None


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


def _claim_ref(claim: m.SemanticClaim) -> m.ClaimRef:
    return m.ClaimRef(id=claim.claim_id)


def _relationship_ref(rel: m.SemanticRelationship) -> m.RelationshipRef:
    return m.RelationshipRef(id=rel.relationship_id)


def _item_ref(
    item: m.SemanticClaim | m.SemanticRelationship,
) -> m.ClaimRef | m.RelationshipRef:
    if isinstance(item, m.SemanticClaim):
        return _claim_ref(item)
    return _relationship_ref(item)


def _ref_value(ref: m.ClaimRef | m.RelationshipRef) -> str:
    return ref.id.value


def _setup_requirement(repository_id: str) -> m.ResolutionRequirement:
    """Deterministic resolver for uninitialized repositories (I-27)."""
    return m.ResolutionRequirement(
        kind=m.ResolutionKind.MISSING_EVIDENCE,
        subject_or_claim=None,
        description=(
            f"repository {repository_id} is not initialized; run "
            f"initialize_repository in a dedicated setup session"
        ),
        supporting_context=(),
    )


def _is_initialized(
    repository_id: str, *, store: SemanticStore
) -> bool:
    """Whether explicit initialization recorded this repository.

    Read-only: checking never initializes (I-27).
    """
    return store.load_repository_state(repository_id) is not None


def _uninitialized_answer(
    intent: m.SemanticIntent,
    repository_id: str,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
) -> m.SemanticAnswer:
    """Setup notice for uninitialized repositories (plan §11.1, I-27).

    Never initializes implicitly; directs to a dedicated
    initialization session through a deterministic requirement.
    """
    content: m.SemanticContent
    if intent is m.SemanticIntent.STATUS:
        content = m.StatusContent(
            readiness=m.RepositoryReadiness.UNINITIALIZED
        )
    elif intent is m.SemanticIntent.EXPLAIN:
        content = m.ExplainContent()
    elif intent is m.SemanticIntent.TRACE:
        content = m.TraceContent()
    elif intent is m.SemanticIntent.IMPACT:
        content = m.ImpactContent()
    else:
        content = m.AuthorityContent()
    return m.SemanticAnswer(
        answer_id=_answer_id(
            "uninit", repository_id, intent.value
        ),
        intent=intent,
        repository_state=state,
        subject_resolution=None,
        content=content,
        evidence=(),
        resolution_requirements=(_setup_requirement(repository_id),),
        bound_info=_bound_info(bounds, 0, False, None),
    )


def _answer_id(prefix: str, request_part: str, subject_part: str) -> m.AnswerId:
    import hashlib as _hashlib

    digest = _hashlib.sha256(
        f"{prefix}:{request_part}:{subject_part}".encode("utf-8")
    ).hexdigest()[:16]
    return m.AnswerId(f"{prefix}-{digest}")


def _inventory_snapshot(
    repository_id: str,
    *,
    evidence: EvidenceSource,
    seeds: tuple[tuple[str, str], ...] = (),
) -> tuple[str, dict[str, str]]:
    """Inventory snapshot plus per-seed map (plan §8.5).

    The combined fingerprint covers inventory MEMBERSHIP (which sources
    exist), not their content: newly added sources are visible even
    with no existing dependants, while content changes to known
    sources stay per-item through direct dependencies (MI-07 partial
    staleness). Membership derivation is identical to the paged
    inventory walk (sorted evidence ids); content is hashed only for
    the requested seed locators, so snapshots cost one metadata walk
    instead of one full re-hash per page. Seed content fingerprints come
    from the same walk.
    """
    import hashlib as _hashlib

    entries, fingerprints = evidence.list_inventory_entries(
        repository_id,
        tuple(loc for loc, _ in seeds),
    )
    pairs = sorted(eid for _, eid in entries)
    membership = _hashlib.sha256(repr(pairs).encode("utf-8")).hexdigest()
    return membership, {
        eid: fingerprints.get(loc, "") for loc, eid in seeds
    }


def preflight(
    repository_id: str,
    semantic_ids: tuple[m.ClaimRef | m.RelationshipRef, ...],
    *,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> tuple[m.FreshnessUpdate, ...]:
    """Query freshness preflight (plan §9.2 steps 1–4, Addendum B B-05).

    Direct evidence plus bounded transitive semantic-premise walk with
    cycle detection. Truncation yields UNVERIFIABLE, never silent green.
    """
    if not semantic_ids:
        return ()
    updates, _ = _classify_current(
        repository_id, semantic_ids, evidence=evidence,
        store=store, bounds=bounds,
    )
    premise_updates = _premise_preflight(
        repository_id, semantic_ids, store=store, bounds=bounds,
    )
    merged: dict[str, m.FreshnessUpdate] = {}
    for update in (*updates, *premise_updates):
        merged[update.semantic_id.id.value] = update
    final = tuple(merged.values())
    if final:
        store.mark_freshness(final)
    return final


def _premise_preflight(
    repository_id: str,
    semantic_ids: tuple[m.ClaimRef | m.RelationshipRef, ...],
    *,
    store: SemanticStore,
    bounds: m.QueryBounds,
    max_depth: int = 6,
) -> tuple[m.FreshnessUpdate, ...]:
    """Bounded transitive premise walk with path-based cycle detection.

    A cycle is reported only when a premise chain leads back to an
    item already on the CURRENT traversal path (true circularity).
    Merely visiting the same premise from two roots (diamond or
    sibling order) is not a cycle. Truncation yields UNVERIFIABLE,
    never silent green.
    """
    updates: dict[str, m.FreshnessUpdate] = {}
    clean: set[str] = set()

    def _mark(rid: str, ref: m.ClaimRef | m.RelationshipRef,
              state: m.FreshnessState, reason: str) -> None:
        updates.setdefault(
            rid,
            m.FreshnessUpdate(
                semantic_id=ref, freshness=m.Freshness(state, reason=reason)
            ),
        )

    def _premise_update_state(pid: str) -> m.FreshnessState | None:
        update = updates.get(pid)
        return update.freshness.state if update is not None else None

    def _visit(
        ref: m.ClaimRef | m.RelationshipRef, path: tuple[str, ...],
        depth: int,
    ) -> bool:
        """Walk one subtree; True iff fully explored (no truncation)."""
        rid = ref.id.value
        if rid in clean or rid in updates:
            return True
        if depth >= max_depth:
            return False
        try:
            (item,) = store.load_by_refs(repository_id, (ref,))
        except ValueError:
            _mark(
                rid, ref, m.FreshnessState.UNVERIFIABLE,
                "premise unknown/retired; reassessment required",
            )
            return True
        premises = [
            pref for pref in item.basis.input_refs
            if isinstance(pref, (m.ClaimRef, m.RelationshipRef))
        ]
        if not premises:
            clean.add(rid)
            return True
        complete = True
        for pref in premises:
            pid = pref.id.value
            if pid == rid or pid in path:
                _mark(
                    rid, ref, m.FreshnessState.UNVERIFIABLE,
                    "premise cycle; unverifiable until reconciled",
                )
                continue
            if not _visit(pref, path + (rid,), depth + 1):
                complete = False
                continue
            state = _premise_update_state(pid)
            if state is None:
                try:
                    (premise,) = store.load_by_refs(
                        repository_id, (pref,)
                    )
                except ValueError:
                    _mark(
                        rid, ref, m.FreshnessState.STALE,
                        "premise retired/unknown; dependent reassessment "
                        "required",
                    )
                    continue
                state = premise.freshness.state
            if state is m.FreshnessState.UNVERIFIABLE:
                _mark(
                    rid, ref, m.FreshnessState.UNVERIFIABLE,
                    "upstream premise unverifiable; dependent "
                    "reassessment required",
                )
            elif state is not m.FreshnessState.CURRENT:
                _mark(
                    rid, ref, m.FreshnessState.STALE,
                    "upstream premise noncurrent; dependent reassessment "
                    "required",
                )
        if complete and rid not in updates:
            clean.add(rid)
        return complete

    for ref in semantic_ids:
        if not _visit(ref, (), 0):
            _mark(
                ref.id.value, ref, m.FreshnessState.UNVERIFIABLE,
                "premise frontier truncated; outstanding scope",
            )
        if len(clean) + len(updates) > bounds.max_results * 4 + len(
            semantic_ids
        ):
            _mark(
                ref.id.value, ref, m.FreshnessState.UNVERIFIABLE,
                "premise frontier truncated; outstanding scope",
            )
            break
    return tuple(updates.values())


def _question_identity_key(question: m.SemanticQuestionScope) -> tuple[str, ...]:
    return (
        "q",
        question.scope_root.repository_id,
        question.scope_root.subject_kind.value,
        question.scope_root.canonical_locator,
        question.subject.subject_kind.value,
        question.subject.canonical_locator,
        question.question_class.value,
        question.question_slice,
    )


def effective_question_view(
    coverage: m.InterpretationCoverage,
    *,
    evidence: EvidenceSource | None = None,
    store: SemanticStore | None = None,
    repository_id: str = "",
) -> m.SemanticQuestionCoverageView:
    recorded = coverage.disposition
    effective = recorded
    freshness = m.Freshness(
        state=m.FreshnessState.CURRENT, reason="question dependencies current"
    )
    requirements = tuple(coverage.resolution_requirements)
    # Result/premise check: any noncurrent result ref makes a recorded
    # ANSWERED/NOT_APPLICABLE noncurrent (effective PENDING).
    if store is not None and repository_id and coverage.result_refs:
        try:
            items = store.load_by_refs(
                repository_id, tuple(coverage.result_refs)
            )
        except ValueError:
            items = ()
            effective = m.SemanticQuestionDisposition.PENDING
            freshness = m.Freshness(
                state=m.FreshnessState.UNVERIFIABLE,
                reason="question result unknown/retired",
            )
        else:
            for item in items:
                if item.freshness.state is not m.FreshnessState.CURRENT:
                    if recorded in (
                        m.SemanticQuestionDisposition.ANSWERED,
                        m.SemanticQuestionDisposition.NOT_APPLICABLE,
                    ):
                        effective = m.SemanticQuestionDisposition.PENDING
                    freshness = m.Freshness(
                        state=m.FreshnessState.STALE,
                        reason="question premise/result noncurrent",
                    )
                    break
    # Direct question-evidence check: recompute live fingerprints for
    # every QuestionEvidenceObservation. A changed/unreadable source
    # reopens the question even with zero result refs.
    if (
        effective is not m.SemanticQuestionDisposition.PENDING
        and evidence is not None
        and repository_id
        and coverage.question_evidence
    ):
        for obs in coverage.question_evidence:
            try:
                (unit,) = evidence.read_evidence(
                    (obs.evidence_ref,),
                    m.QueryBounds(50, 2, 8, 24, 96_000, 64, 64),
                )
                current_fp = unit.content_fingerprint
            except ValueError:
                current_fp = None
            if current_fp != obs.observed_fingerprint:
                if recorded in (
                    m.SemanticQuestionDisposition.ANSWERED,
                    m.SemanticQuestionDisposition.NOT_APPLICABLE,
                    m.SemanticQuestionDisposition.OPEN,
                ):
                    effective = m.SemanticQuestionDisposition.PENDING
                freshness = m.Freshness(
                    state=m.FreshnessState.STALE,
                    reason="question evidence changed since examination",
                )
                break
    # Discovery check for the exact question identity: the question's
    # own CoverageDependency snapshot (inventory membership + seeds)
    # is evaluated even when result_refs is empty, so OPEN and
    # NOT_APPLICABLE with zero refs still track discovery movement.
    if (
        effective is not m.SemanticQuestionDisposition.PENDING
        and evidence is not None
        and store is not None
        and repository_id
        and coverage.question is not None
    ):
        try:
            dep_coverages = store.load_coverage_dependencies(
                repository_id, (coverage.question.subject,)
            )
        except Exception:
            dep_coverages = ()
        mine = [
            cov for cov in dep_coverages
            if cov.question is not None
            and _question_identity_key(cov.question)
            == _question_identity_key(coverage.question)
        ]
        if mine:
            latest = mine[-1]
            try:
                inventory_fp, seed_map = _inventory_snapshot(
                    repository_id,
                    evidence=evidence,
                    seeds=tuple(
                        (sf.locator, sf.evidence_id.value)
                        for sf in latest.seed_fingerprints
                    ),
                )
                discovery = _freshness.classify_coverage(
                    latest, inventory_fp, seed_map
                )
            except Exception:
                discovery = m.Freshness(
                    state=m.FreshnessState.UNVERIFIABLE,
                    reason="question discovery unevaluable",
                )
            if discovery.state is not m.FreshnessState.CURRENT:
                if recorded in (
                    m.SemanticQuestionDisposition.ANSWERED,
                    m.SemanticQuestionDisposition.NOT_APPLICABLE,
                    m.SemanticQuestionDisposition.OPEN,
                ):
                    effective = m.SemanticQuestionDisposition.PENDING
                freshness = m.Freshness(
                    state=discovery.state,
                    supporting_revision_or_fingerprint=(
                        discovery.supporting_revision_or_fingerprint
                    ),
                    reason=(
                        "question discovery scope changed; reassessment "
                        "required"
                    ),
                )
    if recorded is m.SemanticQuestionDisposition.PENDING:
        effective = m.SemanticQuestionDisposition.PENDING
    if not coverage.question_evidence and not coverage.result_refs:
        # Zero-result questions rely on discovery snapshot; insufficient
        # snapshot is UNVERIFIABLE, never durable negative fact.
        if recorded is m.SemanticQuestionDisposition.NOT_APPLICABLE:
            freshness = m.Freshness(
                state=m.FreshnessState.UNVERIFIABLE,
                reason="negative determination without direct evidence",
            )
    question = coverage.question
    assert question is not None
    return m.SemanticQuestionCoverageView(
        question=question,
        recorded_disposition=recorded,
        effective_disposition=effective,
        freshness=freshness,
        resolution_requirements=requirements,
    )


def _latest_coverages(
    coverages: tuple[m.CoverageDependency, ...],
) -> tuple[m.CoverageDependency, ...]:
    """Deduplicate coverage history: latest record per subject scope wins.

    This function serves ITEM-level freshness only (`coverage_check`):
    an item's bytes are current when the newest discovery snapshot for
    its subject scope matches current state, regardless of which
    question recorded that snapshot. A refresh under any question
    heals item marks for its scope.

    Question-level currency is deliberately NOT derived here: each
    question's own snapshot is evaluated by exact question identity in
    `effective_question_view`/`question_coverage_check`, so a refresh
    under one question never makes another question current. The
    optional question tag on rows is the audit trail of which
    question refreshed discovery, not an item-freshness partition —
    partitioning items by question would let one outdated snapshot
    poison freshly established items indefinitely.
    """
    latest: dict[tuple[str, ...], m.CoverageDependency] = {}
    for coverage in coverages:
        key = tuple(
            sorted(s.canonical_locator for s in coverage.scope_subjects)
        )
        latest[key] = coverage
    return tuple(latest.values())


def question_coverage_check(
    repository_id: str,
    coverages: tuple[m.InterpretationCoverage, ...],
    *,
    evidence: EvidenceSource,
    store: SemanticStore,
) -> tuple[m.InterpretationCoverage, ...]:
    """Discovery freshness for question coverages incl. zero-result ones.

    For every question coverage (including OPEN/NOT_APPLICABLE with
    zero ``result_refs``), evaluate its exact-question discovery
    snapshot plus direct question evidence. Returns the coverages
    whose dependencies moved and therefore require reassessment
    (effective PENDING). Never infers sufficiency from empty refs.
    """
    stale: list[m.InterpretationCoverage] = []
    for coverage in coverages:
        if coverage.question is None:
            continue
        view = effective_question_view(
            coverage, evidence=evidence, store=store,
            repository_id=repository_id,
        )
        if (
            view.effective_disposition is m.SemanticQuestionDisposition.PENDING
            and coverage.disposition
            is not m.SemanticQuestionDisposition.PENDING
        ) or view.freshness.state is not m.FreshnessState.CURRENT:
            stale.append(coverage)
    return tuple(stale)


def coverage_check(
    repository_id: str,
    items: tuple[m.SemanticClaim | m.SemanticRelationship, ...],
    *,
    evidence: EvidenceSource,
    store: SemanticStore,
) -> tuple[m.FreshnessUpdate, ...]:
    """Discovery-coverage freshness (plan §9.2 step 0, §8.5).

    Compares recorded inventory/seed fingerprints against current state.
    A moved inventory fingerprint — including a newly added authority
    with no existing dependants — marks covered items stale. Persists
    non-current classifications and returns the applied updates.

    Item-scoped by signature: with zero items there is nothing to
    mark, so this path returns early. Zero-result (OPEN /
    NOT_APPLICABLE) question freshness is owned instead by
    `question_coverage_check` plus per-question discovery evaluation
    in `effective_question_view`, which refresh and every answer
    composition consult even when `result_refs` is empty. An empty
    item list alone never proves currentness anywhere.
    """
    if not items:
        return ()
    scope_subjects = tuple(
        dict.fromkeys(
            item.subject if isinstance(item, m.SemanticClaim) else item.source
            for item in items
        )
    )
    coverages = store.load_coverage_dependencies(
        repository_id, scope_subjects
    )
    if not coverages:
        return ()
    inventory_fp, seed_map = _inventory_snapshot(
        repository_id,
        evidence=evidence,
        seeds=tuple(
            (sf.locator, sf.evidence_id.value)
            for cov in coverages
            for sf in cov.seed_fingerprints
        ),
    )
    updates: list[m.FreshnessUpdate] = []
    for coverage in _latest_coverages(coverages):
        freshness = _freshness.classify_coverage(
            coverage, inventory_fp, seed_map
        )
        if freshness.state is m.FreshnessState.CURRENT:
            continue
        covered = {
            s.canonical_locator for s in coverage.scope_subjects
        }
        for item in items:
            locator = (
                item.subject.canonical_locator
                if isinstance(item, m.SemanticClaim)
                else item.source.canonical_locator
            )
            if locator not in covered:
                continue
            ref = (
                m.ClaimRef(id=item.claim_id)
                if isinstance(item, m.SemanticClaim)
                else m.RelationshipRef(id=item.relationship_id)
            )
            updates.append(m.FreshnessUpdate(semantic_id=ref, freshness=freshness))
    if updates:
        store.mark_freshness(tuple(updates))
    return tuple(updates)


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
    # Store-only fallback (Addendum B baseline roots): a subject with
    # no structural observations at all (registered semantic-only
    # root) would otherwise receive an empty task. Top up from the
    # deterministic path-prefix inventory under the subject locator —
    # the subsystem's own files, sorted — so the audit has material
    # to admit member questions from. Structural subjects never reach
    # here (they always carry location observations).
    truncated = len(kept) < len(selected)
    if not observations and len(kept) < bounds.max_evidence_units:
        prefix_page = evidence.inventory_evidence(
            repository_id,
            m.EvidenceScope(
                paths=(sid.canonical_locator,), evidence_refs=()
            ),
            bounds,
        )
        for item in prefix_page.items:
            if len(kept) >= bounds.max_evidence_units:
                break
            if item.evidence_ref.evidence_id.value in seen:
                continue
            seen.add(item.evidence_ref.evidence_id.value)
            kept = kept + (item.evidence_ref,)
        truncated = truncated or prefix_page.bound_info.truncated
    return m.EvidenceSelection(
        selected_refs=kept,
        bound_info=m.BoundInfo(
            requested_max_results=bounds.max_evidence_units,
            requested_max_depth=0,
            returned_results=len(kept),
            truncated=truncated,
            truncated_category="discovery" if truncated else None,
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


def _coverage_for_task(
    repository_id: str,
    subjects: tuple[m.SubjectId, ...],
    *,
    evidence: EvidenceSource,
    seeds: tuple[m.EvidenceRef, ...],
    question: m.SemanticQuestionScope | None = None,
) -> m.CoverageDependency:
    """Build the discovery-coverage record for one unit (plan §8.5)."""
    import datetime as _datetime

    inventory_fp, seed_map = _inventory_snapshot(
        repository_id,
        evidence=evidence,
        seeds=tuple(
            (seed.locator, seed.evidence_id.value) for seed in seeds
        ),
    )
    return m.CoverageDependency(
        scope_subjects=subjects,
        inventory_fingerprint=inventory_fp,
        seed_fingerprints=tuple(
            m.SeedFingerprint(
                evidence_id=seed.evidence_id,
                locator=seed.locator,
                fingerprint=seed_map.get(seed.evidence_id.value, ""),
            )
            for seed in seeds
        ),
        observed_at=_datetime.datetime.now(_datetime.timezone.utc),
        question=question,
    )


def _read_units_within_bytes(
    evidence: EvidenceSource,
    refs: tuple[m.EvidenceRef, ...],
    bounds: m.QueryBounds,
) -> tuple[m.EvidenceUnit, ...]:
    """Read selected refs without breaching the byte budget (§8.4).

    Discovery counts units; the byte budget is enforced here by keeping
    refs that fit and stopping before the first ref that would breach
    it — a selection decision, never a silent bounds widening.
    Oversized singles are skipped (they could never be delivered);
    if nothing fits, the unit fails closed with an actionable message
    instead of dying mid-read.
    """
    units: list[m.EvidenceUnit] = []
    total = 0
    for ref in refs:
        try:
            (unit,) = evidence.read_evidence((ref,), bounds)
        except ValueError:
            continue
        size = len(unit.content.encode("utf-8"))
        if units and total + size > bounds.max_evidence_bytes:
            break
        units.append(unit)
        total += size
    if not units:
        if not refs:
            return ()
        raise ValueError(
            "bounded evidence selection exceeds max_evidence_bytes "
            f"({bounds.max_evidence_bytes}); narrow the target"
        )
    return tuple(units)


def _question_class_for_intent(
    intent: m.SemanticIntent, establish_baseline: bool = False
) -> m.SemanticQuestionClass:
    if establish_baseline:
        return m.SemanticQuestionClass.CQ_01
    if intent is m.SemanticIntent.TRACE:
        return m.SemanticQuestionClass.CQ_04
    if intent is m.SemanticIntent.IMPACT:
        return m.SemanticQuestionClass.CQ_08
    if intent is m.SemanticIntent.AUTHORITY:
        return m.SemanticQuestionClass.CQ_06
    if intent is m.SemanticIntent.STATUS:
        return m.SemanticQuestionClass.CQ_09
    return m.SemanticQuestionClass.CQ_01


#: B.3/B.7: primary question class per operation for question-local
#: missing-state evaluation. A single claim of any kind never
#: satisfies an unexamined question; coverage decides, not claim counts.
_REQUIRED_QUESTION_CLASS: dict[m.SemanticIntent, m.SemanticQuestionClass] = {
    m.SemanticIntent.EXPLAIN: m.SemanticQuestionClass.CQ_01,
    m.SemanticIntent.TRACE: m.SemanticQuestionClass.CQ_04,
    m.SemanticIntent.IMPACT: m.SemanticQuestionClass.CQ_08,
    m.SemanticIntent.AUTHORITY: m.SemanticQuestionClass.CQ_06,
    m.SemanticIntent.STATUS: m.SemanticQuestionClass.CQ_09,
}


def _question_local_missing(
    repository_id: str,
    subject: m.Subject,
    intent: m.SemanticIntent,
    *,
    store: SemanticStore,
    evidence: EvidenceSource | None,
    bounds: m.QueryBounds,
) -> m.SemanticQuestionScope | None:
    """Question-aware missing-state decision (Addendum B B.7).

    Returns the bounded question to examine next, or None when the
    operation may answer from stored/current semantics (possibly
    qualified). Claim/relationship existence alone never counts as
    examined: the operation's primary question class needs recorded
    ANSWERED/NOT_APPLICABLE/OPEN/PENDING coverage. Recorded-but-
    noncurrent answers are served as qualified noncurrent views on
    reads (reassessment belongs to explicit refresh), never
    manufactured inline — except recorded PENDING with no stored
    semantics, which still needs its first examination.
    """
    sid = subject.subject_id
    try:
        coverages = store.load_all_question_coverages(
            repository_id, None, (sid,),
        )
    except Exception:
        try:
            coverages = store.load_question_coverages(
                repository_id, None, (sid,), bounds,
            )
        except Exception:
            coverages = ()
    mine = [
        cov for cov in coverages
        if cov.question is not None and cov.question.subject == sid
    ]
    primary = _REQUIRED_QUESTION_CLASS[intent]
    if intent is m.SemanticIntent.STATUS:
        # STATUS is a read path (currency/verification over stored
        # semantics): it suspends only for a totally unexamined
        # subject (no coverages and no stored claims/relationships).
        # Stale-but-examined state is reported as qualified
        # noncurrent views; reassessment belongs to explicit refresh.
        if not mine:
            claims, relationships, _, _ = _load_subject_state(
                repository_id, sid, store=store, bounds=bounds,
            )
            if not claims and not relationships:
                return m.SemanticQuestionScope(
                    scope_root=sid,
                    subject=sid,
                    question_class=primary,
                    question_slice=sid.canonical_locator,
                    materiality_basis=f"{intent.value} question-local",
                )
        return None
    if not mine:
        # Nothing examined (legacy claims or not): examine primary.
        return m.SemanticQuestionScope(
            scope_root=sid,
            subject=sid,
            question_class=primary,
            question_slice=sid.canonical_locator,
            materiality_basis=f"{intent.value} question-local",
        )
    primary_covs = [
        cov for cov in mine
        if cov.question.question_class is primary
    ]
    if not primary_covs:
        # Claims of other questions never satisfy this unexamined one.
        return m.SemanticQuestionScope(
            scope_root=sid,
            subject=sid,
            question_class=primary,
            question_slice=sid.canonical_locator,
            materiality_basis=f"{intent.value} question-local",
        )
    for cov in primary_covs:
        if (
            cov.disposition is m.SemanticQuestionDisposition.PENDING
            and cov.question is not None
        ):
            return cov.question
    return None


def _stale_question_scopes(
    repository_id: str,
    subject: m.Subject,
    *,
    store: SemanticStore,
    evidence: EvidenceSource,
    bounds: m.QueryBounds,
) -> list[m.SemanticQuestionScope]:
    """Persisted questions requiring reassessment, deterministic order.

    Recorded ANSWERED/NOT_APPLICABLE/OPEN whose effective disposition
    is PENDING or whose freshness is noncurrent (changed evidence,
    moved discovery, retired/stale premises or results). Refresh
    re-examines under these persisted identities (B.3/B-06).
    """
    sid = subject.subject_id
    try:
        coverages = _load_all_coverages_or_defer(
            repository_id, None, (sid,),
            store=store, bounds=bounds,
            purpose="stale question enumeration",
        )
    except Exception:
        return []
    stale: list[m.SemanticQuestionScope] = []
    for cov in coverages:
        if cov.question is None or cov.question.subject != sid:
            continue
        if cov.disposition is m.SemanticQuestionDisposition.PENDING:
            continue
        try:
            view = effective_question_view(
                cov, evidence=evidence, store=store,
                repository_id=repository_id,
            )
        except Exception:
            continue
        if (
            view.effective_disposition
            is m.SemanticQuestionDisposition.PENDING
            or view.freshness.state is not m.FreshnessState.CURRENT
        ):
            stale.append(cov.question)
    stale.sort(
        key=lambda q: (q.question_class.value, q.question_slice)
    )
    return stale


def prepare_interpretation_task(
    repository_id: str,
    subject: m.Subject,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    authority_seeds: tuple[m.EvidenceRef, ...] = (),
    operation_intent: m.SemanticIntent = m.SemanticIntent.EXPLAIN,
    question_slice: str = "",
    proposed_change: m.ProposedChange | None = None,
    store: SemanticStore | None = None,
    scope_root: m.SubjectId | None = None,
    question_class: m.SemanticQuestionClass | None = None,
    materiality_basis: str = "",
    establish_baseline: bool = False,
) -> InterpretationTask:
    """Build the bounded task for the invoking agent (§8.3/§11.12).

    Addendum B: constructs the immutable question scope, loads bounded
    prior canonical items, and attaches service-owned SA obligations.
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
    units = _read_units_within_bytes(
        evidence, selection.selected_refs, bounds
    )
    fingerprints = tuple(
        (unit.evidence_ref.evidence_id.value, unit.content_fingerprint)
        for unit in units
    )
    known_subjects = (sid,) + tuple(
        obs.target_subject
        for obs in observations
        if obs.target_subject is not None
    ) + tuple(obs.source_subject for obs in observations)
    resolved_slice = question_slice or sid.canonical_locator
    resolved_class = question_class or _question_class_for_intent(
        operation_intent, establish_baseline
    )
    if establish_baseline and not question_slice:
        resolved_slice = (
            "Establish the selected root's purpose, principal participants, "
            "and material CQ-01–CQ-09 questions for this bounded scope."
        )
    root = scope_root or sid
    question = m.SemanticQuestionScope(
        scope_root=root,
        subject=sid,
        question_class=resolved_class,
        question_slice=resolved_slice,
        materiality_basis=(
            materiality_basis
            or (
                "user-requested bounded baseline"
                if establish_baseline
                else f"{operation_intent.value} question-local"
            )
        ),
    )
    prior_claims: tuple[m.SemanticClaim, ...] = ()
    prior_relationships: tuple[m.SemanticRelationship, ...] = ()
    if store is not None:
        try:
            claim_page = store.load_claims(
                repository_id, (sid,), (), bounds, None
            )
            prior_claims = tuple(claim_page.items)[: bounds.max_results]
        except Exception:
            prior_claims = ()
        try:
            from span.ports.structural import StructuralDirection as _Dir

            rel_page = store.load_relationships(
                repository_id, (sid,), (), _Dir.BOTH, bounds, None
            )
            prior_relationships = tuple(rel_page.items)[: bounds.max_results]
        except Exception:
            prior_relationships = ()
    request = m.SemanticInterpretationRequest(
        repository_id=repository_id,
        subjects=(subject,),
        evidence_units=units,
        structural_observations=tuple(observations),
        allowed_claim_kinds=tuple(m.ClaimKind),
        allowed_relationship_kinds=tuple(m.RelationshipKind),
        identity_bindings=(sid,),
        operation_intent=operation_intent,
        question_slice=resolved_slice,
        proposed_change=proposed_change,
        bounds=bounds,
        question=question,
        prior_claims=prior_claims,
        prior_relationships=prior_relationships,
        analysis_obligations=m.SA_ANALYSIS_OBLIGATIONS,
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
        evidence_contents={
            unit.evidence_ref.evidence_id.value: unit.content
            for unit in task.request.evidence_units
        },
    )


def _assign_candidate_keys(
    result: m.SemanticInterpretationResult,
) -> m.SemanticInterpretationResult:
    """Deterministic key assignment (plan §4.11 discipline).

    Explicit keys link conflict proposals; empty keys receive
    deterministic `auto:<index>` values so every result carries unique
    non-empty keys. Explicit duplicates reject the unit.
    """
    keys = [
        c.candidate_key for c in result.claims
    ] + [
        r.candidate_key for r in result.relationships
    ]
    explicit = [k for k in keys if k]
    if len(set(explicit)) != len(explicit):
        raise _validation.InterpretationUnitRejected(
            ("duplicate candidate_key in interpretation result",)
        )
    if all(keys):
        return result
    claims = tuple(
        c if c.candidate_key else m.CandidateSemanticClaim(
            candidate_key=f"auto-{n}",
            subject=c.subject,
            kind=c.kind,
            value=c.value,
            evidence=c.evidence,
            candidate_authority=c.candidate_authority,
            basis=c.basis,
        )
        for n, c in enumerate(result.claims)
    )
    relationships = tuple(
        r if r.candidate_key else m.CandidateSemanticRelationship(
            candidate_key=f"auto-c{len(result.claims) + n}",
            source=r.source,
            kind=r.kind,
            target=r.target,
            evidence=r.evidence,
            candidate_authority=r.candidate_authority,
            basis=r.basis,
        )
        for n, r in enumerate(result.relationships)
    )
    return m.SemanticInterpretationResult(
        claims=claims,
        relationships=relationships,
        governing_source_refs=result.governing_source_refs,
        diagnostics=result.diagnostics,
        candidate_subjects=result.candidate_subjects,
        candidate_conflicts=result.candidate_conflicts,
        proposed_question_coverages=result.proposed_question_coverages,
        candidate_withdrawals=result.candidate_withdrawals,
    )


def _admit_established_evidence(
    repository_id: str,
    result: m.SemanticInterpretationResult,
    ctx: _validation.ValidationContext,
    *,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> tuple[_validation.ValidationContext, list[str]]:
    """Admit citations to previously established evidence (addendum A, F2).

    Cited ids unknown to the task are looked up among recorded evidence
    dependencies; current bytes must hash equal to a recorded
    observation, else the citation comes back as a stale/unreadable
    problem — never silently admitted. Unknown ids stay unknown for the
    core to report. Quote, substring, section, and authority checks in
    the core are unchanged.
    """
    cited: set[str] = set()
    for candidate in (*result.claims, *result.relationships):
        cited.update(r.evidence_id.value for r in candidate.evidence)
        authority = candidate.candidate_authority
        if authority is not None:
            cited.add(authority.binding.evidence_ref.evidence_id.value)
    for proposed in result.candidate_subjects:
        cited.update(r.evidence_id.value for r in proposed.evidence)
    wanted = sorted(i for i in cited if i not in ctx.known_evidence_ids)
    if not wanted:
        return ctx, []
    records: dict[str, list[m.EvidenceDependency]] = {}
    for dep in store.load_evidence_records(repository_id, tuple(wanted)):
        records.setdefault(
            dep.evidence_ref.evidence_id.value, []
        ).append(dep)
    fingerprints = dict(ctx.evidence_fingerprints)
    contents = dict(ctx.evidence_contents)
    problems: list[str] = []
    for eid in wanted:
        deps = records.get(eid, ())
        if not deps:
            continue
        ref = deps[0].evidence_ref
        try:
            (unit,) = evidence.read_evidence((ref,), bounds)
        except ValueError:
            problems.append(
                f"cited established evidence is unreadable: {eid}"
            )
            continue
        if unit.content_fingerprint not in {
            d.observed_fingerprint for d in deps
        }:
            problems.append(
                "cited established evidence changed since "
                f"establishment: {eid}"
            )
            continue
        fingerprints[eid] = unit.content_fingerprint
        contents[eid] = unit.content
    return _validation.ValidationContext(
        allowed_claim_kinds=ctx.allowed_claim_kinds,
        allowed_relationship_kinds=ctx.allowed_relationship_kinds,
        known_evidence_ids=ctx.known_evidence_ids | frozenset(fingerprints),
        known_subject_ids=ctx.known_subject_ids,
        evidence_fingerprints=fingerprints,
        evidence_contents=contents,
    ), problems


def _load_all_coverages_or_defer(
    repository_id: str,
    scope_root: m.SubjectId | None,
    subject_ids: tuple[m.SubjectId, ...],
    *,
    store: SemanticStore,
    bounds: m.QueryBounds,
    purpose: str,
) -> tuple[m.InterpretationCoverage, ...]:
    """Unbounded coverage enumeration with bounds-safety deferral (B-03).

    Retirement and withdrawal fanout must see every owning question.
    When the total exceeds the operation bounds the owners cannot be
    safely enumerated, so the unit is rejected/deferred with an
    outstanding-scope requirement — never retired with an incomplete
    fanout, and nothing is partially mutated (raise precedes write).
    """
    try:
        total = store.count_question_coverages(
            repository_id, scope_root, subject_ids
        )
    except Exception:
        total = None
    if total is not None and total > bounds.max_results:
        raise _validation.InterpretationUnitRejected(
            (
                f"{purpose}: {total} owning questions exceed "
                f"bounds max_results={bounds.max_results}; deferred with "
                "outstanding scope — narrow the scope and resubmit",
            )
        )
    try:
        return store.load_all_question_coverages(
            repository_id, scope_root, subject_ids
        )
    except Exception:
        try:
            return store.load_question_coverages(
                repository_id, scope_root, subject_ids, bounds
            )
        except Exception:
            return ()


def _derive_current_question_support(
    claims, relationships, task, fingerprints,
) -> tuple[
    tuple[m.ClaimRef | m.RelationshipRef, ...],
    tuple[m.QuestionEvidenceObservation, ...],
]:
    """Derive result refs and question evidence for an ANSWERED bound
    question from validated unit material (Addendum C C-05).

    Submitted empty refs are completion intent; only derived refs backed
    by materialized candidates count as examined output.
    """
    derived_refs: tuple[
        m.ClaimRef | m.RelationshipRef, ...
    ] = tuple(
        m.ClaimRef(id=c.claim_id) for c in claims
    ) + tuple(
        m.RelationshipRef(id=r.relationship_id)
        for r in relationships
    )
    question_evidence = tuple(
        m.QuestionEvidenceObservation(
            evidence_ref=ref,
            observed_fingerprint=fingerprints[
                ref.evidence_id.value
            ],
        )
        for ref in tuple(
            unit.evidence_ref
            for unit in task.request.evidence_units
        )
        if ref.evidence_id.value in fingerprints
    )
    return derived_refs, question_evidence


def _materialize_unit(
    task: InterpretationTask,
    result: m.SemanticInterpretationResult,
    *,
    store: SemanticStore,
    evidence: EvidenceSource,
    state: m.RepositoryState,
    extra_known_subjects: tuple[m.SubjectId, ...] = (),
    coverage: m.CoverageDependency,
    declared_complete: bool,
    retire_scope: tuple[m.SubjectId, ...],
) -> None:
    """Validate and atomically materialize one submitted unit (§7.5, I-37).

    Addendum B: exact-question completion/retirement with shared-output
    safety, legacy-unassigned preservation, explicit withdrawals and
    entire-unit atomicity. Subject-wide omission is truncation, never
    withdrawal, for question-scoped writes.
    """
    if len(result.claims) > task.request.bounds.max_candidate_claims:
        raise _validation.InterpretationUnitRejected(
            ("interpretation unit exceeds max_candidate_claims",)
        )
    if len(result.relationships) > task.request.bounds.max_candidate_relationships:
        raise _validation.InterpretationUnitRejected(
            ("interpretation unit exceeds max_candidate_relationships",)
        )
    result = _assign_candidate_keys(result)
    ctx = _validation_context_for(task, extra_known_subjects)
    ctx, evidence_problems = _admit_established_evidence(
        task.request.repository_id, result, ctx,
        evidence=evidence, store=store, bounds=task.request.bounds,
    )
    failures: list[str] = []
    failures.extend(evidence_problems)
    new_subjects: list[m.Subject] = []
    new_subject_ids: list[m.SubjectId] = []
    for proposed in result.candidate_subjects:
        validation = _validation.validate_candidate_subject(proposed, ctx)
        if not validation.ok:
            failures.extend(validation.diagnostics)
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
            known_subject_ids=(
                ctx.known_subject_ids + tuple(new_subject_ids)
            ),
            evidence_fingerprints=ctx.evidence_fingerprints,
            evidence_contents=ctx.evidence_contents,
        )
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
                + tuple(
                    m.RelationshipRef(id=r.relationship_id)
                    for r in relationships
                )
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
                    failures.append(
                        f"semantic premise cycle within unit: {pid}"
                    )
                    continue
                try:
                    (prior,) = store.load_by_refs(
                        task.request.repository_id, (pref,)
                    )
                except ValueError:
                    failures.append(
                        f"semantic premise does not resolve: {pid}"
                    )
                    continue
                if prior.freshness.state is not m.FreshnessState.CURRENT:
                    failures.append(
                        f"stale premise cannot support current conclusion: {pid}"
                    )
    except Exception as exc:  # store without new methods in legacy tests
        failures.append(f"premise validation unavailable: {exc}")
    keys_in_result = frozenset(
        [c.candidate_key for c in result.claims]
        + [r.candidate_key for r in result.relationships]
    )
    key_to_ref: dict[str, m.ClaimRef | m.RelationshipRef] = {}
    for candidate, item in zip(result.claims, claims):
        key_to_ref[candidate.candidate_key] = m.ClaimRef(id=item.claim_id)
    for candidate, item in zip(result.relationships, relationships):
        key_to_ref[candidate.candidate_key] = m.RelationshipRef(
            id=item.relationship_id
        )
    recorded: list[m.RecordedConflict] = []
    for proposed in result.candidate_conflicts:
        validation = _validation.validate_candidate_conflict(
            proposed, keys_in_result, ctx
        )
        if not validation.ok:
            failures.extend(validation.diagnostics)
            continue
        left = key_to_ref[proposed.left_key]
        right = key_to_ref[proposed.right_key]
        left_item = next(
            item for item in (*claims, *relationships)
            if _item_ref(item) == left
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
    if failures:
        raise _validation.InterpretationUnitRejected(tuple(failures))
    # ctx fingerprints include addendum-A/F2 admitted established
    # evidence alongside task fingerprints.
    fingerprints = dict(ctx.evidence_fingerprints)
    subjects = tuple(task.request.subjects) + tuple(new_subjects)
    known_ids = {c.claim_id.value for c in claims} | {
        r.relationship_id.value for r in relationships
    }
    # Explicit withdrawals (B-03): validated, source-grounded, never omission.
    all_result_ids = frozenset(known_ids)
    try:
        prior_refs_for_withdrawal: set[str] = set()
        if task.request.question is not None:
            bq = task.request.question
            try:
                existing_qcovs = store.load_all_question_coverages(
                    task.request.repository_id, bq.scope_root,
                    (bq.subject,),
                )
            except Exception:
                try:
                    existing_qcovs = store.load_question_coverages(
                        task.request.repository_id, bq.scope_root,
                        (bq.subject,), task.request.bounds,
                    )
                except Exception:
                    existing_qcovs = ()
            for qc in existing_qcovs:
                if qc.question is None:
                    continue
                q = qc.question
                if (
                    q.scope_root == bq.scope_root and q.subject == bq.subject
                    and q.question_class == bq.question_class
                    and q.question_slice == bq.question_slice
                ):
                    prior_refs_for_withdrawal.update(
                        r.id.value for r in qc.result_refs
                    )
        else:
            for sid in retire_scope:
                try:
                    lc, lr, _, _ = _load_subject_state(
                        task.request.repository_id, sid, store=store,
                        bounds=task.request.bounds,
                    )
                except Exception:
                    continue
                prior_refs_for_withdrawal.update(
                    c.claim_id.value for c in lc
                )
                prior_refs_for_withdrawal.update(
                    r.relationship_id.value for r in lr
                )
    except Exception:
        prior_refs_for_withdrawal = set()
    known_for_withdrawal = frozenset(all_result_ids | prior_refs_for_withdrawal)
    validated_withdrawals: list[m.CandidateSemanticWithdrawal] = []
    for withdrawal in result.candidate_withdrawals:
        problem = _validation.validate_candidate_withdrawal(
            withdrawal, ctx, known_for_withdrawal, "withdrawal",
        )
        if problem is not None:
            raise _validation.InterpretationUnitRejected((problem,))
        # Must name active item in bound question or shared-output set.
        target_id = withdrawal.target.id.value
        try:
            store.load_by_refs(
                task.request.repository_id, (withdrawal.target,)
            )
        except ValueError:
            raise _validation.InterpretationUnitRejected(
                (f"withdrawal target unknown: {target_id}",)
            )
        validated_withdrawals.append(withdrawal)
    retires_claims: list[m.ClaimRef] = []
    retires_relationships: list[m.RelationshipRef] = []
    for withdrawal in validated_withdrawals:
        if isinstance(withdrawal.target, m.ClaimRef):
            retires_claims.append(withdrawal.target)
        else:
            retires_relationships.append(withdrawal.target)
    # Question-scoped retirement: only exact bound question outputs retire,
    # and only when unshared. Legacy path (no bound question and no
    # submitted coverages) retains v0.6 subject-wide behavior for backward
    # compatibility. A bound question with no submitted coverages
    # synthesizes its own current-question coverage below so that every
    # materialization leaves durable question state (no silent unassessed
    # writes); PENDING-only synthesis claims no completion.
    bound_question = task.request.question
    question_coverages_to_persist: list[m.InterpretationCoverage] = []
    reopened_coverages: list[m.InterpretationCoverage] = []
    if bound_question is not None or result.proposed_question_coverages:
        # Validate submitted coverages; derive refs/evidence from validated
        # candidates and expressly selected support refs.
        seen_qidentities: set[tuple[str, ...]] = set()
        for submitted in result.proposed_question_coverages:
            if submitted.question is None:
                raise _validation.InterpretationUnitRejected(
                    ("question coverage without question scope",)
                )
            q = submitted.question
            ident = (
                q.scope_root.repository_id, q.scope_root.canonical_locator,
                q.scope_root.subject_kind.value, q.subject.canonical_locator,
                q.subject.subject_kind.value, q.question_class.value,
                q.question_slice,
            )
            if ident in seen_qidentities:
                raise _validation.InterpretationUnitRejected(
                    ("duplicate question identity in submission",)
                )
            seen_qidentities.add(ident)
            problem = _validation.validate_question_coverage(
                submitted, ctx, "question coverage",
            )
            if problem is not None:
                raise _validation.InterpretationUnitRejected((problem,))
            if q.question_slice != submitted.question_slice:
                raise _validation.InterpretationUnitRejected(
                    ("question_slice mismatch in coverage",)
                )
        # Current-question coverage: Addendum C C-05 eliminates implied
        # completion. An explicit submitted disposition for the bound
        # question is required for ANSWERED/NOT_APPLICABLE. Missing
        # explicit coverage always synthesizes PENDING, never completion,
        # so claims without a completion claim stay unassigned output.
        current_qcov: m.InterpretationCoverage | None = None
        if bound_question is not None:
            is_current = [
                c for c in result.proposed_question_coverages
                if c.question is not None and c.question == bound_question
            ]
            if is_current:
                current_qcov = is_current[0]
                if (
                    current_qcov.disposition
                    is m.SemanticQuestionDisposition.ANSWERED
                ):
                    if not (claims or relationships):
                        raise _validation.InterpretationUnitRejected(
                            (
                                "explicit ANSWERED with zero validated "
                                "material; submit PENDING/OPEN or add "
                                "supported candidates",
                            )
                        )
                    derived_refs, derived_qe = (
                        _derive_current_question_support(
                            claims, relationships, task, fingerprints,
                        )
                    )
                    current_qcov = _dataclasses.replace(
                        current_qcov,
                        result_refs=derived_refs,
                        question_evidence=derived_qe,
                    )
            else:
                # Addendum C C-05: no explicit current coverage means no
                # completion claim. Always synthesize PENDING (admitted but
                # unexamined) so the unit still leaves durable question
                # state; submitted claims persist as unassigned output.
                current_qcov = m.InterpretationCoverage(
                    subjects=tuple(s.subject_id for s in subjects),
                    question_slice=bound_question.question_slice,
                    evidence_scope=m.EvidenceScope(
                        paths=(),
                        evidence_refs=tuple(
                            unit.evidence_ref
                            for unit in task.request.evidence_units
                        ),
                    ),
                    declared_complete=False,
                    question=bound_question,
                    disposition=m.SemanticQuestionDisposition.PENDING,
                    result_refs=(),
                    resolution_requirements=(
                        m.ResolutionRequirement(
                            kind=(
                                m.ResolutionKind.MISSING_SEMANTIC_COVERAGE
                            ),
                            subject_or_claim=bound_question.subject,
                            description=(
                                "question submitted without explicit "
                                "completion; examination pending"
                            ),
                            supporting_context=(),
                        ),
                    ),
                    disposition_basis=(
                        "synthesized pending: no explicit completion submitted"
                    ),
                    question_evidence=(),
                )
            if current_qcov is not None and (
                current_qcov.disposition
                is m.SemanticQuestionDisposition.ANSWERED
            ):
                # Addendum C C-05: only a complete replacement retires
                # prior unshared outputs. PENDING/OPEN/NOT_APPLICABLE never
                # authorize omission-based retirement; explicit withdrawals
                # retire through the validated-withdrawal path above.
                try:
                    prior_qcovs = store.load_all_question_coverages(
                        task.request.repository_id,
                        bound_question.scope_root,
                        (bound_question.subject,),
                    )
                except Exception:
                    try:
                        prior_qcovs = store.load_question_coverages(
                            task.request.repository_id,
                            bound_question.scope_root,
                            (bound_question.subject,),
                            task.request.bounds,
                        )
                    except Exception:
                        prior_qcovs = ()
                old_refs: set[str] = set()
                for qc in prior_qcovs:
                    if qc.question == bound_question:
                        old_refs.update(r.id.value for r in qc.result_refs)
                new_refs = {r.id.value for r in current_qcov.result_refs}
                for oid in old_refs - new_refs:
                    # Shared-output check across ALL questions (unbounded:
                    # a bounded read could hide an owner and cause an
                    # unsafe retirement). Deferral propagates: never
                    # retire with an incomplete owner set.
                    all_qcovs = _load_all_coverages_or_defer(
                        task.request.repository_id, None, (),
                        store=store, bounds=task.request.bounds,
                        purpose="shared-output retirement check",
                    )
                    shared = False
                    for other in all_qcovs:
                        if other.question == bound_question:
                            continue
                        if oid in {r.id.value for r in other.result_refs}:
                            shared = True
                            break
                    if shared:
                        continue
                    # Unshared: retire.
                    try:
                        (old_item,) = store.load_by_refs(
                            task.request.repository_id,
                            (
                                m.ClaimRef(id=m.ClaimId(oid)),
                            ),
                        )
                        if isinstance(old_item, m.SemanticClaim):
                            retires_claims.append(m.ClaimRef(id=m.ClaimId(oid)))
                        else:
                            retires_relationships.append(
                                m.RelationshipRef(id=m.RelationshipId(oid))
                            )
                    except Exception:
                        try:
                            (old_rel,) = store.load_by_refs(
                                task.request.repository_id,
                                (
                                    m.RelationshipRef(
                                        id=m.RelationshipId(oid)
                                    ),
                                ),
                            )
                            retires_relationships.append(
                                m.RelationshipRef(id=m.RelationshipId(oid))
                            )
                        except Exception:
                            continue
        # Addendum C C-05: the bound question persists exactly once, as
        # the derived/synthesized current coverage — never the submitted
        # original (whose empty refs are intent, not examined output).
        question_coverages_to_persist = [
            c for c in result.proposed_question_coverages
            if c.question is None
            or bound_question is None
            or c.question != bound_question
        ]
        if current_qcov is not None:
            question_coverages_to_persist.append(current_qcov)
        # Explicit withdrawal fanout: reopen all other referencing questions.
        # Enumeration is unbounded; overflow defers (raises, no partial
        # write) instead of retiring with an incomplete fanout.
        if validated_withdrawals:
            all_qcovs = _load_all_coverages_or_defer(
                task.request.repository_id, None, (),
                store=store, bounds=task.request.bounds,
                purpose="withdrawal fanout",
            )
            withdrawn_ids = {
                w.target.id.value for w in validated_withdrawals
            }
            for other in all_qcovs:
                if other.question is None:
                    continue
                if bound_question is not None and other.question == bound_question:
                    continue
                if withdrawn_ids & {r.id.value for r in other.result_refs}:
                    reopened_coverages.append(
                        m.InterpretationCoverage(
                            subjects=other.subjects,
                            question_slice=other.question_slice,
                            evidence_scope=other.evidence_scope,
                            declared_complete=False,
                            question=other.question,
                            disposition=m.SemanticQuestionDisposition.PENDING,
                            result_refs=other.result_refs,
                            resolution_requirements=(
                                m.ResolutionRequirement(
                                    kind=m.ResolutionKind.STALE_EVIDENCE,
                                    subject_or_claim=other.question.subject,
                                    description=(
                                        "shared output withdrawn; reassessment "
                                        "required"
                                    ),
                                    supporting_context=(),
                                ),
                            ),
                            disposition_basis=(
                                "reopened by explicit withdrawal in bound question"
                            ),
                            question_evidence=other.question_evidence,
                        )
                    )
            # Bound check: if fanout exceeds bounds, fail without partial.
            if len(reopened_coverages) > task.request.bounds.max_results:
                raise _validation.InterpretationUnitRejected(
                    ("withdrawal fanout exceeds bounds; deferred",)
                )
    else:
        if declared_complete and retire_scope:
            prior_claims: list[m.SemanticClaim] = []
            prior_rels: list[m.SemanticRelationship] = []
            for sid in retire_scope:
                loaded_c, loaded_r, _, _ = _load_subject_state(
                    task.request.repository_id, sid, store=store,
                    bounds=task.request.bounds,
                )
                prior_claims.extend(loaded_c)
                prior_rels.extend(loaded_r)
            for prior in prior_claims:
                if prior.claim_id.value not in known_ids:
                    retires_claims.append(m.ClaimRef(id=prior.claim_id))
            for prior in prior_rels:
                if prior.relationship_id.value not in known_ids:
                    retires_relationships.append(
                        m.RelationshipRef(id=prior.relationship_id)
                    )
    dependencies = tuple(
        m.EvidenceDependency(
            semantic_id=_item_ref(item),
            evidence_ref=ref,
            observed_fingerprint=fingerprints[ref.evidence_id.value],
        )
        for item in (*claims, *relationships)
        for ref in item.evidence
    )
    all_coverages = tuple(question_coverages_to_persist) + tuple(
        reopened_coverages
    )
    if not all_coverages and bound_question is None:
        # Legacy: single empty coverage tuple preserves atomic batch shape.
        all_coverages = ()
    # Deduplicate retirements: an explicit withdrawal and complete
    # replacement may name the same item; retiring twice must not
    # fail the batch on the second (already-moved) lookup.
    seen_retire_claims: set[str] = set()
    unique_retire_claims: list[m.ClaimRef] = []
    for ref in retires_claims:
        if ref.id.value not in seen_retire_claims:
            seen_retire_claims.add(ref.id.value)
            unique_retire_claims.append(ref)
    seen_retire_rels: set[str] = set()
    unique_retire_rels: list[m.RelationshipRef] = []
    for ref in retires_relationships:
        if ref.id.value not in seen_retire_rels:
            seen_retire_rels.add(ref.id.value)
            unique_retire_rels.append(ref)
    store.write_index_batch(
        m.CanonicalIndexBatch(
            subjects=subjects,
            claims=tuple(claims),
            relationships=tuple(relationships),
            evidence_dependencies=dependencies,
            coverage_dependencies=(coverage,),
            coverage=all_coverages,
            retires_claims=tuple(unique_retire_claims),
            retires_relationships=tuple(unique_retire_rels),
            conflicts=tuple(recorded),
        )
    )


def _next_baseline_pending(
    repository_id: str,
    root: m.Subject,
    *,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> m.InterpretationCoverage | None:
    """First admitted PENDING question under a baseline root, if any.

    Deterministic order (CQ class, subject, slice). Used both when a
    baseline resumes after submit and when the baseline operation is
    reissued after a lost continuation: persisted coverage — never
    prompt wording — determines remaining work, so the audit is never
    restarted while admitted work exists.
    """
    try:
        pending = store.load_all_question_coverages(
            repository_id, root.subject_id, (root.subject_id,),
        )
    except Exception:
        try:
            pending = store.load_question_coverages(
                repository_id, root.subject_id,
                (root.subject_id,), bounds,
            )
        except Exception:
            pending = ()
    next_pending = [
        cov for cov in pending
        if cov.disposition is m.SemanticQuestionDisposition.PENDING
        and cov.question is not None
    ]
    next_pending.sort(
        key=lambda c: (
            c.question.question_class.value,  # type: ignore[union-attr]
            c.question.subject.canonical_locator,  # type: ignore[union-attr]
            c.question.question_slice,  # type: ignore[union-attr]
        )
    )
    return next_pending[0] if next_pending else None


def _suspend_baseline_pending(
    repository_id: str,
    root: m.Subject,
    coverage: m.InterpretationCoverage,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    seeds: tuple[m.EvidenceRef, ...],
    resolution: m.SubjectResolution | None,
    continuations: ContinuationStore,
) -> PendingInterpretation:
    """Suspend the next admitted baseline question under its persisted
    identity (no regenerated wording, no restarted audit)."""
    assert coverage.question is not None
    try:
        loaded = store.load_subjects(
            repository_id, (coverage.question.subject,)
        )
        nxt_subject = (
            m.Subject(
                subject_id=loaded[0].subject_id,
                display_name=loaded[0].display_name,
                declared_kind=loaded[0].declared_kind,
            )
            if loaded else root
        )
    except Exception:
        nxt_subject = root
    nxt_task = prepare_interpretation_task(
        repository_id, nxt_subject,
        structural=structural, evidence=evidence, bounds=bounds,
        state=state, authority_seeds=seeds,
        operation_intent=m.SemanticIntent.EXPLAIN,
        question_slice=coverage.question.question_slice,
        store=store,
        scope_root=coverage.question.scope_root,
        question_class=coverage.question.question_class,
        materiality_basis=coverage.question.materiality_basis,
        establish_baseline=False,
    )
    return _suspend(
        op="explain", repository_id=repository_id,
        subject=nxt_subject, task=nxt_task, seeds=seeds,
        bounds=bounds, state=state, resolution=resolution,
        continuations=continuations,
        operation_intent="EXPLAIN",
        question_slice=coverage.question.question_slice,
        establish_baseline=True,
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
    affected_assertions: tuple[m.ClaimRef | m.RelationshipRef, ...] = (),
    operation_intent: str = "EXPLAIN",
    question_slice: str = "",
    declared_complete: bool = False,
    trace_direction: str | None = None,
    trace_filter: tuple[m.RelationshipKind, ...] = (),
    trace_filter_set: bool = False,
    trace_boundary: bool = False,
    continuations: ContinuationStore,
    establish_baseline: bool = False,
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
            affected_assertions=affected_assertions,
            operation_intent=operation_intent,
            question_slice=question_slice,
            declared_complete=declared_complete,
            trace_direction=trace_direction,
            trace_filter=trace_filter,
            trace_filter_set=trace_filter_set,
            trace_boundary=trace_boundary,
            establish_baseline=establish_baseline,
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
    endpoints = []
    for candidate in result.relationships:
        endpoints.extend((candidate.source, candidate.target))
    endpoints.extend(candidate.subject for candidate in result.claims)
    for endpoint in endpoints:
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
            continue
        # Registered semantic-only subjects live in the store, not the
        # structural source: previously indexed identities join the unit
        # scope exactly like structurally resolved ones (§4.11).
        if store.load_subjects(record.repository_id, (endpoint,)):
            extra_known.append(endpoint)
    _materialize_unit(
        task, result, store=store, evidence=evidence, state=state,
        extra_known_subjects=tuple(extra_known),
        coverage=_coverage_for_task(
            record.repository_id,
            tuple(s.subject_id for s in task.request.subjects),
            evidence=evidence, seeds=record.seeds,
            question=task.request.question,
        ),
        declared_complete=record.declared_complete,
        retire_scope=tuple(s.subject_id for s in task.request.subjects),
    )
    if record.op == "refresh" and record.remaining:
        nxt, rest = record.remaining[0], record.remaining[1:]
        nxt_stale = _stale_question_scopes(
            record.repository_id, nxt,
            store=store, evidence=evidence, bounds=bounds,
        )
        nxt_scope = nxt_stale[0] if nxt_stale else None
        nxt_task = prepare_interpretation_task(
            record.repository_id, nxt, structural=structural,
            evidence=evidence, bounds=bounds, state=state,
            authority_seeds=record.seeds,
            operation_intent=m.SemanticIntent.STATUS,
            question_slice=(
                nxt_scope.question_slice if nxt_scope is not None
                else nxt.subject_id.canonical_locator
            ),
            store=store,
            scope_root=(
                nxt_scope.scope_root if nxt_scope is not None
                else nxt.subject_id
            ),
            question_class=(
                nxt_scope.question_class if nxt_scope is not None else None
            ),
            materiality_basis=(
                nxt_scope.materiality_basis if nxt_scope is not None else ""
            ),
        )
        return _suspend(
            op="refresh", repository_id=record.repository_id, subject=nxt,
            task=nxt_task, seeds=record.seeds, bounds=bounds, state=state,
            resolution=None, scope=record.scope, remaining=rest,
            changed=record.changed, continuations=continuations,
            operation_intent="STATUS",
            question_slice=nxt_task.request.question_slice,
            declared_complete=True,
        )
    if record.op == "explain":
        if record.establish_baseline:
            nxt_cov = _next_baseline_pending(
                record.repository_id, record.subject,
                store=store, bounds=bounds,
            )
            if nxt_cov is not None:
                return _suspend_baseline_pending(
                    record.repository_id, record.subject, nxt_cov,
                    structural=structural, evidence=evidence, store=store,
                    bounds=bounds, state=state, seeds=record.seeds,
                    resolution=record.resolution,
                    continuations=continuations,
                )
        return _compose_explain_answer(
            record.repository_id, record.subject, record.resolution,
            structural=structural, evidence=evidence, store=store,
            bounds=bounds, state=state,
            scope_root=record.subject.subject_id,
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
            affected_assertions=record.affected_assertions,
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
            affected_assertions=record.affected_assertions,
            operation_intent=record.operation_intent,
            question_slice=record.question_slice,
            declared_complete=record.declared_complete,
            establish_baseline=record.establish_baseline,
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
    page_token: str | None = None,
) -> tuple[
    tuple[m.SemanticClaim, ...],
    tuple[m.SemanticRelationship, ...],
    str | None,
    str | None,
]:
    """Load one subject's state window plus per-list next tokens.

    The answer-level token carries per-list offsets
    (``pg:<claims_skip>:<rels_skip>:<questions_skip>``); each load windows
    from its own offset, so every item is reachable exactly once across
    pages. The returned tokens are the raw store cursors (``None`` =
    exhausted).
    """
    claims_skip, rels_skip, _ = _paging.parse_service_token(page_token)
    claim_page = store.load_claims(
        repository_id,
        (sid,),
        tuple(m.ClaimKind),
        bounds,
        _paging.next_page_token(claims_skip) if claims_skip else None,
    )
    rel_page = store.load_relationships(
        repository_id,
        (sid,),
        tuple(m.RelationshipKind),
        direction,
        bounds,
        _paging.next_page_token(rels_skip) if rels_skip else None,
    )
    return (
        claim_page.items,
        rel_page.items,
        claim_page.bound_info.continuation_token,
        rel_page.bound_info.continuation_token,
    )


def _next_service_token(
    page_token: str | None,
    kept_claims: tuple[m.SemanticClaim, ...],
    kept_rels: tuple[m.SemanticRelationship, ...],
    loaded_claims: tuple[m.SemanticClaim, ...],
    loaded_rels: tuple[m.SemanticRelationship, ...],
    claims_token: str | None,
    rels_token: str | None,
    questions_skip: int = 0,
    questions_remaining: int = 0,
) -> str | None:
    """Answer-level next token from shown counts (plan I-39).

    Each side advances past shown items only, so unshown-but-loaded
    items reappear in the next window instead of being skipped. A side
    is exhausted when its load cursor is done and everything loaded
    was shown.
    """
    claims_skip, rels_skip, qskip = _paging.parse_service_token(page_token)
    claims_exhausted = (
        claims_token is None and len(kept_claims) >= len(loaded_claims)
    )
    rels_exhausted = (
        rels_token is None and len(kept_rels) >= len(loaded_rels)
    )
    questions_exhausted = questions_remaining <= 0
    if claims_exhausted and rels_exhausted and questions_exhausted:
        return None
    return _paging.format_service_token(
        claims_skip + len(kept_claims),
        rels_skip + len(kept_rels),
        (qskip + questions_skip) if not questions_exhausted else qskip,
    )


def _refresh_view(
    repository_id: str,
    claims: tuple[m.SemanticClaim, ...],
    relationships: tuple[m.SemanticRelationship, ...],
    *,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> tuple[tuple[m.SemanticClaim, ...], tuple[m.SemanticRelationship, ...]]:
    ids: tuple[m.ClaimRef | m.RelationshipRef, ...] = tuple(
        _claim_ref(c) for c in claims
    ) + tuple(_relationship_ref(r) for r in relationships)
    updates = preflight(
        repository_id, ids, evidence=evidence, store=store, bounds=bounds
    )
    updates = updates + coverage_check(
        repository_id, tuple(claims) + tuple(relationships),
        evidence=evidence, store=store,
    )
    if not updates:
        return claims, relationships
    by_id = {_ref_value(u.semantic_id): u.freshness for u in updates}

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


def _recorded_conflicts(
    repository_id: str,
    claims: tuple[m.SemanticClaim, ...],
    relationships: tuple[m.SemanticRelationship, ...],
    *,
    store: SemanticStore,
) -> tuple[m.SemanticConflict, ...]:
    """Merge validated agent-proposed conflicts (plan §6.4) with derived ones.

    Only pairs whose both sides resolve among the loaded items are shown;
    anything else is a store inconsistency, never guessed into place.
    """
    if not claims and not relationships:
        return ()
    scope = tuple(
        dict.fromkeys(
            [c.subject for c in claims]
            + [r.source for r in relationships]
            + [r.target for r in relationships]
        )
    )
    known = {_claim_ref(c) for c in claims} | {
        _relationship_ref(r) for r in relationships
    }
    merged: list[m.SemanticConflict] = []
    for record in store.load_conflicts(repository_id, scope):
        if record.left in known and record.right in known:
            merged.append(
                m.SemanticConflict(
                    left=record.left,
                    right=record.right,
                    declared_precedence=record.declared_precedence,
                )
            )
    merged.sort(
        key=lambda c: (
            _ref_value(c.left),
            _ref_value(c.right),
        )
    )
    return tuple(merged)


def _conflicts_for(
    repository_id: str,
    claims: tuple[m.SemanticClaim, ...],
    relationships: tuple[m.SemanticRelationship, ...],
    *,
    store: SemanticStore,
) -> tuple[m.SemanticConflict, ...]:
    """All visible conflicts: core-derived plus recorded proposals."""
    derived = _validation.find_conflicts(claims, relationships)
    recorded = _recorded_conflicts(
        repository_id, claims, relationships, store=store
    )
    seen = {
        (_ref_value(c.left), _ref_value(c.right)) for c in derived
    }
    extra = tuple(
        c for c in recorded
        if (_ref_value(c.left), _ref_value(c.right)) not in seen
    )
    return derived + extra


def _select_answer_items(
    claims: tuple[m.SemanticClaim, ...],
    relationships: tuple[m.SemanticRelationship, ...],
    conflicts: tuple[m.SemanticConflict, ...],
    max_results: int,
    extra_mandatory: tuple[str, ...] = (),
) -> tuple[
    tuple[m.SemanticClaim, ...],
    tuple[m.SemanticRelationship, ...],
    tuple[m.SemanticConflict, ...],
    bool,
    str | None,
]:
    """Bounded item selection preserving answer self-containment (I-36).

    Conflict pairs are atomic and their endpoints mandatory: a known
    conflict is never truncated to one visible side. All ref-lists in
    the answer are derived from the kept set only, so no reference
    dangles. Returns kept claims, kept relationships, kept conflicts,
    truncated flag, and first-dropped category.
    """
    kept_conf = list(conflicts[:max_results])
    truncated = len(conflicts) > len(kept_conf)
    category: str | None = "conflicts" if truncated else None

    def _mandatory(pairs: list[m.SemanticConflict]) -> list[str]:
        ids: list[str] = []
        for pair in pairs:
            ids.append(_ref_value(pair.left))
            ids.append(_ref_value(pair.right))
        ids.extend(extra_mandatory)
        return list(dict.fromkeys(ids))

    while kept_conf and (
        len(kept_conf)
        + len(set(_mandatory(kept_conf)) & (
            {c.claim_id.value for c in claims}
            | {r.relationship_id.value for r in relationships}
        )) > max_results
    ):
        kept_conf.pop()
        truncated = True
        if category is None:
            category = "conflicts"
    mandatory = set(_mandatory(kept_conf))
    budget = max_results - len(kept_conf)
    mand_claims = [c for c in claims if c.claim_id.value in mandatory]
    mand_rels = [
        r for r in relationships if r.relationship_id.value in mandatory
    ]
    rest_claims = [c for c in claims if c.claim_id.value not in mandatory]
    rest_rels = [
        r for r in relationships if r.relationship_id.value not in mandatory
    ]
    kept_claims = list(mand_claims)
    kept_rels = list(mand_rels)
    # Fair round-robin fill in stable order: each side advances only
    # past shown items, so per-list page offsets stay exact (I-39).
    while len(kept_claims) + len(kept_rels) < budget and (
        rest_claims or rest_rels
    ):
        if rest_claims:
            kept_claims.append(rest_claims.pop(0))
            if len(kept_claims) + len(kept_rels) >= budget:
                break
        if rest_rels:
            kept_rels.append(rest_rels.pop(0))
    if len(kept_claims) + len(kept_rels) < len(claims) + len(relationships):
        truncated = True
        if category is None:
            category = "claims"
    kept_ids = {c.claim_id.value for c in kept_claims} | {
        r.relationship_id.value for r in kept_rels
    }
    kept_conf = [
        pair for pair in kept_conf
        if _ref_value(pair.left) in kept_ids
        and _ref_value(pair.right) in kept_ids
    ]
    return tuple(kept_claims), tuple(kept_rels), tuple(kept_conf), truncated, category


def _freshness_items_for(
    claims: tuple[m.SemanticClaim, ...],
    relationships: tuple[m.SemanticRelationship, ...],
) -> tuple[m.FreshnessItem, ...]:
    """Per-item freshness records for exactly the carried items (I-36)."""
    return tuple(
        [m.FreshnessItem(_claim_ref(c), c.subject, c.freshness, c.trust)
         for c in claims]
        + [m.FreshnessItem(_relationship_ref(r), r.source, r.freshness, r.trust)
           for r in relationships]
    )


def _baseline_sufficient(
    repository_id: str,
    scope_root: m.SubjectId,
    *,
    store: SemanticStore,
    evidence: EvidenceSource,
    bounds: m.QueryBounds,
) -> bool:
    """Recorded scoped sufficiency for an expressly selected root (B.3.2).

    True only when: (a) all nine root CQ classes have an explicit
    applicability disposition; (b) every admitted material root/member
    question is ANSWERED or genuinely NOT_APPLICABLE with *current*
    (effective) dependencies; (c) no unresolved requirements, conflicts,
    or unassessed legacy items remain in scope; (d) no outstanding
    pages, unexamined questions, unprocessed premise frontier, or
    stale/unverifiable items; (e) synthesis rests on established,
    currently supported member evidence. Recorded dispositions alone
    never suffice — effective currentness is recomputed.
    """
    try:
        coverages = _load_all_coverages_or_defer(
            repository_id, scope_root, (),
            store=store, bounds=bounds,
            purpose="baseline sufficiency audit",
        )
    except Exception:
        return False
    root_covs = [
        cov for cov in coverages
        if cov.question is not None and cov.question.scope_root == scope_root
    ]
    if not root_covs:
        return False
    # (a) all nine root CQ classes have an explicit disposition entry
    # on the root subject itself.
    root_classes = {
        cov.question.question_class
        for cov in root_covs
        if cov.question.subject == scope_root
    }
    if any(cls not in root_classes for cls in m.SemanticQuestionClass):
        return False
    # (b)+(d) every admitted question effective-current ANSWERED or
    # NOT_APPLICABLE; PENDING/OPEN/noncurrent/stale block sufficiency.
    for cov in root_covs:
        if cov.question is None:
            continue
        try:
            view = effective_question_view(
                cov, evidence=evidence, store=store,
                repository_id=repository_id,
            )
        except Exception:
            return False
        if view.recorded_disposition in (
            m.SemanticQuestionDisposition.PENDING,
            m.SemanticQuestionDisposition.OPEN,
        ):
            return False
        if view.effective_disposition not in (
            m.SemanticQuestionDisposition.ANSWERED,
            m.SemanticQuestionDisposition.NOT_APPLICABLE,
        ):
            return False
        if view.freshness.state is not m.FreshnessState.CURRENT:
            return False
        # (c) any open requirement (missing authority/evidence,
        # conflicts, stale premises) prevents full sufficiency.
        if view.resolution_requirements:
            return False
    # (c) no conflicts among scoped canonical items.
    try:
        scoped_subjects = tuple(
            dict.fromkeys(
                cov.question.subject for cov in root_covs
                if cov.question is not None
            )
        )
        scoped_claims: list[m.SemanticClaim] = []
        scoped_rels: list[m.SemanticRelationship] = []
        for sid in scoped_subjects:
            loaded_c, loaded_r, _, _ = _load_subject_state(
                repository_id, sid, store=store, bounds=bounds,
            )
            scoped_claims.extend(loaded_c)
            scoped_rels.extend(loaded_r)
        if _conflicts_for(
            repository_id, tuple(scoped_claims), tuple(scoped_rels),
            store=store,
        ):
            return False
        # (d) no stale/unverifiable items and no unprocessed premise
        # frontier across scoped results.
        all_refs: tuple[m.ClaimRef | m.RelationshipRef, ...] = tuple(
            _claim_ref(c) for c in scoped_claims
        ) + tuple(_relationship_ref(r) for r in scoped_rels)
        if all_refs:
            premise_updates = _premise_preflight(
                repository_id, all_refs, store=store, bounds=bounds,
            )
            if premise_updates:
                return False
            if any(
                c.freshness.state is not m.FreshnessState.CURRENT
                for c in scoped_claims
            ) or any(
                r.freshness.state is not m.FreshnessState.CURRENT
                for r in scoped_rels
            ):
                return False
        # (d) no outstanding pages: every scoped subject load must be
        # exhaustive within bounds.
        for sid in scoped_subjects:
            claim_page = store.load_claims(
                repository_id, (sid,), (), bounds, None
            )
            if claim_page.bound_info.truncated:
                return False
    except Exception:
        return False
    # (e) is entailed by (b)+(d): every ANSWERED result ref resolved
    # above to a CURRENT canonical item through the effective views.
    return True


def _question_views_for_scope(
    repository_id: str,
    scope_root: m.SubjectId | None,
    subject_ids: tuple[m.SubjectId, ...],
    *,
    store: SemanticStore,
    bounds: m.QueryBounds,
    evidence: EvidenceSource | None = None,
) -> tuple[m.SemanticQuestionCoverageView, ...]:
    try:
        coverages = store.load_question_coverages(
            repository_id, scope_root, subject_ids, bounds,
        )
    except Exception:
        return ()
    views: list[m.SemanticQuestionCoverageView] = []
    for cov in coverages:
        if cov.question is None:
            continue
        try:
            views.append(
                effective_question_view(
                    cov, evidence=evidence, store=store,
                    repository_id=repository_id,
                )
            )
        except Exception:
            continue
    views.sort(
        key=lambda v: (
            v.question.question_class.value,
            v.question.subject.canonical_locator,
            v.question.question_slice,
        )
    )
    return tuple(views)


def _paged_question_views(
    repository_id: str,
    scope_root: m.SubjectId | None,
    subject_ids: tuple[m.SubjectId, ...],
    *,
    store: SemanticStore,
    bounds: m.QueryBounds,
    page_token: str | None = None,
    evidence: EvidenceSource | None = None,
) -> tuple[tuple[m.SemanticQuestionCoverageView, ...], int, int]:
    """Return (kept views, shown count, remaining count) for paging."""
    from span.shell import paging as _paging

    try:
        _, _, qskip = _paging.parse_service_token(page_token)
    except ValueError:
        qskip = 0
    all_views = _question_views_for_scope(
        repository_id, scope_root, subject_ids,
        store=store, bounds=bounds, evidence=evidence,
    )
    # Reserve budget: questions share max_results with claims/rels.
    # Simple policy: show up to remaining budget after caller slices
    # claims/rels; here return windowed slice, caller decides budget.
    kept = all_views[qskip:qskip + bounds.max_results]
    remaining = max(0, len(all_views) - (qskip + len(kept)))
    return kept, len(kept), remaining


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
    page_token: str | None = None,
    scope_root: m.SubjectId | None = None,
) -> m.SemanticAnswer:
    sid = subject.subject_id
    claims, relationships, claims_token, rels_token = _load_subject_state(
        repository_id, sid, store=store, bounds=bounds,
        page_token=page_token,
    )
    claims, relationships = _refresh_view(
        repository_id, claims, relationships,
        evidence=evidence, store=store, bounds=bounds,
    )
    conflicts_all = _conflicts_for(
        repository_id, claims, relationships, store=store
    )
    kept_claims, kept_rels, kept_conf, items_truncated, items_category = (
        _select_answer_items(
            claims, relationships, conflicts_all, bounds.max_results
        )
    )
    locations = structural.locations(
        repository_id, sid, bounds
    ).items
    requirements: list[m.ResolutionRequirement] = []
    if resolution is not None:
        requirements.extend(_answers.requirements_for_resolution(resolution))
    for claim in kept_claims:
        requirements.extend(_answers.requirements_for_claim(claim))
    (kept_locs,), truncated_locs, category_locs, _ = (
        _answers.truncate_fields(
            ((locations, "locations"),),
            max(
                0,
                bounds.max_results
                - len(kept_conf) - len(kept_claims) - len(kept_rels),
            ),
        )
    )
    truncated = items_truncated or truncated_locs
    category = items_category if items_category is not None else category_locs
    views, qshown, qremaining = _paged_question_views(
        repository_id, scope_root or sid, (sid,),
        store=store, bounds=bounds, page_token=page_token,
        evidence=evidence,
    )
    if not views and not kept_claims and not kept_rels:
        requirements.append(
            m.ResolutionRequirement(
                kind=m.ResolutionKind.MISSING_SEMANTIC_COVERAGE,
                subject_or_claim=sid,
                description="no examined semantic question for subject",
                supporting_context=(),
            )
        )
    elif not views and (kept_claims or kept_rels):
        # B.8: legacy items without adopted question coverage stay
        # readable but explicitly unassessed for question sufficiency;
        # byte-current evidence never proves semantic sufficiency.
        requirements.append(
            m.ResolutionRequirement(
                kind=m.ResolutionKind.MISSING_SEMANTIC_COVERAGE,
                subject_or_claim=sid,
                description=(
                    "stored semantics predate question coverage; "
                    "unassessed for question sufficiency"
                ),
                supporting_context=(),
            )
        )
    if qremaining > 0:
        truncated = True
        category = category or "question_coverage"
        requirements.append(
            m.ResolutionRequirement(
                kind=m.ResolutionKind.INCOMPLETE_SEMANTIC_SCOPE,
                subject_or_claim=sid,
                description=(
                    f"{qremaining} question coverage entries truncated; "
                    "continue with page_token"
                ),
                supporting_context=(),
            )
        )
    content = m.ExplainContent(
        claims=kept_claims,
        relationships=kept_rels,
        implementation_locations=kept_locs,  # type: ignore[arg-type]
        conflicts=kept_conf,
        question_coverage=views,
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
        bound_info=_bound_info(
            bounds, returned, truncated, category,
            _next_service_token(
                page_token, kept_claims, kept_rels, claims, relationships,
                claims_token, rels_token,
                questions_skip=qshown,
                questions_remaining=qremaining,
            ),
        ),
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
    if not _is_initialized(request.repository_id, store=store):
        return _uninitialized_answer(
            m.SemanticIntent.EXPLAIN, request.repository_id, bounds, state
        )
    resolution = _resolve_query_subject(
        request.repository_id, request.target, structural=structural,
        store=store, bounds=bounds,
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
    if request.establish_baseline:
        if _baseline_sufficient(
            request.repository_id, subject.subject_id,
            store=store, evidence=evidence, bounds=bounds,
        ):
            return _compose_explain_answer(
                request.repository_id, subject, resolution,
                structural=structural, evidence=evidence, store=store,
                bounds=bounds, state=state, page_token=request.page_token,
                scope_root=subject.subject_id,
            )
        # Reissue recovery: never restart the audit while admitted work
        # exists — persisted coverage determines the next unit.
        nxt_cov = _next_baseline_pending(
            request.repository_id, subject,
            store=store, bounds=bounds,
        )
        if nxt_cov is not None:
            return _suspend_baseline_pending(
                request.repository_id, subject, nxt_cov,
                structural=structural, evidence=evidence, store=store,
                bounds=bounds, state=state, seeds=authority_seeds,
                resolution=resolution,
                continuations=continuations,
            )
        try:
            existing = store.load_all_question_coverages(
                request.repository_id, subject.subject_id,
                (subject.subject_id,),
            )
        except Exception:
            existing = ()
        audited = any(
            cov.question is not None
            and cov.question.question_class
            is m.SemanticQuestionClass.CQ_01
            and cov.question.subject == subject.subject_id
            for cov in existing
        )
        if audited:
            # Worklist exhausted but qualified (OPEN/similarly honest
            # states remain): serve the qualified answer, never a
            # redundant second audit.
            return _compose_explain_answer(
                request.repository_id, subject, resolution,
                structural=structural, evidence=evidence, store=store,
                bounds=bounds, state=state, page_token=request.page_token,
                scope_root=subject.subject_id,
            )
        task = prepare_interpretation_task(
            request.repository_id, subject, structural=structural,
            evidence=evidence, bounds=bounds, state=state,
            authority_seeds=authority_seeds,
            operation_intent=m.SemanticIntent.EXPLAIN,
            question_slice="",
            store=store,
            scope_root=subject.subject_id,
            establish_baseline=True,
        )
        return _suspend(
            op="explain", repository_id=request.repository_id,
            subject=subject, task=task, seeds=authority_seeds,
            bounds=bounds, state=state, resolution=resolution,
            continuations=continuations,
            operation_intent="EXPLAIN",
            question_slice=task.request.question_slice,
            establish_baseline=True,
        )
    claims, relationships, _, _ = _load_subject_state(
        request.repository_id, subject.subject_id,
        store=store, bounds=bounds,
    )
    missing_question = _question_local_missing(
        request.repository_id, subject, m.SemanticIntent.EXPLAIN,
        store=store, evidence=evidence, bounds=bounds,
    )
    if missing_question is not None:
        task = prepare_interpretation_task(
            request.repository_id, subject, structural=structural,
            evidence=evidence, bounds=bounds, state=state,
            authority_seeds=authority_seeds,
            operation_intent=m.SemanticIntent.EXPLAIN,
            question_slice=missing_question.question_slice,
            store=store,
            scope_root=missing_question.scope_root,
            question_class=missing_question.question_class,
            materiality_basis=missing_question.materiality_basis,
        )
        return _suspend(
            op="explain", repository_id=request.repository_id,
            subject=subject, task=task, seeds=authority_seeds,
            bounds=bounds, state=state, resolution=resolution,
            continuations=continuations,
            operation_intent="EXPLAIN",
            question_slice=missing_question.question_slice,
        )
    return _compose_explain_answer(
        request.repository_id, subject, resolution,
        structural=structural, evidence=evidence, store=store,
        bounds=bounds, state=state, page_token=request.page_token,
        scope_root=subject.subject_id,
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
    page_token: str | None = None,
) -> m.SemanticAnswer:
    sid = subject.subject_id
    claims, relationships, claims_token, rels_token = _load_subject_state(
        repository_id, sid, store=store, bounds=bounds,
        page_token=page_token,
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
    conflicts = _conflicts_for(
        repository_id, claims, relationships, store=store
    )
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
    views, qshown, qremaining = _paged_question_views(
        repository_id, sid, (sid,),
        store=store, bounds=bounds, page_token=page_token,
        evidence=evidence,
    )
    if qremaining > 0:
        truncated = True
        category = category or "question_coverage"
    content = m.AuthorityContent(
        governing_bindings=kept_bindings,  # type: ignore[arg-type]
        supersession=kept_super,  # type: ignore[arg-type]
        precedence=kept_prec,  # type: ignore[arg-type]
        claims=claims,
        relationships=relationships,
        conflicts=kept_conflicts,  # type: ignore[arg-type]
        unresolved=kept_unresolved,  # type: ignore[arg-type]
        question_coverage=views,
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
            bounds, len(kept_bindings), truncated, category,
            _next_service_token(
                page_token, claims, relationships, claims, relationships,
                claims_token, rels_token,
                questions_skip=qshown,
                questions_remaining=qremaining,
            ) or token,
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
        bounds = _resolve_bounds(request.bounds, hook=False)
        state = structural.repository_state(request.repository_id)
        try:
            (item,) = store.load_by_refs(
                request.repository_id, (request.target,)
            )
        except ValueError as exc:
            raise AuthorityTargetError(str(exc)) from None
        if not isinstance(item, m.SemanticClaim):
            raise AuthorityTargetError("claim ref did not resolve to a claim")
        subjects = store.load_subjects(
            request.repository_id, (item.subject,)
        )
        if not subjects:
            raise AuthorityTargetError("claim subject is not indexed")
        return _compose_authority_answer(
            request.repository_id, subjects[0], None,
            structural=structural, evidence=evidence, store=store,
            bounds=bounds, state=state,
        )
    bounds = _resolve_bounds(request.bounds, hook=False)
    state = structural.repository_state(request.repository_id)
    if not _is_initialized(request.repository_id, store=store):
        return _uninitialized_answer(
            m.SemanticIntent.AUTHORITY, request.repository_id, bounds, state
        )
    resolution = _resolve_query_subject(
        request.repository_id, request.target, structural=structural,
        store=store, bounds=bounds,
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
    missing_question = _question_local_missing(
        request.repository_id, subject, m.SemanticIntent.AUTHORITY,
        store=store, evidence=evidence, bounds=bounds,
    )
    if missing_question is not None:
        task = prepare_interpretation_task(
            request.repository_id, subject, structural=structural,
            evidence=evidence, bounds=bounds, state=state,
            authority_seeds=authority_seeds,
            operation_intent=m.SemanticIntent.AUTHORITY,
            question_slice=missing_question.question_slice,
            store=store,
            scope_root=missing_question.scope_root,
            question_class=missing_question.question_class,
            materiality_basis=missing_question.materiality_basis,
        )
        return _suspend(
            op="authority", repository_id=request.repository_id,
            subject=subject, task=task, seeds=authority_seeds,
            bounds=bounds, state=state, resolution=resolution,
            continuations=continuations,
            operation_intent="AUTHORITY",
            question_slice=missing_question.question_slice,
        )
    return _compose_authority_answer(
        request.repository_id, subject, resolution,
        structural=structural, evidence=evidence, store=store,
        bounds=bounds, state=state, page_token=request.page_token,
    )


# ---------------------------------------------------------------------------
# Explicit refresh (plan §9.5)
# ---------------------------------------------------------------------------

def _resolve_scope_subjects(
    repository_id: str,
    target: m.SubjectSelector | m.EvidenceScope,
    *,
    structural: StructuralSource,
    store: SemanticStore,
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
    resolution = _resolve_query_subject(
        repository_id, target, structural=structural, store=store,
        bounds=bounds,
    )
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
        ),
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
            "repo-wide refresh requires Phase 3 subject enumeration"
        )
    subjects, ambiguity = _resolve_scope_subjects(
        request.repository_id, request.target,
        structural=structural, store=store, bounds=bounds,
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
        )
    first, rest = affected[0], affected[1:]
    # B.3/B-06: refresh re-examines under the persisted stale question
    # scope — never a fresh generic question and never a silent
    # baseline expansion. Only subjects with no persisted questions
    # fall back to a STATUS question-local unit.
    first_stale = _stale_question_scopes(
        request.repository_id, first,
        store=store, evidence=evidence, bounds=bounds,
    )
    first_scope = first_stale[0] if first_stale else None
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
    return _suspend(
        op="refresh", repository_id=request.repository_id, subject=first,
        task=task, seeds=authority_seeds, bounds=bounds, state=state,
        resolution=None, scope=subjects, remaining=rest,
        changed=tuple(changed_deps), continuations=continuations,
        operation_intent="STATUS",
        question_slice=task.request.question_slice,
        declared_complete=True,
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
    authority seeds (caller-held session config — the §10.2 schema
    carries no config table), persists the repository state record,
    and initializes the semantic store schema. Performs NO agent
    semantic interpretation: there is no interpretation input by
    construction.
    """
    if not request.repository_locator:
        raise ValueError("repository_locator must be non-empty")
    policy_bounds = bounds or DEFAULT_SERVICE_BOUNDS_POLICY.maximum_query_bounds
    state = structural.repository_state(repository_id)
    store.record_repository_state(state)
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
    # §4.8/I-31: readiness is operational — whether the repository can
    # service semantic operations — never inventory completeness.
    # Partial inventory is boundedness (§8.4), carried in
    # evidence_inventory_status and warnings, and the HOOK_FAST path
    # likewise reports READY once initialized (plan Q34: readiness
    # must not be confused with freshness/boundedness).
    readiness = m.RepositoryReadiness.READY
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


def _resolve_query_subject(
    repository_id: str,
    target: m.SubjectSelector,
    *,
    structural: StructuralSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> m.SubjectResolution:
    """Query-time subject resolution (addendum A, F1).

    Structural first; on NOT_FOUND with an exact identity, fall back
    to the stored subject record (registered semantic-only subjects
    live in the store, never in the structural source). Ambiguity is
    never overridden and name-only queries never reach the store
    (§4.2: names alone are never identity).
    """
    resolution = structural.resolve_subject(repository_id, target, bounds)
    if resolution.ambiguity is m.ResolutionAmbiguity.RESOLVED:
        return resolution
    if (
        resolution.ambiguity is m.ResolutionAmbiguity.NOT_FOUND
        and target.exact_subject_id is not None
    ):
        found = store.load_subjects(
            repository_id, (target.exact_subject_id,)
        )
        if found:
            return m.SubjectResolution(
                candidates=(
                    m.SubjectCandidate(
                        subject=found[0],
                        structural_evidence=(),
                        rank_basis=m.CandidateRankBasis.EXACT_LOCATOR,
                    ),
                ),
                ambiguity=m.ResolutionAmbiguity.RESOLVED,
                bound_info=m.BoundInfo(
                    requested_max_results=bounds.max_subjects,
                    requested_max_depth=0,
                    returned_results=1,
                    truncated=False,
                    truncated_category=None,
                    continuation_token=None,
                ),
            )
    return resolution


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
    page_token: str | None = None,
) -> m.SemanticAnswer | PendingInterpretation:
    """Bounded iterative frontier expansion (plan §8.6) with suspension.

    Expands one deterministic frontier at a time. The first subject with
    no semantic state that was not already suspended suspends the
    operation (§11.12); resume restarts the deterministic walk, so each
    subject is requested at most once and the walk always terminates.

    Paging (plan I-39): `page_token` windows the target subject's
    initial state load only; frontier expansion loads proceed unpaged.
    Page deep results through narrower targets.
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
    target_windowed = False
    while queue and len(rels) + len(sedges) < bounds.max_results:
        sid, depth = queue.pop(0)
        locator = sid.canonical_locator
        if locator in visited:
            continue
        visited.append(locator)
        window = None if target_windowed else page_token
        target_windowed = True
        loaded_claims, loaded_rels, _, _ = _load_subject_state(
            repository_id, sid, store=store, bounds=bounds,
            direction=direction, page_token=window,
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
                    operation_intent=m.SemanticIntent.TRACE,
                    question_slice=full.subject_id.canonical_locator,
                )
                return _suspend(
                    op="trace", repository_id=repository_id, subject=full,
                    task=task, seeds=seeds, bounds=bounds, state=state,
                    resolution=resolution, scope=(target,),
                    suspended=suspended + (locator,),
                    operation_intent="TRACE",
                    question_slice=full.subject_id.canonical_locator,
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
    page_token: str | None = None,
) -> m.SemanticAnswer:
    ids: tuple[m.ClaimRef | m.RelationshipRef, ...] = tuple(
        _claim_ref(c) for c in claims
    ) + tuple(_relationship_ref(r) for r in relationships)
    updates = preflight(
        repository_id, ids, evidence=evidence, store=store, bounds=bounds
    )
    fresh_by_id = {u.semantic_id.id.value: u.freshness for u in updates}

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
    conflicts_all = _conflicts_for(
        repository_id, claims, relationships, store=store
    )
    kept_claims, kept_rels, kept_conf, items_truncated, items_category = (
        _select_answer_items(
            claims, relationships, conflicts_all, bounds.max_results
        )
    )
    kept_ids = {c.claim_id.value for c in kept_claims} | {
        r.relationship_id.value for r in kept_rels
    }
    boundary_ids: list[m.SubjectId] = []
    lifecycle_refs: list[m.ClaimRef | m.RelationshipRef] = []
    for claim in kept_claims:
        if claim.kind is m.ClaimKind.LIFECYCLE_STATE:
            lifecycle_refs.append(_claim_ref(claim))
    for rel in kept_rels:
        if rel.kind in (
            m.RelationshipKind.TRANSITIONS_TO,
            m.RelationshipKind.PERSISTS_AT,
        ):
            lifecycle_refs.append(_relationship_ref(rel))
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
    for rel in kept_rels:
        requirements.extend(_answers.requirements_for_relationship(rel))
    for claim in kept_claims:
        requirements.extend(_answers.requirements_for_claim(claim))
    (kept_boundary, kept_edges), truncated, category, token = (
        _answers.truncate_fields(
            (
                (tuple(boundary_ids), "boundary_context"),
                (structural_edges, "structural_edges"),
            ),
            max(0, bounds.max_results - len(kept_conf) - len(kept_rels)),
        )
    )
    truncated = truncated or items_truncated
    if category is None:
        category = items_category
    sid = subject.subject_id
    views, _, qremaining = _paged_question_views(
        repository_id, sid, (sid,),
        store=store, bounds=bounds, page_token=page_token,
        evidence=evidence,
    )
    if qremaining > 0:
        truncated = True
        category = category or "question_coverage"
    content = m.TraceContent(
        relationships=kept_rels,  # type: ignore[arg-type]
        structural_edges=kept_edges,  # type: ignore[arg-type]
        boundary_context=kept_boundary,  # type: ignore[arg-type]
        lifecycle_context=tuple(lifecycle_refs),
        claims=kept_claims,
        conflicts=kept_conf,
        question_coverage=views,
    )
    returned = (
        len(kept_conf) + len(kept_rels) + len(lifecycle_refs)
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
    frontier interpretation is missing; never interprets inline.

    Paging (plan I-39): `page_token` windows the target subject's
    initial state load only; frontier expansion loads proceed unpaged.
    Page deep results through narrower targets."""
    bounds = _resolve_bounds(request.bounds, hook=False)
    state = structural.repository_state(request.repository_id)
    if not _is_initialized(request.repository_id, store=store):
        return _uninitialized_answer(
            m.SemanticIntent.TRACE, request.repository_id, bounds, state
        )
    resolution = _resolve_query_subject(
        request.repository_id, request.target, structural=structural,
        store=store, bounds=bounds,
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
        page_token=request.page_token,
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
    semantic_ids: tuple[m.ClaimRef | m.RelationshipRef, ...],
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
    if not _is_initialized(repository_id, store=store):
        return m.HookStatusNotice(
            readiness=m.RepositoryReadiness.UNINITIALIZED,
            recommended_action=(
                "run initialize_repository in a dedicated "
                "setup session"
            ),
        )
    if target is None:
        return m.HookStatusNotice(
            readiness=m.RepositoryReadiness.READY
        )
    subjects, _ = _resolve_scope_subjects(
        repository_id, target, structural=structural, store=store,
        bounds=bounds,
    )
    affected: list[m.SubjectId] = []
    stale = 0
    unverifiable = 0
    for subject in subjects:
        claims, relationships, _, _ = _load_subject_state(
            repository_id, subject.subject_id, store=store, bounds=bounds
        )
        ids: tuple[m.ClaimRef | m.RelationshipRef, ...] = tuple(
            _claim_ref(c) for c in claims
        ) + tuple(_relationship_ref(r) for r in relationships)
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
    # Seed reliance is explicit: a moved or missing authority seed
    # marks its scope stale even with quiet direct dependencies.
    # Inventory-membership changes alone stay silent here (I-32: a new
    # file has no dependants); queries surface them via coverage.
    coverages = store.load_coverage_dependencies(
        repository_id,
        tuple(s.subject_id for s in subjects),
    )
    coverages = _latest_coverages(coverages)
    seed_refs = tuple(
        dict.fromkeys(
            m.EvidenceRef(
                evidence_id=seed.evidence_id,
                repository_id=repository_id,
                source_kind=m.EvidenceSourceKind.USER_PROJECT_CONFIG,
                locator=seed.locator or seed.evidence_id.value,
            )
            for coverage in coverages
            for seed in coverage.seed_fingerprints
        )
    )
    seed_current: dict[str, str | None] = {}
    if seed_refs:
        seed_page = evidence.inventory_evidence(
            repository_id,
            m.EvidenceScope(paths=(), evidence_refs=seed_refs),
            bounds,
        )
        seed_current = {
            item.evidence_ref.evidence_id.value: item.content_fingerprint
            for item in seed_page.items
        }
    for coverage in coverages:
        if not coverage.seed_fingerprints:
            continue
        seed_moved = any(
            seed_current.get(seed.evidence_id.value) != seed.fingerprint
            for seed in coverage.seed_fingerprints
        )
        if not seed_moved:
            continue
        for sid in coverage.scope_subjects:
            if sid not in affected:
                affected.append(sid)
            claims, relationships, _, _ = _load_subject_state(
                repository_id, sid, store=store, bounds=bounds
            )
            stale += len(claims) + len(relationships)
    action = None
    if stale or unverifiable:
        action = (
            f"run refresh: {stale} stale, "
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
    page_token: str | None = None,
) -> m.SemanticAnswer:
    all_claims: list[m.SemanticClaim] = []
    all_rels: list[m.SemanticRelationship] = []
    first_claims_token: str | None = None
    first_rels_token: str | None = None
    for position, subject in enumerate(subjects):
        claims, relationships, tok_c, tok_r = _load_subject_state(
            repository_id, subject.subject_id, store=store, bounds=bounds,
            page_token=page_token if len(subjects) == 1 else None,
        )
        all_claims.extend(claims)
        all_rels.extend(relationships)
        if position == 0:
            first_claims_token, first_rels_token = tok_c, tok_r
    # Classify before the view persists anything: _refresh_view marks
    # state, after which a second classification would always report
    # clean and changed_dependencies would always be empty.
    pre_ids: tuple[m.ClaimRef | m.RelationshipRef, ...] = tuple(
        _claim_ref(c) for c in all_claims
    ) + tuple(_relationship_ref(r) for r in all_rels)
    updates, dependencies = _classify_current(
        repository_id, pre_ids, evidence=evidence, store=store, bounds=bounds
    )
    updated_ids = {u.semantic_id.id.value for u in updates}
    changed = tuple(
        dep for dep in dependencies if dep.semantic_id.id.value in updated_ids
    )
    stale_evidence = {
        dep.evidence_ref.locator
        for dep in dependencies
        if dep.semantic_id.id.value in updated_ids
    }
    claims_t, rels_t = _refresh_view(
        repository_id, tuple(all_claims), tuple(all_rels),
        evidence=evidence, store=store, bounds=bounds,
    )
    verification_all = tuple(
        claim.value
        for claim in claims_t
        if claim.kind is m.ClaimKind.VERIFICATION
        and isinstance(claim.value, m.VerificationValue)
    )
    conflicts_all = _conflicts_for(
        repository_id, tuple(claims_t), tuple(rels_t), store=store
    )
    kept_claims, kept_rels, kept_conf, items_truncated, items_category = (
        _select_answer_items(
            claims_t, rels_t, conflicts_all, bounds.max_results
        )
    )
    kept_ids = {c.claim_id.value for c in kept_claims} | {
        r.relationship_id.value for r in kept_rels
    }
    changed_kept = tuple(
        dep for dep in changed
        if dep.semantic_id.id.value in kept_ids
    )
    unresolved: list[m.ResolutionRequirement] = []
    for claim in kept_claims:
        unresolved.extend(_answers.requirements_for_claim(claim))
    for rel in kept_rels:
        unresolved.extend(_answers.requirements_for_relationship(rel))
    # Non-ref lists (evidence pointers and values, never semantic refs)
    # take the remaining budget deterministically.
    rest_budget = max(
        0, bounds.max_results - len(kept_conf) - len(kept_claims)
    )
    kept_unresolved = tuple(unresolved[:rest_budget])
    kept_changed = changed_kept[: max(0, rest_budget - len(kept_unresolved))]
    kept_ver = verification_all[
        : max(0, rest_budget - len(kept_unresolved) - len(kept_changed))
    ]
    truncated = items_truncated or (
        len(kept_unresolved) + len(kept_changed) + len(kept_ver)
        < len(unresolved) + len(changed_kept) + len(verification_all)
    )
    category = items_category
    if category is None and truncated:
        category = "unresolved"
    if len(subjects) == 1:
        views, qshown, qremaining = _paged_question_views(
            repository_id, subjects[0].subject_id,
            tuple(s.subject_id for s in subjects),
            store=store, bounds=bounds, page_token=page_token,
            evidence=evidence,
        )
        token: str | None = _next_service_token(
            page_token, kept_claims, kept_rels, claims_t, rels_t,
            first_claims_token, first_rels_token,
            questions_skip=qshown,
            questions_remaining=qremaining,
        )
    else:
        views, _, qremaining = _paged_question_views(
            repository_id, None,
            tuple(s.subject_id for s in subjects),
            store=store, bounds=bounds, page_token=None,
            evidence=evidence,
        )
        token = None
    if qremaining > 0:
        truncated = True
        category = category or "question_coverage"
    content = m.StatusContent(
        readiness=m.RepositoryReadiness.READY,
        freshness_items=_freshness_items_for(kept_claims, kept_rels),
        changed_dependencies=kept_changed,  # type: ignore[arg-type]
        verification_currency=kept_ver,  # type: ignore[arg-type]
        refresh_scope=m.EvidenceScope(
            paths=tuple(sorted(stale_evidence)), evidence_refs=()
        ),
        claims=kept_claims,
        relationships=kept_rels,
        conflicts=kept_conf,
        unresolved=tuple(unresolved),
        question_coverage=views,
    )
    returned = (
        len(kept_conf) + len(unresolved) + len(kept_claims)
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
        evidence=tuple(ref for c in kept_claims for ref in c.evidence),
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
    never writes. Claim/relationship targets resolve through the §5.5
    ref lookup; answer envelopes are never persisted (StatusTargetError).

    Paging (plan I-39): `page_token` carries per-list offsets redeemed
    for single-subject and ref targets (composite `pg:<claims>:<rels>`
    cursors). Multi-subject scopes load unpaged; page them through
    narrower single-subject targets.
    """
    if isinstance(request.target, m.AnswerRef):
        raise StatusTargetError(
            "answer envelopes are not persisted; status serves "
            "subject, claim, relationship, and evidence-scope targets"
        )
    bounds = _resolve_bounds(request.bounds, hook=False)
    if request.mode is m.StatusMode.HOOK_FAST:
        return _hook_fast(
            request.repository_id, request.target,
            structural=structural, evidence=evidence, store=store,
            bounds=bounds,
        )
    if isinstance(request.target, (m.ClaimRef, m.RelationshipRef)):
        try:
            (item,) = store.load_by_refs(
                request.repository_id, (request.target,)
            )
        except ValueError as exc:
            raise StatusTargetError(str(exc)) from None
        state = structural.repository_state(request.repository_id)
        if not _is_initialized(request.repository_id, store=store):
            return _uninitialized_answer(
                m.SemanticIntent.STATUS, request.repository_id,
                bounds, state,
            )
        sid = (
            item.subject
            if isinstance(item, m.SemanticClaim)
            else item.source
        )
        subjects = store.load_subjects(request.repository_id, (sid,))
        if not subjects:
            raise StatusTargetError("referenced subject is not indexed")
        return _compose_status_answer(
            request.repository_id, subjects, structural=structural,
            evidence=evidence, store=store, bounds=bounds, state=state,
            page_token=request.page_token,
        )
    state = structural.repository_state(request.repository_id)
    if not _is_initialized(request.repository_id, store=store):
        return _uninitialized_answer(
            m.SemanticIntent.STATUS, request.repository_id, bounds, state
        )
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
        structural=structural, store=store, bounds=bounds,
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
        suspended=(), evidence=evidence,
    )
    if missing is not None:
        needed = _question_local_missing(
            request.repository_id, missing, m.SemanticIntent.STATUS,
            store=store, evidence=evidence, bounds=bounds,
        )
        task = prepare_interpretation_task(
            request.repository_id, missing, structural=structural,
            evidence=evidence, bounds=bounds, state=state,
            authority_seeds=authority_seeds,
            operation_intent=m.SemanticIntent.STATUS,
            question_slice=(
                needed.question_slice if needed is not None
                else missing.subject_id.canonical_locator
            ),
            store=store,
            scope_root=(
                needed.scope_root if needed is not None
                else missing.subject_id
            ),
            question_class=(
                needed.question_class if needed is not None else None
            ),
            materiality_basis=(
                needed.materiality_basis if needed is not None else ""
            ),
        )
        return _suspend(
            op="status", repository_id=request.repository_id,
            subject=missing, task=task, seeds=authority_seeds,
            bounds=bounds, state=state, resolution=None, scope=subjects,
            suspended=(missing.subject_id.canonical_locator,),
            continuations=continuations,
            operation_intent="STATUS",
            question_slice=task.request.question_slice,
        )
    return _compose_status_answer(
        request.repository_id, subjects, structural=structural,
        evidence=evidence, store=store, bounds=bounds, state=state,
        page_token=request.page_token,
    )


def _missing_subjects(
    repository_id: str,
    subjects: tuple[m.Subject, ...],
    *,
    store: SemanticStore,
    bounds: m.QueryBounds,
    suspended: tuple[str, ...],
    evidence: EvidenceSource | None = None,
) -> m.Subject | None:
    """First subject with unexamined question-local state (B.7).

    Question-aware: a subject is missing when its STATUS primary
    question (CQ_09) or any admitted PENDING question lacks
    effective-current coverage — never merely when claims are absent.
    """
    for subject in subjects:
        if subject.subject_id.canonical_locator in suspended:
            continue
        missing = _question_local_missing(
            repository_id, subject, m.SemanticIntent.STATUS,
            store=store, evidence=evidence, bounds=bounds,
        )
        if missing is not None:
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
        suspended=suspended, evidence=evidence,
    )
    if missing is not None:
        needed = _question_local_missing(
            record.repository_id, missing, m.SemanticIntent.STATUS,
            store=store, evidence=evidence, bounds=bounds,
        )
        task = prepare_interpretation_task(
            record.repository_id, missing, structural=structural,
            evidence=evidence, bounds=bounds, state=state,
            authority_seeds=record.seeds,
            operation_intent=m.SemanticIntent.STATUS,
            question_slice=(
                needed.question_slice if needed is not None
                else missing.subject_id.canonical_locator
            ),
            store=store,
            scope_root=(
                needed.scope_root if needed is not None
                else missing.subject_id
            ),
            question_class=(
                needed.question_class if needed is not None else None
            ),
            materiality_basis=(
                needed.materiality_basis if needed is not None else ""
            ),
        )
        return _suspend(
            op="status", repository_id=record.repository_id,
            subject=missing, task=task, seeds=record.seeds,
            bounds=bounds, state=state, resolution=None,
            scope=record.scope, suspended=suspended,
            continuations=continuations,
            operation_intent="STATUS",
            question_slice=task.request.question_slice,
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
    affected_assertions: tuple[m.ClaimRef | m.RelationshipRef, ...] = (),
) -> tuple[m.ChangeCondition, ...]:
    """Deterministic ChangeCondition derivation (plan §11.5.1, I-38).

    Dimension flags, never severity/confidence/approval scores. Presence
    rows fire on established canonical state; kind-gated rows additionally
    require the stated change_kind. Proposal-sensitive rows fire only for
    typed affected assertions resolved against current canonical state;
    proposal prose is never mined. `OTHER` suppresses kind-gated rows
    only — independently established dimensions still apply.
    """
    sid = target.subject_id
    established_claims = {
        c.claim_id.value: c
        for c in claims
        if c.trust is m.TrustState.ESTABLISHED
    }
    established_rels = {
        r.relationship_id.value: r
        for r in relationships
        if r.trust is m.TrustState.ESTABLISHED
    }
    affected = {_ref_value(ref) for ref in affected_assertions}
    rel_kinds = {r.kind for r in relationships}
    has_kind = change_kind is not ChangeKind.OTHER
    conditions: list[m.ChangeCondition] = []
    if any(
        value in established_claims
        and established_claims[value].authority is not None
        and established_claims[value].authority.status
        is m.AuthorityStatus.ACCEPTED
        and established_claims[value].freshness.state
        is m.FreshnessState.CURRENT
        for value in affected
    ) or any(
        value in established_rels
        and established_rels[value].kind is m.RelationshipKind.GOVERNED_BY
        for value in affected
    ):
        conditions.append(m.ChangeCondition.AUTHORITY_CHANGE)
    if has_kind and change_kind is ChangeKind.OWNERSHIP:
        conditions.append(m.ChangeCondition.OWNERSHIP_CHANGE)
    elif any(
        value in established_claims
        and established_claims[value].kind
        in (
            m.ClaimKind.OWNERSHIP_CUSTODY,
            m.ClaimKind.TRANSFORMATION_OWNERSHIP,
        )
        for value in affected
    ):
        conditions.append(m.ChangeCondition.OWNERSHIP_CHANGE)
    if (
        has_kind
        and change_kind is ChangeKind.REPRESENTATION
        and (
            any(
                c.kind is m.ClaimKind.REPRESENTATION_CONTRACT
                for c in established_claims.values()
            )
            or m.RelationshipKind.REPRESENTS_AS in rel_kinds
        )
    ):
        conditions.append(m.ChangeCondition.CANONICAL_REPRESENTATION_CHANGE)
    target_item_ids = {
        c.claim_id.value for c in claims if c.subject == sid
    } | {
        r.relationship_id.value
        for r in relationships
        if r.source == sid or r.target == sid
    }
    if any(
        value in established_rels
        and established_rels[value].kind
        is m.RelationshipKind.CROSSES_BOUNDARY
        for value in affected
    ) or (
        sid.subject_kind is m.SubjectKind.BOUNDARY
        and bool(affected & target_item_ids)
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
    if any(
        value in established_claims
        and established_claims[value].kind
        is m.ClaimKind.INVARIANT_CONSTRAINT
        for value in affected
    ):
        conditions.append(m.ChangeCondition.INVARIANT_CHANGE)
    if (
        has_kind
        and change_kind is ChangeKind.CONFIGURATION
        or any(
            c.kind is m.ClaimKind.CONFIGURATION_ENVIRONMENT
            for c in established_claims.values()
        )
        or m.RelationshipKind.CONFIGURED_BY in rel_kinds
    ):
        conditions.append(m.ChangeCondition.CONFIGURATION_CHANGE)
    if (
        has_kind
        and change_kind is ChangeKind.LIFECYCLE
        or any(
            c.kind is m.ClaimKind.LIFECYCLE_STATE
            for c in established_claims.values()
        )
        or m.RelationshipKind.TRANSITIONS_TO in rel_kinds
        or m.RelationshipKind.PERSISTS_AT in rel_kinds
    ):
        conditions.append(m.ChangeCondition.LIFECYCLE_CHANGE)
    if any(
        value in established_claims
        and established_claims[value].kind is m.ClaimKind.VERIFICATION
        for value in affected
    ) or any(
        value in established_rels
        and established_rels[value].kind is m.RelationshipKind.VERIFIED_BY
        for value in affected
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
    affected_assertions: tuple[m.ClaimRef | m.RelationshipRef, ...] = (),
    seeds: tuple[m.EvidenceRef, ...] = (),
    suspended: tuple[str, ...] = (),
    page_token: str | None = None,
) -> m.SemanticAnswer | PendingInterpretation:
    # change_description is carried on suspend/resume for agent context but
    # never text-mined: proposal-content inference would violate AP-01.
    proposal = m.ProposedChange(
        change_kind=change_kind,
        change_description=change_description,
        affected_assertions=affected_assertions,
    )
    sid = subject.subject_id
    claims, relationships, _, _ = _load_subject_state(
        repository_id, sid, store=store, bounds=bounds,
        page_token=page_token if not suspended else None,
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
                    operation_intent=m.SemanticIntent.IMPACT,
                    question_slice=full.subject_id.canonical_locator,
                    proposed_change=proposal,
                )
                return _suspend(
                    op="impact", repository_id=repository_id,
                    subject=full, task=task, seeds=seeds,
                    bounds=bounds, state=state, resolution=resolution,
                    scope=(subject,),
                    suspended=suspended + (sid.canonical_locator,),
                    change_kind=change_kind.value,
                    change_description=change_description,
                    affected_assertions=affected_assertions,
                    operation_intent="IMPACT",
                    question_slice=full.subject_id.canonical_locator,
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
        loaded_c, loaded_r, _, _ = _load_subject_state(
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
                    operation_intent=m.SemanticIntent.IMPACT,
                    question_slice=full.subject_id.canonical_locator,
                    proposed_change=proposal,
                )
                return _suspend(
                    op="impact", repository_id=repository_id,
                    subject=full, task=task, seeds=seeds,
                    bounds=bounds, state=state, resolution=resolution,
                    scope=(subject,),
                    suspended=suspended + (locator,),
                    change_kind=change_kind.value,
                    change_description=change_description,
                    affected_assertions=affected_assertions,
                    operation_intent="IMPACT",
                    question_slice=full.subject_id.canonical_locator,
                    continuations=continuations,
                )
        node_claims[locator] = loaded_c
        node_rels[locator] = loaded_r
    target_rels = [
        r for r in relationships
        if r.source == sid or r.target == sid
    ]
    conditions = _derive_change_conditions(
        change_kind, subject, claims, tuple(target_rels),
        affected_assertions=affected_assertions,
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
                    _item_ref(i) for i in questionable
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
                    _relationship_ref(r) for r in established
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
                    _claim_ref(c) for c in claims_here
                ),
                relevant_relationships=tuple(
                    _relationship_ref(r)
                    for r in list(rels_here) + established
                ),
            )
        )
    target_context: tuple[m.ClaimRef | m.RelationshipRef, ...] = tuple(
        [_claim_ref(c) for c in claims]
        + [_relationship_ref(r) for r in relationships]
    )
    verification: tuple[m.ClaimRef | m.RelationshipRef, ...] = tuple(
        [_claim_ref(c) for c in claims if c.kind is m.ClaimKind.VERIFICATION]
        + [
            _relationship_ref(r)
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
    conflicts_all = _conflicts_for(
        repository_id, tuple(all_claims), tuple(all_rels), store=store
    )
    kept_claims, kept_rels, kept_conf, items_truncated, items_category = (
        _select_answer_items(
            tuple(all_claims), tuple(all_rels), conflicts_all,
            bounds.max_results,
        )
    )
    kept_ids = {c.claim_id.value for c in kept_claims} | {
        r.relationship_id.value for r in kept_rels
    }
    kept_context = tuple(
        ref for ref in target_context if _ref_value(ref) in kept_ids
    )
    kept_ver = tuple(
        ref for ref in verification if _ref_value(ref) in kept_ids
    )
    unresolved: list[m.ResolutionRequirement] = []
    if resolution is not None:
        unresolved.extend(_answers.requirements_for_resolution(resolution))
    for claim in kept_claims:
        unresolved.extend(_answers.requirements_for_claim(claim))
    for rel in kept_rels:
        unresolved.extend(_answers.requirements_for_relationship(rel))
    kept_impacts = tuple(
        m.ImpactItem(
            subject=item.subject,
            establishment=item.establishment,
            basis=item.basis,
            structural_evidence=item.structural_evidence,
            relevant_claims=tuple(
                ref for ref in item.relevant_claims
                if _ref_value(ref) in kept_ids
            ),
            relevant_relationships=tuple(
                ref for ref in item.relevant_relationships
                if _ref_value(ref) in kept_ids
            ),
        )
        for item in items
    )
    rest_budget = max(
        0,
        bounds.max_results
        - len(kept_conf) - len(kept_context) - len(kept_ver)
        - len(kept_claims) - len(kept_rels) - len(unresolved),
    )
    kept_impacts = kept_impacts[:rest_budget]
    kept_conds = conditions[: max(0, rest_budget - len(kept_impacts))]
    truncated = items_truncated or (
        len(kept_impacts) < len(items) or len(kept_conds) < len(conditions)
    )
    category = items_category
    if category is None and truncated:
        category = "impacts"
    views, _, qremaining = _paged_question_views(
        repository_id, sid, (sid,),
        store=store, bounds=bounds, page_token=page_token,
        evidence=evidence,
    )
    if qremaining > 0:
        truncated = True
        category = category or "question_coverage"
    content = m.ImpactContent(
        target_context=kept_context,
        change_conditions=kept_conds,
        impacts=kept_impacts,
        verification=kept_ver,
        claims=kept_claims,
        relationships=kept_rels,
        conflicts=kept_conf,
        unresolved=tuple(unresolved),
        question_coverage=views,
    )
    returned = (
        len(kept_conf) + len(unresolved) + len(kept_impacts)
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
        evidence=tuple(ref for c in kept_claims for ref in c.evidence),
        resolution_requirements=tuple(unresolved),
        bound_info=_bound_info(bounds, returned, truncated, category, None),
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

    Paging (plan I-39): `page_token` windows the target subject's
    initial state load only; downstream node loads proceed unpaged.
    Page deep results through narrower targets.
    """
    bounds = _resolve_bounds(request.bounds, hook=False)
    state = structural.repository_state(request.repository_id)
    if not _is_initialized(request.repository_id, store=store):
        return _uninitialized_answer(
            m.SemanticIntent.IMPACT, request.repository_id, bounds, state
        )
    resolution = _resolve_query_subject(
        request.repository_id, request.target, structural=structural,
        store=store, bounds=bounds,
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
        affected_assertions=request.affected_assertions,
        seeds=authority_seeds, suspended=(),
        page_token=request.page_token,
    )
