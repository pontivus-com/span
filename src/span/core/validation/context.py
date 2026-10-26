"""Validation context, results, and shared evidence checks."""

from __future__ import annotations

import hashlib as _hashlib
import json as _json
import types as _types
import typing as _typing
from dataclasses import dataclass as _dataclass
from dataclasses import field as _field
from span.core import model as m
from span.core import requirements as _requirements

FREE_TEXT_FIELDS: _typing.Mapping[type, frozenset[str]] = _types.MappingProxyType(
    {
        m.PurposeValue: frozenset({"summary"}),
        m.CapabilityMembershipValue: frozenset({"membership_role"}),
        m.ResponsibilityValue: frozenset({"responsibility", "scope"}),
        m.OwnershipCustodyValue: frozenset({"scope"}),
        m.RepresentationContractValue: frozenset(
            {"representation_name", "serialization_or_shape_rule"}
        ),
        m.TransformationOwnershipValue: frozenset({"responsibility"}),
        m.InvariantConstraintValue: frozenset({"statement", "applicability"}),
        m.ConfigurationEnvironmentValue: frozenset({"concern", "applicability"}),
        m.LifecycleStateValue: frozenset({"description", "retention_or_expiry"}),
        m.VerificationValue: frozenset(),
    }
)


@_dataclass(frozen=True)
class ValidationContext:
    """Values a candidate is checked against (all caller-supplied)."""

    allowed_claim_kinds: tuple[m.ClaimKind, ...]
    allowed_relationship_kinds: tuple[m.RelationshipKind, ...]
    known_evidence_ids: frozenset[str]
    known_subject_ids: tuple[m.SubjectId, ...]
    evidence_fingerprints: dict[str, str]
    evidence_contents: dict[str, str] = _field(default_factory=dict)
    evidence_refs: dict[str, m.EvidenceRef] = _field(default_factory=dict)
    """Canonical evidence refs by evidence id (task-known plus
    provider-admitted). Ephemeral validation lookup only — never
    persisted, never a public carrier."""


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


def _check_basis(basis: m.SemanticBasis, owner: str) -> str | None:
    # Plan §4.9: every material claim/relationship carries a bounded
    # SemanticBasis whose summary restates the evidence/derivation
    # relationship. An empty summary states no account and is a unit
    # failure — the service never invents it downstream.
    if not basis.summary:
        return f"{owner}: semantic basis summary is empty"
    return None


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
    authority: m.CandidateAuthority | None,
    evidence: tuple[m.EvidenceRef, ...],
    derivation: m.DerivationKind,
    ctx: ValidationContext,
    owner: str,
) -> str | None:
    if authority is None:
        return None
    binding = authority.binding
    support = authority.support
    # §6.3: UNKNOWN status means status cannot be established — such a
    # binding has no explicit support and may not be created.
    if binding.status is m.AuthorityStatus.UNKNOWN:
        return f"{owner}: authority status UNKNOWN has no explicit support"
    # §6.3: no structural signal promoted to authority.
    if derivation is m.DerivationKind.STRUCTURAL_OBSERVATION:
        return f"{owner}: structural derivation cannot carry authority"
    cited = {ref.evidence_id.value for ref in evidence}
    if binding.evidence_ref.evidence_id.value not in cited:
        return f"{owner}: authority evidence is not among cited evidence"
    # §6.3 (v0.6): the verbatim quote must occur in the cited unit.
    if not support.quoted_span:
        return f"{owner}: authority support quote is empty"
    unit_content = ctx.evidence_contents.get(binding.evidence_ref.evidence_id.value)
    if unit_content is None:
        return f"{owner}: authority evidence content unavailable for " f"support check"
    if support.quoted_span not in unit_content:
        return (
            f"{owner}: authority support quote is not a verbatim "
            f"substring of cited evidence"
        )
    # Status/applicability sections must resolve to cited evidence
    # sections whenever the binding asserts them.
    if binding.status is not m.AuthorityStatus.UNKNOWN:
        if not support.status_section:
            return f"{owner}: authority status has no locating section"
        sections = {(ref.section_or_span or ref.locator) for ref in evidence}
        if support.status_section not in sections:
            return (
                f"{owner}: authority status section does not resolve "
                f"to cited evidence"
            )
    scope = binding.applicability
    if scope.subject_scope or scope.description:
        if not support.applicability_section:
            return f"{owner}: authority applicability has no locating section"
        sections = {(ref.section_or_span or ref.locator) for ref in evidence}
        if support.applicability_section not in sections:
            return (
                f"{owner}: authority applicability section does not "
                f"resolve to cited evidence"
            )
    return None


