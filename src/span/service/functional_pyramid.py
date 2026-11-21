"""Functional Pyramid declaration and resolution orchestration."""

from __future__ import annotations

import datetime as _datetime
import typing as _typing

from span.core import functional_pyramid as _fp
from span.core import model as m
from span.core.identity import functional_pyramid_identity, payload_digest
from span.core.recording import RecordingConflict, receipt_content_decision
from span.core.rejection import RejectionCauseKind
from span.ports.functional_pyramid import (
    FunctionalPyramidDeclarationInvalid,
    FunctionalPyramidDeclarationPort,
    FunctionalPyramidRepositoryUnavailable,
    FunctionalPyramidStatePort,
    FunctionalPyramidStateTransaction,
)
from span.ports.lifecycle import LifecycleAuthorityResolver

_DeclarationEntry = tuple[str, m.FunctionalPyramidDeclaration]
_AuthorityMap = dict[tuple[str, str], m.AuthorityBinding]

_EffectProjection = _typing.Callable[
    [
        FunctionalPyramidStateTransaction,
        m.FunctionalPyramidAction,
        m.FunctionalPyramidId,
        tuple[m.FunctionalPyramidMemberView, ...],
        tuple[m.FunctionalPyramidMemberView, ...],
    ],
    tuple[
        tuple[m.ChangedSurface, ...],
        tuple[m.InvestigationContextRef, ...],
        tuple[m.ConclusionRevisionRef, ...],
    ],
]
_RetainedEffectProjection = _typing.Callable[
    [
        FunctionalPyramidStateTransaction,
        tuple[m.ConclusionRevisionRef, ...],
    ],
    tuple[
        tuple[m.ChangedSurface, ...],
        tuple[m.InvestigationContextRef, ...],
    ],
]
_RepositoryPaths = _typing.Callable[
    [tuple[str, ...]],
    tuple[tuple[str, str], ...],
]


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
        effect_projection: _EffectProjection | None = None,
        retained_effect_projection: _RetainedEffectProjection | None = None,
        clock: _typing.Callable[[], _datetime.datetime] | None = None,
    ) -> None:
        self._declarations = declarations
        self._authority = authority
        self._state = state
        self._registered_repository_ids = registered_repository_ids
        self._repository_paths = repository_paths
        self._effect_projection = effect_projection
        self._retained_effect_projection = retained_effect_projection
        self._clock = clock or (lambda: _datetime.datetime.now(_datetime.timezone.utc))

    def _require_state(self) -> FunctionalPyramidStatePort:
        if self._state is None:
            raise ValueError("Functional Pyramid state service is not configured")
        return self._state

    def _registered(self) -> frozenset[str]:
        if self._registered_repository_ids is None:
            raise ValueError("Functional Pyramid repository registry is not configured")
        return frozenset(self._registered_repository_ids())

    def status(
        self, selector: m.FunctionalPyramidSelector
    ) -> m.FunctionalPyramidStatus:
        """Project exact durable participation plus live ACTIVE health (FD-83)."""
        state = self._require_state()
        pyramid_id = selector.pyramid_id
        if selector.repository_id is not None:
            pyramid_id = state.active_pyramid_id(selector.repository_id)
            if pyramid_id is None:
                participation = (
                    m.FunctionalPyramidParticipationState.EXCLUDED
                    if state.is_excluded(selector.repository_id)
                    else m.FunctionalPyramidParticipationState.UNCONFIGURED
                )
                return m.FunctionalPyramidStatus(state=participation)

        assert pyramid_id is not None
        version = state.pyramid_version(pyramid_id)
        if version is None:
            return m.FunctionalPyramidStatus(
                state=m.FunctionalPyramidParticipationState.UNCONFIGURED
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
        registered = self._registered()
        validation: list[m.FunctionalPyramidValidationFinding] = []

        intents_by_repository: dict[str, m.FunctionalPyramidMemberIntent] = {}
        duplicate_repositories: set[str] = set()
        for intent in selector.members:
            if intent.repository_id in intents_by_repository:
                duplicate_repositories.add(intent.repository_id)
                continue
            intents_by_repository[intent.repository_id] = intent

        for repository_id in sorted(duplicate_repositories):
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
            current = state.pyramid_version(target_id)
            if current is None:
                validation.append(
                    _validation_finding(
                        m.FunctionalPyramidValidationReason.UNKNOWN_PYRAMID,
                        None,
                        "target Functional Pyramid is not ACTIVE",
                        "obtain current Functional Pyramid status before revising",
                        pyramid_id=target_id,
                    )
                )
            else:
                target_version = current
                if current != selector.expected_version:
                    validation.append(
                        _validation_finding(
                            m.FunctionalPyramidValidationReason.STALE_PYRAMID_VERSION,
                            None,
                            "target Functional Pyramid version is stale",
                            "obtain current status and rebuild the revision candidate",
                            pyramid_id=target_id,
                            expected_version=selector.expected_version,
                            current_version=current,
                        )
                    )

        eligible: list[m.FunctionalPyramidMemberIntent] = []
        for repository_id in sorted(intents_by_repository):
            intent = intents_by_repository[repository_id]
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
            retained_target = target_id is not None and active_id == target_id
            if active_id is not None and not retained_target:
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

        lifecycle_blockers = {
            m.FunctionalPyramidValidationReason.UNREGISTERED_MEMBER,
            m.FunctionalPyramidValidationReason.DUPLICATE_MEMBER,
            m.FunctionalPyramidValidationReason.MEMBER_ALREADY_ACTIVE,
            m.FunctionalPyramidValidationReason.UNKNOWN_PYRAMID,
            m.FunctionalPyramidValidationReason.STALE_PYRAMID_VERSION,
        }
        if any(item.reason in lifecycle_blockers for item in validation):
            ordered_validation = tuple(
                sorted(
                    validation,
                    key=lambda item: (
                        item.reason.value,
                        item.repository_id or "",
                        item.declaration_locator or "",
                        "" if item.pyramid_id is None else item.pyramid_id.value,
                    ),
                )
            )
            return m.FunctionalPyramidCandidate(
                action=selector.action,
                pyramid_id=target_id,
                version=target_version,
                members=(),
                activation_ready=False,
                validation_findings=ordered_validation,
                graph_findings=(),
            )

        members, declarations, available, source_validation, source_graph = (
            self.load_candidate_members(tuple(eligible))
        )
        validation.extend(source_validation)
        authorities, authority_findings = self._authority_bindings(
            members, declarations, available
        )
        del authorities
        health, structural = _fp.evaluate_functional_pyramid_health(
            members,
            declarations,
            available,
            source_graph + authority_findings,
        )
        del health

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
                continue
            graph.append(finding)

        ordered_validation = tuple(
            sorted(
                validation,
                key=lambda item: (
                    item.reason.value,
                    item.repository_id or "",
                    item.declaration_locator or "",
                    "" if item.pyramid_id is None else item.pyramid_id.value,
                ),
            )
        )
        return m.FunctionalPyramidCandidate(
            action=selector.action,
            pyramid_id=target_id,
            version=target_version,
            members=members,
            activation_ready=not ordered_validation and not graph,
            validation_findings=ordered_validation,
            graph_findings=tuple(graph),
        )

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

    def _project_receipt(
        self,
        transaction: FunctionalPyramidStateTransaction,
        receipt: m.RetrievedFunctionalPyramidReceipt,
    ) -> m.FunctionalPyramidRecorded:
        if not receipt.dependent_effect_refs:
            return self._recorded(receipt, (), ())
        if self._retained_effect_projection is None:
            raise ValueError(
                "Functional Pyramid retained effect projection is not configured"
            )
        surfaces, contexts = self._retained_effect_projection(
            transaction,
            receipt.dependent_effect_refs,
        )
        return self._recorded(receipt, surfaces, contexts)

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
        if self._effect_projection is None:
            raise ValueError("Functional Pyramid effect projection is not configured")
        return self._effect_projection(
            transaction,
            action,
            pyramid_id,
            old_members,
            new_members,
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
