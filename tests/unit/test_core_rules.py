"""Core rule tests (plan Phase 1.3/1.4).

Covers candidate validation, trust derivation, conflict detection with
SUPERSEDES resolution, deterministic ids, freshness classification, and
answer-composition helpers.
"""

import unittest

from span.core import answers as ans
from span.core import freshness as fresh
from span.core import model as m
from span.core import validation as v


def _sid(locator="src/a.py"):
    return m.SubjectId(
        repository_id="repo-1",
        subject_kind=m.SubjectKind.COMPONENT,
        canonical_locator=locator,
    )


def _ref(eid="ev-src/a.py", locator="src/a.py"):
    return m.EvidenceRef(
        evidence_id=m.EvidenceId(eid),
        repository_id="repo-1",
        source_kind=m.EvidenceSourceKind.SOURCE_CODE,
        locator=locator,
        revision_or_fingerprint="fp-1",
    )


def _ctx(**overrides):
    base = dict(
        allowed_claim_kinds=tuple(m.ClaimKind),
        allowed_relationship_kinds=tuple(m.RelationshipKind),
        known_evidence_ids=frozenset({"ev-src/a.py"}),
        known_subject_ids=(_sid(),),
        evidence_fingerprints={"ev-src/a.py": "fp-1"},
        evidence_contents={"ev-src/a.py": "owns orders module scope"},
    )
    base.update(overrides)
    return v.ValidationContext(**base)


def _claim(**overrides):
    base = dict(
        subject=_sid(),
        kind=m.ClaimKind.PURPOSE,
        assertion_nature=m.AssertionNature.DESCRIPTIVE,
        value=m.PurposeValue("does X", ()),
        evidence=(_ref(),),
        candidate_authority=None,
        basis=m.SemanticBasis(
            m.DerivationKind.SEMANTIC_INTERPRETATION,
            "test candidate restating cited evidence",
        ),
    )
    base.update(overrides)
    return m.CandidateSemanticClaim(**base)


def _accepted_binding():
    return m.AuthorityBinding(
        evidence_ref=_ref(),
        authority_kind=m.AuthorityKind.REPOSITORY_RULE,
        status=m.AuthorityStatus.ACCEPTED,
    )


def _support(**overrides):
    base = dict(
        quoted_span="owns orders",
        status_section="src/a.py",
        applicability_section=None,
    )
    base.update(overrides)
    return m.AuthoritySupport(**base)


def _candidate_authority(binding=None, support=None):
    return m.CandidateAuthority(
        binding=binding or _accepted_binding(),
        support=support or _support(),
    )


def _state():
    import datetime as dt

    return m.RepositoryState(
        repository_id="repo-1", revision_id="r1", dirty=False,
        state_fingerprint="state-fp",
        observed_at=dt.datetime(2026, 10, 7, tzinfo=dt.timezone.utc),
    )


