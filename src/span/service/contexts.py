"""Shared server-owned context issuance for lifecycle services."""

from __future__ import annotations

import datetime as _datetime
import typing as _typing

from span.core import model as m
from span.core.identity import payload_digest
from span.ports.lifecycle import LifecycleStorePort

__all__ = ["issue_context"]


def issue_context(
    store: LifecycleStorePort,
    *,
    payload: object,
    repository_id: str,
    request_id: m.RequestId,
    scope: m.EvidenceScope,
    question: str | None,
    clock: _typing.Callable[[], _datetime.datetime],
    new_context_id: _typing.Callable[[], str],
) -> m.InvestigationContext:
    """Issue or recover the one context bound to this request identity."""
    digest = payload_digest(payload)

    def factory() -> m.InvestigationContext:
        now = clock()
        return m.InvestigationContext(
            context_id=m.InvestigationContextId(new_context_id()),
            repository_id=repository_id,
            request_id=request_id,
            request_digest=digest,
            origin=(
                m.ContextOrigin.QUESTION
                if question is not None
                else m.ContextOrigin.EVIDENCE_ONLY
            ),
            state=m.ContextState.LIVE,
            scope=scope,
            created_at=now,
            question=question,
            expires_at=now + store.retention.context_lifetime,
        )

    return store.resolve_context(repository_id, request_id, digest, factory)
