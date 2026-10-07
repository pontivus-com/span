"""Span pure core validation (plan Phase 1.3).

Validates agent-submitted candidates against stated plan rules only:

- kind allowlist (§5.4/§7.2 — the interpreter cannot emit new kinds);
- mandatory evidence citation (plan §7.1);
- cited evidence resolves (§6.3);
- candidate endpoints/identities are run-bound (§4.2, §8.4 unit scope);
- authority bindings require explicit support (§6.3 — no UNKNOWN-status
  authority, no structural-derivation authority);
- trust derivation (ESTABLISHED / PARTIAL / UNRESOLVED);
- conflict detection with SUPERSEDES resolution (I-08).

Semantic behavior for later phases (conflict precedence ranking beyond
SUPERSEDES, refresh, impact derivation) is not decided here. No effects:
all inputs are values; all outputs are values.
"""

from __future__ import annotations

import hashlib as _hashlib
import json as _json
from dataclasses import dataclass as _dataclass

from span.core import model as m

__all__ = [
    "ValidationContext",
    "CandidateValidation",
    "InterpretationUnitRejected",
    "validate_candidate_claim",
    "validate_candidate_relationship",
    "materialize_claim",
    "materialize_relationship",
    "find_conflicts",
    "deterministic_claim_id",
    "deterministic_relationship_id",
]


@_dataclass(frozen=True)
class ValidationContext:
    """Values a candidate is checked against (all caller-supplied)."""

    allowed_claim_kinds: tuple[m.ClaimKind, ...]
    allowed_relationship_kinds: tuple[m.RelationshipKind, ...]
    known_evidence_ids: frozenset[str]
    known_subject_ids: tuple[m.SubjectId, ...]
    evidence_fingerprints: dict[str, str]


@_dataclass(frozen=True)
class CandidateValidation:
    ok: bool
    trust: m.TrustState
    requirements: tuple[m.ResolutionRequirement, ...]
    diagnostics: tuple[str, ...]


class InterpretationUnitRejected(Exception):
    """Plan §7.5: any SemanticValidationFailure rejects the entire
    affected interpretation unit (no candidate-level salvage). Carries
    the exact failed-member diagnostics (non-semantic, §7.5)."""

    def __init__(self, diagnostics: tuple[str, ...]) -> None:
        super().__init__("; ".join(diagnostics))
        self.diagnostics = diagnostics


def _check_evidence(
    evidence: tuple[m.EvidenceRef, ...], ctx: ValidationContext, owner: str
) -> str | None:
    if not evidence:
        return f"{owner}: no cited evidence (plan §7.1)"
    for ref in evidence:
        if ref.evidence_id.value not in ctx.known_evidence_ids:
            return f"{owner}: cited evidence does not resolve: {ref.evidence_id.value}"
        if ref.evidence_id.value not in ctx.evidence_fingerprints:
            return (
                f"{owner}: evidence fingerprint unavailable: "
                f"{ref.evidence_id.value}"
            )
    return None


def _check_authority(
    authority: m.AuthorityBinding | None,
    evidence: tuple[m.EvidenceRef, ...],
    derivation: m.DerivationKind,
    owner: str,
) -> str | None:
    if authority is None:
        return None
    # §6.3: UNKNOWN status means status cannot be established — such a
    # binding has no explicit support and may not be created.
    if authority.status is m.AuthorityStatus.UNKNOWN:
        return f"{owner}: authority status UNKNOWN has no explicit support"
    # §6.3: no structural signal promoted to authority.
    if derivation is m.DerivationKind.STRUCTURAL_OBSERVATION:
        return f"{owner}: structural derivation cannot carry authority"
    cited = {ref.evidence_id.value for ref in evidence}
    if authority.evidence_ref.evidence_id.value not in cited:
        return f"{owner}: authority evidence is not among cited evidence"
    return None


