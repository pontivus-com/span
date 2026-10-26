"""Cited-evidence admission and candidate normalization."""

from __future__ import annotations

import dataclasses as _dataclasses

from span.core import model as m
from span.core import validation as _validation
from span.ports.evidence import EvidenceSource

from span.service.interpretation.task import (
    InterpretationTask,
)


def _validation_context_for(
    task: InterpretationTask,
    extra_known: tuple[m.SubjectId, ...] = (),
) -> _validation.ValidationContext:
    return _validation.ValidationContext(
        allowed_claim_kinds=tuple(m.ClaimKind),
        allowed_relationship_kinds=tuple(m.RelationshipKind),
        known_evidence_ids=frozenset(eid for eid, _ in task.fingerprints),
        known_subject_ids=task.known_subject_ids + extra_known,
        evidence_fingerprints=dict(task.fingerprints),
        evidence_contents={
            unit.evidence_ref.evidence_id.value: unit.content
            for unit in task.request.task_evidence.evidence_units
        },
        evidence_refs={
            unit.evidence_ref.evidence_id.value: unit.evidence_ref
            for unit in task.request.task_evidence.evidence_units
        },
    )


def _assign_candidate_keys(
    result: m.SemanticInterpretationResult,
) -> m.SemanticInterpretationResult:
    """Deterministic key assignment (plan §4.11 discipline).

    Explicit keys link conflict proposals; empty keys receive
    deterministic `auto:<index>` values so every result carries unique
    non-empty keys. Explicit duplicates reject the unit.
    """
    keys = [c.candidate_key for c in result.claims] + [
        r.candidate_key for r in result.relationships
    ]
    seen: dict[str, int] = {}
    duplicates: list[str] = []
    for index, key in enumerate(keys):
        if not key:
            continue
        if key in seen:
            for dup_index in (seen[key], index):
                member = (
                    f"claims[{dup_index}]"
                    if dup_index < len(result.claims)
                    else f"relationships[{dup_index - len(result.claims)}]"
                )
                duplicates.append(f"{member} (key={key})")
        else:
            seen[key] = index
    if duplicates:
        raise _validation.InterpretationUnitRejected(
            tuple(
                f"{label}: duplicate candidate_key in interpretation result"
                for label in duplicates
            )
        )
    if all(keys):
        return result
    claims = tuple(
        (
            c
            if c.candidate_key
            else m.CandidateSemanticClaim(
                candidate_key=f"auto-{n}",
                subject=c.subject,
                kind=c.kind,
                value=c.value,
                assertion_nature=c.assertion_nature,
                evidence=c.evidence,
                candidate_authority=c.candidate_authority,
                basis=c.basis,
            )
        )
        for n, c in enumerate(result.claims)
    )
    relationships = tuple(
        (
            r
            if r.candidate_key
            else m.CandidateSemanticRelationship(
                candidate_key=f"auto-c{len(result.claims) + n}",
                source=r.source,
                kind=r.kind,
                target=r.target,
                assertion_nature=r.assertion_nature,
                evidence=r.evidence,
                candidate_authority=r.candidate_authority,
                basis=r.basis,
            )
        )
        for n, r in enumerate(result.relationships)
    )
    return _dataclasses.replace(
        result,
        claims=claims,
        relationships=relationships,
    )


def _normalize_cited_ref(
    cited: m.EvidenceRef,
    canonical: m.EvidenceRef,
    observed_fingerprint: str,
) -> m.EvidenceRef:
    """Project one agent-supplied ref onto its canonical observation.

    Base identity is already verified equal by the caller. The
    observation fingerprint always comes from the provider; the span
    survives only when it equals the canonical span, else it strips to
    None (file-level citation, location unasserted).
    """
    return m.EvidenceRef(
        evidence_id=cited.evidence_id,
        repository_id=canonical.repository_id,
        source_kind=canonical.source_kind,
        locator=canonical.locator,
        revision_or_fingerprint=observed_fingerprint,
        section_or_span=(
            cited.section_or_span
            if cited.section_or_span == canonical.section_or_span
            else None
        ),
    )


