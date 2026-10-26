"""Status page delivery: identity, token, and the live freshness overlay."""

from __future__ import annotations

import dataclasses as _dataclasses

from span.core import model as m
from span.core.paging import INVALID_PAGE_TOKEN_MESSAGE
from span.ports.evidence import EvidenceSource
from span.ports.store import SemanticStore
from span.ports.structural import StaleContinuationError

from span.service.answers import (
    _conflicts_for,
    _query_digest,
    _validate_service_token,
)
from span.service.freshness import (
    _evaluate_current,
    with_freshness,
)
from span.service.questions import (
    _paged_question_views,
)
from span.service.refs import (
    _claim_ref,
    _relationship_ref,
)
from span.service.resolution import (
    _load_subject_state,
)
from span.service.operations.status.coverage import (
    _derived_verification_status,
)
from span.service.operations.status.tokens import (
    _format_question_token,
    _parse_scope_token,
)


@_dataclasses.dataclass
class _PageIdentity:
    """The page's version digest and, for one subject, its item cursor."""

    digest: str
    subject_page_token: str | None


@_dataclasses.dataclass
class _Delivered:
    """The live overlay of everything this page delivers before selection."""

    claims: tuple[m.SemanticClaim, ...]
    relationships: tuple[m.SemanticRelationship, ...]
    live_states: dict[str, m.FreshnessState]
    changed: tuple[m.EvidenceDependency, ...]
    stale_evidence: set[str]
    verification: tuple[m.VerificationStatus, ...]
    conflicts: tuple[m.SemanticConflict, ...]
    claims_token: str | None
    relationships_token: str | None


def _page_identity(
    repository_id: str,
    subjects: tuple[m.Subject, ...],
    *,
    bounds: m.QueryBounds,
    page_token: str | None,
    scope: m.EvidenceScope | None,
    item_cursor: tuple[int, int, int],
    frontier: str,
) -> _PageIdentity:
    """Resolve the page's version and validate the token naming it."""
    if scope is not None:
        # A scope cursor identifies the scope, never the page that returned
        # it: every resume resolves a different page, so a page-derived key
        # can never match the token it was issued with. Membership drift is
        # still caught by ``frontier``, which is part of the version (J-10).
        target_key = "scope:" + m.evidence_scope_fingerprint(scope)
    elif len(subjects) == 1:
        subject_id = subjects[0].subject_id
        target_key = f"{subject_id.subject_kind.value}:{subject_id.canonical_locator}"
    else:
        target_key = "scope:" + ",".join(
            sorted(
                f"{subject.subject_id.subject_kind.value}:"
                f"{subject.subject_id.canonical_locator}"
                for subject in subjects
            )
        )
    digest = _query_digest("STATUS", repository_id, target_key, "", bounds)
    if scope is None:
        _validate_service_token(page_token, digest)
        return _PageIdentity(
            digest=digest,
            subject_page_token=page_token if len(subjects) == 1 else None,
        )
    # The scope cursor names the frontier position and, when one subject did
    # not fit, that subject's item offsets. Drift in membership or request
    # restarts the listing; item offsets never substitute for a version check.
    if page_token is not None:
        if not frontier:
            raise StaleContinuationError(INVALID_PAGE_TOKEN_MESSAGE)
        _parse_scope_token(page_token, version=digest + frontier)
    return _PageIdentity(
        digest=digest,
        subject_page_token=(
            _format_question_token(digest, *item_cursor) if any(item_cursor) else None
        ),
    )


