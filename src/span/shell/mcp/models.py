"""MCP transport envelopes (shell-owned, not semantics)."""

from __future__ import annotations

from dataclasses import dataclass as _dataclass

from span.core import model as m
from span.ports.evidence import EvidenceSource
from span.ports.store import SemanticStore
from span.ports.structural import StructuralSource
from span.shell.agent_exchange.continuations import ContinuationStore

__all__ = ["ServiceContext", "ToolResult"]


@_dataclass(frozen=True)
class ServiceContext:
    """Wired service dependencies for one repository (shell lifecycle)."""

    structural: StructuralSource
    evidence: EvidenceSource
    store: SemanticStore
    continuations: ContinuationStore
    authority_seeds: tuple[m.EvidenceRef, ...] = ()


@_dataclass(frozen=True)
class ToolResult:
    """One tool invocation outcome (transport envelope, not semantics)."""

    content: str
    structured_content: dict | None = None
    is_error: bool = False
