"""Held-out slice with the read-only Graft provider after explicit
initialization (plan Phase 2.9, as amended).

Held-out repository: ``tests/fixtures/order-svc`` (distinct from the
Phase-1 pay-svc synthetic repo). The structural provider is the real
Graft adapter over a machine-readable wiring fixture; Span does not run
``graft build`` or generate target Markdown. Evidence comes from
deterministic fixtures;
interpretation is performed by the deterministic test agent through the
§11.12 exchange (Span suspends, agent performs, agent submits); the
store is a real SQLite file. Generated material lives under
``.tmp-e2e/`` (git-ignored), never in fixtures.
"""

import json
import pathlib
import shutil
import unittest

from span.core import model as m
from span.ports.interpretation import PendingInterpretation
from span import service as ops
from span.service import DEFAULT_SERVICE_BOUNDS_POLICY
from span.shell.agent_exchange.continuations import ContinuationStore
from span.shell.agent_exchange.fixture import FixtureAgent, FixtureCandidates
from span.shell.evidence import FixtureEvidenceSource
from span.shell.sqlite_store import SqliteSemanticStore
from span.shell.structural import structural_source_from_config

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _git(args):
    import subprocess

    completed = subprocess.run(
        ("git", "-C", str(WORK_DIR)) + tuple(args),
        capture_output=True,
        text=True,
        timeout=60,
    )
    if completed.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {completed.stderr}")


FIXTURE_SRC = REPO_ROOT / "tests" / "fixtures" / "order-svc"
E2E_ROOT = REPO_ROOT / ".tmp-e2e"
WORK_DIR = E2E_ROOT / "order-svc"
DB_PATH = E2E_ROOT / "span-order-svc.db"


def _bounds():
    return DEFAULT_SERVICE_BOUNDS_POLICY.default_query_bounds


def _files(work):
    return {
        str(p.relative_to(work)): p.read_text(encoding="utf-8")
        for p in sorted(work.rglob("*"))
        if p.is_file()
        and "graft" not in p.parts
        and ".git" not in p.parts
        and not p.name.startswith(".")
    }


def _ref(repo_id, path, files):
    from span.shell.structural.memory import fingerprint_content

    return m.EvidenceRef(
        evidence_id=m.EvidenceId(f"ev-{path}"),
        repository_id=repo_id,
        source_kind=m.EvidenceSourceKind.SOURCE_CODE,
        locator=path,
        revision_or_fingerprint=fingerprint_content(files[path]),
    )


