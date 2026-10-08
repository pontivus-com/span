"""Canonical model tests (plan Phase 1.1).

Covers every §4 enum/type: closed-vocabulary closure, construction
validation (stated plan rules only), ClaimKind↔value mapping,
intent↔content correspondence, and canonical serialization round-trips
for all variants — including later-phase variants, which receive their
semantic behavior in their owning later phase.
"""

import datetime
import unittest

from span.core import model as m


def _subject_id(kind=m.SubjectKind.COMPONENT, locator="src/example.py"):
    return m.SubjectId(
        repository_id="repo-1", subject_kind=kind, canonical_locator=locator
    )


def _evidence_ref():
    return m.EvidenceRef(
        evidence_id=m.EvidenceId("ev-1"),
        repository_id="repo-1",
        source_kind=m.EvidenceSourceKind.SOURCE_CODE,
        locator="src/example.py",
        revision_or_fingerprint="abc123",
        section_or_span="L10-L20",
    )


def _authority_binding():
    return m.AuthorityBinding(
        evidence_ref=_evidence_ref(),
        authority_kind=m.AuthorityKind.REPOSITORY_RULE,
        status=m.AuthorityStatus.ACCEPTED,
        applicability=m.AuthorityApplicability(
            subject_scope=(_subject_id(),), description="owns example"
        ),
        declared_precedence=None,
    )


def _repository_state():
    return m.RepositoryState(
        repository_id="repo-1",
        revision_id="rev-1",
        dirty=False,
        state_fingerprint="fp-1",
        observed_at=datetime.datetime(
            2026, 10, 7, 12, 0, 0, tzinfo=datetime.timezone.utc
        ),
    )


def _bound_info():
    return m.BoundInfo(
        requested_max_results=10,
        requested_max_depth=3,
        returned_results=1,
        truncated=False,
    )


def _query_bounds():
    return m.QueryBounds(
        max_results=50,
        max_depth=5,
        max_subjects=20,
        max_evidence_units=20,
        max_evidence_bytes=65536,
        max_candidate_claims=20,
        max_candidate_relationships=20,
    )


def _semantic_claim():
    return m.SemanticClaim(
        claim_id=m.ClaimId("claim-1"),
        subject=_subject_id(),
        kind=m.ClaimKind.PURPOSE,
        value=m.PurposeValue(summary="does X", capability_refs=(_subject_id(),)),
        evidence=(_evidence_ref(),),
        authority=_authority_binding(),
        trust=m.TrustState.ESTABLISHED,
        freshness=m.Freshness(
            state=m.FreshnessState.CURRENT,
            supporting_revision_or_fingerprint="abc123",
            reason="verified against current fingerprint",
        ),
        basis=m.SemanticBasis(
            derivation=m.DerivationKind.EXPLICIT_EVIDENCE,
            summary="stated in README",
            input_refs=(),
        ),
    )


def _semantic_relationship():
    return m.SemanticRelationship(
        relationship_id=m.RelationshipId("rel-1"),
        source=_subject_id(),
        kind=m.RelationshipKind.MEMBER_OF,
        target=_subject_id(m.SubjectKind.CAPABILITY, "cap/payments"),
        evidence=(_evidence_ref(),),
        authority=None,
        trust=m.TrustState.PARTIAL,
        freshness=m.Freshness(state=m.FreshnessState.STALE, reason="dep changed"),
        basis=m.SemanticBasis(derivation=m.DerivationKind.DERIVED_JOIN),
    )


