"""Span service shared answer primitives (v0.6 §14 Amendment A-01).

Downstream-neutral constructors and selectors used by every answer
composer plus ``repository.py``. Imports only ``refs``,
``core.validation`` (pure), port signatures, ``model``, and
``shell.paging`` — never ``freshness.py`` or ``questions.py``.
Verbatim from ``span.service_operations``; only the module path
changed.
"""

from __future__ import annotations

from span.core import model as m
from span.core import validation as _validation
from span.ports.store import SemanticStore
from span.shell import paging as _paging
from span.service.refs import (
    _claim_ref,
    _ref_value,
    _relationship_ref,
)

__all__ = [
    "_answer_id",
    "_bound_info",
    "_recorded_conflicts",
    "_conflicts_for",
    "_select_answer_items",
    "_freshness_items_for",
    "_next_service_token",
    "_query_digest",
    "_bounds_key",
    "_validate_service_token",
    "coverage_counts_for",
    "state_explanation_for",
    "verification_currencies_for",
]


def _answer_id(prefix: str, request_part: str, subject_part: str) -> m.AnswerId:
    import hashlib as _hashlib

    digest = _hashlib.sha256(
        f"{prefix}:{request_part}:{subject_part}".encode("utf-8")
    ).hexdigest()[:16]
    return m.AnswerId(f"{prefix}-{digest}")


def _bounds_key(bounds: m.QueryBounds) -> str:
    """Deterministic listing-affecting bounds identity (M-06.5).

    Every bounds field that can change the selected/ordered page slice
    is part of the query digest; `page_token` is never part of it.
    """
    return "|".join(
        str(value)
        for value in (
            bounds.max_results,
            bounds.max_depth,
            bounds.max_subjects,
            bounds.max_evidence_units,
            bounds.max_evidence_bytes,
            bounds.max_candidate_claims,
            bounds.max_candidate_relationships,
        )
    )


def _query_digest(
    operation: str,
    repository_id: str,
    target_key: str,
    question_key: str,
    bounds: m.QueryBounds,
) -> str:
    """Query digest binding a service page token to its request (M-06.5)."""
    return _paging.question_digest(
        operation,
        repository_id,
        target_key,
        question_key,
        _bounds_key(bounds),
    )


def _validate_service_token(
    page_token: str | None,
    expected_digest: str,
) -> None:
    """Reject a page token bound to a different query (M-06.5a).

    The public diagnostic names the remedy, never the internal encoding.
    """
    if page_token is None:
        return
    if not page_token.startswith("pgq:"):
        raise ValueError(
            "page token is invalid for this request; restart pagination "
            "from the first page with page_token omitted"
        )
    digest, _, _, _ = _paging.parse_question_token(page_token)
    if digest != expected_digest:
        raise ValueError(
            "page token is invalid for this request; restart pagination "
            "from the first page with page_token omitted"
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
    query_digest: str = "default",
    expected_digest: str | None = None,
) -> str | None:
    """Answer-level next token from shown counts (plan I-39; I S4 pgq).

    Binds pages to the selected question via query_digest. Rejects old
    pg: service cursors upstream; emits pgq only. Each side advances
    past shown items only. A side is exhausted when its load cursor is
    done and everything loaded was shown.
    """
    # Decode incoming offsets via pgq-aware parser (old pg: rejected).
    try:
        if page_token is not None and page_token.startswith("pgq:"):
            token_digest, claims_skip, rels_skip, qskip = _paging.parse_question_token(
                page_token
            )
            if expected_digest is not None and token_digest != expected_digest:
                raise ValueError(
                    "page token is invalid for this request; restart "
                    "pagination from the first page with page_token omitted"
                )
        elif page_token is None:
            claims_skip, rels_skip, qskip = 0, 0, 0
        else:
            # Old cursor: force restart diagnostic upstream.
            raise ValueError(
                "page token is invalid for this request; restart "
                "pagination from the first page with page_token omitted"
            )
    except ValueError:
        # Let caller map to typed invalid-token error; re-raise.
        raise
    claims_exhausted = claims_token is None and len(kept_claims) >= len(loaded_claims)
    rels_exhausted = rels_token is None and len(kept_rels) >= len(loaded_rels)
    questions_exhausted = questions_remaining <= 0
    if claims_exhausted and rels_exhausted and questions_exhausted:
        return None
    return _paging.format_question_token(
        query_digest,
        claims_skip + len(kept_claims),
        rels_skip + len(kept_rels),
        (qskip + questions_skip) if not questions_exhausted else qskip,
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
    recorded = _recorded_conflicts(repository_id, claims, relationships, store=store)
    seen = {(_ref_value(c.left), _ref_value(c.right)) for c in derived}
    extra = tuple(
        c for c in recorded if (_ref_value(c.left), _ref_value(c.right)) not in seen
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
        + len(
            set(_mandatory(kept_conf))
            & (
                {c.claim_id.value for c in claims}
                | {r.relationship_id.value for r in relationships}
            )
        )
        > max_results
    ):
        kept_conf.pop()
        truncated = True
        if category is None:
            category = "conflicts"
    mandatory = set(_mandatory(kept_conf))
    budget = max_results - len(kept_conf)
    mand_claims = [c for c in claims if c.claim_id.value in mandatory]
    mand_rels = [r for r in relationships if r.relationship_id.value in mandatory]
    rest_claims = [c for c in claims if c.claim_id.value not in mandatory]
    rest_rels = [r for r in relationships if r.relationship_id.value not in mandatory]
    kept_claims = list(mand_claims)
    kept_rels = list(mand_rels)
    # Fair round-robin fill in stable order: each side advances only
    # past shown items, so per-list page offsets stay exact (I-39).
    while len(kept_claims) + len(kept_rels) < budget and (rest_claims or rest_rels):
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
        pair
        for pair in kept_conf
        if _ref_value(pair.left) in kept_ids and _ref_value(pair.right) in kept_ids
    ]
    return tuple(kept_claims), tuple(kept_rels), tuple(kept_conf), truncated, category


