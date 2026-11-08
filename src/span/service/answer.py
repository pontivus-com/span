"""Answer composition: current conclusions, gaps, ambiguity, and the document view.

Covers FD-23–FD-29 and the bounded response of FD-54–FD-57. Resolution uses
the shared containment resolver; support comes from the shared evaluator;
nothing is stored or rendered. A question ask returns ``Answer`` when at least
one matched conclusion is current and ``Gap`` otherwise. A no-question ask
returns the same current content grouped by recorded question (FD-28).

A cold result admits inspectable evidence into a server-issued context inside
the operation, so the caller never performs a separate admission step.
"""

from __future__ import annotations

import datetime as _datetime
import typing as _typing

from span.core import containment
from span.core import model as m
from span.core import support_rules
from span.core.recording import RecordingValidationError
from span.ports.lifecycle import LifecycleStorePort
from span.service.bounds import DEFAULT_SERVICE_BOUNDS_POLICY
from span.service.contexts import issue_context
from span.service.continuation import (
    ContinuationCursor,
    decode_continuation,
    encode_continuation,
)
from span.service.evidence import EvidenceService
from span.service.ids import server_context_id
from span.service.support import SupportService
from span.service.surface_status import compose_surface_status, covers_path

__all__ = ["AnswerService", "gap_recovery"]


def gap_recovery(reason: m.GapReason) -> str:
    """The one fixed remedy for a gap reason (FD-25, A8, TD §9.2).

    The text is server-owned. It names the next action and never ranks or
    describes other questions.
    """
    if reason is m.GapReason.NO_MATCH:
        return (
            "ask the same surface without a question to read its current "
            "document view"
        )
    if reason is m.GapReason.UNASSESSED:
        return "read the cited evidence, then record the conclusion"
    return "re-read the cited evidence, then record against the current revision"


def _encoded_size(value: object) -> int:
    """The exact MCP wire size: the budget is measured on delivered bytes."""
    import json

    from span.core.schema import to_wire_root

    payload = to_wire_root(type(value), m.to_canonical(value))
    return len(json.dumps(payload, sort_keys=True).encode("utf-8"))


