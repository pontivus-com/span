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
    "structural_coverage_requirement",
    "merge_coverage_detail",
    "truncate_fields",
]


def requirements_for_claim(
    claim: m.SemanticClaim,
) -> tuple[m.ResolutionRequirement, ...]:
    """Derive deterministic requirements for one materialized claim.

    All applicable states are reported (§4.9 lists PARTIAL, AMBIGUOUS,
    CONFLICTED, UNRESOLVED, STALE, UNVERIFIABLE): a claim that is both
    unresolved and stale yields both requirements. Where no
    deterministic resolver exists (conflicted, partial), no requirement
    is invented (§4.9).
    """
    requirements: list[m.ResolutionRequirement] = []
    if claim.trust is m.TrustState.UNRESOLVED and claim.authority is None:
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
    if rel.trust is m.TrustState.UNRESOLVED and rel.authority is None:
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
    *,
    repository_id: str = "",
    name_or_locator: str | None = None,
) -> tuple[m.ResolutionRequirement, ...]:
    """Requirements for ambiguous or not-found resolutions.

    AMBIGUOUS keeps its exact-identity requirement. NOT_FOUND carries a
    locator hint: locators resolve against the queried repository's own
    root (never the workspace root), plus the discovery operations that
    name exact locators. Text-only diagnostics; no carrier change.
    """
    if resolution.ambiguity is m.ResolutionAmbiguity.AMBIGUOUS:
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
    if resolution.ambiguity is m.ResolutionAmbiguity.NOT_FOUND:
        target = (
            f"no indexed subject matches {name_or_locator!r}"
            if name_or_locator
            else "no indexed subject matched"
        )
        scope = f" in repository {repository_id!r}" if repository_id else ""
        return (
            m.ResolutionRequirement(
                kind=m.ResolutionKind.MISSING_EVIDENCE,
                subject_or_claim=None,
                description=(
                    f"{target}{scope}; locators resolve against that "
                    f"repository's root; "
                    f"discover exact locators with locate "
                    f"(FILE_OUTLINE for a file, TARGET_MEMBERS for "
                    f"scope members)"
                ),
                supporting_context=(),
            ),
        )
    return ()


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


#: Coverage tokens that mean the structure moved under the index.
_STALE_COVERAGE_TOKENS = frozenset(
    {"dirty-tree", "touched-file-mismatch", "index-older-than-head"}
)


def merge_coverage_detail(details: tuple[str | None, ...]) -> str | None:
    """Union of provider coverage tokens, in the canonical fixed order.

    Mechanical projection only: unknown tokens are ignored rather than
    interpreted, and ``clean-verified`` never survives alongside a reason.
    """
    tokens = {
        token
        for detail in details
        if detail
        for token in detail.split("+")
        if token in m.COVERAGE_DETAIL_TOKENS
    }
    tokens.discard("clean-verified")
    if not tokens:
        return None
    return "+".join(token for token in m.COVERAGE_DETAIL_TOKENS if token in tokens)


def structural_coverage_requirement(
    operation: str,
    coverage: m.ScopeCoverage,
    coverage_detail: str | None,
) -> m.ResolutionRequirement | None:
    """Qualify structural facts that are not current (D6).

    The verdict is projected from the provider, never recomputed. A
    VERIFIED page is silent; an UNVERIFIED page names why and the
    operation that can restore currency. An empty UNVERIFIED page still
    qualifies: absence over changed structure proves nothing.
    """
    if coverage is m.ScopeCoverage.VERIFIED:
        return None
    tokens = frozenset((coverage_detail or "").split("+"))
    kind = (
        m.ResolutionKind.STALE_EVIDENCE
        if tokens & _STALE_COVERAGE_TOKENS
        else m.ResolutionKind.UNVERIFIABLE_FRESHNESS
    )
    reason = coverage_detail or "coverage could not be established"
    return m.ResolutionRequirement(
        kind=kind,
        subject_or_claim=None,
        description=(
            f"{operation} used structural facts that are not current "
            f"({reason}); run `refresh` for the affected scope before "
            "treating them as current"
        ),
        supporting_context=(),
    )