def _note_citation(
    cited_by_id: dict[str, list[m.EvidenceRef]],
    ref: m.EvidenceRef,
) -> None:
    cited_by_id.setdefault(ref.evidence_id.value, []).append(ref)


def _note_nested_basis(
    cited_by_id: dict[str, list[m.EvidenceRef]],
    basis: m.SemanticBasis,
) -> None:
    # Basis input refs persist inside claims, relationships, and recorded
    # conflicts: unverifiable nested provenance must not reach canonical state,
    # so nested evidence goes through the same provider admission as primary
    # citations.
    for input_ref in basis.input_refs:
        if isinstance(input_ref, m.EvidenceRef):
            _note_citation(cited_by_id, input_ref)


def _note_nested_requirements(
    cited_by_id: dict[str, list[m.EvidenceRef]],
    requirements: tuple[m.ResolutionRequirement, ...],
) -> None:
    # Requirement supporting context persists inside coverages and target
    # accounts: same admission rule as basis input refs.
    for requirement in requirements:
        for context_ref in requirement.supporting_context:
            if isinstance(context_ref, m.EvidenceRef):
                _note_citation(cited_by_id, context_ref)


def _note_decision(
    cited_by_id: dict[str, list[m.EvidenceRef]],
    decision: m.SemanticQuestionDecision,
) -> None:
    # The agent owns only its selected support scope and typed requirements;
    # those are the only command-shaped citations.
    for ref in decision.evidence_scope.evidence_refs:
        _note_citation(cited_by_id, ref)
    _note_nested_requirements(cited_by_id, decision.resolution_requirements)


def _collect_citations(
    result: m.SemanticInterpretationResult,
) -> dict[str, list[m.EvidenceRef]]:
    """Index every evidence citation the submission makes, by identity."""
    cited_by_id: dict[str, list[m.EvidenceRef]] = {}
    for candidate in (*result.claims, *result.relationships):
        for ref in candidate.evidence:
            _note_citation(cited_by_id, ref)
        authority = candidate.candidate_authority
        if authority is not None:
            _note_citation(cited_by_id, authority.binding.evidence_ref)
        _note_nested_basis(cited_by_id, candidate.basis)
    for proposed in result.candidate_subjects:
        for ref in proposed.evidence:
            _note_citation(cited_by_id, ref)
        _note_nested_basis(cited_by_id, proposed.basis)
    for withdrawal in result.candidate_withdrawals:
        for ref in withdrawal.evidence:
            _note_citation(cited_by_id, ref)
        _note_nested_basis(cited_by_id, withdrawal.basis)
    for conflict in result.candidate_conflicts:
        _note_nested_basis(cited_by_id, conflict.basis)
        if conflict.candidate_precedence is not None:
            for ref in conflict.candidate_precedence.overrides:
                _note_citation(cited_by_id, ref)
    if result.question_decision is not None:
        _note_decision(cited_by_id, result.question_decision)
    for proposed in result.proposed_questions:
        _note_decision(cited_by_id, proposed.decision)
    return cited_by_id


@_dataclasses.dataclass
class _CitationAdmission:
    """Outcome of resolving one unit's new citations with the provider.

    ``fatal`` means the submission cannot be trusted at all and the unit is
    returned unchanged; otherwise ``problems`` isolates the individual
    citations that failed admission.
    """

    fatal: str | None
    problems: list[str]


