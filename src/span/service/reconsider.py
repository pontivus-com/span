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

from span.core import containment
from span.core import model as m
from span.core.identity import payload_digest, record_content_digest
from span.core.recording import RecordingValidationError
from span.ports.lifecycle import LifecycleStorePort
from span.service.bounds import DEFAULT_SERVICE_BOUNDS_POLICY
from span.service.contexts import issue_context
from span.service.evidence import EvidenceService
from span.service.support import SupportService

__all__ = ["ReconsiderService"]


class ReconsiderService:
    """Compose one bounded reconsideration result over stored understanding."""

    def __init__(
        self,
        *,
        store: LifecycleStorePort,
        support: SupportService | None = None,
        evidence: EvidenceService | None = None,
        policy: m.ServiceBoundsPolicy = DEFAULT_SERVICE_BOUNDS_POLICY,
        clock: _typing.Callable[[], _datetime.datetime] | None = None,
        new_context_id: _typing.Callable[[], str] | None = None,
    ) -> None:
        self._store = store
        self._support = support
        self._evidence = evidence
        self._policy = policy
        self._clock = clock or (lambda: _datetime.datetime.now(_datetime.timezone.utc))
        self._new_context_id = new_context_id or (lambda: "ctx-" + _uuid.uuid4().hex)

    def reconsider(self, request: m.ReconsiderRequest) -> m.Changed | m.Challenged:
        repository_id = request.bound_repository_id
        self._store.require_repository(repository_id)
        if request.challenge is not None:
            return self._raise_challenge(repository_id, request.challenge)
        surfaces = self._store.list_surfaces(repository_id)
        reasons: dict[m.SurfaceKey, set[m.ChangeReason]] = {}
        affected: dict[m.SurfaceKey, set[m.ConclusionRevisionRef]] = {}
        omitted: list[str] = []
        truncated = False
        limit = self._policy.default_query_bounds.max_results
        max_depth = self._policy.default_query_bounds.max_depth

        def record(
            surface: m.SurfaceKey,
            reason: m.ChangeReason,
            ref: m.ConclusionRevisionRef | None = None,
        ) -> None:
            reasons.setdefault(surface, set()).add(reason)
            if ref is not None:
                affected.setdefault(surface, set()).add(ref)

        for path in request.changed_paths:
            member = containment.path_surface(repository_id, path)
            for surface in containment.containing_surfaces(surfaces, member):
                record(surface, m.ChangeReason.CONTAINMENT)
            direct = [
                ref
                for observation in self._store.source_observation_ids_for_locator(
                    repository_id, path
                )
                for ref in self._store.support_dependents("SOURCE", observation)
            ]
            for discovery in self._store.list_discovery_observations(
                repository_id
            ):
                if m.evidence_scope_contains(
                    discovery.scope, m.EvidenceScope(paths=(path,))
                ):
                    direct.extend(
                        self._store.support_dependents(
                            "DISCOVERY", discovery.observation_id.value
                        )
                    )
            direct = list(dict.fromkeys(direct))
            if len(direct) > limit:
                omitted.append(
                    "direct dependency bound reached before every dependent "
                    "was examined"
                )
                direct = direct[:limit]
                truncated = True
            for ref in direct:
                record(
                    self._surface_of(ref),
                    m.ChangeReason.DIRECT,
                    ref,
                )
            indirect, cut = self._indirect(direct, max_depth, limit)
            if cut:
                omitted.append(
                    "premise traversal bound reached before the walk completed"
                )
                truncated = True
            for ref in indirect:
                record(
                    self._surface_of(ref),
                    m.ChangeReason.INDIRECT,
                    ref,
                )

        for surface in request.changed_surfaces:
            record(surface, m.ChangeReason.CONTAINMENT)

        ordered = containment.order_surfaces(reasons)
        if len(ordered) > limit:
            omitted.append(f"{len(ordered) - limit} surface(s) beyond the bound")
            ordered = ordered[:limit]
            truncated = True

        current_versions: dict[str, m.UnderstandingVersion] = {}
        return m.Changed(
            surfaces=tuple(
                m.ChangedSurface(
                    surface=surface,
                    reasons=tuple(
                        sorted(reasons[surface], key=lambda item: item.value)
                    ),
                    conclusions=tuple(
                        conclusion
                        for conclusion in (
                            self._changed_conclusion(
                                ref, reasons[surface], current_versions
                            )
                            for ref in sorted(
                                affected.get(surface, ()),
                                key=lambda ref: ref.sort_key,
                            )
                        )
                        if conclusion is not None
                    ),
                )
                for surface in ordered
            ),
            omitted=tuple(omitted),
            truncated=truncated,
            context=self._reconsider_context(repository_id, request, ordered),
        )

    def _changed_conclusion(
        self,
        ref: m.ConclusionRevisionRef,
        reasons: set[m.ChangeReason],
        current_versions: dict[str, m.UnderstandingVersion],
    ) -> m.ChangedConclusion | None:
        """Emit only a current-membership ref as an actionable target.

        Dependency traversal still walks historical revisions so a current
        downstream dependent is not lost; composition filters them out here.
        """
        version = self._current_version(ref, current_versions)
        if ref not in version.conclusions:
            return None
        return m.ChangedConclusion(
            ref=ref,
            expected_version=version.version,
            reasons=tuple(sorted(reasons, key=lambda item: item.value)),
            support=self._support_state(ref),
        )

    def _current_version(
        self,
        ref: m.ConclusionRevisionRef,
        current_versions: dict[str, m.UnderstandingVersion],
    ) -> m.UnderstandingVersion:
        understanding_id = ref.understanding_id.value
        if understanding_id not in current_versions:
            understanding = self._store.get_understanding(understanding_id)
            current_versions[understanding_id] = self._store.get_version(
                understanding_id, understanding.current_version.value
            )
        return current_versions[understanding_id]

    def _reconsider_context(
        self,
        repository_id: str,
        request: m.ReconsiderRequest,
        surfaces: tuple[m.SurfaceKey, ...],
    ) -> m.InvestigationContextRef:
        paths = list(request.changed_paths)
        for surface in surfaces:
            if surface.kind is m.SurfaceKind.FILE:
                paths.append(surface.locator)
            else:
                declared = self._store.find_surface(surface)
                if declared is not None:
                    paths.extend(declared.boundary.paths)
        digest = payload_digest(request)
        context = issue_context(
            self._store,
            payload=request,
            repository_id=repository_id,
            request_id=m.RequestId("reconsider:" + digest.value.split(":", 1)[1][:32]),
            scope=m.EvidenceScope(paths=tuple(sorted(set(paths)))),
            question=None,
            clock=self._clock,
            new_context_id=self._new_context_id,
        )
        return m.InvestigationContextRef(
            repository_id=repository_id,
            context_id=context.context_id,
        )

    def _support_state(
        self, ref: m.ConclusionRevisionRef
    ) -> m.SupportEvaluation | m.SupportUnavailable:
        if self._support is None:
            return m.SupportUnavailable(
                "support evaluation is not configured for this reconsideration"
            )
        try:
            return self._support.evaluate_revision(ref)
        except (OSError, ValueError) as exc:
            return m.SupportUnavailable(str(exc))

    def _raise_challenge(
        self, repository_id: str, challenge: m.ChallengeRaise
    ) -> m.Challenged:
        """Raise one explicit dispute through reconsider (L2 §4.3)."""
        context_id = (
            challenge.context.context_id
            if challenge.context is not None
            else self._challenge_context(repository_id, challenge)
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
        self, repository_id: str, challenge: m.ChallengeRaise
    ) -> m.InvestigationContextId:
        understanding = self._store.get_understanding(challenge.understanding_id)
        version = self._store.get_version(
            challenge.understanding_id, challenge.target_version
        )
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
            payload=challenge,
            repository_id=repository_id,
            request_id=m.RequestId(challenge.request_id),
            scope=m.evidence_scope_union(scopes),
            question=None,
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

    def _surface_of(self, ref: m.ConclusionRevisionRef) -> m.SurfaceKey:
        return self._store.get_understanding(ref.understanding_id.value).surface

    def _indirect(
        self,
        direct: list[m.ConclusionRevisionRef],
        max_depth: int,
        max_nodes: int,
    ) -> tuple[list[m.ConclusionRevisionRef], bool]:
        """Walk premise dependents to the policy bound, reporting incompleteness.

        FD-22: the walk itself is bounded, not just its output. A node beyond
        the depth bound is not expanded; if it still has dependents the result
        reports the limit and never calls the remainder unaffected.
        """
        visited = set(direct)
        frontier = [(ref, 0) for ref in direct]
        found: list[m.ConclusionRevisionRef] = []
        truncated = False
        while frontier:
            ref, depth = frontier.pop()
            dependents = self._store.support_dependents("PREMISE", ref.label)
            if depth >= max_depth:
                if dependents:
                    truncated = True
                continue
            for dependent in dependents:
                if dependent in visited:
                    continue
                if len(visited) >= max_nodes:
                    return found, True
                visited.add(dependent)
                found.append(dependent)
                frontier.append((dependent, depth + 1))
        return found, truncated
