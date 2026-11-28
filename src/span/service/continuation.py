"""Stateless continuation tokens over the existing context lifecycle.

A continuation binds one repository, investigation context, request binding,
and the next evidence position. It introduces no table, TTL, or reaper: it is
valid exactly while its context is live. The token is opaque to the host and
server-decodable; the store remains the owner of context expiry and reaping.
"""

from __future__ import annotations

import base64 as _base64
import dataclasses as _dataclasses
import datetime as _datetime
import json as _json
import typing as _typing
from dataclasses import dataclass as _dataclass

from span.core import model as m
from span.core.model import ContentDigest, RequestId
from span.core.paging import largest_fitting_prefix
from span.core.recording import RecordingValidationError
from span.core.rejection import RejectionCauseKind
from span.ports.functional_pyramid import FunctionalPyramidStatePort
from span.service.bounds import encoded_size
from span.service.ids import server_cursor_id, server_selection_id
from span.core.model.primitives import _require_non_empty

__all__ = [
    "ContinuationCursor",
    "decode_continuation",
    "encode_continuation",
    "ContinuationService",
    "is_bound_delivery",
]

_PREFIX = "span1_"


@_dataclass(frozen=True)
class ContinuationCursor:
    """The exact position a continuation resumes from."""

    repository_id: str
    context_id: str
    request_id: RequestId
    binding_digest: ContentDigest
    unit_index: int = 0
    line_offset: int = 0

    def __post_init__(self) -> None:
        _require_non_empty("ContinuationCursor.repository_id", self.repository_id)
        _require_non_empty("ContinuationCursor.context_id", self.context_id)
        if self.unit_index < 0 or self.line_offset < 0:
            raise ValueError("continuation positions are non-negative")
        if self.line_offset and self.unit_index < 0:
            raise ValueError("a line offset requires a unit index")


def encode_continuation(cursor: ContinuationCursor) -> str:
    payload = {
        "v": 1,
        "r": cursor.repository_id,
        "c": cursor.context_id,
        "q": cursor.request_id.value,
        "d": cursor.binding_digest.value,
        "i": cursor.unit_index,
        "l": cursor.line_offset,
    }
    raw = _json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _PREFIX + _base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_continuation(token: str) -> ContinuationCursor:
    _require_non_empty("continuation", token)
    if not token.startswith(_PREFIX):
        raise ValueError("unknown continuation token")
    encoded = token[len(_PREFIX) :]
    padding = "=" * (-len(encoded) % 4)
    try:
        raw = _base64.urlsafe_b64decode(encoded + padding)
        payload = _json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise ValueError("malformed continuation token") from exc
    if not isinstance(payload, dict) or payload.get("v") != 1:
        raise ValueError("unsupported continuation version")
    required = ("r", "c", "q", "d", "i", "l")
    if any(key not in payload for key in required):
        raise ValueError("incomplete continuation token")
    values = [payload[key] for key in required]
    if not all(isinstance(value, (str, int)) for value in values):
        raise ValueError("malformed continuation token")
    if isinstance(payload["i"], bool) or isinstance(payload["l"], bool):
        raise ValueError("malformed continuation token")
    return ContinuationCursor(
        repository_id=payload["r"],
        context_id=payload["c"],
        request_id=RequestId(payload["q"]),
        binding_digest=ContentDigest(payload["d"]),
        unit_index=payload["i"],
        line_offset=payload["l"],
    )


_GovernanceResult = (
    m.FunctionalPyramidView
    | m.FunctionalPyramidStatus
    | m.FunctionalPyramidCandidate
    | m.RetrievedFunctionalPyramidReceipt
)
_BoundCursor = tuple[m.DeliverySelection, m.DeliveryPosition]


def is_bound_delivery(token: str) -> bool:
    """Route an issued opaque delivery ID without decoding semantic data."""
    return token.startswith("cur-srv-")


