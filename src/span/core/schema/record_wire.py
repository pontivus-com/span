"""Canonical reference-only transport projection for record commands.

This module is the single public transport boundary for the record command
shapes. It is not a host-specific DTO: every host shares it, the schema is
generated from these types, and it decodes strictly into the canonical domain
commands.

The projection carries admitted observation/reference identities, not the full
evidence or authority structures. The service resolves those references to
canonical carriers before constructing the domain command. That keeps the
wire small and preserves the evidence-admission / semantic-recording
separation.
"""

from __future__ import annotations

import datetime as _datetime
import typing as _typing
from dataclasses import dataclass as _dataclass, field as _field

from span.core.identity import conclusion_identity, payload_digest
from span.core.model.canonical import to_canonical
from span.core.model import commands as _c
from span.core.model import primitives as _p
from span.core.model import support as _s
from span.core.model import surfaces as _surfaces
from span.core.model import verification as _v
from span.core.model.investigation import (
    InvestigationContextRef as _InvestigationContextRef,
    SourceRange as _SourceRange,
)
from span.core.model.recording import ContentDigest
from span.core.model.claims import AssertionNature
from span.core.model.understanding import (
    ConclusionRevision as _ConclusionRevision,
    SupportedConclusion as _SupportedConclusion,
)


@_dataclass(frozen=True)
class RecordWireResolver:
    """Required resolution supplied by the service boundary."""

    reference: _typing.Callable[[str], _p.EvidenceRef]
    authority: _typing.Callable[[str], _p.AuthorityBinding]
    source: _typing.Callable[[str, tuple[_SourceRange, ...]], _p.SourceObservationId]
    discovery: _typing.Callable[[_p.EvidenceScope], _p.DiscoveryObservationId]
    observation_locator: _typing.Callable[[str], str]


@_dataclass(frozen=True)
class RangeWire:
    """One inclusive line range in a source-support citation."""

    start_line: int
    end_line: int

    def __post_init__(self) -> None:
        if self.start_line < 1 or self.end_line < self.start_line:
            raise ValueError("RangeWire requires 1 <= start_line <= end_line")


@_dataclass(frozen=True)
class SourceSupportWire:
    """Cite exact source bytes by locator and optional ranges (F7, FD-18)."""

    locator: str
    ranges: tuple[RangeWire, ...] = ()

    def __post_init__(self) -> None:
        if not self.locator:
            raise ValueError("SourceSupportWire.locator must be non-empty")


@_dataclass(frozen=True)
class AdmittedSourceSupportWire:
    """Cite an observation already admitted for the context (L2 §4.2)."""

    observation_id: str

    def __post_init__(self) -> None:
        if not self.observation_id:
            raise ValueError(
                "AdmittedSourceSupportWire.observation_id must be non-empty"
            )


@_dataclass(frozen=True)
class AuthoritySupportWire:
    authority_ref: str


@_dataclass(frozen=True)
class PremiseSupportWire:
    understanding_id: str
    conclusion_id: str
    revision: int


@_dataclass(frozen=True)
class DiscoveryScopeWire:
    """The exact scope an agent inspected for a discovery claim."""

    paths: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for path in self.paths:
            if not path:
                raise ValueError("DiscoveryScopeWire.paths must be non-empty")
            if path.startswith("/"):
                raise ValueError("DiscoveryScopeWire.paths must be relative")


@_dataclass(frozen=True)
class DiscoveryBoundarySupportWire:
    """Declare the boundary the agent inspected; Span observes membership."""

    scope: DiscoveryScopeWire


@_dataclass(frozen=True)
class AdmittedDiscoverySupportWire:
    """Cite a discovery observation already admitted in the context."""

    observation_id: str

    def __post_init__(self) -> None:
        if not self.observation_id:
            raise ValueError(
                "AdmittedDiscoverySupportWire.observation_id must be non-empty"
            )


SupportWire = _typing.Union[
    SourceSupportWire,
    AdmittedSourceSupportWire,
    AuthoritySupportWire,
    PremiseSupportWire,
    DiscoveryBoundarySupportWire,
    AdmittedDiscoverySupportWire,
]


@_dataclass(frozen=True)
class GapWire:
    question: str
    basis: str


def _evidence_mode_count(
    locator: str | None,
    observation_id: str | None,
    support: tuple[SupportWire, ...],
) -> int:
    return (
        int(locator is not None) + int(observation_id is not None) + int(bool(support))
    )


def _require_action_field(action: str, field: str, value: str) -> None:
    if not value:
        raise ValueError(f"record.actions.{action} requires a non-empty {field!r}")


def _validate_optional_identifier(action: str, field: str, value: str | None) -> None:
    if value is not None and not value:
        raise ValueError(
            f"record.actions.{action}.{field} must be non-empty when supplied"
        )


