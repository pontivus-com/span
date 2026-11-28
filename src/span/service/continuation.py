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


_DirectoryCursor = tuple[m.DirectoryDeliverySelection, m.DeliveryPosition]


def is_bound_delivery(token: str) -> bool:
    """Route an issued opaque delivery ID without decoding semantic data."""
    return token.startswith("cur-srv-")


def _directory_position(
    selection: m.DirectoryDeliverySelection, delivered: int
) -> m.DeliveryPosition | None:
    placements = len(selection.placements)
    if delivered < placements:
        return m.DeliveryPosition(
            m.DeliveryCollection.PLACEMENTS, delivered, selection.state_fingerprint
        )
    if delivered < placements + selection.unresolved_count:
        return m.DeliveryPosition(
            m.DeliveryCollection.UNRESOLVED,
            delivered - placements,
            selection.state_fingerprint,
        )
    return None


def _directory_omission(
    selection: m.DirectoryDeliverySelection, delivered: int
) -> tuple[str, ...]:
    position = _directory_position(selection, delivered)
    if position is None:
        return ()
    remaining = len(selection.placements) + selection.unresolved_count - delivered
    return (f"{position.collection.value}: {remaining} remaining selected items",)


def _directory_unavailable(
    selection: m.DirectoryDeliverySelection, delivered: int
) -> m.FunctionalPyramidUnavailable:
    position = _directory_position(selection, delivered)
    coordinate = (
        "initial directory envelope"
        if position is None
        else f"{position.collection.value}[{position.offset}]"
    )
    return m.FunctionalPyramidUnavailable(
        failure=f"Response budget cannot carry the required unit {coordinate}",
        recovery=(
            f"Obtain a narrower directory than {selection.selector.repository_id}:"
            f"{selection.selector.directory}; if the unit remains indivisible, "
            "report the named delivery blocker"
        ),
    )


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
    def stale_directory(
        selection: m.DirectoryDeliverySelection,
    ) -> RecordingValidationError:
        selector = selection.selector
        return RecordingValidationError(
            "the directory selection is no longer current",
            cause_kind=RejectionCauseKind.CONTINUATION_INVALID,
            public_identity=f"{selector.repository_id}:{selector.directory}",
            public_cause=(
                "The bound directory selection is stale or expired; repeat "
                "FunctionalPyramidDirectorySelector with repository_id="
                f"{selector.repository_id!r}, directory={selector.directory!r}, "
                "and no after token"
            ),
        )

    def load_directory(
        self,
        cursor_id: str,
        selector: m.FunctionalPyramidDirectorySelector | None = None,
    ) -> _DirectoryCursor:
        bound = self._state.load_delivery_cursor(cursor_id)
        if bound is None:
            raise RecordingValidationError.continuation_invalid(
                "the delivery cursor was not issued"
            )
        selection, position = bound
        if (
            self._clock() >= selection.expires_at
            or position.state_fingerprint != selection.state_fingerprint
            or (selector is not None and selector != selection.selector)
        ):
            raise self.stale_directory(selection)
        return bound

    def initial_directory(
        self,
        selector: m.FunctionalPyramidDirectorySelector,
        view: m.FunctionalPyramidView,
        fingerprint: m.ContentDigest,
        limit: int,
    ) -> m.FunctionalPyramidView | m.FunctionalPyramidUnavailable:
        if encoded_size(view) <= limit:
            return view
        assert view.resolved_repository_id is not None
        now = self._clock()
        selection = m.DirectoryDeliverySelection(
            selection_id=server_selection_id(),
            selector=selector,
            owner_repository_id=view.resolved_repository_id,
            created_at=now,
            expires_at=now + self._state.retention.context_lifetime,
            state_fingerprint=fingerprint,
            placements=view.placements,
            unresolved_count=len(view.unresolved),
        )
        total = len(view.placements) + len(view.unresolved)
        cursor_id = server_cursor_id()

        def build(count: int) -> m.FunctionalPyramidView:
            if count == total:
                return view
            return _dataclasses.replace(
                view,
                placements=view.placements[:count],
                unresolved=view.unresolved[: max(0, count - len(view.placements))],
                selection_id=selection.selection_id,
                next_after=cursor_id,
                omitted=_directory_omission(selection, count),
                truncated=True,
            )

        count = largest_fitting_prefix(
            total, lambda n: n > 0 and encoded_size(build(n)) <= limit
        )
        if not count:
            return _directory_unavailable(selection, 0)
        position = _directory_position(selection, count)
        if position is None:
            return view
        candidate = build(count)
        with self._state.transaction() as transaction:
            transaction.write_delivery_selection(selection)
            issued = transaction.issue_delivery_cursor(
                selection.selection_id, position, cursor_id
            )
        return _dataclasses.replace(candidate, next_after=issued)

    def resume_directory(
        self,
        bound: _DirectoryCursor,
        view: m.FunctionalPyramidView,
        fingerprint: m.ContentDigest,
        limit: int,
    ) -> m.ResultPage | m.FunctionalPyramidUnavailable:
        selection, position = bound
        if (
            fingerprint != selection.state_fingerprint
            or view.resolved_repository_id != selection.owner_repository_id
            or view.placements != selection.placements
            or len(view.unresolved) != selection.unresolved_count
            or self._clock() >= selection.expires_at
        ):
            raise self.stale_directory(selection)
        offset = position.offset
        if position.collection is m.DeliveryCollection.PLACEMENTS:
            delivered = offset
            remaining = len(view.placements) - offset
        else:
            delivered = len(view.placements) + offset
            remaining = len(view.unresolved) - offset
        if remaining <= 0:
            raise self.stale_directory(selection)
        cursor_id = server_cursor_id()

        def build(count: int) -> m.ResultPage:
            end = offset + count
            part: m.ResultPart
            if position.collection is m.DeliveryCollection.PLACEMENTS:
                part = m.PlacementsPart(
                    offset, len(view.placements), view.placements[offset:end]
                )
            else:
                part = m.UnresolvedPart(
                    offset, len(view.unresolved), view.unresolved[offset:end]
                )
            omitted = _directory_omission(selection, delivered + count)
            return m.ResultPage(
                selection_id=selection.selection_id,
                result_kind=m.ResultKind.FUNCTIONAL_PYRAMID_VIEW,
                parts=(part,),
                continuation=cursor_id if omitted else None,
                omitted=omitted,
                truncated=bool(omitted),
            )

        count = largest_fitting_prefix(
            remaining, lambda n: n > 0 and encoded_size(build(n)) <= limit
        )
        if not count:
            return _directory_unavailable(selection, delivered)
        candidate = build(count)
        next_position = _directory_position(selection, delivered + count)
        if next_position is None:
            return candidate
        with self._state.transaction() as transaction:
            issued = transaction.issue_delivery_cursor(
                selection.selection_id, next_position, cursor_id
            )
        return _dataclasses.replace(candidate, continuation=issued)
