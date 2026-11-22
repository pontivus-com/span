"""Functional Pyramid declaration and resolution orchestration."""

from __future__ import annotations

import datetime as _datetime
import typing as _typing

from span.core import containment
from span.core import functional_pyramid as _fp
from span.core import model as m
from span.core import support_rules as _support_rules
from span.core.identity import functional_pyramid_identity, payload_digest
from span.core.recording import (
    RecordingConflict,
    RecordingValidationError,
    receipt_content_decision,
)
from span.core.rejection import RejectionCauseKind
from span.ports.functional_pyramid import (
    FunctionalPyramidDeclarationInvalid,
    FunctionalPyramidDeclarationPort,
    FunctionalPyramidRepositoryRuntime,
    FunctionalPyramidRepositoryUnavailable,
    FunctionalPyramidStatePort,
    FunctionalPyramidStateTransaction,
)
from span.ports.lifecycle import LifecycleAuthorityResolver
from span.service.contexts import ContextBinding, build_context
from span.service.effects import DependencyEffectService
from span.service.ids import server_context_id
from span.service.support import SupportService

_DeclarationEntry = tuple[str, m.FunctionalPyramidDeclaration]
_AuthorityMap = dict[tuple[str, str], m.AuthorityBinding]

_RepositoryPaths = _typing.Callable[
    [tuple[str, ...]],
    tuple[tuple[str, str], ...],
]


def _ordered_validation_findings(
    findings: list[m.FunctionalPyramidValidationFinding],
) -> tuple[m.FunctionalPyramidValidationFinding, ...]:
    return tuple(
        sorted(
            findings,
            key=lambda item: (
                item.reason.value,
                item.repository_id or "",
                item.declaration_locator or "",
                "" if item.pyramid_id is None else item.pyramid_id.value,
            ),
        )
    )


def _validation_finding(
    reason: m.FunctionalPyramidValidationReason,
    repository_id: str | None,
    detail: str,
    recovery: str,
    *,
    pyramid_id: m.FunctionalPyramidId | None = None,
    declaration_locator: str | None = None,
    expected_version: m.FunctionalPyramidVersion | None = None,
    current_version: m.FunctionalPyramidVersion | None = None,
) -> m.FunctionalPyramidValidationFinding:
    return m.FunctionalPyramidValidationFinding(
        reason=reason,
        repository_id=repository_id,
        pyramid_id=pyramid_id,
        declaration_locator=declaration_locator,
        expected_version=expected_version,
        current_version=current_version,
        detail=detail,
        recovery=recovery,
    )


def _graph_finding(
    reason: m.FunctionalPyramidFindingReason,
    repository_id: str,
    detail: str,
    recovery: str,
    *,
    declaration_locator: str | None = None,
    rule_id: str | None = None,
) -> m.FunctionalPyramidFinding:
    return m.FunctionalPyramidFinding(
        reason=reason,
        repository_id=repository_id,
        declaration_locator=declaration_locator,
        rule_id=rule_id,
        detail=detail,
        recovery=recovery,
    )


