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

import datetime as _datetime
import typing as _typing

from span.core import model as m
from span.core.identity import understanding_identity
from span.core.recording import (
    RecordingConflict,
    RecordingValidationError,
    receipt_decision,
)
from span.core.schema import record_wire as _rw
from span.ports.lifecycle import LifecycleAuthorityResolver, LifecycleStorePort
from span.service.contexts import issue_context
from span.service.support import SupportService
from span.service.ids import server_context_id

__all__ = ["LifecycleService"]


def _recording_identity(value: _rw.IdentityWire) -> m.RecordingIdentity:
    return m.RecordingIdentity(
        repository_id=value.repository_id,
        context_id=m.InvestigationContextId(value.context_id),
        submission_id=m.SubmissionId(value.submission_id),
    )


class LifecycleService:
    """One repository-independent lifecycle service over one store."""

    def __init__(
        self,
        *,
        store: LifecycleStorePort,
        authority: LifecycleAuthorityResolver,
        support: SupportService,
        clock: _typing.Callable[[], _datetime.datetime] | None = None,
        new_context_id: _typing.Callable[[], str] | None = None,
    ) -> None:
        self._store = store
        self._authority = authority
        self._support = support
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

    def create(self, wire: _rw.RecordCreateWire) -> m.RecordReceipt:
        identity = _recording_identity(wire.identity)
        digest = _rw.wire_content_digest(wire)
        replay = self._replay(identity, digest)
        if replay is not None:
            return replay
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
            wire, lambda: _rw.add_command(wire, self._resolver(wire.identity))
        )

    def confirm(self, wire: _rw.RecordConfirmWire) -> m.RecordReceipt:
        return self._record_update(
            wire, lambda: _rw.confirm_command(wire, self._resolver(wire.identity))
        )

    def correct(self, wire: _rw.RecordCorrectWire) -> m.RecordReceipt:
        return self._record_update(
            wire, lambda: _rw.correct_command(wire, self._resolver(wire.identity))
        )

    def replace(self, wire: _rw.RecordReplaceWire) -> m.RecordReceipt:
        return self._record_update(
            wire, lambda: _rw.replace_command(wire, self._resolver(wire.identity))
        )

    def withdraw(self, wire: _rw.RecordWithdrawWire) -> m.RecordReceipt:
        return self._record_update(
            wire, lambda: _rw.withdraw_command(wire, self._resolver(wire.identity))
        )

    def update(self, wire: _rw.RecordUpdateWire) -> m.RecordReceipt:
        return self._record_update(
            wire, lambda: _rw.update_command(wire, self._resolver(wire.identity))
        )

    def challenge(self, wire: _rw.RecordChallengeWire) -> m.RecordReceipt:
        identity = _recording_identity(wire.identity)
        digest = _rw.wire_content_digest(wire)
        replay = self._replay(identity, digest)
        if replay is not None:
            return replay
        command = _rw.challenge_command(wire, self._resolver(wire.identity))
        return self._store.record_challenge(command, content_digest=digest)

    def verification(self, wire: _rw.RecordVerificationWire) -> m.RecordReceipt:
        identity = _recording_identity(wire.identity)
        digest = _rw.wire_content_digest(wire)
        replay = self._replay(identity, digest)
        if replay is not None:
            return replay
        command = _rw.verification_command(wire)
        self._require_admitted_verification(command)
        self._support.assert_observations(command.run.observations)
        return self._store.record_verification(command, content_digest=digest)

    def receipt(self, identity: m.RecordingIdentity) -> m.RecordReceipt | None:
        """Return the retained receipt for one caller-known identity."""
        return self._store.get_receipt(identity)

    def _replay(
        self, identity: m.RecordingIdentity, digest: m.ContentDigest
    ) -> m.RecordReceipt | None:
        """Resolve a retained receipt before any new-write dependency check."""
        existing = self._store.get_receipt(identity)
        if existing is None:
            return None
        decision = receipt_decision(existing, identity, digest)
        if decision.kind is m.ReceiptDecisionKind.REPLAY:
            return decision.receipt
        raise RecordingConflict(
            decision.reason
            or "this submission identity already committed different content"
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
        builder: _typing.Callable[[], m.UpdateUnderstandingCommand],
    ) -> m.RecordReceipt:
        identity = _recording_identity(wire.identity)
        digest = _rw.wire_content_digest(wire)
        replay = self._replay(identity, digest)
        if replay is not None:
            return replay
        command = builder()
        self._require_admitted_support(command)
        self._support.assert_current(command)
        return self._store.record_understanding(command, content_digest=digest)

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

        return _rw.RecordWireResolver(reference=reference, authority=authority)

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
                        f"in context {context_id}"
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
                        f"in context {context_id}"
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
                    f"admitted in context {context_id}"
                )
