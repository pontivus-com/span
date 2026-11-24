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
from span.core.recording import RecordingValidationError
from span.ports.lifecycle import LifecycleStorePort
from span.service.bounds import DEFAULT_SERVICE_BOUNDS_POLICY
from span.service.contexts import context_binding, issue_context
from span.service.evidence import EvidenceService
from span.service.effects import DependencyEffectService

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

    def reconsider(self, request: m.ReconsiderRequest) -> m.Changed | m.Challenged:
        if request.challenge is not None:
            repository_id = request.bound_repository_id
            self._store.require_repository(repository_id)
            return self._raise_challenge(repository_id, request.challenge)
        return self._effects.repository_change(request)

    def preview_changed_scope(self, request: m.ReconsiderRequest) -> m.Changed:
        """Return the canonical changed-scope projection without context writes."""
        if request.challenge is not None:
            raise ValueError("a challenge is not a changed-scope preview")
        return self._effects.repository_change(request, issue_contexts=False)

    def _raise_challenge(
        self, repository_id: str, challenge: m.ChallengeRaise
    ) -> m.Challenged:
        """Raise one explicit dispute through reconsider (L2 §4.3)."""
        understanding = self._store.find_understanding(challenge.understanding_id)
        if understanding is None:
            raise _unknown_exact("understanding", challenge.understanding_id)
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
        command = m.CreateChallengeCommand(
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
        receipt = self._store.record_challenge(
            command, content_digest=record_content_digest(command)
        )
        if not receipt.accepted_challenge_ids:
            raise RecordingValidationError(
                "a challenge receipt has no accepted challenge"
            )
        return m.Challenged(
            challenge=self._store.get_challenge(
                receipt.accepted_challenge_ids[0].value
            ),
            context=m.InvestigationContextRef(
                repository_id=repository_id,
                context_id=context_id,
            ),
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