def _require_evidence(
    action: str,
    locator: str | None,
    observation_id: str | None,
    support: tuple[SupportWire, ...],
    *,
    required: bool,
) -> None:
    modes = _evidence_mode_count(locator, observation_id, support)
    if modes > 1:
        raise ValueError(
            f"record.actions.{action} takes exactly one evidence mode: "
            "locator, observation_id, or support; it received more than one"
        )
    if required and modes == 0:
        raise ValueError(
            f"record.actions.{action} requires exactly one evidence mode: "
            "locator, observation_id, or non-empty support"
        )


@_dataclass(frozen=True)
class AddConclusionWire:
    """One compact add action: statement plus the evidence already held."""

    conclusion: str
    assertion_nature: AssertionNature = AssertionNature.DESCRIPTIVE
    scope_paths: tuple[str, ...] = ()
    locator: str | None = None
    observation_id: str | None = None
    support: tuple[SupportWire, ...] = ()

    def __post_init__(self) -> None:
        _require_action_field("add", "conclusion", self.conclusion)
        _validate_optional_identifier("add", "locator", self.locator)
        _validate_optional_identifier("add", "observation_id", self.observation_id)
        _require_evidence(
            "add", self.locator, self.observation_id, self.support, required=True
        )


@_dataclass(frozen=True)
class ConfirmConclusionWire:
    """One compact confirm action: Span preserves the current content."""

    conclusion_id: str
    locator: str | None = None
    observation_id: str | None = None
    support: tuple[SupportWire, ...] = ()

    def __post_init__(self) -> None:
        _require_action_field("confirm", "conclusion_id", self.conclusion_id)
        _validate_optional_identifier("confirm", "locator", self.locator)
        _validate_optional_identifier("confirm", "observation_id", self.observation_id)
        _require_evidence(
            "confirm", self.locator, self.observation_id, self.support, required=True
        )


@_dataclass(frozen=True)
class CorrectConclusionWire:
    """One compact correct action; omitted nature and scope are preserved."""

    conclusion_id: str
    conclusion: str
    assertion_nature: AssertionNature | None = None
    scope_paths: tuple[str, ...] = ()
    locator: str | None = None
    observation_id: str | None = None
    support: tuple[SupportWire, ...] = ()

    def __post_init__(self) -> None:
        _require_action_field("correct", "conclusion_id", self.conclusion_id)
        _require_action_field("correct", "conclusion", self.conclusion)
        _validate_optional_identifier("correct", "locator", self.locator)
        _validate_optional_identifier("correct", "observation_id", self.observation_id)
        _require_evidence(
            "correct", self.locator, self.observation_id, self.support, required=True
        )


@_dataclass(frozen=True)
class ReplaceActionWire:
    """One flat replace action; Span derives the old revision identity."""

    conclusion_id: str
    conclusion: str
    reason: str
    assertion_nature: AssertionNature | None = None
    scope_paths: tuple[str, ...] = ()
    locator: str | None = None
    observation_id: str | None = None
    support: tuple[SupportWire, ...] = ()

    def __post_init__(self) -> None:
        _require_action_field("replace", "conclusion_id", self.conclusion_id)
        _require_action_field("replace", "conclusion", self.conclusion)
        _require_action_field("replace", "reason", self.reason)
        _validate_optional_identifier("replace", "locator", self.locator)
        _validate_optional_identifier("replace", "observation_id", self.observation_id)
        _require_evidence(
            "replace", self.locator, self.observation_id, self.support, required=True
        )


@_dataclass(frozen=True)
class WithdrawActionWire:
    """One compact withdrawal; the reason is the semantic basis."""

    conclusion_id: str
    reason: str
    locator: str | None = None
    observation_id: str | None = None
    support: tuple[SupportWire, ...] = ()

    def __post_init__(self) -> None:
        _require_action_field("withdraw", "conclusion_id", self.conclusion_id)
        _require_action_field("withdraw", "reason", self.reason)
        _validate_optional_identifier("withdraw", "locator", self.locator)
        _validate_optional_identifier("withdraw", "observation_id", self.observation_id)
        _require_evidence(
            "withdraw", self.locator, self.observation_id, self.support, required=False
        )


@_dataclass(frozen=True)
class ConclusionRefWire:
    understanding_id: str
    conclusion_id: str
    revision: int


@_dataclass(frozen=True)
class UnresolvedDispositionWire:
    challenge_id: str
    expected_challenge_revision: int
    remaining_question: str
    basis: str


@_dataclass(frozen=True)
class ResolvedDispositionWire:
    challenge_id: str
    expected_challenge_revision: int
    reasoning: str
    resulting_understanding_id: str
    resulting_version: int
    conclusions: tuple[ConclusionRefWire, ...] = ()
    withdrawn: tuple[ConclusionRefWire, ...] = ()
    evidence_refs: tuple[str, ...] = ()