def _derive_trust(
    authority: m.CandidateAuthority | None,
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
                _requirements.missing_authority(
                    subject_or_claim=subject,
                    description=(f"no authority binding established for {kind_label}"),
                    supporting_context=(),
                ),
            ),
        )
    if authority.binding.status is m.AuthorityStatus.ACCEPTED:
        return m.TrustState.ESTABLISHED, ()
    return m.TrustState.PARTIAL, ()


def _stable_id(prefix: str, payload: object) -> str:
    digest = _hashlib.sha256(
        _json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _claim_content_payload(
    candidate: m.CandidateSemanticClaim, trust: m.TrustState
) -> object:
    stripped = m.CandidateSemanticClaim(
        candidate_key="",
        subject=candidate.subject,
        kind=candidate.kind,
        value=candidate.value,
        assertion_nature=candidate.assertion_nature,
        evidence=tuple(
            sorted(
                candidate.evidence,
                key=lambda r: (r.evidence_id.value, r.locator),
            )
        ),
        candidate_authority=candidate.candidate_authority,
        basis=m.SemanticBasis(
            derivation=candidate.basis.derivation,
            summary=candidate.basis.summary,
            input_refs=tuple(
                sorted(
                    (
                        (
                            r.id.value
                            if isinstance(r, (m.ClaimRef, m.RelationshipRef))
                            else r.evidence_id.value
                        )
                        for r in candidate.basis.input_refs
                    )
                )
            ),
        ),
    )
    return [m.to_canonical(stripped), trust.value]


def _relationship_content_payload(
    candidate: m.CandidateSemanticRelationship, trust: m.TrustState
) -> object:
    stripped = m.CandidateSemanticRelationship(
        candidate_key="",
        source=candidate.source,
        kind=candidate.kind,
        target=candidate.target,
        assertion_nature=candidate.assertion_nature,
        evidence=tuple(
            sorted(
                candidate.evidence,
                key=lambda r: (r.evidence_id.value, r.locator),
            )
        ),
        candidate_authority=candidate.candidate_authority,
        basis=m.SemanticBasis(
            derivation=candidate.basis.derivation,
            summary=candidate.basis.summary,
            input_refs=tuple(
                sorted(
                    (
                        (
                            r.id.value
                            if isinstance(r, (m.ClaimRef, m.RelationshipRef))
                            else r.evidence_id.value
                        )
                        for r in candidate.basis.input_refs
                    )
                )
            ),
        ),
    )
    return [m.to_canonical(stripped), trust.value]


def deterministic_claim_id(
    candidate: m.CandidateSemanticClaim, trust: m.TrustState
) -> m.ClaimId:
    """Stable id excluding unit-local candidate_key ([design note B](docs/design-references.md#b) B-03)."""
    return m.ClaimId(_stable_id("clm", _claim_content_payload(candidate, trust)))


def deterministic_relationship_id(
    candidate: m.CandidateSemanticRelationship, trust: m.TrustState
) -> m.RelationshipId:
    """Stable id excluding unit-local candidate_key ([design note B](docs/design-references.md#b) B-03)."""
    return m.RelationshipId(
        _stable_id("rel", _relationship_content_payload(candidate, trust))
    )


def _check_premise_refs(basis: m.SemanticBasis, owner: str) -> str | None:
    for ref in basis.input_refs:
        if isinstance(ref, (m.ClaimRef, m.RelationshipRef)):
            if not ref.id.value:
                return f"{owner}: premise ref has empty id"
        elif isinstance(ref, m.EvidenceRef):
            if not ref.evidence_id.value:
                return f"{owner}: premise evidence ref has empty id"
        else:
            return f"{owner}: premise ref has unknown shape"
    return None
