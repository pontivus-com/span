"""Ordinary question composition: candidates, evidence, exact retrieval."""

from __future__ import annotations

import datetime as _datetime
import json as _json
import typing as _typing

from span.core import model as m
from span.core import support_rules as _rules
from span.core.identity import discovery_observation_identity
from span.core.recording import RecordingValidationError
from span.ports.evidence import EvidenceSource
from span.ports.lifecycle import LifecycleStorePort
from span.service.contexts import issue_context
from span.service.evidence import EvidenceService
from span.service.ids import server_context_id
from span.service.support import SupportService
from span.service.understanding_discovery import DiscoveryService

__all__ = ["UnderstandService"]


class UnderstandService:
    """Compose saved-understanding discovery with inspectable evidence."""

    def __init__(
        self,
        *,
        store: LifecycleStorePort,
        discovery: DiscoveryService,
        evidence: EvidenceService,
        evidence_source: EvidenceSource,
        support: SupportService,
        clock: _typing.Callable[[], _datetime.datetime] | None = None,
        new_context_id: _typing.Callable[[], str] | None = None,
    ) -> None:
        self._store = store
        self._discovery = discovery
        self._evidence = evidence
        self._evidence_source = evidence_source
        self._support = support
        self._clock = clock or (lambda: _datetime.datetime.now(_datetime.timezone.utc))
        self._new_context_id = new_context_id or server_context_id

    def retrieve(self, request: m.RetrieveRequest) -> m.RetrieveResult:
        """Return the selected snapshot, context, or retained receipt."""
        if isinstance(request, m.UnderstandingSnapshotSelector):
            self._store.require_repository(request.repository_id)
            return self._snapshot(
                request.repository_id,
                request.understanding_id,
                request.version,
            )
        if isinstance(request, m.ContextRetrievalSelector):
            context = self._store.get_context(request.context_id)
            self._require_repository(context.repository_id, request.repository_id)
            return m.RetrievedContext(
                context=context,
                observations=self._store.list_context_evidence(request.context_id),
                discovery=self._store.list_context_discovery(request.context_id),
            )
        if isinstance(request, m.ReceiptRetrievalSelector):
            identity = m.RecordingIdentity(
                repository_id=request.repository_id,
                context_id=m.InvestigationContextId(request.context_id),
                submission_id=m.SubmissionId(request.submission_id),
            )
            receipt = self._store.get_receipt(identity)
            if receipt is None:
                raise RecordingValidationError(
                    "no retained receipt for "
                    f"{request.context_id}/{request.submission_id}"
                )
            return m.RetrievedReceipt(
                receipt=receipt,
                context=self._store.find_context_by_id(request.context_id),
            )
        raise TypeError(f"unhandled retrieval selector: {type(request).__name__}")

    def _snapshot(
        self,
        repository_id: str,
        understanding_id: str,
        version: int | None,
    ) -> m.RetrievedUnderstanding:
        understanding = self._store.get_understanding(understanding_id)
        self._require_repository(understanding.repository_id, repository_id)
        selected = understanding.current_version.value if version is None else version
        snapshot = self._store.get_version(understanding_id, selected)
        conclusions = self._store.get_version_conclusions(understanding_id, selected)
        return m.RetrievedUnderstanding(
            understanding=understanding,
            version=snapshot,
            conclusions=conclusions,
            support=self._support.evaluate_version(understanding_id, selected),
            challenges=self._store.get_challenges(understanding_id),
        )

    def question(
        self, request: m.UnderstandQuestionRequest
    ) -> m.UnderstandQuestionResult:
        """Return candidates, inspectable evidence, or an explicit limit."""
        self._store.require_repository(request.repository_id)
        discovery = self._discovery.discover(
            request.repository_id,
            request.scope,
            request.question,
            request.bounds,
            request.page_token,
        )
        if discovery.candidates:
            context = issue_context(
                self._store,
                payload=request,
                repository_id=request.repository_id,
                request_id=request.request_id,
                scope=request.scope,
                question=request.question,
                clock=self._clock,
                new_context_id=self._new_context_id,
            )
            retrieved, omitted = self._bounded_snapshots(
                request.repository_id,
                discovery.candidates,
                request.bounds.max_evidence_bytes,
            )
            return m.UnderstandingCandidateAnswer(
                context=context,
                discovery=discovery,
                retrieved=retrieved,
                bound_info=m.BoundInfo(
                    requested_max_results=request.bounds.max_results,
                    requested_max_depth=0,
                    returned_results=len(retrieved),
                    truncated=omitted or discovery.bound_info.truncated,
                    truncated_category=(
                        "candidate-content"
                        if omitted
                        else discovery.bound_info.truncated_category
                    ),
                    continuation_token=discovery.bound_info.continuation_token,
                ),
            )
        if not (request.scope.paths or request.scope.evidence_refs):
            return m.DiscoveryLimit(discovery=discovery)
        context = issue_context(
            self._store,
            payload=request,
            repository_id=request.repository_id,
            request_id=request.request_id,
            scope=request.scope,
            question=request.question,
            clock=self._clock,
            new_context_id=self._new_context_id,
        )
        inventory = self._evidence_source.inventory_evidence(
            request.repository_id, request.scope, request.bounds
        )
        pairs = tuple(
            (
                item.evidence_ref.locator,
                item.evidence_ref.evidence_id.value,
            )
            for item in inventory.items
        )
        fingerprint = _rules.discovery_membership_fingerprint(pairs)
        observation = m.DiscoveryObservation(
            observation_id=discovery_observation_identity(
                request.repository_id, request.scope, fingerprint
            ),
            repository_id=request.repository_id,
            scope=request.scope,
            membership_fingerprint=fingerprint,
            captured_at=self._clock(),
        )
        self._store.put_discovery_observation(observation)
        self._store.add_context_discovery_evidence(
            context.context_id.value, observation.observation_id.value
        )
        requests = tuple(
            m.EvidenceRequest(item.evidence_ref.locator)
            for item in inventory.items[: request.bounds.max_evidence_units]
        )
        if not requests:
            return m.InvestigationNeeded(
                context=context,
                outcomes=(),
                evidence=(),
                reason=(
                    "no saved understanding matched and the scope contains "
                    "no servable text evidence"
                ),
                discovery_observation_id=observation.observation_id,
                bound_info=inventory.bound_info,
            )
        admission = self._evidence.extend(
            m.EvidenceExtendRequest(
                repository_id=request.repository_id,
                context_id=context.context_id,
                requests=requests,
                bounds=request.bounds,
            )
        )
        observation_ids = tuple(
            outcome.observation_id.value
            for outcome in admission.outcomes
            if isinstance(outcome, (m.AdmittedEvidence, m.AlreadyAdmittedEvidence))
        )
        evidence = (
            self._evidence.read(
                context.context_id.value, observation_ids, request.bounds
            )
            if observation_ids
            else ()
        )
        return m.InvestigationNeeded(
            context=context,
            outcomes=admission.outcomes,
            evidence=evidence,
            reason=(
                "no saved understanding matched this question and scope; "
                "the admitted evidence is the bounded material for investigation"
            ),
            discovery_observation_id=observation.observation_id,
            bound_info=inventory.bound_info,
        )

    def _bounded_snapshots(
        self,
        repository_id: str,
        candidates: tuple[m.UnderstandingCandidate, ...],
        max_bytes: int,
    ) -> tuple[tuple[m.RetrievedUnderstanding, ...], bool]:
        retrieved: list[m.RetrievedUnderstanding] = []
        total = 0
        omitted = False
        for candidate in candidates:
            snapshot = self._snapshot(
                repository_id, candidate.understanding_id.value, None
            )
            size = len(
                _json.dumps(m.to_canonical(snapshot), sort_keys=True).encode("utf-8")
            )
            if retrieved and total + size > max_bytes:
                omitted = True
                break
            retrieved.append(snapshot)
            total += size
        return tuple(retrieved), omitted

    @staticmethod
    def _require_repository(actual: str, requested: str) -> None:
        if actual != requested:
            raise RecordingValidationError(
                f"referenced content belongs to repository {actual!r}, not "
                f"{requested!r}"
            )