def _binding(
    selector: m.GovernanceReadSelector, result: _GovernanceResult
) -> m.GovernanceReadBinding:
    if isinstance(selector, m.FunctionalPyramidDirectorySelector) and isinstance(
        result, m.FunctionalPyramidView
    ):
        assert result.resolved_repository_id is not None
        return m.DirectoryReadBinding(
            selector,
            result.resolved_repository_id,
            result.placements,
            len(result.unresolved),
        )
    if isinstance(selector, m.FunctionalPyramidSelector) and isinstance(
        result, m.FunctionalPyramidStatus
    ):
        if result.pyramid_id is None or result.version is None:
            raise ValueError("inactive status has no pageable selection")
        return m.PyramidStatusReadBinding(
            selector,
            result.pyramid_id,
            result.version,
            result.member_repository_ids,
            len(result.findings),
        )
    if isinstance(selector, m.FunctionalPyramidCandidateSelector) and isinstance(
        result, m.FunctionalPyramidCandidate
    ):
        return m.PyramidCandidateReadBinding(
            selector,
            result.version,
            len(result.validation_findings),
            len(result.graph_findings),
        )
    if isinstance(selector, m.FunctionalPyramidReceiptSelector) and isinstance(
        result, m.RetrievedFunctionalPyramidReceipt
    ):
        historical = isinstance(
            result.dependency_effects, m.HistoricalAcceptanceDetailUnavailable
        )
        return m.PyramidReceiptReadBinding(
            selector,
            result.member_repository_ids,
            len(result.member_declaration_refs),
            len(result.participation_effects),
            len(_receipt_effects(result)),
            historical,
        )
    raise ValueError("result does not belong to the supplied exact selector")


def _result_kind(binding: m.GovernanceReadBinding) -> m.ResultKind:
    if isinstance(binding, m.DirectoryReadBinding):
        return m.ResultKind.FUNCTIONAL_PYRAMID_VIEW
    if isinstance(binding, m.PyramidStatusReadBinding):
        return m.ResultKind.FUNCTIONAL_PYRAMID_STATUS
    if isinstance(binding, m.PyramidReceiptReadBinding):
        return m.ResultKind.RETRIEVED_FUNCTIONAL_PYRAMID_RECEIPT
    return m.ResultKind.FUNCTIONAL_PYRAMID_CANDIDATE


def _total(selection: m.DeliverySelection) -> int:
    return sum(count for _, count in m.delivery_extents(selection.binding))


def _omission(selection: m.DeliverySelection, delivered: int) -> tuple[str, ...]:
    position = m.delivery_position(selection, delivered)
    if position is None:
        return ()
    remaining = _total(selection) - delivered
    return (f"{position.collection.value}: {remaining} remaining selected items",)


def _recovery(binding: m.GovernanceReadBinding) -> str:
    selector = binding.selector
    if isinstance(selector, m.FunctionalPyramidDirectorySelector):
        return (
            "Repeat FunctionalPyramidDirectorySelector with repository_id="
            f"{selector.repository_id!r}, directory={selector.directory!r}, "
            "and no after token"
        )
    if isinstance(selector, m.FunctionalPyramidSelector):
        coordinate = (
            f"repository_id={selector.repository_id!r}"
            if selector.repository_id is not None
            else (
                f"pyramid_id={selector.pyramid_id.value!r}"
                if selector.pyramid_id
                else "the original identity"
            )
        )
        return f"Repeat FunctionalPyramidSelector with {coordinate}"
    if isinstance(selector, m.FunctionalPyramidReceiptSelector):
        return f"Repeat FunctionalPyramidReceiptSelector with request_id={selector.request_id.value!r}"
    return (
        f"Repeat the original FunctionalPyramidCandidateSelector for {selector.action.value} "
        "with the same target version and member intents"
    )


def _unavailable(
    selection: m.DeliverySelection, delivered: int
) -> m.FunctionalPyramidUnavailable:
    position = m.delivery_position(selection, delivered)
    coordinate = (
        "initial result envelope"
        if position is None
        else f"{position.collection.value}[{position.offset}]"
    )
    return m.FunctionalPyramidUnavailable(
        failure=f"Response budget cannot carry the required unit {coordinate}",
        recovery=(
            f"{_recovery(selection.binding)} with a narrower existing selection "
            "where applicable; otherwise report the named indivisible delivery blocker"
        ),
    )


def _receipt_effects(
    result: m.RetrievedFunctionalPyramidReceipt,
) -> tuple[m.AcceptedDependencyEffect, ...] | tuple[m.ConclusionRevisionRef, ...]:
    effects = result.dependency_effects
    if isinstance(effects, m.AcceptedDependencyEffects):
        return effects.effects
    return effects.dependent_effect_refs


def _receipt_prefix(
    result: m.RetrievedFunctionalPyramidReceipt, count: int
) -> m.RetrievedFunctionalPyramidReceipt:
    members = result.member_repository_ids[:count]
    count = max(0, count - len(result.member_repository_ids))
    declarations = result.member_declaration_refs[:count]
    count = max(0, count - len(result.member_declaration_refs))
    participation = result.participation_effects[:count]
    count = max(0, count - len(result.participation_effects))
    effects = result.dependency_effects
    if isinstance(effects, m.AcceptedDependencyEffects):
        effects = _dataclasses.replace(effects, effects=effects.effects[:count])
    else:
        effects = _dataclasses.replace(
            effects, dependent_effect_refs=effects.dependent_effect_refs[:count]
        )
    return _dataclasses.replace(
        result,
        member_repository_ids=members,
        member_declaration_refs=declarations,
        participation_effects=participation,
        dependency_effects=effects,
    )


