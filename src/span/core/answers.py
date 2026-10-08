"""Span answer composition helpers (plan §4.9–§4.10, §11.9 subset).

Pure rules for deriving ResolutionRequirements and applying the §11.9
retention priority under bounds. Full deterministic truncation with
continuation tokens belongs to Phase 3.5; this module truncates tails
without continuation and never splits a known conflict pair or drops a
qualifier (plan §11.9 rules).
"""

from __future__ import annotations

from span.core import model as m

__all__ = [
    "requirements_for_claim",
    "requirements_for_relationship",
    "requirements_for_resolution",
    "truncate_fields",
]


def requirements_for_claim(claim: m.SemanticClaim) -> tuple[m.ResolutionRequirement, ...]:
    """Derive deterministic requirements for one materialized claim.

    All applicable states are reported (§4.9 lists PARTIAL, AMBIGUOUS,
    CONFLICTED, UNRESOLVED, STALE, UNVERIFIABLE): a claim that is both
    unresolved and stale yields both requirements. Where no
    deterministic resolver exists (conflicted, partial), no requirement
    is invented (§4.9).
    """
    requirements: list[m.ResolutionRequirement] = []
    if (
        claim.trust is m.TrustState.UNRESOLVED
        and claim.authority is None
    ):
        requirements.append(
            m.ResolutionRequirement(
                kind=m.ResolutionKind.MISSING_AUTHORITY,
                subject_or_claim=m.ClaimRef(id=claim.claim_id),
                description=(
                    f"no authority binding established for "
                    f"{claim.kind.value} claim {claim.claim_id.value}"
                ),
                supporting_context=(),
            )
        )
    if claim.freshness.state is m.FreshnessState.STALE:
        requirements.append(
            m.ResolutionRequirement(
                kind=m.ResolutionKind.STALE_EVIDENCE,
                subject_or_claim=m.ClaimRef(id=claim.claim_id),
                description=(
                    f"evidence changed since claim {claim.claim_id.value} "
                    f"was established; explicit refresh required"
                ),
                supporting_context=(),
            )
        )
    if claim.freshness.state is m.FreshnessState.UNVERIFIABLE:
        requirements.append(
            m.ResolutionRequirement(
                kind=m.ResolutionKind.UNVERIFIABLE_FRESHNESS,
                subject_or_claim=m.ClaimRef(id=claim.claim_id),
                description=(
                    f"currency of claim {claim.claim_id.value} cannot be "
                    f"established from current evidence"
                ),
                supporting_context=(),
            )
        )
    return tuple(requirements)


def requirements_for_relationship(
    rel: m.SemanticRelationship,
) -> tuple[m.ResolutionRequirement, ...]:
    """Derive deterministic requirements for one materialized relationship.

    Same state rules as claims (§4.9): missing authority, stale, and
    unverifiable states each yield their requirement; conflicted and
    partial states carry no invented resolver.
    """
    requirements: list[m.ResolutionRequirement] = []
    if (
        rel.trust is m.TrustState.UNRESOLVED
        and rel.authority is None
    ):
        requirements.append(
            m.ResolutionRequirement(
                kind=m.ResolutionKind.MISSING_AUTHORITY,
                subject_or_claim=m.RelationshipRef(id=rel.relationship_id),
                description=(
                    f"no authority binding established for "
                    f"{rel.kind.value} relationship "
                    f"{rel.relationship_id.value}"
                ),
                supporting_context=(),
            )
        )
    if rel.freshness.state is m.FreshnessState.STALE:
        requirements.append(
            m.ResolutionRequirement(
                kind=m.ResolutionKind.STALE_EVIDENCE,
                subject_or_claim=m.RelationshipRef(id=rel.relationship_id),
                description=(
                    f"evidence changed since relationship "
                    f"{rel.relationship_id.value} was established; "
                    f"explicit refresh required"
                ),
                supporting_context=(),
            )
        )
    if rel.freshness.state is m.FreshnessState.UNVERIFIABLE:
        requirements.append(
            m.ResolutionRequirement(
                kind=m.ResolutionKind.UNVERIFIABLE_FRESHNESS,
                subject_or_claim=m.RelationshipRef(id=rel.relationship_id),
                description=(
                    f"currency of relationship {rel.relationship_id.value} "
                    f"cannot be established from current evidence"
                ),
                supporting_context=(),
            )
        )
    return tuple(requirements)


def requirements_for_resolution(
    resolution: m.SubjectResolution,
) -> tuple[m.ResolutionRequirement, ...]:
    """Requirement for an ambiguous (multi-candidate) resolution."""
    if resolution.ambiguity is not m.ResolutionAmbiguity.AMBIGUOUS:
        return ()
    return (
        m.ResolutionRequirement(
            kind=m.ResolutionKind.AMBIGUOUS_IDENTITY,
            subject_or_claim=None,
            description=(
                f"{len(resolution.candidates)} subjects match; "
                f"an exact identity is required"
            ),
            supporting_context=(),
        ),
    )


def truncate_fields(
    lists: tuple[tuple[tuple[object, ...], str], ...],
    max_results: int,
) -> tuple[tuple[tuple[object, ...], ...], bool, str | None, str | None]:
    """Keep list tails in §11.9 retention priority under a result cap.

    ``lists`` is (items, category-name) pairs in retention priority
    (highest first: qualifiers such as conflicts/unresolved, then
    authority/evidence, then claims/relationships, then structural
    context). Conflict pairs are atomic objects, so neither side of a
    known conflict is ever returned as if uncontested. Returns (kept
    lists, truncated, first-dropped category, continuation token).

    The continuation token (``trunc:<category>:<dropped>``) is a
    deterministic availability signal: it states that continuation is
    available and what was dropped. v0.5 request contracts carry no
    continuation field (contracts are exact, §11.10), so follow-up is
    agent-directed re-query with a tighter scope — never a hidden
    second query path.
    """
    kept: list[tuple[object, ...]] = []
    remaining = max_results
    truncated = False
    category: str | None = None
    dropped = 0
    for items, name in lists:
        if len(items) <= remaining:
            kept.append(items)
            remaining -= len(items)
        else:
            kept.append(items[:remaining] if remaining > 0 else ())
            dropped += len(items) - len(kept[-1])
            truncated = True
            if category is None:
                category = name
            remaining = 0
    token = f"trunc:{category}:{dropped}" if truncated else None
    return tuple(kept), truncated, category, token
