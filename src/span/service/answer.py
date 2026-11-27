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

import dataclasses as _dataclasses
import datetime as _datetime
import typing as _typing

from span.core import containment
from span.core import model as m
from span.core import support_rules, selection
from span.core.recording import RecordingValidationError
from span.core.rejection import RejectionCauseKind
from span.ports.lifecycle import LifecycleStorePort
from span.service.bounds import (
    DEFAULT_SERVICE_BOUNDS_POLICY,
    encoded_size as _encoded_size,
)
from span.service.contexts import context_binding, issue_context
from span.service.continuation import (
    ContinuationCursor,
    decode_continuation,
    encode_continuation,
)
from span.service.evidence import EvidenceService
from span.service.ids import server_context_id
from span.service.support import SupportService
from span.service.understand import UnderstandService
from span.service.surface_status import compose_surface_status

__all__ = ["AnswerService", "gap_recovery"]

_FunctionalPyramidOrientation = (
    m.FunctionalPyramidView
    | m.FunctionalPyramidUnavailable
    | m.FunctionalPyramidParticipation
)
_FunctionalPyramidOrientationLookup = _typing.Callable[
    [str, m.SurfaceKey, m.EvidenceScope | None],
    _FunctionalPyramidOrientation,
]


def gap_recovery(reason: m.GapReason) -> str:
    """The one fixed remedy for a gap reason (FD-25, A8, TD §9.2).

    The text is server-owned. It names the next action and never ranks or
    describes other questions.
    """
    if reason is m.GapReason.UNASSESSED:
        return "read the cited evidence, then record the conclusion"
    if reason is m.GapReason.PENDING_CURATION:
        return (
            "review the captured exact revision and record actions.curate "
            "when the meaning is stable for shared reuse"
        )
    return "re-read the cited evidence, then record against the current revision"