class ClosedVocabularyTest(unittest.TestCase):
    """I-03: core kinds are only those defined in §4."""

    def test_subject_kind_members(self):
        self.assertEqual(
            {e.value for e in m.SubjectKind},
            {
                "REPOSITORY", "SUBSYSTEM", "COMPONENT", "CAPABILITY",
                "CODE_SYMBOL", "CONTRACT", "BOUNDARY", "REPRESENTATION",
                "CONFIGURATION", "DOCUMENT", "TEST_OR_GATE", "SURFACE",
                "FIELD", "EXTERNAL_DEPENDENCY", "OTHER",
            },
        )

    def test_claim_kind_members(self):
        self.assertEqual(
            {e.value for e in m.ClaimKind},
            {
                "PURPOSE", "CAPABILITY_MEMBERSHIP", "RESPONSIBILITY",
                "OWNERSHIP_CUSTODY", "REPRESENTATION_CONTRACT",
                "TRANSFORMATION_OWNERSHIP", "INVARIANT_CONSTRAINT",
                "CONFIGURATION_ENVIRONMENT", "LIFECYCLE_STATE", "VERIFICATION",
            },
        )

    def test_relationship_kind_members(self):
        self.assertEqual(
            {e.value for e in m.RelationshipKind},
            {
                "MEMBER_OF", "IMPLEMENTS", "PRODUCES", "CARRIES", "CONSUMES",
                "DEPENDS_ON", "CROSSES_BOUNDARY", "REPRESENTS_AS",
                "TRANSFORMS_TO", "GOVERNED_BY", "CONFIGURED_BY", "PERSISTS_AT",
                "TRANSITIONS_TO", "VERIFIED_BY", "SUPERSEDES",
            },
        )

    def test_evidence_authority_enums(self):
        self.assertEqual(len(m.EvidenceSourceKind), 9)
        self.assertEqual(len(m.AuthorityKind), 10)
        self.assertEqual(
            {e.value for e in m.AuthorityStatus},
            {"ACCEPTED", "DRAFT", "SUPERSEDED", "DECLARED", "UNKNOWN"},
        )
        self.assertEqual(
            {e.value for e in m.PrecedenceKind}, {"PRIORITY_RANK", "OVERRIDES"}
        )

    def test_trust_freshness_intent_enums(self):
        self.assertEqual(
            {e.value for e in m.TrustState},
            {"ESTABLISHED", "PARTIAL", "AMBIGUOUS", "CONFLICTED", "UNRESOLVED"},
        )
        self.assertEqual(
            {e.value for e in m.FreshnessState},
            {"CURRENT", "STALE", "UNVERIFIABLE"},
        )
        self.assertEqual(
            {e.value for e in m.SemanticIntent},
            {"EXPLAIN", "TRACE", "IMPACT", "AUTHORITY", "STATUS"},
        )

    def test_change_and_resolution_enums(self):
        self.assertEqual(len(m.ChangeCondition), 9)
        self.assertEqual(
            {e.value for e in m.ImpactEstablishment},
            {
                "STRUCTURAL_POSSIBILITY",
                "SEMANTICALLY_ESTABLISHED",
                "PARTIAL_OR_UNRESOLVED",
            },
        )
        self.assertEqual(len(m.ResolutionKind), 9)
        self.assertEqual(
            {e.value for e in m.DerivationKind},
            {
                "EXPLICIT_EVIDENCE", "SEMANTIC_INTERPRETATION",
                "STRUCTURAL_OBSERVATION", "DERIVED_JOIN",
            },
        )

    def test_remaining_enums(self):
        self.assertEqual(len(m.OwnershipRole), 5)
        self.assertEqual(len(m.OwnershipExclusivity), 3)
        self.assertEqual(len(m.VerificationKind), 4)
        self.assertEqual(len(m.VerificationCurrency), 5)
        self.assertEqual(len(m.RepositoryReadiness), 5)
        self.assertEqual(
            {e.value for e in m.StatusMode}, {"NORMAL", "HOOK_FAST"}
        )
        self.assertEqual(len(m.StructuralEdgeKind), 5)
        self.assertEqual(len(m.LifecyclePhase), 12)
        self.assertEqual(len(m.CandidateRankBasis), 5)
        self.assertEqual(
            {e.value for e in m.ResolutionAmbiguity},
            {"RESOLVED", "AMBIGUOUS", "NOT_FOUND"},
        )
        self.assertEqual(
            {e.value for e in m.RepresentationDirection},
            {"SOURCE", "DESTINATION", "BIDIRECTIONAL", "NOT_APPLICABLE"},
        )


