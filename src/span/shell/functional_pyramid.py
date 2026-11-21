"""Filesystem-backed Functional Pyramid declaration source."""

from __future__ import annotations

import datetime as _datetime
import typing as _typing

from span.core import functional_pyramid as _fp
from span.core import model as m
from span.ports.evidence import EvidenceSource
from span.ports.functional_pyramid import (
    FunctionalPyramidDeclarationInvalid,
    FunctionalPyramidDeclarationPort,
    FunctionalPyramidRepositoryUnavailable,
    FunctionalPyramidStatePort,
    FunctionalPyramidStateTransaction,
)
from span.ports.lifecycle import LifecycleStorePort
from span.shell.filesystem_evidence import FilesystemEvidenceSource
from span.shell.sqlite_store.lifecycle import UnknownRepository
from span.service.contexts import ContextBinding, build_context
from span.service.effects import DependencyEffectService
from span.service.functional_pyramid import FunctionalPyramidService
from span.service.ids import server_context_id
from span.service.support import SupportService


class FilesystemFunctionalPyramidDeclarations(FunctionalPyramidDeclarationPort):
    """Read strict declarations from registered repository roots."""

    def __init__(self, repository_root: _typing.Callable[[str], str]) -> None:
        self._repository_root = repository_root

    def _source(self, repository_id: str) -> FilesystemEvidenceSource:
        try:
            root = self._repository_root(repository_id)
        except (OSError, ValueError, UnknownRepository) as exc:
            raise FunctionalPyramidRepositoryUnavailable(
                f"Functional Pyramid member {repository_id!r} is unavailable"
            ) from exc
        return FilesystemEvidenceSource(repository_id, root)

    def read_bootstrap(
        self, repository_id: str
    ) -> tuple[m.EvidenceRef, m.FunctionalPyramidBootstrap] | None:
        request = m.EvidenceRequest(".span/functional-pyramid.json")
        result = self._source(repository_id).read_exact(repository_id, request, None)
        if isinstance(result, m.EvidenceSourceFailure):
            if result.kind is m.EvidenceSourceFailureKind.MISSING:
                return None
            raise FunctionalPyramidDeclarationInvalid(
                "Functional Pyramid bootstrap cannot be read"
            )
        try:
            bootstrap = _fp.decode_functional_pyramid_bootstrap(result.content)
        except ValueError as exc:
            raise FunctionalPyramidDeclarationInvalid(
                "Functional Pyramid bootstrap violates the Version-1 contract"
            ) from exc
        return result.evidence_ref, bootstrap

    def read_declaration(
        self, repository_id: str, request: m.EvidenceRequest
    ) -> tuple[m.EvidenceRef, m.FunctionalPyramidDeclaration] | m.EvidenceSourceFailure:
        if request.ranges:
            raise FunctionalPyramidDeclarationInvalid(
                "Functional Pyramid declaration sources must be whole documents"
            )
        result = self._source(repository_id).read_exact(repository_id, request, None)
        if isinstance(result, m.EvidenceSourceFailure):
            return result
        try:
            declaration = _fp.decode_functional_pyramid_declaration(result.content)
        except ValueError as exc:
            raise FunctionalPyramidDeclarationInvalid(
                "Functional Pyramid declaration violates the Version-1 contract"
            ) from exc
        return result.evidence_ref, declaration


class FunctionalPyramidRepositoryRuntime(_typing.Protocol):
    repository_id: str
    root: str
    store: LifecycleStorePort
    evidence: EvidenceSource


class _InstallationAuthorityResolver:
    def __init__(
        self,
        repository_runtime: _typing.Callable[[str], FunctionalPyramidRepositoryRuntime],
    ) -> None:
        self._repository_runtime = repository_runtime

    def resolve_authority(
        self, repository_id: str, authority_ref: str
    ) -> m.AuthorityBinding:
        return self._repository_runtime(repository_id).store.resolve_authority(
            repository_id, authority_ref
        )


