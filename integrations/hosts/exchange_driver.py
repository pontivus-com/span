"""Host-side canonical exchange driver (addendum D §6, TOOL-D-01).

Runs the query → answer-or-pending → investigate → submit loop to a
terminal result for one repository scope. Host-side orchestration
only: the driver never inspects, alters, or judges semantic content —
requests, results, and answers pass through untouched (deterministic
transport by construction: this module contains no transformation of
claims, evidence, dispositions, or answers). All semantic decisions
remain in Span's service/core; all strict ingress stays server-side.

Loop mechanics (D §6, C-08.6–7):

- serial submission only (no threads, no concurrent submits);
- validation rejection (``InterpretationUnitRejected``) halts with
  the exact diagnostics — reported, never retried, nothing written;
- ingress failure halts; unknown/expired continuations reissue the
  idempotent original operation (the authorized resume path, counted
  in cost — not a hidden retry);
- unexpected exceptions propagate: real failures stay visible;
- ``max_rounds`` is an explicit caller-stated liveness budget, not a
  semantic threshold; exhaustion halts with ``round_budget``.

Cost (``ExchangeCost``) is non-persisted operational telemetry —
counts plus wall-clock milliseconds, returned with the result. It is
never written to any store, never resumed from (resume uses persisted
canonical coverage only), and therefore is not a progress ledger.
Repository routing is bound by the caller: ``invoke``/``submit``/
``reissue`` thunks close over the repository's context (as
``McpAdapter._context`` does); one drive covers one repository scope.
"""

from __future__ import annotations

import time as _time
from collections.abc import Callable as _Callable
from dataclasses import dataclass as _dataclass
from typing import Literal as _Literal

from span.core import model as m
from span.core.validation import (
    InterpretationUnitRejected as _InterpretationUnitRejected,
)
from span.ports.interpretation import (
    InterpretationIngressFailure,
    InterpretationUnavailable,
    PendingInterpretation,
)

__all__ = [
    "ExchangeCost",
    "DriveHalt",
    "DriveResult",
    "drive",
]

#: Terminal halt classes. ``validation``/``ingress``/``unavailable``
#: mirror the service failure taxonomy; ``round_budget`` is liveness
#: exhaustion. None is a semantic verdict.
HaltKind = _Literal["validation", "ingress", "unavailable", "round_budget"]


@_dataclass(frozen=True)
class ExchangeCost:
    """Measured operational cost of one drive (telemetry, not a ledger)."""

    submissions: int
    reissues: int
    elapsed_ms: int


@_dataclass(frozen=True)
class DriveHalt:
    """Why a drive stopped without a terminal answer."""

    kind: HaltKind
    message: str
    diagnostics: tuple[str, ...] = ()


@_dataclass(frozen=True)
class DriveResult:
    """Terminal drive outcome: exactly one of answer/halt is present."""

    answer: m.SemanticAnswer | None
    halt: DriveHalt | None
    cost: ExchangeCost

    def __post_init__(self) -> None:
        if (self.answer is None) == (self.halt is None):
            raise ValueError(
                "DriveResult carries exactly one of answer/halt"
            )


def drive(
    invoke: _Callable[[], m.SemanticAnswer | PendingInterpretation],
    investigate: _Callable[
        [m.SemanticInterpretationRequest], m.SemanticInterpretationResult
    ],
    *,
    submit: _Callable[
        [str, m.SemanticInterpretationResult],
        m.SemanticAnswer | PendingInterpretation,
    ],
    reissue: _Callable[[], m.SemanticAnswer | PendingInterpretation],
    max_rounds: int,
) -> DriveResult:
    """Drive one canonical exchange to a terminal answer or a halt.

    ``invoke`` performs the initial operation call; ``investigate`` is
    the host agent's bounded interpretation of a pending task;
    ``submit``/``reissue`` are bound to the same repository context.
    ``max_rounds`` bounds submissions plus reissues; it must be
    positive.
    """
    if max_rounds <= 0:
        raise ValueError("max_rounds must be positive")
    started = _time.monotonic_ns()
    submissions = 0
    reissues = 0

    def _cost() -> ExchangeCost:
        return ExchangeCost(
            submissions=submissions,
            reissues=reissues,
            elapsed_ms=(_time.monotonic_ns() - started) // 1_000_000,
        )

    def _halt(
        kind: HaltKind, message: str,
        diagnostics: tuple[str, ...] = (),
    ) -> DriveResult:
        return DriveResult(answer=None, halt=DriveHalt(kind, message, diagnostics), cost=_cost())

    try:
        current = invoke()
    except _InterpretationUnitRejected as exc:
        return _halt("validation", str(exc), exc.diagnostics)
    except InterpretationIngressFailure as exc:
        return _halt("ingress", str(exc))
    except InterpretationUnavailable as exc:
        return _halt("unavailable", str(exc))

    while isinstance(current, PendingInterpretation):
        if submissions + reissues >= max_rounds:
            return _halt(
                "round_budget",
                f"round budget exhausted ({max_rounds}); "
                "investigation did not terminate",
            )
        result = investigate(current.request)
        try:
            current = submit(current.continuation, result)
            submissions += 1
        except _InterpretationUnitRejected as exc:
            return _halt("validation", str(exc), exc.diagnostics)
        except InterpretationIngressFailure as exc:
            return _halt("ingress", str(exc))
        except InterpretationUnavailable:
            if submissions + reissues >= max_rounds:
                return _halt(
                    "round_budget",
                    f"round budget exhausted ({max_rounds}); "
                    "continuation unavailable with no budget to reissue",
                )
            try:
                current = reissue()
                reissues += 1
            except _InterpretationUnitRejected as exc:
                return _halt("validation", str(exc), exc.diagnostics)
            except InterpretationIngressFailure as exc:
                return _halt("ingress", str(exc))
            except InterpretationUnavailable as exc:
                return _halt("unavailable", str(exc))
    return DriveResult(answer=current, halt=None, cost=_cost())