@_dataclasses.dataclass
class _EvidenceNormalizer:
    """Rewrite citations to provider-canonical identity, once per unit."""

    canonical_refs: dict[str, m.EvidenceRef]
    fingerprints: dict[str, str]

    def ref(self, ref: m.EvidenceRef) -> m.EvidenceRef:
        canonical = self.canonical_refs.get(ref.evidence_id.value)
        if canonical is None:
            return ref
        return _normalize_cited_ref(
            ref,
            canonical,
            self.fingerprints[ref.evidence_id.value],
        )

    def basis(self, basis: m.SemanticBasis) -> m.SemanticBasis:
        return _dataclasses.replace(
            basis,
            input_refs=tuple(
                (
                    self.ref(input_ref)
                    if isinstance(input_ref, m.EvidenceRef)
                    else input_ref
                )
                for input_ref in basis.input_refs
            ),
        )

    def requirement(
        self,
        requirement: m.ResolutionRequirement,
    ) -> m.ResolutionRequirement:
        return _dataclasses.replace(
            requirement,
            supporting_context=tuple(
                (
                    self.ref(context_ref)
                    if isinstance(context_ref, m.EvidenceRef)
                    else context_ref
                )
                for context_ref in requirement.supporting_context
            ),
        )

    def precedence(
        self,
        precedence: m.DeclaredPrecedence | None,
    ) -> m.DeclaredPrecedence | None:
        if precedence is None:
            return None
        return _dataclasses.replace(
            precedence,
            overrides=tuple(self.ref(ref) for ref in precedence.overrides),
        )

    def authority(
        self,
        authority: m.CandidateAuthority | None,
    ) -> m.CandidateAuthority | None:
        if authority is None:
            return None
        return _dataclasses.replace(
            authority,
            binding=_dataclasses.replace(
                authority.binding,
                evidence_ref=self.ref(authority.binding.evidence_ref),
            ),
        )

    def decision(
        self,
        decision: m.SemanticQuestionDecision,
    ) -> m.SemanticQuestionDecision:
        return _dataclasses.replace(
            decision,
            evidence_scope=_dataclasses.replace(
                decision.evidence_scope,
                evidence_refs=tuple(
                    self.ref(ref) for ref in decision.evidence_scope.evidence_refs
                ),
            ),
            resolution_requirements=tuple(
                self.requirement(requirement)
                for requirement in decision.resolution_requirements
            ),
        )

    def submission(
        self,
        result: m.SemanticInterpretationResult,
    ) -> m.SemanticInterpretationResult:
        claims = tuple(
            _dataclasses.replace(
                candidate,
                evidence=tuple(self.ref(ref) for ref in candidate.evidence),
                candidate_authority=self.authority(candidate.candidate_authority),
                basis=self.basis(candidate.basis),
            )
            for candidate in result.claims
        )
        relationships = tuple(
            _dataclasses.replace(
                candidate,
                evidence=tuple(self.ref(ref) for ref in candidate.evidence),
                candidate_authority=self.authority(candidate.candidate_authority),
                basis=self.basis(candidate.basis),
            )
            for candidate in result.relationships
        )
        subjects = tuple(
            _dataclasses.replace(
                proposed,
                evidence=tuple(self.ref(ref) for ref in proposed.evidence),
                basis=self.basis(proposed.basis),
            )
            for proposed in result.candidate_subjects
        )
        conflicts = tuple(
            _dataclasses.replace(
                conflict,
                candidate_precedence=self.precedence(conflict.candidate_precedence),
                basis=self.basis(conflict.basis),
            )
            for conflict in result.candidate_conflicts
        )
        withdrawals = tuple(
            _dataclasses.replace(
                withdrawal,
                evidence=tuple(self.ref(ref) for ref in withdrawal.evidence),
                basis=self.basis(withdrawal.basis),
            )
            for withdrawal in result.candidate_withdrawals
        )
        return _dataclasses.replace(
            result,
            claims=claims,
            relationships=relationships,
            governing_source_refs=tuple(
                self.ref(ref) for ref in result.governing_source_refs
            ),
            candidate_subjects=subjects,
            candidate_conflicts=conflicts,
            question_decision=(
                None
                if result.question_decision is None
                else self.decision(result.question_decision)
            ),
            proposed_questions=tuple(
                _dataclasses.replace(
                    proposed,
                    decision=self.decision(proposed.decision),
                )
                for proposed in result.proposed_questions
            ),
            candidate_withdrawals=withdrawals,
        )