class CandidateValidationTest(unittest.TestCase):
    def test_disallowed_kind_rejected(self):
        result = v.validate_candidate_claim(
            _claim(), _ctx(allowed_claim_kinds=(m.ClaimKind.RESPONSIBILITY,))
        )
        self.assertFalse(result.ok)
        self.assertIn("not allowed", result.diagnostics[0])

    def test_unknown_subject_rejected(self):
        other = m.SubjectId(
            repository_id="repo-1",
            subject_kind=m.SubjectKind.COMPONENT,
            canonical_locator="src/other.py",
        )
        result = v.validate_candidate_claim(_claim(subject=other), _ctx())
        self.assertFalse(result.ok)

    def test_missing_evidence_rejected(self):
        result = v.validate_candidate_claim(_claim(evidence=()), _ctx())
        self.assertFalse(result.ok)

    def test_unresolving_evidence_rejected(self):
        result = v.validate_candidate_claim(
            _claim(), _ctx(known_evidence_ids=frozenset())
        )
        self.assertFalse(result.ok)

    def test_unknown_authority_status_rejected(self):
        binding = m.AuthorityBinding(
            evidence_ref=_ref(),
            authority_kind=m.AuthorityKind.REPOSITORY_RULE,
            status=m.AuthorityStatus.UNKNOWN,
        )
        result = v.validate_candidate_claim(
            _claim(candidate_authority=_candidate_authority(binding)), _ctx()
        )
        self.assertFalse(result.ok)

    def test_structural_derivation_cannot_carry_authority(self):
        binding = _accepted_binding()
        candidate = _claim(
            candidate_authority=_candidate_authority(binding),
            basis=m.SemanticBasis(
                m.DerivationKind.STRUCTURAL_OBSERVATION,
                "test candidate restating cited evidence",
            ),
        )
        result = v.validate_candidate_claim(candidate, _ctx())
        self.assertFalse(result.ok)

    def test_authority_evidence_must_be_cited(self):
        other_ref = m.EvidenceRef(
            evidence_id=m.EvidenceId("ev-other"),
            repository_id="repo-1",
            source_kind=m.EvidenceSourceKind.DOCUMENTATION,
            locator="OWNERS.md",
        )
        binding = m.AuthorityBinding(
            evidence_ref=other_ref,
            authority_kind=m.AuthorityKind.REPOSITORY_RULE,
            status=m.AuthorityStatus.ACCEPTED,
        )
        result = v.validate_candidate_claim(
            _claim(candidate_authority=_candidate_authority(binding)),
            _ctx(
                known_evidence_ids=frozenset({"ev-src/a.py", "ev-other"}),
                evidence_fingerprints={
                    "ev-src/a.py": "fp-1", "ev-other": "fp-2",
                },
            ),
        )
        self.assertFalse(result.ok)

    def test_accepted_authority_establishes(self):
        result = v.validate_candidate_claim(
            _claim(candidate_authority=_candidate_authority()), _ctx()
        )
        self.assertTrue(result.ok)
        self.assertIs(result.trust, m.TrustState.ESTABLISHED)
        self.assertEqual(result.requirements, ())

    def test_draft_authority_is_partial(self):
        binding = m.AuthorityBinding(
            evidence_ref=_ref(),
            authority_kind=m.AuthorityKind.REPOSITORY_RULE,
            status=m.AuthorityStatus.DRAFT,
        )
        result = v.validate_candidate_claim(
            _claim(candidate_authority=_candidate_authority(binding)), _ctx()
        )
        self.assertTrue(result.ok)
        self.assertIs(result.trust, m.TrustState.PARTIAL)

    def test_support_quote_must_be_verbatim(self):
        candidate = _claim(
            candidate_authority=_candidate_authority(
                support=_support(quoted_span="not in evidence")
            )
        )
        result = v.validate_candidate_claim(candidate, _ctx())
        self.assertFalse(result.ok)
        self.assertIn("verbatim", result.diagnostics[0])

    def test_support_sections_must_resolve(self):
        candidate = _claim(
            candidate_authority=_candidate_authority(
                support=_support(status_section="nowhere.md")
            )
        )
        result = v.validate_candidate_claim(candidate, _ctx())
        self.assertFalse(result.ok)

    def test_missing_authority_unresolved_with_requirement(self):
        result = v.validate_candidate_claim(_claim(), _ctx())
        self.assertTrue(result.ok)
        self.assertIs(result.trust, m.TrustState.UNRESOLVED)
        self.assertEqual(len(result.requirements), 1)
        self.assertIs(
            result.requirements[0].kind, m.ResolutionKind.MISSING_AUTHORITY
        )

    def test_relationship_endpoint_must_be_known(self):
        rel = m.CandidateSemanticRelationship(
            source=_sid(),
            kind=m.RelationshipKind.MEMBER_OF,
        assertion_nature=m.AssertionNature.DESCRIPTIVE,
            target=m.SubjectId(
                repository_id="repo-1",
                subject_kind=m.SubjectKind.CAPABILITY,
                canonical_locator="cap/x",
            ),
            evidence=(_ref(),),
            basis=m.SemanticBasis(m.DerivationKind.SEMANTIC_INTERPRETATION),
        )
        result = v.validate_candidate_relationship(rel, _ctx())
        self.assertFalse(result.ok)