class ConstructionValidationTest(unittest.TestCase):
    def test_nominal_ids_reject_empty(self):
        for cls in (m.ClaimId, m.RelationshipId, m.AnswerId, m.EvidenceId):
            with self.assertRaises(ValueError, msg=cls.__name__):
                cls("")

    def test_subject_id_rejects_empty_components(self):
        with self.assertRaises(ValueError):
            m.SubjectId("", m.SubjectKind.COMPONENT, "x.py")
        with self.assertRaises(ValueError):
            m.SubjectId("repo-1", m.SubjectKind.COMPONENT, "")

    def test_subject_other_requires_declared_kind(self):
        sid = _subject_id(m.SubjectKind.OTHER, "custom/thing")
        with self.assertRaises(ValueError):
            m.Subject(sid, "Thing", None)
        with self.assertRaises(ValueError):
            m.Subject(sid, "Thing", "")
        ok = m.Subject(sid, "Thing", "widget")
        self.assertEqual(ok.declared_kind, "widget")

    def test_precedence_priority_rank_rules(self):
        with self.assertRaises(ValueError):
            m.DeclaredPrecedence(m.PrecedenceKind.PRIORITY_RANK)
        with self.assertRaises(ValueError):
            m.DeclaredPrecedence(
                m.PrecedenceKind.PRIORITY_RANK,
                priority_rank=0,
                precedence_scheme="s",
            )
        with self.assertRaises(ValueError):
            m.DeclaredPrecedence(
                m.PrecedenceKind.PRIORITY_RANK,
                priority_rank=1,
                precedence_scheme="s",
                overrides=(_evidence_ref(),),
            )
        with self.assertRaises(ValueError):
            m.DeclaredPrecedence(
                m.PrecedenceKind.PRIORITY_RANK, priority_rank=1
            )
        ok = m.DeclaredPrecedence(
            m.PrecedenceKind.PRIORITY_RANK,
            priority_rank=1,
            precedence_scheme="adr-order",
        )
        self.assertEqual(ok.priority_rank, 1)

    def test_precedence_overrides_rules(self):
        with self.assertRaises(ValueError):
            m.DeclaredPrecedence(m.PrecedenceKind.OVERRIDES)
        with self.assertRaises(ValueError):
            m.DeclaredPrecedence(
                m.PrecedenceKind.OVERRIDES,
                overrides=(_evidence_ref(),),
                priority_rank=1,
            )
        ok = m.DeclaredPrecedence(
            m.PrecedenceKind.OVERRIDES, overrides=(_evidence_ref(),)
        )
        self.assertEqual(len(ok.overrides), 1)

    def test_query_bounds_positivity(self):
        good = _query_bounds()
        self.assertEqual(good.max_depth, 5)
        bad = dict(
            max_results=50, max_depth=5, max_subjects=20, max_evidence_units=20,
            max_evidence_bytes=65536, max_candidate_claims=20,
            max_candidate_relationships=20,
        )
        for key in (
            "max_results", "max_subjects", "max_evidence_units",
            "max_evidence_bytes", "max_candidate_claims",
            "max_candidate_relationships",
        ):
            with self.assertRaises(ValueError, msg=key):
                m.QueryBounds(**{**bad, key: 0})
        with self.assertRaises(ValueError):
            m.QueryBounds(**{**bad, "max_depth": -1})
        # Booleans are not ints for bound purposes.
        with self.assertRaises(ValueError):
            m.QueryBounds(**{**bad, "max_results": True})

    def test_repository_state_rejects_naive_datetime(self):
        with self.assertRaises(ValueError):
            m.RepositoryState(
                repository_id="repo-1", revision_id=None, dirty=False,
                state_fingerprint="fp",
                observed_at=datetime.datetime(2026, 10, 7, 12, 0, 0),
            )

    def test_unsupported_page_requires_empty_items(self):
        edge = m.StructuralEdge(
            source=_subject_id(), kind=m.StructuralEdgeKind.CALLS,
            target=_subject_id(), evidence=_evidence_ref(),
        )
        with self.assertRaises(ValueError):
            m.StructuralEdgePage(
                items=(edge,), repository_state=_repository_state(),
                bound_info=_bound_info(), unsupported=True,
            )