def _initial_prefix(
    result: _GovernanceResult,
    selection: m.DeliverySelection,
    count: int,
    cursor: str,
) -> _GovernanceResult:
    if count == _total(selection):
        return result
    omitted = _omission(selection, count)
    if isinstance(result, m.FunctionalPyramidView):
        return _dataclasses.replace(
            result,
            placements=result.placements[:count],
            unresolved=result.unresolved[: max(0, count - len(result.placements))],
            selection_id=selection.selection_id,
            next_after=cursor,
            omitted=omitted,
            truncated=True,
        )
    if isinstance(result, m.FunctionalPyramidStatus):
        return _dataclasses.replace(
            result,
            member_repository_ids=result.member_repository_ids[:count],
            findings=result.findings[
                : max(0, count - len(result.member_repository_ids))
            ],
            selection_id=selection.selection_id,
            continuation=cursor,
            omitted=omitted,
            truncated=True,
        )
    if isinstance(result, m.RetrievedFunctionalPyramidReceipt):
        marked = _dataclasses.replace(
            result,
            selection_id=selection.selection_id,
            continuation=cursor,
            omitted=omitted,
            truncated=True,
        )
        return _receipt_prefix(marked, count)
    return _dataclasses.replace(
        result,
        validation_findings=result.validation_findings[:count],
        graph_findings=result.graph_findings[
            : max(0, count - len(result.validation_findings))
        ],
        selection_id=selection.selection_id,
        continuation=cursor,
        omitted=omitted,
        truncated=True,
    )


def _part(
    result: _GovernanceResult, position: m.DeliveryPosition, count: int
) -> m.ResultPart:
    start, end = position.offset, position.offset + count
    collection = position.collection
    if isinstance(result, m.FunctionalPyramidView):
        if collection is m.DeliveryCollection.PLACEMENTS:
            return m.PlacementsPart(
                start, len(result.placements), result.placements[start:end]
            )
        if collection is m.DeliveryCollection.UNRESOLVED:
            return m.UnresolvedPart(
                start, len(result.unresolved), result.unresolved[start:end]
            )
    if isinstance(result, m.FunctionalPyramidStatus):
        if collection is m.DeliveryCollection.MEMBER_REPOSITORY_IDS:
            return m.MemberRepositoryIdsPart(
                start,
                len(result.member_repository_ids),
                result.member_repository_ids[start:end],
            )
        if collection is m.DeliveryCollection.STATUS_FINDINGS:
            return m.StatusFindingsPart(
                start, len(result.findings), result.findings[start:end]
            )
    if isinstance(result, m.FunctionalPyramidCandidate):
        if collection is m.DeliveryCollection.VALIDATION_FINDINGS:
            return m.ValidationFindingsPart(
                start,
                len(result.validation_findings),
                result.validation_findings[start:end],
            )
        if collection is m.DeliveryCollection.GRAPH_FINDINGS:
            return m.GraphFindingsPart(
                start,
                len(result.graph_findings),
                result.graph_findings[start:end],
            )
    if isinstance(result, m.RetrievedFunctionalPyramidReceipt):
        return _receipt_part(result, position, count)
    raise ValueError("collection does not belong to the bound result")


def _receipt_part(
    result: m.RetrievedFunctionalPyramidReceipt,
    position: m.DeliveryPosition,
    count: int,
) -> m.ResultPart:
    start, end = position.offset, position.offset + count
    collection = position.collection
    if collection is m.DeliveryCollection.MEMBER_REPOSITORY_IDS:
        items = result.member_repository_ids
        return m.MemberRepositoryIdsPart(start, len(items), items[start:end])
    if collection is m.DeliveryCollection.MEMBER_DECLARATION_REFS:
        refs = result.member_declaration_refs
        return m.MemberDeclarationRefsPart(start, len(refs), refs[start:end])
    if collection is m.DeliveryCollection.PARTICIPATION_EFFECTS:
        participation = result.participation_effects
        return m.ParticipationEffectsPart(
            start, len(participation), participation[start:end]
        )
    parent = (m.FunctionalPyramidReceiptSelector(result.request_id),)
    effects = result.dependency_effects
    if isinstance(effects, m.AcceptedDependencyEffects):
        if collection is m.DeliveryCollection.ACCEPTED_DEPENDENCY_EFFECTS:
            return m.AcceptedDependencyEffectsPart(
                parent, start, len(effects.effects), effects.effects[start:end]
            )
    elif collection is m.DeliveryCollection.DEPENDENT_EFFECT_REFS:
        dependent = effects.dependent_effect_refs
        return m.DependentEffectRefsPart(
            parent, start, len(dependent), dependent[start:end]
        )
    raise ValueError("collection does not belong to the accepted receipt")


