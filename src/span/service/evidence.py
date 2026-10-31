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
from span.core.identity import source_observation_identity
from span.core.recording import RecordingValidationError
from span.ports.evidence import EvidenceSource
from span.ports.lifecycle import LifecycleStorePort
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
    ) -> None:
        self._store = store
        self._evidence = evidence
        self._clock = clock or (lambda: _datetime.datetime.now(_datetime.timezone.utc))
        self._new_context_id = new_context_id or server_context_id

    # -- context start / extension ----------------------------------------

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
        return self._admit(context, request.requests, request.bounds)

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
        return self._admit(context, request.requests, request.bounds)

    # -- retrieval ---------------------------------------------------------

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
            content = record.excerpt
            total_bytes += len(content.encode("utf-8"))
            if total_bytes > bounds.max_evidence_bytes:
                raise ValueError("evidence exceeds max_evidence_bytes")
            content_range = None
            if len(record.delivered_ranges) == 1:
                only = record.delivered_ranges[0]
                content_range = m.EvidenceLineRange(
                    start_line=only.start_line,
                    end_line=only.end_line,
                    total_lines=record.total_lines,
                )
            units.append(
                m.EvidenceUnit(
                    evidence_ref=record.evidence,
                    content=content,
                    content_fingerprint=record.content_digest.value.split(":", 1)[1],
                    content_range=content_range,
                )
            )
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
            size = len(unit.content.encode("utf-8"))
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
            digest = m.ContentDigest(f"sha256:{unit.content_fingerprint}")
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
