"""Functional Pyramid Version-3 source/service orchestration tests."""

import contextlib
import dataclasses
import datetime
import unittest
from unittest import mock

from span.core import model as m
from span.core.recording import RecordingConflict, RecordingValidationError
from span.ports.functional_pyramid import (
    FunctionalPyramidDeclarationInvalid,
    FunctionalPyramidRepositoryUnavailable,
)
from span.ports.structural import StaleContinuationError
from span.service.bounds import DEFAULT_SERVICE_BOUNDS_POLICY, encoded_size
from span.service.functional_pyramid import FunctionalPyramidService


def _ref(repository_id: str, locator: str) -> m.EvidenceRef:
    return m.EvidenceRef(
        evidence_id=m.EvidenceId(f"ev-{repository_id}-{locator}"),
        repository_id=repository_id,
        source_kind=m.EvidenceSourceKind.CONFIGURATION,
        locator=locator,
        revision_or_fingerprint=f"digest-{repository_id}-{locator}",
    )


def _binding(repository_id: str, locator: str) -> m.AuthorityBinding:
    return m.AuthorityBinding(
        evidence_ref=m.EvidenceRef(
            evidence_id=m.EvidenceId(f"authority-{repository_id}-{locator}"),
            repository_id=repository_id,
            source_kind=m.EvidenceSourceKind.DOCUMENTATION,
            locator=locator,
            revision_or_fingerprint=f"authority-digest-{repository_id}-{locator}",
        ),
        authority_kind=m.AuthorityKind.REPOSITORY_RULE,
        status=m.AuthorityStatus.ACCEPTED,
    )


def _placement(
    repository_id: str,
    locator: str,
    layer: m.FunctionalPyramidLayer,
    scope: str,
) -> m.FunctionalDocumentPlacement:
    return m.FunctionalDocumentPlacement(
        declaring_repository_id=repository_id,
        document=m.FunctionalDocumentRef(
            repository_id=repository_id,
            document_ref=locator,
            layer=layer,
        ),
        scope=scope,
    )


def _declaration(
    repository_id: str,
    *,
    local_scope: str | None = None,
) -> tuple[m.FunctionalPyramidDeclaration, ...]:
    root = _placement(
        repository_id,
        "docs/foundation.md",
        m.FunctionalPyramidLayer.P0,
        ".",
    )
    sources = [
        m.FunctionalPyramidDeclaration(
            version=3,
            source_id=f"{repository_id}:repository",
            kind=m.FunctionalPyramidSourceKind.REPOSITORY,
            scope=".",
            documents=(root.document.identity,),
            placements=(
                m.FunctionalDocumentDeclaration(
                    placement=root,
                    governing_placements=("ROOT",),
                ),
            ),
        )
    ]
    if local_scope is not None:
        local = _placement(
            repository_id,
            "docs/design.md",
            m.FunctionalPyramidLayer.P3,
            local_scope,
        )
        sources.append(
            m.FunctionalPyramidDeclaration(
                version=3,
                source_id=f"{repository_id}:{local_scope}",
                kind=m.FunctionalPyramidSourceKind.AREA,
                scope=local_scope,
                documents=(local.document.identity,),
                placements=(
                    m.FunctionalDocumentDeclaration(
                        placement=local,
                        governing_placements=(root,),
                    ),
                ),
            )
        )
    return tuple(sources)


class _Declarations:
    def __init__(self) -> None:
        self.bootstrap: tuple[m.EvidenceRef, m.FunctionalPyramidBootstrap] | None = None
        self.results: dict[
            tuple[str, str],
            (
                tuple[
                    m.EvidenceRef,
                    m.FunctionalPyramidDeclaration,
                    tuple[m.FunctionalPyramidFinding, ...],
                ]
                | m.EvidenceSourceFailure
                | Exception
            ),
        ] = {}
        self.calls: list[tuple[str, m.EvidenceRequest]] = []
        self.directories: dict[str, set[str]] = {
            "repo-a": {".", "src", "src/service"},
            "repo-b": {".", "src"},
        }

    def read_bootstrap(
        self, repository_id: str
    ) -> tuple[m.EvidenceRef, m.FunctionalPyramidBootstrap] | None:
        del repository_id
        return self.bootstrap

    def directory_exists(self, repository_id: str, directory: str) -> bool:
        return directory in self.directories.get(repository_id, set())

    def read_declaration(self, repository_id: str, request: m.EvidenceRequest):
        self.calls.append((repository_id, request))
        result = self.results[(repository_id, request.locator)]
        if isinstance(result, Exception):
            raise result
        return result


