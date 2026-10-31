"""Pure deterministic support decisions.

The core owns these rules. Services gather typed observations through ports
and call them; the shell only enforces storage and clock effects.
"""

from __future__ import annotations

import datetime as _datetime

from span.core.identity import payload_digest
from span.core import model as _m
from span.core.model import support as _s


def combine_states(states: tuple[_m.SupportState, ...]) -> _m.SupportState:
    """Combine independent conclusion states without promoting uncertainty."""
    if not states:
        return _m.SupportState.CURRENT
    if _m.SupportState.UNVERIFIABLE in states:
        return _m.SupportState.UNVERIFIABLE
    if _m.SupportState.REASSESSMENT_REQUIRED in states:
        return _m.SupportState.REASSESSMENT_REQUIRED
    return _m.SupportState.CURRENT


def worse_state(left: _m.SupportState, right: _m.SupportState) -> _m.SupportState:
    """Return the less current of two observed states."""
    return combine_states((left, right))


def evaluation(
    state: _m.SupportState,
    observed_at: _datetime.datetime,
    reason: str = "",
    *,
    dependencies: tuple[_s.SupportDependency, ...] = (),
    limitations: tuple[str, ...] = (),
) -> _s.SupportEvaluation:
    return _s.SupportEvaluation(
        state=state,
        dependencies=dependencies,
        reason=reason,
        observed_at=observed_at,
        limitations=limitations,
    )


def _fingerprint(value: str | None) -> str | None:
    if not value:
        return None
    return value.split(":", 1)[-1]


def source_state(
    *,
    record: _m.SourceObservation | None,
    observed_fingerprint: str | None,
    observed_at: _datetime.datetime,
) -> _s.SupportEvaluation:
    """Compare one admitted source observation with present bytes."""
    if record is None:
        return evaluation(
            _m.SupportState.UNVERIFIABLE,
            observed_at,
            "source observation no longer exists",
        )
    if observed_fingerprint is None:
        return evaluation(
            _m.SupportState.UNVERIFIABLE,
            observed_at,
            "observed source is no longer present",
        )
    expected = _fingerprint(record.content_digest.value)
    if expected is None:
        return evaluation(
            _m.SupportState.UNVERIFIABLE,
            observed_at,
            "source observation has no content identity",
        )
    if expected != observed_fingerprint:
        return evaluation(
            _m.SupportState.REASSESSMENT_REQUIRED,
            observed_at,
            "observed source bytes changed",
        )
    return evaluation(_m.SupportState.CURRENT, observed_at)


def discovery_state(
    *,
    record: _m.DiscoveryObservation | None,
    observed_fingerprint: str | None,
    observed_at: _datetime.datetime,
) -> _s.SupportEvaluation:
    """Compare one discovery-membership observation with present membership."""
    if record is None:
        return evaluation(
            _m.SupportState.UNVERIFIABLE,
            observed_at,
            "discovery observation no longer exists",
        )
    if observed_fingerprint is None:
        return evaluation(
            _m.SupportState.UNVERIFIABLE,
            observed_at,
            "discovery membership could not be observed",
        )
    if observed_fingerprint != record.membership_fingerprint:
        return evaluation(
            _m.SupportState.REASSESSMENT_REQUIRED,
            observed_at,
            "discovery membership changed",
        )
    return evaluation(_m.SupportState.CURRENT, observed_at)


def authority_state(
    *,
    recorded: _m.AuthorityBinding,
    declared: _m.AuthorityBinding | None,
    observed_fingerprint: str | None,
    observed_at: _datetime.datetime,
) -> _s.SupportEvaluation:
    """Compare the recorded authority declaration with present authority state."""
    if declared is None:
        return evaluation(
            _m.SupportState.UNVERIFIABLE,
            observed_at,
            "declared authority no longer resolves",
        )
    if declared.status is not _m.AuthorityStatus.ACCEPTED:
        state = (
            _m.SupportState.REASSESSMENT_REQUIRED
            if declared.status is _m.AuthorityStatus.SUPERSEDED
            else _m.SupportState.UNVERIFIABLE
        )
        return evaluation(
            state, observed_at, "authority status is " + declared.status.value
        )
    if (
        declared.evidence_ref.evidence_id != recorded.evidence_ref.evidence_id
        or declared.evidence_ref.repository_id != recorded.evidence_ref.repository_id
        or declared.evidence_ref.locator != recorded.evidence_ref.locator
    ):
        return evaluation(
            _m.SupportState.REASSESSMENT_REQUIRED,
            observed_at,
            "declared authority identity changed",
        )
    if (
        declared.authority_kind is not recorded.authority_kind
        or declared.applicability != recorded.applicability
    ):
        return evaluation(
            _m.SupportState.REASSESSMENT_REQUIRED,
            observed_at,
            "declared authority kind or applicability changed",
        )
    if observed_fingerprint is None:
        return evaluation(
            _m.SupportState.UNVERIFIABLE,
            observed_at,
            "authority evidence is no longer present",
        )
    expected = _fingerprint(recorded.evidence_ref.revision_or_fingerprint)
    if expected is None:
        return evaluation(
            _m.SupportState.UNVERIFIABLE,
            observed_at,
            "authority content identity is not recorded",
        )
    if expected != observed_fingerprint:
        return evaluation(
            _m.SupportState.REASSESSMENT_REQUIRED,
            observed_at,
            "authority content changed",
        )
    return evaluation(_m.SupportState.CURRENT, observed_at)


def premise_membership_state(
    *,
    exists: bool,
    in_current_membership: bool,
    observed_at: _datetime.datetime,
) -> _s.SupportEvaluation:
    """Check the premise's existence and current membership before recursion."""
    if not exists:
        return evaluation(
            _m.SupportState.UNVERIFIABLE,
            observed_at,
            "premise revision no longer exists",
        )
    if not in_current_membership:
        return evaluation(
            _m.SupportState.REASSESSMENT_REQUIRED,
            observed_at,
            "premise revision was superseded or withdrawn",
        )
    return evaluation(_m.SupportState.CURRENT, observed_at)


def discovery_membership_fingerprint(
    pairs: tuple[tuple[str, str], ...],
) -> str:
    """Hash one observed inventory membership deterministically."""
    payload = [list(item) for item in pairs]
    return payload_digest(payload).value