class AnswerService:
    """Compose one answer, gap, ambiguity, or document view over stored meaning."""

    def __init__(
        self,
        *,
        store: LifecycleStorePort,
        support: SupportService,
        understand: UnderstandService,
        evidence: EvidenceService,
        policy: m.ServiceBoundsPolicy = DEFAULT_SERVICE_BOUNDS_POLICY,
        clock: _typing.Callable[[], _datetime.datetime] | None = None,
        new_context_id: _typing.Callable[[], str] | None = None,
        functional_pyramid_orientation: (
            _FunctionalPyramidOrientationLookup | None
        ) = None,
    ) -> None:
        self._store = store
        self._support = support
        self._understand = understand
        self._evidence = evidence
        self._policy = policy
        self._clock = clock or (lambda: _datetime.datetime.now(_datetime.timezone.utc))
        self._new_context_id = new_context_id or server_context_id
        self._functional_pyramid_orientation = functional_pyramid_orientation

    def ask(self, request: m.AskRequest) -> m.AskResult:
        if request.continuation is not None:
            return self._evidence_page(request)
        selected_question: str | None = None
        selected_understanding: m.Understanding | None = None
        if isinstance(
            request.selector,
            (m.UnderstandingSnapshotSelector, m.ReceiptRetrievalSelector),
        ):
            return self._exact_reference(request.selector)
        if isinstance(request.selector, m.PendingCurationSelector):
            return self._pending_curation(request.selector)
        if isinstance(request.selector, m.RecordedQuestionSelector):
            repository_id = request.selector.repository_id
            selected_question = request.selector.question
            surface = m.SurfaceKey(
                repository_id=repository_id,
                kind=request.selector.surface.kind,
                locator=request.selector.surface.locator,
            )
        elif isinstance(request.selector, m.CurrentUnderstandingSelector):
            repository_id = request.selector.repository_id
            selected_understanding = self._store.find_understanding(
                request.selector.understanding_id
            )
            if selected_understanding is None:
                identity = request.selector.understanding_id
                raise RecordingValidationError(
                    f"unknown understanding: {identity!r}",
                    public_identity=identity,
                    public_cause=f"the exact understanding {identity!r} does not exist",
                )
            if selected_understanding.repository_id != repository_id:
                raise RecordingValidationError(
                    "selected understanding belongs to another repository"
                )
            surface = selected_understanding.surface
            selected_question = selected_understanding.question
        else:
            assert request.repository_id is not None
            repository_id = request.repository_id
            if request.surface is not None:
                surface = m.SurfaceKey(
                    repository_id=repository_id,
                    kind=request.surface.kind,
                    locator=request.surface.locator,
                )
            else:
                if request.reference is None:
                    raise RecordingValidationError(
                        "ask requires a surface or reference"
                    )
                resolved = self._resolve(repository_id, request.reference)
                if isinstance(resolved, m.AmbiguousSurface):
                    return self._fit(request, resolved)
                surface = resolved
        self._store.require_repository(repository_id)
        all_understandings = tuple(self._store.list_understandings(repository_id))
        understandings = (
            (selected_understanding,)
            if selected_understanding is not None
            else tuple(item for item in all_understandings if item.surface == surface)
        )
        if selected_question is not None:
            understandings = tuple(
                item for item in understandings if item.question == selected_question
            )
        subject: m.StatusSubject
        if selected_understanding is not None:
            subject = m.UnderstandingStatusSubject(
                surface,
                selected_understanding.understanding_id,
                selected_understanding.current_version,
            )
        elif selected_question is not None:
            subject = m.QuestionStatusSubject(surface, selected_question)
        else:
            subject = m.SurfaceStatusSubject(surface)
        evaluations = tuple(
            self._support.evaluate_version(
                item.understanding_id.value, item.current_version.value
            )
            for item in understandings
        )
        status = compose_surface_status(
            subject,
            store=self._store,
            support=self._support,
            evidence=self._evidence,
            selected=understandings,
            evaluations=evaluations,
        )
        if selected_question is None:
            functional_pyramid = self._functional_pyramid_projection(
                repository_id,
                surface,
            )
            result = self._document(
                request,
                surface,
                understandings,
                evaluations,
                status,
                functional_pyramid,
            )
            return self._with_admission(request, surface, result)
        return self._question_result(
            request,
            repository_id,
            surface,
            selected_question,
            understandings,
            evaluations,
            status,
        )

    def _question_result(
        self,
        request: m.AskRequest,
        repository_id: str,
        surface: m.SurfaceKey,
        selected_question: str,
        understandings: tuple[m.Understanding, ...],
        evaluations: tuple[m.UnderstandingSupport, ...],
        status: m.SurfaceStatus,
    ) -> m.AskResult:
        matched = understandings
        semantic_scope = self._matched_semantic_scope(matched) if matched else None
        functional_pyramid = self._functional_pyramid_projection(
            repository_id,
            surface,
            semantic_scope,
        )
        if not matched:
            result = self._cold_gap(
                surface,
                status,
                functional_pyramid,
                m.GapReason.UNASSESSED,
                missing=(selected_question,),
            )
            return self._with_admission(request, surface, result)

        current: list[m.ConclusionView] = []
        historical: list[m.HistoricalConclusion] = []
        gaps: list[m.RecordedQuestionGap] = []
        states: list[m.SupportState] = []
        pending = False
        for understanding, support in zip(matched, evaluations, strict=True):
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
                    curated = self._store.find_curation(
                        item.ref,
                        as_of_version=understanding.current_version,
                    )
                    if curated is not None:
                        current.append(self._view(item, revisions))
                    else:
                        pending = True
                else:
                    historical.extend(
                        self._historical(item, revisions, understanding.current_version)
                    )
        if current:
            return self._fit(
                request,
                m.Answer(
                    surface=surface,
                    status=status,
                    functional_pyramid=functional_pyramid,
                    conclusions=tuple(current),
                    gaps=tuple(gaps),
                    verification=self._verification(surface, semantic_scope),
                ),
            )

        combined = support_rules.combine_states(tuple(states))
        reason = (
            m.GapReason.PENDING_CURATION
            if pending
            else (
                m.GapReason.INVALIDATED
                if combined is m.SupportState.REASSESSMENT_REQUIRED
                else m.GapReason.UNVERIFIABLE
            )
        )
        result = m.Gap(
            surface=surface,
            status=status,
            functional_pyramid=functional_pyramid,
            reason=reason,
            recovery=gap_recovery(reason),
            changed_evidence=tuple(
                {
                    ref.evidence_id.value: ref
                    for item in historical
                    for ref in item.evidence
                }.values()
            ),
            historical=tuple(historical),
            missing=(selected_question,),
            source_pointers=self._source_pointers(surface),
        )
        return self._with_admission(request, surface, result)

    def _surface_semantic_scope(self, surface: m.SurfaceKey) -> m.EvidenceScope:
        """Return the semantic scope selected by an ordinary surface obtain."""
        if surface.kind is m.SurfaceKind.FILE:
            return m.EvidenceScope(paths=(surface.locator,))
        if surface.kind is m.SurfaceKind.SYMBOL:
            path = containment.surface_file_locator(surface.locator)
            if path is None:
                raise RecordingValidationError(
                    "selected symbol surface has no canonical owning path"
                )
            return m.EvidenceScope(paths=(path,))
        declared = self._store.find_surface(surface)
        if declared is None:
            raise RecordingValidationError("selected declared surface does not exist")
        semantic_members = (
            *declared.boundary.paths,
            *declared.boundary.symbols,
        )
        if not semantic_members:
            raise RecordingValidationError(
                "selected declared surface has an empty semantic boundary"
            )
        return m.EvidenceScope(paths=semantic_members)

    def _matched_semantic_scope(
        self, understandings: tuple[m.Understanding, ...]
    ) -> m.EvidenceScope:
        """Compose the fixed current scopes selected by an exact semantic obtain."""
        return m.evidence_scope_union(
            self._store.get_version(
                item.understanding_id.value,
                item.current_version.value,
            ).scope
            for item in understandings
        )

    def _functional_pyramid_projection(
        self,
        repository_id: str,
        surface: m.SurfaceKey,
        semantic_scope: m.EvidenceScope | None = None,
    ) -> _FunctionalPyramidOrientation:
        if self._functional_pyramid_orientation is None:
            raise RuntimeError("Functional Pyramid orientation is not configured")
        selected_scope = semantic_scope
        if selected_scope is None:
            try:
                selected_scope = self._surface_semantic_scope(surface)
            except RecordingValidationError:
                selected_scope = None
        return self._functional_pyramid_orientation(
            repository_id,
            surface,
            selected_scope,
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
                candidates=tuple(
                    m.SurfaceReference(kind=item.kind, locator=item.locator)
                    for item in candidates
                ),
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
            support=self._support.qualify_support(support.evaluation),
            evidence=self._evidence_refs(content.support),
        )

    def _historical(
        self,
        support: m.ConclusionSupport,
        revisions: dict[tuple[str, int], m.ConclusionRevision],
        understanding_version: m.UnderstandingVersionNumber,
    ) -> tuple[m.HistoricalConclusion, ...]:
        """Project statement content; withdrawals remain explicit status refs."""
        revision = revisions.get(
            (support.ref.conclusion_id.value, support.ref.revision.value)
        )
        if revision is None:
            raise RecordingValidationError("a historical revision is missing")
        if isinstance(revision.content, m.WithdrawnConclusion):
            return ()
        if not isinstance(revision.content, m.SupportedConclusion):
            raise RecordingValidationError(
                "a historical conclusion has no supported revision content"
            )
        content = revision.content
        return (
            m.HistoricalConclusion(
                ref=support.ref,
                understanding_version=understanding_version,
                statement=content.statement,
                state=support.evaluation.state,
                evidence=self._evidence_refs(content.support),
            ),
        )

    def _evidence_refs(
        self, dependencies: tuple[m.SupportDependency, ...]
    ) -> tuple[m.EvidenceRef, ...]:
        return m.basis_evidence(
            tuple(
                self._support.support_basis(dependency)
                for dependency in dependencies
                if isinstance(
                    dependency, (m.SourceSupport, m.AuthoritySupportDependency)
                )
            )
        )

    def _cold_gap(
        self,
        surface: m.SurfaceKey,
        status: m.SurfaceStatus,
        functional_pyramid: _FunctionalPyramidOrientation,
        reason: m.GapReason,
        *,
        missing: tuple[str, ...] = ("no current conclusion on this surface",),
    ) -> m.Gap:
        return m.Gap(
            surface=surface,
            status=status,
            functional_pyramid=functional_pyramid,
            reason=reason,
            recovery=gap_recovery(reason),
            missing=missing,
            source_pointers=self._source_pointers(surface),
        )

    def _source_pointers(self, surface: m.SurfaceKey) -> tuple[m.EvidenceRequest, ...]:
        return tuple(m.EvidenceRequest(path) for path in self._surface_paths(surface))

    def _with_admission(
        self,
        request: m.AskRequest,
        surface: m.SurfaceKey,
        result: m.Answer | m.Gap,
    ) -> m.AskResult:
        evidence = request.evidence
        if evidence is None:
            return self._fit(request, result)
        repository_id = request.repository_id
        request_id = request.request_id
        assert repository_id is not None
        assert request_id is not None
        context = issue_context(
            self._store,
            binding=context_binding(
                scope=m.EvidenceScope(paths=self._surface_paths(surface)),
                origin=m.ContextOrigin.EVIDENCE_ONLY,
                source_requests=evidence,
            ),
            repository_id=repository_id,
            request_id=m.RequestId(request_id),
            clock=self._clock,
            new_context_id=self._new_context_id,
        )
        admitted = self._evidence.admit(
            context,
            evidence,
            self._policy.default_query_bounds,
        )
        records = {
            record.observation_id: record
            for record in self._evidence.context_observations(context.context_id.value)
        }
        deliveries: list[m.EvidenceDelivery] = []
        seen: set[m.SourceObservationId] = set()
        for outcome in admitted.outcomes:
            if not isinstance(outcome, (m.AdmittedEvidence, m.AlreadyAdmittedEvidence)):
                continue
            if outcome.observation_id in seen or outcome.observation_id not in records:
                continue
            seen.add(outcome.observation_id)
            deliveries.extend(
                self._evidence.context_deliveries(records[outcome.observation_id])
            )
        omitted = tuple(
            outcome.request.locator
            for outcome in admitted.outcomes
            if isinstance(outcome, m.OmittedEvidence)
        )
        context_ref = m.InvestigationContextRef(
            repository_id=context.repository_id,
            context_id=context.context_id,
        )
        full_view = m.EvidenceAdmissionView(
            context=context_ref,
            outcomes=admitted.outcomes,
            deliveries=tuple(deliveries),
            continuation=None,
            omitted=omitted,
            truncated=False,
        )
        full_result = _dataclasses.replace(result, admission=full_view)
        if _encoded_size(full_result) <= self._policy.max_response_bytes:
            return full_result
        continuation = (
            encode_continuation(
                ContinuationCursor(
                    repository_id=context.repository_id,
                    context_id=context.context_id.value,
                    request_id=context.request_id,
                    binding_digest=context.binding_digest,
                )
            )
            if deliveries
            else None
        )
        deferred_view = m.EvidenceAdmissionView(
            context=context_ref,
            outcomes=admitted.outcomes,
            deliveries=(),
            continuation=continuation,
            omitted=omitted + tuple(_delivery_label(item) for item in deliveries),
            truncated=continuation is not None,
        )
        return self._fit(request, _dataclasses.replace(result, admission=deferred_view))

    def _surface_paths(self, surface: m.SurfaceKey) -> tuple[str, ...]:
        if surface.kind is m.SurfaceKind.FILE:
            return (surface.locator,)
        declared = self._store.find_surface(surface)
        return () if declared is None else declared.boundary.paths

    def _verification(
        self, surface: m.SurfaceKey, semantic_scope: m.EvidenceScope | None = None
    ) -> tuple[m.VerificationView, ...]:
        if (
            surface.kind is m.SurfaceKind.SYMBOL
            and containment.surface_file_locator(surface.locator) is None
        ):
            return ()
        if semantic_scope is None:
            try:
                semantic_scope = self._surface_semantic_scope(surface)
            except RecordingValidationError:
                return ()
        candidates: list[m.VerificationView] = []
        for run in self._store.list_verification_runs(surface.repository_id):
            if not selection.verification_covers(
                run, surface.repository_id, semantic_scope
            ):
                continue
            try:
                detailed = self._support.evaluate_verification(run.facts.run_id.value)
                qualification: m.VerificationQualification | m.SupportUnavailable = (
                    self._support.qualify_verification(detailed)
                )
            except (OSError,) + self._store.operational_errors:
                qualification = m.SupportUnavailable(
                    "verification support evaluation is unavailable"
                )
            candidates.append(m.VerificationView.from_run(run, qualification))
        selected, _history = selection.select_verification(tuple(candidates))
        return selected

    def _exact_reference(
        self,
        selector: m.UnderstandingSnapshotSelector | m.ReceiptRetrievalSelector,
    ) -> m.AskResult:
        if isinstance(selector, m.UnderstandingSnapshotSelector):
            return self._understand.snapshot(selector)
        return self._understand.receipt(selector)

    def _pending_curation(
        self,
        selector: m.PendingCurationSelector,
    ) -> m.AskResult:
        """Return one deterministic repository-local page of CURRENT captures."""
        self._store.require_repository(selector.repository_id)
        eligible = tuple(
            item
            for item in self._store.pending_curation_candidates(
                selector.repository_id,
                after=selector.after,
            )
            if self._support.evaluate_revision(item.ref).state is m.SupportState.CURRENT
        )
        if not eligible:
            return m.PendingCuration(repository_id=selector.repository_id, items=())

        count_limit = self._policy.default_query_bounds.max_results
        items = list(eligible[:count_limit])
        truncated = len(items) < len(eligible)
        response_limit = self._policy.max_response_bytes

        def build() -> m.PendingCuration:
            omitted_count = len(eligible) - len(items)
            return m.PendingCuration(
                repository_id=selector.repository_id,
                items=tuple(items),
                next_after=items[-1].ref if truncated else None,
                omitted=(
                    (f"{omitted_count} additional pending curation items",)
                    if truncated and omitted_count
                    else ()
                ),
                truncated=truncated,
            )

        result = build()
        while items and _encoded_size(result) > response_limit:
            items.pop()
            truncated = True
            if not items:
                break
            result = build()
        if items:
            return result
        return m.Unavailable(
            operation="ask",
            failure=(
                "one pending-curation item plus the response envelope exceeds "
                f"the {response_limit}-byte budget"
            ),
            recovery=(
                "use a server configuration with a response budget large enough "
                "to carry one exact pending-curation reference"
            ),
        )

    def _evidence_page(self, request: m.AskRequest) -> m.AskResult:
        try:
            cursor = decode_continuation(request.continuation or "")
        except ValueError:
            raise RecordingValidationError.continuation_invalid(
                "the continuation is malformed"
            ) from None
        context = self._store.find_context_by_id(cursor.context_id)
        if context is None:
            raise RecordingValidationError.continuation_invalid(
                "the continuation context is unavailable"
            )
        if (
            context.repository_id != cursor.repository_id
            or context.request_id != cursor.request_id
            or context.binding_digest != cursor.binding_digest
        ):
            raise RecordingValidationError.continuation_invalid(
                "the continuation does not match its context"
            )
        if context.state is not m.ContextState.LIVE:
            raise RecordingValidationError.continuation_invalid(
                "the continuation context is not live"
            )
        if context.expires_at is not None and context.expires_at < self._clock():
            raise RecordingValidationError.continuation_invalid(
                "the continuation context is expired"
            )
        try:
            deliveries = tuple(
                delivery
                for record in self._evidence.context_observations(
                    context.context_id.value
                )
                for delivery in self._evidence.context_deliveries(record)
            )
        except RecordingValidationError as exc:
            if exc.cause_kind is RejectionCauseKind.SOURCE_DRIFT:
                raise RecordingValidationError.continuation_invalid(
                    "the admitted evidence changed; start a new admission"
                ) from None
            raise
        if cursor.unit_index > len(deliveries):
            raise RecordingValidationError.continuation_invalid(
                "the continuation position is outside its context"
            )
        return self._fit_evidence_page(deliveries, cursor)

    def _fit_evidence_page(
        self,
        deliveries: tuple[m.EvidenceDelivery, ...],
        cursor: ContinuationCursor,
    ) -> m.AskResult:
        """Fit one evidence page while preserving exact original positions."""
        pages: list[m.EvidenceDelivery] = []
        next_index = cursor.unit_index
        next_line = cursor.line_offset
        omitted: list[str] = []
        committed: list[tuple[list[m.EvidenceDelivery], list[str], int, int]] = []
        limit = self._policy.max_response_bytes

        def build(
            values: list[m.EvidenceDelivery],
            labels: list[str],
            unit_index: int,
            line_offset: int,
        ) -> m.EvidencePage:
            continuation = None
            if unit_index < len(deliveries):
                continuation = encode_continuation(
                    ContinuationCursor(
                        repository_id=cursor.repository_id,
                        context_id=cursor.context_id,
                        request_id=cursor.request_id,
                        binding_digest=cursor.binding_digest,
                        unit_index=unit_index,
                        line_offset=line_offset,
                    )
                )
            return m.EvidencePage(
                deliveries=tuple(values),
                continuation=continuation,
                omitted=tuple(labels),
                truncated=continuation is not None,
            )

        while next_index < len(deliveries):
            delivery = deliveries[next_index]
            lines = delivery.unit.content.splitlines(keepends=True)
            if next_line >= len(lines):
                next_index += 1
                next_line = 0
                continue
            remaining = lines[next_line:]
            candidate_delivery = _slice_delivery(delivery, next_line, len(remaining))
            candidate = build([*pages, candidate_delivery], omitted, next_index + 1, 0)
            if _encoded_size(candidate) <= limit:
                committed.append((list(pages), list(omitted), next_index, next_line))
                pages.append(candidate_delivery)
                next_index += 1
                next_line = 0
                continue
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
                    trial_omitted.append(_delivery_label(delivery))
                trial = build(
                    [*pages, _slice_delivery(delivery, next_line, count)],
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
                    omitted.append(_delivery_label(delivery))
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
            pages.append(_slice_delivery(delivery, next_line, fit))
            next_line += fit
            if next_line >= len(lines):
                next_index += 1
                next_line = 0
            else:
                omitted.append(_delivery_label(delivery))
            break
        if not pages:
            raise RecordingValidationError.continuation_invalid(
                "the continuation has no remaining evidence"
            )
        final = build(pages, omitted, next_index, next_line)
        while _encoded_size(final) > limit and committed:
            pages, omitted, next_index, next_line = committed.pop()
            omitted.append(_delivery_label(deliveries[next_index]))
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
        evaluations: tuple[m.UnderstandingSupport, ...],
        status: m.SurfaceStatus,
        functional_pyramid: _FunctionalPyramidOrientation,
    ) -> m.Answer | m.Gap:
        grouped: dict[str, list[m.ConclusionView]] = {}
        gaps: list[m.RecordedQuestionGap] = []
        historical: list[m.HistoricalConclusion] = []
        for understanding, support in zip(understandings, evaluations, strict=True):
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
                and self._store.find_curation(
                    item.ref,
                    as_of_version=understanding.current_version,
                )
                is not None
            ]
            historical.extend(
                content
                for item in support.conclusions
                if item.evaluation.state is not m.SupportState.CURRENT
                for content in self._historical(
                    item, revisions, understanding.current_version
                )
            )
            if current:
                grouped.setdefault(understanding.question, []).extend(current)
        if not grouped:
            reason = (
                m.GapReason.UNASSESSED
                if not understandings
                else (
                    m.GapReason.PENDING_CURATION
                    if status.pending
                    else (
                        m.GapReason.INVALIDATED
                        if status.stale
                        else m.GapReason.UNVERIFIABLE
                    )
                )
            )
            return m.Gap(
                surface=surface,
                reason=reason,
                status=status,
                functional_pyramid=functional_pyramid,
                recovery=gap_recovery(reason),
                historical=tuple(historical),
                missing=("no current conclusion on this surface",),
                source_pointers=self._source_pointers(surface),
            )
        return m.Answer(
            surface=surface,
            status=status,
            functional_pyramid=functional_pyramid,
            groups=tuple(
                m.AnswerGroup(question=question, conclusions=tuple(views))
                for question, views in sorted(grouped.items())
            ),
            gaps=tuple(gaps),
            verification=self._verification(surface),
        )

    # -- bounded response (FD-54–FD-57) -----------------------------------

    def _fit(self, request: m.AskRequest, result: m.AskResult) -> m.AskResult:
        """Fit one canonical result, stating every omission and refusal."""
        limit = self._policy.max_response_bytes
        if _encoded_size(result) <= limit:
            return result
        trimmed = self._fit_functional_pyramid(result, limit)
        if trimmed is not None:
            return trimmed
        if isinstance(result, m.Answer):
            return self._fit_answer(result, limit)
        if isinstance(result, m.Gap):
            return self._fit_gap(result, limit)
        return self._refuse(result, limit)

    def _fit_functional_pyramid(
        self, result: m.AskResult, limit: int
    ) -> m.AskResult | None:
        """Bound the governing document list, never its unresolved state.

        Placements are ordered P0 through P4, so the largest fitting prefix
        keeps the foundational layers. The omission is one constant-size
        statement, not one entry per document, so naming what was dropped
        cannot itself exhaust the budget (FD-55–FD-57). `unresolved` is never
        dropped.
        """
        if not isinstance(result, (m.Answer, m.Gap)):
            return None
        view = result.functional_pyramid
        if not isinstance(view, m.FunctionalPyramidView) or not view.placements:
            return None
        total = len(view.placements)

        def candidate(kept: int) -> m.AskResult:
            dropped = total - kept
            omitted: tuple[str, ...] = ()
            if dropped:
                omitted = (
                    f"{dropped} trailing governing document placements omitted "
                    "beyond the response budget",
                )
            return _dataclasses.replace(
                result,
                functional_pyramid=_dataclasses.replace(
                    view,
                    placements=view.placements[:kept],
                    truncated=bool(omitted),
                    omitted=omitted,
                ),
                truncated=bool(result.omitted) or bool(omitted),
                omitted=tuple(result.omitted) + omitted,
            )

        if _encoded_size(candidate(total)) <= limit:
            return candidate(total)
        low, high = 0, total - 1
        best: m.AskResult | None = None
        while low <= high:
            middle = (low + high) // 2
            built = candidate(middle)
            if _encoded_size(built) <= limit:
                best = built
                low = middle + 1
            else:
                high = middle - 1
        return best

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
                group = groups[-1]
                dropped = group.conclusions[-1]
                remaining = group.conclusions[:-1]
                if remaining:
                    groups[-1] = _dataclasses.replace(group, conclusions=remaining)
                else:
                    groups.pop()
                omitted.append(_group_label(dropped))
                references.append(dropped.ref.understanding_id.value)
                continue
            dropped = conclusions.pop()
            omitted.append(dropped.ref.label)
            references.append(dropped.ref.understanding_id.value)

    def _fit_gap(self, gap: m.Gap, limit: int) -> m.AskResult:
        historical = list(gap.historical)
        source_pointers = list(gap.source_pointers)
        omitted = list(gap.omitted)
        candidate = gap
        recovery = gap.recovery
        while _encoded_size(candidate) > limit and historical:
            omitted.append(historical.pop().ref.label)
            if "UnderstandingSnapshotSelector" not in recovery:
                recovery += (
                    "; retrieve omitted historical content with "
                    "UnderstandingSnapshotSelector{repository_id, "
                    "understanding_id, version}"
                )
            candidate = _dataclasses.replace(
                gap,
                historical=tuple(historical),
                omitted=tuple(omitted),
                recovery=recovery,
                truncated=True,
            )
        if _encoded_size(candidate) > limit and source_pointers:
            omitted.extend(pointer.locator for pointer in source_pointers)
            source_pointers.clear()
            recovery += "; omitted pointers: EvidenceRequest"
            candidate = _dataclasses.replace(
                candidate,
                source_pointers=(),
                omitted=tuple(omitted),
                recovery=recovery,
                truncated=True,
            )
        if _encoded_size(candidate) <= limit:
            return candidate
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
        functional_pyramid=answer.functional_pyramid,
        conclusions=conclusions,
        groups=groups,
        gaps=answer.gaps,
        verification=answer.verification,
        references=references,
        admission=answer.admission,
        omitted=omitted,
        truncated=truncated,
    )