class MaterializeTest(unittest.TestCase):
    def test_ids_are_deterministic(self):
        candidate = _claim(candidate_authority=_candidate_authority())
        result = v.validate_candidate_claim(candidate, _ctx())
        first = v.materialize_claim(candidate, result, _state())
        second = v.materialize_claim(candidate, result, _state())
        self.assertEqual(first.claim_id, second.claim_id)
        self.assertTrue(first.claim_id.value.startswith("clm-"))
        self.assertIs(
            first.freshness.state, m.FreshnessState.CURRENT
        )

    def test_failed_candidate_not_materialized(self):
        result = v.validate_candidate_claim(_claim(evidence=()), _ctx())
        with self.assertRaises(ValueError):
            v.materialize_claim(_claim(evidence=()), result, _state())


class ConflictDetectionTest(unittest.TestCase):
    def _established(self, cid, kind, value):
        return m.SemanticClaim(
            claim_id=m.ClaimId(cid),
            subject=_sid(),
            kind=kind,
            value=value,
            assertion_nature=m.AssertionNature.NORMATIVE,
            evidence=(_ref(),),
            authority=_accepted_binding(),
            trust=m.TrustState.ESTABLISHED,
            freshness=m.Freshness(m.FreshnessState.CURRENT, reason="t"),
            basis=m.SemanticBasis(m.DerivationKind.EXPLICIT_EVIDENCE),
        )

    def _purpose(self, cid, summary):
        return self._established(
            cid, m.ClaimKind.PURPOSE, m.PurposeValue(summary, ())
        )

    def _verification(self, cid, currency):
        return self._established(
            cid,
            m.ClaimKind.VERIFICATION,
            m.VerificationValue(
                _sid(), m.VerificationKind.TEST, currency
            ),
        )

    def test_equal_values_no_conflict(self):
        pair = (
            self._purpose("c-1", "same"), self._purpose("c-2", "same")
        )
        self.assertEqual(v.find_conflicts(pair, ()), ())

    def test_structured_difference_conflicts(self):
        pair = (
            self._verification("c-1", m.VerificationCurrency.CURRENT_PASS),
            self._verification("c-2", m.VerificationCurrency.CURRENT_FAIL),
        )
        conflicts = v.find_conflicts(pair, ())
        self.assertEqual(len(conflicts), 1)
        self.assertIsNone(conflicts[0].declared_precedence)

    def test_free_text_difference_is_not_a_core_conflict(self):
        # Different statements are not necessarily conflicting
        # statements (§6.4): free-text differences need an agent
        # proposal or explicit supersession.
        pair = (
            self._purpose("c-1", "does X"),
            self._purpose("c-2", "does Y"),
        )
        self.assertEqual(v.find_conflicts(pair, ()), ())

    def test_accepted_supersedes_resolves(self):
        pair = (
            self._verification("c-1", m.VerificationCurrency.CURRENT_PASS),
            self._verification("c-2", m.VerificationCurrency.CURRENT_FAIL),
        )
        sup = m.SemanticRelationship(
            relationship_id=m.RelationshipId("r-sup"),
            source=_sid("src/b.py"),
            kind=m.RelationshipKind.SUPERSEDES,
        assertion_nature=m.AssertionNature.NORMATIVE,
            target=_sid(),
            evidence=(_ref(),),
            authority=_accepted_binding(),
            trust=m.TrustState.ESTABLISHED,
            freshness=m.Freshness(m.FreshnessState.CURRENT, reason="t"),
            basis=m.SemanticBasis(m.DerivationKind.EXPLICIT_EVIDENCE),
        )
        # Different subject pair: no resolution effect here.
        self.assertEqual(len(v.find_conflicts(pair, (sup,))), 1)

    def test_agent_proposed_conflict_validates(self):
        candidate = m.CandidateSemanticConflict(
            left_key="k1",
            right_key="k2",
            basis=m.SemanticBasis(
                m.DerivationKind.SEMANTIC_INTERPRETATION,
                summary="contradictory responsibilities",
            ),
        )
        result = v.validate_candidate_conflict(
            candidate, frozenset({"k1", "k2"}), _ctx()
        )
        self.assertTrue(result.ok)
        dangling = m.CandidateSemanticConflict(
            left_key="k1",
            right_key="k9",
            basis=m.SemanticBasis(
                m.DerivationKind.SEMANTIC_INTERPRETATION,
                summary="x",
            ),
        )
        bad = v.validate_candidate_conflict(
            dangling, frozenset({"k1", "k2"}), _ctx()
        )
        self.assertFalse(bad.ok)

    def test_subject_proposal_validates(self):
        good = m.CandidateSubject(
            provisional_locator="docs/cap-billing.md",
            kind=m.SubjectKind.CAPABILITY,
            display_name="Billing",
            evidence=(_ref(),),
            basis=m.SemanticBasis(
                m.DerivationKind.SEMANTIC_INTERPRETATION,
                "test proposal restating cited evidence",
            ),
        )
        self.assertTrue(
            v.validate_candidate_subject(good, _ctx()).ok
        )
        bad = m.CandidateSubject(
            provisional_locator="",
            kind=m.SubjectKind.CAPABILITY,
            display_name="Billing",
            evidence=(_ref(),),
        )
        self.assertFalse(
            v.validate_candidate_subject(bad, _ctx()).ok
        )


