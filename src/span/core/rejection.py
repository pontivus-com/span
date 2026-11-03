"""Typed rejection causes shared by core, service, and shell.

A rejection is the caller's to resolve and carries a typed cause. The adapter
copies the typed cause into the public result; it never derives a cause or an
action from message text (FD-39, FD-41, TD §9.2).
"""

from __future__ import annotations

import enum as _enum

__all__ = [
    "Rejection",
    "RejectionCauseKind",
    "SurfaceConflict",
    "required_action_for",
]


class RejectionCauseKind(_enum.Enum):
    """Why a write was rejected, independent of its human message."""

    VALIDATION = "validation"
    SOURCE_DRIFT = "source_drift"
    VERSION_CONFLICT = "version_conflict"
    SURFACE_CONFLICT = "surface_conflict"
    SURFACE_REQUIRED = "surface_required"
    SURFACE_AMBIGUOUS = "surface_ambiguous"
    SURFACE_MISMATCH = "surface_mismatch"
    CONTEXT_TARGET_CONFLICT = "context_target_conflict"
    CONTEXT_REQUIRED = "context_required"
    OBSERVATION_NOT_ADMITTED = "observation_not_admitted"
    REPLAY_CONFLICT = "replay_conflict"
    ALREADY_EXISTS = "already_exists"


def required_action_for(kind: RejectionCauseKind) -> str:
    """The one remedy for a typed cause; never derived from a message."""
    if kind is RejectionCauseKind.SOURCE_DRIFT:
        return "re-read the cited evidence, then record against the current revision"
    if kind is RejectionCauseKind.VERSION_CONFLICT:
        return "re-read the named state, then retry with its current version"
    if kind is RejectionCauseKind.SURFACE_CONFLICT:
        return "re-read the surface, then retry with its current boundary version"
    if kind is RejectionCauseKind.SURFACE_REQUIRED:
        return (
            "supply surface, or one scope_paths entry, or record against the "
            "context from ask"
        )
    if kind is RejectionCauseKind.SURFACE_AMBIGUOUS:
        return (
            "record one conclusion per surface, or supply the exact surface, or "
            "declare a service/domain surface first"
        )
    if kind is RejectionCauseKind.SURFACE_MISMATCH:
        return "make surface agree with the carried scope, or omit it and let Span derive it"
    if kind is RejectionCauseKind.CONTEXT_TARGET_CONFLICT:
        return "omit the explicit target when recording against a question context"
    if kind is RejectionCauseKind.CONTEXT_REQUIRED:
        return "supply context_id or a declared scope with locator support"
    if kind is RejectionCauseKind.OBSERVATION_NOT_ADMITTED:
        return (
            "use an observation id returned by ask for this context, or cite "
            "the source by locator so Span admits it"
        )
    if kind is RejectionCauseKind.REPLAY_CONFLICT:
        return (
            "reuse the original content for this request identity, or start a new "
            "request identity"
        )
    if kind is RejectionCauseKind.ALREADY_EXISTS:
        return (
            "record against the existing understanding with actions.add, "
            "actions.correct, or actions.replace"
        )
    return "correct the named field, then retry"


class Rejection(ValueError):
    """A typed, actionable rejection raised by the service or the store."""

    def __init__(
        self,
        cause: str,
        *,
        cause_kind: RejectionCauseKind = RejectionCauseKind.VALIDATION,
        current_version: int | None = None,
        current_boundary_version: int | None = None,
    ) -> None:
        super().__init__(cause)
        self.cause = cause
        self.cause_kind = cause_kind
        self.required_action = required_action_for(cause_kind)
        self.current_version = current_version
        self.current_boundary_version = current_boundary_version


class SurfaceConflict(ValueError):
    """A declared-surface boundary conflict, distinct from a store failure.

    The service maps this to a public ``Rejected`` with the current boundary
    version. It is not ``Unavailable``: the caller can resolve it.
    """

    def __init__(
        self, cause: str, *, current_boundary_version: int | None = None
    ) -> None:
        super().__init__(cause)
        self.cause = cause
        self.current_boundary_version = current_boundary_version