def _group_label(view: m.ConclusionView) -> str:
    return view.ref.label


def _delivery_label(delivery: m.EvidenceDelivery) -> str:
    content_range = delivery.unit.content_range
    if content_range is None:
        return f"observation:{delivery.observation_id.value}"
    return (
        f"observation:{delivery.observation_id.value}:"
        f"lines:{content_range.start_line}-{content_range.end_line}"
    )


def _slice_delivery(
    delivery: m.EvidenceDelivery,
    line_offset: int,
    line_count: int,
) -> m.EvidenceDelivery:
    unit = delivery.unit
    lines = unit.content.splitlines(keepends=True)
    selected = "".join(lines[line_offset : line_offset + line_count])
    base_line = unit.content_range.start_line if unit.content_range is not None else 1
    total_lines = (
        unit.content_range.total_lines if unit.content_range is not None else len(lines)
    )
    return m.EvidenceDelivery(
        observation_id=delivery.observation_id,
        unit=m.EvidenceUnit(
            evidence_ref=unit.evidence_ref,
            content=selected,
            content_fingerprint=unit.content_fingerprint,
            content_range=m.EvidenceLineRange(
                start_line=base_line + line_offset,
                end_line=base_line + line_offset + line_count - 1,
                total_lines=total_lines,
            ),
        ),
    )
