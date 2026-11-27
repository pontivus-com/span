"""Support evaluation tests: sources, authority, premises, discovery, failure."""

from __future__ import annotations

import datetime
import hashlib
import json
import pathlib
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from span.core import model as m
from span.service.support import SupportService
from span.shell.filesystem_evidence import FilesystemEvidenceSource
from span.shell.sqlite_store.lifecycle import LifecycleStore
from tests.support.functional_pyramid import functional_pyramid_view

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
                binding_digest=m.ContentDigest("sha256:request"),
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
            )
        )
        return observation_id

    def _put_ranged_observation(
        self,
        observation_id: str,
        locator: str,
        start_line: int,
        end_line: int,
    ) -> str:
        content = (self.root / locator).read_text(encoding="utf-8")
        lines = content.splitlines(keepends=True)
        source_range = m.SourceRange(start_line, end_line)
        excerpt = "".join(lines[start_line - 1 : end_line])
        ranged_digest = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
        whole_digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        self.store.put_source_observation(
            m.SourceObservation(
                observation_id=m.SourceObservationId(observation_id),
                repository_id="repo-1",
                evidence=m.EvidenceRef(
                    evidence_id=m.EvidenceId(f"ev-{locator}"),
                    repository_id="repo-1",
                    source_kind=m.EvidenceSourceKind.SOURCE_CODE,
                    locator=locator,
                    revision_or_fingerprint=whole_digest,
                ),
                content_digest=m.ContentDigest(f"sha256:{ranged_digest}"),
                captured_at=NOW,
                total_lines=len(lines),
                delivered_ranges=(source_range,),
                whole_file=False,
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
                    request_id=m.RequestId(submission),
                ),
                surface=m.SurfaceKey(
                    repository_id="repo-1",
                    kind=m.SurfaceKind.FILE,
                    locator=f"src/{understanding_id}.py",
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

    def test_ranged_support_ignores_unrelated_edit_below_range(self) -> None:
        _write(
            self.root,
            "src/ranged.py",
            "header\ntarget\ncontext\nfooter\n",
        )
        observation = self._put_ranged_observation("obs-range", "src/ranged.py", 2, 2)
        self._create(
            "u-range",
            "sub-range",
            (m.SourceSupport(observation_id=m.SourceObservationId(observation)),),
        )
        _write(
            self.root,
            "src/ranged.py",
            "header\ntarget\ncontext\nchanged footer\n",
        )
        self.assertEqual(
            self.service.evaluate_version("u-range").state,
            m.SupportState.CURRENT,
        )

    def test_ranged_support_reassesses_edit_inside_range(self) -> None:
        _write(
            self.root,
            "src/ranged.py",
            "header\ntarget\ncontext\nfooter\n",
        )
        observation = self._put_ranged_observation("obs-range", "src/ranged.py", 2, 2)
        self._create(
            "u-range",
            "sub-range",
            (m.SourceSupport(observation_id=m.SourceObservationId(observation)),),
        )
        _write(
            self.root,
            "src/ranged.py",
            "header\nchanged target\ncontext\nfooter\n",
        )
        self.assertEqual(
            self.service.evaluate_version("u-range").state,
            m.SupportState.REASSESSMENT_REQUIRED,
        )

    def test_ranged_support_conservatively_reassesses_insertion_above(self) -> None:
        _write(
            self.root,
            "src/ranged.py",
            "header\ntarget\ncontext\nfooter\n",
        )
        observation = self._put_ranged_observation("obs-range", "src/ranged.py", 2, 2)
        self._create(
            "u-range",
            "sub-range",
            (m.SourceSupport(observation_id=m.SourceObservationId(observation)),),
        )
        _write(
            self.root,
            "src/ranged.py",
            "inserted\nheader\ntarget\ncontext\nfooter\n",
        )
        self.assertEqual(
            self.service.evaluate_version("u-range").state,
            m.SupportState.REASSESSMENT_REQUIRED,
        )

    def test_unbindable_range_falls_back_to_whole_file_identity(self) -> None:
        _write(
            self.root,
            "src/ranged.py",
            "header\ntarget\ncontext\nfooter\n",
        )
        observation = self._put_ranged_observation("obs-range", "src/ranged.py", 3, 4)
        self._create(
            "u-range",
            "sub-range",
            (m.SourceSupport(observation_id=m.SourceObservationId(observation)),),
        )
        _write(self.root, "src/ranged.py", "header\ntarget\n")
        evaluation = self.service.evaluate_version("u-range")
        self.assertEqual(
            evaluation.state,
            m.SupportState.REASSESSMENT_REQUIRED,
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
                    request_id=m.RequestId("sub-multi"),
                ),
                surface=m.SurfaceKey(
                    repository_id="repo-1",
                    kind=m.SurfaceKind.FILE,
                    locator="src/multi.py",
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

    def test_dependency_findings_address_each_dependency(self) -> None:
        first = self._put_observation("obs-1", "src/app.py")
        _write(self.root, "src/util.py", "helper\n")
        second = self._put_observation("obs-2", "src/util.py")
        self._create(
            "u-a",
            "sub-a",
            (
                m.SourceSupport(observation_id=m.SourceObservationId(first)),
                m.SourceSupport(observation_id=m.SourceObservationId(second)),
            ),
        )
        _write(self.root, "src/util.py", "changed helper\n")
        evaluation = self.service.evaluate_version("u-a").conclusions[0].evaluation
        self.assertEqual(evaluation.state, m.SupportState.REASSESSMENT_REQUIRED)
        self.assertEqual(len(evaluation.findings), 2)
        by_observation = {
            finding.dependency.observation_id.value: finding
            for finding in evaluation.findings
        }
        self.assertEqual(by_observation[first].state, m.SupportState.CURRENT)
        self.assertEqual(
            by_observation[second].state,
            m.SupportState.REASSESSMENT_REQUIRED,
        )
        self.assertIn("observed source bytes changed", by_observation[second].reason)

    def test_public_support_basis_preserves_recorded_source_boundary(self) -> None:
        self._put_observation("public-source", "src/app.py")
        dependency = m.SourceSupport(
            observation_id=m.SourceObservationId("public-source")
        )
        self._create("u-public-source", "req-public-source", (dependency,))
        ref = m.ConclusionRevisionRef(
            understanding_id=m.UnderstandingId("u-public-source"),
            conclusion_id=m.ConclusionId("c-1"),
            revision=m.ConclusionRevisionNumber(1),
        )
        _write(self.root, "src/app.py", "changed\n")
        qualification = self.service.qualify_support(
            self.service.evaluate_revision(ref)
        )
        self.assertEqual(len(qualification.findings), 1)
        basis = qualification.findings[0].basis
        self.assertIsInstance(basis, m.SourceSupportBasis)
        assert isinstance(basis, m.SourceSupportBasis)
        observation = self.store.get_source_observation("public-source")
        self.assertEqual(basis.evidence, observation.evidence)
        self.assertEqual(basis.ranges, observation.delivered_ranges)
        self.assertEqual(basis.captured_at, observation.captured_at)
        self.assertEqual(basis.whole_file, observation.whole_file)

    def test_public_basis_preserves_recorded_dependency_facts(self) -> None:
        observation = self._put_ranged_observation("obs-audit", "src/app.py", 1, 1)
        source = m.SourceSupport(m.SourceObservationId(observation))
        recorded = self.store.get_source_observation(observation)
        scope = m.EvidenceScope(paths=("src",))
        discovery = m.DiscoveryObservation(
            observation_id=m.DiscoveryObservationId("disc-audit"),
            repository_id="repo-1",
            scope=scope,
            membership_fingerprint="sha256:private-discovery",
            captured_at=NOW,
        )
        self.store.put_discovery_observation(discovery)
        authority = m.AuthorityBinding(
            evidence_ref=recorded.evidence,
            authority_kind=m.AuthorityKind.REPOSITORY_RULE,
            status=m.AuthorityStatus.SUPERSEDED,
            applicability=m.AuthorityApplicability(description="Recorded applicability"),
            declared_precedence=m.DeclaredPrecedence(
                kind=m.PrecedenceKind.PRIORITY_RANK,
                priority_rank=1,
                precedence_scheme="recorded policy",
            ),
        )
        premise = m.ConclusionRevisionRef(
            understanding_id=m.UnderstandingId("u-audit"),
            conclusion_id=m.ConclusionId("c-audit"),
            revision=m.ConclusionRevisionNumber(2),
        )
        route = m.FunctionalRouteSupport(
            repository_id="repo-1",
            pyramid_id=m.FunctionalPyramidId("fp-audit"),
            semantic_scope=scope,
            route_identity=m.FunctionalRouteIdentity("private-route"),
        )
        cases = (
            (
                source,
                m.SourceSupportBasis(
                    evidence=recorded.evidence,
                    observation_id=recorded.observation_id,
                    ranges=recorded.delivered_ranges,
                    captured_at=recorded.captured_at,
                    whole_file=False,
                ),
            ),
            (
                m.DiscoverySupport(discovery.observation_id),
                m.DiscoverySupportBasis("repo-1", scope, NOW),
            ),
            (
                m.AuthoritySupportDependency(authority),
                m.AuthoritySupportBasis(
                    authority.evidence_ref,
                    authority.authority_kind,
                    authority.status,
                    authority.applicability,
                    authority.declared_precedence,
                ),
            ),
            (m.PremiseSupport(premise), m.PremiseSupportBasis(premise)),
            (route, m.GovernanceSupportBasis("repo-1", route.pyramid_id, scope)),
        )
        for dependency, expected in cases:
            with self.subTest(dependency=type(dependency).__name__):
                self.assertEqual(self.service.support_basis(dependency), expected)

    def test_unavailable_recorded_basis_preserves_exact_reference(self) -> None:
        cases = (
            (
                "find_source_observation",
                m.SourceSupport(m.SourceObservationId("missing")),
            ),
            (
                "find_discovery_observation",
                m.DiscoverySupport(m.DiscoveryObservationId("missing")),
            ),
        )
        for lookup, dependency in cases:
            with self.subTest(lookup=lookup):
                missing = self.service.support_basis(dependency)
                self.assertIsInstance(missing, m.UnavailableSupportBasis)
                assert isinstance(missing, m.UnavailableSupportBasis)
                self.assertEqual(missing.reference, dependency.observation_id)
                with mock.patch.object(self.store, lookup, side_effect=OSError("down")):
                    self.assertEqual(self.service.support_basis(dependency), missing)
                with mock.patch.object(
                    self.store, lookup, side_effect=ValueError("bad")
                ):
                    with self.assertRaisesRegex(ValueError, "bad"):
                        self.service.support_basis(dependency)

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

    def test_cross_repository_authority_uses_canonical_owner_runtime(self) -> None:
        base = pathlib.Path(self._tmp.name)
        root_b = base / "repo-b"
        root_b.mkdir()
        _write(root_b, "docs/rule.md", "external rule\n")
        digest = hashlib.sha256((root_b / "docs/rule.md").read_bytes()).hexdigest()
        binding = m.AuthorityBinding(
            evidence_ref=m.EvidenceRef(
                evidence_id=m.EvidenceId("auth-b"),
                repository_id="repo-b",
                source_kind=m.EvidenceSourceKind.DOCUMENTATION,
                locator="docs/rule.md",
                revision_or_fingerprint=f"sha256:{digest}",
            ),
            authority_kind=m.AuthorityKind.REPOSITORY_RULE,
            status=m.AuthorityStatus.ACCEPTED,
        )
        store_b = LifecycleStore(
            base / "repo-b.db",
            retention=RETENTION,
            clock=lambda: NOW,
        )
        self.addCleanup(store_b.close)
        store_b.register_repository(
            "repo-b",
            str(root_b),
            authority_bindings=(binding,),
        )
        runtime_a = SimpleNamespace(
            repository_id="repo-1",
            root=str(self.root),
            store=self.store,
            evidence=self.evidence,
        )
        runtime_b = SimpleNamespace(
            repository_id="repo-b",
            root=str(root_b),
            store=store_b,
            evidence=FilesystemEvidenceSource("repo-b", root_b),
        )
        runtimes = {"repo-1": runtime_a, "repo-b": runtime_b}
        service = SupportService(
            store=self.store,
            evidence=self.evidence,
            authority=self.store,
            repository_runtime=lambda repository_id: runtimes[repository_id],
            clock=lambda: NOW,
        )
        self._create(
            "u-cross-authority",
            "sub-cross-authority",
            (m.AuthoritySupportDependency(authority=binding),),
        )

        self.assertEqual(
            service.evaluate_version("u-cross-authority").state,
            m.SupportState.CURRENT,
        )

        _write(root_b, "docs/rule.md", "changed external rule\n")
        self.assertEqual(
            service.evaluate_version("u-cross-authority").state,
            m.SupportState.REASSESSMENT_REQUIRED,
        )

    def test_external_authority_without_repository_runtime_fails_closed(self) -> None:
        binding = m.AuthorityBinding(
            evidence_ref=m.EvidenceRef(
                evidence_id=m.EvidenceId("auth-external"),
                repository_id="repo-b",
                source_kind=m.EvidenceSourceKind.DOCUMENTATION,
                locator="docs/rule.md",
                revision_or_fingerprint="sha256:external",
            ),
            authority_kind=m.AuthorityKind.REPOSITORY_RULE,
            status=m.AuthorityStatus.ACCEPTED,
        )
        self._create(
            "u-external-authority-missing-runtime",
            "sub-external-authority-missing-runtime",
            (m.AuthoritySupportDependency(authority=binding),),
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "repository-qualified authority evaluation is not configured",
        ):
            self.service.evaluate_version("u-external-authority-missing-runtime")

    def test_premise_withdrawal_is_unverifiable(self) -> None:
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
                    request_id=m.RequestId("sub-withdraw"),
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
            m.SupportState.UNVERIFIABLE,
        )

    def test_premise_supersession_requires_reassessment(self) -> None:
        observation = self._put_observation("obs-1", "src/app.py")
        source = m.SourceSupport(observation_id=m.SourceObservationId(observation))
        self._create("u-a", "sub-a", (source,))
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
                    request_id=m.RequestId("sub-replace"),
                ),
                understanding_id=m.UnderstandingId("u-a"),
                expected_version=m.UnderstandingVersionNumber(1),
                replace=(
                    m.ReplaceConclusion(
                        old=premise,
                        new_conclusion_id=m.ConclusionId("c-2"),
                        statement="A is replaced.",
                        assertion_nature=m.AssertionNature.DESCRIPTIVE,
                        scope=m.EvidenceScope(),
                        support=(source,),
                        basis=self._basis(),
                        replacement_basis=self._basis(),
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
                        request_id=m.RequestId(submission),
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

    def test_functional_route_support_uses_retained_surface_and_shared_index(
        self,
    ) -> None:
        dependency = m.FunctionalRouteSupport(
            repository_id="repo-1",
            pyramid_id=m.FunctionalPyramidId("fp-1"),
            semantic_scope=m.EvidenceScope(paths=("src/u-a.py",)),
            route_identity=m.FunctionalRouteIdentity("route-1"),
        )
        self._create("u-a", "sub-route", (dependency,))
        ref = self.store.get_version("u-a", 1).conclusions[0]
        self.assertEqual(
            self.store.support_dependents("FUNCTIONAL_ROUTE", "route-1"),
            (ref,),
        )

        seen: list[m.SurfaceKey] = []

        def current_route(recorded, surface):
            seen.append(surface)
            return (
                functional_pyramid_view(
                    recorded.semantic_scope,
                    pyramid_id=recorded.pyramid_id.value,
                ),
                recorded.route_identity,
            )

        service = SupportService(
            store=self.store,
            evidence=self.evidence,
            authority=self.store,
            clock=lambda: NOW,
            functional_route_resolver=current_route,
        )
        evaluation = service.evaluate_revision(ref)
        self.assertEqual(evaluation.state, m.SupportState.CURRENT)
        self.assertEqual(
            seen,
            [
                m.SurfaceKey(
                    repository_id="repo-1",
                    kind=m.SurfaceKind.FILE,
                    locator="src/u-a.py",
                )
            ],
        )

    def test_functional_route_support_distinguishes_route_states(self) -> None:
        dependency = m.FunctionalRouteSupport(
            repository_id="repo-1",
            pyramid_id=m.FunctionalPyramidId("fp-1"),
            semantic_scope=m.EvidenceScope(paths=("src/u-a.py",)),
            route_identity=m.FunctionalRouteIdentity("route-1"),
        )
        self._create("u-a", "sub-route-states", (dependency,))
        ref = self.store.get_version("u-a", 1).conclusions[0]

        cases = (
            (
                m.FunctionalPyramidParticipation(
                    m.FunctionalPyramidParticipationState.UNCONFIGURED
                ),
                None,
                m.SupportState.REASSESSMENT_REQUIRED,
            ),
            (
                m.FunctionalPyramidParticipation(
                    m.FunctionalPyramidParticipationState.EXCLUDED
                ),
                None,
                m.SupportState.REASSESSMENT_REQUIRED,
            ),
            (
                functional_pyramid_view(
                    dependency.semantic_scope,
                    pyramid_id="fp-2",
                ),
                m.FunctionalRouteIdentity("route-1"),
                m.SupportState.REASSESSMENT_REQUIRED,
            ),
            (
                functional_pyramid_view(
                    dependency.semantic_scope,
                    pyramid_id=dependency.pyramid_id.value,
                ),
                m.FunctionalRouteIdentity("route-2"),
                m.SupportState.REASSESSMENT_REQUIRED,
            ),
            (
                functional_pyramid_view(
                    dependency.semantic_scope,
                    pyramid_id=dependency.pyramid_id.value,
                    status=m.FunctionalPyramidRouteStatus.UNRESOLVED,
                ),
                None,
                m.SupportState.UNVERIFIABLE,
            ),
            (
                m.FunctionalPyramidUnavailable(
                    failure="declaration source unavailable",
                    recovery="restore the declared source",
                ),
                None,
                m.SupportState.UNVERIFIABLE,
            ),
        )
        for current, route_identity, expected in cases:
            with self.subTest(current=type(current).__name__, expected=expected.value):
                service = SupportService(
                    store=self.store,
                    evidence=self.evidence,
                    authority=self.store,
                    clock=lambda: NOW,
                    functional_route_resolver=lambda _dependency, _surface: (
                        current,
                        route_identity,
                    ),
                )
                self.assertEqual(service.evaluate_revision(ref).state, expected)

        with self.assertRaisesRegex(RuntimeError, "route evaluation is not configured"):
            self.service.evaluate_revision(ref)

    def test_functional_route_support_propagates_through_premises(self) -> None:
        route_identity = [m.FunctionalRouteIdentity("route-1")]
        dependency = m.FunctionalRouteSupport(
            repository_id="repo-1",
            pyramid_id=m.FunctionalPyramidId("fp-1"),
            semantic_scope=m.EvidenceScope(paths=("src/u-a.py",)),
            route_identity=route_identity[0],
        )
        self._create("u-a", "sub-route-premise", (dependency,))
        premise = self.store.get_version("u-a", 1).conclusions[0]
        self._create("u-b", "sub-route-dependent", (m.PremiseSupport(premise),))

        def current_route(recorded, _surface):
            return (
                functional_pyramid_view(
                    recorded.semantic_scope,
                    pyramid_id=recorded.pyramid_id.value,
                ),
                route_identity[0],
            )

        service = SupportService(
            store=self.store,
            evidence=self.evidence,
            authority=self.store,
            clock=lambda: NOW,
            functional_route_resolver=current_route,
        )
        self.assertEqual(service.evaluate_version("u-b").state, m.SupportState.CURRENT)
        route_identity[0] = m.FunctionalRouteIdentity("route-2")
        self.assertEqual(
            service.evaluate_version("u-b").state,
            m.SupportState.REASSESSMENT_REQUIRED,
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

            def fingerprints(self, *args, **kwargs):
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
