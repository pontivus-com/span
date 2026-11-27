"""Reconsideration: map a changed scope to the surfaces that must be re-examined.

Covers FD-17–FD-22. Membership comes from the shared containment resolver;
direct loss comes from the source reverse index; indirect loss is a premise
walk to a fixed point. The result is grouped by surface, carries every reason,
and is ordered narrowest to widest by the same resolver used for status.
"""

from __future__ import annotations

import datetime as _datetime
import typing as _typing
import uuid as _uuid

from span.core import model as m
from span.core.identity import record_content_digest
from span.core.recording import (
    RecordingConflict,
    RecordingValidationError,
    receipt_decision,
)
from span.ports.lifecycle import LifecycleStorePort
from span.service.bounds import DEFAULT_SERVICE_BOUNDS_POLICY
from span.service.contexts import context_binding, issue_context
from span.service.evidence import EvidenceService
from span.service.effects import DependencyEffectService
from span.service.understand import UnderstandService

__all__ = ["ReconsiderService"]


def _unknown_exact(kind: str, identity: str) -> RecordingValidationError:
    return RecordingValidationError(
        f"unknown {kind}: {identity!r}",
        public_identity=identity,
        public_cause=f"the exact {kind} {identity!r} does not exist",
    )


class ReconsiderService:
    """Compose one bounded reconsideration result over stored understanding."""

    def __init__(
        self,
        *,
        store: LifecycleStorePort,
        effects: DependencyEffectService,
        understand: UnderstandService,
        evidence: EvidenceService | None = None,
        policy: m.ServiceBoundsPolicy = DEFAULT_SERVICE_BOUNDS_POLICY,
        clock: _typing.Callable[[], _datetime.datetime] | None = None,
        new_context_id: _typing.Callable[[], str] | None = None,
    ) -> None:
        self._store = store
        self._evidence = evidence
        self._policy = policy
        self._clock = clock or (lambda: _datetime.datetime.now(_datetime.timezone.utc))
        self._new_context_id = new_context_id or (lambda: "ctx-" + _uuid.uuid4().hex)
        self._effects = effects
        self._understand = understand

    def reconsider(
        self, request: m.ReconsiderRequest
    ) -> m.Changed | m.Challenged | m.AcceptedDetailUnavailable | m.Unavailable:
        if request.challenge is not None:
            repository_id = request.bound_repository_id
            self._store.require_repository(repository_id)
            return self._raise_challenge(repository_id, request.challenge)
        try:
            return self._effects.repository_change(request)
        except (OSError,) + self._store.operational_errors:
            return m.Unavailable(
                operation="reconsider",
                failure="changed-scope analysis could not be completed",
                recovery=(
                    "restore repository availability and retry reconsider with the "
                    "original repository_id, changed_paths and changed_surfaces"
                ),
            )

    def preview_changed_scope(self, request: m.ReconsiderRequest) -> m.Changed:
        """Return the canonical changed-scope projection without context writes."""
        if request.challenge is not None:
            raise ValueError("a challenge is not a changed-scope preview")
        return self._effects.repository_change(request, issue_contexts=False)

    def _raise_challenge(
        self, repository_id: str, challenge: m.ChallengeRaise
    ) -> m.Challenged | m.AcceptedDetailUnavailable:
        """Accept or replay one explicit dispute through reconsider (L2 §4.3)."""
        key = m.RecordingKey(repository_id, m.RequestId(challenge.request_id))
        existing = self._store.get_receipt(key)
        if existing is not None:
            command = self._challenge_command(
                repository_id, challenge, existing.identity.context_id
            )
            decision = receipt_decision(existing, key, record_content_digest(command))
            if decision.kind is m.ReceiptDecisionKind.CONFLICT:
                raise RecordingConflict(
                    decision.reason or "the request already committed different content",
                    cause_kind=m.RejectionCauseKind.REPLAY_CONFLICT,
                )
            return self._understand.challenge_opening(existing)

        understanding = self._store.find_understanding(challenge.understanding_id)
        if understanding is None:
            raise _unknown_exact("understanding", challenge.understanding_id)
        if understanding.repository_id != repository_id:
            raise RecordingValidationError(
                "challenge target belongs to another repository"
            )
        version = self._store.find_version(
            challenge.understanding_id, challenge.target_version
        )
        if version is None:
            raise _unknown_exact(
                "understanding version",
                f"{challenge.understanding_id}@{challenge.target_version}",
            )
        context_id = (
            challenge.context.context_id
            if challenge.context is not None
            else self._challenge_context(
                repository_id,
                challenge,
                understanding=understanding,
                version=version,
            )
        )
        for reference in challenge.evidence:
            admitted = self._store.find_admitted_evidence(
                context_id.value, reference.evidence_id.value
            )
            if admitted is None:
                raise RecordingValidationError(
                    f"challenge evidence {reference.evidence_id.value!r} is not "
                    f"admitted in context {context_id.value}"
                )
        command = self._challenge_command(repository_id, challenge, context_id)
        receipt = self._store.record_challenge(
            command, content_digest=record_content_digest(command)
        )
        return self._understand.challenge_opening(receipt)

    @staticmethod
    def _challenge_command(
        repository_id: str,
        challenge: m.ChallengeRaise,
        context_id: m.InvestigationContextId,
    ) -> m.CreateChallengeCommand:
        return m.CreateChallengeCommand(
            identity=m.RecordingIdentity(
                repository_id=repository_id,
                request_id=m.RequestId(challenge.request_id),
                context_id=context_id,
            ),
            understanding_id=m.UnderstandingId(challenge.understanding_id),
            target_version=m.UnderstandingVersionNumber(challenge.target_version),
            target_conclusions=tuple(
                m.ConclusionRevisionRef(
                    understanding_id=m.UnderstandingId(item.understanding_id),
                    conclusion_id=m.ConclusionId(item.conclusion_id),
                    revision=m.ConclusionRevisionNumber(item.revision),
                )
                for item in challenge.target_conclusions
            ),
            reason=challenge.reason,
            evidence=challenge.evidence,
        )

    def _challenge_context(
        self,
        repository_id: str,
        challenge: m.ChallengeRaise,
        *,
        understanding: m.Understanding,
        version: m.UnderstandingVersion,
    ) -> m.InvestigationContextId:
        scopes = [version.scope]
        if understanding.surface.kind is m.SurfaceKind.FILE:
            scopes.append(m.EvidenceScope(paths=(understanding.surface.locator,)))
        else:
            declared = self._store.find_surface(understanding.surface)
            if declared is not None and declared.boundary.paths:
                scopes.append(m.EvidenceScope(paths=declared.boundary.paths))
        if challenge.evidence:
            scopes.append(m.EvidenceScope(evidence_refs=challenge.evidence))
        context = issue_context(
            self._store,
            binding=context_binding(
                scope=m.evidence_scope_union(scopes),
                origin=m.ContextOrigin.CHALLENGE,
                source_requests=tuple(
                    m.EvidenceRequest(reference.locator)
                    for reference in challenge.evidence
                ),
            ),
            repository_id=repository_id,
            request_id=m.RequestId(challenge.request_id),
            clock=self._clock,
            new_context_id=self._new_context_id,
        )
        if self._evidence is not None:
            for reference in challenge.evidence:
                if (
                    self._store.find_admitted_evidence(
                        context.context_id.value, reference.evidence_id.value
                    )
                    is None
                ):
                    self._evidence.admit(
                        context,
                        (m.EvidenceRequest(reference.locator),),
                        self._policy.default_query_bounds,
                    )
        return context.context_id
