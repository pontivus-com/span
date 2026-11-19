"""Shared server-owned context binding and issuance for lifecycle services."""

from __future__ import annotations

import datetime as _datetime
import json as _json
import typing as _typing

from span.core import model as m
from span.core.identity import payload_digest
from span.ports.lifecycle import LifecycleStorePort

__all__ = ["context_binding", "issue_context"]


_T = _typing.TypeVar("_T")


def _canonical_values(values: tuple[_T, ...]) -> tuple[_T, ...]:
    """Deduplicate and sort canonical values without inventing another identity."""
    keyed = {
        _json.dumps(
            m.to_canonical(value),
            sort_keys=True,
            separators=(",", ":"),
        ): value
        for value in values
    }
    return tuple(keyed[key] for key in sorted(keyed))


def context_binding(
    *,
    scope: m.EvidenceScope,
    question: str | None = None,
    source_requests: tuple[m.EvidenceRequest, ...] = (),
    discovery_scopes: tuple[m.EvidenceScope, ...] = (),
) -> m.ContextBinding:
    """Build the sole canonical context-binding projection (FD-2, FD-59)."""
    return m.ContextBinding(
        scope=scope,
        question=question,
        source_requests=_canonical_values(source_requests),
        discovery_scopes=_canonical_values(discovery_scopes),
    )


def issue_context(
    store: LifecycleStorePort,
    *,
    binding: m.ContextBinding,
    repository_id: str,
    request_id: m.RequestId,
    clock: _typing.Callable[[], _datetime.datetime],
    new_context_id: _typing.Callable[[], str],
) -> m.InvestigationContext:
    """Issue or recover the one context bound to this request identity."""
    digest = payload_digest(binding)

    def factory() -> m.InvestigationContext:
        now = clock()
        return m.InvestigationContext(
            context_id=m.InvestigationContextId(new_context_id()),
            repository_id=repository_id,
            request_id=request_id,
            binding_digest=digest,
            origin=(
                m.ContextOrigin.QUESTION
                if binding.question is not None
                else m.ContextOrigin.EVIDENCE_ONLY
            ),
            state=m.ContextState.LIVE,
            scope=binding.scope,
            created_at=now,
            question=binding.question,
            expires_at=now + store.retention.context_lifetime,
        )

    return store.resolve_context(repository_id, request_id, digest, factory)
