"""Shared dependency-effect computation for reconsider and Functional Pyramid writes.

FD-17–FD-22 and FD-79/FD-89 have one service-owned effect engine. Repository
changed-scope and Functional Pyramid participation/route changes provide roots;
projection, premise closure, support qualification and re-establishment context
issuance are shared.
"""

from __future__ import annotations

import datetime as _datetime
import typing as _typing

from span.core import containment
from span.core import model as m
from span.core import support_rules as _support_rules
from span.core.recording import RecordingValidationError
from span.ports.functional_pyramid import FunctionalPyramidRepositoryRuntime
from span.ports.lifecycle import LifecycleStorePort
from span.service.contexts import ContextBinding, context_binding, issue_context
from span.service.ids import server_context_id
from span.service.support import SupportService

_FunctionalRouteImpactLookup = _typing.Callable[
    [str, tuple[str, ...], tuple[m.SurfaceKey, ...]],
    tuple[m.FunctionalRouteIdentity, ...],
]

_ReestablishmentContextIssuer = _typing.Callable[
    [str, str, ContextBinding, tuple[str, ...], tuple[str, ...]],
    m.InvestigationContextRef,
]
_RepositoryRuntimeLookup = _typing.Callable[[str], FunctionalPyramidRepositoryRuntime]
_RegisteredRepositoryIds = _typing.Callable[[], tuple[str, ...]]
_SupportLookup = _typing.Callable[[str], SupportService]


