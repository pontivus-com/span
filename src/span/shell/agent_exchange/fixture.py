"""Deterministic fixture agent (test stand-in for the §11.12 boundary).

Returns canned candidates per subject locator from an explicit fixture
map. This is a test substitute for the invoking agent — it frames what
an agent would submit, and proves Span's request → validate/materialize
path. It is not evidence of any production provider interface (of which
Span has none). Obeys the §7.2 contract shape: only allowed kinds are
emitted, and fixture content exceeding the request bounds is a fixture
authoring error (raised, never silently widened).
"""

from __future__ import annotations

from dataclasses import dataclass as _dataclass

from span.core import model as m

__all__ = ["FixtureCandidates", "FixtureAgent"]


@_dataclass(frozen=True)
class FixtureCandidates:
    claims: tuple[m.CandidateSemanticClaim, ...] = ()
    relationships: tuple[m.CandidateSemanticRelationship, ...] = ()
    subjects: tuple[m.CandidateSubject, ...] = ()
    conflicts: tuple[m.CandidateSemanticConflict, ...] = ()


class FixtureAgent:
    """Deterministic test agent over a canned candidate map."""

    def __init__(
        self,
        mapping: dict[str, FixtureCandidates],
        complete_questions: bool = False,
    ) -> None:
        self._mapping = dict(mapping)
        # Addendum C C-05 cutover: claims alone never complete a
        # question. When enabled, the fixture attaches explicit
        # ANSWERED completion intent for the bound question, letting
        # the service derive result refs from validated candidates.
        self._complete_questions = complete_questions

    def perform(
        self, request: m.SemanticInterpretationRequest
    ) -> m.SemanticInterpretationResult:
        """Perform the bounded interpretation task (test-only execution)."""
        allowed_claims = set(request.allowed_claim_kinds)
        allowed_rels = set(request.allowed_relationship_kinds)
        claims: list[m.CandidateSemanticClaim] = []
        relationships: list[m.CandidateSemanticRelationship] = []
        candidate_subjects: list[m.CandidateSubject] = []
        conflicts: list[m.CandidateSemanticConflict] = []
        # A mapping unit is whole-target inventory accounting, not a
        # semantic unit: its contract carries accounts, never claims.
        if not request.target_inventory_items:
            for subject in request.subjects:
                canned = self._mapping.get(subject.subject_id.canonical_locator)
                if canned is None:
                    continue
                claims.extend(c for c in canned.claims if c.kind in allowed_claims)
                relationships.extend(
                    r for r in canned.relationships if r.kind in allowed_rels
                )
                candidate_subjects.extend(canned.subjects)
                conflicts.extend(canned.conflicts)
        if len(claims) > request.bounds.max_candidate_claims:
            raise ValueError(
                "fixture claims exceed max_candidate_claims "
                f"({request.bounds.max_candidate_claims})"
            )
        if len(relationships) > request.bounds.max_candidate_relationships:
            raise ValueError(
                "fixture relationships exceed max_candidate_relationships "
                f"({request.bounds.max_candidate_relationships})"
            )
        refs: list[m.EvidenceRef] = []
        for claim in claims:
            refs.extend(claim.evidence)
            if claim.candidate_authority is not None:
                refs.append(claim.candidate_authority.binding.evidence_ref)
        for rel in relationships:
            refs.extend(rel.evidence)
            if rel.candidate_authority is not None:
                refs.append(rel.candidate_authority.binding.evidence_ref)
        for subject in candidate_subjects:
            refs.extend(subject.evidence)
        by_id = {r.evidence_id.value: r for r in refs}
        governing = sorted(
            {
                c.candidate_authority.binding.evidence_ref.evidence_id.value
                for c in claims
                if c.candidate_authority is not None
            }
            | {
                r.candidate_authority.binding.evidence_ref.evidence_id.value
                for r in relationships
                if r.candidate_authority is not None
            }
        )
        # A mapping unit must account for every bound inventory item.
        # The fixture does not examine them, so it states that rather
        # than silently leaving the batch unaccounted.
        inventory_accounts = tuple(
            m.CandidateTargetInventoryAccount(
                evidence_id=item.evidence_ref.evidence_id,
                resolution_requirements=(
                    m.ResolutionRequirement(
                        kind=m.ResolutionKind.MISSING_SEMANTIC_COVERAGE,
                        subject_or_claim=None,
                        description="fixture did not examine this member",
                        supporting_context=(),
                    ),
                ),
            )
            for item in request.target_inventory_items
        )
        question_decision: m.SemanticQuestionDecision | None = None
        if self._complete_questions and request.question is not None:
            question_decision = m.SemanticQuestionDecision(
                disposition=m.SemanticQuestionDisposition.ANSWERED,
                disposition_basis="fixture explicit completion intent",
            )
        return m.SemanticInterpretationResult(
            claims=tuple(claims),
            relationships=tuple(relationships),
            question_decision=question_decision,
            governing_source_refs=tuple(
                by_id[eid] for eid in governing if eid in by_id
            ),
            diagnostics=(
                f"fixture: {len(request.subjects)} subjects, "
                f"{len(claims)} claims, {len(relationships)} relationships",
            ),
            candidate_subjects=tuple(candidate_subjects),
            candidate_conflicts=tuple(conflicts),
            proposed_target_inventory_accounting=inventory_accounts,
        )