def compose_functional_pyramid_service(
    *,
    state: FunctionalPyramidStatePort,
    repository_runtime: _typing.Callable[[str], FunctionalPyramidRepositoryRuntime],
    registered_repository_ids: _typing.Callable[[], tuple[str, ...]],
    repository_paths: _typing.Callable[[tuple[str, ...]], tuple[tuple[str, str], ...]],
    clock: _typing.Callable[[], _datetime.datetime] | None = None,
    new_context_id: _typing.Callable[[], str] | None = None,
) -> FunctionalPyramidService:
    """Compose the one installation-wide Functional Pyramid service."""
    coordinator: FunctionalPyramidEffectCoordinator | None = None

    def project_change(
        transaction: FunctionalPyramidStateTransaction,
        action: m.FunctionalPyramidAction,
        pyramid_id: m.FunctionalPyramidId,
        old_members: tuple[m.FunctionalPyramidMemberView, ...],
        new_members: tuple[m.FunctionalPyramidMemberView, ...],
    ) -> tuple[
        tuple[m.ChangedSurface, ...],
        tuple[m.InvestigationContextRef, ...],
        tuple[m.ConclusionRevisionRef, ...],
    ]:
        if coordinator is None:
            raise RuntimeError(
                "Functional Pyramid effect coordinator is not initialized"
            )
        return coordinator.change(
            transaction,
            action,
            pyramid_id,
            old_members,
            new_members,
        )

    def project_retained(
        transaction: FunctionalPyramidStateTransaction,
        refs: tuple[m.ConclusionRevisionRef, ...],
    ) -> tuple[
        tuple[m.ChangedSurface, ...],
        tuple[m.InvestigationContextRef, ...],
    ]:
        if coordinator is None:
            raise RuntimeError(
                "Functional Pyramid effect coordinator is not initialized"
            )
        return coordinator.retained(transaction, refs)

    service = FunctionalPyramidService(
        declarations=FilesystemFunctionalPyramidDeclarations(
            lambda repository_id: repository_runtime(repository_id).root
        ),
        authority=_InstallationAuthorityResolver(repository_runtime),
        state=state,
        registered_repository_ids=registered_repository_ids,
        repository_paths=repository_paths,
        effect_projection=project_change,
        retained_effect_projection=project_retained,
        clock=clock,
    )
    coordinator = FunctionalPyramidEffectCoordinator(
        service=service,
        repository_runtime=repository_runtime,
        registered_repository_ids=registered_repository_ids,
        clock=clock,
        new_context_id=new_context_id,
    )
    return service