class AnswerService:
    """Compose one answer, gap, ambiguity, or document view over stored meaning."""

    def __init__(
        self,
        *,
        store: LifecycleStorePort,
        support: SupportService,
        evidence: EvidenceService,
        policy: m.ServiceBoundsPolicy = DEFAULT_SERVICE_BOUNDS_POLICY,
        clock: _typing.Callable[[], _datetime.datetime] | None = None,
        new_context_id: _typing.Callable[[], str] | None = None,
    ) -> None:
        self._store = store
        self._support = support
        self._evidence = evidence
        self._policy = policy
        self._clock = clock or (lambda: _datetime.datetime.now(_datetime.timezone.utc))
        self._new_context_id = new_context_id or server_context_id

    def ask(self, request: m.AskRequest) -> m.AskResult:
        self._store.require_repository(request.repository_id)
        if request.continuation is not None:
            return self._evidence_page(request)
        if request.selector is not None:
            return self._exact_reference(request.selector)
        if request.surface is not None:
            surface = m.SurfaceKey(
                repository_id=request.repository_id,
                kind=request.surface.kind,
                locator=request.surface.locator,
            )
        else:
            if request.reference is None:
                raise RecordingValidationError("ask requires a surface or reference")
            resolved = self._resolve(request.repository_id, request.reference)
            if isinstance(resolved, m.AmbiguousSurface):
                return self._fit(request, resolved)
            surface = resolved
        all_understandings = tuple(
            self._store.list_understandings(request.repository_id)
        )
        understandings = tuple(
            item for item in all_understandings if item.surface == surface
        )
        status = compose_surface_status(
            surface, store=self._store, support=self._support, evidence=self._evidence
        )
        if request.question is None:
            return self._fit(
                request, self._document(request, surface, understandings, status)
            )
        matched = tuple(
            item for item in understandings if item.question == request.question
        )
        if not matched:
            return self._fit(
                request,
                self._cold_gap(
                    request,
                    surface,
                    (
                        m.GapReason.NO_MATCH
                        if understandings
                        else m.GapReason.UNASSESSED
                    ),
                ),
            )
        current: list[m.ConclusionView] = []
        historical: list[m.HistoricalConclusion] = []
        gaps: list[m.RecordedQuestionGap] = []
        states: list[m.SupportState] = []
        for understanding in matched:
            support = self._support.evaluate_version(
                understanding.understanding_id.value
            )
            states.append(support.state)
            version = self._store.get_version(
                understanding.understanding_id.value,
                understanding.current_version.value,
            )
            gaps.extend(version.gaps)
            revisions = {
                (item.conclusion_id.value, item.revision.value): item
                for item in self._store.get_conclusions(
                    understanding.understanding_id.value
                )
            }
            for item in support.conclusions:
                if item.evaluation.state is m.SupportState.CURRENT:
                    current.append(self._view(item, revisions))
                else:
                    historical.append(
                        self._historical(item, revisions, understanding.current_version)
                    )
        if current:
            return self._fit(
                request,
                m.Answer(
                    surface=surface,
                    status=status,
                    question=request.question,
                    conclusions=tuple(current),
                    gaps=tuple(gaps),
                    verification=self._verification(surface),
                    context=self._context(request, surface),
                ),
            )
        combined = support_rules.combine_states(tuple(states))
        reason = (
            m.GapReason.INVALIDATED
            if combined is m.SupportState.REASSESSMENT_REQUIRED
            else m.GapReason.UNVERIFIABLE
        )
        context_id, evidence, observations = self._investigate(request, surface)
        return self._fit(
            request,
            m.Gap(
                surface=surface,
                reason=reason,
                recovery=gap_recovery(reason),
                question=request.question,
                changed_evidence=tuple(unit.evidence_ref for unit in evidence),
                historical=tuple(historical),
                missing=(request.question,),
                evidence=evidence,
                observations=observations,
                context=context_id,
            ),
        )

    def _resolve(
        self, repository_id: str, reference: str
    ) -> m.SurfaceKey | m.AmbiguousSurface:
        surfaces = self._store.list_surfaces(repository_id)
        for surface in surfaces:
            if surface.key.kind.is_declared and surface.key.locator == reference:
                return surface.key
        member = containment.path_surface(repository_id, reference)
        candidates = containment.containing_surfaces(surfaces, member)
        if len(candidates) > 1:
            return m.AmbiguousSurface(
                reference=reference,
                candidates=candidates,
                missing_decision=(
                    "choose the file, symbol, service, or domain surface"
                ),
            )
        return candidates[0]

    def _view(
        self,
        support: m.ConclusionSupport,
        revisions: dict[tuple[str, int], m.ConclusionRevision],
    ) -> m.ConclusionView:
        revision = revisions.get(
            (support.ref.conclusion_id.value, support.ref.revision.value)
        )
        if revision is None or not isinstance(revision.content, m.SupportedConclusion):
            raise RecordingValidationError(
                "a current conclusion has no supported revision content"
            )
        content = revision.content
        return m.ConclusionView(
            ref=support.ref,
            statement=content.statement,
            assertion_nature=content.assertion_nature,
            scope=content.scope,
            support=support,
            evidence=self._evidence_refs(content.support),
        )

    def _historical(
        self,
        support: m.ConclusionSupport,
        revisions: dict[tuple[str, int], m.ConclusionRevision],
        understanding_version: m.UnderstandingVersionNumber,
    ) -> m.HistoricalConclusion:
        """Project one non-current revision as historical content (L2, F3)."""
        revision = revisions.get(
            (support.ref.conclusion_id.value, support.ref.revision.value)
        )
        if revision is None or not isinstance(revision.content, m.SupportedConclusion):
            raise RecordingValidationError(
                "a historical conclusion has no supported revision content"
            )
        content = revision.content
        return m.HistoricalConclusion(
            ref=support.ref,
            understanding_version=understanding_version,
            statement=content.statement,
            state=support.evaluation.state,
            evidence=self._evidence_refs(content.support),
        )

    def _evidence_refs(
        self, dependencies: tuple[m.SupportDependency, ...]
    ) -> tuple[m.EvidenceRef, ...]:
        refs: list[m.EvidenceRef] = []
        for dependency in dependencies:
            if isinstance(dependency, m.SourceSupport):
                record = self._store.find_source_observation(
                    dependency.observation_id.value
                )
                if record is not None:
                    refs.append(record.evidence)
            elif isinstance(dependency, m.AuthoritySupportDependency):
                refs.append(dependency.authority.evidence_ref)
        return tuple({ref.evidence_id.value: ref for ref in refs}.values())

    def _cold_gap(
        self,
        request: m.AskRequest,
        surface: m.SurfaceKey,
        reason: m.GapReason,
    ) -> m.Gap:
        """Return a gap with the surface's inspectable evidence admitted."""
        context, evidence, observations = self._investigate(request, surface)
        return m.Gap(
            surface=surface,
            reason=reason,
            recovery=gap_recovery(reason),
            question=request.question or "",
            evidence=evidence,
            observations=observations,
            context=context,
            missing=(
                (
                    request.question
                    if request.question
                    else "no current conclusion on this surface"
                ),
            ),
        )

    def _investigate(self, request: m.AskRequest, surface: m.SurfaceKey) -> tuple[
        m.InvestigationContextId | None,
        tuple[m.EvidenceUnit, ...],
        tuple[m.SourceObservationId, ...],
    ]:
        paths = self._surface_paths(surface)
        if not paths:
            return None, (), ()
        scope = m.EvidenceScope(paths=paths)
        try:
            context = issue_context(
                self._store,
                payload=request,
                repository_id=request.repository_id,
                request_id=m.RequestId(str(request.request_id)),
                scope=scope,
                question=request.question,
                clock=self._clock,
                new_context_id=self._new_context_id,
            )
            bounds = self._policy.default_query_bounds
            self._evidence.admit(
                context,
                tuple(m.EvidenceRequest(path) for path in paths),
                bounds,
            )
            records = self._evidence.context_observations(context.context_id.value)
            evidence = tuple(self._evidence.context_unit(record) for record in records)
            observation_ids = tuple(record.observation_id.value for record in records)
        except ValueError:
            return None, (), ()
        return (
            context.context_id,
            evidence,
            tuple(m.SourceObservationId(value) for value in observation_ids),
        )

    def _surface_paths(self, surface: m.SurfaceKey) -> tuple[str, ...]:
        if surface.kind is m.SurfaceKind.FILE:
            return (surface.locator,)
        declared = self._store.find_surface(surface)
        return () if declared is None else declared.boundary.paths

    def _context(
        self, request: m.AskRequest, surface: m.SurfaceKey
    ) -> m.InvestigationContextId:
        context = issue_context(
            self._store,
            payload=request,
            repository_id=request.repository_id,
            request_id=m.RequestId(str(request.request_id)),
            scope=m.EvidenceScope(paths=self._surface_paths(surface)),
            question=request.question,
            clock=self._clock,
            new_context_id=self._new_context_id,
        )
        return context.context_id

    def _verification_members(self, surface: m.SurfaceKey) -> tuple[str, ...] | None:
        """The file members the asked surface denotes, or None when unresolvable.

        A file is itself. A symbol is matched through its containing file; a
        symbol identity with no file prefix is excluded explicitly. A declared
        surface denotes its boundary paths and the containing files of its
        declared symbols.
        """
        if surface.kind is m.SurfaceKind.FILE:
            return (surface.locator,)
        if surface.kind is m.SurfaceKind.SYMBOL:
            containing = containment.surface_file_locator(surface.locator)
            return None if containing is None else (containing,)
        declared = self._store.find_surface(surface)
        if declared is None:
            return None
        members = list(declared.boundary.paths)
        for symbol in declared.boundary.symbols:
            containing = containment.surface_file_locator(symbol)
            if containing is not None:
                members.append(containing)
        return tuple(dict.fromkeys(members))

    def _run_scope_covers(
        self,
        scope: m.EvidenceScope,
        repository_id: str,
        members: tuple[str, ...],
    ) -> bool:
        """True when the run's declared scope covers every surface member.

        A run scope path covers a member when it is equal or an ancestor
        (FD-5, FD-17). Declared evidence references are scope members too; a
        reference from another repository cannot cover this surface.
        """
        atoms: list[str] = list(scope.paths)
        for ref in scope.evidence_refs:
            if ref.repository_id != repository_id:
                return False
            atoms.append(containment.surface_file_locator(ref.locator) or ref.locator)
        if not atoms:
            return False
        covered = set(atoms)
        return all(covers_path(member, covered) for member in members)

    def _verification(self, surface: m.SurfaceKey) -> tuple[m.VerificationView, ...]:
        members = self._verification_members(surface)
        if not members:
            return ()
        selected: list[m.VerificationView] = []
        for run in self._store.list_verification_runs(surface.repository_id):
            if not self._run_scope_covers(
                run.scope.scope, surface.repository_id, members
            ):
                continue
            try:
                qualification: m.VerificationSupport | m.SupportUnavailable = (
                    self._support.evaluate_verification(run.run_id.value)
                )
            except (OSError, ValueError) as exc:
                qualification = m.SupportUnavailable(str(exc))
            selected.append(m.VerificationView(run=run, qualification=qualification))
        return tuple(selected)

    def _exact_reference(
        self,
        selector: m.UnderstandingSnapshotSelector | m.ReceiptRetrievalSelector,
    ) -> m.AskResult:
        self._store.require_repository(selector.repository_id)
        if isinstance(selector, m.UnderstandingSnapshotSelector):
            understanding = self._store.get_understanding(selector.understanding_id)
            version_number = (
                understanding.current_version.value
                if selector.version is None
                else selector.version
            )
            version = self._store.get_version(selector.understanding_id, version_number)
            try:
                support: m.UnderstandingSupport | m.SupportUnavailable = (
                    self._support.evaluate_version(
                        selector.understanding_id, version_number
                    )
                )
            except (OSError, ValueError) as exc:
                support = m.SupportUnavailable(str(exc))
            return m.RetrievedUnderstanding(
                understanding=understanding,
                version=version,
                conclusions=self._store.get_version_conclusions(
                    selector.understanding_id, version_number
                ),
                support=support,
                challenges=self._store.get_challenges(selector.understanding_id),
            )
        key = m.RecordingKey(
            repository_id=selector.repository_id,
            request_id=m.RequestId(selector.request_id),
        )
        receipt = self._store.get_receipt(key)
        if receipt is None:
            raise RecordingValidationError(
                f"no receipt for request {selector.request_id!r}"
            )
        context = self._store.find_context_by_request(
            selector.repository_id, m.RequestId(selector.request_id)
        )
        return m.RetrievedReceipt(receipt=receipt, context=context)

    def _evidence_page(self, request: m.AskRequest) -> m.AskResult:
        try:
            cursor = decode_continuation(request.continuation or "")
        except ValueError as exc:
            return m.Unavailable(
                operation="ask",
                failure=str(exc),
                recovery="ask again for the surface; the continuation is invalid",
            )
        if cursor.repository_id != request.repository_id:
            return m.Unavailable(
                operation="ask",
                failure="the continuation belongs to another repository",
                recovery="ask again for this repository",
            )
        context = self._store.find_context_by_id(cursor.context_id)
        if context is None:
            return m.Unavailable(
                operation="ask",
                failure="the continuation context no longer exists",
                recovery="ask again for the surface; the context was reaped",
            )
        if (
            context.repository_id != cursor.repository_id
            or context.request_id != cursor.request_id
            or context.request_digest != cursor.request_digest
        ):
            return m.Unavailable(
                operation="ask",
                failure="the continuation does not match its context",
                recovery="ask again for the surface",
            )
        if context.state is not m.ContextState.LIVE:
            return m.Unavailable(
                operation="ask",
                failure=f"the continuation context is {context.state.value.lower()}",
                recovery="ask again for the surface; the context is no longer live",
            )
        if context.expires_at is not None and context.expires_at < self._clock():
            return m.Unavailable(
                operation="ask",
                failure="the continuation context has expired",
                recovery="ask again for the surface; the context expired",
            )
        records = self._evidence.context_observations(context.context_id.value)
        if cursor.unit_index > len(records):
            return m.Unavailable(
                operation="ask",
                failure="the continuation position is outside its context",
                recovery="ask again for the surface",
            )
        return self._fit_evidence_page(records, cursor)

    def _fit_evidence_page(
        self,
        records: tuple[m.SourceObservation, ...],
        cursor: ContinuationCursor,
    ) -> m.AskResult:
        """Fit one evidence page with its real token and omission list."""
        pages: list[m.EvidenceUnit] = []
        next_index = cursor.unit_index
        next_line = cursor.line_offset
        omitted: list[str] = []
        committed: list[tuple[list[m.EvidenceUnit], list[str], int, int]] = []
        limit = self._policy.max_response_bytes

        def build(
            units: list[m.EvidenceUnit],
            labels: list[str],
            unit_index: int,
            line_offset: int,
        ) -> m.EvidencePage:
            continuation = None
            if unit_index < len(records):
                continuation = encode_continuation(
                    ContinuationCursor(
                        repository_id=cursor.repository_id,
                        context_id=cursor.context_id,
                        request_id=cursor.request_id,
                        request_digest=cursor.request_digest,
                        unit_index=unit_index,
                        line_offset=line_offset,
                    )
                )
            return m.EvidencePage(
                evidence=tuple(units),
                continuation=continuation,
                omitted=tuple(labels),
                truncated=continuation is not None,
            )

        while next_index < len(records):
            record = records[next_index]
            lines = record.excerpt.splitlines(keepends=True)
            if next_line >= len(lines):
                next_index += 1
                next_line = 0
                continue
            remaining = lines[next_line:]
            candidate_unit = _slice_unit(record, next_line, len(remaining))
            candidate = build([*pages, candidate_unit], omitted, next_index + 1, 0)
            if _encoded_size(candidate) <= limit:
                committed.append((list(pages), list(omitted), next_index, next_line))
                pages.append(candidate_unit)
                next_index += 1
                next_line = 0
                continue
            # The whole unit does not fit. Return the largest exact line prefix,
            # measured with the omission it will actually carry and the real
            # continuation token for the position it will actually name.
            fit = 0
            for count in range(1, len(remaining) + 1):
                end = next_line + count
                trial_index = next_index
                trial_line = end
                trial_omitted = list(omitted)
                if end >= len(lines):
                    trial_index += 1
                    trial_line = 0
                else:
                    trial_omitted.append(f"observation:{record.observation_id.value}")
                trial = build(
                    [*pages, _slice_unit(record, next_line, count)],
                    trial_omitted,
                    trial_index,
                    trial_line,
                )
                if _encoded_size(trial) <= limit:
                    fit = count
                else:
                    break
            if fit == 0:
                if pages:
                    omitted.append(f"observation:{record.observation_id.value}")
                    break
                return m.Unavailable(
                    operation="ask",
                    failure=(
                        "one evidence line plus the response envelope exceeds "
                        f"the {limit}-byte budget"
                    ),
                    recovery="ask again with a narrower surface",
                )
            committed.append((list(pages), list(omitted), next_index, next_line))
            pages.append(_slice_unit(record, next_line, fit))
            next_line += fit
            if next_line >= len(lines):
                next_index += 1
                next_line = 0
            else:
                omitted.append(f"observation:{record.observation_id.value}")
            break
        if not pages:
            return m.Unavailable(
                operation="ask",
                failure="the continuation has no remaining evidence",
                recovery="ask again for the surface",
            )
        final = build(pages, omitted, next_index, next_line)
        # The candidate measurements include the real token and omission list;
        # this backstop keeps the final page inside the budget if an unexpected
        # envelope change grows it. Dropping a unit changes the continuation to
        # that unit's start, so the omitted evidence remains recoverable.
        while _encoded_size(final) > limit and committed:
            pages, omitted, next_index, next_line = committed.pop()
            omitted.append(f"observation:{records[next_index].observation_id.value}")
            final = build(pages, omitted, next_index, next_line)
        if not pages:
            return m.Unavailable(
                operation="ask",
                failure=(
                    "the response budget cannot carry the minimum evidence page "
                    f"within {limit} bytes"
                ),
                recovery="ask again with a narrower surface",
            )
        return final

    def _document(
        self,
        request: m.AskRequest,
        surface: m.SurfaceKey,
        understandings: tuple[m.Understanding, ...],
        status: m.SurfaceStatus,
    ) -> m.AskResult:
        grouped: dict[str, list[m.ConclusionView]] = {}
        gaps: list[m.RecordedQuestionGap] = []
        historical: list[m.HistoricalConclusion] = []
        for understanding in understandings:
            support = self._support.evaluate_version(
                understanding.understanding_id.value
            )
            version = self._store.get_version(
                understanding.understanding_id.value,
                understanding.current_version.value,
            )
            gaps.extend(version.gaps)
            revisions = {
                (item.conclusion_id.value, item.revision.value): item
                for item in self._store.get_conclusions(
                    understanding.understanding_id.value
                )
            }
            current = [
                self._view(item, revisions)
                for item in support.conclusions
                if item.evaluation.state is m.SupportState.CURRENT
            ]
            historical.extend(
                self._historical(item, revisions, understanding.current_version)
                for item in support.conclusions
                if item.evaluation.state is not m.SupportState.CURRENT
            )
            if current:
                grouped.setdefault(understanding.question, []).extend(current)
        if not grouped:
            reason = (
                m.GapReason.UNASSESSED
                if not understandings
                else (
                    m.GapReason.INVALIDATED
                    if status.stale
                    else m.GapReason.UNVERIFIABLE
                )
            )
            return m.Gap(
                surface=surface,
                reason=reason,
                recovery=gap_recovery(reason),
                historical=tuple(historical),
                missing=("no current conclusion on this surface",),
            )
        return m.Answer(
            surface=surface,
            status=status,
            groups=tuple(
                m.AnswerGroup(question=question, conclusions=tuple(views))
                for question, views in sorted(grouped.items())
            ),
            gaps=tuple(gaps),
            verification=self._verification(surface),
            context=self._context(request, surface),
        )

    # -- bounded response (FD-54–FD-57) -----------------------------------

    def _fit(self, request: m.AskRequest, result: m.AskResult) -> m.AskResult:
        """Fit one canonical result, stating every omission and refusal."""
        limit = self._policy.max_response_bytes
        if _encoded_size(result) <= limit:
            return result
        if isinstance(result, m.Answer):
            return self._fit_answer(result, limit)
        if isinstance(result, m.Gap):
            return self._fit_gap(result, limit)
        return self._refuse(result, limit)

    def _fit_answer(self, answer: m.Answer, limit: int) -> m.AskResult:
        conclusions = list(answer.conclusions)
        groups = list(answer.groups)
        omitted: list[str] = []
        references = list(answer.references)
        while True:
            if not conclusions and not groups:
                return self._refuse(answer, limit)
            candidate = _replace_answer(
                answer,
                conclusions=tuple(conclusions),
                groups=tuple(groups),
                omitted=tuple(omitted),
                references=tuple(sorted(set(references))),
                truncated=True,
            )
            if _encoded_size(candidate) <= limit:
                return candidate
            if groups:
                group = groups.pop()
                omitted.extend(_group_label(view) for view in group.conclusions)
                references.extend(
                    view.ref.understanding_id.value for view in group.conclusions
                )
                continue
            dropped = conclusions.pop()
            omitted.append(dropped.ref.label)
            references.append(dropped.ref.understanding_id.value)

    def _fit_gap(self, gap: m.Gap, limit: int) -> m.AskResult:
        evidence = list(gap.evidence)
        observations = list(gap.observations)
        historical = list(gap.historical)
        recovery = gap.recovery
        if gap.historical:
            recovery = (
                f"{gap.recovery} For the prior statement, call "
                "ask(selector=UnderstandingSnapshotSelector"
                "{understanding_id, version})."
            )
        omitted: list[str] = []
        while True:
            continuation = None
            if len(evidence) < len(gap.evidence):
                if gap.context is None:
                    return self._refuse(gap, limit)
                context = self._store.find_context_by_id(gap.context.value)
                if context is None:
                    return self._refuse(gap, limit)
                continuation = encode_continuation(
                    ContinuationCursor(
                        repository_id=gap.surface.repository_id,
                        context_id=gap.context.value,
                        request_id=context.request_id,
                        request_digest=context.request_digest,
                        unit_index=len(evidence),
                    )
                )
            candidate = _replace_gap(
                gap,
                evidence=tuple(evidence),
                observations=tuple(observations),
                historical=tuple(historical),
                recovery=recovery,
                omitted=tuple(omitted),
                continuation=continuation,
                truncated=True,
            )
            if _encoded_size(candidate) <= limit:
                return candidate
            if evidence:
                evidence.pop()
                omitted.append(
                    f"observation:{observations.pop().value}"
                    if observations
                    else "admitted evidence"
                )
                continue
            if historical:
                omitted.append(historical.pop().ref.label)
                continue
            return self._refuse(gap, limit)

    def _refuse(self, result: m.AskResult, limit: int) -> m.AskResult:
        """FD-57: refuse rather than return a misleading fragment."""
        return m.Unavailable(
            operation="ask",
            failure=(
                "the server response budget cannot carry the minimum result "
                f"for this surface within {limit} bytes"
            ),
            recovery=("ask for a narrower surface or follow a gap continuation"),
        )