class FunctionalPyramidService:
    """Compose exact source loading, authority binding and pure graph rules."""

    def __init__(
        self,
        *,
        declarations: FunctionalPyramidDeclarationPort,
        authority: LifecycleAuthorityResolver,
        state: FunctionalPyramidStatePort | None = None,
        registered_repository_ids: _typing.Callable[[], tuple[str, ...]] | None = None,
        repository_paths: _RepositoryPaths | None = None,
        repository_runtime: (
            _typing.Callable[[str], FunctionalPyramidRepositoryRuntime] | None
        ) = None,
        clock: _typing.Callable[[], _datetime.datetime] | None = None,
        new_context_id: _typing.Callable[[], str] | None = None,
    ) -> None:
        self._declarations = declarations
        self._authority = authority
        self._state = state
        self._registered_repository_ids = registered_repository_ids
        self._repository_paths = repository_paths
        self._repository_runtime = repository_runtime
        self._clock = clock or (lambda: _datetime.datetime.now(_datetime.timezone.utc))
        self._new_context_id = new_context_id or server_context_id

    def _require_state(self) -> FunctionalPyramidStatePort:
        if self._state is None:
            raise ValueError("Functional Pyramid state service is not configured")
        return self._state

    def _registered(self) -> frozenset[str]:
        if self._registered_repository_ids is None:
            raise ValueError("Functional Pyramid repository registry is not configured")
        return frozenset(self._registered_repository_ids())

    def registered_repository_ids(self) -> tuple[str, ...]:
        """Return the exact installation registry used by Functional Pyramid state."""
        return tuple(sorted(self._registered()))

    def _runtime(self, repository_id: str) -> FunctionalPyramidRepositoryRuntime:
        if self._repository_runtime is None:
            raise RuntimeError(
                "Functional Pyramid repository runtime is not configured"
            )
        return self._repository_runtime(repository_id)

    def _support_for_repository(self, repository_id: str) -> SupportService:
        runtime = self._runtime(repository_id)
        return SupportService(
            store=runtime.store,
            evidence=runtime.evidence,
            authority=runtime.store,
            functional_route_resolver=self.support_route,
            repository_runtime=self._runtime,
        )

    def status(
        self, selector: m.FunctionalPyramidSelector
    ) -> m.FunctionalPyramidStatus:
        """Project exact durable participation plus live ACTIVE health (FD-83)."""
        state = self._require_state()
        pyramid_id = selector.pyramid_id
        if selector.repository_id is not None:
            repository_id = selector.repository_id
            if repository_id not in self._registered():
                raise RecordingValidationError(
                    f"unknown repository: {repository_id!r}",
                    public_identity=repository_id,
                    public_cause=(
                        f"the exact repository {repository_id!r} is not registered"
                    ),
                )
            pyramid_id = state.active_pyramid_id(repository_id)
            if pyramid_id is None:
                participation = (
                    m.FunctionalPyramidParticipationState.EXCLUDED
                    if state.is_excluded(repository_id)
                    else m.FunctionalPyramidParticipationState.UNCONFIGURED
                )
                return m.FunctionalPyramidStatus(state=participation)

        assert pyramid_id is not None
        version = state.pyramid_version(pyramid_id)
        if version is None:
            identity = pyramid_id.value
            raise RecordingValidationError(
                f"unknown Functional Pyramid: {identity!r}",
                public_identity=identity,
                public_cause=(
                    f"the exact Functional Pyramid {identity!r} is not ACTIVE"
                ),
            )
        members = state.pyramid_members(pyramid_id, version)
        health, findings = self.health(members)
        return m.FunctionalPyramidStatus(
            state=m.FunctionalPyramidParticipationState.ACTIVE,
            health=health,
            pyramid_id=pyramid_id,
            version=version,
            members=members,
            findings=findings,
        )

    def route(
        self,
        repository_id: str,
        surface: m.SurfaceKey,
        semantic_scope: m.EvidenceScope,
    ) -> (
        m.FunctionalPyramidParticipation
        | m.FunctionalPyramidUnavailable
        | tuple[m.FunctionalPyramidView, m.FunctionalRouteIdentity]
    ):
        """Resolve the current repository route through the installation state."""
        try:
            status = self.status(
                m.FunctionalPyramidSelector(repository_id=repository_id)
            )
            if status.state is not m.FunctionalPyramidParticipationState.ACTIVE:
                return m.FunctionalPyramidParticipation(status.state)
            assert status.pyramid_id is not None
            assert status.version is not None
            return self.resolve(
                pyramid_id=status.pyramid_id,
                version=status.version,
                members=status.members,
                surface=surface,
                semantic_scope=semantic_scope,
            )
        except (OSError, FunctionalPyramidRepositoryUnavailable):
            return m.FunctionalPyramidUnavailable(
                failure="Functional Pyramid governance cannot be evaluated",
                recovery="restore the registered member repository and retry",
            )

    def orientation(
        self,
        repository_id: str,
        surface: m.SurfaceKey,
        semantic_scope: m.EvidenceScope,
    ) -> (
        m.FunctionalPyramidParticipation
        | m.FunctionalPyramidView
        | m.FunctionalPyramidUnavailable
    ):
        """Project ordinary ask orientation from the same route owner."""
        current = self.route(repository_id, surface, semantic_scope)
        if isinstance(current, tuple):
            return current[0]
        return current

    def support_route(
        self,
        dependency: m.FunctionalRouteSupport,
        surface: m.SurfaceKey,
    ) -> tuple[
        m.FunctionalPyramidParticipation
        | m.FunctionalPyramidView
        | m.FunctionalPyramidUnavailable,
        m.FunctionalRouteIdentity | None,
    ]:
        """Resolve one retained FunctionalRouteSupport against current state."""
        current = self.route(
            dependency.repository_id,
            surface,
            dependency.semantic_scope,
        )
        if isinstance(current, tuple):
            view, route_identity = current
            return view, route_identity
        return current, None

    def changed_route_identities(
        self,
        repository_id: str,
        changed_paths: tuple[str, ...],
        changed_surfaces: tuple[m.SurfaceKey, ...],
    ) -> tuple[m.FunctionalRouteIdentity, ...]:
        """Return recorded routes whose governing declaration change is now non-current."""
        changed = list(changed_paths)
        for surface in changed_surfaces:
            if surface.kind is m.SurfaceKind.FILE:
                changed.append(surface.locator)
            elif surface.kind is m.SurfaceKind.SYMBOL:
                owner = containment.surface_file_locator(surface.locator)
                if owner is not None:
                    changed.append(owner)
        changed_scope = m.EvidenceScope(paths=tuple(dict.fromkeys(changed)))
        if not changed_scope.paths:
            return ()

        impacted: set[m.FunctionalRouteIdentity] = set()
        for owner_repository_id in sorted(self._registered()):
            store = self._runtime(owner_repository_id).store
            for understanding in store.list_understandings(owner_repository_id):
                version = store.get_version(
                    understanding.understanding_id.value,
                    understanding.current_version.value,
                )
                revisions = {
                    (revision.conclusion_id, revision.revision): revision
                    for revision in store.get_conclusions(
                        understanding.understanding_id.value
                    )
                }
                for ref in version.conclusions:
                    revision = revisions.get((ref.conclusion_id, ref.revision))
                    if revision is None or not isinstance(
                        revision.content, m.SupportedConclusion
                    ):
                        continue
                    for dependency in revision.content.support:
                        if not isinstance(dependency, m.FunctionalRouteSupport):
                            continue
                        members = self._require_state().pyramid_members(
                            dependency.pyramid_id
                        )
                        changed_member = next(
                            (
                                member
                                for member in members
                                if member.repository_id == repository_id
                            ),
                            None,
                        )
                        if changed_member is None or not any(
                            m.evidence_scope_allows(ref.locator, changed_scope)
                            for ref in changed_member.declaration_refs
                        ):
                            continue
                        current, route_identity = self.support_route(
                            dependency, understanding.surface
                        )
                        evaluation = _support_rules.functional_route_state(
                            recorded=dependency,
                            current=current,
                            current_route_identity=route_identity,
                            observed_at=self._clock(),
                        )
                        if evaluation.state is not m.SupportState.CURRENT:
                            impacted.add(dependency.route_identity)
        return tuple(sorted(impacted, key=lambda item: item.value))

    def candidate(
        self, selector: m.FunctionalPyramidCandidateSelector
    ) -> m.FunctionalPyramidCandidate:
        """Pure action-aware candidate validation (FD-84)."""
        return self._candidate(selector, self._require_state())

    def _candidate(
        self,
        selector: m.FunctionalPyramidCandidateSelector,
        state: FunctionalPyramidStatePort | FunctionalPyramidStateTransaction,
    ) -> m.FunctionalPyramidCandidate:
        (
            target_id,
            target_version,
            eligible,
            validation,
        ) = self._candidate_lifecycle(selector, state)
        if not eligible:
            return m.FunctionalPyramidCandidate(
                action=selector.action,
                pyramid_id=target_id,
                version=target_version,
                members=(),
                activation_ready=False,
                validation_findings=_ordered_validation_findings(validation),
                graph_findings=(),
            )

        members, declarations, available, source_validation, source_graph = (
            self.load_candidate_members(eligible)
        )
        validation.extend(source_validation)
        _, authority_findings = self._authority_bindings(
            members, declarations, available
        )
        _, structural = _fp.evaluate_functional_pyramid_health(
            members,
            declarations,
            available,
            source_graph + authority_findings,
        )

        graph: list[m.FunctionalPyramidFinding] = []
        for finding in structural:
            if finding.reason is m.FunctionalPyramidFindingReason.UNCOVERED_PATH:
                validation.append(
                    _validation_finding(
                        m.FunctionalPyramidValidationReason.INCOMPLETE_COMPLETE_COVERAGE,
                        finding.repository_id,
                        finding.detail,
                        finding.recovery,
                    )
                )
            else:
                graph.append(finding)

        ordered_validation = _ordered_validation_findings(validation)
        return m.FunctionalPyramidCandidate(
            action=selector.action,
            pyramid_id=target_id,
            version=target_version,
            members=members,
            activation_ready=not ordered_validation and not graph,
            validation_findings=ordered_validation,
            graph_findings=tuple(graph),
        )

    def _candidate_lifecycle(
        self,
        selector: m.FunctionalPyramidCandidateSelector,
        state: FunctionalPyramidStatePort | FunctionalPyramidStateTransaction,
    ) -> tuple[
        m.FunctionalPyramidId | None,
        m.FunctionalPyramidVersion | None,
        tuple[m.FunctionalPyramidMemberIntent, ...],
        list[m.FunctionalPyramidValidationFinding],
    ]:
        registered = self._registered()
        validation: list[m.FunctionalPyramidValidationFinding] = []
        intents: dict[str, m.FunctionalPyramidMemberIntent] = {}
        duplicates: set[str] = set()
        for intent in selector.members:
            if intent.repository_id in intents:
                duplicates.add(intent.repository_id)
            else:
                intents[intent.repository_id] = intent

        for repository_id in sorted(duplicates):
            validation.append(
                _validation_finding(
                    m.FunctionalPyramidValidationReason.DUPLICATE_MEMBER,
                    repository_id,
                    "candidate contains the same repository more than once",
                    "retain exactly one member intent for the repository",
                )
            )

        target_id = selector.pyramid_id
        target_version: m.FunctionalPyramidVersion | None = None
        if selector.action is m.FunctionalPyramidAction.REVISE:
            assert target_id is not None
            assert selector.expected_version is not None
            target_version = state.pyramid_version(target_id)
            if target_version is None:
                validation.append(
                    _validation_finding(
                        m.FunctionalPyramidValidationReason.UNKNOWN_PYRAMID,
                        None,
                        "target Functional Pyramid is not ACTIVE",
                        "obtain current Functional Pyramid status before revising",
                        pyramid_id=target_id,
                    )
                )
            elif target_version != selector.expected_version:
                validation.append(
                    _validation_finding(
                        m.FunctionalPyramidValidationReason.STALE_PYRAMID_VERSION,
                        None,
                        "target Functional Pyramid version is stale",
                        "obtain current status and rebuild the revision candidate",
                        pyramid_id=target_id,
                        expected_version=selector.expected_version,
                        current_version=target_version,
                    )
                )

        eligible: list[m.FunctionalPyramidMemberIntent] = []
        for repository_id in sorted(intents):
            intent = intents[repository_id]
            if repository_id not in registered:
                validation.append(
                    _validation_finding(
                        m.FunctionalPyramidValidationReason.UNREGISTERED_MEMBER,
                        repository_id,
                        "candidate repository is not registered with Span",
                        "register the repository before Functional Pyramid validation",
                    )
                )
                continue
            active_id = state.active_pyramid_id(repository_id)
            if active_id is not None and active_id != target_id:
                validation.append(
                    _validation_finding(
                        m.FunctionalPyramidValidationReason.MEMBER_ALREADY_ACTIVE,
                        repository_id,
                        "repository already belongs to another ACTIVE Functional Pyramid",
                        "revise/deactivate the current instance before reassigning it",
                        pyramid_id=active_id,
                    )
                )
                continue
            eligible.append(intent)

        return target_id, target_version, tuple(eligible), validation

    def receipt(
        self, selector: m.FunctionalPyramidReceiptSelector
    ) -> m.RetrievedFunctionalPyramidReceipt | None:
        """Retrieve one immutable installation-scoped Functional Pyramid receipt."""
        return self._require_state().receipt(selector.request_id)

    def record(
        self,
        *,
        request_id: m.RequestId,
        action: m.FunctionalPyramidAction,
        members: tuple[m.FunctionalPyramidMemberIntent, ...] = (),
        pyramid_id: m.FunctionalPyramidId | None = None,
        expected_version: m.FunctionalPyramidVersion | None = None,
        repository_id: str | None = None,
    ) -> m.FunctionalPyramidRecorded:
        """Accept/replay one installation-scoped participation write (FD-85/FD-93)."""
        state = self._require_state()
        self._validate_record_shape(
            action=action,
            members=members,
            pyramid_id=pyramid_id,
            expected_version=expected_version,
            repository_id=repository_id,
        )
        digest = self._record_digest(
            action=action,
            members=members,
            pyramid_id=pyramid_id,
            expected_version=expected_version,
            repository_id=repository_id,
        )
        existing = state.receipt(request_id)
        decision = receipt_content_decision(
            None if existing is None else existing.content_digest,
            digest,
        )
        if decision is m.ReceiptDecisionKind.REPLAY:
            assert existing is not None
            return self._replay_record(existing)
        if decision is m.ReceiptDecisionKind.CONFLICT:
            raise RecordingConflict(
                "this Functional Pyramid request identity already committed different content",
                cause_kind=RejectionCauseKind.REPLAY_CONFLICT,
            )

        if action is m.FunctionalPyramidAction.EXCLUDE:
            assert repository_id is not None
            return self._record_exclude(
                request_id=request_id,
                digest=digest,
                repository_id=repository_id,
            )

        if action is m.FunctionalPyramidAction.ACTIVATE:
            repository_ids = tuple(sorted({item.repository_id for item in members}))
        else:
            assert pyramid_id is not None
            current_members = state.pyramid_members(pyramid_id)
            repository_ids = tuple(
                sorted(
                    {item.repository_id for item in current_members}
                    | {item.repository_id for item in members}
                )
            )
        repository_paths = self._attached_paths(repository_ids)
        with state.transaction(repository_paths) as transaction:
            replay = transaction.receipt(request_id)
            transaction_decision = receipt_content_decision(
                None if replay is None else replay.content_digest,
                digest,
            )
            if transaction_decision is m.ReceiptDecisionKind.REPLAY:
                assert replay is not None
                return self._project_receipt(transaction, replay)
            if transaction_decision is m.ReceiptDecisionKind.CONFLICT:
                raise RecordingConflict(
                    "this Functional Pyramid request identity already committed different content",
                    cause_kind=RejectionCauseKind.REPLAY_CONFLICT,
                )
            if action in (
                m.FunctionalPyramidAction.ACTIVATE,
                m.FunctionalPyramidAction.REVISE,
            ):
                return self._record_active(
                    transaction=transaction,
                    request_id=request_id,
                    digest=digest,
                    action=action,
                    members=members,
                    pyramid_id=pyramid_id,
                    expected_version=expected_version,
                )
            assert action is m.FunctionalPyramidAction.DEACTIVATE
            assert pyramid_id is not None
            assert expected_version is not None
            return self._record_deactivate(
                transaction=transaction,
                request_id=request_id,
                digest=digest,
                pyramid_id=pyramid_id,
                expected_version=expected_version,
            )

    @staticmethod
    def _validate_record_shape(
        *,
        action: m.FunctionalPyramidAction,
        members: tuple[m.FunctionalPyramidMemberIntent, ...],
        pyramid_id: m.FunctionalPyramidId | None,
        expected_version: m.FunctionalPyramidVersion | None,
        repository_id: str | None,
    ) -> None:
        if action is m.FunctionalPyramidAction.ACTIVATE:
            if not members or any(
                value is not None
                for value in (pyramid_id, expected_version, repository_id)
            ):
                raise ValueError(
                    "activate requires members and no pyramid/version/repository selector"
                )
            return
        if action is m.FunctionalPyramidAction.REVISE:
            if (
                not members
                or pyramid_id is None
                or expected_version is None
                or repository_id is not None
            ):
                raise ValueError(
                    "revise requires members, pyramid_id and expected_version"
                )
            return
        if action is m.FunctionalPyramidAction.DEACTIVATE:
            if (
                members
                or pyramid_id is None
                or expected_version is None
                or repository_id is not None
            ):
                raise ValueError(
                    "deactivate requires pyramid_id and expected_version only"
                )
            return
        if action is m.FunctionalPyramidAction.EXCLUDE:
            if (
                members
                or pyramid_id is not None
                or expected_version is not None
                or repository_id is None
                or not repository_id
            ):
                raise ValueError("exclude requires repository_id only")
            return
        raise ValueError(f"unsupported Functional Pyramid action: {action!r}")

    @staticmethod
    def _record_digest(
        *,
        action: m.FunctionalPyramidAction,
        members: tuple[m.FunctionalPyramidMemberIntent, ...],
        pyramid_id: m.FunctionalPyramidId | None,
        expected_version: m.FunctionalPyramidVersion | None,
        repository_id: str | None,
    ) -> m.ContentDigest:
        return payload_digest(
            {
                "action": action.value,
                "members": [m.to_canonical(item) for item in members],
                "pyramid_id": None if pyramid_id is None else pyramid_id.value,
                "expected_version": (
                    None if expected_version is None else expected_version.value
                ),
                "repository_id": repository_id,
            }
        )

    def _attached_paths(
        self, repository_ids: tuple[str, ...]
    ) -> tuple[tuple[str, str], ...]:
        if not repository_ids:
            return ()
        if self._repository_paths is None:
            raise ValueError("Functional Pyramid repository paths are not configured")
        paths = self._repository_paths(repository_ids)
        if tuple(repository_id for repository_id, _ in paths) != tuple(
            sorted(repository_ids)
        ):
            raise ValueError(
                "Functional Pyramid repository paths must cover repositories in sorted order"
            )
        return paths

    def _record_active(
        self,
        *,
        transaction: FunctionalPyramidStateTransaction,
        request_id: m.RequestId,
        digest: m.ContentDigest,
        action: m.FunctionalPyramidAction,
        members: tuple[m.FunctionalPyramidMemberIntent, ...],
        pyramid_id: m.FunctionalPyramidId | None,
        expected_version: m.FunctionalPyramidVersion | None,
    ) -> m.FunctionalPyramidRecorded:
        selector = m.FunctionalPyramidCandidateSelector(
            action=action,
            members=members,
            pyramid_id=pyramid_id,
            expected_version=expected_version,
        )
        candidate = self._candidate(selector, transaction)
        stale = next(
            (
                finding
                for finding in candidate.validation_findings
                if finding.reason
                is m.FunctionalPyramidValidationReason.STALE_PYRAMID_VERSION
            ),
            None,
        )
        if stale is not None:
            observed = (
                None if stale.current_version is None else stale.current_version.value
            )
            raise RecordingConflict(
                "Functional Pyramid version changed before write commit",
                cause_kind=RejectionCauseKind.VERSION_CONFLICT,
                current_version=observed,
            )
        if not candidate.activation_ready:
            reasons = tuple(
                item.reason.value for item in candidate.validation_findings
            ) + tuple(item.reason.value for item in candidate.graph_findings)
            raise ValueError(
                "Functional Pyramid candidate is not activation-ready: "
                + ", ".join(reasons)
            )

        old_members: tuple[m.FunctionalPyramidMemberView, ...] = ()
        if action is m.FunctionalPyramidAction.ACTIVATE:
            selected_id = functional_pyramid_identity(request_id)
            version = m.FunctionalPyramidVersion(1)
        else:
            assert pyramid_id is not None
            assert expected_version is not None
            current = transaction.pyramid_version(pyramid_id)
            if current != expected_version:
                observed = None if current is None else current.value
                raise RecordingConflict(
                    "Functional Pyramid version changed before revision commit: "
                    f"expected {expected_version.value}, observed {observed}",
                    cause_kind=RejectionCauseKind.VERSION_CONFLICT,
                    current_version=observed,
                )
            old_members = transaction.pyramid_members(pyramid_id, current)
            selected_id = pyramid_id
            version = m.FunctionalPyramidVersion(expected_version.value + 1)

        effects = self._participation_effects(
            action=action,
            old_members=old_members,
            new_members=candidate.members,
        )
        dependent, contexts, refs = self._change_effects(
            transaction,
            action,
            selected_id,
            old_members,
            candidate.members,
        )
        now = self._clock()
        transaction.write_pyramid_version(
            pyramid_id=selected_id,
            version=version,
            content_digest=digest,
            committed_at=now,
            members=candidate.members,
        )
        transaction.set_current_pyramid(
            pyramid_id=selected_id,
            version=version,
            members=candidate.members,
        )
        receipt = m.RetrievedFunctionalPyramidReceipt(
            request_id=request_id,
            content_digest=digest,
            committed_at=now,
            action=action,
            pyramid_id=selected_id,
            version=version,
            members=candidate.members,
            participation_effects=effects,
            dependent_effect_refs=refs,
        )
        transaction.write_receipt(
            receipt,
            replay_expires_at=now + self._require_state().retention.replay_retention,
        )
        return self._recorded(receipt, dependent, contexts)

    def _record_deactivate(
        self,
        *,
        transaction: FunctionalPyramidStateTransaction,
        request_id: m.RequestId,
        digest: m.ContentDigest,
        pyramid_id: m.FunctionalPyramidId,
        expected_version: m.FunctionalPyramidVersion,
    ) -> m.FunctionalPyramidRecorded:
        current = transaction.pyramid_version(pyramid_id)
        if current != expected_version:
            observed = None if current is None else current.value
            raise RecordingConflict(
                "Functional Pyramid version changed before deactivation commit: "
                f"expected {expected_version.value}, observed {observed}",
                cause_kind=RejectionCauseKind.VERSION_CONFLICT,
                current_version=observed,
            )
        old_members = transaction.pyramid_members(pyramid_id, current)
        if not old_members:
            raise ValueError("cannot deactivate an unknown Functional Pyramid")
        dependent, contexts, refs = self._change_effects(
            transaction,
            m.FunctionalPyramidAction.DEACTIVATE,
            pyramid_id,
            old_members,
            (),
        )
        effects = tuple(
            m.FunctionalPyramidParticipationEffect(
                repository_id=member.repository_id,
                state=m.FunctionalPyramidParticipationState.EXCLUDED,
            )
            for member in sorted(old_members, key=lambda item: item.repository_id)
        )
        transaction.clear_current_pyramid(pyramid_id)
        for member in old_members:
            transaction.set_excluded(member.repository_id, True)
        now = self._clock()
        receipt = m.RetrievedFunctionalPyramidReceipt(
            request_id=request_id,
            content_digest=digest,
            committed_at=now,
            action=m.FunctionalPyramidAction.DEACTIVATE,
            pyramid_id=pyramid_id,
            version=current,
            members=(),
            participation_effects=effects,
            dependent_effect_refs=refs,
        )
        transaction.write_receipt(
            receipt,
            replay_expires_at=now + self._require_state().retention.replay_retention,
        )
        return self._recorded(receipt, dependent, contexts)

    def _record_exclude(
        self,
        *,
        request_id: m.RequestId,
        digest: m.ContentDigest,
        repository_id: str,
    ) -> m.FunctionalPyramidRecorded:
        if repository_id not in self._registered():
            raise ValueError("cannot exclude an unregistered repository")
        state = self._require_state()
        with state.transaction() as transaction:
            replay = transaction.receipt(request_id)
            decision = receipt_content_decision(
                None if replay is None else replay.content_digest,
                digest,
            )
            if decision is m.ReceiptDecisionKind.REPLAY:
                assert replay is not None
                return self._recorded(replay, (), ())
            if decision is m.ReceiptDecisionKind.CONFLICT:
                raise RecordingConflict(
                    "this Functional Pyramid request identity already committed different content",
                    cause_kind=RejectionCauseKind.REPLAY_CONFLICT,
                )
            if transaction.active_pyramid_id(repository_id) is not None:
                raise ValueError("ACTIVE repository cannot be excluded")
            changed = not transaction.is_excluded(repository_id)
            transaction.set_excluded(repository_id, True)
            effects = (
                (
                    m.FunctionalPyramidParticipationEffect(
                        repository_id=repository_id,
                        state=m.FunctionalPyramidParticipationState.EXCLUDED,
                    ),
                )
                if changed
                else ()
            )
            now = self._clock()
            receipt = m.RetrievedFunctionalPyramidReceipt(
                request_id=request_id,
                content_digest=digest,
                committed_at=now,
                action=m.FunctionalPyramidAction.EXCLUDE,
                pyramid_id=None,
                version=None,
                members=(),
                participation_effects=effects,
                dependent_effect_refs=(),
            )
            transaction.write_receipt(
                receipt,
                replay_expires_at=now
                + self._require_state().retention.replay_retention,
            )
            return self._recorded(receipt, (), ())

    def _replay_record(
        self, receipt: m.RetrievedFunctionalPyramidReceipt
    ) -> m.FunctionalPyramidRecorded:
        repository_ids = tuple(
            sorted(
                {member.repository_id for member in receipt.members}
                | {effect.repository_id for effect in receipt.participation_effects}
            )
        )
        paths = self._attached_paths(repository_ids) if repository_ids else ()
        with self._require_state().transaction(paths) as transaction:
            return self._project_receipt(transaction, receipt)

    def _effect_service(
        self,
        transaction: FunctionalPyramidStateTransaction,
    ) -> DependencyEffectService:
        def issue(
            repository_id: str,
            context_id: str,
            binding: ContextBinding,
            source_observation_ids: tuple[str, ...],
            discovery_observation_ids: tuple[str, ...],
        ) -> m.InvestigationContextRef:
            runtime = self._runtime(repository_id)
            context = build_context(
                retention=runtime.store.retention,
                binding=binding,
                repository_id=repository_id,
                request_id=m.RequestId(f"effects:{context_id}"),
                clock=self._clock,
                new_context_id=lambda: context_id,
            )
            transaction.write_reestablishment_context(
                context,
                source_observation_ids=source_observation_ids,
                discovery_observation_ids=discovery_observation_ids,
            )
            return m.InvestigationContextRef(
                repository_id=repository_id,
                context_id=context.context_id,
            )

        return DependencyEffectService(
            repository_runtime=self._runtime,
            registered_repository_ids=lambda: tuple(sorted(self._registered())),
            support_for_repository=self._support_for_repository,
            functional_route_impacts=self.changed_route_identities,
            clock=self._clock,
            new_context_id=self._new_context_id,
            context_issuer=issue,
        )

    def _project_receipt(
        self,
        transaction: FunctionalPyramidStateTransaction,
        receipt: m.RetrievedFunctionalPyramidReceipt,
    ) -> m.FunctionalPyramidRecorded:
        if not receipt.dependent_effect_refs:
            return self._recorded(receipt, (), ())
        surfaces, contexts = self._effect_service(
            transaction
        ).retained_functional_pyramid_effects(receipt.dependent_effect_refs)
        return self._recorded(receipt, surfaces, contexts)

    def _proposed_changed_route_identities(
        self,
        *,
        pyramid_id: m.FunctionalPyramidId,
        proposed_version: m.FunctionalPyramidVersion,
        old_members: tuple[m.FunctionalPyramidMemberView, ...],
        new_members: tuple[m.FunctionalPyramidMemberView, ...],
    ) -> tuple[m.FunctionalRouteIdentity, ...]:
        retained = {member.repository_id for member in old_members} & {
            member.repository_id for member in new_members
        }
        changed: set[m.FunctionalRouteIdentity] = set()
        for repository_id in sorted(retained):
            store = self._runtime(repository_id).store
            for understanding in store.list_understandings(repository_id):
                version = store.get_version(
                    understanding.understanding_id.value,
                    understanding.current_version.value,
                )
                revisions = {
                    (revision.conclusion_id, revision.revision): revision
                    for revision in store.get_conclusions(
                        understanding.understanding_id.value
                    )
                }
                for ref in version.conclusions:
                    revision = revisions.get((ref.conclusion_id, ref.revision))
                    if revision is None or not isinstance(
                        revision.content, m.SupportedConclusion
                    ):
                        continue
                    for dependency in revision.content.support:
                        if (
                            not isinstance(dependency, m.FunctionalRouteSupport)
                            or dependency.pyramid_id != pyramid_id
                        ):
                            continue
                        try:
                            view, identity = self.resolve(
                                pyramid_id=pyramid_id,
                                version=proposed_version,
                                members=new_members,
                                surface=understanding.surface,
                                semantic_scope=dependency.semantic_scope,
                            )
                        except (OSError, ValueError):
                            changed.add(dependency.route_identity)
                            continue
                        if (
                            view.status is not m.FunctionalPyramidRouteStatus.RESOLVED
                            or identity != dependency.route_identity
                        ):
                            changed.add(dependency.route_identity)
        return tuple(sorted(changed, key=lambda item: item.value))

    def _change_effects(
        self,
        transaction: FunctionalPyramidStateTransaction,
        action: m.FunctionalPyramidAction,
        pyramid_id: m.FunctionalPyramidId,
        old_members: tuple[m.FunctionalPyramidMemberView, ...],
        new_members: tuple[m.FunctionalPyramidMemberView, ...],
    ) -> tuple[
        tuple[m.ChangedSurface, ...],
        tuple[m.InvestigationContextRef, ...],
        tuple[m.ConclusionRevisionRef, ...],
    ]:
        old = {member.repository_id for member in old_members}
        new = {member.repository_id for member in new_members}
        route_ids: tuple[m.FunctionalRouteIdentity, ...] = ()
        if action is m.FunctionalPyramidAction.REVISE:
            current = transaction.pyramid_version(pyramid_id)
            if current is None:
                raise ValueError("Functional Pyramid version is unavailable")
            route_ids = self._proposed_changed_route_identities(
                pyramid_id=pyramid_id,
                proposed_version=m.FunctionalPyramidVersion(current.value + 1),
                old_members=old_members,
                new_members=new_members,
            )
        return self._effect_service(transaction).functional_pyramid_change(
            changed_route_identities=route_ids,
            newly_active_repositories=tuple(sorted(new - old)),
            deliberately_inactive_repositories=tuple(sorted(old - new)),
        )

    @staticmethod
    def _participation_effects(
        *,
        action: m.FunctionalPyramidAction,
        old_members: tuple[m.FunctionalPyramidMemberView, ...],
        new_members: tuple[m.FunctionalPyramidMemberView, ...],
    ) -> tuple[m.FunctionalPyramidParticipationEffect, ...]:
        old = {item.repository_id for item in old_members}
        new = {item.repository_id for item in new_members}
        effects: list[m.FunctionalPyramidParticipationEffect] = []
        if action is m.FunctionalPyramidAction.ACTIVATE:
            changed = sorted(new)
            target = m.FunctionalPyramidParticipationState.ACTIVE
            return tuple(
                m.FunctionalPyramidParticipationEffect(repository_id=item, state=target)
                for item in changed
            )
        if action is m.FunctionalPyramidAction.REVISE:
            for repository_id in sorted(new - old):
                effects.append(
                    m.FunctionalPyramidParticipationEffect(
                        repository_id=repository_id,
                        state=m.FunctionalPyramidParticipationState.ACTIVE,
                    )
                )
            for repository_id in sorted(old - new):
                effects.append(
                    m.FunctionalPyramidParticipationEffect(
                        repository_id=repository_id,
                        state=m.FunctionalPyramidParticipationState.UNCONFIGURED,
                    )
                )
        return tuple(effects)

    @staticmethod
    def _recorded(
        receipt: m.RetrievedFunctionalPyramidReceipt,
        dependent_effects: tuple[m.ChangedSurface, ...],
        contexts: tuple[m.InvestigationContextRef, ...],
    ) -> m.FunctionalPyramidRecorded:
        return m.FunctionalPyramidRecorded(
            receipt_selector=m.FunctionalPyramidReceiptSelector(receipt.request_id),
            committed_at=receipt.committed_at,
            action=receipt.action,
            pyramid_id=receipt.pyramid_id,
            version=receipt.version,
            members=receipt.members,
            participation_effects=receipt.participation_effects,
            dependent_effects=dependent_effects,
            reestablishment_contexts=contexts,
        )

    def discover_bootstrap(
        self, repository_id: str
    ) -> tuple[m.EvidenceRef, m.FunctionalPyramidBootstrap] | None:
        """Read only the conventional optional bootstrap."""
        return self._declarations.read_bootstrap(repository_id)

    def _load_requests(
        self,
        repository_id: str,
        requests: tuple[m.EvidenceRequest, ...],
    ) -> tuple[
        tuple[m.EvidenceRef, ...],
        tuple[_DeclarationEntry, ...],
        bool,
        tuple[m.FunctionalPyramidValidationFinding, ...],
        tuple[m.FunctionalPyramidFinding, ...],
    ]:
        refs: list[m.EvidenceRef] = []
        declarations: list[_DeclarationEntry] = []
        validation: list[m.FunctionalPyramidValidationFinding] = []
        graph: list[m.FunctionalPyramidFinding] = []
        available = True

        for request in requests:
            if request.ranges:
                validation.append(
                    _validation_finding(
                        m.FunctionalPyramidValidationReason.INVALID_DECLARATION_SOURCE,
                        repository_id,
                        "Functional Pyramid declaration source is ranged",
                        "select the complete declaration document",
                        declaration_locator=request.locator,
                    )
                )
                graph.append(
                    _graph_finding(
                        m.FunctionalPyramidFindingReason.INVALID_DECLARATION,
                        repository_id,
                        "Functional Pyramid declaration source is ranged",
                        "select the complete declaration document",
                        declaration_locator=request.locator,
                    )
                )
                continue

            try:
                result = self._declarations.read_declaration(repository_id, request)
            except FunctionalPyramidRepositoryUnavailable:
                available = False
                graph.append(
                    _graph_finding(
                        m.FunctionalPyramidFindingReason.REPOSITORY_UNAVAILABLE,
                        repository_id,
                        "Functional Pyramid member repository is unavailable",
                        "restore the registered member repository",
                        declaration_locator=request.locator,
                    )
                )
                break
            except FunctionalPyramidDeclarationInvalid:
                validation.append(
                    _validation_finding(
                        m.FunctionalPyramidValidationReason.INVALID_DECLARATION_SOURCE,
                        repository_id,
                        "Functional Pyramid declaration violates the Version-1 contract",
                        "correct the named declaration document",
                        declaration_locator=request.locator,
                    )
                )
                graph.append(
                    _graph_finding(
                        m.FunctionalPyramidFindingReason.INVALID_DECLARATION,
                        repository_id,
                        "Functional Pyramid declaration violates the Version-1 contract",
                        "correct the named declaration document",
                        declaration_locator=request.locator,
                    )
                )
                continue

            if isinstance(result, m.EvidenceSourceFailure):
                reason = (
                    m.FunctionalPyramidValidationReason.MISSING_DECLARATION_SOURCE
                    if result.kind is m.EvidenceSourceFailureKind.MISSING
                    else m.FunctionalPyramidValidationReason.INVALID_DECLARATION_SOURCE
                )
                validation.append(
                    _validation_finding(
                        reason,
                        repository_id,
                        "Functional Pyramid declaration source cannot be loaded",
                        "restore or correct the named declaration document",
                        declaration_locator=request.locator,
                    )
                )
                graph.append(
                    _graph_finding(
                        m.FunctionalPyramidFindingReason.INVALID_DECLARATION,
                        repository_id,
                        "Functional Pyramid declaration source cannot be loaded",
                        "restore or correct the named declaration document",
                        declaration_locator=request.locator,
                    )
                )
                continue

            evidence_ref, declaration = result
            refs.append(evidence_ref)
            declarations.append((repository_id, declaration))

        return (
            tuple(refs),
            tuple(declarations),
            available,
            tuple(validation),
            tuple(graph),
        )

    def load_candidate_members(
        self, intents: tuple[m.FunctionalPyramidMemberIntent, ...]
    ) -> tuple[
        tuple[m.FunctionalPyramidMemberView, ...],
        tuple[_DeclarationEntry, ...],
        frozenset[str],
        tuple[m.FunctionalPyramidValidationFinding, ...],
        tuple[m.FunctionalPyramidFinding, ...],
    ]:
        """Resolve candidate source requests without changing participation."""
        members: list[m.FunctionalPyramidMemberView] = []
        declarations: list[_DeclarationEntry] = []
        available: set[str] = set()
        validation: list[m.FunctionalPyramidValidationFinding] = []
        graph: list[m.FunctionalPyramidFinding] = []

        for intent in intents:
            refs, loaded, is_available, source_validation, source_graph = (
                self._load_requests(intent.repository_id, intent.declaration_sources)
            )
            if is_available:
                available.add(intent.repository_id)
            validation.extend(source_validation)
            graph.extend(source_graph)
            declarations.extend(loaded)
            if refs:
                members.append(
                    m.FunctionalPyramidMemberView(
                        repository_id=intent.repository_id,
                        declaration_refs=refs,
                        functional_scope=intent.functional_scope,
                        coverage=intent.coverage,
                    )
                )

        return (
            tuple(members),
            tuple(declarations),
            frozenset(available),
            tuple(validation),
            tuple(graph),
        )

    def _load_active_members(
        self, members: tuple[m.FunctionalPyramidMemberView, ...]
    ) -> tuple[
        tuple[m.FunctionalPyramidMemberView, ...],
        tuple[_DeclarationEntry, ...],
        frozenset[str],
        tuple[m.FunctionalPyramidFinding, ...],
    ]:
        current_members: list[m.FunctionalPyramidMemberView] = []
        declarations: list[_DeclarationEntry] = []
        available: set[str] = set()
        graph: list[m.FunctionalPyramidFinding] = []

        for member in members:
            requests = tuple(
                m.EvidenceRequest(ref.locator) for ref in member.declaration_refs
            )
            refs, loaded, is_available, _, source_graph = self._load_requests(
                member.repository_id, requests
            )
            if is_available:
                available.add(member.repository_id)
            graph.extend(source_graph)
            declarations.extend(loaded)
            current_members.append(
                m.FunctionalPyramidMemberView(
                    repository_id=member.repository_id,
                    declaration_refs=refs or member.declaration_refs,
                    functional_scope=member.functional_scope,
                    coverage=member.coverage,
                )
            )

        return (
            tuple(current_members),
            tuple(declarations),
            frozenset(available),
            tuple(graph),
        )

    def _authority_bindings(
        self,
        members: tuple[m.FunctionalPyramidMemberView, ...],
        declarations: tuple[_DeclarationEntry, ...],
        available: frozenset[str],
    ) -> tuple[_AuthorityMap, tuple[m.FunctionalPyramidFinding, ...]]:
        member_repositories = frozenset(member.repository_id for member in members)
        bindings: _AuthorityMap = {}
        findings: list[m.FunctionalPyramidFinding] = []

        for _, declaration in declarations:
            for rule in declaration.rules:
                owner = rule.owner
                if owner.repository_id not in member_repositories:
                    findings.append(
                        _graph_finding(
                            m.FunctionalPyramidFindingReason.INVALID_DECLARATION,
                            owner.repository_id,
                            "functional rule owner repository is outside the active pyramid",
                            "move the authority owner into the instance or correct the rule owner",
                            rule_id=rule.rule_id,
                        )
                    )
                    continue
                if owner.repository_id not in available:
                    findings.append(
                        _graph_finding(
                            m.FunctionalPyramidFindingReason.REPOSITORY_UNAVAILABLE,
                            owner.repository_id,
                            "functional rule authority owner repository is unavailable",
                            "restore the named member repository",
                            rule_id=rule.rule_id,
                        )
                    )
                    continue
                key = (owner.repository_id, owner.authority_ref)
                if key in bindings:
                    continue
                try:
                    bindings[key] = self._authority.resolve_authority(*key)
                except ValueError:
                    findings.append(
                        _graph_finding(
                            m.FunctionalPyramidFindingReason.INVALID_DECLARATION,
                            owner.repository_id,
                            "functional rule owner is not a declared authority binding",
                            "declare the canonical authority binding or correct the owner reference",
                            rule_id=rule.rule_id,
                        )
                    )

        return bindings, tuple(findings)

    def resolve(
        self,
        *,
        pyramid_id: m.FunctionalPyramidId,
        version: m.FunctionalPyramidVersion,
        members: tuple[m.FunctionalPyramidMemberView, ...],
        surface: m.SurfaceKey,
        semantic_scope: m.EvidenceScope,
    ) -> tuple[m.FunctionalPyramidView, m.FunctionalRouteIdentity]:
        """Load current declarations and resolve one route."""
        current_members, declarations, available, source_findings = (
            self._load_active_members(members)
        )
        authorities, authority_findings = self._authority_bindings(
            current_members, declarations, available
        )
        return _fp.resolve_functional_pyramid_route(
            pyramid_id=pyramid_id,
            version=version,
            members=current_members,
            surface=surface,
            semantic_scope=semantic_scope,
            declarations=declarations,
            available_repositories=available,
            authority_bindings=authorities,
            declaration_findings=source_findings + authority_findings,
        )

    def health(
        self, members: tuple[m.FunctionalPyramidMemberView, ...]
    ) -> tuple[m.FunctionalPyramidHealth, tuple[m.FunctionalPyramidFinding, ...]]:
        """Evaluate live structural health from current declarations."""
        current_members, declarations, available, source_findings = (
            self._load_active_members(members)
        )
        _, authority_findings = self._authority_bindings(
            current_members, declarations, available
        )
        return _fp.evaluate_functional_pyramid_health(
            current_members,
            declarations,
            available,
            source_findings + authority_findings,
        )