def _freshness_items_for(
    claims: tuple[m.SemanticClaim, ...],
    relationships: tuple[m.SemanticRelationship, ...],
) -> tuple[m.FreshnessItem, ...]:
    """Per-item freshness records for exactly the carried items (I-36)."""
    return tuple(
        [
            m.FreshnessItem(_claim_ref(c), c.subject, c.freshness, c.trust)
            for c in claims
        ]
        + [
            m.FreshnessItem(_relationship_ref(r), r.source, r.freshness, r.trust)
            for r in relationships
        ]
    )


#: Verification currency literals for state explanation (Addendum I S8
#: §5.8): the enum meaning in words. `current pass` / `current fail`
#: use a space, matching the adopted contract vocabulary.
_CURRENCY_LITERAL = {
    m.VerificationCurrency.CANDIDATE: "candidate",
    m.VerificationCurrency.CURRENT_PASS: "current pass",
    m.VerificationCurrency.CURRENT_FAIL: "current fail",
    m.VerificationCurrency.STALE: "stale",
    m.VerificationCurrency.UNKNOWN: "unknown",
}


def verification_currencies_for(
    claims: tuple[m.SemanticClaim, ...],
) -> tuple[str, ...]:
    """Distinct verification currency literals over carried VERIFICATION
    values, sorted. Empty when the page carries no verification."""
    found: set[str] = set()
    for claim in claims:
        if claim.kind is m.ClaimKind.VERIFICATION and isinstance(
            claim.value, m.VerificationValue
        ):
            found.add(_CURRENCY_LITERAL.get(claim.value.currency, "unknown"))
    return tuple(sorted(found))


def coverage_counts_for(
    views: tuple[m.SemanticQuestionCoverageView, ...],
) -> tuple[int, int, int]:
    """(answered, open, total) over returned question-coverage views.

    OPEN and PENDING both count as open: work the agent still owes.
    Deterministic; page-scoped like every explanation sentence.
    """
    answered = sum(
        1
        for v in views
        if v.effective_disposition is m.SemanticQuestionDisposition.ANSWERED
    )
    open_ = sum(
        1
        for v in views
        if v.effective_disposition
        in (
            m.SemanticQuestionDisposition.OPEN,
            m.SemanticQuestionDisposition.PENDING,
        )
    )
    return (answered, open_, len(views))