DispositionWire = _typing.Union[
    UnresolvedDispositionWire,
    ResolvedDispositionWire,
]

RecordActionWire = _typing.Union[
    AddConclusionWire,
    ConfirmConclusionWire,
    CorrectConclusionWire,
    ReplaceActionWire,
    WithdrawActionWire,
]


@_dataclass(frozen=True)
class IdentityWire:
    repository_id: str
    request_id: str
    #: Optional: a recording that cites locators/ranges is admitted into a
    #: server-issued context inside the operation (L2 §4.2, TD §12).
    context_id: str | None = None


@_dataclass(frozen=True)
class SurfaceKeyWire:
    """Exact surface identity used as a declaration parent."""

    kind: str
    locator: str

    def __post_init__(self) -> None:
        try:
            _surfaces.SurfaceKind(self.kind)
        except ValueError:
            raise ValueError(f"unknown surface kind: {self.kind!r}") from None
        if not self.locator:
            raise ValueError("SurfaceKeyWire.locator must be a non-empty string")


@_dataclass(frozen=True)
class SurfaceBoundaryWire:
    """Declared containment for a service or domain surface."""

    paths: tuple[str, ...] = ()
    symbols: tuple[str, ...] = ()


@_dataclass(frozen=True)
class SurfaceWire:
    """The surface a record request addresses.

    Understanding creates use only ``kind`` and ``locator``. Surface
    declarations may also carry a boundary and parent.
    """

    kind: str
    locator: str
    boundary: SurfaceBoundaryWire | None = None
    parent: SurfaceKeyWire | None = None

    def __post_init__(self) -> None:
        try:
            _surfaces.SurfaceKind(self.kind)
        except ValueError:
            raise ValueError(f"unknown surface kind: {self.kind!r}") from None
        if not self.locator:
            raise ValueError("SurfaceWire.locator must be a non-empty string")


@_dataclass(frozen=True)
class VerificationRunWire:
    repository_id: str
    scope_description: str
    scope_paths: tuple[str, ...]
    command: str | None
    scenario: str | None
    outcome: _v.VerificationOutcome
    observed_at: _datetime.datetime
    observer: str
    observations: tuple[str, ...] = ()
    evidence: tuple[SourceSupportWire, ...] = ()
    environment_limitations: tuple[str, ...] = ()
    provenance: str = ""

    def __post_init__(self) -> None:
        if not self.observations and not self.evidence:
            raise ValueError(
                "a verification run requires observations or evidence; supply "
                "the obs: ids ask returned for the context, or run.evidence "
                "with a locator"
            )


@_dataclass(frozen=True)
class RecordActionsWire:
    """The explicit semantic actions one record request states.

    Keys are actions, not tool variants. Multiple keys are applied atomically.
    """

    add: tuple[AddConclusionWire, ...] = ()
    confirm: tuple[ConfirmConclusionWire, ...] = ()
    correct: tuple[CorrectConclusionWire, ...] = ()
    replace: tuple[ReplaceActionWire, ...] = ()
    withdraw: tuple[WithdrawActionWire, ...] = ()


