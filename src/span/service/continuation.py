"""Stateless continuation tokens over the existing context lifecycle.

A continuation binds one repository, investigation context, request binding,
and the next evidence position. It introduces no table, TTL, or reaper: it is
valid exactly while its context is live. The token is opaque to the host and
server-decodable; the store remains the owner of context expiry and reaping.
"""

from __future__ import annotations

import base64 as _base64
import json as _json
from dataclasses import dataclass as _dataclass

from span.core.model import ContentDigest, RequestId
from span.core.model.primitives import _require_non_empty

__all__ = ["ContinuationCursor", "decode_continuation", "encode_continuation"]

_PREFIX = "span1_"


@_dataclass(frozen=True)
class ContinuationCursor:
    """The exact position a continuation resumes from."""

    repository_id: str
    context_id: str
    request_id: RequestId
    request_digest: ContentDigest
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
        "d": cursor.request_digest.value,
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
        request_digest=ContentDigest(payload["d"]),
        unit_index=payload["i"],
        line_offset=payload["l"],
    )
