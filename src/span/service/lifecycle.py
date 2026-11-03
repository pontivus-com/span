"""Lifecycle service: server-issued contexts and reference-only recording.

The service is the single composition boundary between the canonical wire
projection and the lifecycle store. It issues repository-bound contexts,
resolves admitted references, validates admission preconditions, and
delegates the atomic acceptance decision to the store.

It owns no SQL, no semantic transition rule, and no duplicated carrier: the
wire types are decoded by ``span.core.schema.record_wire`` and the store
persists canonical model carriers.
"""

from __future__ import annotations

import dataclasses as _dataclasses
import datetime as _datetime
import typing as _typing

from span.core import model as m
from span.core import support_rules
from span.core.identity import (
    discovery_observation_identity,
    recording_key,
    understanding_identity,
)
from span.core.recording import (
    RecordingConflict,
    RecordingValidationError,
    receipt_decision,
)
from span.core.rejection import Rejection, RejectionCauseKind, SurfaceConflict
from span.core.schema import record_wire as _rw
from span.ports.lifecycle import LifecycleAuthorityResolver, LifecycleStorePort
from span.service.bounds import DEFAULT_SERVICE_BOUNDS_POLICY
from span.service.contexts import issue_context
from span.service.evidence import EvidenceService
from span.service.support import SupportService
from span.service.ids import server_context_id

__all__ = ["LifecycleService"]

_RecordWire = _typing.Union[
    _rw.RecordCreateWire,
    _rw.RecordAddWire,
    _rw.RecordConfirmWire,
    _rw.RecordCorrectWire,
    _rw.RecordReplaceWire,
    _rw.RecordWithdrawWire,
    _rw.RecordUpdateWire,
]


def _recording_identity(value: _rw.IdentityWire) -> m.RecordingIdentity:
    if value.context_id is None:
        raise RecordingValidationError(
            "recording requires an evidence context; supply context_id or "
            "locator/range source support"
        )
    return m.RecordingIdentity(
        repository_id=value.repository_id,
        request_id=m.RequestId(value.request_id),
        context_id=m.InvestigationContextId(value.context_id),
    )


def _cited_locators(value: object) -> tuple[str, ...]:
    """Every source locator a wire cites, in deterministic order."""
    found: list[str] = []
    if isinstance(value, _rw.SourceSupportWire):
        found.append(value.locator)
    elif _dataclasses.is_dataclass(value) and not isinstance(value, type):
        for field in _dataclasses.fields(value):
            found.extend(_cited_locators(getattr(value, field.name)))
    elif isinstance(value, (tuple, list)):
        for item in value:
            found.extend(_cited_locators(item))
    return tuple(sorted(set(found)))


def _record_wire_locators(value: object) -> tuple[str, ...]:
    """Every source locator cited by a record request's actions."""
    return _cited_locators(value)


