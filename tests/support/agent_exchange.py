"""Shared deterministic harness for operation tests.

Extracted from ``tests/unit/test_phase3_operations.py`` so that the answer
conformance gate does not import another test module's internals.

The harness is fixture-only: an in-memory structural source, a fixture evidence
source, a ``:memory:`` semantic store, and a ``FixtureAgent`` standing in for the
invoking agent. No product code lives here.
"""

from span.core import model as m
from span.ports.interpretation import PendingInterpretation
from span import service as ops
from span.shell.agent_exchange.continuations import ContinuationStore
from tests.support.agent_fixture import FixtureCandidates
from span.shell.structural.memory import (
    InMemoryEdge,
    InMemorySubject,
)

from tests.support.factories import query_bounds, semantic_harness

from functools import partial as _partial
from tests.support.factories import subject_id

from tests.support.factories import evidence_ref

REPO = "flow-svc"

FILES = {
    "README.md": "# flow-svc\n\nMoves records.\n",
    "OWNERSHIP.md": "# Ownership\n\nTeam flow owns flow-svc.\n",
    "config.yaml": "workers: 4\n",
    "src/flow.py": "class Pipe:\n    pass\n",
    "src/store.py": "class Ledger:\n    pass\n",
}

SUBJECTS = (
    InMemorySubject("cap/flow", m.SubjectKind.CAPABILITY, "flow-cap"),
    InMemorySubject("src/flow.py", m.SubjectKind.COMPONENT, "flow"),
    InMemorySubject("src/flow.py:Pipe", m.SubjectKind.CODE_SYMBOL, "Pipe"),
    InMemorySubject("src/store.py", m.SubjectKind.COMPONENT, "store"),
    InMemorySubject("conf/workers", m.SubjectKind.CONFIGURATION, "workers"),
    InMemorySubject("contract/api", m.SubjectKind.CONTRACT, "api"),
    InMemorySubject("test/test_flow.py", m.SubjectKind.TEST_OR_GATE, "flow-test"),
)

EDGES = (
    InMemoryEdge("src/flow.py:Pipe", m.StructuralEdgeKind.DEFINES, "src/flow.py"),
    InMemoryEdge("src/flow.py", m.StructuralEdgeKind.REFERENCES, "src/store.py"),
    InMemoryEdge(
        "src/flow.py",
        m.StructuralEdgeKind.REFERENCES,
        "test/test_flow.py",
    ),
)


_sid = _partial(subject_id, repository_id=REPO)


_ref = _partial(evidence_ref, repository_id=REPO, files=FILES)


_QUOTES = {
    "README.md": "Moves records",
    "OWNERSHIP.md": "Team flow owns flow-svc",
    "config.yaml": "workers: 4",
    "src/flow.py": "class Pipe",
}


def _accepted(path, kind, applicability=None):
    return m.CandidateAuthority(
        binding=m.AuthorityBinding(
            evidence_ref=_ref(path),
            authority_kind=kind,
            status=m.AuthorityStatus.ACCEPTED,
            applicability=m.AuthorityApplicability(
                subject_scope=(), description=applicability
            ),
        ),
        support=m.AuthoritySupport(
            quoted_span=_QUOTES[path],
            status_section=path,
            applicability_section=path if applicability else None,
        ),
    )