@_dataclass(frozen=True)
class RecordRequestWire:
    """One public record request, selected by ``kind``.

    ``kind`` selects understanding, verification, or surface declaration. The
    fields that do not belong to the selected kind fail closed in
    ``__post_init__``. Repository and request identity are flat on the wire,
    matching ``ask``; the internal recording identity is derived.
    """

    request_id: str
    kind: _c.RecordKind
    repository_id: str | None = None
    context: _InvestigationContextRef | None = None
    surface: SurfaceWire | None = None
    question: str | None = None
    scope_paths: tuple[str, ...] = ()
    #: Flat create form. One conclusion per create request; updates use
    #: ``actions``. ``locator`` is the file the conclusion is about;
    #: ``observation_id`` may replace it with an observation from ``ask``.
    #: Span derives the new conclusion lineage identity (L7).
    conclusion: str | None = None
    locator: str | None = None
    observation_id: str | None = None
    assertion_nature: AssertionNature | None = None
    support: tuple[SupportWire, ...] = ()
    understanding_id: str | None = None
    expected_version: int | None = None
    actions: RecordActionsWire | None = _field(
        default=None,
        metadata={
            "description": "Understanding update: an object of action lists, e.g. "
            '{"correct":[{"conclusion_id":"<returned id>","conclusion":"<statement>","locator":"<path>"}]}. '
            "Use understanding_id and expected_version; omit top-level action."
        },
    )
    run: VerificationRunWire | None = None
    action: _c.SurfaceAction | None = _field(
        default=None,
        metadata={
            "description": "Only for kind=surface declarations. Omit action for "
            "every kind=understanding create or update; updates use actions."
        },
    )
    expected_boundary_version: int | None = None
    gaps: tuple[GapWire, ...] | None = None
    challenge_dispositions: tuple[DispositionWire, ...] = ()
    provenance: str = ""

    @property
    def bound_repository_id(self) -> str:
        if self.context is not None:
            return self.context.repository_id
        if self.repository_id is None:
            raise ValueError("a direct record request requires repository_id")
        return self.repository_id

    @property
    def context_id(self) -> str | None:
        return None if self.context is None else self.context.context_id.value

    @property
    def identity(self) -> IdentityWire:
        return IdentityWire(
            repository_id=self.bound_repository_id,
            request_id=self.request_id,
            context_id=self.context_id,
        )

    def __post_init__(self) -> None:
        if not self.request_id:
            raise ValueError("RecordRequestWire.request_id must be non-empty")
        if self.context is not None:
            if self.repository_id is not None:
                raise ValueError("context-bound record carries no repository override")
        elif self.repository_id is None:
            raise ValueError("direct record requires repository_id")
        elif not self.repository_id:
            raise ValueError("RecordRequestWire.repository_id must be non-empty")
        if self.kind is _c.RecordKind.UNDERSTANDING:
            self._validate_understanding()
        elif self.kind is _c.RecordKind.VERIFICATION:
            self._validate_verification()
        elif self.kind is _c.RecordKind.SURFACE:
            self._validate_surface()

    def _validate_understanding(self) -> None:
        if self.run is not None or self.action is not None:
            raise ValueError(
                "an understanding record takes no run or action; a create is "
                "flat (conclusion plus locator, observation_id, or support), an "
                "update uses actions, and action belongs to kind=surface"
            )
        if self.expected_boundary_version is not None:
            raise ValueError("an understanding record does not take a boundary version")
        if self.actions is not None:
            self._validate_update()
            return
        if self.conclusion is not None:
            self._validate_create()
            return
        raise ValueError("an understanding record requires actions")

    def _validate_create(self) -> None:
        if not self.conclusion:
            raise ValueError("an understanding create requires a conclusion")
        if not self.support and self.locator is None and self.observation_id is None:
            raise ValueError(
                "an understanding create requires support, locator, or observation_id"
            )
        if self.locator is not None and self.observation_id is not None:
            raise ValueError(
                "an understanding create takes locator or observation_id, not both"
            )
        if self.support and self.observation_id is not None:
            raise ValueError(
                "an understanding create takes support or observation_id, not both; "
                "supply observation_id inside support when citing an admitted "
                "observation"
            )
        if self.question is None and self.context_id is None:
            raise ValueError(
                "an understanding create requires a question, or a context "
                "that already binds it"
            )
        if self.surface is not None and (
            self.surface.boundary is not None or self.surface.parent is not None
        ):
            raise ValueError(
                "an understanding record does not declare a boundary or parent"
            )
        if self.actions is not None and (
            self.actions.add
            or self.actions.confirm
            or self.actions.correct
            or self.actions.replace
            or self.actions.withdraw
        ):
            raise ValueError("create cannot be combined with update actions")
        if self.understanding_id is not None or self.expected_version is not None:
            raise ValueError("create does not take understanding_id or version")
        if self.challenge_dispositions:
            raise ValueError("create does not take challenge dispositions")

    def _validate_update(self) -> None:
        actions = self.actions
        assert actions is not None
        forbidden = [
            name
            for name in ("conclusion", "locator", "observation_id")
            if getattr(self, name) is not None
        ]
        if forbidden:
            raise ValueError(
                "an understanding update cannot contain top-level fields: "
                + ", ".join(forbidden)
                + "; put update content/evidence inside actions"
            )
        if self.question is not None:
            raise ValueError("an understanding update does not take a question")
        if self.surface is not None:
            raise ValueError("an understanding update does not take a surface")
        if self.scope_paths:
            raise ValueError(
                "an understanding update does not take root scope_paths; put a "
                "scope override on the action"
            )
        if self.support:
            raise ValueError(
                "an understanding update does not take root support; put the "
                "evidence on the action"
            )
        if self.assertion_nature is not None:
            raise ValueError(
                "an understanding update does not take root assertion_nature; put "
                "a nature override on the action"
            )
        if self.understanding_id is None or self.expected_version is None:
            raise ValueError(
                "an understanding update requires understanding_id and "
                "expected_version"
            )
        if not (
            actions.add
            or actions.confirm
            or actions.correct
            or actions.replace
            or actions.withdraw
            or self.challenge_dispositions
            or self.gaps is not None
        ):
            raise ValueError("an understanding update must have an effect")

    def _validate_verification(self) -> None:
        if self.run is None:
            raise ValueError("a verification record requires run")
        if (
            self.surface is not None
            or self.actions is not None
            or self.action is not None
            or self.question is not None
            or self.scope_paths
            or self.understanding_id is not None
            or self.expected_version is not None
            or self.expected_boundary_version is not None
            or self.gaps is not None
            or self.challenge_dispositions
            or self.conclusion is not None
            or self.locator is not None
            or self.observation_id is not None
            or self.support
            or self.assertion_nature is not None
        ):
            raise ValueError(
                "a verification record takes only run, context_id, and provenance"
            )

    def _validate_surface(self) -> None:
        if self.surface is None or self.action is None:
            raise ValueError("a surface record requires surface and action")
        declared = _surfaces.SurfaceKind(self.surface.kind).is_declared
        if self.surface.boundary is None:
            if declared:
                raise ValueError("a service or domain surface requires a boundary")
        elif not declared:
            raise ValueError("a file or symbol surface rejects a boundary")
        if (
            self.context is not None
            or self.actions is not None
            or self.run is not None
            or self.question is not None
            or self.scope_paths
            or self.understanding_id is not None
            or self.expected_version is not None
            or self.gaps is not None
            or self.challenge_dispositions
            or self.conclusion is not None
            or self.locator is not None
            or self.observation_id is not None
            or self.support
            or self.assertion_nature is not None
        ):
            raise ValueError(
                "a surface record takes only surface, action, "
                "expected_boundary_version, and provenance"
            )
        if self.action is _c.SurfaceAction.UPDATE:
            if self.expected_boundary_version is None:
                raise ValueError("a surface update requires expected_boundary_version")
        elif self.expected_boundary_version is not None:
            raise ValueError("a surface create does not take a boundary version")


