"""Support evaluation tests: sources, authority, premises, discovery, failure."""

from __future__ import annotations

import datetime
import hashlib
import json
import pathlib
import tempfile
import unittest

from span.core import model as m
from span.service.support import SupportService
from span.shell.filesystem_evidence import FilesystemEvidenceSource
from span.shell.sqlite_store.lifecycle import LifecycleStore

NOW = datetime.datetime(2026, 10, 31, 12, 0, tzinfo=datetime.timezone.utc)
RETENTION = m.LifecycleRetention(
    context_lifetime=datetime.timedelta(hours=1),
    replay_retention=datetime.timedelta(hours=4),
)
CONTEXT_ID = m.InvestigationContextId("ctx-1")


def _write(root: pathlib.Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class SupportServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = pathlib.Path(self._tmp.name)
        self.root = base / "repo"
        self.root.mkdir()
        _write(self.root, "src/app.py", "line1\nline2\n")
        _write(self.root, "docs/rule.md", "rule\n")
        self.store = LifecycleStore(
            base / "lifecycle.db", retention=RETENTION, clock=lambda: NOW
        )
        self.addCleanup(self.store.close)
        self.store.register_repository("repo-1", str(self.root))
        self.store.put_context(
            m.InvestigationContext(
                context_id=CONTEXT_ID,
                repository_id="repo-1",
                request_id=m.RequestId("req-1"),
                request_digest=m.ContentDigest("sha256:request"),
                origin=m.ContextOrigin.EVIDENCE_ONLY,
                state=m.ContextState.LIVE,
                scope=m.EvidenceScope(),
                created_at=NOW,
                expires_at=NOW + RETENTION.context_lifetime,
            )
        )
        self.evidence = FilesystemEvidenceSource("repo-1", self.root)
        self.service = SupportService(
            store=self.store,
            evidence=self.evidence,
            authority=self.store,
            clock=lambda: NOW,
        )

    def _put_observation(self, observation_id: str, locator: str) -> str:
        data = (self.root / locator).read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        self.store.put_source_observation(
            m.SourceObservation(
                observation_id=m.SourceObservationId(observation_id),
                repository_id="repo-1",
                evidence=m.EvidenceRef(
                    evidence_id=m.EvidenceId(f"ev-{locator}"),
                    repository_id="repo-1",
                    source_kind=m.EvidenceSourceKind.SOURCE_CODE,
                    locator=locator,
                    revision_or_fingerprint=digest,
                ),
                content_digest=m.ContentDigest(f"sha256:{digest}"),
                captured_at=NOW,
                total_lines=len(data.decode().splitlines()),
                whole_file=True,
                excerpt=data.decode(),
            )
        )
        return observation_id

    def _basis(self) -> m.SemanticBasis:
        return m.SemanticBasis(
            derivation=m.DerivationKind.EXPLICIT_EVIDENCE,
            summary="read",
            input_refs=(),
        )

    def _create(
        self,
        understanding_id: str,
        submission: str,
        support: tuple[m.SupportDependency, ...],
    ) -> m.RecordReceipt:
        return self.store.record_understanding(
            m.CreateUnderstandingCommand(
                identity=m.RecordingIdentity(
                    repository_id="repo-1",
                    context_id=CONTEXT_ID,
                    submission_id=m.SubmissionId(submission),
                ),
                target=m.ExplicitTarget(
                    question="What does A do?", scope=m.EvidenceScope()
                ),
                conclusions=(
                    m.ProposedConclusion(
                        conclusion_id=m.ConclusionId("c-1"),
                        statement="A does X.",
                        assertion_nature=m.AssertionNature.DESCRIPTIVE,
                        scope=m.EvidenceScope(),
                        support=support,
                        basis=self._basis(),
                    ),
                ),
            ),
            understanding_id=m.UnderstandingId(understanding_id),
        )

    def test_source_support_current_changed_missing(self) -> None:
        observation = self._put_observation("obs-1", "src/app.py")
        self._create(
            "u-a",
            "sub-a",
            (m.SourceSupport(observation_id=m.SourceObservationId(observation)),),
        )
        self.assertEqual(
            self.service.evaluate_version("u-a").state, m.SupportState.CURRENT
        )
        _write(self.root, "src/app.py", "line1\nchanged\n")
        self.assertEqual(
            self.service.evaluate_version("u-a").state,
            m.SupportState.REASSESSMENT_REQUIRED,
        )
        (self.root / "src/app.py").unlink()
        self.assertEqual(
            self.service.evaluate_version("u-a").state,
            m.SupportState.UNVERIFIABLE,
        )

    def test_unrelated_source_change_keeps_current(self) -> None:
        observation = self._put_observation("obs-1", "src/app.py")
        self._create(
            "u-a",
            "sub-a",
            (m.SourceSupport(observation_id=m.SourceObservationId(observation)),),
        )
        _write(self.root, "docs/rule.md", "changed rule\n")
        self.assertEqual(
            self.service.evaluate_version("u-a").state, m.SupportState.CURRENT
        )

    def test_sibling_conclusions_retain_independent_support(self) -> None:
        first = self._put_observation("obs-1", "src/app.py")
        _write(self.root, "src/util.py", "helper\n")
        second = self._put_observation("obs-2", "src/util.py")
        self.store.record_understanding(
            m.CreateUnderstandingCommand(
                identity=m.RecordingIdentity(
                    repository_id="repo-1",
                    context_id=CONTEXT_ID,
                    submission_id=m.SubmissionId("sub-multi"),
                ),
                target=m.ExplicitTarget(
                    question="What does A do?", scope=m.EvidenceScope()
                ),
                conclusions=(
                    m.ProposedConclusion(
                        conclusion_id=m.ConclusionId("c-1"),
                        statement="A does X.",
                        assertion_nature=m.AssertionNature.DESCRIPTIVE,
                        scope=m.EvidenceScope(),
                        support=(
                            m.SourceSupport(
                                observation_id=m.SourceObservationId(first)
                            ),
                        ),
                        basis=self._basis(),
                    ),
                    m.ProposedConclusion(
                        conclusion_id=m.ConclusionId("c-2"),
                        statement="A uses a helper.",
                        assertion_nature=m.AssertionNature.DESCRIPTIVE,
                        scope=m.EvidenceScope(),
                        support=(
                            m.SourceSupport(
                                observation_id=m.SourceObservationId(second)
                            ),
                        ),
                        basis=self._basis(),
                    ),
                ),
            ),
            understanding_id=m.UnderstandingId("u-a"),
        )
        _write(self.root, "src/app.py", "line1\nchanged\n")
        support = self.service.evaluate_version("u-a")
        states = {
            item.ref.conclusion_id.value: item.evaluation.state
            for item in support.conclusions
        }
        self.assertEqual(states["c-1"], m.SupportState.REASSESSMENT_REQUIRED)
        self.assertEqual(states["c-2"], m.SupportState.CURRENT)

    def test_authority_support_status_and_presence(self) -> None:
        digest = hashlib.sha256((self.root / "docs/rule.md").read_bytes()).hexdigest()
        binding = m.AuthorityBinding(
            evidence_ref=m.EvidenceRef(
                evidence_id=m.EvidenceId("auth-1"),
                repository_id="repo-1",
                source_kind=m.EvidenceSourceKind.DOCUMENTATION,
                locator="docs/rule.md",
                revision_or_fingerprint=f"sha256:{digest}",
            ),
            authority_kind=m.AuthorityKind.REPOSITORY_RULE,
            status=m.AuthorityStatus.ACCEPTED,
        )
        self.store.register_repository(
            "repo-1", str(self.root), authority_bindings=(binding,)
        )
        self._create(
            "u-a",
            "sub-a",
            (m.AuthoritySupportDependency(authority=binding),),
        )
        self.assertEqual(
            self.service.evaluate_version("u-a").state, m.SupportState.CURRENT
        )
        superseded = m.AuthorityBinding(
            evidence_ref=binding.evidence_ref,
            authority_kind=binding.authority_kind,
            status=m.AuthorityStatus.SUPERSEDED,
        )
        self.store.register_repository(
            "repo-1", str(self.root), authority_bindings=(superseded,)
        )
        self.assertEqual(
            self.service.evaluate_version("u-a").state,
            m.SupportState.REASSESSMENT_REQUIRED,
        )
        self.store.register_repository("repo-1", str(self.root), authority_bindings=())
        self.assertEqual(
            self.service.evaluate_version("u-a").state,
            m.SupportState.UNVERIFIABLE,
        )

    def test_premise_supersession_requires_reassessment(self) -> None:
        observation = self._put_observation("obs-1", "src/app.py")
        self._create(
            "u-a",
            "sub-a",
            (m.SourceSupport(observation_id=m.SourceObservationId(observation)),),
        )
        premise = m.ConclusionRevisionRef(
            understanding_id=m.UnderstandingId("u-a"),
            conclusion_id=m.ConclusionId("c-1"),
            revision=m.ConclusionRevisionNumber(1),
        )
        self._create("u-b", "sub-b", (m.PremiseSupport(premise=premise),))
        self.assertEqual(
            self.service.evaluate_version("u-b").state, m.SupportState.CURRENT
        )
        self.store.record_understanding(
            m.UpdateUnderstandingCommand(
                identity=m.RecordingIdentity(
                    repository_id="repo-1",
                    context_id=CONTEXT_ID,
                    submission_id=m.SubmissionId("sub-withdraw"),
                ),
                understanding_id=m.UnderstandingId("u-a"),
                expected_version=m.UnderstandingVersionNumber(1),
                withdraw=(
                    m.WithdrawConclusion(
                        conclusion_id=m.ConclusionId("c-1"),
                        basis=self._basis(),
                    ),
                ),
            )
        )
        self.assertEqual(
            self.service.evaluate_version("u-b").state,
            m.SupportState.REASSESSMENT_REQUIRED,
        )

    def test_discovery_membership_change(self) -> None:
        pairs, _ = self.evidence.list_inventory_entries(
            "repo-1", m.EvidenceScope(paths=("src",))
        )
        payload = json.dumps(
            [list(item) for item in pairs],
            sort_keys=True,
            separators=(",", ":"),
        )
        fingerprint = "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()
        self.store.put_discovery_observation(
            m.DiscoveryObservation(
                observation_id=m.DiscoveryObservationId("disc-1"),
                repository_id="repo-1",
                scope=m.EvidenceScope(paths=("src",)),
                membership_fingerprint=fingerprint,
                captured_at=NOW,
            )
        )
        self._create(
            "u-a",
            "sub-a",
            (m.DiscoverySupport(observation_id=m.DiscoveryObservationId("disc-1")),),
        )
        self.assertEqual(
            self.service.evaluate_version("u-a").state, m.SupportState.CURRENT
        )
        _write(self.root, "src/new.py", "new\n")
        self.assertEqual(
            self.service.evaluate_version("u-a").state,
            m.SupportState.REASSESSMENT_REQUIRED,
        )

    def test_verification_runs_are_independent_and_source_aware(self) -> None:
        observation = self._put_observation("obs-1", "src/app.py")
        for submission, outcome in (
            ("sub-v-pass", m.VerificationOutcome.PASS),
            ("sub-v-fail", m.VerificationOutcome.FAIL),
        ):
            self.store.record_verification(
                m.RecordVerificationCommand(
                    identity=m.RecordingIdentity(
                        repository_id="repo-1",
                        context_id=CONTEXT_ID,
                        submission_id=m.SubmissionId(submission),
                    ),
                    run=m.ProposedVerificationRun(
                        repository_id="repo-1",
                        scope=m.VerificationScope(
                            description="app entry",
                            scope=m.EvidenceScope(paths=("src/app.py",)),
                        ),
                        observations=(m.SourceObservationId(observation),),
                        command="python3 -m unittest",
                        scenario=None,
                        outcome=outcome,
                        observed_at=NOW,
                        observer="test",
                    ),
                )
            )
        runs = self.store._connection.execute(
            "SELECT run_id FROM verification_runs ORDER BY run_id"
        ).fetchall()
        self.assertEqual(len(runs), 2)
        for row in runs:
            support = self.service.evaluate_verification(row[0])
            self.assertEqual(support.state, m.SupportState.CURRENT)
            self.assertEqual(
                support.run.observations,
                (m.SourceObservationId(observation),),
            )
        _write(self.root, "src/app.py", "line1\nchanged\n")
        for row in runs:
            support = self.service.evaluate_verification(row[0])
            self.assertEqual(support.state, m.SupportState.REASSESSMENT_REQUIRED)
            self.assertEqual(
                support.run.observations,
                (m.SourceObservationId(observation),),
            )

    def test_provider_failure_does_not_erase_acceptance(self) -> None:
        observation = self._put_observation("obs-1", "src/app.py")
        receipt = self._create(
            "u-a",
            "sub-a",
            (m.SourceSupport(observation_id=m.SourceObservationId(observation)),),
        )

        class FailingEvidence:
            def list_inventory_entries(self, *args, **kwargs):
                raise RuntimeError("support provider down")

        failing = SupportService(
            store=self.store,
            evidence=FailingEvidence(),
            authority=self.store,
            clock=lambda: NOW,
        )
        with self.assertRaises(RuntimeError):
            failing.evaluate_version("u-a")
        self.assertEqual(self.store.get_receipt(receipt.identity), receipt)


if __name__ == "__main__":
    unittest.main()
