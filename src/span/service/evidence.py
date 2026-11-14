"""Evidence admission service: exact sources and same-context extension.

This is the source-first half of the lifecycle. It admits exact text sources
into one server-issued context, reuses canonical observations for repeated
bytes/ranges, and reports one closed outcome per submitted item. It creates no
semantic question and performs no coverage work.
"""

from __future__ import annotations

import datetime as _datetime
import typing as _typing

from span.core import model as m
from span.core import support_rules
from span.core.identity import source_observation_identity
from span.core.recording import RecordingValidationError
from span.ports.evidence import EvidenceSource
from span.ports.lifecycle import LifecycleStorePort
from span.service.bounds import DEFAULT_SERVICE_BOUNDS_POLICY
from span.service.contexts import issue_context
from span.service.ids import server_context_id

__all__ = ["EvidenceService"]


class EvidenceService:
    """Admit exact source evidence into repository-bound contexts."""

    def __init__(
        self,
        *,
        store: LifecycleStorePort,
        evidence: EvidenceSource,
        clock: _typing.Callable[[], _datetime.datetime] | None = None,
        new_context_id: _typing.Callable[[], str] | None = None,
        policy: m.ServiceBoundsPolicy = DEFAULT_SERVICE_BOUNDS_POLICY,
    ) -> None:
        self._store = store
        self._evidence = evidence
        self._clock = clock or (lambda: _datetime.datetime.now(_datetime.timezone.utc))
        self._new_context_id = new_context_id or server_context_id
        self._policy = policy

    # -- context start / extension ----------------------------------------

    def inventory_paths(
        self, repository_id: str, scope: m.EvidenceScope
    ) -> tuple[str, ...]:
        """Servable repository paths inside one scope, for boundary status."""
        pairs, _ = self._evidence.list_inventory_entries(repository_id, scope)
        return tuple(path for path, _ in pairs)

    def inventory_entries(
        self, repository_id: str, scope: m.EvidenceScope
    ) -> tuple[tuple[str, str], ...]:
        """Membership pairs for a discovery observation."""
        pairs, _ = self._evidence.list_inventory_entries(repository_id, scope)
        return pairs

    def context_observations(self, context_id: str) -> tuple[m.SourceObservation, ...]:
        """Return one context's admitted source observations in stable order."""
        return tuple(
            sorted(
                self._store.list_context_evidence(context_id),
                key=lambda item: item.observation_id.value,
            )
        )

    def context_unit(self, record: m.SourceObservation) -> m.EvidenceUnit:
        """Project one single-fragment observation into an evidence unit."""
        deliveries = self.context_deliveries(record)
        if len(deliveries) != 1:
            raise ValueError("an observation with disjoint ranges has multiple deliveries")
        return deliveries[0].unit

    def context_deliveries(
        self, record: m.SourceObservation
    ) -> tuple[m.EvidenceDelivery, ...]:
        """Project immutable observation content into exact positioned deliveries."""
        fingerprint = record.content_digest.value.split(":", 1)[1]
        if record.whole_file:
            return (
                m.EvidenceDelivery(
                    observation_id=record.observation_id,
                    unit=m.EvidenceUnit(
                        evidence_ref=record.evidence,
                        content=record.excerpt,
                        content_fingerprint=fingerprint,
                    ),
                ),
            )
        lines = record.excerpt.splitlines(keepends=True)
        offset = 0
        deliveries: list[m.EvidenceDelivery] = []
        for source_range in record.delivered_ranges:
            count = source_range.end_line - source_range.start_line + 1
            content = "".join(lines[offset : offset + count])
            offset += count
            deliveries.append(
                m.EvidenceDelivery(
                    observation_id=record.observation_id,
                    unit=m.EvidenceUnit(
                        evidence_ref=record.evidence,
                        content=content,
                        content_fingerprint=fingerprint,
                        content_range=m.EvidenceLineRange(
                            start_line=source_range.start_line,
                            end_line=source_range.end_line,
                            total_lines=record.total_lines,
                        ),
                    ),
                )
            )
        return tuple(deliveries)

    def start(self, request: m.EvidenceStartRequest) -> m.EvidenceAdmissionResult:
        """Create or recover the evidence-only context and admit the batch."""
        self._store.require_repository(request.repository_id)
        context = issue_context(
            self._store,
            payload=request,
            repository_id=request.repository_id,
            request_id=request.request_id,
            scope=request.scope,
            question=None,
            clock=self._clock,
            new_context_id=self._new_context_id,
        )
        return self._admit(context, request.requests, self._policy.default_query_bounds)

    def extend(self, request: m.EvidenceExtendRequest) -> m.EvidenceAdmissionResult:
        """Admit further exact sources into one existing live context."""
        self._store.require_repository(request.repository_id)
        context = self._store.get_context(request.context_id.value)
        if context.repository_id != request.repository_id:
            raise RecordingValidationError(
                f"context belongs to repository {context.repository_id!r}, not "
                f"{request.repository_id!r}"
            )
        self._require_live(context)
        return self._admit(context, request.requests, self._policy.default_query_bounds)

    # -- retrieval ---------------------------------------------------------

    def admit(
        self,
        context: m.InvestigationContext,
        requests: tuple[m.EvidenceRequest, ...],
        bounds: m.QueryBounds,
    ) -> m.EvidenceAdmissionResult:
        """Admit exact sources into one live context (internal record step)."""
        self._require_live(context)
        return self._admit(context, requests, bounds)

    def admitted(self, context_id: str) -> tuple[m.AdmittedEvidence, ...]:
        """Return the context's admitted observations as canonical carriers."""
        return tuple(
            m.AdmittedEvidence(
                request=m.EvidenceRequest(
                    record.evidence.locator, record.delivered_ranges
                ),
                observation_id=record.observation_id,
                delivered_ranges=record.delivered_ranges,
                admitted_at=record.captured_at,
                whole_file=record.whole_file,
            )
            for record in self._store.list_context_evidence(context_id)
        )

    def read(
        self,
        context_id: str,
        observation_ids: tuple[str, ...],
        bounds: m.QueryBounds,
    ) -> tuple[m.EvidenceUnit, ...]:
        """Read stored admitted excerpts without re-reading the workspace."""
        records = {
            record.observation_id.value: record
            for record in self._store.list_context_evidence(context_id)
        }
        selected = (
            tuple(records.values())
            if not observation_ids
            else tuple(records[key] for key in observation_ids if key in records)
        )
        if observation_ids and len(selected) != len(observation_ids):
            missing = sorted(set(observation_ids) - set(records))
            raise RecordingValidationError(
                "unknown admitted observation(s): " + ", ".join(missing)
            )
        units: list[m.EvidenceUnit] = []
        total_bytes = 0
        for record in selected:
            for delivery in self.context_deliveries(record):
                content = delivery.unit.content
                total_bytes += len(content.encode("utf-8"))
                if total_bytes > bounds.max_evidence_bytes:
                    raise ValueError("evidence exceeds max_evidence_bytes")
                units.append(delivery.unit)
                if len(units) > bounds.max_evidence_units:
                    raise ValueError("evidence exceeds max_evidence_units")
        return tuple(units)

    # -- admission ---------------------------------------------------------

    def _admit(
        self,
        context: m.InvestigationContext,
        requests: tuple[m.EvidenceRequest, ...],
        bounds: m.QueryBounds,
    ) -> m.EvidenceAdmissionResult:
        now = self._clock()
        outcomes: list[m.EvidenceAdmissionOutcome] = []
        total_bytes = 0
        stop = False
        for index, request in enumerate(requests):
            if stop or index >= bounds.max_evidence_units:
                outcomes.append(
                    m.OmittedEvidence(
                        request,
                        "batch bound reached; resubmit the remaining items",
                    )
                )
                continue
            scope = context.scope
            if (scope.paths or scope.evidence_refs) and not (
                m.evidence_scope_allows(request.locator, scope)
            ):
                outcomes.append(
                    m.OmittedEvidence(
                        request,
                        "locator lies outside the admitted scope",
                    )
                )
                continue
            unit = self._evidence.read_exact(context.repository_id, request, bounds)
            if isinstance(unit, m.EvidenceSourceFailure):
                outcomes.append(unit)
                continue
            lines = unit.content.splitlines(keepends=True)
            total_lines = len(lines)
            if request.ranges:
                delivered = tuple(
                    sorted(
                        request.ranges,
                        key=lambda item: (item.start_line, item.end_line),
                    )
                )
                if any(item.end_line > total_lines for item in delivered):
                    outcomes.append(
                        m.OmittedEvidence(
                            request,
                            "requested range exceeds the observed "
                            f"{total_lines} lines",
                        )
                    )
                    continue
                excerpt = "".join(
                    "".join(lines[item.start_line - 1 : item.end_line])
                    for item in delivered
                )
                whole_file = False
            else:
                delivered = ()
                excerpt = unit.content
                whole_file = True
            if request.ranges:
                ranged = support_rules.ranged_fingerprint(unit.content, delivered)
                if ranged is None:
                    outcomes.append(
                        m.OmittedEvidence(
                            request,
                            "requested range cannot bind to the observed text",
                        )
                    )
                    continue
                digest = m.ContentDigest(f"sha256:{ranged}")
            else:
                digest = m.ContentDigest(f"sha256:{unit.content_fingerprint}")
            size = len(excerpt.encode("utf-8"))
            if total_bytes + size > bounds.max_evidence_bytes:
                outcomes.append(
                    m.OmittedEvidence(
                        request,
                        "max_evidence_bytes reached; resubmit the remaining " "items",
                    )
                )
                stop = True
                continue
            total_bytes += size
            observation_id = source_observation_identity(
                context.repository_id,
                request.locator,
                digest,
                delivered,
                whole_file,
            )
            existed = self._store.has_source_observation(observation_id.value)
            if not existed:
                self._store.put_source_observation(
                    m.SourceObservation(
                        observation_id=observation_id,
                        repository_id=context.repository_id,
                        evidence=unit.evidence_ref,
                        content_digest=digest,
                        captured_at=now,
                        total_lines=total_lines,
                        delivered_ranges=delivered,
                        whole_file=whole_file,
                        excerpt=excerpt,
                    )
                )
            self._store.add_context_evidence(
                context.context_id.value, observation_id.value
            )
            if existed:
                outcomes.append(m.AlreadyAdmittedEvidence(request, observation_id))
            else:
                outcomes.append(
                    m.AdmittedEvidence(
                        request=request,
                        observation_id=observation_id,
                        delivered_ranges=delivered,
                        admitted_at=now,
                        whole_file=whole_file,
                    )
                )
        return m.EvidenceAdmissionResult(context=context, outcomes=tuple(outcomes))

    def _require_live(self, context: m.InvestigationContext) -> None:
        if context.state is not m.ContextState.LIVE:
            raise RecordingValidationError("the investigation context is not live")
        if context.expires_at is not None and context.expires_at < self._clock():
            raise RecordingValidationError("the investigation context has expired")