def wire_content_digest(value: object) -> ContentDigest:
    """Hash one submitted wire payload, excluding its recording identity.

    This is the receipt-first digest: it is available before any evidence or
    authority reference is resolved, so a retained receipt can replay after
    its context was reaped. The same digest is passed to the atomic store.
    """
    canonical = to_canonical(value) if hasattr(value, "__dataclass_fields__") else value
    if not isinstance(canonical, dict):
        raise TypeError("a record wire payload must encode as an object")
    content = dict(canonical)
    content.pop("identity", None)
    if isinstance(value, RecordRequestWire):
        for key in ("repository_id", "request_id", "context"):
            content.pop(key, None)
    return payload_digest(content)


def _scope(
    paths: tuple[str, ...],
    references: tuple[str, ...],
    resolver: RecordWireResolver,
) -> _p.EvidenceScope:
    return _p.EvidenceScope(
        paths=paths,
        evidence_refs=tuple(resolver.reference(item) for item in references),
    )


def _support(
    value: SupportWire,
    resolver: RecordWireResolver,
) -> _s.SupportDependency:
    if isinstance(value, AdmittedSourceSupportWire):
        return _s.SourceSupport(
            observation_id=_p.SourceObservationId(value.observation_id)
        )
    if isinstance(value, SourceSupportWire):
        return _s.SourceSupport(
            observation_id=resolver.source(
                value.locator,
                tuple(
                    _SourceRange(
                        start_line=item.start_line,
                        end_line=item.end_line,
                    )
                    for item in value.ranges
                ),
            )
        )
    if isinstance(value, AuthoritySupportWire):
        return _s.AuthoritySupportDependency(
            authority=resolver.authority(value.authority_ref)
        )
    if isinstance(value, PremiseSupportWire):
        return _s.PremiseSupport(
            premise=_p.ConclusionRevisionRef(
                understanding_id=_p.UnderstandingId(value.understanding_id),
                conclusion_id=_p.ConclusionId(value.conclusion_id),
                revision=_p.ConclusionRevisionNumber(value.revision),
            )
        )
    if isinstance(value, DiscoveryBoundarySupportWire):
        scope = _p.EvidenceScope(
            paths=value.scope.paths,
            evidence_refs=tuple(
                resolver.reference(item) for item in value.scope.evidence_refs
            ),
        )
        return _s.DiscoverySupport(observation_id=resolver.discovery(scope))
    if isinstance(value, AdmittedDiscoverySupportWire):
        return _s.DiscoverySupport(
            observation_id=_p.DiscoveryObservationId(value.observation_id)
        )
    raise TypeError(f"unhandled support wire: {type(value).__name__}")


def _mechanical_basis(summary: str) -> _p.SemanticBasis:
    """The deterministic basis Span owns for an evidence-backed transition."""
    return _p.SemanticBasis(
        derivation=_p.DerivationKind.EXPLICIT_EVIDENCE,
        summary=summary,
        input_refs=(),
    )


def _action_support(
    locator: str | None,
    observation_id: str | None,
    support: tuple[SupportWire, ...],
    resolver: RecordWireResolver,
) -> tuple[_s.SupportDependency, ...]:
    if support:
        return tuple(_support(item, resolver) for item in support)
    if observation_id is not None:
        return (
            _s.SourceSupport(observation_id=_p.SourceObservationId(observation_id)),
        )
    if locator is not None:
        return (_s.SourceSupport(observation_id=resolver.source(locator, ())),)
    raise ValueError("an action requires locator, observation_id, or support")