class FunctionalPyramidEffectCoordinator:
    """Project installation-scoped pyramid writes through repository effect engines."""

    def __init__(
        self,
        *,
        service: FunctionalPyramidService,
        repository_runtime: _typing.Callable[[str], FunctionalPyramidRepositoryRuntime],
        registered_repository_ids: _typing.Callable[[], tuple[str, ...]],
        clock: _typing.Callable[[], _datetime.datetime] | None = None,
        new_context_id: _typing.Callable[[], str] | None = None,
    ) -> None:
        self._service = service
        self._repository_runtime = repository_runtime
        self._registered_repository_ids = registered_repository_ids
        self._clock = clock or (lambda: _datetime.datetime.now(_datetime.timezone.utc))
        self._new_context_id = new_context_id or server_context_id

    def change(
        self,
        transaction: FunctionalPyramidStateTransaction,
        action: m.FunctionalPyramidAction,
        pyramid_id: m.FunctionalPyramidId,
        old_members: tuple[m.FunctionalPyramidMemberView, ...],
        new_members: tuple[m.FunctionalPyramidMemberView, ...],
    ) -> tuple[
        tuple[m.ChangedSurface, ...],
        tuple[m.InvestigationContextRef, ...],
        tuple[m.ConclusionRevisionRef, ...],
    ]:
        """Compute one accepted/proposed participation delta under transaction locks."""
        old = {member.repository_id for member in old_members}
        new = {member.repository_id for member in new_members}
        surfaces: list[m.ChangedSurface] = []
        contexts: list[m.InvestigationContextRef] = []
        refs: list[m.ConclusionRevisionRef] = []

        proposed_version = self._proposed_version(action, pyramid_id)
        for repository_id in sorted(old | new):
            runtime = self._repository_runtime(repository_id)
            route_ids: tuple[m.FunctionalRouteIdentity, ...] = ()
            if (
                action is m.FunctionalPyramidAction.REVISE
                and repository_id in old & new
            ):
                route_ids = self._changed_route_identities(
                    runtime=runtime,
                    pyramid_id=pyramid_id,
                    proposed_version=proposed_version,
                    members=new_members,
                )
            engine = self._effect_engine(runtime, transaction, current_support=False)
            projected, issued, effect_refs = engine.functional_pyramid_change(
                changed_route_identities=route_ids,
                newly_active_repositories=(
                    (repository_id,) if repository_id in new - old else ()
                ),
                deliberately_inactive_repositories=(
                    (repository_id,) if repository_id in old - new else ()
                ),
            )
            surfaces.extend(projected)
            contexts.extend(issued)
            refs.extend(effect_refs)

        return (
            self._merge_surfaces(tuple(surfaces)),
            tuple(
                sorted(
                    contexts,
                    key=lambda item: (item.repository_id, item.context_id.value),
                )
            ),
            tuple(sorted(set(refs), key=lambda item: item.sort_key)),
        )

    def retained(
        self,
        transaction: FunctionalPyramidStateTransaction,
        refs: tuple[m.ConclusionRevisionRef, ...],
    ) -> tuple[
        tuple[m.ChangedSurface, ...],
        tuple[m.InvestigationContextRef, ...],
    ]:
        """Live-project only retained immutable effect refs, grouped by owning repo."""
        grouped = self._group_refs_by_repository(refs)
        surfaces: list[m.ChangedSurface] = []
        contexts: list[m.InvestigationContextRef] = []
        for repository_id in sorted(grouped):
            runtime = self._repository_runtime(repository_id)
            engine = self._effect_engine(runtime, transaction, current_support=True)
            projected, issued = engine.retained_functional_pyramid_effects(
                grouped[repository_id]
            )
            surfaces.extend(projected)
            contexts.extend(issued)
        return (
            self._merge_surfaces(tuple(surfaces)),
            tuple(
                sorted(
                    contexts,
                    key=lambda item: (item.repository_id, item.context_id.value),
                )
            ),
        )

    def _effect_engine(
        self,
        runtime: FunctionalPyramidRepositoryRuntime,
        transaction: FunctionalPyramidStateTransaction,
        *,
        current_support: bool,
    ) -> DependencyEffectService:
        support = (
            SupportService(
                store=runtime.store,
                evidence=runtime.evidence,
                authority=runtime.store,
                functional_route_resolver=self._current_route,
            )
            if current_support
            else None
        )

        def issue(
            repository_id: str,
            context_id: str,
            binding: ContextBinding,
            source_observation_ids: tuple[str, ...],
            discovery_observation_ids: tuple[str, ...],
        ) -> m.InvestigationContextRef:
            context = build_context(
                retention=runtime.store.retention,
                binding=binding,
                repository_id=repository_id,
                request_id=m.RequestId(f"effects:{context_id}"),
                clock=self._clock,
                new_context_id=lambda: context_id,
            )
            transaction.write_reestablishment_context(
                context,
                source_observation_ids=source_observation_ids,
                discovery_observation_ids=discovery_observation_ids,
            )
            return m.InvestigationContextRef(
                repository_id=repository_id,
                context_id=context.context_id,
            )

        return DependencyEffectService(
            store=runtime.store,
            support=support,
            clock=self._clock,
            new_context_id=self._new_context_id,
            context_issuer=issue,
        )

    def _current_route(
        self,
        dependency: m.FunctionalRouteSupport,
        surface: m.SurfaceKey,
    ) -> tuple[
        m.FunctionalPyramidParticipation
        | m.FunctionalPyramidView
        | m.FunctionalPyramidUnavailable,
        m.FunctionalRouteIdentity | None,
    ]:
        status = self._service.status(
            m.FunctionalPyramidSelector(repository_id=dependency.repository_id)
        )
        if status.state is not m.FunctionalPyramidParticipationState.ACTIVE:
            return m.FunctionalPyramidParticipation(status.state), None
        assert status.pyramid_id is not None
        assert status.version is not None
        view, route_identity = self._service.resolve(
            pyramid_id=status.pyramid_id,
            version=status.version,
            members=status.members,
            surface=surface,
            semantic_scope=dependency.semantic_scope,
        )
        return view, route_identity

    def _changed_route_identities(
        self,
        *,
        runtime: FunctionalPyramidRepositoryRuntime,
        pyramid_id: m.FunctionalPyramidId,
        proposed_version: m.FunctionalPyramidVersion,
        members: tuple[m.FunctionalPyramidMemberView, ...],
    ) -> tuple[m.FunctionalRouteIdentity, ...]:
        changed: set[m.FunctionalRouteIdentity] = set()
        for understanding in runtime.store.list_understandings(runtime.repository_id):
            version = runtime.store.get_version(
                understanding.understanding_id.value,
                understanding.current_version.value,
            )
            revisions = {
                (revision.conclusion_id, revision.revision): revision
                for revision in runtime.store.get_conclusions(
                    understanding.understanding_id.value
                )
            }
            for ref in version.conclusions:
                revision = revisions.get((ref.conclusion_id, ref.revision))
                if revision is None or not isinstance(
                    revision.content, m.SupportedConclusion
                ):
                    continue
                for dependency in revision.content.support:
                    if not isinstance(dependency, m.FunctionalRouteSupport):
                        continue
                    if dependency.pyramid_id != pyramid_id:
                        continue
                    _, proposed_identity = self._service.resolve(
                        pyramid_id=pyramid_id,
                        version=proposed_version,
                        members=members,
                        surface=understanding.surface,
                        semantic_scope=dependency.semantic_scope,
                    )
                    if proposed_identity != dependency.route_identity:
                        changed.add(dependency.route_identity)
        return tuple(sorted(changed, key=lambda item: item.value))

    def _group_refs_by_repository(
        self, refs: tuple[m.ConclusionRevisionRef, ...]
    ) -> dict[str, tuple[m.ConclusionRevisionRef, ...]]:
        grouped: dict[str, list[m.ConclusionRevisionRef]] = {}
        repository_ids = self._registered_repository_ids()
        for ref in refs:
            owners = [
                repository_id
                for repository_id in repository_ids
                if self._repository_runtime(
                    repository_id
                ).store.has_conclusion_revision(
                    ref.understanding_id.value,
                    ref.conclusion_id.value,
                    ref.revision.value,
                )
            ]
            if len(owners) != 1:
                raise ValueError(
                    "retained Functional Pyramid effect ref must resolve to exactly "
                    f"one registered repository: {ref.label}"
                )
            grouped.setdefault(owners[0], []).append(ref)
        return {
            repository_id: tuple(sorted(values, key=lambda item: item.sort_key))
            for repository_id, values in grouped.items()
        }

    def _proposed_version(
        self,
        action: m.FunctionalPyramidAction,
        pyramid_id: m.FunctionalPyramidId,
    ) -> m.FunctionalPyramidVersion:
        if action is m.FunctionalPyramidAction.ACTIVATE:
            return m.FunctionalPyramidVersion(1)
        current = self._service.status(
            m.FunctionalPyramidSelector(pyramid_id=pyramid_id)
        )
        if current.version is None:
            raise ValueError("Functional Pyramid version is unavailable")
        return m.FunctionalPyramidVersion(current.version.value + 1)

    @staticmethod
    def _merge_surfaces(
        surfaces: tuple[m.ChangedSurface, ...],
    ) -> tuple[m.ChangedSurface, ...]:
        by_surface: dict[m.SurfaceKey, list[m.ChangedConclusion]] = {}
        reasons: dict[m.SurfaceKey, set[m.ChangeReason]] = {}
        for surface in surfaces:
            by_surface.setdefault(surface.surface, []).extend(surface.conclusions)
            reasons.setdefault(surface.surface, set()).update(surface.reasons)
        return tuple(
            m.ChangedSurface(
                surface=surface,
                reasons=tuple(sorted(reasons[surface], key=lambda item: item.value)),
                conclusions=tuple(
                    sorted(
                        {item.ref: item for item in by_surface[surface]}.values(),
                        key=lambda item: item.ref.sort_key,
                    )
                ),
            )
            for surface in sorted(
                by_surface,
                key=lambda item: (item.repository_id, item.kind.value, item.locator),
            )
        )
