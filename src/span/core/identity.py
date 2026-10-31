"""Pure request/submission identity and canonical payload digests.

No filesystem, database, transport, clock, or model access belongs here.
"""

from __future__ import annotations

import hashlib as _hashlib
import json as _json

from span.core.model.canonical import to_canonical
from span.core.model.commands import RecordCommand
from span.core.model.investigation import SourceRange
from span.core.model.primitives import (
    ChallengeId,
    DiscoveryObservationId,
    EvidenceScope,
    RequestId,
    SourceObservationId,
    UnderstandingId,
)
from span.core.model.recording import (
    ContentDigest,
    RecordingIdentity,
    RecordingKey,
    RequestBinding,
)


def _canonical_json(value: object) -> str:
    if hasattr(value, "__dataclass_fields__"):
        value = to_canonical(value)
    if not isinstance(value, (dict, list, str, int, bool)) and value is not None:
        raise TypeError(f"cannot digest {type(value).__name__} canonically")
    return _json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def payload_digest(payload: object) -> ContentDigest:
    """Hash one canonical payload deterministically."""
    encoded = _canonical_json(payload).encode("utf-8")
    return ContentDigest("sha256:" + _hashlib.sha256(encoded).hexdigest())


def record_content_digest(command: RecordCommand) -> ContentDigest:
    """Hash a recording command's content, excluding its recording identity.

    Repository, context, and submission identities are the recording key;
    they are not duplicated inside the content digest. The digest therefore
    answers exactly "is this the same submitted content for this key?".
    """
    canonical = to_canonical(command)
    if not isinstance(canonical, dict):
        raise TypeError("a record command must encode as an object")
    content = dict(canonical)
    content.pop("identity", None)
    return payload_digest(content)


def recording_key(identity: RecordingIdentity) -> RecordingKey:
    """Project one recording identity into its unique store key."""
    return RecordingKey(
        repository_id=identity.repository_id,
        context_id=identity.context_id,
        submission_id=identity.submission_id,
    )


def understanding_identity(identity: RecordingIdentity) -> UnderstandingId:
    """Derive the stable understanding identity of one create submission.

    A create is keyed by its recording identity, so a retry after a lost
    response addresses the same understanding even when the receipt is being
    re-read by a new process. Updates carry their own understanding identity.
    """
    return UnderstandingId(
        f"u:{identity.context_id.value}:{identity.submission_id.value}"
    )


def challenge_identity(identity: RecordingIdentity) -> ChallengeId:
    """Derive the stable challenge identity of one create submission."""
    return ChallengeId(f"ch:{identity.context_id.value}:{identity.submission_id.value}")


def source_observation_identity(
    repository_id: str,
    locator: str,
    content_digest: ContentDigest,
    delivered_ranges: tuple[SourceRange, ...],
    whole_file: bool,
) -> SourceObservationId:
    """Derive the stable identity of one observed locator/content/range set.

    Repeated requests for the same observed bytes and delivered ranges reuse
    the observation; changed bytes produce a distinct identity. Range order
    and duplicates do not change identity.
    """
    ranges = tuple(
        sorted({(item.start_line, item.end_line) for item in delivered_ranges})
    )
    digest = payload_digest(
        {
            "repository_id": repository_id,
            "locator": locator,
            "content_digest": content_digest.value,
            "ranges": [list(item) for item in ranges],
            "whole_file": whole_file,
        }
    )
    return SourceObservationId("obs:" + digest.value.split(":", 1)[1])


def discovery_observation_identity(
    repository_id: str,
    scope: EvidenceScope,
    membership_fingerprint: str,
) -> DiscoveryObservationId:
    """Derive the stable identity of one exact observed membership snapshot."""
    digest = payload_digest(
        {
            "repository_id": repository_id,
            "scope": to_canonical(scope),
            "membership_fingerprint": membership_fingerprint,
        }
    )
    return DiscoveryObservationId("dsc:" + digest.value.split(":", 1)[1])


def request_binding(
    repository_id: str,
    request_id: RequestId,
    payload: object,
) -> RequestBinding:
    """Bind one initial request identity to its canonical content digest."""
    return RequestBinding(
        repository_id=repository_id,
        request_id=request_id,
        content_digest=payload_digest(payload),
    )
