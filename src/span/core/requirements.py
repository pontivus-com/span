"""The one owner of `ResolutionRequirement` construction (plan §2.6, D2).

Every caller names the situation it is reporting; the kind is fixed by the
constructor, so a site cannot pair one kind with wording meant for another.
Descriptions stay at the call site because they are the actionable guidance the
agent reads — this module owns shape, not prose.
"""

from __future__ import annotations

from span.core import model as m

__all__ = [
    "requirement",
    "ambiguous_identity",
    "incomplete_scope",
    "missing_authority",
    "missing_evidence",
    "missing_semantic_coverage",
    "stale_evidence",
    "unverifiable_freshness",
]

_SubjectOrClaim = m.SubjectId | m.ClaimRef | m.RelationshipRef | None


def requirement(
    kind: m.ResolutionKind,
    subject_or_claim: _SubjectOrClaim = None,
    description: str = "",
    supporting_context: tuple[m.ClaimRef | m.RelationshipRef | m.EvidenceRef, ...] = (),
) -> m.ResolutionRequirement:
    """Construct one requirement when the kind is genuinely dynamic."""
    return m.ResolutionRequirement(
        kind=kind,
        subject_or_claim=subject_or_claim,
        description=description,
        supporting_context=supporting_context,
    )


def ambiguous_identity(
    subject_or_claim: _SubjectOrClaim = None,
    description: str = "",
    supporting_context: tuple[m.ClaimRef | m.RelationshipRef | m.EvidenceRef, ...] = (),
) -> m.ResolutionRequirement:
    """The identity could not be resolved to exactly one subject or item."""
    return requirement(
        m.ResolutionKind.AMBIGUOUS_IDENTITY,
        subject_or_claim,
        description,
        supporting_context,
    )


def incomplete_scope(
    subject_or_claim: _SubjectOrClaim = None,
    description: str = "",
    supporting_context: tuple[m.ClaimRef | m.RelationshipRef | m.EvidenceRef, ...] = (),
) -> m.ResolutionRequirement:
    """Admitted work remains within the scope and must be continued."""
    return requirement(
        m.ResolutionKind.INCOMPLETE_SEMANTIC_SCOPE,
        subject_or_claim,
        description,
        supporting_context,
    )


def missing_authority(
    subject_or_claim: _SubjectOrClaim = None,
    description: str = "",
    supporting_context: tuple[m.ClaimRef | m.RelationshipRef | m.EvidenceRef, ...] = (),
) -> m.ResolutionRequirement:
    """Governing authority for the claim or result is absent."""
    return requirement(
        m.ResolutionKind.MISSING_AUTHORITY,
        subject_or_claim,
        description,
        supporting_context,
    )


def missing_evidence(
    subject_or_claim: _SubjectOrClaim = None,
    description: str = "",
    supporting_context: tuple[m.ClaimRef | m.RelationshipRef | m.EvidenceRef, ...] = (),
) -> m.ResolutionRequirement:
    """Evidence the result needs was not delivered."""
    return requirement(
        m.ResolutionKind.MISSING_EVIDENCE,
        subject_or_claim,
        description,
        supporting_context,
    )


def missing_semantic_coverage(
    subject_or_claim: _SubjectOrClaim = None,
    description: str = "",
    supporting_context: tuple[m.ClaimRef | m.RelationshipRef | m.EvidenceRef, ...] = (),
) -> m.ResolutionRequirement:
    """No adopted question coverage exists for the subject."""
    return requirement(
        m.ResolutionKind.MISSING_SEMANTIC_COVERAGE,
        subject_or_claim,
        description,
        supporting_context,
    )


def stale_evidence(
    subject_or_claim: _SubjectOrClaim = None,
    description: str = "",
    supporting_context: tuple[m.ClaimRef | m.RelationshipRef | m.EvidenceRef, ...] = (),
) -> m.ResolutionRequirement:
    """Recorded evidence or a premise no longer matches current bytes."""
    return requirement(
        m.ResolutionKind.STALE_EVIDENCE,
        subject_or_claim,
        description,
        supporting_context,
    )


def unverifiable_freshness(
    subject_or_claim: _SubjectOrClaim = None,
    description: str = "",
    supporting_context: tuple[m.ClaimRef | m.RelationshipRef | m.EvidenceRef, ...] = (),
) -> m.ResolutionRequirement:
    """Currency could not be established; an empty result proves nothing."""
    return requirement(
        m.ResolutionKind.UNVERIFIABLE_FRESHNESS,
        subject_or_claim,
        description,
        supporting_context,
    )