class FreshnessClassificationTest(unittest.TestCase):
    def test_current(self):
        out = fresh.classify_dependency("fp-1", "fp-1")
        self.assertIs(out.state, m.FreshnessState.CURRENT)

    def test_stale(self):
        out = fresh.classify_dependency("fp-1", "fp-2")
        self.assertIs(out.state, m.FreshnessState.STALE)

    def test_unverifiable(self):
        out = fresh.classify_dependency("fp-1", None)
        self.assertIs(out.state, m.FreshnessState.UNVERIFIABLE)

    def test_classify_all_only_updates_non_current(self):
        dep_current = m.EvidenceDependency(
            m.ClaimRef(id=m.ClaimId("c-1")), _ref("ev-a", "a.py"), "fp-a"
        )
        dep_stale = m.EvidenceDependency(
            m.ClaimRef(id=m.ClaimId("c-2")), _ref("ev-b", "b.py"), "fp-old"
        )
        dep_gone = m.EvidenceDependency(
            m.RelationshipRef(id=m.RelationshipId("r-1")),
            _ref("ev-c", "c.py"), "fp-c",
        )
        updates = fresh.classify_all(
            (dep_current, dep_stale, dep_gone),
            {"ev-a": "fp-a", "ev-b": "fp-new"},
        )
        self.assertEqual(len(updates), 2)
        self.assertEqual(
            updates[0].semantic_id, m.ClaimRef(id=m.ClaimId("c-2"))
        )
        self.assertIs(updates[0].freshness.state, m.FreshnessState.STALE)
        self.assertIs(updates[1].freshness.state, m.FreshnessState.UNVERIFIABLE)

    def test_classify_coverage(self):
        recorded = m.CoverageDependency(
            scope_subjects=(_sid(),),
            inventory_fingerprint="inv-1",
            seed_fingerprints=(
                m.SeedFingerprint(
                    m.EvidenceId("ev-a"), "a.py", "fp-a"
                ),
            ),
        )
        current = fresh.classify_coverage(
            recorded, "inv-1", {"ev-a": "fp-a"}
        )
        self.assertIs(current.state, m.FreshnessState.CURRENT)
        stale = fresh.classify_coverage(
            recorded, "inv-2", {"ev-a": "fp-a"}
        )
        self.assertIs(stale.state, m.FreshnessState.STALE)
        unverifiable = fresh.classify_coverage(
            recorded, "inv-1", {}
        )
        self.assertIs(
            unverifiable.state, m.FreshnessState.UNVERIFIABLE
        )