class ClaimValueMappingTest(unittest.TestCase):
    """§4.4: every ClaimKind maps to exactly one typed value carrier."""

    def test_mapping_is_total_over_claim_kinds(self):
        self.assertEqual(set(m.CLAIM_VALUE_TYPE), set(m.ClaimKind))

    def test_all_ten_mappings_accepted(self):
        sid = _subject_id()
        values = {
            m.ClaimKind.PURPOSE: m.PurposeValue("s", (sid,)),
            m.ClaimKind.CAPABILITY_MEMBERSHIP: m.CapabilityMembershipValue(sid),
            m.ClaimKind.RESPONSIBILITY: m.ResponsibilityValue("r"),
            m.ClaimKind.OWNERSHIP_CUSTODY: m.OwnershipCustodyValue(
                sid, m.OwnershipRole.OWNER, m.OwnershipExclusivity.EXCLUSIVE
            ),
            m.ClaimKind.REPRESENTATION_CONTRACT:
                m.RepresentationContractValue("rep"),
            m.ClaimKind.TRANSFORMATION_OWNERSHIP:
                m.TransformationOwnershipValue(sid),
            m.ClaimKind.INVARIANT_CONSTRAINT: m.InvariantConstraintValue("inv"),
            m.ClaimKind.CONFIGURATION_ENVIRONMENT:
                m.ConfigurationEnvironmentValue("concern"),
            m.ClaimKind.LIFECYCLE_STATE:
                m.LifecycleStateValue(m.LifecyclePhase.USE),
            m.ClaimKind.VERIFICATION: m.VerificationValue(
                sid, m.VerificationKind.TEST, m.VerificationCurrency.CANDIDATE
            ),
        }
        for n, (kind, value) in enumerate(values.items()):
            claim = m.SemanticClaim(
                m.ClaimId(f"c-{n}"), sid, kind, value,
                basis=m.SemanticBasis(m.DerivationKind.EXPLICIT_EVIDENCE),
            )
            self.assertIs(claim.kind, kind)

    def test_mismatched_value_rejected(self):
        with self.assertRaises(ValueError):
            m.SemanticClaim(
                m.ClaimId("c-x"), _subject_id(), m.ClaimKind.PURPOSE,
                m.ResponsibilityValue("r"),
                basis=m.SemanticBasis(m.DerivationKind.EXPLICIT_EVIDENCE),
            )
        with self.assertRaises(ValueError):
            m.CandidateSemanticClaim(
                subject=_subject_id(), kind=m.ClaimKind.VERIFICATION,
                value=m.PurposeValue("s", ()),
            )


class AnswerCorrespondenceTest(unittest.TestCase):
    def test_intent_content_mapping_is_total(self):
        self.assertEqual(set(m.INTENT_CONTENT_TYPE), set(m.SemanticIntent))

    def test_each_intent_accepts_its_content(self):
        pairs = [
            (m.SemanticIntent.EXPLAIN, m.ExplainContent()),
            (m.SemanticIntent.TRACE, m.TraceContent()),
            (m.SemanticIntent.IMPACT, m.ImpactContent()),
            (m.SemanticIntent.AUTHORITY, m.AuthorityContent()),
            (m.SemanticIntent.STATUS, m.StatusContent()),
        ]
        for n, (intent, content) in enumerate(pairs):
            answer = m.SemanticAnswer(
                m.AnswerId(f"a-{n}"), intent, _repository_state(), None,
                content,
            )
            self.assertIs(answer.intent, intent)

    def test_mismatched_content_rejected(self):
        with self.assertRaises(ValueError):
            m.SemanticAnswer(
                m.AnswerId("a-x"), m.SemanticIntent.EXPLAIN,
                _repository_state(), None, m.TraceContent(),
            )


