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
from dataclasses import dataclass as _dataclass

from span.core.identity import payload_digest
from span.core.model.canonical import to_canonical
from span.core.model import commands as _c
from span.core.model import primitives as _p
from span.core.model import support as _s
from span.core.model import surfaces as _surfaces
from span.core.model import verification as _v
from span.core.model.investigation import SourceRange as _SourceRange
from span.core.model.recording import ContentDigest
from span.core.model.claims import AssertionNature


@_dataclass(frozen=True)
class RecordWireResolver:
    """Required resolution supplied by the service boundary."""

    reference: _typing.Callable[[str], _p.EvidenceRef]
    authority: _typing.Callable[[str], _p.AuthorityBinding]
    source: _typing.Callable[[str, tuple[_SourceRange, ...]], _p.SourceObservationId]
    discovery: _typing.Callable[[_p.EvidenceScope], _p.DiscoveryObservationId]


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


@_dataclass(frozen=True)
class ConclusionWire:
    conclusion_id: str
    statement: str
    assertion_nature: AssertionNature
    scope_paths: tuple[str, ...]
    scope_evidence_refs: tuple[str, ...]
    support: tuple[SupportWire, ...]
    basis_derivation: _p.DerivationKind
    basis_summary: str
    basis_input_refs: tuple[str, ...]


@_dataclass(frozen=True)
class ReplaceWire:
    old_understanding_id: str
    old_conclusion_id: str
    old_revision: int
    new_conclusion: ConclusionWire
    replacement_basis_derivation: _p.DerivationKind
    replacement_basis_summary: str
    replacement_basis_input_refs: tuple[str, ...]


@_dataclass(frozen=True)
class WithdrawWire:
    conclusion_id: str
    basis_derivation: _p.DerivationKind
    basis_summary: str
    basis_input_refs: tuple[str, ...]
    support: tuple[SupportWire, ...] = ()


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


@_dataclass(frozen=True)
class IdentityWire:
    repository_id: str
    request_id: str
    #: Optional: a recording that cites locators/ranges is admitted into a
    #: server-issued context inside the operation (L2 §4.2, TD §12).
    context_id: str | None = None


@_dataclass(frozen=True)
class ContextBoundTargetWire:
    pass


@_dataclass(frozen=True)
class ExplicitTargetWire:
    question: str
    scope_paths: tuple[str, ...]
    scope_evidence_refs: tuple[str, ...]


TargetWire = _typing.Union[ContextBoundTargetWire, ExplicitTargetWire]


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
class RecordCreateWire:
    identity: IdentityWire
    surface: SurfaceWire
    target: TargetWire
    conclusions: tuple[ConclusionWire, ...]
    gaps: tuple[GapWire, ...] = ()
    provenance: str = ""


@_dataclass(frozen=True)
class RecordUpdateWire:
    identity: IdentityWire
    understanding_id: str
    expected_version: int
    add: tuple[ConclusionWire, ...] = ()
    confirm: tuple[ConclusionWire, ...] = ()
    correct: tuple[ConclusionWire, ...] = ()
    replace: tuple[ReplaceWire, ...] = ()
    withdraw: tuple[WithdrawWire, ...] = ()
    gaps: tuple[GapWire, ...] | None = None
    challenge_dispositions: tuple[DispositionWire, ...] = ()
    provenance: str = ""


@_dataclass(frozen=True)
class RecordAddWire:
    identity: IdentityWire
    understanding_id: str
    expected_version: int
    conclusion: ConclusionWire


@_dataclass(frozen=True)
class RecordConfirmWire:
    identity: IdentityWire
    understanding_id: str
    expected_version: int
    conclusion: ConclusionWire


@_dataclass(frozen=True)
class RecordCorrectWire:
    identity: IdentityWire
    understanding_id: str
    expected_version: int
    conclusion: ConclusionWire


@_dataclass(frozen=True)
class RecordReplaceWire:
    identity: IdentityWire
    understanding_id: str
    expected_version: int
    replacement: ReplaceWire


@_dataclass(frozen=True)
class RecordWithdrawWire:
    identity: IdentityWire
    understanding_id: str
    expected_version: int
    withdrawal: WithdrawWire


@_dataclass(frozen=True)
class ChallengeConclusionRefWire:
    understanding_id: str
    conclusion_id: str
    revision: int


@_dataclass(frozen=True)
class RecordChallengeWire:
    identity: IdentityWire
    understanding_id: str
    target_version: int
    target_conclusions: tuple[ChallengeConclusionRefWire, ...]
    reason: str
    evidence_refs: tuple[str, ...] = ()
    provenance: str = ""


