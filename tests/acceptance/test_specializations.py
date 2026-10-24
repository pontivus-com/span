"""S-01/S-02 acceptance subcases (plan §12, Phase 3.6).

S-01 terminology/register authority and S-02 publication/disposition
custody are specializations of existing factors — no repository-specific
glossary schema, no proprietary proof-tier vocabulary, no new ontology
or operations. Both run through the standard explain/authority/status
surface with the deterministic test agent.
"""

import unittest

from span.core import model as m
from span.ports.interpretation import PendingInterpretation
from span.ports.structural import StructuralDirection
from span.service import DEFAULT_SERVICE_BOUNDS_POLICY
from span import service as ops
from span.shell.agent_exchange.continuations import ContinuationStore
from span.shell.agent_exchange.fixture import FixtureAgent, FixtureCandidates
from span.shell.evidence import FixtureEvidenceSource
from span.shell.sqlite_store import SqliteSemanticStore
from span.shell.structural.memory import (
    InMemoryEdge,
    InMemoryFile,
    InMemoryStructuralSource,
    InMemorySubject,
    fingerprint_content,
)

REPO = "spec-svc"

FILES = {
    "docs/terminology.md": (
        "# Terminology\n\nCanonical wire unit is cents. " "Display shows dollars.\n"
    ),
    "src/money.py": "# display surface rendering\nDOLLARS = True\n",
    "RELEASE.md": ("# Release 1.0\n\nTerminal. Downstream use is copy-only.\n"),
    "src/publish.py": "# release-1.0 publisher\nRELEASED = True\n",
}

SUBJECTS = (
    InMemorySubject("cap/amount", m.SubjectKind.CAPABILITY, "amount"),
    InMemorySubject("rep/wire", m.SubjectKind.REPRESENTATION, "wire"),
    InMemorySubject("rep/display", m.SubjectKind.REPRESENTATION, "display"),
    InMemorySubject("docs/terminology", m.SubjectKind.DOCUMENT, "terminology"),
    InMemorySubject("src/money.py", m.SubjectKind.COMPONENT, "money"),
    InMemorySubject("contract/release-1.0", m.SubjectKind.CONTRACT, "release"),
    InMemorySubject("src/publish.py", m.SubjectKind.COMPONENT, "publish"),
)

EDGES = (InMemoryEdge("src/money.py", m.StructuralEdgeKind.DEFINES, "rep/display"),)


def _sid(locator, kind=m.SubjectKind.COMPONENT):
    return m.SubjectId(repository_id=REPO, subject_kind=kind, canonical_locator=locator)


def _ref(path):
    return m.EvidenceRef(
        evidence_id=m.EvidenceId(f"ev-{path}"),
        repository_id=REPO,
        source_kind=(
            m.EvidenceSourceKind.DOCUMENTATION
            if path.endswith(".md")
            else m.EvidenceSourceKind.SOURCE_CODE
        ),
        locator=path,
        revision_or_fingerprint=fingerprint_content(FILES[path]),
    )


def _term_binding(status):
    term_ref = _ref("docs/terminology.md")
    return m.CandidateAuthority(
        binding=m.AuthorityBinding(
            evidence_ref=term_ref,
            authority_kind=m.AuthorityKind.TERMINOLOGY,
            status=status,
            applicability=m.AuthorityApplicability(
                subject_scope=(), description="canonical units register"
            ),
            declared_precedence=m.DeclaredPrecedence(
                kind=m.PrecedenceKind.OVERRIDES, overrides=(term_ref,)
            ),
        ),
        support=m.AuthoritySupport(
            quoted_span="Canonical wire unit is cents",
            status_section="docs/terminology.md",
            applicability_section="docs/terminology.md",
        ),
    )


def _release_authority():
    return m.CandidateAuthority(
        binding=m.AuthorityBinding(
            evidence_ref=_ref("RELEASE.md"),
            authority_kind=m.AuthorityKind.CONTRACT_SPECIFICATION,
            status=m.AuthorityStatus.ACCEPTED,
        ),
        support=m.AuthoritySupport(
            quoted_span="Terminal",
            status_section="RELEASE.md",
            applicability_section=None,
        ),
    )