def _support_source_paths(
    support: tuple[SupportWire, ...],
    resolver: RecordWireResolver,
) -> tuple[str, ...]:
    paths: list[str] = []
    for item in support:
        if isinstance(item, SourceSupportWire):
            paths.append(item.locator)
        elif isinstance(item, AdmittedSourceSupportWire):
            paths.append(resolver.observation_locator(item.observation_id))
    return tuple(paths)


def _add_scope(
    value: AddConclusionWire,
    resolver: RecordWireResolver,
) -> _p.EvidenceScope:
    if value.scope_paths:
        return _scope(value.scope_paths, (), resolver)
    paths: tuple[str, ...]
    if value.locator is not None:
        paths = (value.locator,)
    elif value.observation_id is not None:
        paths = (resolver.observation_locator(value.observation_id),)
    else:
        paths = _support_source_paths(value.support, resolver)
    unique = tuple(dict.fromkeys(path for path in paths if path))
    if len(unique) != 1:
        raise ValueError(
            "record.actions.add requires scope_paths: the supplied evidence "
            "does not identify exactly one source path"
        )
    return _scope(unique, (), resolver)


def _current_revision(
    current_revisions: tuple[_ConclusionRevision, ...],
    conclusion_id: str,
    action: str,
) -> _ConclusionRevision:
    for revision in current_revisions:
        if revision.conclusion_id.value == conclusion_id:
            return revision
    raise ValueError(
        f"record.actions.{action} targets conclusion {conclusion_id!r}, which "
        "is not a member of expected_version; name a conclusion in the current "
        "membership"
    )


def _supported_content(
    current: _ConclusionRevision,
    action: str,
) -> _SupportedConclusion:
    content = current.content
    if not isinstance(content, _SupportedConclusion):
        raise ValueError(
            f"record.actions.{action} targets conclusion "
            f"{current.conclusion_id.value!r}, which is withdrawn"
        )
    return content


def _add_proposed(
    value: AddConclusionWire,
    resolver: RecordWireResolver,
    conclusion_id: _p.ConclusionId,
) -> _c.ProposedConclusion:
    return _c.ProposedConclusion(
        conclusion_id=conclusion_id,
        statement=value.conclusion,
        assertion_nature=value.assertion_nature,
        scope=_add_scope(value, resolver),
        support=_action_support(
            value.locator, value.observation_id, value.support, resolver
        ),
        basis=_mechanical_basis("added from supplied support"),
    )


def _confirm_action(
    value: ConfirmConclusionWire,
    resolver: RecordWireResolver,
    current_revisions: tuple[_ConclusionRevision, ...],
) -> _c.ConfirmConclusion:
    content = _supported_content(
        _current_revision(current_revisions, value.conclusion_id, "confirm"),
        "confirm",
    )
    return _c.ConfirmConclusion(
        conclusion_id=_p.ConclusionId(value.conclusion_id),
        statement=content.statement,
        assertion_nature=content.assertion_nature,
        scope=content.scope,
        support=_action_support(
            value.locator, value.observation_id, value.support, resolver
        ),
        basis=_mechanical_basis("reassessed from supplied support"),
    )


def _correct_action(
    value: CorrectConclusionWire,
    resolver: RecordWireResolver,
    current_revisions: tuple[_ConclusionRevision, ...],
) -> _c.CorrectConclusion:
    content = _supported_content(
        _current_revision(current_revisions, value.conclusion_id, "correct"),
        "correct",
    )
    scope = (
        _scope(value.scope_paths, (), resolver) if value.scope_paths else content.scope
    )
    return _c.CorrectConclusion(
        conclusion_id=_p.ConclusionId(value.conclusion_id),
        statement=value.conclusion,
        assertion_nature=value.assertion_nature or content.assertion_nature,
        scope=scope,
        support=_action_support(
            value.locator, value.observation_id, value.support, resolver
        ),
        basis=_mechanical_basis("corrected from supplied support"),
    )


def _replace_action(
    value: ReplaceActionWire,
    resolver: RecordWireResolver,
    current_revisions: tuple[_ConclusionRevision, ...],
    new_conclusion_id: _p.ConclusionId,
) -> _c.ReplaceConclusion:
    current = _current_revision(current_revisions, value.conclusion_id, "replace")
    content = _supported_content(current, "replace")
    scope = (
        _scope(value.scope_paths, (), resolver) if value.scope_paths else content.scope
    )
    return _c.ReplaceConclusion(
        old=_p.ConclusionRevisionRef(
            understanding_id=current.understanding_id,
            conclusion_id=current.conclusion_id,
            revision=current.revision,
        ),
        new_conclusion_id=new_conclusion_id,
        replacement_basis=_p.SemanticBasis(
            derivation=_p.DerivationKind.SEMANTIC_INTERPRETATION,
            summary=value.reason,
            input_refs=(),
        ),
        statement=value.conclusion,
        assertion_nature=value.assertion_nature or content.assertion_nature,
        scope=scope,
        support=_action_support(
            value.locator, value.observation_id, value.support, resolver
        ),
        basis=_mechanical_basis("replaced from supplied support"),
    )


