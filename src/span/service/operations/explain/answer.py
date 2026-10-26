"""Span service explain operation (plan §11.4; v0.6 §14 Amendment A-01).

Bounded semantic explanation with baseline establishment. Verbatim from
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
    _next_service_token,
    _query_digest,
    _validate_service_token,
    _select_answer_items,
    coverage_counts_for,
    state_explanation_for,
)
from span.service.freshness import (
    _refresh_view,
)
from span.service.questions import (
    _paged_question_views,
)
from span.service.resolution import (
    _load_subject_state,
)


def _baseline_answer(
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
    """The root's answer once its establishment frontier is exhausted."""
    return _compose_explain_answer(
        repository_id,
        subject,
        resolution,
        structural=structural,
        evidence=evidence,
        store=store,
        bounds=bounds,
        state=state,
        page_token=page_token,
        scope_root=subject.subject_id,
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
    page_token: str | None = None,
    scope_root: m.SubjectId | None = None,
    question_key: str = "",
) -> m.SemanticAnswer:
    sid = subject.subject_id
    _digest = _query_digest(
        "EXPLAIN",
        repository_id,
        f"{sid.subject_kind.value}:{sid.canonical_locator}",
        question_key,
        bounds,
    )
    _validate_service_token(page_token, _digest)
    claims, relationships, claims_token, rels_token = _load_subject_state(
        repository_id,
        sid,
        store=store,
        bounds=bounds,
        page_token=page_token,
    )
    claims, relationships = _refresh_view(
        repository_id,
        claims,
        relationships,
        evidence=evidence,
        store=store,
        bounds=bounds,
    )
    conflicts_all = _conflicts_for(repository_id, claims, relationships, store=store)
    kept_claims, kept_rels, kept_conf, items_truncated, items_category = (
        _select_answer_items(claims, relationships, conflicts_all, bounds.max_results)
    )
    locations = structural.locations(repository_id, sid, bounds).items
    requirements: list[m.ResolutionRequirement] = []
    if resolution is not None:
        requirements.extend(_answers.requirements_for_resolution(resolution))
    for claim in kept_claims:
        requirements.extend(_answers.requirements_for_claim(claim))
    (kept_locs,), truncated_locs, category_locs, _ = _answers.truncate_fields(
        ((locations, "locations"),),
        max(
            0,
            bounds.max_results - len(kept_conf) - len(kept_claims) - len(kept_rels),
        ),
    )
    truncated = items_truncated or truncated_locs
    category = items_category if items_category is not None else category_locs
    views, qshown, qremaining = _paged_question_views(
        repository_id,
        scope_root or sid,
        (sid,),
        store=store,
        bounds=bounds,
        page_token=page_token,
        evidence=evidence,
    )
    if not views and not kept_claims and not kept_rels:
        requirements.append(
            _requirements.missing_semantic_coverage(
                subject_or_claim=sid,
                description="no examined semantic question for subject",
                supporting_context=(),
            )
        )
    elif not views and (kept_claims or kept_rels):
        # Every current semantic item is written with its owning
        # question coverage in the same atomic batch. Stored assertions
        # with no coverage at all mean the store violates that
        # invariant; exposed current data is never downgraded to
        # unassessed content.
        raise RuntimeError(
            "semantic store invariant violation: stored assertions "
            f"without question coverage for subject {sid.canonical_locator}"
        )
    if qremaining > 0:
        truncated = True
        category = category or "question_coverage"
        requirements.append(
            _requirements.incomplete_scope(
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
    return ANSWER_ASSEMBLER.build(
        answer_id=_answer_id("ans", repository_id, sid.canonical_locator),
        intent=m.SemanticIntent.EXPLAIN,
        repository_state=state,
        subject_resolution=resolution,
        content=content,
        evidence=tuple(ref for c in kept_claims for ref in c.evidence),
        resolution_requirements=tuple(requirements),
        bounds=bounds,
        withheld_category=category,
        continuation_token=_next_service_token(
            page_token,
            kept_claims,
            kept_rels,
            claims,
            relationships,
            claims_token,
            rels_token,
            questions_skip=qshown,
            questions_remaining=qremaining,
            query_digest=_digest,
        ),
        state_explanation=state_explanation_for(
            tuple(kept_claims),
            tuple(kept_rels),
            coverage=coverage_counts_for(views),
            bounds=(bounds.max_results, truncated),
        ),
    )
