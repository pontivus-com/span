"""Ordinary question composition: candidates, evidence, exact retrieval."""

from __future__ import annotations

import dataclasses as _dataclasses
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
from span.service.understanding_discovery import (
    DiscoveryService,
    encode_discovery_cursor,
)

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
        kind = _token_kind(request.page_token)
        # Pagination position is not part of the investigation binding: the
        # same request identity must recover the same context across pages.
        binding = _dataclasses.replace(request, page_token=None)
        discovery: m.UnderstandingDiscovery | None = None
        if kind != "inventory":
            discovery = self._discovery.discover(
                request.repository_id,
                request.scope,
                request.question,
                request.bounds,
                request.page_token if kind == "discovery" else None,
            )
            if discovery.candidates:
                context = issue_context(
                    self._store,
                    payload=binding,
                    repository_id=request.repository_id,
                    request_id=request.request_id,
                    scope=request.scope,
                    question=request.question,
                    clock=self._clock,
                    new_context_id=self._new_context_id,
                )
                answer = m.UnderstandingCandidateAnswer(
                    context=context,
                    discovery=discovery,
                    retrieved=self._snapshots(
                        request.repository_id, discovery.candidates
                    ),
                )
                return self._fit_result(answer, request.bounds.max_evidence_bytes)
            if kind == "discovery":
                return self._fit_result(
                    m.DiscoveryLimit(discovery=discovery),
                    request.bounds.max_evidence_bytes,
                )
        if not (request.scope.paths or request.scope.evidence_refs):
            if discovery is None:
                raise RecordingValidationError(
                    "an inventory cursor requires a concrete evidence scope"
                )
            return self._fit_result(
                m.DiscoveryLimit(discovery=discovery),
                request.bounds.max_evidence_bytes,
            )
        context = issue_context(
            self._store,
            payload=binding,
            repository_id=request.repository_id,
            request_id=request.request_id,
            scope=request.scope,
            question=request.question,
            clock=self._clock,
            new_context_id=self._new_context_id,
        )
        inventory = self._evidence_source.inventory_evidence(
            request.repository_id,
            request.scope,
            request.bounds,
            request.page_token if kind == "inventory" else None,
        )
        observation: m.DiscoveryObservation | None = None
        inventory_limitation = ""
        if kind == "inventory":
            inventory_limitation = (
                "continuing an inventory cursor; membership remains partial"
            )
        else:
            observation, inventory_limitation = self._observe_inventory(
                context, request, inventory
            )
        requests = tuple(
            m.EvidenceRequest(item.evidence_ref.locator)
            for item in inventory.items[: request.bounds.max_evidence_units]
        )
        if not requests:
            reason = (
                "no saved understanding matched and the scope contains "
                "no servable text evidence"
            )
            if inventory_limitation:
                reason += f"; {inventory_limitation}"
            return self._fit_result(
                m.InvestigationNeeded(
                    context=context,
                    outcomes=(),
                    evidence=(),
                    reason=reason,
                    discovery_observation_id=(
                        observation.observation_id if observation else None
                    ),
                    bound_info=inventory.bound_info,
                ),
                request.bounds.max_evidence_bytes,
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
        reason = (
            "no saved understanding matched this question and scope; "
            "the admitted evidence is the bounded material for investigation"
        )
        if inventory_limitation:
            reason += f"; {inventory_limitation}"
        return self._fit_result(
            m.InvestigationNeeded(
                context=context,
                outcomes=admission.outcomes,
                evidence=evidence,
                reason=reason,
                discovery_observation_id=(
                    observation.observation_id if observation else None
                ),
                bound_info=inventory.bound_info,
            ),
            request.bounds.max_evidence_bytes,
        )

    def _observe_inventory(
        self,
        context: m.InvestigationContext,
        request: m.UnderstandQuestionRequest,
        inventory: m.EvidenceInventoryPage,
    ) -> tuple[m.DiscoveryObservation | None, str]:
        """Record complete scope membership only; a page is never complete."""
        if inventory.bound_info.truncated:
            return (
                None,
                "inventory was truncated; no complete-scope membership "
                "observation was created",
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
        return observation, ""

    def _snapshots(
        self,
        repository_id: str,
        candidates: tuple[
            m.UnderstandingCandidate | m.UnderstandingCandidateReference, ...
        ],
    ) -> tuple[m.RetrievedUnderstanding | m.UnderstandingSnapshotReference, ...]:
        retrieved: list[m.RetrievedUnderstanding | m.UnderstandingSnapshotReference] = (
            []
        )
        for candidate in candidates:
            if isinstance(candidate, m.UnderstandingCandidate):
                retrieved.append(
                    self._snapshot(
                        repository_id, candidate.understanding_id.value, None
                    )
                )
        return tuple(retrieved)

    def _fit_result(
        self, result: m.UnderstandQuestionResult, max_bytes: int
    ) -> m.UnderstandQuestionResult:
        """Apply the one response budget to every answer variant."""
        if _encoded_size(result) <= max_bytes:
            return result
        if isinstance(result, m.UnderstandingCandidateAnswer):
            return self._fit_candidate(result, max_bytes)
        if isinstance(result, m.InvestigationNeeded):
            return self._fit_investigation(result, max_bytes)
        if isinstance(result, m.DiscoveryLimit):
            return _budget_exceeded(result, max_bytes)
        return result

    def _fit_investigation(
        self,
        answer: m.InvestigationNeeded,
        max_bytes: int,
    ) -> m.UnderstandQuestionResult:
        """Reduce a cold answer, then refuse explicitly if it cannot fit."""
        context: m.InvestigationContext | m.InvestigationContextReference = (
            answer.context
        )
        limitation = "full context omitted by the response byte budget"
        if isinstance(answer.context, m.InvestigationContext):
            context = m.InvestigationContextReference(
                context_id=answer.context.context_id,
                repository_id=answer.context.repository_id,
            )
        bound = _budget_bound(answer.bound_info)
        reduced = _dataclasses.replace(
            answer,
            context=context,
            reason=answer.reason + f"; {limitation}",
            bound_info=bound,
        )
        if _encoded_size(reduced) <= max_bytes:
            return reduced
        reduced = _dataclasses.replace(
            reduced,
            evidence=(),
            reason=reduced.reason
            + "; admitted evidence omitted; retrieve the context for its observations",
        )
        if _encoded_size(reduced) <= max_bytes:
            return reduced
        reduced = _dataclasses.replace(
            reduced,
            outcomes=(),
            reason=reduced.reason + "; admission outcomes omitted by response budget",
        )
        if _encoded_size(reduced) <= max_bytes:
            return reduced
        reduced = _dataclasses.replace(reduced, discovery_observation_id=None)
        if _encoded_size(reduced) <= max_bytes:
            return reduced
        return _budget_exceeded(reduced, max_bytes)

    def _fit_candidate(
        self,
        answer: m.UnderstandingCandidateAnswer,
        max_bytes: int,
    ) -> m.UnderstandQuestionResult:
        """Keep the whole answer inside the response budget.

        Full snapshots are replaced by minimal references first, then full
        candidates, then candidate references are dropped with an explicit
        cursor. The context binding itself is never rewritten.
        """
        if _encoded_size(answer) <= max_bytes:
            return answer
        retrieved = list(answer.retrieved)
        candidates = list(answer.discovery.candidates)
        positions = {
            candidate.understanding_id.value: candidate.scan_position
            for candidate in candidates
        }
        truncated = answer.discovery.bound_info.truncated
        token = answer.discovery.bound_info.continuation_token
        category = answer.discovery.bound_info.truncated_category
        for index in reversed(range(len(retrieved))):
            item = retrieved[index]
            if isinstance(item, m.RetrievedUnderstanding):
                retrieved[index] = m.UnderstandingSnapshotReference(
                    understanding_id=item.understanding.understanding_id,
                    version=item.version.version,
                    scan_position=positions.get(
                        item.understanding.understanding_id.value, 0
                    ),
                )
                truncated = True
                category = "response-budget"
                rebuilt = _replace_answer(
                    answer, retrieved, candidates, truncated, token, category
                )
                if _encoded_size(rebuilt) <= max_bytes:
                    return rebuilt
        for index in reversed(range(len(candidates))):
            candidate_item = candidates[index]
            if isinstance(candidate_item, m.UnderstandingCandidate):
                candidates[index] = _candidate_reference(candidate_item)
                truncated = True
                category = "response-budget"
                rebuilt = _replace_answer(
                    answer, retrieved, candidates, truncated, token, category
                )
                if _encoded_size(rebuilt) <= max_bytes:
                    return rebuilt
        while candidates:
            dropped = candidates.pop()
            token = encode_discovery_cursor(dropped.scan_position)
            truncated = True
            category = "response-budget"
            rebuilt = _replace_answer(
                answer, retrieved, candidates, truncated, token, category
            )
            if _encoded_size(rebuilt) <= max_bytes:
                return rebuilt
        while retrieved:
            dropped_snapshot = retrieved.pop()
            if isinstance(dropped_snapshot, m.UnderstandingSnapshotReference):
                position = dropped_snapshot.scan_position
            else:
                position = positions.get(
                    dropped_snapshot.understanding.understanding_id.value, 0
                )
            token = encode_discovery_cursor(position)
            truncated = True
            category = "response-budget"
            rebuilt = _replace_answer(
                answer, retrieved, candidates, truncated, token, category
            )
            if _encoded_size(rebuilt) <= max_bytes:
                return rebuilt
        context: m.InvestigationContext | m.InvestigationContextReference = (
            m.InvestigationContextReference(
                context_id=answer.context.context_id,
                repository_id=answer.context.repository_id,
            )
        )
        truncated = True
        category = "response-budget"
        discovery = _dataclasses.replace(
            answer.discovery,
            candidates=tuple(candidates),
            bound_info=_dataclasses.replace(
                answer.discovery.bound_info,
                returned_results=len(candidates),
                truncated=True,
                truncated_category=category,
                continuation_token=token,
            ),
        )
        rebuilt = _dataclasses.replace(
            answer,
            context=context,
            retrieved=tuple(retrieved),
            discovery=discovery,
        )
        if _encoded_size(rebuilt) <= max_bytes:
            return rebuilt
        return _budget_exceeded(rebuilt, max_bytes)

    @staticmethod
    def _require_repository(actual: str, requested: str) -> None:
        if actual != requested:
            raise RecordingValidationError(
                f"referenced content belongs to repository {actual!r}, not "
                f"{requested!r}"
            )


def _token_kind(token: str | None) -> str | None:
    """Classify one canonical question cursor by its owning listing."""
    if token is None:
        return None
    if token.startswith("dsp:"):
        return "discovery"
    if token.startswith("pg:"):
        return "inventory"
    raise RecordingValidationError(
        "unsupported page token; expected a discovery or inventory cursor"
    )


def _encoded_size(value: object) -> int:
    return len(
        _json.dumps(
            m.to_canonical(value), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    )


def _candidate_reference(
    candidate: m.UnderstandingCandidate,
) -> m.UnderstandingCandidateReference:
    return m.UnderstandingCandidateReference(
        understanding_id=candidate.understanding_id,
        current_version=candidate.current_version,
        scan_position=candidate.scan_position,
    )


def _replace_answer(
    answer: m.UnderstandingCandidateAnswer,
    retrieved: list[m.RetrievedUnderstanding | m.UnderstandingSnapshotReference],
    candidates: list[m.UnderstandingCandidate | m.UnderstandingCandidateReference],
    truncated: bool,
    token: str | None,
    category: str | None,
) -> m.UnderstandingCandidateAnswer:
    discovery = _dataclasses.replace(
        answer.discovery,
        candidates=tuple(candidates),
        bound_info=_dataclasses.replace(
            answer.discovery.bound_info,
            returned_results=len(candidates),
            truncated=truncated,
            truncated_category=category,
            continuation_token=token,
        ),
    )
    return _dataclasses.replace(
        answer,
        retrieved=tuple(retrieved),
        discovery=discovery,
    )


def _budget_bound(bound: m.BoundInfo | None) -> m.BoundInfo | None:
    if bound is None:
        return None
    return _dataclasses.replace(
        bound,
        truncated=True,
        truncated_category="response-budget",
    )


def _budget_exceeded(minimal: object, requested_bytes: int) -> m.ResponseBudgetExceeded:
    return m.ResponseBudgetExceeded(
        requested_bytes=requested_bytes,
        minimum_bytes=_encoded_size(minimal),
    )