def _live_freshness(
    repository_id: str,
    claims: tuple[m.SemanticClaim, ...],
    relationships: tuple[m.SemanticRelationship, ...],
    *,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
) -> tuple[
    dict[str, m.FreshnessState],
    dict[str, m.Freshness],
    tuple[m.EvidenceDependency, ...],
    set[str],
]:
    """Evaluate the live overlay without persisting it (S2 §5.2 read route).

    Direct plus premise live overlay plus discovery, projected onto the answer
    items only: no preflight, no coverage_check persistence, no store writes.
    """
    semantic_refs: tuple[m.ClaimRef | m.RelationshipRef, ...] = tuple(
        _claim_ref(claim) for claim in claims
    ) + tuple(_relationship_ref(relationship) for relationship in relationships)
    all_items = tuple(claims) + tuple(relationships)
    updates, dependencies = _evaluate_current(
        repository_id,
        semantic_refs,
        all_items,
        evidence=evidence,
        store=store,
        bounds=bounds,
    )
    live_states: dict[str, m.FreshnessState] = {
        update.semantic_id.id.value: update.freshness.state for update in updates
    }
    live_freshness: dict[str, m.Freshness] = {
        update.semantic_id.id.value: update.freshness for update in updates
    }
    updated_ids = set(live_states)
    # Items without updates are CURRENT in the live overlay.
    for ref in semantic_refs:
        live_states.setdefault(ref.id.value, m.FreshnessState.CURRENT)
    changed = tuple(
        dependency
        for dependency in dependencies
        if dependency.semantic_id.id.value in updated_ids
    )
    stale_evidence = {
        dependency.evidence_ref.locator
        for dependency in dependencies
        if dependency.semantic_id.id.value in updated_ids
    }
    return live_states, live_freshness, changed, stale_evidence


def _delivered_state(
    repository_id: str,
    subjects: tuple[m.Subject, ...],
    *,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    state: m.RepositoryState,
    page_token: str | None,
) -> _Delivered:
    """Load every subject on the page and overlay its live freshness."""
    all_claims: list[m.SemanticClaim] = []
    all_rels: list[m.SemanticRelationship] = []
    first_claims_token: str | None = None
    first_rels_token: str | None = None
    for position, subject in enumerate(subjects):
        claims, relationships, claims_token, rels_token = _load_subject_state(
            repository_id,
            subject.subject_id,
            store=store,
            bounds=bounds,
            page_token=page_token,
        )
        all_claims.extend(claims)
        all_rels.extend(relationships)
        if position == 0:
            first_claims_token, first_rels_token = claims_token, rels_token
    live_states, live_freshness, changed, stale_evidence = _live_freshness(
        repository_id,
        tuple(all_claims),
        tuple(all_rels),
        evidence=evidence,
        store=store,
        bounds=bounds,
    )
    claims_t, rels_t = with_freshness(
        tuple(all_claims), tuple(all_rels), live_freshness
    )
    verification = tuple(
        _derived_verification_status(repository_id, state, claim, store=store)
        for claim in claims_t
        if claim.kind is m.ClaimKind.VERIFICATION
        and isinstance(claim.value, m.VerificationValue)
    )
    return _Delivered(
        claims=claims_t,
        relationships=rels_t,
        live_states=live_states,
        changed=changed,
        stale_evidence=stale_evidence,
        verification=verification,
        conflicts=_conflicts_for(
            repository_id, tuple(claims_t), tuple(rels_t), store=store
        ),
        claims_token=first_claims_token,
        relationships_token=first_rels_token,
    )


def _delivered_views(
    repository_id: str,
    subjects: tuple[m.Subject, ...],
    *,
    evidence: EvidenceSource,
    store: SemanticStore,
    bounds: m.QueryBounds,
    live_states: dict[str, m.FreshnessState],
    subject_page_token: str | None,
) -> tuple[
    tuple[m.SemanticQuestionCoverageView, ...],
    int,
    int,
]:
    """Project the question views this page delivers and its item position."""
    if len(subjects) > 1:
        views, _, remaining = _paged_question_views(
            repository_id,
            None,
            tuple(subject.subject_id for subject in subjects),
            store=store,
            bounds=bounds,
            page_token=None,
            evidence=evidence,
            live_states=live_states,
        )
        return views, 0, remaining
    views, shown, remaining = _paged_question_views(
        repository_id,
        subjects[0].subject_id,
        tuple(subject.subject_id for subject in subjects),
        store=store,
        bounds=bounds,
        page_token=subject_page_token,
        evidence=evidence,
        live_states=live_states,
    )
    return views, shown, remaining
