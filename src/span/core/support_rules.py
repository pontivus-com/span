"""Pure deterministic support decisions.

The core owns these rules. Services gather typed observations through ports
and call them; the shell only enforces storage and clock effects.
"""

from __future__ import annotations

import datetime as _datetime
import hashlib as _hashlib

from span.core.identity import payload_digest
from span.core import model as _m
from span.core.model import support as _s


def unvisited_premises(
    dependents: tuple[_m.ConclusionRevisionRef, ...],
    visited: set[_m.ConclusionRevisionRef],
) -> tuple[_m.ConclusionRevisionRef, ...]:
    """Select new frontier members, independent of edge cause attribution."""
    return tuple(dict.fromkeys(ref for ref in dependents if ref not in visited))


def dependency_change_reasons(
    direct: set[_m.ConclusionRevisionRef],
    indirect: set[_m.ConclusionRevisionRef],
) -> dict[_m.ConclusionRevisionRef, set[_m.ChangeReason]]:
    """Assign each exact revision its own causes, including both when present."""
    reasons = {ref: {_m.ChangeReason.DIRECT} for ref in direct}
    for ref in indirect:
        reasons.setdefault(ref, set()).add(_m.ChangeReason.INDIRECT)
    return reasons


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
    findings: tuple[_s.DependencyFinding, ...] = (),
    limitations: tuple[str, ...] = (),
) -> _s.SupportEvaluation:
    return _s.SupportEvaluation(
        state=state,
        dependencies=dependencies,
        reason=reason,
        findings=findings,
        observed_at=observed_at,
        limitations=limitations,
    )


def _fingerprint(value: str | None) -> str | None:
    if not value:
        return None
    return value.split(":", 1)[-1]


def ranged_fingerprint(content: str, ranges: tuple[_m.SourceRange, ...]) -> str | None:
    """Fingerprint the exact declared ranges, or None when they cannot bind.

    A range that names lines beyond the present text cannot be evaluated as
    that range; FD-18 requires the caller to fall back to the whole file
    rather than a narrower claim.
    """
    lines = content.splitlines(keepends=True)
    if any(item.end_line > len(lines) for item in ranges):
        return None
    ordered = sorted(ranges, key=lambda item: (item.start_line, item.end_line))
    excerpt = "".join(
        "".join(lines[item.start_line - 1 : item.end_line]) for item in ordered
    )
    return _hashlib.sha256(excerpt.encode("utf-8")).hexdigest()


def source_state(
    *,
    record: _m.SourceObservation | None,
    observed_fingerprint: str | None,
    expected_fingerprint: str | None,
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
    expected = _fingerprint(expected_fingerprint)
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


def functional_route_state(
    *,
    recorded: _m.FunctionalRouteSupport,
    current: (
        _m.FunctionalPyramidParticipation
        | _m.FunctionalPyramidView
        | _m.FunctionalPyramidUnavailable
    ),
    current_route_identity: _m.FunctionalRouteIdentity | None,
    observed_at: _datetime.datetime,
) -> _s.SupportEvaluation:
    """Qualify one recorded Functional Pyramid route against current state."""
    if isinstance(current, _m.FunctionalPyramidUnavailable):
        return evaluation(
            _m.SupportState.UNVERIFIABLE,
            observed_at,
            "governing applicability could not be evaluated",
        )
    if isinstance(current, _m.FunctionalPyramidParticipation):
        return evaluation(
            _m.SupportState.REASSESSMENT_REQUIRED,
            observed_at,
            "repository is no longer ACTIVE in the recorded Functional Pyramid",
        )
    if current.pyramid_id != recorded.pyramid_id:
        return evaluation(
            _m.SupportState.REASSESSMENT_REQUIRED,
            observed_at,
            "repository is ACTIVE in a different Functional Pyramid",
        )
    if current.status is _m.FunctionalPyramidRouteStatus.UNRESOLVED:
        return evaluation(
            _m.SupportState.UNVERIFIABLE,
            observed_at,
            "current functional route is unresolved",
        )
    if current_route_identity is None:
        return evaluation(
            _m.SupportState.UNVERIFIABLE,
            observed_at,
            "current governing applicability is unavailable",
        )
    if current_route_identity != recorded.route_identity:
        return evaluation(
            _m.SupportState.REASSESSMENT_REQUIRED,
            observed_at,
            "governing applicability changed",
        )
    return evaluation(_m.SupportState.CURRENT, observed_at)


def premise_membership_state(
    *,
    exists: bool,
    in_current_membership: bool,
    withdrawn: bool,
    observed_at: _datetime.datetime,
) -> _s.SupportEvaluation:
    """Check the premise's existence, withdrawal, and current membership."""
    if not exists:
        return evaluation(
            _m.SupportState.UNVERIFIABLE,
            observed_at,
            "premise revision no longer exists",
        )
    if withdrawn:
        return evaluation(
            _m.SupportState.UNVERIFIABLE,
            observed_at,
            "premise revision was withdrawn",
        )
    if not in_current_membership:
        return evaluation(
            _m.SupportState.REASSESSMENT_REQUIRED,
            observed_at,
            "premise revision was superseded",
        )
    return evaluation(_m.SupportState.CURRENT, observed_at)


def discovery_membership_fingerprint(
    pairs: tuple[tuple[str, str], ...],
) -> str:
    """Hash one observed inventory membership deterministically."""
    payload = [list(item) for item in pairs]
    return payload_digest(payload).value