class ContinuationService:
    """Bind and fit public semantic selections at the existing installation owner."""

    def __init__(
        self,
        state: FunctionalPyramidStatePort,
        clock: _typing.Callable[[], _datetime.datetime],
    ) -> None:
        self._state = state
        self._clock = clock

    @staticmethod
    def stale(selection: m.DeliverySelection) -> RecordingValidationError:
        return RecordingValidationError(
            "the bound selection is no longer current",
            cause_kind=RejectionCauseKind.CONTINUATION_INVALID,
            public_identity=selection.selection_id,
            public_cause=f"The bound selection is stale or expired. {_recovery(selection.binding)}",
        )

    def load(
        self,
        cursor_id: str,
        selector: m.FunctionalPyramidDirectorySelector | None = None,
    ) -> _BoundCursor:
        bound = self._state.load_delivery_cursor(cursor_id)
        if bound is None:
            raise RecordingValidationError.continuation_invalid(
                "the delivery cursor was not issued"
            )
        selection, position = bound
        if (
            self._clock() >= selection.expires_at
            or position.state_fingerprint != selection.state_fingerprint
            or (selector is not None and selector != selection.binding.selector)
        ):
            raise self.stale(selection)
        return bound

    def initial(
        self,
        selector: m.GovernanceReadSelector,
        result: _GovernanceResult,
        fingerprint: m.ContentDigest,
        limit: int,
    ) -> _GovernanceResult | m.FunctionalPyramidUnavailable:
        if encoded_size(result) <= limit:
            return result
        now = self._clock()
        selection = m.DeliverySelection(
            selection_id=server_selection_id(),
            created_at=now,
            expires_at=now + self._state.retention.context_lifetime,
            state_fingerprint=fingerprint,
            binding=_binding(selector, result),
        )
        cursor_id = server_cursor_id()
        count = largest_fitting_prefix(
            _total(selection),
            lambda n: n > 0
            and encoded_size(_initial_prefix(result, selection, n, cursor_id)) <= limit,
        )
        if not count:
            return _unavailable(selection, 0)
        position = m.delivery_position(selection, count)
        if position is None:
            return result
        candidate = _initial_prefix(result, selection, count, cursor_id)
        with self._state.transaction() as transaction:
            transaction.write_delivery_selection(selection)
            issued = transaction.issue_delivery_cursor(
                selection.selection_id, position, cursor_id
            )
        if isinstance(candidate, m.FunctionalPyramidView):
            return _dataclasses.replace(candidate, next_after=issued)
        return _dataclasses.replace(candidate, continuation=issued)

    def resume(
        self,
        bound: _BoundCursor,
        result: _GovernanceResult,
        fingerprint: m.ContentDigest,
        limit: int,
    ) -> m.ResultPage | m.FunctionalPyramidUnavailable:
        selection, position = bound
        if (
            fingerprint != selection.state_fingerprint
            or self._clock() >= selection.expires_at
            or _binding(selection.binding.selector, result) != selection.binding
        ):
            raise self.stale(selection)
        try:
            delivered, remaining = m.delivery_offset(selection, position)
        except ValueError as exc:
            raise self.stale(selection) from exc
        cursor_id = server_cursor_id()

        def build(count: int) -> m.ResultPage:
            omitted = _omission(selection, delivered + count)
            return m.ResultPage(
                selection_id=selection.selection_id,
                result_kind=_result_kind(selection.binding),
                parts=(_part(result, position, count),),
                continuation=cursor_id if omitted else None,
                omitted=omitted,
                truncated=bool(omitted),
            )

        count = largest_fitting_prefix(
            remaining, lambda n: n > 0 and encoded_size(build(n)) <= limit
        )
        if not count:
            return _unavailable(selection, delivered)
        candidate = build(count)
        next_position = m.delivery_position(selection, delivered + count)
        if next_position is None:
            return candidate
        with self._state.transaction() as transaction:
            issued = transaction.issue_delivery_cursor(
                selection.selection_id, next_position, cursor_id
            )
        return _dataclasses.replace(candidate, continuation=issued)