class SerializationRoundTripTest(unittest.TestCase):
    """Canonical serialization is exact and lossless for every carrier."""

    def _round_trip(self, cls, value):
        data = m.to_canonical(value)
        back = m.from_canonical(cls, data)
        self.assertEqual(back, value)
        # Canonical form is JSON-compatible plain data.
        import json

        json.dumps(data)
        return data

    def test_subject_and_selector(self):
        subject = m.Subject(_subject_id(), "Example", None)
        self._round_trip(m.Subject, subject)
        selector = m.SubjectSelector(
            _subject_id(), "example", (m.SubjectKind.COMPONENT,), "src/"
        )
        self._round_trip(m.SubjectSelector, selector)
        resolution = m.SubjectResolution(
            (
                m.SubjectCandidate(
                    subject, (_evidence_ref(),),
                    m.CandidateRankBasis.EXACT_LOCATOR,
                ),
            ),
            m.ResolutionAmbiguity.RESOLVED,
            _bound_info(),
        )
        self._round_trip(m.SubjectResolution, resolution)

    def test_claim_and_relationship(self):
        self._round_trip(m.SemanticClaim, _semantic_claim())
        self._round_trip(m.SemanticRelationship, _semantic_relationship())
        conflict = m.SemanticConflict(
            m.ClaimRef(id=m.ClaimId("c-1")),
            m.RelationshipRef(id=m.RelationshipId("r-1")),
        )
        self._round_trip(m.SemanticConflict, conflict)

    def test_authority_and_freshness(self):
        self._round_trip(m.AuthorityBinding, _authority_binding())
        self._round_trip(
            m.Freshness,
            m.Freshness(m.FreshnessState.CURRENT, "rev-9", "verified"),
        )

    def test_readiness_and_hook_notice(self):
        notice = m.HookStatusNotice(
            m.RepositoryReadiness.READY, 2, 1, 0, (_subject_id(),), None
        )
        self._round_trip(m.HookStatusNotice, notice)

    def test_resolution_change_impact(self):
        req = m.ResolutionRequirement(
            m.ResolutionKind.MISSING_AUTHORITY, _subject_id(), "no binding",
            (m.ClaimRef(id=m.ClaimId("c-1")),),
        )
        self._round_trip(m.ResolutionRequirement, req)
        item = m.ImpactItem(
            _subject_id(), m.ImpactEstablishment.SEMANTICALLY_ESTABLISHED,
            m.SemanticBasis(m.DerivationKind.DERIVED_JOIN),
            (_evidence_ref(),), (m.ClaimRef(id=m.ClaimId("c-1")),), (),
        )
        self._round_trip(m.ImpactItem, item)
        kind = m.ChangeKind.OWNERSHIP
        self._round_trip(
            m.ProposedChange,
            m.ProposedChange(kind, "handoff", (m.ClaimRef(id=m.ClaimId("c-1")),)),
        )

    def test_answer_envelope(self):
        answer = m.SemanticAnswer(
            m.AnswerId("a-1"), m.SemanticIntent.EXPLAIN,
            _repository_state(), None,
            m.ExplainContent(
                (_semantic_claim(),), (_semantic_relationship(),), (), (),
            ),
            resolution_requirements=(),
        )
        self._round_trip(m.SemanticAnswer, answer)

    def test_supporting_contracts(self):
        self._round_trip(m.RepositoryState, _repository_state())
        unit = m.EvidenceUnit(_evidence_ref(), "content", "fp")
        self._round_trip(m.EvidenceUnit, unit)
        obs = m.StructuralObservation(
            _subject_id(), m.StructuralEdgeKind.CALLS, _subject_id(),
            _evidence_ref(), _repository_state(),
        )
        self._round_trip(m.StructuralObservation, obs)
        edge = m.StructuralEdge(
            _subject_id(), m.StructuralEdgeKind.IMPORTS, _subject_id(),
            _evidence_ref(),
        )
        self._round_trip(m.StructuralEdge, edge)
        loc = m.StructuralLocation(_subject_id(), _evidence_ref())
        self._round_trip(m.StructuralLocation, loc)
        node = m.StructuralReachNode(_subject_id(), 2, edge)
        self._round_trip(m.StructuralReachNode, node)
        self._round_trip(m.BoundInfo, _bound_info())
        self._round_trip(
            m.EvidenceScope, m.EvidenceScope(("src/",), (_evidence_ref(),))
        )
        page = m.StructuralEdgePage((edge,), _repository_state(), _bound_info())
        self._round_trip(m.StructuralEdgePage, page)
        inv = m.EvidenceInventoryPage(
            (m.EvidenceInventoryItem(_evidence_ref(), "fp"),),
            _repository_state(), _bound_info(),
        )
        self._round_trip(m.EvidenceInventoryPage, inv)
        sel = m.EvidenceSelection((_evidence_ref(),), _bound_info())
        self._round_trip(m.EvidenceSelection, sel)

    def test_interpretation_contracts(self):
        req = m.SemanticInterpretationRequest(
            repository_id="repo-1",
            subjects=(m.Subject(_subject_id(), "E", None),),
            evidence_units=(m.EvidenceUnit(_evidence_ref(), "c", "fp"),),
            structural_observations=(),
            allowed_claim_kinds=(m.ClaimKind.PURPOSE,),
            allowed_relationship_kinds=(m.RelationshipKind.MEMBER_OF,),
            identity_bindings=(_subject_id(),),
            operation_intent=m.SemanticIntent.EXPLAIN,
            question_slice="src/a.py",
            proposed_change=None,
            bounds=_query_bounds(),
        )
        self._round_trip(m.SemanticInterpretationRequest, req)
        res = m.SemanticInterpretationResult(
            (
                m.CandidateSemanticClaim(
                    subject=_subject_id(), kind=m.ClaimKind.PURPOSE,
                    value=m.PurposeValue("s", ()),
                ),
            ),
            (),
            (_evidence_ref(),),
            ("diag",),
        )
        self._round_trip(m.SemanticInterpretationResult, res)
        self._round_trip(
            m.RecordedConflict,
            m.RecordedConflict(
                _subject_id(),
                m.ClaimRef(id=m.ClaimId("c-1")),
                m.ClaimRef(id=m.ClaimId("c-2")),
            ),
        )

    def test_store_and_index_contracts(self):
        batch = m.CanonicalIndexBatch(
            (m.Subject(_subject_id(), "E", None),),
            (_semantic_claim(),),
            (_semantic_relationship(),),
            (
                m.EvidenceDependency(
                    m.ClaimRef(id=m.ClaimId("c-1")), _evidence_ref(), "fp-obs"
                ),
            ),
        )
        self._round_trip(m.CanonicalIndexBatch, batch)
        self._round_trip(
            m.CoverageDependency,
            m.CoverageDependency(
                scope_subjects=(_subject_id(),),
                inventory_fingerprint="inv-9",
                seed_fingerprints=(
                    m.SeedFingerprint(
                        m.EvidenceId("ev-x"), "x.md", "fp-x"
                    ),
                ),
            ),
        )
        self._round_trip(
            m.FreshnessUpdate,
            m.FreshnessUpdate(
                m.RelationshipRef(id=m.RelationshipId("r-1")),
                m.Freshness(m.FreshnessState.STALE, reason="dep changed"),
            ),
        )
        self._round_trip(m.StoreWriteResult, m.StoreWriteResult(3))
        self._round_trip(m.SchemaVersion, m.SchemaVersion(1))
        self._round_trip(m.ClaimPage, m.ClaimPage((_semantic_claim(),), _bound_info()))
        policy = m.ServiceBoundsPolicy(
            _query_bounds(), _query_bounds(), _query_bounds()
        )
        self._round_trip(m.ServiceBoundsPolicy, policy)

    def test_decode_rejects_unknown_tags_and_values(self):
        with self.assertRaises(m.CanonicalDecodeError):
            m.from_canonical(
                m.SemanticContent, {"$type": "Nope", "claims": []}
            )
        with self.assertRaises(m.CanonicalDecodeError):
            m.from_canonical(m.TrustState, "BOGUS")
        with self.assertRaises(m.CanonicalDecodeError):
            m.from_canonical(m.QueryBounds, {"$type": "QueryBounds"})
        with self.assertRaises(m.CanonicalDecodeError):
            m.from_canonical(
                m.FreshnessState, {"$type": "FreshnessState"}
            )

    def test_decode_rejects_unknown_fields(self):
        data = m.to_canonical(_subject_id())
        data["bogus"] = 1
        with self.assertRaises(m.CanonicalDecodeError):
            m.from_canonical(m.SubjectId, data)


class CorePurityTest(unittest.TestCase):
    def test_core_imports_values_only(self):
        import ast
        import pathlib
        import sys

        allowed_roots = set(sys.stdlib_module_names)
        core = (
            pathlib.Path(__file__).resolve().parents[2]
            / "src" / "span" / "core"
        )
        offenders = []
        for path in sorted(core.glob("*.py")):
            tree = ast.parse(
                path.read_text(encoding="utf-8"), str(path)
            )
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        root = alias.name.split(".")[0]
                        if root not in allowed_roots:
                            offenders.append(f"{path.name}:{root}")
                elif isinstance(node, ast.ImportFrom):
                    if node.level != 0:
                        offenders.append(f"{path.name}:relative")
                        continue
                    root = (node.module or "").split(".")[0]
                    if root == "span":
                        if not (node.module or "").startswith(
                            "span.core"
                        ):
                            offenders.append(
                                f"{path.name}:{node.module}"
                            )
                    elif root not in allowed_roots:
                        offenders.append(f"{path.name}:{root}")
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
