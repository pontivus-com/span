"""Candidate, question, conflict, and verification rules."""

from __future__ import annotations

from span.core import model as m


from span.core.validation.context import (
    CandidateValidation,
    FREE_TEXT_FIELDS,
    ValidationContext,
    _check_authority,
    _check_basis,
    _check_evidence,
    _check_premise_refs,
    _derive_trust,
    deterministic_claim_id,
    deterministic_relationship_id,
)


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
    # S6 §5.6: candidate ingress requires an explicit DESCRIPTIVE or
    # NORMATIVE nature; there is no default (missing fails at decode).
    nature = candidate.assertion_nature
    # Normative-only kinds assert assigned custody, contracts, or
    # governance: they cannot bypass authority by choosing descriptive.
    if (
        candidate.kind in m.NORMATIVE_ONLY_CLAIM_KINDS
        and nature is not m.AssertionNature.NORMATIVE
    ):
        return CandidateValidation(
            ok=False,
            trust=m.TrustState.UNRESOLVED,
            requirements=(),
            diagnostics=(
                f"claim kind {candidate.kind.value} is normative-only; "
                "descriptive nature cannot carry it",
            ),
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
        failure = _check_basis(candidate.basis, owner)
    if failure is None:
        failure = _check_premise_refs(candidate.basis, owner)
    if failure is None:
        failure = _check_authority(
            candidate.candidate_authority,
            candidate.evidence,
            candidate.basis.derivation,
            ctx,
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
            diagnostics=(f"relationship kind not allowed: {candidate.kind.value}",),
        )
    nature = candidate.assertion_nature
    if (
        candidate.kind.value in m.NORMATIVE_ONLY_RELATIONSHIP_KINDS
        and nature is not m.AssertionNature.NORMATIVE
    ):
        return CandidateValidation(
            ok=False,
            trust=m.TrustState.UNRESOLVED,
            requirements=(),
            diagnostics=(
                f"relationship kind {candidate.kind.value} is "
                "normative-only; descriptive nature cannot carry it",
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
        failure = _check_basis(candidate.basis, owner)
    if failure is None:
        failure = _check_premise_refs(candidate.basis, owner)
    if failure is None:
        failure = _check_authority(
            candidate.candidate_authority,
            candidate.evidence,
            candidate.basis.derivation,
            ctx,
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


def validate_candidate_subject(
    candidate: m.CandidateSubject, ctx: ValidationContext
) -> CandidateValidation:
    """Validate one proposed semantic-only subject (plan §4.11).

    Evidence-backed proposal; the structural provider never creates
    subjects. Locator collisions against distinct stored identities are
    resolved by the service as ambiguity, never overwrite — validation
    here checks only shape and evidence.
    """
    if not candidate.provisional_locator:
        return CandidateValidation(
            ok=False,
            trust=m.TrustState.UNRESOLVED,
            requirements=(),
            diagnostics=("subject provisional locator is empty",),
        )
    locator = candidate.provisional_locator
    if locator.startswith("/") or not locator or ".." in locator.split("/"):
        return CandidateValidation(
            ok=False,
            trust=m.TrustState.UNRESOLVED,
            requirements=(),
            diagnostics=("subject provisional locator is not repository-relative",),
        )
    for known in ctx.known_subject_ids:
        if known.canonical_locator == locator and known.subject_kind != candidate.kind:
            return CandidateValidation(
                ok=False,
                trust=m.TrustState.UNRESOLVED,
                requirements=(),
                diagnostics=("subject locator collides with a different-kind subject",),
            )
    if candidate.kind is m.SubjectKind.OTHER and not candidate.declared_kind:
        return CandidateValidation(
            ok=False,
            trust=m.TrustState.UNRESOLVED,
            requirements=(),
            diagnostics=("OTHER subject kind requires declared_kind",),
        )
    failure = _check_evidence(candidate.evidence, ctx, "subject proposal")
    if failure is None:
        failure = _check_basis(candidate.basis, "subject proposal")
    if failure is not None:
        return CandidateValidation(
            ok=False,
            trust=m.TrustState.UNRESOLVED,
            requirements=(),
            diagnostics=(failure,),
        )
    return CandidateValidation(True, m.TrustState.PARTIAL, (), ())


def validate_candidate_conflict(
    candidate: m.CandidateSemanticConflict,
    keys_in_result: frozenset[str],
    ctx: ValidationContext,
) -> CandidateValidation:
    """Validate one proposed free-text contradiction (plan §6.4)."""
    if not candidate.left_key or not candidate.right_key:
        return CandidateValidation(
            ok=False,
            trust=m.TrustState.UNRESOLVED,
            requirements=(),
            diagnostics=("conflict keys must be non-empty",),
        )
    if candidate.left_key == candidate.right_key:
        return CandidateValidation(
            ok=False,
            trust=m.TrustState.UNRESOLVED,
            requirements=(),
            diagnostics=("conflict keys must name two candidates",),
        )
    if (
        candidate.left_key not in keys_in_result
        or candidate.right_key not in keys_in_result
    ):
        return CandidateValidation(
            ok=False,
            trust=m.TrustState.UNRESOLVED,
            requirements=(),
            diagnostics=("conflict key does not resolve within the result",),
        )
    if candidate.candidate_precedence is not None:
        precedence = candidate.candidate_precedence
        if precedence.kind is m.PrecedenceKind.PRIORITY_RANK and (
            not precedence.precedence_scheme or precedence.overrides
        ):
            return CandidateValidation(
                ok=False,
                trust=m.TrustState.UNRESOLVED,
                requirements=(),
                diagnostics=("conflict precedence shape invalid",),
            )
    if not candidate.basis.summary:
        return CandidateValidation(
            ok=False,
            trust=m.TrustState.UNRESOLVED,
            requirements=(),
            diagnostics=("conflict basis summary is empty",),
        )
    return CandidateValidation(True, m.TrustState.PARTIAL, (), ())


def validate_question_coverage(
    coverage: m.InterpretationCoverage,
    ctx: ValidationContext,
    owner: str,
) -> str | None:
    question = coverage.question
    if question is None:
        return f"{owner}: question scope is missing"
    if not question.question_slice or not question.materiality_basis:
        return f"{owner}: question slice/materiality is empty"
    if question.subject not in ctx.known_subject_ids:
        return f"{owner}: question subject is not run-bound"
    if question.scope_root not in ctx.known_subject_ids:
        return f"{owner}: question scope_root is not run-bound"
    if coverage.disposition is m.SemanticQuestionDisposition.ANSWERED:
        # [design note C](docs/design-references.md#c) C-05: explicit ANSWERED is completion intent; result
        # refs are derived by the service from validated candidates before
        # persisting (empty refs here do not count as examined output).
        if not coverage.declared_complete:
            return f"{owner}: ANSWERED requires declared_complete"
    if coverage.disposition is m.SemanticQuestionDisposition.OPEN:
        if not coverage.resolution_requirements:
            return f"{owner}: OPEN requires resolution requirements"
    if coverage.disposition is m.SemanticQuestionDisposition.NOT_APPLICABLE:
        if coverage.result_refs:
            return f"{owner}: NOT_APPLICABLE requires empty result_refs"
        if not coverage.disposition_basis:
            return f"{owner}: NOT_APPLICABLE requires disposition_basis"
    for ref in coverage.result_refs:
        if not ref.id.value:
            return f"{owner}: result ref has empty id"
    for req in coverage.resolution_requirements:
        if not req.description:
            return f"{owner}: resolution requirement needs description"
    for obs in coverage.question_evidence:
        if obs.evidence_ref.evidence_id.value not in ctx.known_evidence_ids:
            return (
                f"{owner}: question evidence does not resolve: "
                f"{obs.evidence_ref.evidence_id.value}"
            )
    return None


def validate_candidate_withdrawal(
    withdrawal: m.CandidateSemanticWithdrawal,
    ctx: ValidationContext,
    known_result_ids: frozenset[str],
    owner: str,
) -> str | None:
    target_id = withdrawal.target.id.value
    if not target_id:
        return f"{owner}: withdrawal target has empty id"
    if target_id not in known_result_ids:
        return f"{owner}: withdrawal target is not in bound question scope"
    if not withdrawal.basis.summary:
        return f"{owner}: withdrawal basis summary is empty"
    failure = _check_evidence(withdrawal.evidence, ctx, owner)
    if failure is not None:
        return failure
    return _check_premise_refs(withdrawal.basis, owner)


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
    authority = (
        candidate.candidate_authority.binding
        if candidate.candidate_authority is not None
        else None
    )
    return m.SemanticClaim(
        claim_id=deterministic_claim_id(candidate, validation.trust),
        subject=candidate.subject,
        kind=candidate.kind,
        value=candidate.value,
        assertion_nature=candidate.assertion_nature,  # type: ignore[arg-type]
        evidence=candidate.evidence,
        authority=authority,
        trust=validation.trust,
        freshness=m.Freshness(
            state=m.FreshnessState.CURRENT,
            supporting_revision_or_fingerprint=(repository_state.state_fingerprint),
            reason=(
                "materialized from current evidence at repository state "
                + repository_state.state_fingerprint
            ),
        ),
        basis=candidate.basis,
    )


def validate_verification_records(
    repository_id: str,
    result: m.SemanticInterpretationResult,
    claims: tuple[m.SemanticClaim, ...],
) -> tuple[m.VerificationRecord, ...]:
    """Map an attested execution to the link that defines its scope.

    The agent never supplies the natural-key fingerprint: the verified
    scope is the matching verification link's evidence scope. Several
    links for one subject are unambiguous when they share that scope (a
    test and a gate over the same evidence); different scopes are
    rejected rather than guessed.
    """
    links = [claim for claim in claims if isinstance(claim.value, m.VerificationValue)]
    seen: set[tuple[str, str, str]] = set()
    accepted: list[m.VerificationRecord] = []
    for execution in result.verification_records:
        if execution.repository_id != repository_id:
            raise ValueError(
                "execution names another repository: " + execution.repository_id
            )
        matching = [
            claim
            for claim in links
            if claim.value.verification_ref == execution.subject
        ]
        if not matching:
            raise ValueError(
                "execution has no submitted verification link for "
                f"{execution.subject.canonical_locator}"
            )
        scopes = {
            m.evidence_scope_fingerprint(
                m.EvidenceScope(
                    paths=tuple(sorted({ref.locator for ref in claim.evidence})),
                    evidence_refs=(),
                )
            )
            for claim in matching
        }
        if len(scopes) != 1:
            raise ValueError(
                "ambiguous verification scope for "
                f"{execution.subject.canonical_locator}; submit one "
                "verification link per verified scope"
            )
        (scope_fingerprint,) = scopes
        key = (
            repository_id,
            execution.subject.canonical_locator,
            scope_fingerprint,
        )
        if key in seen:
            raise ValueError(
                "duplicate verification execution for one (subject, scope)"
            )
        seen.add(key)
        accepted.append(
            m.VerificationRecord(
                repository_id=execution.repository_id,
                subject=execution.subject,
                scope_fingerprint=scope_fingerprint,
                command=execution.command,
                exit_status=execution.exit_status,
                observed_revision=execution.observed_revision,
                observed_at=execution.observed_at,
                observer=execution.observer,
            )
        )
    return tuple(accepted)


def materialize_relationship(
    candidate: m.CandidateSemanticRelationship,
    validation: CandidateValidation,
    repository_state: m.RepositoryState,
) -> m.SemanticRelationship:
    """Build the canonical relationship from a validated candidate."""
    if not validation.ok:
        raise ValueError("cannot materialize a failed candidate")
    authority = (
        candidate.candidate_authority.binding
        if candidate.candidate_authority is not None
        else None
    )
    return m.SemanticRelationship(
        relationship_id=deterministic_relationship_id(candidate, validation.trust),
        source=candidate.source,
        kind=candidate.kind,
        target=candidate.target,
        assertion_nature=candidate.assertion_nature,  # type: ignore[arg-type]
        evidence=candidate.evidence,
        authority=authority,
        trust=validation.trust,
        freshness=m.Freshness(
            state=m.FreshnessState.CURRENT,
            supporting_revision_or_fingerprint=(repository_state.state_fingerprint),
            reason=(
                "materialized from current evidence at repository state "
                + repository_state.state_fingerprint
            ),
        ),
        basis=candidate.basis,
    )


def _structured_projection(value: m.TypedClaimValue) -> object:
    """Canonical value with free-text fields removed (§6.4).

    Differences confined to structured fields are core conflicts;
    differences involving free-text fields are never core conflicts.
    """
    canonical = m.to_canonical(value)
    if not isinstance(canonical, dict):
        return canonical
    free = FREE_TEXT_FIELDS.get(type(value), frozenset())
    return {
        key: item
        for key, item in canonical.items()
        if key not in free and key != "$type"
    }


def find_conflicts(
    claims: tuple[m.SemanticClaim, ...],
    relationships: tuple[m.SemanticRelationship, ...],
) -> tuple[m.SemanticConflict, ...]:
    """Detect conflicting current claims (pure, deterministic).

    A conflict is two claims over the same subject and kind whose
    structured projections differ (§6.4). Identical canonical values are
    the same assertion (dedupe). Free-text differences are never core
    conflicts — those arrive only as validated agent-proposed conflicts
    or explicit SUPERSEDES. A pair is resolved (excluded) only when a
    SUPERSEDES relationship with accepted authority runs between their
    subjects — the superseded side loses (plan I-08). Precedence-rank
    resolution beyond SUPERSEDES belongs to a later phase.
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
                if _structured_projection(left.value) == _structured_projection(
                    right.value
                ):
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


def validate_target_questions(
    questions: tuple[m.SemanticQuestionScope, ...],
    *,
    admitted_area_ids: tuple[m.SubjectId, ...],
) -> CandidateValidation:
    """Every referenced question must belong to an admitted area."""
    admitted = set(admitted_area_ids)
    for q in questions:
        if q.scope_root not in admitted:
            return CandidateValidation(
                False,
                m.TrustState.UNRESOLVED,
                (),
                (
                    f"target question root not admitted: {q.scope_root.canonical_locator}",
                ),
            )
    return CandidateValidation(True, m.TrustState.ESTABLISHED, (), ())