class LifecycleService:
    """One repository-independent lifecycle service over one store."""

    def __init__(
        self,
        *,
        store: LifecycleStorePort,
        authority: LifecycleAuthorityResolver,
        support: SupportService,
        evidence: EvidenceService,
        clock: _typing.Callable[[], _datetime.datetime] | None = None,
        new_context_id: _typing.Callable[[], str] | None = None,
    ) -> None:
        self._store = store
        self._authority = authority
        self._support = support
        self._evidence = evidence
        self._clock = clock or (lambda: _datetime.datetime.now(_datetime.timezone.utc))
        self._new_context_id = new_context_id or server_context_id

    # -- context issuance --------------------------------------------------

    def start_context(self, request: m.StartContextRequest) -> m.InvestigationContext:
        """Issue or recover the one context bound to this request identity."""
        self._store.require_repository(request.repository_id)
        return issue_context(
            self._store,
            payload=request,
            repository_id=request.repository_id,
            request_id=request.request_id,
            scope=request.scope,
            question=request.question,
            clock=self._clock,
            new_context_id=self._new_context_id,
        )

    # -- recording ---------------------------------------------------------

    def record(self, wire: _rw.RecordRequestWire) -> m.RecordResult:
        """One public record entry dispatching on the request kind."""
        self._store.require_repository(wire.identity.repository_id)
        if wire.kind is m.RecordKind.SURFACE:
            return self._declare_surface(wire)
        if wire.kind is m.RecordKind.VERIFICATION:
            return self._record_verification_request(wire)
        return self._record_understanding_request(wire)

    def _declare_surface(self, wire: _rw.RecordRequestWire) -> m.SurfaceDeclared:
        surface = _rw.surface_declaration(wire)
        if surface.key.kind.is_declared:
            self._require_valid_parent(surface)
        try:
            if wire.action is m.SurfaceAction.CREATE:
                return m.SurfaceDeclared(
                    action="create", surface=self._store.put_surface(surface)
                )
            if not surface.key.kind.is_declared:
                raise RecordingValidationError(
                    "only a service or domain surface has a mutable boundary"
                )
            updated = self._store.update_surface(
                surface,
                expected_boundary_version=_typing.cast(
                    int, wire.expected_boundary_version
                ),
            )
            return m.SurfaceDeclared(action="update", surface=updated)
        except SurfaceConflict as exc:
            raise Rejection(
                exc.cause,
                cause_kind=RejectionCauseKind.SURFACE_CONFLICT,
                current_boundary_version=exc.current_boundary_version,
            ) from exc

    def _flat_conclusion(self, wire: _rw.RecordRequestWire) -> m.ProposedConclusion:
        """Build the one conclusion from the flat create fields."""
        if wire.conclusion is None:
            raise ValueError("a flat conclusion requires conclusion text")
        resolver = self._resolver(wire.identity)
        locator = wire.locator or (
            wire.scope_paths[0]
            if wire.scope_paths
            else (wire.surface.locator if wire.surface is not None else "")
        )
        default: m.SourceSupport | None = None
        if not wire.support:
            if wire.observation_id is not None:
                observation = self._store.get_source_observation(wire.observation_id)
                if observation.repository_id != wire.identity.repository_id:
                    raise RecordingValidationError(
                        "the observation belongs to another repository"
                    )
                locator = observation.evidence.locator
                default = m.SourceSupport(
                    observation_id=m.SourceObservationId(wire.observation_id)
                )
            elif wire.locator is not None:
                default = m.SourceSupport(
                    observation_id=resolver.source(wire.locator, ())
                )
        return _rw.flat_conclusion(
            wire, resolver, locator=locator, default_support=default
        )

    def _resolve_create_surface(
        self,
        wire: _rw.RecordRequestWire,
        context: m.InvestigationContext,
        context_bound: bool,
    ) -> m.SurfaceKey:
        """Resolve the create surface once: supplied, context, or scope.

        This is the single resolver for a create. It never guesses from a
        free-text name and never widens to a declared surface.
        """
        repository_id = wire.identity.repository_id
        if wire.surface is not None:
            surface = m.SurfaceKey(
                repository_id=repository_id,
                kind=m.SurfaceKind(wire.surface.kind),
                locator=wire.surface.locator,
            )
            self._require_surface_in_scope(surface, wire, context, context_bound)
            return surface
        paths = (
            context.scope.paths
            if context_bound and context.scope.paths
            else wire.scope_paths
        )
        surfaces = {
            m.SurfaceKey(
                repository_id=repository_id,
                kind=m.SurfaceKind.FILE,
                locator=path,
            )
            for path in paths
        }
        if len(surfaces) == 1:
            return next(iter(surfaces))
        if not surfaces:
            raise Rejection(
                "a create without a surface needs one scope_paths entry or a "
                "question context",
                cause_kind=RejectionCauseKind.SURFACE_REQUIRED,
            )
        ordered = sorted(item.locator for item in surfaces)
        shown = ", ".join(ordered[:4])
        more = f" (+{len(ordered) - 4} more)" if len(ordered) > 4 else ""
        raise Rejection(
            f"the carried scope names {len(ordered)} surfaces, but a create "
            f"records one conclusion per surface; declare a service/domain "
            f"surface, or pass one scope path. Named: {shown}{more}",
            cause_kind=RejectionCauseKind.SURFACE_AMBIGUOUS,
        )

    def _require_surface_in_scope(
        self,
        surface: m.SurfaceKey,
        wire: _rw.RecordRequestWire,
        context: m.InvestigationContext,
        context_bound: bool,
    ) -> None:
        if surface.kind is not m.SurfaceKind.FILE:
            return
        carried = set(context.scope.paths) if context_bound else set(wire.scope_paths)
        if carried and surface.locator not in carried:
            raise Rejection(
                f"surface {surface.locator!r} is not in the carried scope",
                cause_kind=RejectionCauseKind.SURFACE_MISMATCH,
            )

    def _require_valid_parent(self, surface: m.Surface) -> None:
        """Reject an unknown, undeclared, or cyclic parent for create and update."""
        parent = surface.parent
        seen: set[m.SurfaceKey] = set()
        while parent is not None:
            if parent == surface.key or parent in seen:
                raise RecordingValidationError(
                    "a surface parent chain cannot contain a cycle"
                )
            seen.add(parent)
            parent_surface = self._store.find_surface(parent)
            if parent_surface is None:
                raise RecordingValidationError(
                    f"unknown parent surface: {parent.locator}"
                )
            if not parent_surface.key.kind.is_declared:
                raise RecordingValidationError(
                    "a parent surface must be a declared service or domain"
                )
            parent = parent_surface.parent

    def _record_understanding_request(
        self, wire: _rw.RecordRequestWire
    ) -> m.RecordResult:
        wire = self._resolve_record_request(wire)
        digest = _rw.wire_content_digest(wire)
        replay = self._replay(
            wire.identity.repository_id, wire.identity.request_id, digest
        )
        if replay is not None:
            if replay.accepted_verification_run_ids:
                return self.qualify_verification(replay)
            return self.qualify_understanding(replay)
        context = self._store.get_context(_typing.cast(str, wire.identity.context_id))
        context_bound = context.origin is m.ContextOrigin.QUESTION
        create = wire.kind is m.RecordKind.UNDERSTANDING and wire.conclusion is not None
        if create and context_bound and (wire.question or wire.scope_paths):
            raise Rejection(
                "a question context binds the create target; omit question and "
                "scope_paths",
                cause_kind=RejectionCauseKind.CONTEXT_TARGET_CONFLICT,
            )
        derived = (
            self._resolve_create_surface(wire, context, context_bound)
            if create
            else None
        )
        derived_conclusions = (self._flat_conclusion(wire),) if create else None
        command = _rw.record_command(
            wire,
            self._resolver(wire.identity),
            context_bound=context_bound,
            derived_surface=derived,
            derived_conclusions=derived_conclusions,
        )
        if isinstance(command, m.CreateUnderstandingCommand):
            if command.surface.kind.is_declared:
                if self._store.find_surface(command.surface) is None:
                    raise RecordingValidationError(
                        "an understanding create against a declared surface "
                        "requires that surface to exist"
                    )
            self._require_admitted_support(command)
            self._support.assert_current(command)
            receipt = self._store.record_understanding(
                command,
                understanding_id=understanding_identity(command.identity),
                content_digest=digest,
            )
            return self.qualify_understanding(receipt)
        if isinstance(command, m.UpdateUnderstandingCommand):
            self._require_admitted_support(command)
            self._support.assert_current(command)
            no_op = self._confirm_noop(command)
            if no_op is not None:
                return self.qualify_understanding(
                    self._store.record_noop(command.identity, digest, no_op)
                )
            return self.qualify_understanding(
                self._store.record_understanding(command, content_digest=digest)
            )
        raise RecordingValidationError("record did not produce a command")

    def _record_verification_request(
        self, wire: _rw.RecordRequestWire
    ) -> m.RecordResult:
        original = wire
        wire = self._resolve_record_request(wire)
        if wire.run is not None and wire.run.evidence:
            admitted = [
                self._admit_source(
                    wire.repository_id,
                    wire.context_id or "",
                    item.locator,
                    tuple(
                        m.SourceRange(
                            start_line=value.start_line,
                            end_line=value.end_line,
                        )
                        for value in item.ranges
                    ),
                )
                for item in wire.run.evidence
            ]
            run = _dataclasses.replace(
                wire.run,
                observations=tuple(
                    [*wire.run.observations, *(item.value for item in admitted)]
                ),
            )
            wire = _dataclasses.replace(wire, run=run)
        digest = _rw.wire_content_digest(original)
        replay = self._replay(
            wire.identity.repository_id, wire.identity.request_id, digest
        )
        if replay is not None:
            return self.qualify_verification(replay)
        command = _rw.record_command(wire, self._resolver(wire.identity))
        if not isinstance(command, m.RecordVerificationCommand):
            raise RecordingValidationError("verification record produced no run")
        self._require_admitted_verification(command)
        self._support.assert_observations(command.run.observations)
        return self.qualify_verification(
            self._store.record_verification(command, content_digest=digest)
        )

    def create(self, wire: _rw.RecordCreateWire) -> m.RecordReceipt:
        digest = _rw.wire_content_digest(wire)
        replay = self._replay(
            wire.identity.repository_id, wire.identity.request_id, digest
        )
        if replay is not None:
            return replay
        wire = self._resolved_wire(wire)  # type: ignore[assignment]
        command = _rw.create_command(wire, self._resolver(wire.identity))
        self._require_admitted_support(command)
        self._support.assert_current(command)
        return self._store.record_understanding(
            command,
            understanding_id=understanding_identity(command.identity),
            content_digest=digest,
        )

    def add(self, wire: _rw.RecordAddWire) -> m.RecordReceipt:
        return self._record_update(
            wire,
            lambda value: _rw.add_command(value, self._resolver(value.identity)),  # type: ignore[arg-type]
        )

    def confirm(self, wire: _rw.RecordConfirmWire) -> m.RecordReceipt:
        return self._record_update(
            wire,
            lambda value: _rw.confirm_command(value, self._resolver(value.identity)),  # type: ignore[arg-type]
        )

    def correct(self, wire: _rw.RecordCorrectWire) -> m.RecordReceipt:
        return self._record_update(
            wire,
            lambda value: _rw.correct_command(value, self._resolver(value.identity)),  # type: ignore[arg-type]
        )

    def replace(self, wire: _rw.RecordReplaceWire) -> m.RecordReceipt:
        return self._record_update(
            wire,
            lambda value: _rw.replace_command(value, self._resolver(value.identity)),  # type: ignore[arg-type]
        )

    def withdraw(self, wire: _rw.RecordWithdrawWire) -> m.RecordReceipt:
        return self._record_update(
            wire,
            lambda value: _rw.withdraw_command(value, self._resolver(value.identity)),  # type: ignore[arg-type]
        )

    def update(self, wire: _rw.RecordUpdateWire) -> m.RecordReceipt:
        return self._record_update(
            wire,
            lambda value: _rw.update_command(value, self._resolver(value.identity)),  # type: ignore[arg-type]
        )

    def challenge(self, wire: _rw.RecordChallengeWire) -> m.RecordReceipt:
        digest = _rw.wire_content_digest(wire)
        replay = self._replay(
            wire.identity.repository_id, wire.identity.request_id, digest
        )
        if replay is not None:
            return replay
        if wire.identity.context_id is None:
            raise RecordingValidationError(
                "a challenge cites admitted evidence; supply context_id"
            )
        command = _rw.challenge_command(wire, self._resolver(wire.identity))
        return self._store.record_challenge(command, content_digest=digest)

    def verification(self, wire: _rw.RecordVerificationWire) -> m.RecordReceipt:
        digest = _rw.wire_content_digest(wire)
        replay = self._replay(
            wire.identity.repository_id, wire.identity.request_id, digest
        )
        if replay is not None:
            return replay
        if wire.identity.context_id is None:
            raise RecordingValidationError(
                "a verification run cites admitted observations; supply context_id"
            )
        command = _rw.verification_command(wire)
        self._require_admitted_verification(command)
        self._support.assert_observations(command.run.observations)
        return self._store.record_verification(command, content_digest=digest)

    def receipt(self, identity: m.RecordingIdentity) -> m.RecordReceipt | None:
        """Return the retained receipt for one caller-known request identity."""
        return self._store.get_receipt(recording_key(identity))

    def _replay(
        self, repository_id: str, request_id: str, digest: m.ContentDigest
    ) -> m.RecordReceipt | None:
        """Resolve a retained receipt before any new-write dependency check."""
        key = m.RecordingKey(
            repository_id=repository_id,
            request_id=m.RequestId(request_id),
        )
        existing = self._store.get_receipt(key)
        if existing is None:
            return None
        decision = receipt_decision(existing, key, digest)
        if decision.kind is m.ReceiptDecisionKind.REPLAY:
            return decision.receipt
        raise RecordingConflict(
            decision.reason
            or "this submission identity already committed different content",
            cause_kind=RejectionCauseKind.REPLAY_CONFLICT,
        )

    def _record_update(
        self,
        wire: (
            _rw.RecordAddWire
            | _rw.RecordConfirmWire
            | _rw.RecordCorrectWire
            | _rw.RecordReplaceWire
            | _rw.RecordWithdrawWire
            | _rw.RecordUpdateWire
        ),
        builder: _typing.Callable[[_RecordWire], m.UpdateUnderstandingCommand],
    ) -> m.RecordReceipt:
        digest = _rw.wire_content_digest(wire)
        replay = self._replay(
            wire.identity.repository_id, wire.identity.request_id, digest
        )
        if replay is not None:
            return replay
        wire = self._resolved_wire(wire)  # type: ignore[assignment]
        command = builder(wire)
        self._require_admitted_support(command)
        self._support.assert_current(command)
        no_op = self._confirm_noop(command)
        if no_op is not None:
            return self._store.record_noop(command.identity, digest, no_op)
        return self._store.record_understanding(command, content_digest=digest)

    def _confirm_noop(
        self, command: m.UpdateUnderstandingCommand
    ) -> m.UnderstandingId | None:
        """FD-31: confirming an already-current, unchanged version is a no-op."""
        if (
            not command.confirm
            or command.add
            or command.correct
            or command.replace
            or command.withdraw
            or command.gaps is not None
            or command.challenge_dispositions
        ):
            return None
        understanding = self._store.get_understanding(command.understanding_id.value)
        version = self._store.get_version(
            command.understanding_id.value,
            understanding.current_version.value,
        )
        if version.version != command.expected_version:
            return None
        revisions = self._store.get_conclusions(command.understanding_id.value)
        by_key = {(item.conclusion_id, item.revision.value): item for item in revisions}
        current = {ref.conclusion_id: ref for ref in version.conclusions}
        for action in command.confirm:
            ref = current.get(action.conclusion_id)
            if ref is None:
                raise RecordingValidationError(
                    "confirm targets a conclusion absent from the current version"
                )
            if self._support.evaluate_revision(ref).state is not m.SupportState.CURRENT:
                return None
            content = by_key[(ref.conclusion_id, ref.revision.value)].content
            if not isinstance(content, m.SupportedConclusion):
                return None
            if (
                content.statement != action.statement
                or content.assertion_nature != action.assertion_nature
                or content.scope != action.scope
                or content.support != action.support
            ):
                raise RecordingValidationError(
                    "a current conclusion with changed content requires correct"
                )
        return command.understanding_id

    def qualify_understanding(
        self, receipt: m.RecordReceipt
    ) -> m.UnderstandingRecorded:
        if not receipt.accepted_understanding_ids:
            raise RecordingValidationError(
                "an understanding receipt has no accepted understanding"
            )
        understanding_id = receipt.accepted_understanding_ids[0].value
        version = receipt.accepted_understanding_versions[0].value
        try:
            qualification: m.UnderstandingSupport | m.SupportUnavailable = (
                self._support.evaluate_version(understanding_id, version)
            )
        except (OSError, ValueError) as exc:
            qualification = m.SupportUnavailable(str(exc))
        return m.UnderstandingRecorded(receipt=receipt, qualification=qualification)

    def qualify_verification(self, receipt: m.RecordReceipt) -> m.VerificationRecorded:
        if not receipt.accepted_verification_run_ids:
            raise RecordingValidationError("a verification receipt has no accepted run")
        run_id = receipt.accepted_verification_run_ids[0].value
        try:
            qualification: m.VerificationSupport | m.SupportUnavailable = (
                self._support.evaluate_verification(run_id)
            )
        except (OSError, ValueError) as exc:
            qualification = m.SupportUnavailable(str(exc))
        return m.VerificationRecorded(receipt=receipt, qualification=qualification)

    def qualify_challenge(self, receipt: m.RecordReceipt) -> m.ChallengeRecorded:
        if not receipt.accepted_challenge_ids:
            raise RecordingValidationError("a challenge receipt has no challenge")
        challenge_id = receipt.accepted_challenge_ids[0].value
        return m.ChallengeRecorded(
            receipt=receipt, challenge=self._store.get_challenge(challenge_id)
        )

    # -- reference resolution and admission --------------------------------

    def _resolve_record_request(
        self, wire: _rw.RecordRequestWire
    ) -> _rw.RecordRequestWire:
        if wire.identity.context_id is not None:
            return wire
        paths = self._record_request_paths(wire)
        discovery_scopes = self._record_request_discovery_scopes(wire)
        if not paths and not discovery_scopes:
            raise RecordingValidationError(
                "recording without a context requires a declared scope, a "
                "cited locator, or a discovery boundary",
                cause_kind=RejectionCauseKind.CONTEXT_REQUIRED,
            )
        context = issue_context(
            self._store,
            payload=wire,
            repository_id=wire.identity.repository_id,
            request_id=m.RequestId(f"{wire.identity.request_id}:record-context"),
            scope=m.EvidenceScope(paths=tuple(sorted(set(paths)))),
            question=None,
            clock=self._clock,
            new_context_id=self._new_context_id,
        )
        return _dataclasses.replace(wire, context_id=context.context_id.value)

    def _record_request_paths(self, wire: _rw.RecordRequestWire) -> list[str]:
        paths: list[str] = []
        if wire.kind is m.RecordKind.UNDERSTANDING:
            if wire.conclusion is not None:
                paths.extend(wire.scope_paths)
                if wire.locator is not None:
                    paths.append(wire.locator)
                paths.extend(_cited_locators(wire.support))
            elif (
                wire.understanding_id is not None and wire.expected_version is not None
            ):
                version = self._store.get_version(
                    wire.understanding_id, wire.expected_version
                )
                paths.extend(version.scope.paths)
            paths.extend(_record_wire_locators(wire.actions))
        elif wire.kind is m.RecordKind.VERIFICATION and wire.run is not None:
            paths.extend(wire.run.scope_paths)
            paths.extend(item.locator for item in wire.run.evidence)
        for scope in self._record_request_discovery_scopes(wire):
            paths.extend(scope.paths)
        return [path for path in paths if path]

    def _record_request_discovery_scopes(
        self, wire: _rw.RecordRequestWire
    ) -> tuple[m.EvidenceScope, ...]:
        supports: list[_rw.SupportWire] = list(wire.support)
        if wire.actions is not None:
            for conclusion in (
                *wire.actions.add,
                *wire.actions.confirm,
                *wire.actions.correct,
                *(item.new_conclusion for item in wire.actions.replace),
            ):
                supports.extend(conclusion.support)
        scopes: list[m.EvidenceScope] = []
        for support in supports:
            if isinstance(support, _rw.DiscoveryBoundarySupportWire):
                scopes.append(m.EvidenceScope(paths=support.scope.paths))
        return tuple(scopes)

    def _resolved_wire(self, wire: _RecordWire) -> _RecordWire:
        """Bind a recording that cites locators to a server-issued context.

        Recording may cite locators/ranges the agent already holds or a
        context from a preceding ask; there is no third mode and no separate
        admission call (L2 §4.2). When no context is supplied, the operation
        issues one internally and admits the cited sources into it.
        """
        if wire.identity.context_id is not None:
            return wire
        context = self._issue_record_context(wire)
        return _dataclasses.replace(
            wire,
            identity=_dataclasses.replace(
                wire.identity, context_id=context.context_id.value
            ),
        )

    def _issue_record_context(self, wire: _RecordWire) -> m.InvestigationContext:
        paths = self._record_scope_paths(wire)
        return issue_context(
            self._store,
            payload=wire,
            repository_id=wire.identity.repository_id,
            request_id=m.RequestId(f"{wire.identity.request_id}:record-context"),
            scope=m.EvidenceScope(paths=paths),
            question=None,
            clock=self._clock,
            new_context_id=self._new_context_id,
        )

    def _record_scope_paths(self, wire: _RecordWire) -> tuple[str, ...]:
        paths = list(_cited_locators(wire))
        if isinstance(wire, _rw.RecordCreateWire):
            if not isinstance(wire.target, _rw.ExplicitTargetWire):
                raise RecordingValidationError(
                    "recording without a context requires an explicit target; "
                    "supply context_id for a context-bound target",
                    cause_kind=RejectionCauseKind.CONTEXT_REQUIRED,
                )
            paths.extend(wire.target.scope_paths)
        else:
            version = self._store.get_version(
                wire.understanding_id, wire.expected_version
            )
            paths.extend(version.scope.paths)
        if not paths:
            raise RecordingValidationError(
                "recording without a context requires a declared scope or "
                "locator source support",
                cause_kind=RejectionCauseKind.CONTEXT_REQUIRED,
            )
        return tuple(sorted(set(paths)))

    def _resolver(self, identity_wire: _rw.IdentityWire) -> _rw.RecordWireResolver:
        identity = _recording_identity(identity_wire)
        context_id = identity.context_id.value
        repository_id = identity.repository_id

        def reference(value: str) -> m.EvidenceRef:
            resolved = self._store.find_admitted_evidence(context_id, value)
            if resolved is None:
                raise RecordingValidationError(
                    f"evidence reference {value!r} is not admitted in "
                    f"context {context_id}"
                )
            if resolved.repository_id != repository_id:
                raise RecordingValidationError(
                    f"evidence reference {value!r} belongs to another repository"
                )
            return resolved

        def authority(value: str) -> m.AuthorityBinding:
            return self._authority.resolve_authority(repository_id, value)

        def source(
            locator: str, ranges: tuple[m.SourceRange, ...]
        ) -> m.SourceObservationId:
            return self._admit_source(repository_id, context_id, locator, ranges)

        def discovery(scope: m.EvidenceScope) -> m.DiscoveryObservationId:
            return self._admit_discovery(repository_id, context_id, scope)

        return _rw.RecordWireResolver(
            reference=reference,
            authority=authority,
            source=source,
            discovery=discovery,
        )

    def _admit_source(
        self,
        repository_id: str,
        context_id: str,
        locator: str,
        ranges: tuple[m.SourceRange, ...],
    ) -> m.SourceObservationId:
        """Admit one cited source inside the recording operation (F7, TD §12)."""
        context = self._store.get_context(context_id)
        if context.repository_id != repository_id:
            raise RecordingValidationError(
                f"context belongs to repository {context.repository_id!r}, not "
                f"{repository_id!r}"
            )
        result = self._evidence.admit(
            context,
            (m.EvidenceRequest(locator, ranges),),
            DEFAULT_SERVICE_BOUNDS_POLICY.default_query_bounds,
        )
        outcome = result.outcomes[0]
        if isinstance(outcome, (m.AdmittedEvidence, m.AlreadyAdmittedEvidence)):
            return outcome.observation_id
        raise RecordingValidationError(
            f"source evidence {locator!r} could not be admitted: {outcome.reason}"
        )

    def _admit_discovery(
        self,
        repository_id: str,
        context_id: str,
        scope: m.EvidenceScope,
    ) -> m.DiscoveryObservationId:
        """Observe one supplied boundary and admit the membership snapshot."""
        context = self._store.get_context(context_id)
        if context.repository_id != repository_id:
            raise RecordingValidationError(
                f"context belongs to repository {context.repository_id!r}, not "
                f"{repository_id!r}"
            )
        pairs = self._evidence.inventory_entries(repository_id, scope)
        fingerprint = support_rules.discovery_membership_fingerprint(pairs)
        observation_id = discovery_observation_identity(
            repository_id, scope, fingerprint
        )
        existing = self._store.find_discovery_observation(observation_id.value)
        if existing is None:
            self._store.put_discovery_observation(
                m.DiscoveryObservation(
                    observation_id=observation_id,
                    repository_id=repository_id,
                    scope=scope,
                    membership_fingerprint=fingerprint,
                    captured_at=self._clock(),
                )
            )
        self._store.add_context_discovery_evidence(context_id, observation_id.value)
        return observation_id

    def _require_admitted_support(
        self,
        command: m.CreateUnderstandingCommand | m.UpdateUnderstandingCommand,
    ) -> None:
        context_id = command.identity.context_id.value
        for dependency in m.command_support_dependencies(command):
            if isinstance(dependency, m.SourceSupport):
                if not self._store.has_admitted_observation(
                    context_id, dependency.observation_id.value
                ):
                    raise RecordingValidationError(
                        "source observation "
                        f"{dependency.observation_id.value!r} is not admitted "
                        f"in context {context_id}; ask returned the admitted "
                        "observations for this context",
                        cause_kind=RejectionCauseKind.OBSERVATION_NOT_ADMITTED,
                    )
            elif isinstance(dependency, m.PremiseSupport):
                premise = dependency.premise
                if not self._store.has_conclusion_revision(
                    premise.understanding_id.value,
                    premise.conclusion_id.value,
                    premise.revision.value,
                ):
                    raise RecordingValidationError(
                        "premise revision "
                        f"{premise.understanding_id.value}/"
                        f"{premise.conclusion_id.value}@"
                        f"{premise.revision.value} does not exist"
                    )
            elif isinstance(dependency, m.DiscoverySupport):
                if not self._store.has_admitted_discovery(
                    context_id, dependency.observation_id.value
                ):
                    raise RecordingValidationError(
                        "discovery observation "
                        f"{dependency.observation_id.value!r} is not admitted "
                        f"in context {context_id}; ask returned the admitted "
                        "observations for this context",
                        cause_kind=RejectionCauseKind.OBSERVATION_NOT_ADMITTED,
                    )

    def _require_admitted_verification(
        self, command: m.RecordVerificationCommand
    ) -> None:
        if command.run.repository_id != command.identity.repository_id:
            raise RecordingValidationError(
                "a verification run belongs to another repository"
            )
        context_id = command.identity.context_id.value
        for observation in command.run.observations:
            if not self._store.has_admitted_observation(context_id, observation.value):
                raise RecordingValidationError(
                    f"verification observation {observation.value!r} is not "
                    f"admitted in context {context_id}; use the observation id "
                    "ask returned, or cite the locator in run.evidence",
                    cause_kind=RejectionCauseKind.OBSERVATION_NOT_ADMITTED,
                )