def _derive_trust(
    authority: m.AuthorityBinding | None,
    subject: m.SubjectId,
    kind_label: str,
) -> tuple[m.TrustState, tuple[m.ResolutionRequirement, ...]]:
    # §6.3: without established authority the item remains
    # PARTIAL/UNRESOLVED. ACCEPTED authority establishes; other explicit
    # statuses qualify; absent authority leaves UNRESOLVED with a
    # deterministic MISSING_AUTHORITY requirement.
    if authority is None:
        return (
            m.TrustState.UNRESOLVED,
            (
                m.ResolutionRequirement(
                    kind=m.ResolutionKind.MISSING_AUTHORITY,
                    subject_or_claim=subject,
                    description=(
                        f"no authority binding established for {kind_label}"
                    ),
                    supporting_context=(),
                ),
            ),
        )
    if authority.status is m.AuthorityStatus.ACCEPTED:
        return m.TrustState.ESTABLISHED, ()
    return m.TrustState.PARTIAL, ()


def validate_candidate_claim(
    candidate: m.CandidateSemanticClaim, ctx: ValidationContext
) -> CandidateValidation:
    """Validate one candidate claim (pure)."""
    if candidate.kind not in ctx.allowed_claim_kinds:
        return CandidateValidation(
            ok=False,
            trust=m.TrustState.UNRESOLVED,
            requirements=(),
            diagnostics=(f"claim kind not allowed: {candidate.kind.value}",),
        )
    if candidate.subject not in ctx.known_subject_ids:
        return CandidateValidation(
            ok=False,
            trust=m.TrustState.UNRESOLVED,
            requirements=(),
            diagnostics=("claim subject is not a run-bound identity",),
        )
    owner = f"claim {candidate.kind.value}"
    failure = _check_evidence(candidate.evidence, ctx, owner)
    if failure is None:
        failure = _check_authority(
            candidate.candidate_authority,
            candidate.evidence,
            candidate.basis.derivation,
            owner,
        )
    if failure is not None:
        return CandidateValidation(
            ok=False,
            trust=m.TrustState.UNRESOLVED,
            requirements=(),
            diagnostics=(failure,),
        )
    trust, requirements = _derive_trust(
        candidate.candidate_authority,
        candidate.subject,
        f"claim {candidate.kind.value}",
    )
    return CandidateValidation(True, trust, requirements, ())


def validate_candidate_relationship(
    candidate: m.CandidateSemanticRelationship, ctx: ValidationContext
) -> CandidateValidation:
    """Validate one candidate relationship (pure)."""
    if candidate.kind not in ctx.allowed_relationship_kinds:
        return CandidateValidation(
            ok=False,
            trust=m.TrustState.UNRESOLVED,
            requirements=(),
            diagnostics=(
                f"relationship kind not allowed: {candidate.kind.value}",
            ),
        )
    if (
        candidate.source not in ctx.known_subject_ids
        or candidate.target not in ctx.known_subject_ids
    ):
        return CandidateValidation(
            ok=False,
            trust=m.TrustState.UNRESOLVED,
            requirements=(),
            diagnostics=("relationship endpoint is not a run-bound identity",),
        )
    owner = f"relationship {candidate.kind.value}"
    failure = _check_evidence(candidate.evidence, ctx, owner)
    if failure is None:
        failure = _check_authority(
            candidate.candidate_authority,
            candidate.evidence,
            candidate.basis.derivation,
            owner,
        )
    if failure is not None:
        return CandidateValidation(
            ok=False,
            trust=m.TrustState.UNRESOLVED,
            requirements=(),
            diagnostics=(failure,),
        )
    trust, requirements = _derive_trust(
        candidate.candidate_authority,
        candidate.source,
        f"relationship {candidate.kind.value}",
    )
    return CandidateValidation(True, trust, requirements, ())


