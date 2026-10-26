"""Span service shared answer primitives (v0.6 §14 Amendment A-01).

Downstream-neutral constructors and selectors used by every answer
composer plus ``repository.py``. Imports only ``refs``,
``core.validation`` (pure), port signatures, ``model``, and
``core.paging`` — never ``freshness.py`` or ``questions.py``.
Verbatim from ``span.service_operations``; only the module path
changed.
"""

from __future__ import annotations

import dataclasses as _dataclasses
import types as _types
import typing as _typing

from span.core import model as m
from span.core import validation as _validation
from span.ports.store import SemanticStore
from span.service.refs import (
    _claim_ref,
    _ref_value,
    _relationship_ref,
)


@_dataclasses.dataclass(frozen=True)
class ResponseBudget:
    """Accounting for one answer.

    ``returned`` is what the answer actually carries — counted from the
    content and the envelope's requirements, never supplied by the operation.
    ``withheld_category`` names what the operation did not emit; the
    continuation token says whether that remainder is resumable. The atomic
    admission rule (an item is emitted only if its requirements fit with it)
    is applied by the steps that bound production (06 and 07); this carrier
    is what they will draw from and what every answer reports.
    """

    requested_max_results: int
    requested_max_depth: int
    returned: int
    withheld_category: str | None = None
    continuation_token: str | None = None

    @property
    def truncated(self) -> bool:
        return self.withheld_category is not None or self.continuation_token is not None


#: Tuple-valued fields that project an already-counted item rather than
#: carrying independent information. ``freshness_items`` mirrors the freshness
#: already on each returned claim and relationship; counting it would report the
#: same fact twice and halve the usable ceiling.
_PROJECTION_FIELDS = frozenset({"freshness_items"})


def _leaf_count(content: m.SemanticContent, requirements: int) -> int:
    """Count the leaves an answer carries, from the content itself.

    Every tuple-valued field carries independent leaves except the declared
    projections. No stored count is trusted, so the reported number cannot
    disagree with the payload.
    """
    count = requirements
    hints = _typing.get_type_hints(type(content))
    for field in _dataclasses.fields(content):
        if field.name in _PROJECTION_FIELDS:
            continue
        if _typing.get_origin(hints[field.name]) is tuple:
            count += len(getattr(content, field.name) or ())
    return count


class AnswerAssembler:
    """The only constructor of ``SemanticAnswer``.

    Operations hand over content, evidence, requirements, and what they
    withheld. The assembler computes the count and derives truncation, so no
    call site can misreport either.
    """

    def build(
        self,
        *,
        answer_id: m.AnswerId,
        intent: m.SemanticIntent,
        repository_state: m.RepositoryState,
        content: m.SemanticContent,
        bounds: m.QueryBounds,
        subject_resolution: m.SubjectResolution | None = None,
        evidence: tuple[m.EvidenceRef, ...] = (),
        resolution_requirements: tuple[m.ResolutionRequirement, ...] = (),
        withheld_category: str | None = None,
        continuation_token: str | None = None,
        state_explanation: tuple[str, ...] = (),
    ) -> m.SemanticAnswer:
        budget = ResponseBudget(
            requested_max_results=bounds.max_results,
            requested_max_depth=bounds.max_depth,
            returned=_leaf_count(content, len(resolution_requirements)),
            withheld_category=withheld_category,
            continuation_token=continuation_token,
        )
        return m.SemanticAnswer(
            answer_id=answer_id,
            intent=intent,
            repository_state=repository_state,
            subject_resolution=subject_resolution,
            content=content,
            evidence=tuple(evidence),
            resolution_requirements=tuple(resolution_requirements),
            bound_info=m.BoundInfo(
                requested_max_results=budget.requested_max_results,
                requested_max_depth=budget.requested_max_depth,
                returned_results=budget.returned,
                truncated=budget.truncated,
                truncated_category=budget.withheld_category,
                continuation_token=budget.continuation_token,
            ),
            state_explanation=tuple(state_explanation),
        )


ANSWER_ASSEMBLER = AnswerAssembler()


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


#: Currency literals for state explanation ([design note I](docs/design-references.md#i) S8 §5.8).
#: Attested values say only what the agent could know without execution;
#: derived values come from a VerificationRecord.
_CURRENCY_LITERAL: _typing.Mapping[m.AttestedCurrency | m.DerivedCurrency, str] = (
    _types.MappingProxyType(
        {
            m.AttestedCurrency.CANDIDATE: "candidate",
            m.AttestedCurrency.UNKNOWN: "unknown",
            m.DerivedCurrency.CURRENT_PASS: "current pass",
            m.DerivedCurrency.CURRENT_FAIL: "current fail",
            m.DerivedCurrency.STALE: "stale",
        }
    )
)


def currency_literal(
    value: m.AttestedCurrency | m.DerivedCurrency,
) -> str:
    """Plain-language literal for one currency member."""
    return _CURRENCY_LITERAL.get(value, "unknown")


def verification_currencies_for(
    claims: tuple[m.SemanticClaim, ...],
) -> tuple[str, ...]:
    """Attested currency literals over carried VERIFICATION links.

    Operations without a record reader report what the agent attested.
    ``status`` supplies derived literals instead.
    """
    found: set[str] = set()
    for claim in claims:
        if claim.kind is m.ClaimKind.VERIFICATION and isinstance(
            claim.value, m.VerificationValue
        ):
            found.add(_CURRENCY_LITERAL.get(claim.value.attested_currency, "unknown"))
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
    derived_currencies: tuple[str, ...] | None = None,
) -> tuple[str, ...]:
    """Project plain-language state explanation ([design note I](docs/design-references.md#i) S8 §5.8).

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
    items: tuple[m.SemanticClaim | m.SemanticRelationship, ...] = (
        *claims,
        *relationships,
    )
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
    currencies = (
        tuple(sorted(derived_currencies))
        if derived_currencies is not None
        else verification_currencies_for(tuple(claims))
    )
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