class _Authority:
    pass


class _State:
    def __init__(self) -> None:
        self.retention = m.LifecycleRetention(
            context_lifetime=datetime.timedelta(hours=1),
            replay_retention=datetime.timedelta(hours=2),
        )
        self.active: dict[str, m.FunctionalPyramidId] = {}
        self.versions: dict[m.FunctionalPyramidId, m.FunctionalPyramidVersion] = {}
        self.members: dict[
            tuple[m.FunctionalPyramidId, m.FunctionalPyramidVersion],
            tuple[m.FunctionalPyramidMemberView, ...],
        ] = {}
        self.excluded: set[str] = set()
        self.receipts: dict[str, m.RetrievedFunctionalPyramidReceipt] = {}
        self.transaction_paths: list[tuple[tuple[str, str], ...]] = []

    def active_pyramid_id(self, repository_id: str) -> m.FunctionalPyramidId | None:
        return self.active.get(repository_id)

    def pyramid_version(
        self, pyramid_id: m.FunctionalPyramidId
    ) -> m.FunctionalPyramidVersion | None:
        return self.versions.get(pyramid_id)

    def pyramid_members(
        self,
        pyramid_id: m.FunctionalPyramidId,
        version: m.FunctionalPyramidVersion | None = None,
    ) -> tuple[m.FunctionalPyramidMemberView, ...]:
        selected = version or self.versions.get(pyramid_id)
        if selected is None:
            return ()
        return self.members.get((pyramid_id, selected), ())

    def is_excluded(self, repository_id: str) -> bool:
        return repository_id in self.excluded

    def receipt(
        self, request_id: m.RequestId
    ) -> m.RetrievedFunctionalPyramidReceipt | None:
        return self.receipts.get(request_id.value)

    @contextlib.contextmanager
    def transaction(self, repository_paths=()):
        paths = tuple(repository_paths)
        self.transaction_paths.append(paths)
        yield self

    def write_pyramid_version(
        self,
        *,
        pyramid_id,
        version,
        content_digest,
        committed_at,
        members,
    ) -> None:
        del content_digest, committed_at
        self.versions[pyramid_id] = version
        self.members[(pyramid_id, version)] = members

    def set_current_pyramid(self, *, pyramid_id, version, members) -> None:
        for repository_id, active_id in tuple(self.active.items()):
            if active_id == pyramid_id:
                del self.active[repository_id]
        for member in members:
            self.active[member.repository_id] = pyramid_id
            self.excluded.discard(member.repository_id)
        self.versions[pyramid_id] = version

    def clear_current_pyramid(self, pyramid_id) -> None:
        for repository_id, active_id in tuple(self.active.items()):
            if active_id == pyramid_id:
                del self.active[repository_id]
        self.versions.pop(pyramid_id, None)

    def set_excluded(self, repository_id: str, excluded: bool) -> None:
        if excluded:
            self.excluded.add(repository_id)
        else:
            self.excluded.discard(repository_id)

    def write_receipt(self, receipt, *, replay_expires_at) -> None:
        del replay_expires_at
        self.receipts[receipt.request_id.value] = receipt

    def write_reestablishment_context(
        self,
        context,
        *,
        source_observation_ids=(),
        discovery_observation_ids=(),
    ) -> None:
        del context, source_observation_ids, discovery_observation_ids


class FunctionalPyramidServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.declarations = _Declarations()
        self.state = _State()
        self.runtime_stores: dict[str, mock.Mock] = {}
        self.runtimes: dict[str, mock.Mock] = {}
        for repository_id in ("repo-a", "repo-b"):
            store = mock.Mock()
            store.retention = self.state.retention
            store.require_repository.return_value = f"/repos/{repository_id}"
            store.list_understandings.return_value = ()
            store.support_dependents.return_value = ()
            store.load_authority_bindings.return_value = ()
            evidence = mock.Mock()
            evidence.read_exact.return_value = mock.Mock()
            self.runtime_stores[repository_id] = store
            self.runtimes[repository_id] = mock.Mock(
                repository_id=repository_id,
                root=f"/repos/{repository_id}",
                store=store,
                evidence=evidence,
            )

        self.service = FunctionalPyramidService(
            declarations=self.declarations,
            authority=_Authority(),
        )
        self.admin_service = FunctionalPyramidService(
            declarations=self.declarations,
            authority=_Authority(),
            state=self.state,
            registered_repository_ids=lambda: ("repo-a", "repo-b"),
            repository_paths=lambda repository_ids: tuple(
                (repository_id, f"/stores/{repository_id}.db")
                for repository_id in sorted(repository_ids)
            ),
            repository_runtime=lambda repository_id: self.runtimes[repository_id],
            clock=lambda: datetime.datetime(
                2026, 11, 21, 0, 0, tzinfo=datetime.timezone.utc
            ),
        )

    def _install_v3(
        self,
        repository_id: str,
        *,
        local_scope: str | None = None,
        locator: str = "decl.json",
    ) -> m.FunctionalPyramidMemberIntent:
        declarations = _declaration(repository_id, local_scope=local_scope)
        requests = [m.EvidenceRequest(locator)]
        self.declarations.results[(repository_id, locator)] = (
            _ref(repository_id, locator),
            declarations[0],
            (),
        )
        if len(declarations) > 1:
            area_locator = f"{locator}.area"
            self.declarations.results[(repository_id, area_locator)] = (
                _ref(repository_id, area_locator),
                declarations[1],
                (),
            )
            requests.append(m.EvidenceRequest(area_locator))
        bindings = [
            _binding(repository_id, "docs/foundation.md"),
        ]
        if local_scope is not None:
            bindings.append(_binding(repository_id, "docs/design.md"))
        self.runtime_stores[repository_id].load_authority_bindings.return_value = tuple(
            bindings
        )
        return m.FunctionalPyramidMemberIntent(
            repository_id=repository_id,
            declaration_sources=tuple(requests),
        )

    def _active_member(
        self, repository_id: str, locator: str = "decl.json"
    ) -> m.FunctionalPyramidMemberView:
        return m.FunctionalPyramidMemberView(
            repository_id=repository_id,
            declaration_refs=(_ref(repository_id, locator),),
        )

    def test_optional_bootstrap_absence_does_not_imply_exclusion(self) -> None:
        self.assertIsNone(self.service.discover_bootstrap("repo-a"))

    def test_ranged_candidate_source_is_validation_only(self) -> None:
        intent = m.FunctionalPyramidMemberIntent(
            repository_id="repo-a",
            declaration_sources=(
                m.EvidenceRequest(
                    "decl.json",
                    ranges=(m.SourceRange(1, 3),),
                ),
            ),
        )
        members, declarations, available, validation, graph = (
            self.service.load_candidate_members((intent,))
        )
        self.assertEqual(self.declarations.calls, [])
        self.assertEqual(members, ())
        self.assertEqual(declarations, ())
        self.assertEqual(available, frozenset({"repo-a"}))
        self.assertEqual(
            {item.reason for item in validation},
            {m.FunctionalPyramidValidationReason.INVALID_DECLARATION_SOURCE},
        )
        self.assertEqual(graph, ())

    def test_candidate_v1_source_is_validation_error_only(self) -> None:
        self.declarations.results[("repo-a", "decl.json")] = (
            FunctionalPyramidDeclarationInvalid("unsupported", unsupported_version=1)
        )
        candidate = self.admin_service.candidate(
            m.FunctionalPyramidCandidateSelector(
                action=m.FunctionalPyramidAction.ACTIVATE,
                members=(
                    m.FunctionalPyramidMemberIntent(
                        repository_id="repo-a",
                        declaration_sources=(m.EvidenceRequest("decl.json"),),
                    ),
                ),
            )
        )
        self.assertFalse(candidate.activation_ready)
        self.assertEqual(
            {item.reason for item in candidate.validation_findings},
            {m.FunctionalPyramidPublicReason.DECLARATION_INVALID},
        )
        self.assertEqual(candidate.graph_findings, ())

    def test_recoverable_bad_scope_is_graph_only(self) -> None:
        finding = m.FunctionalPyramidFinding(
            reason=m.FunctionalPyramidFindingReason.INVALID_PLACEMENT_SCOPE,
            repository_id="repo-a",
            declaration_locator="decl.json",
            detail="bad scope",
            recovery="declare canonical scope",
        )
        self.declarations.results[("repo-a", "decl.json")] = (
            _ref("repo-a", "decl.json"),
            _declaration("repo-a")[0],
            (finding,),
        )
        self.runtime_stores["repo-a"].load_authority_bindings.return_value = (
            _binding("repo-a", "docs/foundation.md"),
        )
        candidate = self.admin_service.candidate(
            m.FunctionalPyramidCandidateSelector(
                action=m.FunctionalPyramidAction.ACTIVATE,
                members=(
                    m.FunctionalPyramidMemberIntent(
                        repository_id="repo-a",
                        declaration_sources=(m.EvidenceRequest("decl.json"),),
                    ),
                ),
            )
        )
        self.assertFalse(candidate.activation_ready)
        self.assertEqual(candidate.validation_findings, ())
        self.assertEqual(
            {item.reason for item in candidate.graph_findings},
            {m.FunctionalPyramidPublicReason.DECLARATION_INVALID},
        )

    def test_repository_unavailability_is_graph_state(self) -> None:
        self.declarations.results[("repo-a", "decl.json")] = (
            FunctionalPyramidRepositoryUnavailable("offline")
        )
        candidate = self.admin_service.candidate(
            m.FunctionalPyramidCandidateSelector(
                action=m.FunctionalPyramidAction.ACTIVATE,
                members=(
                    m.FunctionalPyramidMemberIntent(
                        repository_id="repo-a",
                        declaration_sources=(m.EvidenceRequest("decl.json"),),
                    ),
                ),
            )
        )
        self.assertEqual(candidate.validation_findings, ())
        self.assertIn(
            m.FunctionalPyramidPublicReason.GOVERNANCE_UNAVAILABLE,
            {item.reason for item in candidate.graph_findings},
        )

    def test_valid_candidate_is_pure_and_ready(self) -> None:
        intent = self._install_v3("repo-a")
        candidate = self.admin_service.candidate(
            m.FunctionalPyramidCandidateSelector(
                action=m.FunctionalPyramidAction.ACTIVATE,
                members=(intent,),
            )
        )
        self.assertTrue(candidate.activation_ready)
        self.assertEqual(candidate.validation_findings, ())
        self.assertEqual(candidate.graph_findings, ())
        self.assertEqual(self.state.active, {})
        self.assertEqual(self.state.versions, {})
        self.assertEqual(self.state.receipts, {})

    def test_status_keeps_active_v1_instance_active_but_degraded(self) -> None:
        pyramid_id = m.FunctionalPyramidId("fp-v1")
        version = m.FunctionalPyramidVersion(1)
        member = self._active_member("repo-a")
        self.state.active["repo-a"] = pyramid_id
        self.state.versions[pyramid_id] = version
        self.state.members[(pyramid_id, version)] = (member,)
        self.declarations.results[("repo-a", "decl.json")] = (
            FunctionalPyramidDeclarationInvalid("unsupported", unsupported_version=1)
        )

        status = self.admin_service.status(
            m.FunctionalPyramidSelector(repository_id="repo-a")
        )

        self.assertEqual(status.state, m.FunctionalPyramidParticipationState.ACTIVE)
        self.assertEqual(status.health, m.FunctionalPyramidHealth.DEGRADED)
        self.assertIn(
            m.FunctionalPyramidPublicReason.DECLARATION_INVALID,
            {finding.reason for finding in status.findings},
        )

    def test_candidate_v2_source_is_validation_error_only(self) -> None:
        self.declarations.results[("repo-a", "decl.json")] = (
            FunctionalPyramidDeclarationInvalid("unsupported", unsupported_version=2)
        )
        candidate = self.admin_service.candidate(
            m.FunctionalPyramidCandidateSelector(
                action=m.FunctionalPyramidAction.ACTIVATE,
                members=(
                    m.FunctionalPyramidMemberIntent(
                        repository_id="repo-a",
                        declaration_sources=(m.EvidenceRequest("decl.json"),),
                    ),
                ),
            )
        )
        self.assertFalse(candidate.activation_ready)
        self.assertEqual(
            {item.reason for item in candidate.validation_findings},
            {m.FunctionalPyramidPublicReason.DECLARATION_INVALID},
        )
        self.assertEqual(candidate.graph_findings, ())

    def test_status_keeps_active_v2_instance_active_but_degraded(self) -> None:
        pyramid_id = m.FunctionalPyramidId("fp-v2")
        version = m.FunctionalPyramidVersion(1)
        member = self._active_member("repo-a")
        self.state.active["repo-a"] = pyramid_id
        self.state.versions[pyramid_id] = version
        self.state.members[(pyramid_id, version)] = (member,)
        self.declarations.results[("repo-a", "decl.json")] = (
            FunctionalPyramidDeclarationInvalid("unsupported", unsupported_version=2)
        )

        status = self.admin_service.status(
            m.FunctionalPyramidSelector(repository_id="repo-a")
        )

        self.assertEqual(status.state, m.FunctionalPyramidParticipationState.ACTIVE)
        self.assertEqual(status.health, m.FunctionalPyramidHealth.DEGRADED)
        self.assertIn(
            m.FunctionalPyramidPublicReason.DECLARATION_INVALID,
            {finding.reason for finding in status.findings},
        )

    def test_status_projects_unconfigured_excluded_and_rejects_unknown(self) -> None:
        self.assertEqual(
            self.admin_service.status(
                m.FunctionalPyramidSelector(repository_id="repo-a")
            ),
            m.FunctionalPyramidStatus(
                state=m.FunctionalPyramidParticipationState.UNCONFIGURED
            ),
        )
        self.state.excluded.add("repo-a")
        self.assertEqual(
            self.admin_service.status(
                m.FunctionalPyramidSelector(repository_id="repo-a")
            ),
            m.FunctionalPyramidStatus(
                state=m.FunctionalPyramidParticipationState.EXCLUDED
            ),
        )
        with self.assertRaises(RecordingValidationError):
            self.admin_service.status(
                m.FunctionalPyramidSelector(repository_id="unknown")
            )

    def test_directory_lookup_rejects_non_directory(self) -> None:
        result = self.admin_service.record(
            request_id=m.RequestId("activate-dir"),
            action=m.FunctionalPyramidAction.ACTIVATE,
            members=(self._install_v3("repo-a", local_scope="src/service"),),
        )
        assert result.pyramid_id is not None
        with self.assertRaises(RecordingValidationError):
            self.admin_service.directory(
                m.FunctionalPyramidDirectorySelector(
                    repository_id="repo-a",
                    directory="not-a-directory",
                )
            )

    def test_directory_lookup_returns_document_placements(self) -> None:
        self.admin_service.record(
            request_id=m.RequestId("activate-dir-view"),
            action=m.FunctionalPyramidAction.ACTIVATE,
            members=(self._install_v3("repo-a", local_scope="src/service"),),
        )
        view = self.admin_service.directory(
            m.FunctionalPyramidDirectorySelector(
                repository_id="repo-a",
                directory="src/service",
            )
        )
        self.assertIsInstance(view, m.FunctionalPyramidView)
        assert isinstance(view, m.FunctionalPyramidView)
        self.assertEqual(
            tuple(placement.document.document_ref for placement in view.placements),
            ("docs/foundation.md", "docs/design.md"),
        )

    def test_directory_continuation_recovers_every_placement(self) -> None:
        intent = self._install_v3("repo-a")
        ref, declaration, _ = self.declarations.results[("repo-a", "decl.json")]
        root = declaration.placements[0].placement
        extra = tuple(
            _placement("repo-a", f"docs/rule-{i:03d}.md", m.FunctionalPyramidLayer.P1, ".")
            for i in range(20)
        )
        declaration = dataclasses.replace(
            declaration,
            documents=declaration.documents + tuple(item.document.identity for item in extra),
            placements=declaration.placements + tuple(
                m.FunctionalDocumentDeclaration(placement=item, governing_placements=(root,))
                for item in extra
            ),
        )
        self.declarations.results[("repo-a", "decl.json")] = (ref, declaration, ())
        store = self.runtime_stores["repo-a"]
        store.load_authority_bindings.return_value += tuple(
            _binding("repo-a", item.document.document_ref) for item in extra
        )
        self.admin_service.record(
            request_id=m.RequestId("paged-activation"),
            action=m.FunctionalPyramidAction.ACTIVATE,
            members=(intent,),
        )
        selector = m.FunctionalPyramidDirectorySelector("repo-a", ".")
        full = self.admin_service.directory(selector)
        assert isinstance(full, m.FunctionalPyramidView)
        self.assertEqual(len(full.placements), 21)
        self.admin_service._policy = dataclasses.replace(
            DEFAULT_SERVICE_BOUNDS_POLICY, max_response_bytes=2500
        )
        collected = []
        first = self.admin_service.directory(selector)
        assert isinstance(first, m.FunctionalPyramidView)
        self.assertTrue(first.truncated)
        self.assertIsNotNone(first.next_after)
        current = first
        while True:
            self.assertLessEqual(encoded_size(current), 2500)
            self.assertEqual(current.unresolved, full.unresolved)
            collected.extend(current.placements)
            if current.next_after is None:
                break
            current = self.admin_service.directory(dataclasses.replace(selector, after=current.next_after))
            assert isinstance(current, m.FunctionalPyramidView)
        self.assertEqual(tuple(collected), full.placements)
        with self.assertRaises(StaleContinuationError):
            self.admin_service.directory(m.FunctionalPyramidDirectorySelector("repo-a", "src", first.next_after))

    def test_duplicate_unregistered_and_other_active_members_accumulate(self) -> None:
        intent = self._install_v3("repo-a")
        unknown = m.FunctionalPyramidMemberIntent(
            repository_id="repo-x",
            declaration_sources=(m.EvidenceRequest("decl.json"),),
        )
        self.state.active["repo-a"] = m.FunctionalPyramidId("other")
        candidate = self.admin_service.candidate(
            m.FunctionalPyramidCandidateSelector(
                action=m.FunctionalPyramidAction.ACTIVATE,
                members=(intent, intent, unknown),
            )
        )
        self.assertEqual(
            {finding.reason for finding in candidate.validation_findings},
            {
                m.FunctionalPyramidPublicReason.DUPLICATE_MEMBER,
                m.FunctionalPyramidPublicReason.UNREGISTERED_MEMBER,
                m.FunctionalPyramidPublicReason.MEMBER_ALREADY_ACTIVE,
            },
        )

    def test_revision_candidate_reports_unknown_and_stale_target(self) -> None:
        intent = self._install_v3("repo-a")
        unknown = self.admin_service.candidate(
            m.FunctionalPyramidCandidateSelector(
                action=m.FunctionalPyramidAction.REVISE,
                members=(intent,),
                pyramid_id=m.FunctionalPyramidId("missing"),
                expected_version=m.FunctionalPyramidVersion(1),
            )
        )
        self.assertIn(
            m.FunctionalPyramidPublicReason.UNKNOWN_PYRAMID,
            {finding.reason for finding in unknown.validation_findings},
        )

        pyramid_id = m.FunctionalPyramidId("fp-1")
        self.state.versions[pyramid_id] = m.FunctionalPyramidVersion(2)
        self.state.active["repo-a"] = pyramid_id
        stale = self.admin_service.candidate(
            m.FunctionalPyramidCandidateSelector(
                action=m.FunctionalPyramidAction.REVISE,
                members=(intent,),
                pyramid_id=pyramid_id,
                expected_version=m.FunctionalPyramidVersion(1),
            )
        )
        finding = next(
            item
            for item in stale.validation_findings
            if item.reason is m.FunctionalPyramidPublicReason.STALE_PYRAMID_VERSION
        )
        self.assertEqual(finding.current_version, m.FunctionalPyramidVersion(2))

    def test_invalid_activation_is_atomic(self) -> None:
        intent = self._install_v3("repo-a")
        self.declarations.results[("repo-a", "decl.json")] = m.EvidenceSourceFailure(
            request=m.EvidenceRequest("decl.json"),
            kind=m.EvidenceSourceFailureKind.MISSING,
            reason="missing",
        )
        with self.assertRaises(ValueError):
            self.admin_service.record(
                request_id=m.RequestId("activate-invalid"),
                action=m.FunctionalPyramidAction.ACTIVATE,
                members=(intent,),
            )
        self.assertEqual(self.state.active, {})
        self.assertEqual(self.state.versions, {})
        self.assertIsNone(self.state.receipt(m.RequestId("activate-invalid")))

    def test_activation_commits_members_effects_and_receipt(self) -> None:
        result = self.admin_service.record(
            request_id=m.RequestId("activate-1"),
            action=m.FunctionalPyramidAction.ACTIVATE,
            members=(self._install_v3("repo-a"), self._install_v3("repo-b")),
        )
        self.assertEqual(result.pyramid_id, m.FunctionalPyramidId("fp:activate-1"))
        self.assertEqual(result.version, m.FunctionalPyramidVersion(1))
        self.assertEqual(
            tuple(effect.repository_id for effect in result.participation_effects),
            ("repo-a", "repo-b"),
        )
        self.assertIsNotNone(self.state.receipt(m.RequestId("activate-1")))
        self.assertEqual(
            self.state.transaction_paths[-1],
            (("repo-a", "/stores/repo-a.db"), ("repo-b", "/stores/repo-b.db")),
        )

    def test_activation_replay_is_idempotent_and_conflict_is_rejected(self) -> None:
        intent = self._install_v3("repo-a")
        first = self.admin_service.record(
            request_id=m.RequestId("activate-replay"),
            action=m.FunctionalPyramidAction.ACTIVATE,
            members=(intent,),
        )
        replay = self.admin_service.record(
            request_id=m.RequestId("activate-replay"),
            action=m.FunctionalPyramidAction.ACTIVATE,
            members=(intent,),
        )
        self.assertEqual(replay.receipt_selector, first.receipt_selector)
        self.assertEqual(replay.committed_at, first.committed_at)

        other_intent = self._install_v3("repo-b")
        with self.assertRaises(RecordingConflict):
            self.admin_service.record(
                request_id=m.RequestId("activate-replay"),
                action=m.FunctionalPyramidAction.ACTIVATE,
                members=(other_intent,),
            )

    def test_revision_compare_and_set_and_deactivate(self) -> None:
        first = self.admin_service.record(
            request_id=m.RequestId("activate-revise"),
            action=m.FunctionalPyramidAction.ACTIVATE,
            members=(self._install_v3("repo-a"),),
        )
        assert first.pyramid_id is not None
        assert first.version is not None
        revised = self.admin_service.record(
            request_id=m.RequestId("revise-1"),
            action=m.FunctionalPyramidAction.REVISE,
            pyramid_id=first.pyramid_id,
            expected_version=first.version,
            members=(
                self._install_v3("repo-a", local_scope="src"),
                self._install_v3("repo-b"),
            ),
        )
        self.assertEqual(revised.version, m.FunctionalPyramidVersion(2))
        with self.assertRaises(ValueError):
            self.admin_service.record(
                request_id=m.RequestId("revise-stale"),
                action=m.FunctionalPyramidAction.REVISE,
                pyramid_id=first.pyramid_id,
                expected_version=m.FunctionalPyramidVersion(1),
                members=(self._install_v3("repo-a"),),
            )
        deactivated = self.admin_service.record(
            request_id=m.RequestId("deactivate-1"),
            action=m.FunctionalPyramidAction.DEACTIVATE,
            pyramid_id=first.pyramid_id,
            expected_version=m.FunctionalPyramidVersion(2),
        )
        self.assertTrue(
            all(
                effect.state is m.FunctionalPyramidParticipationState.EXCLUDED
                for effect in deactivated.participation_effects
            )
        )
        self.assertIn("repo-a", self.state.excluded)
        self.assertIn("repo-b", self.state.excluded)

    def test_exclude_is_explicit_nonparticipation(self) -> None:
        result = self.admin_service.record(
            request_id=m.RequestId("exclude-1"),
            action=m.FunctionalPyramidAction.EXCLUDE,
            repository_id="repo-a",
        )
        self.assertIn("repo-a", self.state.excluded)
        self.assertEqual(
            result.participation_effects,
            (
                m.FunctionalPyramidParticipationEffect(
                    repository_id="repo-a",
                    state=m.FunctionalPyramidParticipationState.EXCLUDED,
                ),
            ),
        )


if __name__ == "__main__":
    unittest.main()