def _withdraw_action(
    value: WithdrawActionWire,
    resolver: RecordWireResolver,
) -> _c.WithdrawConclusion:
    support: tuple[_s.SupportDependency, ...] = ()
    if value.locator is not None or value.observation_id is not None or value.support:
        support = _action_support(
            value.locator, value.observation_id, value.support, resolver
        )
    return _c.WithdrawConclusion(
        conclusion_id=_p.ConclusionId(value.conclusion_id),
        basis=_p.SemanticBasis(
            derivation=_p.DerivationKind.SEMANTIC_INTERPRETATION,
            summary=value.reason,
            input_refs=(),
        ),
        support=support,
    )


def _identity(value: IdentityWire) -> _c.RecordingIdentity:
    if value.context_id is None:
        raise ValueError(
            "recording identity context_id must be resolved before command "
            "construction"
        )
    return _c.RecordingIdentity(
        repository_id=value.repository_id,
        request_id=_p.RequestId(value.request_id),
        context_id=_p.InvestigationContextId(value.context_id),
    )


def _gap(value: GapWire) -> _c.GapDraft:
    return _c.GapDraft(question=value.question, basis=value.basis)


def _disposition(
    value: DispositionWire,
    resolver: RecordWireResolver,
) -> _c.ChallengeDisposition:
    if isinstance(value, UnresolvedDispositionWire):
        return _c.UnresolvedChallengeDisposition(
            challenge_id=_p.ChallengeId(value.challenge_id),
            expected_challenge_revision=_p.ChallengeRevision(
                value.expected_challenge_revision
            ),
            remaining_question=value.remaining_question,
            basis=value.basis,
        )
    if isinstance(value, ResolvedDispositionWire):
        return _c.ResolvedChallengeDisposition(
            challenge_id=_p.ChallengeId(value.challenge_id),
            expected_challenge_revision=_p.ChallengeRevision(
                value.expected_challenge_revision
            ),
            reasoning=value.reasoning,
            resulting_understanding_id=_p.UnderstandingId(
                value.resulting_understanding_id
            ),
            resulting_version=_p.UnderstandingVersionNumber(value.resulting_version),
            conclusions=tuple(
                _p.ConclusionRevisionRef(
                    understanding_id=_p.UnderstandingId(item.understanding_id),
                    conclusion_id=_p.ConclusionId(item.conclusion_id),
                    revision=_p.ConclusionRevisionNumber(item.revision),
                )
                for item in value.conclusions
            ),
            withdrawn=tuple(
                _p.ConclusionRevisionRef(
                    understanding_id=_p.UnderstandingId(item.understanding_id),
                    conclusion_id=_p.ConclusionId(item.conclusion_id),
                    revision=_p.ConclusionRevisionNumber(item.revision),
                )
                for item in value.withdrawn
            ),
            evidence=tuple(resolver.reference(item) for item in value.evidence_refs),
        )
    raise TypeError(f"unhandled disposition wire: {type(value).__name__}")


def _verification_command(
    identity: IdentityWire,
    run: VerificationRunWire,
) -> _c.RecordVerificationCommand:
    return _c.RecordVerificationCommand(
        identity=_identity(identity),
        run=_v.ProposedVerificationRun(
            repository_id=run.repository_id,
            scope=_v.VerificationScope(
                description=run.scope_description,
                scope=_p.EvidenceScope(paths=run.scope_paths),
            ),
            observations=tuple(
                _p.SourceObservationId(item) for item in run.observations
            ),
            command=run.command,
            scenario=run.scenario,
            outcome=run.outcome,
            observed_at=run.observed_at,
            observer=run.observer,
            environment_limitations=run.environment_limitations,
            provenance=run.provenance,
        ),
    )


def _surface_key(value: SurfaceWire, identity: IdentityWire) -> _surfaces.SurfaceKey:
    return _surfaces.SurfaceKey(
        repository_id=identity.repository_id,
        kind=_surfaces.SurfaceKind(value.kind),
        locator=value.locator,
    )