def _replace_answer(
    answer: m.Answer,
    *,
    conclusions: tuple[m.ConclusionView, ...],
    groups: tuple[m.AnswerGroup, ...],
    omitted: tuple[str, ...],
    references: tuple[str, ...],
    truncated: bool,
) -> m.Answer:
    return m.Answer(
        surface=answer.surface,
        status=answer.status,
        question=answer.question,
        conclusions=conclusions,
        groups=groups,
        gaps=answer.gaps,
        verification=answer.verification,
        references=references,
        context=answer.context,
        omitted=omitted,
        truncated=truncated,
    )


def _replace_gap(
    gap: m.Gap,
    *,
    evidence: tuple[m.EvidenceUnit, ...],
    observations: tuple[m.SourceObservationId, ...],
    historical: tuple[m.HistoricalConclusion, ...],
    recovery: str,
    omitted: tuple[str, ...],
    continuation: str | None,
    truncated: bool,
) -> m.Gap:
    return m.Gap(
        surface=gap.surface,
        reason=gap.reason,
        recovery=recovery,
        question=gap.question,
        changed_evidence=gap.changed_evidence,
        historical=historical,
        missing=gap.missing,
        evidence=evidence,
        observations=observations,
        context=gap.context,
        continuation=continuation,
        omitted=omitted,
        truncated=truncated,
    )


def _group_label(view: m.ConclusionView) -> str:
    return view.ref.label


def _slice_unit(
    record: m.SourceObservation,
    line_offset: int,
    line_count: int,
) -> m.EvidenceUnit:
    lines = record.excerpt.splitlines(keepends=True)
    selected = "".join(lines[line_offset : line_offset + line_count])
    start_line = (
        record.delivered_ranges[0].start_line
        if len(record.delivered_ranges) == 1
        else 1
    )
    end_line = start_line + line_offset + line_count - 1
    return m.EvidenceUnit(
        evidence_ref=record.evidence,
        content=selected,
        content_fingerprint=record.content_digest.value.split(":", 1)[1],
        content_range=m.EvidenceLineRange(
            start_line=start_line + line_offset,
            end_line=end_line,
            total_lines=record.total_lines,
        ),
    )
