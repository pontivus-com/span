"""Span service refresh operation (plan §9; v0.6 §14 Amendment A-01).

Explicit reassessment of stale/unverifiable semantics. Verbatim from
``span.service_operations``; only the module path changed.
"""

from __future__ import annotations


from span.core import answers as _answers
from span.core import model as m
from span.core import requirements as _requirements
from span.ports.evidence import EvidenceSource
from span.ports.store import SemanticStore
from span.ports.structural import StructuralSource

from span.service.answers import (
    _answer_id,
    ANSWER_ASSEMBLER,
    _conflicts_for,
    _freshness_items_for,
    _select_answer_items,
    coverage_counts_for,
    state_explanation_for,
)
from span.service.freshness import (
    _refresh_view,
)
from span.service.questions import (
    _question_views_for_scope,
)
from span.service.requests import (
    RefreshScopeError,
)
from span.service.resolution import (
    _load_subject_state,
)


def _currency_note(
    currency: m.Freshness,
) -> m.ResolutionRequirement | None:
    """Unresolved note for a non-current provider refresh (G §4.8d).

    Pure projection: CURRENT yields no note; anything else yields one
    UNVERIFIABLE_FRESHNESS requirement carrying the provider's reason.
    """
    if currency.state is m.FreshnessState.CURRENT:
        return None
    return _requirements.unverifiable_freshness(
        subject_or_claim=None,
        description=(
            f"structural index not refreshed: {currency.reason}; "
            f"scope reads stay UNVERIFIABLE where index "
            f"currency matters"
        ),
        supporting_context=(),
    )


def _refuse_truncated_refresh(truncated: bool, ceiling: int) -> None:
    """A refresh never returns a partial answer it cannot resume.

    The scope is a set of subjects, not a frontier, so there is no honest
    cursor for a cut item list. Returning ``truncated: true`` with no token
    would violate the one contract every answer shares, so an oversized
    scope fails closed with the remedy named.
    """
    if not truncated:
        return
    raise RefreshScopeError(
        f"refresh scope exceeds the answer ceiling ({ceiling}); narrow the "
        "scope or raise the bounds; a partial refresh is never returned"
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
            repository_id,
            subject.subject_id,
            store=store,
            bounds=bounds,
        )
        reloaded_claims.extend(claims)
        reloaded_rels.extend(relationships)
    claims_t, rels_t = tuple(reloaded_claims), tuple(reloaded_rels)
    claims_t, rels_t = _refresh_view(
        repository_id,
        claims_t,
        rels_t,
        evidence=evidence,
        store=store,
        bounds=bounds,
    )
    conflicts_all = _conflicts_for(repository_id, claims_t, rels_t, store=store)
    kept_claims, kept_rels, kept_conf, truncated, category = _select_answer_items(
        claims_t, rels_t, conflicts_all, bounds.max_results
    )
    _refuse_truncated_refresh(truncated, bounds.max_results)
    scope_paths = tuple(s.subject_id.canonical_locator for s in subjects)
    views = _question_views_for_scope(
        repository_id,
        None,
        tuple(s.subject_id for s in subjects),
        store=store,
        bounds=bounds,
        evidence=evidence,
    )
    requirements = (
        tuple(req for c in kept_claims for req in _answers.requirements_for_claim(c))
        + tuple(
            req for r in kept_rels for req in _answers.requirements_for_relationship(r)
        )
        + tuple(extra_unresolved)
    )
    content = m.StatusContent(
        resolved_mode=m.StatusResolvedMode.SCOPED,
        store_readiness=m.StoreReadiness.READY,
        freshness_items=_freshness_items_for(kept_claims, kept_rels),
        changed_dependencies=changed,
        verification_status=(),
        refresh_scope=m.EvidenceScope(paths=scope_paths, evidence_refs=()),
        claims=kept_claims,
        relationships=kept_rels,
        conflicts=kept_conf,
        question_coverage=views,
    )
    evidence_refs = tuple(ref for c in kept_claims for ref in c.evidence)
    return ANSWER_ASSEMBLER.build(
        answer_id=_answer_id("rfr", repository_id, ",".join(scope_paths)),
        intent=m.SemanticIntent.STATUS,
        repository_state=state,
        subject_resolution=None,
        content=content,
        evidence=evidence_refs,
        resolution_requirements=requirements,
        bounds=bounds,
        withheld_category=category,
        continuation_token=None,
        state_explanation=(
            "repository store_readiness: READY means the Span semantic store is "
            "available; semantic coverage and currency are reported separately",
            *state_explanation_for(
                tuple(kept_claims),
                tuple(kept_rels),
                coverage=coverage_counts_for(views),
                bounds=(bounds.max_results, truncated),
            ),
        ),
    )
