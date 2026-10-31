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
        assertion_nature=m.AssertionNature.DESCRIPTIVE,
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
        assertion_nature=m.AssertionNature.DESCRIPTIVE,
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
                "REPOSITORY",
                "SUBSYSTEM",
                "COMPONENT",
                "CAPABILITY",
                "CODE_SYMBOL",
                "CONTRACT",
                "BOUNDARY",
                "REPRESENTATION",
                "CONFIGURATION",
                "DOCUMENT",
                "TEST_OR_GATE",
                "SURFACE",
                "FIELD",
                "EXTERNAL_DEPENDENCY",
                "OTHER",
            },
        )

    def test_claim_kind_members(self):
        self.assertEqual(
            {e.value for e in m.ClaimKind},
            {
                "PURPOSE",
                "CAPABILITY_MEMBERSHIP",
                "RESPONSIBILITY",
                "OWNERSHIP_CUSTODY",
                "REPRESENTATION_CONTRACT",
                "TRANSFORMATION_OWNERSHIP",
                "INVARIANT_CONSTRAINT",
                "CONFIGURATION_ENVIRONMENT",
                "LIFECYCLE_STATE",
                "VERIFICATION",
            },
        )

    def test_relationship_kind_members(self):
        self.assertEqual(
            {e.value for e in m.RelationshipKind},
            {
                "MEMBER_OF",
                "IMPLEMENTS",
                "PRODUCES",
                "CARRIES",
                "CONSUMES",
                "DEPENDS_ON",
                "CROSSES_BOUNDARY",
                "REPRESENTS_AS",
                "TRANSFORMS_TO",
                "GOVERNED_BY",
                "CONFIGURED_BY",
                "PERSISTS_AT",
                "TRANSITIONS_TO",
                "VERIFIED_BY",
                "SUPERSEDES",
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

    def test_remaining_enums(self):
        self.assertEqual(len(m.OwnershipRole), 5)
        self.assertEqual(len(m.OwnershipExclusivity), 3)
        self.assertEqual(len(m.VerificationKind), 4)
        self.assertEqual(
            {member.value for member in m.AttestedCurrency},
            {"CANDIDATE", "UNKNOWN"},
        )
        self.assertEqual(
            {member.value for member in m.DerivedCurrency},
            {"CURRENT_PASS", "CURRENT_FAIL", "STALE", "UNKNOWN"},
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
            m.DeclaredPrecedence(m.PrecedenceKind.PRIORITY_RANK, priority_rank=1)
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
            max_results=50,
            max_depth=5,
            max_subjects=20,
            max_evidence_units=20,
            max_evidence_bytes=65536,
            max_candidate_claims=20,
            max_candidate_relationships=20,
        )
        for key in (
            "max_results",
            "max_subjects",
            "max_evidence_units",
            "max_evidence_bytes",
            "max_candidate_claims",
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
                repository_id="repo-1",
                revision_id=None,
                dirty=False,
                state_fingerprint="fp",
                observed_at=datetime.datetime(2026, 10, 7, 12, 0, 0),
            )

    def test_unsupported_page_requires_empty_items(self):
        edge = m.StructuralEdge(
            source=_subject_id(),
            kind=m.StructuralEdgeKind.CALLS,
            target=_subject_id(),
            evidence=_evidence_ref(),
        )
        with self.assertRaises(ValueError):
            m.StructuralResult(
                items=(edge,),
                repository_state=_repository_state(),
                bound_info=_bound_info(),
                unsupported=True,
            )

    def test_coverage_detail_accepts_closed_tokens_in_order(self):
        report = m.StructuralFreshnessReport(
            stale_files=("a.py",),
            unverifiable_files=(),
            coverage=m.ScopeCoverage.UNVERIFIED,
            coverage_detail="dirty-tree+touched-file-mismatch",
        )
        self.assertEqual(report.coverage_detail, "dirty-tree+touched-file-mismatch")
        clean = m.StructuralFreshnessReport(
            coverage=m.ScopeCoverage.VERIFIED,
            coverage_detail="clean-verified",
        )
        self.assertEqual(clean.coverage_detail, "clean-verified")

    def test_coverage_detail_rejects_bad_shapes(self):
        for bad in (
            "",
            "clean-verified+dirty-tree",
            "dirty-tree+dirty-tree",
            "bogus-token",
            "dirty-tree +touched-file-mismatch",
            "unverifiable-file+dirty-tree",
            " dirty-tree",
        ):
            with self.assertRaises(ValueError, msg=bad):
                m.StructuralFreshnessReport(
                    coverage=m.ScopeCoverage.UNVERIFIED,
                    coverage_detail=bad,
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
                    subject,
                    (_evidence_ref(),),
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

    def test_decode_rejects_unknown_tags_and_values(self):
        with self.assertRaises(m.CanonicalDecodeError):
            m.from_canonical(m.UnderstandQuestionResult, {"$type": "Nope"})
        with self.assertRaises(m.CanonicalDecodeError):
            m.from_canonical(m.TrustState, "BOGUS")
        with self.assertRaises(m.CanonicalDecodeError):
            m.from_canonical(m.QueryBounds, {"$type": "QueryBounds"})
        with self.assertRaises(m.CanonicalDecodeError):
            m.from_canonical(m.FreshnessState, {"$type": "FreshnessState"})

    def test_decode_rejects_unknown_fields(self):
        data = m.to_canonical(_subject_id())
        data["bogus"] = 1
        with self.assertRaises(m.CanonicalDecodeError):
            m.from_canonical(m.SubjectId, data)

    def test_decode_error_carries_dotted_field_path(self):
        data = m.to_canonical(_subject_id())
        data["repository_id"] = 42
        try:
            m.from_canonical(m.SubjectId, data)
        except m.CanonicalDecodeError as exc:
            self.assertIn("repository_id", str(exc))
        else:
            self.fail("expected CanonicalDecodeError")
        bad = m.to_canonical(_query_bounds())
        bad["max_results"] = "many"
        try:
            m.from_canonical(m.QueryBounds, bad)
        except m.CanonicalDecodeError as exc:
            self.assertIn("max_results", str(exc))
        else:
            self.fail("expected CanonicalDecodeError")


class IngressFaultAggregationTest(unittest.TestCase):
    """Ingress reports every shape fault it finds, not only the first.

    Serial discovery (fix one field, get rejected for the next) made one
    malformed call cost several round trips; each pass now reports all
    sibling faults together while a single fault keeps its exact text.
    """

    def test_sibling_missing_fields_reported_together(self):
        try:
            m.from_canonical(m.SubjectId, {"$type": "SubjectId"})
        except m.CanonicalDecodeError as exc:
            text = str(exc)
        else:
            self.fail("expected CanonicalDecodeError")
        self.assertIn("missing field 'repository_id'", text)
        self.assertIn("missing field 'subject_kind'", text)

    def test_single_fault_text_is_unchanged(self):
        try:
            m.from_canonical(
                m.EvidenceLineRange,
                {
                    "$type": "EvidenceLineRange",
                    "start_line": 1,
                    "end_line": 2,
                },
            )
        except m.CanonicalDecodeError as exc:
            self.assertEqual(
                str(exc),
                "missing field 'total_lines' for EvidenceLineRange",
            )
        else:
            self.fail("expected CanonicalDecodeError")


class CorePurityTest(unittest.TestCase):
    def test_core_imports_values_only(self):
        import ast
        import pathlib
        import sys

        allowed_roots = set(sys.stdlib_module_names)
        core = pathlib.Path(__file__).resolve().parents[2] / "src" / "span" / "core"
        offenders = []
        for path in sorted(core.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
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
                        if not (node.module or "").startswith("span.core"):
                            offenders.append(f"{path.name}:{node.module}")
                    elif root not in allowed_roots:
                        offenders.append(f"{path.name}:{root}")
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
