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

from span.core import containment
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
from span.service.surface_status import compose_surface_status

__all__ = ["LifecycleService"]


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
        self._store.require_repository(wire.bound_repository_id)
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

    def _flat_conclusion(
        self,
        wire: _rw.RecordRequestWire,
        scope: m.EvidenceScope,
    ) -> m.ProposedConclusion:
        """Build the one conclusion from the flat create fields.

        The conclusion scope is the effective create scope already established
        by the request or its bound context. A declared surface name is an
        owner identity, never an evidence path.
        """
        if wire.conclusion is None:
            raise ValueError("a flat conclusion requires conclusion text")
        resolver = self._resolver(wire.identity)
        locator = wire.locator or (scope.paths[0] if scope.paths else "")
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
            wire,
            resolver,
            locator=locator,
            default_support=default,
            scope=scope,
        )

    def _create_scope(
        self,
        wire: _rw.RecordRequestWire,
        context: m.InvestigationContext | None,
    ) -> m.EvidenceScope:
        """Resolve the complete semantic scope, independently of support."""
        if context is not None and context.origin is m.ContextOrigin.QUESTION:
            if wire.question or wire.scope_paths:
                raise Rejection(
                    "a question context binds the create target; omit question and scope_paths",
                    cause_kind=RejectionCauseKind.CONTEXT_TARGET_CONFLICT,
                )
            return context.scope
        if wire.scope_paths:
            return m.EvidenceScope(paths=wire.scope_paths)
        if wire.locator is not None:
            return m.EvidenceScope(paths=(wire.locator,))
        if wire.surface is not None and wire.surface.kind is m.SurfaceKind.FILE:
            return m.EvidenceScope(paths=(wire.surface.locator,))
        raise Rejection(
            "a create requires scope_paths, a locator, a FILE surface, or a question context",
            cause_kind=RejectionCauseKind.VALIDATION,
        )

    def _resolve_create_surface(
        self,
        wire: _rw.RecordRequestWire,
        scope: m.EvidenceScope,
    ) -> m.SurfaceKey:
        """Resolve one owner and validate its agreement with semantic scope."""
        repository_id = wire.bound_repository_id
        if wire.surface is not None:
            surface = m.SurfaceKey(
                repository_id, wire.surface.kind, wire.surface.locator
            )
            self._require_surface_in_scope(surface, scope)
            return surface
        paths = set(scope.paths) | {ref.locator for ref in scope.evidence_refs}
        if len(paths) == 1:
            return containment.path_surface(repository_id, next(iter(paths)))
        if not paths:
            raise Rejection(
                "semantic scope does not identify one owner",
                cause_kind=RejectionCauseKind.SURFACE_REQUIRED,
            )
        raise Rejection(
            "semantic scope names multiple candidate surfaces: "
            + ", ".join(sorted(paths)),
            cause_kind=RejectionCauseKind.SURFACE_AMBIGUOUS,
        )

    def _require_surface_in_scope(
        self, surface: m.SurfaceKey, scope: m.EvidenceScope
    ) -> None:
        if not scope.paths and not scope.evidence_refs:
            raise Rejection(
                f"{surface.kind.value} surface {surface.locator!r} cannot own repository-wide semantic scope",
                cause_kind=RejectionCauseKind.SURFACE_MISMATCH,
            )
        owner = (
            self._store.find_surface(surface)
            if surface.kind.is_declared
            else m.Surface(key=surface)
        )
        if owner is None:
            raise RecordingValidationError(
                "an understanding create against a declared surface requires that surface to exist"
            )
        members = containment.scope_surfaces(surface.repository_id, scope)
        for member in members:
            if not containment.surface_contains(owner, member):
                raise Rejection(
                    f"semantic member {member.locator!r} lies outside {surface.kind.value} surface {surface.locator!r}",
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
        digest = _rw.wire_content_digest(wire)
        replay = self._replay(
            wire.identity.repository_id, wire.identity.request_id, digest
        )
        if replay is not None:
            if replay.accepted_verification_run_ids:
                return self.qualify_verification(replay)
            return self.qualify_understanding(replay)
        create = wire.conclusion is not None
        supplied_context = (
            self._store.get_context(wire.context_id)
            if wire.context_id is not None
            else None
        )
        scope = self._create_scope(wire, supplied_context) if create else None
        wire = self._resolve_record_request(wire, semantic_scope=scope)
        context = self._store.get_context(_typing.cast(str, wire.context_id))
        context_bound = context.origin is m.ContextOrigin.QUESTION
        derived = (
            self._resolve_create_surface(wire, scope) if scope is not None else None
        )
        derived_conclusions = (
            (self._flat_conclusion(wire, scope),) if scope is not None else None
        )
        current_revisions: tuple[m.ConclusionRevision, ...] = ()
        if not create:
            current_revisions = self._current_revisions_for_update(wire)
        command = _rw.record_command(
            wire,
            self._resolver(wire.identity),
            context_bound=context_bound,
            derived_surface=derived,
            derived_scope=scope,
            derived_conclusions=derived_conclusions,
            current_revisions=current_revisions,
        )
        if isinstance(command, m.CreateUnderstandingCommand):
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

    def _current_revisions_for_update(
        self, wire: _rw.RecordRequestWire
    ) -> tuple[m.ConclusionRevision, ...]:
        """Apply the expected-version CAS before deriving compact actions.

        The store still owns the authoritative compare-and-set inside the
        acceptance transaction. This read exists so the derivation of
        confirm/correct/replace uses the version the caller named and so a
        stale version rejects with the observed current version (FD-46).
        """
        understanding_id = _typing.cast(str, wire.understanding_id)
        expected = _typing.cast(int, wire.expected_version)
        understanding = self._store.get_understanding(understanding_id)
        if understanding.current_version.value != expected:
            raise RecordingConflict(
                "expected understanding version "
                f"{expected} does not match current "
                f"{understanding.current_version.value}",
                current_version=understanding.current_version.value,
            )
        return self._store.get_version_conclusions(understanding_id, expected)

    def _record_verification_request(
        self, wire: _rw.RecordRequestWire
    ) -> m.RecordResult:
        return self.qualify_verification(self._store_verification(wire))

    def _store_verification(self, wire: _rw.RecordRequestWire) -> m.RecordReceipt:
        """The one verification write path for wire and typed submissions.

        Evidence-only and observation-only runs are both accepted: cited
        evidence is admitted first, then the resulting observation ids travel
        through the same command and admission checks. The two submissions
        never take a divergent route.
        """
        digest = _rw.wire_content_digest(wire)
        replay = self._replay(wire.bound_repository_id, wire.request_id, digest)
        if replay is not None:
            return replay
        wire = self._resolve_record_request(wire)
        run = wire.run
        if run is None:
            raise RecordingValidationError("a verification record requires run")
        if run.evidence:
            admitted = [
                self._admit_source(
                    wire.bound_repository_id,
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
                for item in run.evidence
            ]
            run = _dataclasses.replace(
                run,
                observations=tuple(
                    dict.fromkeys(
                        [*run.observations, *(item.value for item in admitted)]
                    )
                ),
            )
            wire = _dataclasses.replace(wire, run=run)
        command = _rw.record_command(wire, self._resolver(wire.identity))
        if not isinstance(command, m.RecordVerificationCommand):
            raise RecordingValidationError("verification record produced no run")
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
        operational_errors: tuple[type[Exception], ...] = (
            OSError,
        ) + self._store.operational_errors
        try:
            qualification: m.UnderstandingSupport | m.SupportUnavailable = (
                self._support.evaluate_version(understanding_id, version)
            )
        except operational_errors as exc:
            qualification = m.SupportUnavailable(f"{type(exc).__name__}: {exc}")
        owner: m.SurfaceKey | None = None
        try:
            owner = self._store.get_understanding(understanding_id).surface
            status: m.SurfaceStatus | m.SurfaceStatusUnavailable = (
                compose_surface_status(
                    owner,
                    store=self._store,
                    support=self._support,
                    evidence=self._evidence,
                )
            )
        except operational_errors as exc:
            status = m.SurfaceStatusUnavailable(
                reason=f"{type(exc).__name__}: {exc}", surface=owner
            )
        snapshot = self._store.get_version(understanding_id, version)
        compact_qualification = (
            m.compact_understanding(qualification)
            if isinstance(qualification, m.UnderstandingSupport)
            else qualification
        )
        return m.UnderstandingRecorded(
            receipt_selector=m.ReceiptRetrievalSelector(
                repository_id=receipt.identity.repository_id,
                request_id=receipt.identity.request_id.value,
            ),
            committed_at=receipt.committed_at,
            understanding_id=m.UnderstandingId(understanding_id),
            version=m.UnderstandingVersionNumber(version),
            affected_revisions=snapshot.conclusions,
            dependent_effects=receipt.dependent_effects,
            qualification=compact_qualification,
            status=status,
        )

    def qualify_verification(self, receipt: m.RecordReceipt) -> m.VerificationRecorded:
        if not receipt.accepted_verification_run_ids:
            raise RecordingValidationError("a verification receipt has no accepted run")
        run_id = receipt.accepted_verification_run_ids[0].value
        operational_errors: tuple[type[Exception], ...] = (
            OSError,
        ) + self._store.operational_errors
        try:
            qualification: m.VerificationSupport | m.SupportUnavailable = (
                self._support.evaluate_verification(run_id)
            )
        except operational_errors as exc:
            qualification = m.SupportUnavailable(f"{type(exc).__name__}: {exc}")
        run = self._store.get_verification_run(run_id)
        compact_qualification = (
            m.compact_verification(qualification)
            if isinstance(qualification, m.VerificationSupport)
            else qualification
        )
        return m.VerificationRecorded(
            receipt_selector=m.ReceiptRetrievalSelector(
                repository_id=receipt.identity.repository_id,
                request_id=receipt.identity.request_id.value,
            ),
            committed_at=receipt.committed_at,
            run_id=run.run_id,
            command=run.command,
            scenario=run.scenario,
            outcome=run.outcome,
            qualification=compact_qualification,
        )

    def qualify_challenge(self, receipt: m.RecordReceipt) -> m.ChallengeRecorded:
        if not receipt.accepted_challenge_ids:
            raise RecordingValidationError("a challenge receipt has no challenge")
        challenge_id = receipt.accepted_challenge_ids[0].value
        return m.ChallengeRecorded(
            receipt=receipt, challenge=self._store.get_challenge(challenge_id)
        )

    # -- reference resolution and admission --------------------------------

    def _resolve_record_request(
        self,
        wire: _rw.RecordRequestWire,
        *,
        semantic_scope: m.EvidenceScope | None = None,
    ) -> _rw.RecordRequestWire:
        if wire.context_id is not None:
            return wire
        requirements = self._record_request_scopes(wire, semantic_scope)
        if not requirements:
            raise RecordingValidationError(
                "context-free recording requires explicit scope or direct evidence",
                cause_kind=RejectionCauseKind.CONTEXT_REQUIRED,
            )
        context = issue_context(
            self._store,
            payload=wire,
            repository_id=wire.bound_repository_id,
            request_id=m.RequestId(f"{wire.request_id}:record-context"),
            scope=m.evidence_scope_union(requirements),
            question=None,
            clock=self._clock,
            new_context_id=self._new_context_id,
        )
        return _dataclasses.replace(
            wire,
            repository_id=None,
            context=m.InvestigationContextRef(
                repository_id=context.repository_id,
                context_id=context.context_id,
            ),
        )

    def _record_request_scopes(
        self,
        wire: _rw.RecordRequestWire,
        semantic_scope: m.EvidenceScope | None,
    ) -> tuple[m.EvidenceScope, ...]:
        """Actual complete scope requirements; absent fields are not operands."""
        scopes: list[m.EvidenceScope] = []
        if semantic_scope is not None:
            scopes.append(semantic_scope)
        supports: list[_rw.SupportWire] = list(wire.support)
        locators = list(_cited_locators(wire.support))
        if wire.locator is not None:
            locators.append(wire.locator)
        if wire.actions is not None:
            if wire.understanding_id is not None and wire.expected_version is not None:
                scopes.append(
                    self._store.get_version(
                        wire.understanding_id, wire.expected_version
                    ).scope
                )
            actions: tuple[_rw.RecordActionWire, ...] = (
                *wire.actions.add,
                *wire.actions.confirm,
                *wire.actions.correct,
                *wire.actions.replace,
                *wire.actions.withdraw,
            )
            for action in actions:
                supports.extend(action.support)
                if action.locator is not None:
                    locators.append(action.locator)
                if (
                    isinstance(
                        action,
                        (
                            _rw.AddConclusionWire,
                            _rw.CorrectConclusionWire,
                            _rw.ReplaceActionWire,
                        ),
                    )
                    and action.scope_paths
                ):
                    scopes.append(m.EvidenceScope(paths=action.scope_paths))
            locators.extend(_record_wire_locators(wire.actions))
        if wire.run is not None:
            scopes.append(m.EvidenceScope(paths=wire.run.scope_paths))
            locators.extend(item.locator for item in wire.run.evidence)
        scopes.extend(m.EvidenceScope(paths=(locator,)) for locator in locators)
        for support in supports:
            if isinstance(support, _rw.DiscoveryBoundarySupportWire):
                if support.scope.evidence_refs:
                    raise RecordingValidationError(
                        "discovery evidence references require their admitting context or direct evidence/discovery scope",
                        cause_kind=RejectionCauseKind.CONTEXT_REQUIRED,
                    )
                scopes.append(m.EvidenceScope(paths=support.scope.paths))
        return tuple(scopes)

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

        def observation_locator(observation_id: str) -> str:
            observation = self._store.find_source_observation(observation_id)
            if observation is None:
                raise RecordingValidationError(
                    f"unknown source observation: {observation_id!r}"
                )
            if observation.repository_id != repository_id:
                raise RecordingValidationError(
                    f"observation {observation_id!r} belongs to another repository"
                )
            return observation.evidence.locator

        return _rw.RecordWireResolver(
            reference=reference,
            authority=authority,
            source=source,
            discovery=discovery,
            observation_locator=observation_locator,
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
        if (
            context.scope.paths or context.scope.evidence_refs
        ) and not m.evidence_scope_allows(locator, context.scope):
            raise RecordingValidationError(
                f"source {locator!r} lies outside context {context_id!r} scope {context.scope!r}",
                cause_kind=RejectionCauseKind.CONTEXT_SCOPE_CONFLICT,
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
        if not m.evidence_scope_contains(context.scope, scope):
            raise RecordingValidationError(
                f"discovery scope {scope!r} lies outside context {context_id!r} scope {context.scope!r}",
                cause_kind=RejectionCauseKind.CONTEXT_SCOPE_CONFLICT,
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