def _admit_referenced_citations(
    repository_id: str,
    cited_by_id: dict[str, list[m.EvidenceRef]],
    wanted: list[str],
    *,
    evidence: EvidenceSource,
    bounds: m.QueryBounds,
    normalizer: _EvidenceNormalizer,
    contents: dict[str, str],
) -> _CitationAdmission:
    """Resolve each citation unknown to the task against the provider."""
    try:
        page = evidence.inventory_evidence(
            repository_id,
            m.EvidenceScope(
                paths=(),
                evidence_refs=tuple(
                    ref for evidence_id in wanted for ref in cited_by_id[evidence_id]
                ),
            ),
            bounds,
        )
    except ValueError as exc:
        return _CitationAdmission(
            fatal=f"cited evidence inventory unavailable: {exc}",
            problems=[],
        )
    try:
        from span.service.discovery import check_inventory_identity

        items = check_inventory_identity(tuple(page.items))
    except ValueError as exc:
        return _CitationAdmission(fatal=f"cited evidence {exc}", problems=[])
    by_id = {item.evidence_ref.evidence_id.value: item for item in items}
    problems: list[str] = []
    for evidence_id in wanted:
        item = by_id.get(evidence_id)
        if item is None:
            problems.append(f"unknown evidence identity: {evidence_id}")
            continue
        canonical = item.evidence_ref
        if any(
            ref.repository_id != repository_id
            or ref.locator != canonical.locator
            or ref.source_kind != canonical.source_kind
            for ref in cited_by_id[evidence_id]
        ):
            problems.append(
                "cited evidence identity does not match "
                f"provider snapshot: {evidence_id}"
            )
            continue
        try:
            units = evidence.read_evidence((canonical,), bounds)
        except ValueError:
            problems.append(f"cited evidence is unreadable: {evidence_id}")
            continue
        if len(units) != 1:
            problems.append(f"cited evidence is unreadable: {evidence_id}")
            continue
        (unit,) = units
        normalizer.fingerprints[evidence_id] = unit.content_fingerprint
        contents[evidence_id] = unit.content
        normalizer.canonical_refs[evidence_id] = m.EvidenceRef(
            evidence_id=canonical.evidence_id,
            repository_id=canonical.repository_id,
            source_kind=canonical.source_kind,
            locator=canonical.locator,
            revision_or_fingerprint=unit.content_fingerprint,
            section_or_span=canonical.section_or_span,
        )
    return _CitationAdmission(fatal=None, problems=problems)


def _admit_cited_evidence(
    repository_id: str,
    result: m.SemanticInterpretationResult,
    ctx: _validation.ValidationContext,
    *,
    evidence: EvidenceSource,
    bounds: m.QueryBounds,
) -> tuple[
    _validation.ValidationContext,
    m.SemanticInterpretationResult,
    list[str],
]:
    """Admit cited evidence against the canonical provider ([design note H](docs/design-references.md#h) §5).

    Every agent-supplied ``EvidenceRef`` unknown to the task is resolved
    to the provider-canonical identity; base-identity mismatch,
    unknown identity, or unreadable bytes come back as problems — never
    silently admitted. Recorded history never gates admission: a
    fingerprint that differs from recorded observations admits the
    current bytes (old rows keep old fingerprints and go stale through
    existing freshness). Returns the extended context, the normalized
    submission (same carrier; normalized before validation so
    deterministic ids derive from persisted refs), and problems.
    """
    cited_by_id = _collect_citations(result)
    wanted = sorted(
        evidence_id
        for evidence_id in cited_by_id
        if evidence_id not in ctx.known_evidence_ids
    )
    normalizer = _EvidenceNormalizer(
        canonical_refs=dict(ctx.evidence_refs),
        fingerprints=dict(ctx.evidence_fingerprints),
    )
    contents = dict(ctx.evidence_contents)
    problems: list[str] = []
    if wanted:
        admission = _admit_referenced_citations(
            repository_id,
            cited_by_id,
            wanted,
            evidence=evidence,
            bounds=bounds,
            normalizer=normalizer,
            contents=contents,
        )
        if admission.fatal is not None:
            return ctx, result, [admission.fatal]
        problems = admission.problems
    return (
        _dataclasses.replace(
            ctx,
            known_evidence_ids=ctx.known_evidence_ids
            | frozenset(normalizer.fingerprints),
            evidence_fingerprints=normalizer.fingerprints,
            evidence_contents=contents,
            evidence_refs=normalizer.canonical_refs,
        ),
        normalizer.submission(result),
        problems,
    )