class DependencyEffectService:
    """Compute canonical semantic effects from either supported change root."""

    def __init__(
        self,
        *,
        repository_runtime: _RepositoryRuntimeLookup,
        registered_repository_ids: _RegisteredRepositoryIds,
        support_for_repository: _SupportLookup,
        functional_route_impacts: _FunctionalRouteImpactLookup,
        clock: _typing.Callable[[], _datetime.datetime] | None = None,
        new_context_id: _typing.Callable[[], str] | None = None,
        context_issuer: _ReestablishmentContextIssuer | None = None,
    ) -> None:
        self._repository_runtime = repository_runtime
        self._registered_repository_ids = registered_repository_ids
        self._support_for_repository = support_for_repository
        self._functional_route_impacts = functional_route_impacts
        self._clock = clock or (lambda: _datetime.datetime.now(_datetime.timezone.utc))
        self._new_context_id = new_context_id or server_context_id
        self._context_issuer = context_issuer or self._issue_reestablishment_context

    def _registered_ids(self) -> tuple[str, ...]:
        return self._registered_repository_ids()

    def _store_for_repository(self, repository_id: str) -> LifecycleStorePort:
        return self._repository_runtime(repository_id).store

    def _repository_for_ref(self, ref: m.ConclusionRevisionRef) -> str:
        owners = [
            repository_id
            for repository_id in self._registered_ids()
            if self._store_for_repository(repository_id).has_conclusion_revision(
                ref.understanding_id.value,
                ref.conclusion_id.value,
                ref.revision.value,
            )
        ]
        if len(owners) != 1:
            raise RecordingValidationError(
                "affected conclusion revision must resolve to exactly one "
                f"registered repository: {ref.label}"
            )
        return owners[0]

    def _store_for_ref(self, ref: m.ConclusionRevisionRef) -> LifecycleStorePort:
        return self._store_for_repository(self._repository_for_ref(ref))

    def _support_dependents(
        self, dependency_kind: str, dependency_ref: str
    ) -> tuple[m.ConclusionRevisionRef, ...]:
        refs: list[m.ConclusionRevisionRef] = []
        for repository_id in self._registered_ids():
            refs.extend(
                self._store_for_repository(repository_id).support_dependents(
                    dependency_kind, dependency_ref
                )
            )
        return tuple(dict.fromkeys(refs))

    def repository_change(
        self,
        request: m.ReconsiderRequest,
        *,
        issue_contexts: bool = True,
    ) -> m.Changed:
        """Project one repository changed-scope root through the shared engine.

        ``issue_contexts=False`` is the read-only notice path: it returns the
        identical affected projection without persisting re-establishment
        contexts.
        """
        if request.challenge is not None:
            raise ValueError("challenge is not a dependency-effect root")
        repository_id = request.bound_repository_id
        store = self._store_for_repository(repository_id)
        store.require_repository(repository_id)

        reasons: dict[m.SurfaceKey, set[m.ChangeReason]] = {}
        root_scopes = {repository_id: self._repository_root_scopes(request)}
        surfaces = store.list_surfaces(repository_id)
        changed_paths = self._changed_paths(request)

        for path in request.changed_paths:
            member = containment.path_surface(repository_id, path)
            for surface in containment.containing_surfaces(surfaces, member):
                reasons.setdefault(surface, set()).add(m.ChangeReason.CONTAINMENT)
        for surface in request.changed_surfaces:
            reasons.setdefault(surface, set()).add(m.ChangeReason.CONTAINMENT)

        direct: list[m.ConclusionRevisionRef] = []
        for path in changed_paths:
            direct.extend(self._source_and_discovery_dependents(repository_id, path))
            direct.extend(self._authority_dependents(repository_id, path))

        route_ids = self._functional_route_impacts(
            repository_id,
            request.changed_paths,
            request.changed_surfaces,
        )
        direct.extend(self._route_dependents(route_ids))

        projected = self._project(
            reasons=reasons,
            direct=direct,
            forced_reassessment={},
            root_scopes=root_scopes,
            issue_contexts=issue_contexts,
        )
        surfaces_out, contexts, _ = projected
        return m.Changed(
            reestablishment_contexts=contexts,
            surfaces=surfaces_out,
        )

    def retained_functional_pyramid_effects(
        self,
        refs: tuple[m.ConclusionRevisionRef, ...],
    ) -> tuple[
        tuple[m.ChangedSurface, ...],
        tuple[m.InvestigationContextRef, ...],
    ]:
        """Live-project only immutable accepted effect refs; discover nothing new."""
        affected: dict[m.SurfaceKey, list[m.ChangedConclusion]] = {}
        for ref in sorted(set(refs), key=lambda value: value.sort_key):
            try:
                surface = self._surface_of(ref)
                store = self._store_for_ref(ref)
                version = store.get_understanding(
                    ref.understanding_id.value
                ).current_version
            except (OSError, ValueError):
                continue
            current = store.get_version(ref.understanding_id.value, version.value)
            if ref not in current.conclusions:
                continue
            revision = self._conclusion_revision(ref)
            missing_required_route = (
                isinstance(revision.content, m.SupportedConclusion)
                and revision.content.assertion_nature is m.AssertionNature.NORMATIVE
                and not any(
                    isinstance(dependency, m.FunctionalRouteSupport)
                    for dependency in revision.content.support
                )
            )
            support = (
                self._forced_reassessment(
                    "ACTIVE normative revision predates required governing support"
                )
                if missing_required_route
                else self._support_state(ref)
            )
            if (
                isinstance(support, m.SupportQualification)
                and support.state is m.SupportState.CURRENT
            ):
                continue
            affected.setdefault(surface, []).append(
                m.ChangedConclusion(
                    ref=ref,
                    expected_version=current.version,
                    reasons=(m.ChangeReason.DIRECT,),
                    support=support,
                )
            )

        surfaces = tuple(
            m.ChangedSurface(
                surface=surface,
                reasons=(m.ChangeReason.DIRECT,),
                conclusions=tuple(affected[surface]),
            )
            for surface in containment.order_surfaces(
                {surface: {m.ChangeReason.DIRECT} for surface in affected}
            )
        )
        return surfaces, self._reestablishment_contexts(surfaces, {})

    def functional_pyramid_change(
        self,
        *,
        changed_route_identities: tuple[m.FunctionalRouteIdentity, ...] = (),
        changed_authority_refs: tuple[m.EvidenceRef, ...] = (),
        forced_reassessment_refs: tuple[m.ConclusionRevisionRef, ...] = (),
        newly_active_repositories: tuple[str, ...] = (),
        deliberately_inactive_repositories: tuple[str, ...] = (),
    ) -> tuple[
        tuple[m.ChangedSurface, ...],
        tuple[m.InvestigationContextRef, ...],
        tuple[m.ConclusionRevisionRef, ...],
    ]:
        """Project an accepted/proposed Functional Pyramid delta.

        T08 supplies only route identities whose applicability actually differs
        between old/new state plus durable participation changes. This engine
        derives their semantic dependents and never accepts caller-supplied
        dependent repository IDs.
        """
        route_dependents = self._route_dependents(changed_route_identities)
        direct = list(route_dependents)
        for authority in changed_authority_refs:
            direct.extend(
                self._authority_identity_dependents(
                    authority.repository_id, authority.evidence_id
                )
            )
        forced: dict[m.ConclusionRevisionRef, str] = {
            ref: "recorded governing route changed under the accepted Functional Pyramid delta"
            for ref in route_dependents
        }
        for ref in sorted(
            set(forced_reassessment_refs), key=lambda item: item.sort_key
        ):
            direct.append(ref)
            forced[ref] = (
                "Functional Pyramid route identity model changed during the "
                "Version-2 cutover and requires re-establishment"
            )

        for repository_id in sorted(set(newly_active_repositories)):
            self._store_for_repository(repository_id).require_repository(repository_id)
            for ref in self._current_normative_refs(
                repository_id, with_route_support=False
            ):
                direct.append(ref)
                forced[ref] = (
                    "repository became ACTIVE and this normative revision "
                    "predates required governing support"
                )

        for repository_id in sorted(set(deliberately_inactive_repositories)):
            self._store_for_repository(repository_id).require_repository(repository_id)
            for ref in self._current_normative_refs(
                repository_id, with_route_support=True
            ):
                direct.append(ref)
                forced[ref] = (
                    "recorded governing route deliberately ceased to be ACTIVE"
                )

        return self._project(
            reasons={},
            direct=direct,
            forced_reassessment=forced,
            root_scopes={},
        )

    def _project(
        self,
        *,
        reasons: dict[m.SurfaceKey, set[m.ChangeReason]],
        direct: _typing.Iterable[m.ConclusionRevisionRef],
        forced_reassessment: dict[m.ConclusionRevisionRef, str],
        root_scopes: dict[str, tuple[m.EvidenceScope, ...]],
        issue_contexts: bool = True,
    ) -> tuple[
        tuple[m.ChangedSurface, ...],
        tuple[m.InvestigationContextRef, ...],
        tuple[m.ConclusionRevisionRef, ...],
    ]:
        roots = set(direct)
        indirect, forced_descendants = self._premise_closure(
            roots, set(forced_reassessment)
        )
        for ref in forced_descendants:
            forced_reassessment.setdefault(
                ref,
                "premise depends on a conclusion whose governing support changed",
            )
        per_ref = _support_rules.dependency_change_reasons(roots, indirect)
        affected: dict[m.SurfaceKey, set[m.ConclusionRevisionRef]] = {}
        for ref, causes in per_ref.items():
            surface = self._surface_of(ref)
            reasons.setdefault(surface, set()).update(causes)
            affected.setdefault(surface, set()).add(ref)

        ordered = containment.order_surfaces(reasons)
        current_versions: dict[str, m.UnderstandingVersion] = {}
        changed_surfaces: list[m.ChangedSurface] = []
        effect_refs: list[m.ConclusionRevisionRef] = []
        for surface in ordered:
            conclusions: list[m.ChangedConclusion] = []
            for ref in sorted(
                affected.get(surface, ()),
                key=lambda value: value.sort_key,
            ):
                conclusion = self._changed_conclusion(
                    ref,
                    per_ref[ref],
                    current_versions,
                    forced_reassessment.get(ref),
                )
                if conclusion is None:
                    continue
                conclusions.append(conclusion)
                effect_refs.append(ref)
            changed_surfaces.append(
                m.ChangedSurface(
                    surface=surface,
                    reasons=tuple(
                        sorted(reasons[surface], key=lambda item: item.value)
                    ),
                    conclusions=tuple(conclusions),
                )
            )

        projection = tuple(changed_surfaces)
        contexts = (
            self._reestablishment_contexts(projection, root_scopes)
            if issue_contexts
            else ()
        )
        return (
            projection,
            contexts,
            tuple(dict.fromkeys(effect_refs)),
        )

    def _changed_conclusion(
        self,
        ref: m.ConclusionRevisionRef,
        reasons: set[m.ChangeReason],
        current_versions: dict[str, m.UnderstandingVersion],
        forced_reason: str | None,
    ) -> m.ChangedConclusion | None:
        version = self._current_version(ref, current_versions)
        if ref not in version.conclusions:
            return None
        support = (
            self._forced_reassessment(forced_reason)
            if forced_reason is not None
            else self._support_state(ref)
        )
        return m.ChangedConclusion(
            ref=ref,
            expected_version=version.version,
            reasons=tuple(sorted(reasons, key=lambda item: item.value)),
            support=support,
        )

    def _forced_reassessment(self, reason: str) -> m.SupportQualification:
        return m.compact_support(
            _support_rules.evaluation(
                m.SupportState.REASSESSMENT_REQUIRED,
                self._clock(),
                reason,
            ),
            (),
        )

    def _current_version(
        self,
        ref: m.ConclusionRevisionRef,
        current_versions: dict[str, m.UnderstandingVersion],
    ) -> m.UnderstandingVersion:
        understanding_id = ref.understanding_id.value
        if understanding_id not in current_versions:
            store = self._store_for_ref(ref)
            understanding = store.get_understanding(understanding_id)
            current_versions[understanding_id] = store.get_version(
                understanding_id, understanding.current_version.value
            )
        return current_versions[understanding_id]

    def _current_normative_refs(
        self,
        repository_id: str,
        *,
        with_route_support: bool,
    ) -> tuple[m.ConclusionRevisionRef, ...]:
        refs: list[m.ConclusionRevisionRef] = []
        store = self._store_for_repository(repository_id)
        for understanding in store.list_understandings(repository_id):
            version = store.get_version(
                understanding.understanding_id.value,
                understanding.current_version.value,
            )
            for ref in version.conclusions:
                revision = self._conclusion_revision(ref)
                if not isinstance(revision.content, m.SupportedConclusion):
                    continue
                if revision.content.assertion_nature is not m.AssertionNature.NORMATIVE:
                    continue
                has_route = any(
                    isinstance(dependency, m.FunctionalRouteSupport)
                    for dependency in revision.content.support
                )
                if has_route is with_route_support:
                    refs.append(ref)
        return tuple(sorted(set(refs), key=lambda value: value.sort_key))

    def _source_and_discovery_dependents(
        self,
        repository_id: str,
        path: str,
    ) -> tuple[m.ConclusionRevisionRef, ...]:
        store = self._store_for_repository(repository_id)
        refs = [
            ref
            for observation in store.source_observation_ids_for_locator(
                repository_id, path
            )
            for ref in store.support_dependents("SOURCE", observation)
        ]
        for discovery in store.list_discovery_observations(repository_id):
            if m.evidence_scope_contains(
                discovery.scope,
                m.EvidenceScope(paths=(path,)),
            ):
                refs.extend(
                    store.support_dependents(
                        "DISCOVERY", discovery.observation_id.value
                    )
                )
        return tuple(dict.fromkeys(refs))

    def _authority_dependents(
        self,
        repository_id: str,
        path: str,
    ) -> tuple[m.ConclusionRevisionRef, ...]:
        changed = m.EvidenceScope(paths=(path,))
        refs: list[m.ConclusionRevisionRef] = []
        store = self._store_for_repository(repository_id)
        for binding in store.load_authority_bindings(repository_id):
            if not m.evidence_scope_allows(binding.evidence_ref.locator, changed):
                continue
            refs.extend(
                self._authority_identity_dependents(
                    repository_id, binding.evidence_ref.evidence_id
                )
            )
        return tuple(dict.fromkeys(refs))

    def _authority_identity_dependents(
        self, repository_id: str, evidence_id: m.EvidenceId
    ) -> tuple[m.ConclusionRevisionRef, ...]:
        refs: list[m.ConclusionRevisionRef] = []
        for ref in self._support_dependents("AUTHORITY", evidence_id.value):
            revision = self._conclusion_revision(ref)
            if not isinstance(revision.content, m.SupportedConclusion):
                continue
            if any(
                isinstance(dependency, m.AuthoritySupportDependency)
                and dependency.authority.evidence_ref.repository_id == repository_id
                and dependency.authority.evidence_ref.evidence_id == evidence_id
                for dependency in revision.content.support
            ):
                refs.append(ref)
        return tuple(dict.fromkeys(refs))

    def _route_dependents(
        self,
        route_ids: _typing.Iterable[m.FunctionalRouteIdentity],
    ) -> tuple[m.ConclusionRevisionRef, ...]:
        refs: list[m.ConclusionRevisionRef] = []
        for route_id in route_ids:
            refs.extend(self._support_dependents("FUNCTIONAL_ROUTE", route_id.value))
        return tuple(dict.fromkeys(refs))

    def _changed_paths(self, request: m.ReconsiderRequest) -> tuple[str, ...]:
        paths = list(request.changed_paths)
        for surface in request.changed_surfaces:
            if surface.kind is m.SurfaceKind.FILE:
                paths.append(surface.locator)
            elif surface.kind is m.SurfaceKind.SYMBOL:
                owner = containment.surface_file_locator(surface.locator)
                if owner is not None:
                    paths.append(owner)
        return tuple(dict.fromkeys(paths))

    def _repository_root_scopes(
        self,
        request: m.ReconsiderRequest,
    ) -> tuple[m.EvidenceScope, ...]:
        scopes: list[m.EvidenceScope] = []
        if request.changed_paths:
            scopes.append(m.EvidenceScope(paths=tuple(request.changed_paths)))
        for surface in request.changed_surfaces:
            if surface.kind is m.SurfaceKind.FILE:
                scopes.append(m.EvidenceScope(paths=(surface.locator,)))
                continue
            if surface.kind is m.SurfaceKind.SYMBOL:
                owner = containment.surface_file_locator(surface.locator)
                if owner is not None:
                    scopes.append(m.EvidenceScope(paths=(owner,)))
                continue
            declared = self._store_for_repository(
                request.bound_repository_id
            ).find_surface(surface)
            if declared is None:
                continue
            paths = list(declared.boundary.paths)
            paths.extend(
                owner
                for symbol in declared.boundary.symbols
                if (owner := containment.surface_file_locator(symbol)) is not None
            )
            if paths:
                scopes.append(m.EvidenceScope(paths=tuple(paths)))
        return tuple(scopes)

    def _reestablishment_contexts(
        self,
        surfaces: tuple[m.ChangedSurface, ...],
        root_scopes: dict[str, tuple[m.EvidenceScope, ...]],
    ) -> tuple[m.InvestigationContextRef, ...]:
        actionable: dict[str, list[m.ChangedConclusion]] = {}
        for surface in surfaces:
            repository_id = surface.surface.repository_id
            for conclusion in surface.conclusions:
                if self._is_actionable(conclusion):
                    actionable.setdefault(repository_id, []).append(conclusion)

        pending: list[
            tuple[str, ContextBinding, tuple[str, ...], tuple[str, ...]]
        ] = []
        for repository_id in sorted(actionable):
            store = self._store_for_repository(repository_id)
            scopes = list(root_scopes.get(repository_id, ()))
            source_observations: dict[str, m.SourceObservation] = {}
            discovery_observations: dict[str, m.DiscoveryObservation] = {}

            for conclusion in actionable[repository_id]:
                revision = self._conclusion_revision(conclusion.ref)
                if not isinstance(revision.content, m.SupportedConclusion):
                    continue
                scopes.append(revision.content.scope)
                for dependency in revision.content.support:
                    if isinstance(dependency, m.SourceSupport):
                        source_observation = store.find_source_observation(
                            dependency.observation_id.value
                        )
                        if source_observation is None:
                            continue
                        if source_observation.repository_id != repository_id:
                            raise RecordingValidationError(
                                "re-establishment source observation belongs to "
                                "another repository"
                            )
                        scopes.append(
                            m.EvidenceScope(
                                evidence_refs=(source_observation.evidence,)
                            )
                        )
                        source_observations[dependency.observation_id.value] = (
                            source_observation
                        )
                    elif isinstance(dependency, m.DiscoverySupport):
                        discovery_observation = store.find_discovery_observation(
                            dependency.observation_id.value
                        )
                        if discovery_observation is None:
                            continue
                        if discovery_observation.repository_id != repository_id:
                            raise RecordingValidationError(
                                "re-establishment discovery observation belongs to "
                                "another repository"
                            )
                        scopes.append(discovery_observation.scope)
                        discovery_observations[dependency.observation_id.value] = (
                            discovery_observation
                        )
                    elif isinstance(dependency, m.AuthoritySupportDependency):
                        if (
                            dependency.authority.evidence_ref.repository_id
                            == repository_id
                        ):
                            scopes.append(
                                m.EvidenceScope(
                                    evidence_refs=(dependency.authority.evidence_ref,)
                                )
                            )
                    elif isinstance(dependency, m.FunctionalRouteSupport):
                        if dependency.repository_id == repository_id:
                            scopes.append(dependency.semantic_scope)

            if not scopes:
                scopes.append(m.EvidenceScope())

            pending.append(
                (
                    repository_id,
                    context_binding(
                        scope=m.evidence_scope_union(scopes),
                        origin=m.ContextOrigin.CHANGED_SUPPORT,
                    ),
                    tuple(sorted(source_observations)),
                    tuple(sorted(discovery_observations)),
                )
            )

        # All owner scopes and retained observation identities must be known
        # before issuing any context. An interrupted discovery writes nothing.
        return tuple(
            self._context_issuer(
                repository_id,
                self._new_context_id(),
                binding,
                source_ids,
                discovery_ids,
            )
            for repository_id, binding, source_ids, discovery_ids in pending
        )

    def _issue_reestablishment_context(
        self,
        repository_id: str,
        context_id: str,
        binding: ContextBinding,
        source_observation_ids: tuple[str, ...],
        discovery_observation_ids: tuple[str, ...],
    ) -> m.InvestigationContextRef:
        def fixed_context_id() -> str:
            return context_id

        store = self._store_for_repository(repository_id)
        context = issue_context(
            store,
            binding=binding,
            repository_id=repository_id,
            request_id=m.RequestId(f"effects:{context_id}"),
            clock=self._clock,
            new_context_id=fixed_context_id,
        )
        for observation_id in source_observation_ids:
            store.add_context_evidence(context_id, observation_id)
        for observation_id in discovery_observation_ids:
            store.add_context_discovery_evidence(context_id, observation_id)
        return m.InvestigationContextRef(
            repository_id=repository_id,
            context_id=context.context_id,
        )

    @staticmethod
    def _is_actionable(conclusion: m.ChangedConclusion) -> bool:
        return not (
            isinstance(conclusion.support, m.SupportQualification)
            and conclusion.support.state is m.SupportState.CURRENT
        )

    def _conclusion_revision(
        self,
        ref: m.ConclusionRevisionRef,
    ) -> m.ConclusionRevision:
        store = self._store_for_ref(ref)
        for revision in store.get_conclusions(ref.understanding_id.value):
            if (
                revision.conclusion_id == ref.conclusion_id
                and revision.revision == ref.revision
            ):
                return revision
        raise RecordingValidationError(
            "affected conclusion revision is missing: "
            f"{ref.conclusion_id.value}@{ref.revision.value}"
        )

    def _support_state(
        self,
        ref: m.ConclusionRevisionRef,
    ) -> m.SupportQualification | m.SupportUnavailable:
        repository_id = self._repository_for_ref(ref)
        support = self._support_for_repository(repository_id)
        store = self._store_for_repository(repository_id)
        try:
            return support.qualify_support(support.evaluate_revision(ref))
        except (OSError,) + store.operational_errors:
            return m.SupportUnavailable("conclusion support evaluation is unavailable")

    def _surface_of(self, ref: m.ConclusionRevisionRef) -> m.SurfaceKey:
        store = self._store_for_ref(ref)
        return store.get_understanding(ref.understanding_id.value).surface

    def _premise_closure(
        self,
        direct: set[m.ConclusionRevisionRef],
        forced: set[m.ConclusionRevisionRef],
    ) -> tuple[set[m.ConclusionRevisionRef], set[m.ConclusionRevisionRef]]:
        """Read each reached reverse-index entry once, forced roots first."""
        visited = direct | forced
        pending = [(ref, False) for ref in direct - forced]
        pending.extend((ref, True) for ref in forced)
        indirect: set[m.ConclusionRevisionRef] = set()
        processed: set[m.ConclusionRevisionRef] = set()
        while pending:
            ref, propagated = pending.pop()
            if ref in processed:
                continue
            processed.add(ref)
            dependents = self._support_dependents("PREMISE", ref.label)
            indirect.update(dependents)
            unseen = _support_rules.unvisited_premises(dependents, visited)
            if propagated:
                # A queued direct root can itself be a forced descendant.
                promoted = set(dependents) - forced
                forced.update(dependents)
                pending.extend((item, True) for item in promoted & direct)
            visited.update(unseen)
            pending.extend((item, propagated) for item in unseen)
        return indirect, forced