@_dataclass(frozen=True)
class VerificationRunWire:
    repository_id: str
    scope_description: str
    scope_paths: tuple[str, ...]
    observations: tuple[str, ...]
    command: str | None
    scenario: str | None
    outcome: _v.VerificationOutcome
    observed_at: _datetime.datetime
    observer: str
    evidence: tuple[SourceSupportWire, ...] = ()
    environment_limitations: tuple[str, ...] = ()
    provenance: str = ""


@_dataclass(frozen=True)
class RecordVerificationWire:
    identity: IdentityWire
    run: VerificationRunWire


@_dataclass(frozen=True)
class RecordActionsWire:
    """The explicit semantic actions one record request states.

    Keys are actions, not tool variants. Multiple keys are applied atomically.
    """

    add: tuple[ConclusionWire, ...] = ()
    confirm: tuple[ConclusionWire, ...] = ()
    correct: tuple[ConclusionWire, ...] = ()
    replace: tuple[ReplaceWire, ...] = ()
    withdraw: tuple[WithdrawWire, ...] = ()


@_dataclass(frozen=True)
class RecordRequestWire:
    """One public record request, selected by ``kind``.

    ``kind`` selects understanding, verification, or surface declaration. The
    fields that do not belong to the selected kind fail closed in
    ``__post_init__``. Repository and request identity are flat on the wire,
    matching ``ask``; the internal recording identity is derived.
    """

    repository_id: str
    request_id: str
    kind: _c.RecordKind
    context_id: str | None = None
    surface: SurfaceWire | None = None
    question: str | None = None
    scope_paths: tuple[str, ...] = ()
    scope_evidence_refs: tuple[str, ...] = ()
    #: Flat create form. One conclusion per create request; updates use
    #: ``actions``. ``locator`` is the file the conclusion is about;
    #: ``observation_id`` may replace it with an observation from ``ask``.
    conclusion: str | None = None
    conclusion_id: str = "c-1"
    locator: str | None = None
    observation_id: str | None = None
    assertion_nature: AssertionNature = AssertionNature.DESCRIPTIVE
    support: tuple[SupportWire, ...] = ()
    understanding_id: str | None = None
    expected_version: int | None = None
    actions: RecordActionsWire | None = None
    run: VerificationRunWire | None = None
    action: _c.SurfaceAction | None = None
    expected_boundary_version: int | None = None
    gaps: tuple[GapWire, ...] | None = None
    challenge_dispositions: tuple[DispositionWire, ...] = ()
    provenance: str = ""

    @property
    def identity(self) -> IdentityWire:
        """The internal recording identity derived from the flat wire."""
        return IdentityWire(
            repository_id=self.repository_id,
            request_id=self.request_id,
            context_id=self.context_id,
        )

    def __post_init__(self) -> None:
        if not self.repository_id:
            raise ValueError("RecordRequestWire.repository_id must be non-empty")
        if not self.request_id:
            raise ValueError("RecordRequestWire.request_id must be non-empty")
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
                "flat (conclusion plus locator or observation_id), an update "
                "uses actions, and action belongs to kind=surface"
            )
        if self.expected_boundary_version is not None:
            raise ValueError("an understanding record does not take a boundary version")
        if self.conclusion is not None:
            self._validate_create()
            return
        if self.actions is None:
            raise ValueError("an understanding record requires actions")
        self._validate_update()

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

    def _validate_update(self) -> None:
        actions = self.actions
        assert actions is not None
        if (
            self.conclusion is not None
            or self.locator is not None
            or self.observation_id is not None
        ):
            raise ValueError("an understanding update does not take a flat conclusion")
        if self.question is not None:
            raise ValueError("an understanding update does not take a question")
        if self.surface is not None:
            raise ValueError("an understanding update does not take a surface")
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
            or self.understanding_id is not None
            or self.expected_version is not None
            or self.expected_boundary_version is not None
            or self.gaps is not None
            or self.challenge_dispositions
            or self.conclusion is not None
            or self.locator is not None
            or self.observation_id is not None
        ):
            raise ValueError("a verification record takes only run and provenance")

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
            self.actions is not None
            or self.run is not None
            or self.question is not None
            or self.understanding_id is not None
            or self.expected_version is not None
            or self.gaps is not None
            or self.challenge_dispositions
            or self.conclusion is not None
            or self.locator is not None
            or self.observation_id is not None
        ):
            raise ValueError(
                "a surface record takes only surface, action, and provenance"
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
        for key in ("repository_id", "request_id", "context_id"):
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


def _basis(
    derivation: _p.DerivationKind,
    summary: str,
    references: tuple[str, ...],
    resolver: RecordWireResolver,
) -> _p.SemanticBasis:
    return _p.SemanticBasis(
        derivation=derivation,
        summary=summary,
        input_refs=tuple(resolver.reference(item) for item in references),
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


def _content(
    value: ConclusionWire,
    resolver: RecordWireResolver,
) -> tuple[
    str,
    AssertionNature,
    _p.EvidenceScope,
    tuple[_s.SupportDependency, ...],
    _p.SemanticBasis,
]:
    return (
        value.statement,
        value.assertion_nature,
        _scope(value.scope_paths, value.scope_evidence_refs, resolver),
        tuple(_support(item, resolver) for item in value.support),
        _basis(
            value.basis_derivation,
            value.basis_summary,
            value.basis_input_refs,
            resolver,
        ),
    )


def _proposed(
    value: ConclusionWire,
    resolver: RecordWireResolver,
) -> _c.ProposedConclusion:
    statement, nature, scope, support, basis = _content(value, resolver)
    return _c.ProposedConclusion(
        conclusion_id=_p.ConclusionId(value.conclusion_id),
        statement=statement,
        assertion_nature=nature,
        scope=scope,
        support=support,
        basis=basis,
    )


def _confirm(
    value: ConclusionWire,
    resolver: RecordWireResolver,
) -> _c.ConfirmConclusion:
    statement, nature, scope, support, basis = _content(value, resolver)
    return _c.ConfirmConclusion(
        conclusion_id=_p.ConclusionId(value.conclusion_id),
        statement=statement,
        assertion_nature=nature,
        scope=scope,
        support=support,
        basis=basis,
    )


def _correct(
    value: ConclusionWire,
    resolver: RecordWireResolver,
) -> _c.CorrectConclusion:
    statement, nature, scope, support, basis = _content(value, resolver)
    return _c.CorrectConclusion(
        conclusion_id=_p.ConclusionId(value.conclusion_id),
        statement=statement,
        assertion_nature=nature,
        scope=scope,
        support=support,
        basis=basis,
    )


def _replace(
    value: ReplaceWire,
    resolver: RecordWireResolver,
) -> _c.ReplaceConclusion:
    statement, nature, scope, support, basis = _content(value.new_conclusion, resolver)
    return _c.ReplaceConclusion(
        old=_p.ConclusionRevisionRef(
            understanding_id=_p.UnderstandingId(value.old_understanding_id),
            conclusion_id=_p.ConclusionId(value.old_conclusion_id),
            revision=_p.ConclusionRevisionNumber(value.old_revision),
        ),
        new_conclusion_id=_p.ConclusionId(value.new_conclusion.conclusion_id),
        replacement_basis=_basis(
            value.replacement_basis_derivation,
            value.replacement_basis_summary,
            value.replacement_basis_input_refs,
            resolver,
        ),
        statement=statement,
        assertion_nature=nature,
        scope=scope,
        support=support,
        basis=basis,
    )


def _withdraw(
    value: WithdrawWire,
    resolver: RecordWireResolver,
) -> _c.WithdrawConclusion:
    return _c.WithdrawConclusion(
        conclusion_id=_p.ConclusionId(value.conclusion_id),
        basis=_basis(
            value.basis_derivation,
            value.basis_summary,
            value.basis_input_refs,
            resolver,
        ),
        support=tuple(_support(item, resolver) for item in value.support),
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


def _single_update(
    identity: IdentityWire,
    understanding_id: str,
    expected_version: int,
    *,
    add: tuple[_c.ProposedConclusion, ...] = (),
    confirm: tuple[_c.ConfirmConclusion, ...] = (),
    correct: tuple[_c.CorrectConclusion, ...] = (),
    replace: tuple[_c.ReplaceConclusion, ...] = (),
    withdraw: tuple[_c.WithdrawConclusion, ...] = (),
) -> _c.UpdateUnderstandingCommand:
    return _c.UpdateUnderstandingCommand(
        identity=_identity(identity),
        understanding_id=_p.UnderstandingId(understanding_id),
        expected_version=_p.UnderstandingVersionNumber(expected_version),
        add=add,
        confirm=confirm,
        correct=correct,
        replace=replace,
        withdraw=withdraw,
    )


def add_command(
    value: RecordAddWire,
    resolver: RecordWireResolver,
) -> _c.UpdateUnderstandingCommand:
    return _single_update(
        value.identity,
        value.understanding_id,
        value.expected_version,
        add=(_proposed(value.conclusion, resolver),),
    )


def confirm_command(
    value: RecordConfirmWire,
    resolver: RecordWireResolver,
) -> _c.UpdateUnderstandingCommand:
    return _single_update(
        value.identity,
        value.understanding_id,
        value.expected_version,
        confirm=(_confirm(value.conclusion, resolver),),
    )


def correct_command(
    value: RecordCorrectWire,
    resolver: RecordWireResolver,
) -> _c.UpdateUnderstandingCommand:
    return _single_update(
        value.identity,
        value.understanding_id,
        value.expected_version,
        correct=(_correct(value.conclusion, resolver),),
    )


def replace_command(
    value: RecordReplaceWire,
    resolver: RecordWireResolver,
) -> _c.UpdateUnderstandingCommand:
    return _single_update(
        value.identity,
        value.understanding_id,
        value.expected_version,
        replace=(_replace(value.replacement, resolver),),
    )


def withdraw_command(
    value: RecordWithdrawWire,
    resolver: RecordWireResolver,
) -> _c.UpdateUnderstandingCommand:
    return _single_update(
        value.identity,
        value.understanding_id,
        value.expected_version,
        withdraw=(_withdraw(value.withdrawal, resolver),),
    )


def create_command(
    value: RecordCreateWire,
    resolver: RecordWireResolver,
) -> _c.CreateUnderstandingCommand:
    identity = _identity(value.identity)
    target: _c.UnderstandingTarget
    if isinstance(value.target, ContextBoundTargetWire):
        target = _c.ContextBoundTarget()
    else:
        target = _c.ExplicitTarget(
            question=value.target.question,
            scope=_scope(
                value.target.scope_paths,
                value.target.scope_evidence_refs,
                resolver,
            ),
        )
    surface = _surfaces.SurfaceKey(
        repository_id=identity.repository_id,
        kind=_surfaces.SurfaceKind(value.surface.kind),
        locator=value.surface.locator,
    )
    return _c.CreateUnderstandingCommand(
        identity=identity,
        surface=surface,
        target=target,
        conclusions=tuple(_proposed(item, resolver) for item in value.conclusions),
        gaps=tuple(_gap(item) for item in value.gaps),
        provenance=value.provenance,
    )


def update_command(
    value: RecordUpdateWire,
    resolver: RecordWireResolver,
) -> _c.UpdateUnderstandingCommand:
    return _c.UpdateUnderstandingCommand(
        identity=_identity(value.identity),
        understanding_id=_p.UnderstandingId(value.understanding_id),
        expected_version=_p.UnderstandingVersionNumber(value.expected_version),
        add=tuple(_proposed(item, resolver) for item in value.add),
        confirm=tuple(_confirm(item, resolver) for item in value.confirm),
        correct=tuple(_correct(item, resolver) for item in value.correct),
        replace=tuple(_replace(item, resolver) for item in value.replace),
        withdraw=tuple(_withdraw(item, resolver) for item in value.withdraw),
        gaps=None if value.gaps is None else tuple(_gap(item) for item in value.gaps),
        challenge_dispositions=tuple(
            _disposition(item, resolver) for item in value.challenge_dispositions
        ),
        provenance=value.provenance,
    )


def challenge_command(
    value: RecordChallengeWire,
    resolver: RecordWireResolver,
) -> _c.CreateChallengeCommand:
    return _c.CreateChallengeCommand(
        identity=_identity(value.identity),
        understanding_id=_p.UnderstandingId(value.understanding_id),
        target_version=_p.UnderstandingVersionNumber(value.target_version),
        target_conclusions=tuple(
            _p.ConclusionRevisionRef(
                understanding_id=_p.UnderstandingId(item.understanding_id),
                conclusion_id=_p.ConclusionId(item.conclusion_id),
                revision=_p.ConclusionRevisionNumber(item.revision),
            )
            for item in value.target_conclusions
        ),
        reason=value.reason,
        evidence=tuple(resolver.reference(item) for item in value.evidence_refs),
        provenance=value.provenance,
    )


def verification_command(
    value: RecordVerificationWire,
) -> _c.RecordVerificationCommand:
    return _verification_command(value.identity, value.run)


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
) -> _c.ProposedConclusion:
    """Build one conclusion from the flat create fields."""
    if value.support:
        support = tuple(_support(item, resolver) for item in value.support)
    elif default_support is not None:
        support = (default_support,)
    else:
        raise ValueError("a flat create requires support, locator, or observation_id")
    return _c.ProposedConclusion(
        conclusion_id=_p.ConclusionId(value.conclusion_id),
        statement=_typing.cast(str, value.conclusion),
        assertion_nature=value.assertion_nature,
        scope=_p.EvidenceScope(paths=value.scope_paths or (locator,)),
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
    derived_conclusions: tuple[_c.ProposedConclusion, ...] | None = None,
) -> _c.RecordCommand:
    """Decode one public record request into its canonical command."""
    if value.kind is _c.RecordKind.UNDERSTANDING:
        identity = _identity(value.identity)
        if value.conclusion is not None:
            if derived_conclusions is None:
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
                    scope=_scope(
                        value.scope_paths,
                        value.scope_evidence_refs,
                        resolver,
                    ),
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
            add=tuple(_proposed(item, resolver) for item in actions.add),
            confirm=tuple(_confirm(item, resolver) for item in actions.confirm),
            correct=tuple(_correct(item, resolver) for item in actions.correct),
            replace=tuple(_replace(item, resolver) for item in actions.replace),
            withdraw=tuple(_withdraw(item, resolver) for item in actions.withdraw),
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