def _candidates():
    flow = _sid("src/flow.py")
    cap = _sid("cap/flow", m.SubjectKind.CAPABILITY)
    store = _sid("src/store.py")
    test = _sid("test/test_flow.py", m.SubjectKind.TEST_OR_GATE)
    interp = m.DerivationKind.SEMANTIC_INTERPRETATION
    return {
        "src/flow.py": FixtureCandidates(
            claims=(
                m.CandidateSemanticClaim(
                    subject=flow,
                    kind=m.ClaimKind.PURPOSE,
                    assertion_nature=m.AssertionNature.DESCRIPTIVE,
                    value=m.PurposeValue("moves records", (cap,)),
                    evidence=(_ref("README.md"),),
                    candidate_authority=_accepted(
                        "README.md", m.AuthorityKind.REPOSITORY_RULE
                    ),
                    basis=m.SemanticBasis(
                        interp,
                        "README states the flow purpose",
                    ),
                ),
                m.CandidateSemanticClaim(
                    subject=flow,
                    kind=m.ClaimKind.CONFIGURATION_ENVIRONMENT,
                    assertion_nature=m.AssertionNature.DESCRIPTIVE,
                    value=m.ConfigurationEnvironmentValue(
                        "worker count",
                        _sid("conf/workers", m.SubjectKind.CONFIGURATION),
                    ),
                    evidence=(_ref("config.yaml"),),
                    candidate_authority=_accepted(
                        "config.yaml",
                        m.AuthorityKind.CONFIGURATION_RUNTIME,
                    ),
                    basis=m.SemanticBasis(
                        interp,
                        "config declares the worker count",
                    ),
                ),
                m.CandidateSemanticClaim(
                    subject=flow,
                    kind=m.ClaimKind.LIFECYCLE_STATE,
                    assertion_nature=m.AssertionNature.DESCRIPTIVE,
                    value=m.LifecycleStateValue(m.LifecyclePhase.USE),
                    evidence=(_ref("src/flow.py"),),
                    candidate_authority=_accepted(
                        "src/flow.py", m.AuthorityKind.REPOSITORY_RULE
                    ),
                    basis=m.SemanticBasis(
                        interp,
                        "flow source shows active use",
                    ),
                ),
                m.CandidateSemanticClaim(
                    subject=flow,
                    kind=m.ClaimKind.VERIFICATION,
                    assertion_nature=m.AssertionNature.DESCRIPTIVE,
                    value=m.VerificationValue(
                        test,
                        m.VerificationKind.TEST,
                        m.AttestedCurrency.CANDIDATE,
                    ),
                    evidence=(_ref("src/flow.py"),),
                    basis=m.SemanticBasis(
                        interp,
                        "flow test is a verification candidate",
                    ),
                ),
                m.CandidateSemanticClaim(
                    subject=flow,
                    kind=m.ClaimKind.VERIFICATION,
                    assertion_nature=m.AssertionNature.DESCRIPTIVE,
                    value=m.VerificationValue(
                        test,
                        m.VerificationKind.GATE,
                        m.AttestedCurrency.UNKNOWN,
                    ),
                    evidence=(_ref("src/flow.py"),),
                    candidate_authority=_accepted(
                        "src/flow.py", m.AuthorityKind.REPOSITORY_RULE
                    ),
                    basis=m.SemanticBasis(
                        interp,
                        "flow gate passed at the observed revision",
                    ),
                ),
                m.CandidateSemanticClaim(
                    subject=flow,
                    kind=m.ClaimKind.OWNERSHIP_CUSTODY,
                    assertion_nature=m.AssertionNature.NORMATIVE,
                    value=m.OwnershipCustodyValue(
                        _sid("team/flow"),
                        m.OwnershipRole.OWNER,
                        m.OwnershipExclusivity.EXCLUSIVE,
                    ),
                    evidence=(_ref("OWNERSHIP.md"),),
                    candidate_authority=_accepted(
                        "OWNERSHIP.md", m.AuthorityKind.REPOSITORY_RULE
                    ),
                    basis=m.SemanticBasis(
                        interp,
                        "ownership record names the flow owner",
                    ),
                ),
                m.CandidateSemanticClaim(
                    subject=flow,
                    kind=m.ClaimKind.INVARIANT_CONSTRAINT,
                    assertion_nature=m.AssertionNature.NORMATIVE,
                    value=m.InvariantConstraintValue("records are immutable"),
                    evidence=(_ref("README.md"),),
                    candidate_authority=_accepted(
                        "README.md", m.AuthorityKind.REPOSITORY_RULE
                    ),
                    basis=m.SemanticBasis(
                        interp,
                        "README states the immutability invariant",
                    ),
                ),
                m.CandidateSemanticClaim(
                    subject=flow,
                    kind=m.ClaimKind.REPRESENTATION_CONTRACT,
                    assertion_nature=m.AssertionNature.DESCRIPTIVE,
                    value=m.RepresentationContractValue(
                        "wire",
                        _sid("contract/api", m.SubjectKind.CONTRACT),
                        m.RepresentationDirection.SOURCE,
                    ),
                    evidence=(_ref("README.md"),),
                    candidate_authority=_accepted(
                        "README.md", m.AuthorityKind.REPOSITORY_RULE
                    ),
                    basis=m.SemanticBasis(
                        interp,
                        "README states the wire representation contract",
                    ),
                ),
                m.CandidateSemanticClaim(
                    subject=flow,
                    kind=m.ClaimKind.CAPABILITY_MEMBERSHIP,
                    assertion_nature=m.AssertionNature.DESCRIPTIVE,
                    value=m.CapabilityMembershipValue(cap),
                    evidence=(_ref("src/flow.py"),),
                    basis=m.SemanticBasis(
                        interp,
                        "flow source shows capability membership",
                    ),
                ),
            ),
            relationships=(
                m.CandidateSemanticRelationship(
                    source=flow,
                    kind=m.RelationshipKind.CROSSES_BOUNDARY,
                    assertion_nature=m.AssertionNature.DESCRIPTIVE,
                    target=store,
                    evidence=(_ref("src/flow.py"),),
                    candidate_authority=_accepted(
                        "src/flow.py", m.AuthorityKind.REPOSITORY_RULE
                    ),
                    basis=m.SemanticBasis(
                        interp,
                        "flow source crosses into the store",
                    ),
                ),
                m.CandidateSemanticRelationship(
                    source=test,
                    kind=m.RelationshipKind.VERIFIED_BY,
                    assertion_nature=m.AssertionNature.DESCRIPTIVE,
                    target=flow,
                    evidence=(_ref("src/flow.py"),),
                    basis=m.SemanticBasis(
                        interp,
                        "flow test verifies the flow",
                    ),
                ),
            ),
        ),
        "contract/api": FixtureCandidates(
            claims=(
                m.CandidateSemanticClaim(
                    subject=_sid("contract/api", m.SubjectKind.CONTRACT),
                    kind=m.ClaimKind.PURPOSE,
                    assertion_nature=m.AssertionNature.DESCRIPTIVE,
                    value=m.PurposeValue("public record API", ()),
                    evidence=(_ref("README.md"),),
                    candidate_authority=_accepted(
                        "README.md",
                        m.AuthorityKind.CONTRACT_SPECIFICATION,
                        "public external API surface",
                    ),
                    basis=m.SemanticBasis(
                        interp,
                        "README states the public API purpose",
                    ),
                ),
            ),
            relationships=(),
        ),
    }


