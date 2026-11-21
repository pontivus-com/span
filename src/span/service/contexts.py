"""Shared server-owned context binding and issuance for lifecycle services."""

from __future__ import annotations

import datetime as _datetime
import json as _json
import typing as _typing
from dataclasses import dataclass as _dataclass

from span.core import model as m
from span.core.identity import payload_digest
from span.ports.lifecycle import LifecycleStorePort

__all__ = ["ContextBinding", "build_context", "context_binding", "issue_context"]


@_dataclass(frozen=True)
class ContextBinding:
    """Canonical service-owned projection that binds one recoverable context."""

    scope: m.EvidenceScope
    origin: m.ContextOrigin
    question: str | None = None
    source_requests: tuple[m.EvidenceRequest, ...] = ()
    discovery_scopes: tuple[m.EvidenceScope, ...] = ()

    def __post_init__(self) -> None:
        if self.question is not None and not self.question:
            raise ValueError("ContextBinding.question must be non-empty")
        if self.origin is m.ContextOrigin.QUESTION and self.question is None:
            raise ValueError("a QUESTION binding requires a bound question")


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
    origin: m.ContextOrigin,
    question: str | None = None,
    source_requests: tuple[m.EvidenceRequest, ...] = (),
    discovery_scopes: tuple[m.EvidenceScope, ...] = (),
) -> ContextBinding:
    """Build the sole canonical context-binding projection (FD-2, FD-59)."""
    return ContextBinding(
        scope=scope,
        origin=origin,
        question=question,
        source_requests=_canonical_values(source_requests),
        discovery_scopes=_canonical_values(discovery_scopes),
    )


def build_context(
    *,
    retention: m.LifecycleRetention,
    binding: ContextBinding,
    repository_id: str,
    request_id: m.RequestId,
    clock: _typing.Callable[[], _datetime.datetime],
    new_context_id: _typing.Callable[[], str],
) -> m.InvestigationContext:
    """Build the canonical server-owned context without persisting it."""
    now = clock()
    return m.InvestigationContext(
        context_id=m.InvestigationContextId(new_context_id()),
        repository_id=repository_id,
        request_id=request_id,
        binding_digest=payload_digest(binding),
        origin=binding.origin,
        state=m.ContextState.LIVE,
        scope=binding.scope,
        created_at=now,
        question=(binding.question if binding.origin is m.ContextOrigin.QUESTION else None),
        expires_at=now + retention.context_lifetime,
    )


def issue_context(
    store: LifecycleStorePort,
    *,
    binding: ContextBinding,
    repository_id: str,
    request_id: m.RequestId,
    clock: _typing.Callable[[], _datetime.datetime],
    new_context_id: _typing.Callable[[], str],
) -> m.InvestigationContext:
    """Issue or recover the one context bound to this request identity."""
    digest = payload_digest(binding)

    def factory() -> m.InvestigationContext:
        return build_context(
            retention=store.retention,
            binding=binding,
            repository_id=repository_id,
            request_id=request_id,
            clock=clock,
            new_context_id=new_context_id,
        )

    return store.resolve_context(repository_id, request_id, digest, factory)