def _candidates():
    interp = m.DerivationKind.SEMANTIC_INTERPRETATION
    wire = _sid("rep/wire", m.SubjectKind.REPRESENTATION)
    display = _sid("rep/display", m.SubjectKind.REPRESENTATION)
    release = _sid("contract/release-1.0", m.SubjectKind.CONTRACT)
    term_ref = _ref("docs/terminology.md")
    accepted_term = _term_binding(m.AuthorityStatus.ACCEPTED)
    return {
        # S-01: concept + two surfaces + terminology authority.
        "cap/amount": FixtureCandidates(
            claims=(
                m.CandidateSemanticClaim(
                    subject=_sid("cap/amount", m.SubjectKind.CAPABILITY),
                    kind=m.ClaimKind.PURPOSE,
                    assertion_nature=m.AssertionNature.DESCRIPTIVE,
                    value=m.PurposeValue("canonical money concept", ()),
                    evidence=(term_ref,),
                    candidate_authority=accepted_term,
                    basis=m.SemanticBasis(
                        interp,
                        "terminology governs the money concept",
                    ),
                ),
            ),
            relationships=(),
        ),
        "rep/wire": FixtureCandidates(
            claims=(
                m.CandidateSemanticClaim(
                    subject=wire,
                    kind=m.ClaimKind.REPRESENTATION_CONTRACT,
                    assertion_nature=m.AssertionNature.DESCRIPTIVE,
                    value=m.RepresentationContractValue(
                        "wire-cents",
                        None,
                        m.RepresentationDirection.SOURCE,
                    ),
                    evidence=(term_ref,),
                    candidate_authority=accepted_term,
                    basis=m.SemanticBasis(
                        interp,
                        "terminology governs the wire representation",
                    ),
                ),
            ),
            relationships=(
                m.CandidateSemanticRelationship(
                    source=wire,
                    kind=m.RelationshipKind.TRANSFORMS_TO,
                    assertion_nature=m.AssertionNature.DESCRIPTIVE,
                    target=display,
                    evidence=(term_ref,),
                    basis=m.SemanticBasis(
                        interp,
                        "terminology shows the wire-to-display transform",
                    ),
                ),
            ),
        ),
        "rep/display": FixtureCandidates(
            claims=(
                m.CandidateSemanticClaim(
                    candidate_key="display-governed",
                    subject=display,
                    kind=m.ClaimKind.REPRESENTATION_CONTRACT,
                    assertion_nature=m.AssertionNature.DESCRIPTIVE,
                    value=m.RepresentationContractValue(
                        "display-dollars",
                        None,
                        m.RepresentationDirection.DESTINATION,
                    ),
                    evidence=(term_ref,),
                    candidate_authority=accepted_term,
                    basis=m.SemanticBasis(
                        interp,
                        "terminology governs the display representation",
                    ),
                ),
                # Conflicting implementation representation: no authority.
                m.CandidateSemanticClaim(
                    candidate_key="display-observed",
                    subject=display,
                    kind=m.ClaimKind.REPRESENTATION_CONTRACT,
                    assertion_nature=m.AssertionNature.DESCRIPTIVE,
                    value=m.RepresentationContractValue(
                        "raw-dollars",
                        None,
                        m.RepresentationDirection.DESTINATION,
                    ),
                    evidence=(_ref("src/money.py"),),
                    basis=m.SemanticBasis(
                        interp,
                        "money source shows the observed representation",
                    ),
                ),
            ),
            relationships=(),
            conflicts=(
                m.CandidateSemanticConflict(
                    left_key="display-governed",
                    right_key="display-observed",
                    basis=m.SemanticBasis(
                        interp,
                        "implementation contradicts the governed register",
                    ),
                ),
            ),
        ),
        # S-02: closed publication contract + terminal lifecycle.
        "contract/release-1.0": FixtureCandidates(
            claims=(
                m.CandidateSemanticClaim(
                    subject=release,
                    kind=m.ClaimKind.PURPOSE,
                    assertion_nature=m.AssertionNature.DESCRIPTIVE,
                    value=m.PurposeValue("release 1.0 contract", ()),
                    evidence=(_ref("RELEASE.md"),),
                    candidate_authority=_release_authority(),
                    basis=m.SemanticBasis(
                        interp,
                        "release record states the contract purpose",
                    ),
                ),
                m.CandidateSemanticClaim(
                    subject=release,
                    kind=m.ClaimKind.LIFECYCLE_STATE,
                    assertion_nature=m.AssertionNature.DESCRIPTIVE,
                    value=m.LifecycleStateValue(m.LifecyclePhase.TERMINAL, "published"),
                    evidence=(_ref("RELEASE.md"),),
                    candidate_authority=_release_authority(),
                    basis=m.SemanticBasis(
                        interp,
                        "release record shows terminal publication",
                    ),
                ),
                m.CandidateSemanticClaim(
                    subject=release,
                    kind=m.ClaimKind.VERIFICATION,
                    assertion_nature=m.AssertionNature.DESCRIPTIVE,
                    value=m.VerificationValue(
                        _sid("src/publish.py"),
                        m.VerificationKind.TEST,
                        m.VerificationCurrency.CANDIDATE,
                    ),
                    evidence=(_ref("src/publish.py"),),
                    basis=m.SemanticBasis(
                        interp,
                        "publisher is a verification candidate",
                    ),
                ),
                m.CandidateSemanticClaim(
                    subject=release,
                    kind=m.ClaimKind.VERIFICATION,
                    assertion_nature=m.AssertionNature.DESCRIPTIVE,
                    value=m.VerificationValue(
                        _sid("src/publish.py"),
                        m.VerificationKind.GATE,
                        m.VerificationCurrency.CURRENT_PASS,
                        observed_revision="fp-1",
                    ),
                    evidence=(_ref("src/publish.py"), _ref("RELEASE.md")),
                    candidate_authority=_release_authority(),
                    basis=m.SemanticBasis(
                        interp,
                        "release gate passed at the observed revision",
                    ),
                ),
                m.CandidateSemanticClaim(
                    subject=release,
                    kind=m.ClaimKind.OWNERSHIP_CUSTODY,
                    assertion_nature=m.AssertionNature.NORMATIVE,
                    value=m.OwnershipCustodyValue(
                        _sid(
                            "downstream/mirror",
                            m.SubjectKind.EXTERNAL_DEPENDENCY,
                        ),
                        m.OwnershipRole.CUSTODIAN,
                        m.OwnershipExclusivity.NON_EXCLUSIVE,
                    ),
                    evidence=(_ref("RELEASE.md"),),
                    candidate_authority=_release_authority(),
                    basis=m.SemanticBasis(
                        interp,
                        "release record names the downstream custodian",
                    ),
                ),
                m.CandidateSemanticClaim(
                    candidate_key="invariant-copy-only",
                    subject=release,
                    kind=m.ClaimKind.INVARIANT_CONSTRAINT,
                    assertion_nature=m.AssertionNature.NORMATIVE,
                    value=m.InvariantConstraintValue("copy-only downstream"),
                    evidence=(_ref("RELEASE.md"),),
                    candidate_authority=_release_authority(),
                    basis=m.SemanticBasis(
                        interp,
                        "release record states copy-only custody",
                    ),
                ),
                # Attempted downstream recomputation: the negative case.
                m.CandidateSemanticClaim(
                    candidate_key="invariant-recompute",
                    subject=release,
                    kind=m.ClaimKind.INVARIANT_CONSTRAINT,
                    assertion_nature=m.AssertionNature.NORMATIVE,
                    value=m.InvariantConstraintValue("downstream may recompute"),
                    evidence=(_ref("src/publish.py"),),
                    basis=m.SemanticBasis(
                        interp,
                        "publisher shows the recomputation attempt",
                    ),
                ),
            ),
            relationships=(),
            conflicts=(
                m.CandidateSemanticConflict(
                    left_key="invariant-copy-only",
                    right_key="invariant-recompute",
                    basis=m.SemanticBasis(
                        interp,
                        "downstream recomputation violates copy-only custody",
                    ),
                ),
            ),
        ),
    }