_bounds = query_bounds
_harness = _partial(
    semantic_harness,
    REPO,
    FILES,
    subjects=SUBJECTS,
    edges=EDGES,
    with_agent=_candidates(),
)


def _seeds():
    return (_ref("README.md"), _ref("OWNERSHIP.md"), _ref("config.yaml"))


def _exchange(
    request,
    op,
    structural,
    evidence,
    store,
    agent,
    seeds=None,
    continuations=None,
    max_rounds=8,
):
    """Drive the client protocol to an answer: operate, and while Span
    suspends (chained continuations for multi-subject operations),
    have the test agent perform each task and submit each result."""
    continuations = continuations or ContinuationStore()
    seeds = _seeds() if seeds is None else seeds
    current = op(
        request,
        structural=structural,
        evidence=evidence,
        store=store,
        continuations=continuations,
        authority_seeds=seeds,
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
    raise AssertionError("exchange did not settle to an answer")


def _establish(structural, evidence, store, agent) -> None:
    """Persist coverage for several subjects so status has a frontier."""
    for locator in (
        "src/flow.py",
        "src/store.py",
        "conf/workers",
        "contract/api",
        "test/test_flow.py",
    ):
        _exchange(
            ops.SemanticExplainRequest(
                repository_id=REPO,
                target=m.SubjectSelector(None, locator, (), None),
                bounds=_bounds(),
            ),
            ops.explain,
            structural,
            evidence,
            store,
            agent,
        )
