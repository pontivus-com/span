"""Span service agent-exchange coordination (plan §11.12; v0.6 §14 Amendment A-01).

Interpretation submission and resume dispatch across the owning
operation modules. Owns no semantic predicate: validates via ``core``
and rebuilds answers via the owning op composers.
"""

from __future__ import annotations

from span.core import model as m
from span.ports.evidence import EvidenceSource
from span.ports.interpretation import InterpretationUnavailable
from span.ports.interpretation import PendingInterpretation
from span.ports.store import SemanticStore
from span.ports.structural import StructuralSource
from span.ports.continuation import ContinuationPort

from span.service.exchange.commit import _commit_prepared
from span.service.exchange.prepare import _prepare_submission
from span.service.exchange.resume import _resume_operation

__all__ = [
    "submit_interpretation",
]


def submit_interpretation(
    continuation: str,
    result: m.SemanticInterpretationResult,
    *,
    structural: StructuralSource,
    evidence: EvidenceSource,
    store: SemanticStore,
    continuations: ContinuationPort,
) -> m.SemanticAnswer | PendingInterpretation:
    """Accept an agent's typed result and resume the operation (§11.12;
    [design note H](docs/design-references.md#h) §4).

    Unknown or expired continuations yield InterpretationUnavailable
    at peek (the agent re-issues the original operation,
    idempotently); a token taken by a concurrent submitter yields it at
    acquire. Preparation runs on peeked state without
    holding ownership; single-commit ownership is acquired only for
    the commit-critical section (materialize + claim). Validation
    failure retains the live continuation; only a
    successful ``write_index_batch`` consumes it. Refresh resumes
    across remaining subjects, suspending again while affected work
    remains.
    """
    record = continuations.peek(continuation)
    if record is None:
        raise InterpretationUnavailable(
            f"unknown, expired, or in-flight continuation: {continuation}. Re-run the original operation; this token cannot be recovered."
        )
    prepared = _prepare_submission(
        record,
        result,
        structural=structural,
        evidence=evidence,
        store=store,
    )
    committed = _commit_prepared(
        continuation,
        prepared,
        result,
        evidence=evidence,
        store=store,
        continuations=continuations,
    )
    return _resume_operation(
        committed,
        prepared,
        structural=structural,
        evidence=evidence,
        store=store,
        continuations=continuations,
    )