def _distribution_sentence(
    label: str,
    counts: tuple[tuple[str, int], ...],
) -> str:
    """`label: <n> <name>, ...` over nonzero categories in fixed order.

    Mixed states receive qualified wording (every nonzero state shown)
    rather than a single best status.
    """
    shown = ", ".join(f"{n} {name}" for name, n in counts if n)
    return f"{label}: {shown}" if shown else f"{label}: none"


def state_explanation_for(
    claims: tuple[m.SemanticClaim, ...],
    relationships: tuple[m.SemanticRelationship, ...],
    *,
    coverage: tuple[int, int, int] | None = None,
    bounds: tuple[int, bool] | None = None,
) -> tuple[str, ...]:
    """Project plain-language state explanation (Addendum I S8 §5.8).

    At most one bounded nature sentence with precise conditional syntax:
    `returned assertions: none` when no assertions are returned; otherwise
    `returned assertions: <distribution> (<d> descriptive, <n> normative)`
    with <distribution> one of descriptive-only, normative-only, or mixed;
    authority-unresolved items stay qualified regardless of nature.
    Counts are non-negative integers over the returned page.

    Further deterministic sentences cover trust (returned items'
    authority states), freshness (returned items' currency states),
    verification currency (literals over carried VERIFICATION values, or
    an explicit absent statement that never claims tests never ran),
    bounds ((max_results, truncated) page window), and coverage
    ((answered, open, total) over returned question views). The field is
    not persisted. Transport only serializes it. Every sentence describes
    returned scope/page; it cannot imply repository completeness.
    """
    items = (*claims, *relationships)
    if not items:
        # No assertions returned — but a caller that supplies coverage
        # or bounds still gets those page dimensions plus the
        # verification context, instead of losing them with the nature
        # sentence. Bare calls keep the exact none sentence.
        if coverage is None and bounds is None:
            return ("returned assertions: none",)
        empty: list[str] = ["returned assertions: none"]
        empty.append("no current passing verification carried for this scope")
        if bounds is not None:
            max_results, truncated = bounds
            empty.append(
                f"bounds: at most {max_results} returned items per page"
                + ("; listing truncated" if truncated else "")
            )
        if coverage is not None:
            answered, open_, total = coverage
            empty.append(
                f"coverage: {answered} answered, {open_} open " f"of {total} questions"
            )
        return tuple(empty)
    descriptive = sum(
        1 for item in items if item.assertion_nature is m.AssertionNature.DESCRIPTIVE
    )
    normative = len(items) - descriptive
    if descriptive and not normative:
        distribution = "descriptive-only"
    elif normative and not descriptive:
        distribution = "normative-only"
    else:
        distribution = "mixed"
    nature_sentence = (
        f"returned assertions: {distribution} "
        f"({descriptive} descriptive, {normative} normative); "
        "authority-unresolved items stay qualified regardless of nature"
    )
    trust_counts: dict[m.TrustState, int] = {}
    freshness_counts: dict[m.FreshnessState, int] = {}
    for item in items:
        trust_counts[item.trust] = trust_counts.get(item.trust, 0) + 1
        freshness_counts[item.freshness.state] = (
            freshness_counts.get(item.freshness.state, 0) + 1
        )
    sentences = [
        nature_sentence,
        _distribution_sentence(
            "trust",
            tuple(
                (state.value.lower(), trust_counts.get(state, 0))
                for state in m.TrustState
            ),
        ),
        _distribution_sentence(
            "freshness",
            tuple(
                (state.value.lower(), freshness_counts.get(state, 0))
                for state in m.FreshnessState
            ),
        ),
    ]
    currencies = verification_currencies_for(tuple(claims))
    if not currencies:
        sentences.append("no current passing verification carried for this scope")
    elif len(currencies) == 1:
        sentences.append(f"verification: {currencies[0]}")
    else:
        sentences.append(f"verification: mixed ({', '.join(currencies)})")
    if bounds is not None:
        max_results, truncated = bounds
        sentences.append(
            f"bounds: at most {max_results} returned items per page"
            + ("; listing truncated" if truncated else "")
        )
    if coverage is not None:
        answered, open_, total = coverage
        sentences.append(
            f"coverage: {answered} answered, {open_} open " f"of {total} questions"
        )
    return tuple(sentences)