class Phase2SliceTest(unittest.TestCase):
    def test_held_out_repo_real_graft_end_to_end(self):
        # The whole e2e workspace is test-owned. A previous run leaves
        # ``span-data/`` (the wiring graph) and the SQLite store behind, so a
        # second run in the same checkout must start from a clean root.
        if E2E_ROOT.exists():
            shutil.rmtree(E2E_ROOT)
        E2E_ROOT.mkdir(parents=True)
        shutil.copytree(FIXTURE_SRC, WORK_DIR)
        (WORK_DIR / ".gitignore").write_text("graft/\n.ignore\n", encoding="utf-8")
        _git(("init", "-q"))
        _git(("add", "-A"))
        _git(
            (
                "-c",
                "user.email=test@span.local",
                "-c",
                "user.name=span-test",
                "commit",
                "-qm",
                "held-out fixture",
            )
        )
        graph_dir = (
            WORK_DIR.parent / "span-data" / "structural" / "order-svc" / ".graph"
        )
        graph_dir.mkdir(parents=True)
        (graph_dir / "wiring.json").write_text(
            json.dumps(
                {
                    "nodes": [
                        {
                            "id": "src/inventory.js",
                            "name": "inventory.js",
                            "kind": "file",
                            "path": "src/inventory.js",
                            "span": "L1-L4",
                            "signature": None,
                            "body_hash": "aa01",
                        },
                        {
                            "id": "src/inventory.js#reserve",
                            "name": "reserve",
                            "kind": "function",
                            "path": "src/inventory.js",
                            "span": "L1-L3",
                            "signature": "function reserve(sku)",
                            "body_hash": "bb02",
                        },
                        {
                            "id": "src/orders.js",
                            "name": "orders.js",
                            "kind": "file",
                            "path": "src/orders.js",
                            "span": "L1-L6",
                            "signature": None,
                            "body_hash": "cc03",
                        },
                        {
                            "id": "src/orders.js#place",
                            "name": "place",
                            "kind": "function",
                            "path": "src/orders.js",
                            "span": "L3-L5",
                            "signature": "function place(order)",
                            "body_hash": "dd04",
                        },
                        {
                            "id": "README.md",
                            "name": "README.md",
                            "kind": "file",
                            "path": "README.md",
                            "span": None,
                            "signature": None,
                            "body_hash": "ee05",
                        },
                    ],
                    "edges": [
                        {
                            "source": "src/inventory.js",
                            "target": "src/inventory.js#reserve",
                            "relation": "contains",
                        },
                        {
                            "source": "src/orders.js",
                            "target": "src/orders.js#place",
                            "relation": "contains",
                        },
                        {
                            "source": "src/orders.js",
                            "target": "src/inventory.js",
                            "relation": "imports",
                        },
                        {
                            "source": "src/orders.js#place",
                            "target": "src/inventory.js#reserve",
                            "relation": "calls",
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        if DB_PATH.exists():
            DB_PATH.unlink()
        store = None
        try:
            structural, repo_id = structural_source_from_config(
                str(WORK_DIR), WORK_DIR.parent / "span-data"
            )
            self.assertEqual(repo_id, "order-svc")
            files = _files(WORK_DIR)
            evidence = FixtureEvidenceSource(repo_id, files)
            store = SqliteSemanticStore(str(DB_PATH))
            continuations = ContinuationStore()

            init = ops.initialize_repository(
                ops.SemanticInitializeRepositoryRequest(
                    repository_locator=str(WORK_DIR),
                    authority_seeds=(
                        _ref(repo_id, "README.md", files),
                        _ref(repo_id, "OWNERSHIP.md", files),
                    ),
                ),
                repository_id=repo_id,
                structural=structural,
                evidence=evidence,
                store=store,
            )
            self.assertIs(init.readiness, m.RepositoryReadiness.READY)
            self.assertEqual(init.warnings, ())

            sid = m.SubjectId(
                repository_id=repo_id,
                subject_kind=m.SubjectKind.CODE_SYMBOL,
                canonical_locator="src/orders.js#place",
            )
            resolution = structural.resolve_subject(
                repo_id,
                m.SubjectSelector(None, "src/orders.js#place", (), None),
                _bounds(),
            )
            self.assertIs(resolution.ambiguity, m.ResolutionAmbiguity.RESOLVED)
            from span.ports.structural import StructuralDirection

            edges = structural.edges(
                repo_id, sid, (), StructuralDirection.DOWNSTREAM, _bounds()
            )
            self.assertTrue(
                {e.kind for e in edges.items} >= {m.StructuralEdgeKind.CALLS}
            )
            first = structural.repository_state(repo_id)
            second = structural.repository_state(repo_id)
            self.assertEqual(first.state_fingerprint, second.state_fingerprint)

            orders = m.SubjectId(
                repository_id=repo_id,
                subject_kind=m.SubjectKind.COMPONENT,
                canonical_locator="src/orders.js",
            )
            interp = m.DerivationKind.SEMANTIC_INTERPRETATION
            agent = FixtureAgent(
                {
                    "src/orders.js": FixtureCandidates(
                        claims=(
                            m.CandidateSemanticClaim(
                                subject=orders,
                                kind=m.ClaimKind.PURPOSE,
                                assertion_nature=m.AssertionNature.DESCRIPTIVE,
                                value=m.PurposeValue("takes orders", ()),
                                evidence=(_ref(repo_id, "README.md", files),),
                                candidate_authority=m.CandidateAuthority(
                                    binding=m.AuthorityBinding(
                                        evidence_ref=_ref(repo_id, "README.md", files),
                                        authority_kind=(
                                            m.AuthorityKind.REPOSITORY_RULE
                                        ),
                                        status=m.AuthorityStatus.ACCEPTED,
                                    ),
                                    support=m.AuthoritySupport(
                                        quoted_span="Takes orders",
                                        status_section="README.md",
                                        applicability_section=None,
                                    ),
                                ),
                                basis=m.SemanticBasis(
                                    interp, "README states the order purpose"
                                ),
                            ),
                            m.CandidateSemanticClaim(
                                subject=orders,
                                kind=m.ClaimKind.OWNERSHIP_CUSTODY,
                                assertion_nature=m.AssertionNature.NORMATIVE,
                                value=m.OwnershipCustodyValue(
                                    m.SubjectId(
                                        repository_id=repo_id,
                                        subject_kind=m.SubjectKind.COMPONENT,
                                        canonical_locator="team/orders",
                                    ),
                                    m.OwnershipRole.OWNER,
                                    m.OwnershipExclusivity.EXCLUSIVE,
                                ),
                                evidence=(_ref(repo_id, "OWNERSHIP.md", files),),
                                candidate_authority=m.CandidateAuthority(
                                    binding=m.AuthorityBinding(
                                        evidence_ref=_ref(
                                            repo_id, "OWNERSHIP.md", files
                                        ),
                                        authority_kind=(
                                            m.AuthorityKind.REPOSITORY_RULE
                                        ),
                                        status=m.AuthorityStatus.ACCEPTED,
                                    ),
                                    support=m.AuthoritySupport(
                                        quoted_span="Team orders owns",
                                        status_section="OWNERSHIP.md",
                                        applicability_section=None,
                                    ),
                                ),
                                basis=m.SemanticBasis(
                                    interp,
                                    "ownership record names the order owner",
                                ),
                            ),
                        ),
                        relationships=(),
                    )
                }
            )
            seeds = (
                _ref(repo_id, "README.md", files),
                _ref(repo_id, "OWNERSHIP.md", files),
            )
            suspended = ops.explain(
                ops.SemanticExplainRequest(
                    repository_id=repo_id,
                    target=m.SubjectSelector(None, "src/orders.js", (), None),
                    bounds=_bounds(),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
                authority_seeds=seeds,
            )
            # Span suspends (no stored semantics); the test agent performs.
            self.assertIsInstance(suspended, PendingInterpretation)
            self.assertTrue(suspended.request.evidence_units)
            answer = ops.submit_interpretation(
                suspended.continuation,
                agent.perform(suspended.request),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            self.assertIsInstance(answer.content, m.ExplainContent)
            self.assertEqual(len(answer.content.claims), 2)
            self.assertTrue(
                all(c.trust is m.TrustState.ESTABLISHED for c in answer.content.claims)
            )
            auth_suspended = ops.authority(
                ops.SemanticAuthorityRequest(
                    repository_id=repo_id,
                    target=m.SubjectSelector(None, "src/orders.js", (), None),
                    bounds=_bounds(),
                ),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
                authority_seeds=seeds,
            )
            # B.7: the CQ_01 explain examination never satisfies the
            # unexamined CQ_06 authority question — authority suspends
            # its own bounded unit even though claims exist.
            self.assertIsInstance(auth_suspended, PendingInterpretation)
            self.assertIs(
                auth_suspended.request.question.question_class,
                m.SemanticQuestionClass.CQ_06,
            )
            auth_answer = ops.submit_interpretation(
                auth_suspended.continuation,
                agent.perform(auth_suspended.request),
                structural=structural,
                evidence=evidence,
                store=store,
                continuations=continuations,
            )
            self.assertIsInstance(auth_answer, m.SemanticAnswer)
            self.assertIsInstance(auth_answer.content, m.AuthorityContent)
            self.assertEqual(len(auth_answer.content.governing_bindings), 2)
        finally:
            if store is not None:
                store.close()


if __name__ == "__main__":
    unittest.main()