class AnswerHelpersTest(unittest.TestCase):
    def test_requirements_for_claim_states(self):
        base = dict(
            claim_id=m.ClaimId("c-1"), subject=_sid(), kind=m.ClaimKind.PURPOSE,
        assertion_nature=m.AssertionNature.DESCRIPTIVE,
            value=m.PurposeValue("s", ()), evidence=(_ref(),),
            basis=m.SemanticBasis(m.DerivationKind.EXPLICIT_EVIDENCE),
        )
        unresolved = m.SemanticClaim(
            **base, trust=m.TrustState.UNRESOLVED,
            freshness=m.Freshness(m.FreshnessState.CURRENT, reason="t"),
        )
        reqs = ans.requirements_for_claim(unresolved)
        self.assertEqual(len(reqs), 1)
        self.assertIs(reqs[0].kind, m.ResolutionKind.MISSING_AUTHORITY)

        stale = m.SemanticClaim(
            **base, trust=m.TrustState.ESTABLISHED,
            authority=_accepted_binding(),
            freshness=m.Freshness(m.FreshnessState.STALE, reason="t"),
        )
        reqs = ans.requirements_for_claim(stale)
        self.assertIs(reqs[0].kind, m.ResolutionKind.STALE_EVIDENCE)

        established = m.SemanticClaim(
            **base, trust=m.TrustState.ESTABLISHED,
            authority=_accepted_binding(),
            freshness=m.Freshness(m.FreshnessState.CURRENT, reason="t"),
        )
        self.assertEqual(ans.requirements_for_claim(established), ())

    def test_ambiguous_resolution_requirement(self):
        resolution = m.SubjectResolution(
            candidates=(
                m.SubjectCandidate(
                    m.Subject(_sid("a.py"), "A", None), (),
                    m.CandidateRankBasis.EXACT_NAME,
                ),
                m.SubjectCandidate(
                    m.Subject(_sid("b.py"), "A", None), (),
                    m.CandidateRankBasis.EXACT_NAME,
                ),
            ),
            ambiguity=m.ResolutionAmbiguity.AMBIGUOUS,
            bound_info=m.BoundInfo(8, 0, 2, False),
        )
        reqs = ans.requirements_for_resolution(resolution)
        self.assertIs(reqs[0].kind, m.ResolutionKind.AMBIGUOUS_IDENTITY)

    def test_not_found_resolution_requirement_names_root(self):
        resolution = m.SubjectResolution(
            candidates=(),
            ambiguity=m.ResolutionAmbiguity.NOT_FOUND,
            bound_info=m.BoundInfo(8, 0, 0, False),
        )
        reqs = ans.requirements_for_resolution(
            resolution, repository_id="repo-1",
            name_or_locator="other-root/workflows/x.py",
        )
        self.assertEqual(len(reqs), 1)
        self.assertIs(reqs[0].kind, m.ResolutionKind.MISSING_EVIDENCE)
        self.assertIn("repo-1", reqs[0].description)
        self.assertIn("repository's root", reqs[0].description)
        self.assertIn("locate", reqs[0].description)

    def test_not_found_resolution_requirement_without_locator(self):
        resolution = m.SubjectResolution(
            candidates=(),
            ambiguity=m.ResolutionAmbiguity.NOT_FOUND,
            bound_info=m.BoundInfo(8, 0, 0, False),
        )
        reqs = ans.requirements_for_resolution(resolution)
        self.assertEqual(len(reqs), 1)
        self.assertIs(reqs[0].kind, m.ResolutionKind.MISSING_EVIDENCE)

    def test_resolved_resolution_requirement_empty(self):
        resolution = m.SubjectResolution(
            candidates=(),
            ambiguity=m.ResolutionAmbiguity.RESOLVED,
            bound_info=m.BoundInfo(8, 0, 0, False),
        )
        self.assertEqual(ans.requirements_for_resolution(resolution), ())

    def test_truncate_fields_priority_order(self):
        kept, truncated, category, token = ans.truncate_fields(
            ((("q1",), "conflicts"), (("a", "b", "c"), "claims")), 2
        )
        self.assertEqual(kept, (("q1",), ("a",)))
        self.assertTrue(truncated)
        self.assertEqual(category, "claims")
        self.assertEqual(token, "trunc:claims:2")

    def test_truncate_fields_no_truncation_no_token(self):
        kept, truncated, category, token = ans.truncate_fields(
            ((("a",), "claims"),), 5
        )
        self.assertEqual(kept, (("a",),))
        self.assertFalse(truncated)
        self.assertIsNone(category)
        self.assertIsNone(token)


if __name__ == "__main__":
    unittest.main()