def surface_declaration(value: RecordRequestWire) -> _surfaces.Surface:
    """Project one surface declaration request into the canonical carrier."""
    if value.surface is None or value.action is None:
        raise ValueError("a surface record requires surface and action")
    key = _surface_key(value.surface, value.identity)
    boundary = _surfaces.SurfaceBoundary(
        paths=() if value.surface.boundary is None else value.surface.boundary.paths,
        symbols=(
            () if value.surface.boundary is None else value.surface.boundary.symbols
        ),
    )
    parent = (
        None
        if value.surface.parent is None
        else _surfaces.SurfaceKey(
            repository_id=value.identity.repository_id,
            kind=_surfaces.SurfaceKind(value.surface.parent.kind),
            locator=value.surface.parent.locator,
        )
    )
    version = (
        1
        if value.action is _c.SurfaceAction.CREATE
        else _typing.cast(int, value.expected_boundary_version) + 1
    )
    return _surfaces.Surface(
        key=key,
        boundary=boundary,
        parent=parent,
        boundary_version=version,
    )


def flat_conclusion(
    value: RecordRequestWire,
    resolver: RecordWireResolver,
    *,
    locator: str,
    default_support: _s.SupportDependency | None,
    scope: _p.EvidenceScope,
) -> _c.ProposedConclusion:
    """Build one conclusion from the flat create fields."""
    if value.support:
        support = tuple(_support(item, resolver) for item in value.support)
    elif default_support is not None:
        support = (default_support,)
    else:
        raise ValueError("a flat create requires support, locator, or observation_id")
    return _c.ProposedConclusion(
        conclusion_id=conclusion_identity(
            value.bound_repository_id, value.request_id, "create", 0
        ),
        statement=_typing.cast(str, value.conclusion),
        assertion_nature=value.assertion_nature or AssertionNature.DESCRIPTIVE,
        scope=scope,
        support=support,
        basis=_p.SemanticBasis(
            derivation=_p.DerivationKind.EXPLICIT_EVIDENCE,
            summary=(
                f"read {locator}" if locator else "recorded from admitted support"
            ),
            input_refs=(),
        ),
    )


def record_command(
    value: RecordRequestWire,
    resolver: RecordWireResolver,
    *,
    context_bound: bool = False,
    derived_surface: _surfaces.SurfaceKey | None = None,
    derived_scope: _p.EvidenceScope | None = None,
    derived_conclusions: tuple[_c.ProposedConclusion, ...] | None = None,
    current_revisions: tuple[_ConclusionRevision, ...] = (),
) -> _c.RecordCommand:
    """Decode one public record request into its canonical command."""
    if value.kind is _c.RecordKind.UNDERSTANDING:
        identity = _identity(value.identity)
        if value.conclusion is not None:
            if derived_conclusions is None or derived_scope is None:
                raise ValueError(
                    "a flat create requires the service to resolve its support"
                )
            surface = (
                _surface_key(value.surface, value.identity)
                if value.surface is not None
                else derived_surface
            )
            if surface is None:
                raise ValueError(
                    "an understanding create requires a surface or a carried scope"
                )
            target: _c.UnderstandingTarget
            if context_bound:
                target = _c.ContextBoundTarget()
            else:
                target = _c.ExplicitTarget(
                    question=_typing.cast(str, value.question),
                    scope=derived_scope,
                )
            return _c.CreateUnderstandingCommand(
                identity=identity,
                surface=surface,
                target=target,
                conclusions=derived_conclusions,
                gaps=tuple(_gap(item) for item in (value.gaps or ())),
                provenance=value.provenance,
            )
        actions = value.actions
        if actions is None:
            raise ValueError("an understanding record requires actions")
        if value.understanding_id is None or value.expected_version is None:
            raise ValueError("an understanding update requires identity and version")
        return _c.UpdateUnderstandingCommand(
            identity=identity,
            understanding_id=_p.UnderstandingId(value.understanding_id),
            expected_version=_p.UnderstandingVersionNumber(value.expected_version),
            add=tuple(
                _add_proposed(
                    item,
                    resolver,
                    conclusion_identity(
                        value.bound_repository_id, value.request_id, "add", position
                    ),
                )
                for position, item in enumerate(actions.add)
            ),
            confirm=tuple(
                _confirm_action(item, resolver, current_revisions)
                for item in actions.confirm
            ),
            correct=tuple(
                _correct_action(item, resolver, current_revisions)
                for item in actions.correct
            ),
            replace=tuple(
                _replace_action(
                    item,
                    resolver,
                    current_revisions,
                    conclusion_identity(
                        value.bound_repository_id, value.request_id, "replace", position
                    ),
                )
                for position, item in enumerate(actions.replace)
            ),
            withdraw=tuple(
                _withdraw_action(item, resolver) for item in actions.withdraw
            ),
            gaps=(
                None if value.gaps is None else tuple(_gap(item) for item in value.gaps)
            ),
            challenge_dispositions=tuple(
                _disposition(item, resolver) for item in value.challenge_dispositions
            ),
            provenance=value.provenance,
        )
    if value.kind is _c.RecordKind.VERIFICATION:
        if value.run is None:
            raise ValueError("a verification record requires run")
        return _verification_command(value.identity, value.run)
    raise ValueError("a surface declaration is not a record command")
