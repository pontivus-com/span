"""MCP transport envelopes (shell-owned, not semantics)."""

from __future__ import annotations

import dataclasses as _dataclasses

from span.core import model as m
from span.ports.evidence import EvidenceSource
from span.ports.lifecycle import LifecycleStorePort
from span.ports.structural import StructuralSource
from span.service.evidence import EvidenceService
from span.service.lifecycle import LifecycleService
from span.service.support import SupportService
from span.service.understand import UnderstandService

__all__ = ["ServiceContext", "ToolError", "ToolResult"]


@_dataclasses.dataclass(frozen=True)
class ServiceContext:
    """Wired lifecycle dependencies for one repository (shell lifecycle)."""

    repository_id: str
    root: str
    structural: StructuralSource
    evidence: EvidenceSource
    store: LifecycleStorePort
    lifecycle: LifecycleService
    evidence_service: EvidenceService
    understand: UnderstandService
    support: SupportService
    authority_seeds: tuple[m.EvidenceRef, ...] = ()


@_dataclasses.dataclass(frozen=True)
class ToolResult:
    """One tool invocation outcome (transport envelope, not semantics)."""

    content: str
    structured_content: dict | None = None
    is_error: bool = False


@_dataclasses.dataclass(frozen=True)
class ToolError:
    """Typed transport failure; the kind is part of the contract."""

    kind: str
    message: str
    replacement: str | None = None

    def __post_init__(self) -> None:
        if not self.kind:
            raise ValueError("ToolError.kind must be non-empty")
        if not self.message:
            raise ValueError("ToolError.message must be non-empty")