def _harness():
    structural = InMemoryStructuralSource(
        REPO,
        tuple(InMemoryFile(p, c) for p, c in FILES.items()),
        SUBJECTS,
        EDGES,
    )
    evidence = FixtureEvidenceSource(REPO, dict(FILES))
    store = SqliteSemanticStore(":memory:")
    ops.initialize_repository(
        ops.SemanticInitializeRepositoryRequest(
            repository_locator="fixture",
            authority_seeds=(),
        ),
        repository_id=REPO,
        structural=structural,
        evidence=evidence,
        store=store,
    )
    return structural, evidence, store, FixtureAgent(_candidates())


def _bounds():
    return DEFAULT_SERVICE_BOUNDS_POLICY.default_query_bounds


def _seeds():
    return (_ref("docs/terminology.md"), _ref("RELEASE.md"))


def _exchange(
    request, op, structural, evidence, store, agent, continuations=None, max_rounds=8
):
    continuations = continuations or ContinuationStore()
    current = op(
        request,
        structural=structural,
        evidence=evidence,
        store=store,
        continuations=continuations,
        authority_seeds=_seeds(),
    )
    for _ in range(max_rounds):
        if isinstance(current, m.SemanticAnswer):
            return current
        assert isinstance(current, PendingInterpretation), type(current)
        result = agent.perform(current.request)
        current = ops.submit_interpretation(
            current.continuation,
            result,
            structural=structural,
            evidence=evidence,
            store=store,
            continuations=continuations,
        )
    raise AssertionError("exchange did not settle")