def _stable_id(prefix: str, payload: object) -> str:
    digest = _hashlib.sha256(
        _json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    return f"{prefix}-{digest}"


def deterministic_claim_id(
    candidate: m.CandidateSemanticClaim, trust: m.TrustState
) -> m.ClaimId:
    """Stable opaque id for identical semantic content (idempotent indexing)."""
    return m.ClaimId(
        _stable_id("clm", [m.to_canonical(candidate), trust.value])
    )


def deterministic_relationship_id(
    candidate: m.CandidateSemanticRelationship, trust: m.TrustState
) -> m.RelationshipId:
    """Stable opaque id for identical semantic content (idempotent indexing)."""
    return m.RelationshipId(
        _stable_id("rel", [m.to_canonical(candidate), trust.value])
    )


def materialize_claim(
    candidate: m.CandidateSemanticClaim,
    validation: CandidateValidation,
    repository_state: m.RepositoryState,
) -> m.SemanticClaim:
    """Build the canonical claim from a validated candidate.

    Freshness is CURRENT: the cited evidence was just read, so the stored
    supporting state is the current repository state fingerprint. Later
    currency is established only by preflight (§9.2), never assumed here.
    """
    if not validation.ok:
        raise ValueError("cannot materialize a failed candidate")
    return m.SemanticClaim(
        claim_id=deterministic_claim_id(candidate, validation.trust),
        subject=candidate.subject,
        kind=candidate.kind,
        value=candidate.value,
        evidence=candidate.evidence,
        authority=candidate.candidate_authority,
        trust=validation.trust,
        freshness=m.Freshness(
            state=m.FreshnessState.CURRENT,
            supporting_revision_or_fingerprint=(
                repository_state.state_fingerprint
            ),
            reason=(
                "materialized from current evidence at repository state "
                + repository_state.state_fingerprint
            ),
        ),
        basis=candidate.basis,
    )


def materialize_relationship(
    candidate: m.CandidateSemanticRelationship,
    validation: CandidateValidation,
    repository_state: m.RepositoryState,
) -> m.SemanticRelationship:
    """Build the canonical relationship from a validated candidate."""
    if not validation.ok:
        raise ValueError("cannot materialize a failed candidate")
    return m.SemanticRelationship(
        relationship_id=deterministic_relationship_id(
            candidate, validation.trust
        ),
        source=candidate.source,
        kind=candidate.kind,
        target=candidate.target,
        evidence=candidate.evidence,
        authority=candidate.candidate_authority,
        trust=validation.trust,
        freshness=m.Freshness(
            state=m.FreshnessState.CURRENT,
            supporting_revision_or_fingerprint=(
                repository_state.state_fingerprint
            ),
            reason=(
                "materialized from current evidence at repository state "
                + repository_state.state_fingerprint
            ),
        ),
        basis=candidate.basis,
    )


def find_conflicts(
    claims: tuple[m.SemanticClaim, ...],
    relationships: tuple[m.SemanticRelationship, ...],
) -> tuple[m.SemanticConflict, ...]:
    """Detect conflicting current claims (pure, deterministic).

    A conflict is two claims over the same subject and kind with unequal
    values. A pair is resolved (excluded) only when a SUPERSEDES
    relationship with accepted authority runs between their subjects —
    the superseded side loses (plan I-08). Precedence-rank resolution
    beyond SUPERSEDES belongs to a later phase.
    """
    by_key: dict[tuple[m.SubjectId, m.ClaimKind], list[m.SemanticClaim]] = {}
    for claim in claims:
        by_key.setdefault((claim.subject, claim.kind), []).append(claim)
    for group in by_key.values():
        group.sort(key=lambda c: c.claim_id.value)

    supersedes: dict[m.SubjectId, set[m.SubjectId]] = {}
    for rel in relationships:
        if (
            rel.kind is m.RelationshipKind.SUPERSEDES
            and rel.authority is not None
            and rel.authority.status is m.AuthorityStatus.ACCEPTED
        ):
            supersedes.setdefault(rel.source, set()).add(rel.target)

    conflicts: list[m.SemanticConflict] = []
    for group in by_key.values():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                left, right = group[i], group[j]
                if left.value == right.value:
                    continue
                if right.subject in supersedes.get(left.subject, set()):
                    continue
                if left.subject in supersedes.get(right.subject, set()):
                    continue
                conflicts.append(
                    m.SemanticConflict(
                        left=m.ClaimRef(id=left.claim_id),
                        right=m.ClaimRef(id=right.claim_id),
                        declared_precedence=None,
                    )
                )
    return tuple(conflicts)