def _request(op_cls, target):
    return op_cls(
        repository_id=REPO,
        target=m.SubjectSelector(None, target, (), None),
        bounds=_bounds(),
    )


class S01TerminologyTest(unittest.TestCase):
    def test_contract_authority_conflict_precedence(self):
        structural, evidence, store, agent = _harness()
        try:
            answer = _exchange(
                _request(ops.SemanticExplainRequest, "rep/display"),
                ops.explain,
                structural,
                evidence,
                store,
                agent,
            )
            kinds = {c.kind for c in answer.content.claims}
            self.assertIn(m.ClaimKind.REPRESENTATION_CONTRACT, kinds)
            # Conflict without invented resolution.
            self.assertEqual(len(answer.content.conflicts), 1)
            conflict = answer.content.conflicts[0]
            self.assertIsNone(conflict.declared_precedence)
            # Transformation binding present via trace.
            traced = _exchange(
                ops.SemanticTraceRequest(
                    repository_id=REPO,
                    target=m.SubjectSelector(None, "rep/wire", (), None),
                    direction=StructuralDirection.BOTH,
                    relationship_filter=None,
                    boundary_only=False,
                    bounds=_bounds(),
                ),
                ops.trace,
                structural,
                evidence,
                store,
                agent,
            )
            self.assertIn(
                m.RelationshipKind.TRANSFORMS_TO,
                {r.kind for r in traced.content.relationships},
            )
            # Governing terminology authority + declared precedence.
            auth = _exchange(
                _request(ops.SemanticAuthorityRequest, "rep/display"),
                ops.authority,
                structural,
                evidence,
                store,
                agent,
            )
            kinds = {b.authority_kind for b in auth.content.governing_bindings}
            self.assertIn(m.AuthorityKind.TERMINOLOGY, kinds)
            self.assertTrue(auth.content.precedence)
            self.assertTrue(
                any(
                    r.kind is m.ResolutionKind.MISSING_AUTHORITY
                    for r in auth.content.unresolved
                )
            )
        finally:
            store.close()


class S02CustodyTest(unittest.TestCase):
    def test_publication_custody_surface(self):
        structural, evidence, store, agent = _harness()
        try:
            answer = _exchange(
                _request(ops.SemanticExplainRequest, "contract/release-1.0"),
                ops.explain,
                structural,
                evidence,
                store,
                agent,
            )
            kinds = {c.kind for c in answer.content.claims}
            self.assertTrue(
                {
                    m.ClaimKind.LIFECYCLE_STATE,
                    m.ClaimKind.VERIFICATION,
                    m.ClaimKind.OWNERSHIP_CUSTODY,
                    m.ClaimKind.INVARIANT_CONSTRAINT,
                }
                <= kinds
            )
            phases = {
                c.value.phase
                for c in answer.content.claims
                if c.kind is m.ClaimKind.LIFECYCLE_STATE
            }
            self.assertIn(m.LifecyclePhase.TERMINAL, phases)
            roles = {
                c.value.role
                for c in answer.content.claims
                if c.kind is m.ClaimKind.OWNERSHIP_CUSTODY
            }
            self.assertIn(m.OwnershipRole.CUSTODIAN, roles)
            # Downstream recompute surfaces as conflict, not permission.
            # (The two VERIFICATION claims also differ in value and are
            # reported as a second pair: same subject+kind, unequal
            # values. No pair is resolved or hidden.)
            self.assertGreaterEqual(len(answer.content.conflicts), 1)
            statements = set()
            by_id = {c.claim_id.value: c for c in answer.content.claims}
            for conflict in answer.content.conflicts:
                for ref in (conflict.left, conflict.right):
                    claim = by_id.get(ref.id.value)
                    if claim is not None and isinstance(
                        claim.value, m.InvariantConstraintValue
                    ):
                        statements.add(claim.value.statement)
            self.assertTrue(
                {"copy-only downstream", "downstream may recompute"} <= statements
            )
            # Verification currency distinguishes candidate from pass.
            status = _exchange(
                _request(ops.SemanticStatusRequest, "contract/release-1.0"),
                ops.status,
                structural,
                evidence,
                store,
                agent,
            )
            currencies = {v.currency for v in status.content.verification_currency}
            self.assertEqual(
                currencies,
                {
                    m.VerificationCurrency.CANDIDATE,
                    m.VerificationCurrency.CURRENT_PASS,
                },
            )
            for claim in answer.content.claims:
                self.assertIsInstance(claim.trust, m.TrustState)
                self.assertIsInstance(claim.freshness.state, m.FreshnessState)
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
