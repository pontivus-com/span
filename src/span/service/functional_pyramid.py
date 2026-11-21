"""Functional Pyramid declaration and resolution orchestration."""

from __future__ import annotations

import typing as _typing

from span.core import functional_pyramid as _fp
from span.core import model as m
from span.ports.functional_pyramid import (
    FunctionalPyramidDeclarationInvalid,
    FunctionalPyramidDeclarationPort,
    FunctionalPyramidRepositoryUnavailable,
    FunctionalPyramidStatePort,
)
from span.ports.lifecycle import LifecycleAuthorityResolver

_DeclarationEntry = tuple[str, m.FunctionalPyramidDeclaration]
_AuthorityMap = dict[tuple[str, str], m.AuthorityBinding]


def _validation_finding(
    reason: m.FunctionalPyramidValidationReason,
    repository_id: str | None,
    detail: str,
    recovery: str,
    *,
    pyramid_id: m.FunctionalPyramidId | None = None,
    declaration_locator: str | None = None,
    expected_version: m.FunctionalPyramidVersion | None = None,
    current_version: m.FunctionalPyramidVersion | None = None,
) -> m.FunctionalPyramidValidationFinding:
    return m.FunctionalPyramidValidationFinding(
        reason=reason,
        repository_id=repository_id,
        pyramid_id=pyramid_id,
        declaration_locator=declaration_locator,
        expected_version=expected_version,
        current_version=current_version,
        detail=detail,
        recovery=recovery,
    )


def _graph_finding(
    reason: m.FunctionalPyramidFindingReason,
    repository_id: str,
    detail: str,
    recovery: str,
    *,
    declaration_locator: str | None = None,
    rule_id: str | None = None,
) -> m.FunctionalPyramidFinding:
    return m.FunctionalPyramidFinding(
        reason=reason,
        repository_id=repository_id,
        declaration_locator=declaration_locator,
        rule_id=rule_id,
        detail=detail,
        recovery=recovery,
    )


class FunctionalPyramidService:
    """Compose exact source loading, authority binding and pure graph rules."""

    def __init__(
        self,
        *,
        declarations: FunctionalPyramidDeclarationPort,
        authority: LifecycleAuthorityResolver,
        state: FunctionalPyramidStatePort | None = None,
        registered_repository_ids: _typing.Callable[[], tuple[str, ...]] | None = None,
    ) -> None:
        self._declarations = declarations
        self._authority = authority
        self._state = state
        self._registered_repository_ids = registered_repository_ids

    def _require_state(self) -> FunctionalPyramidStatePort:
        if self._state is None:
            raise ValueError("Functional Pyramid state service is not configured")
        return self._state

    def _registered(self) -> frozenset[str]:
        if self._registered_repository_ids is None:
            raise ValueError("Functional Pyramid repository registry is not configured")
        return frozenset(self._registered_repository_ids())

    def status(
        self, selector: m.FunctionalPyramidSelector
    ) -> m.FunctionalPyramidStatus:
        """Project exact durable participation plus live ACTIVE health (FD-83)."""
        state = self._require_state()
        pyramid_id = selector.pyramid_id
        if selector.repository_id is not None:
            pyramid_id = state.active_pyramid_id(selector.repository_id)
            if pyramid_id is None:
                participation = (
                    m.FunctionalPyramidParticipationState.EXCLUDED
                    if state.is_excluded(selector.repository_id)
                    else m.FunctionalPyramidParticipationState.UNCONFIGURED
                )
                return m.FunctionalPyramidStatus(state=participation)

        assert pyramid_id is not None
        version = state.pyramid_version(pyramid_id)
        if version is None:
            return m.FunctionalPyramidStatus(
                state=m.FunctionalPyramidParticipationState.UNCONFIGURED
            )
        members = state.pyramid_members(pyramid_id, version)
        health, findings = self.health(members)
        return m.FunctionalPyramidStatus(
            state=m.FunctionalPyramidParticipationState.ACTIVE,
            health=health,
            pyramid_id=pyramid_id,
            version=version,
            members=members,
            findings=findings,
        )

    def candidate(
        self, selector: m.FunctionalPyramidCandidateSelector
    ) -> m.FunctionalPyramidCandidate:
        """Pure action-aware candidate validation (FD-84)."""
        state = self._require_state()
        registered = self._registered()
        validation: list[m.FunctionalPyramidValidationFinding] = []

        intents_by_repository: dict[str, m.FunctionalPyramidMemberIntent] = {}
        duplicate_repositories: set[str] = set()
        for intent in selector.members:
            if intent.repository_id in intents_by_repository:
                duplicate_repositories.add(intent.repository_id)
                continue
            intents_by_repository[intent.repository_id] = intent

        for repository_id in sorted(duplicate_repositories):
            validation.append(
                _validation_finding(
                    m.FunctionalPyramidValidationReason.DUPLICATE_MEMBER,
                    repository_id,
                    "candidate contains the same repository more than once",
                    "retain exactly one member intent for the repository",
                )
            )

        target_id = selector.pyramid_id
        target_version: m.FunctionalPyramidVersion | None = None
        if selector.action is m.FunctionalPyramidAction.REVISE:
            assert target_id is not None
            assert selector.expected_version is not None
            current = state.pyramid_version(target_id)
            if current is None:
                validation.append(
                    _validation_finding(
                        m.FunctionalPyramidValidationReason.UNKNOWN_PYRAMID,
                        None,
                        "target Functional Pyramid is not ACTIVE",
                        "obtain current Functional Pyramid status before revising",
                        pyramid_id=target_id,
                    )
                )
            else:
                target_version = current
                if current != selector.expected_version:
                    validation.append(
                        _validation_finding(
                            m.FunctionalPyramidValidationReason.STALE_PYRAMID_VERSION,
                            None,
                            "target Functional Pyramid version is stale",
                            "obtain current status and rebuild the revision candidate",
                            pyramid_id=target_id,
                            expected_version=selector.expected_version,
                            current_version=current,
                        )
                    )

        eligible: list[m.FunctionalPyramidMemberIntent] = []
        for repository_id in sorted(intents_by_repository):
            intent = intents_by_repository[repository_id]
            if repository_id not in registered:
                validation.append(
                    _validation_finding(
                        m.FunctionalPyramidValidationReason.UNREGISTERED_MEMBER,
                        repository_id,
                        "candidate repository is not registered with Span",
                        "register the repository before Functional Pyramid validation",
                    )
                )
                continue
            active_id = state.active_pyramid_id(repository_id)
            retained_target = target_id is not None and active_id == target_id
            if active_id is not None and not retained_target:
                validation.append(
                    _validation_finding(
                        m.FunctionalPyramidValidationReason.MEMBER_ALREADY_ACTIVE,
                        repository_id,
                        "repository already belongs to another ACTIVE Functional Pyramid",
                        "revise/deactivate the current instance before reassigning it",
                        pyramid_id=active_id,
                    )
                )
                continue
            eligible.append(intent)

        members, declarations, available, source_validation, source_graph = (
            self.load_candidate_members(tuple(eligible))
        )
        validation.extend(source_validation)
        authorities, authority_findings = self._authority_bindings(
            members, declarations, available
        )
        del authorities
        health, structural = _fp.evaluate_functional_pyramid_health(
            members,
            declarations,
            available,
            source_graph + authority_findings,
        )
        del health

        graph: list[m.FunctionalPyramidFinding] = []
        for finding in structural:
            if finding.reason is m.FunctionalPyramidFindingReason.UNCOVERED_PATH:
                validation.append(
                    _validation_finding(
                        m.FunctionalPyramidValidationReason.INCOMPLETE_COMPLETE_COVERAGE,
                        finding.repository_id,
                        finding.detail,
                        finding.recovery,
                    )
                )
                continue
            graph.append(finding)

        ordered_validation = tuple(
            sorted(
                validation,
                key=lambda item: (
                    item.reason.value,
                    item.repository_id or "",
                    item.declaration_locator or "",
                    "" if item.pyramid_id is None else item.pyramid_id.value,
                ),
            )
        )
        return m.FunctionalPyramidCandidate(
            action=selector.action,
            pyramid_id=target_id,
            version=target_version,
            members=members,
            activation_ready=not ordered_validation and not graph,
            validation_findings=ordered_validation,
            graph_findings=tuple(graph),
        )

    def discover_bootstrap(
        self, repository_id: str
    ) -> tuple[m.EvidenceRef, m.FunctionalPyramidBootstrap] | None:
        """Read only the conventional optional bootstrap."""
        return self._declarations.read_bootstrap(repository_id)

    def _load_requests(
        self,
        repository_id: str,
        requests: tuple[m.EvidenceRequest, ...],
    ) -> tuple[
        tuple[m.EvidenceRef, ...],
        tuple[_DeclarationEntry, ...],
        bool,
        tuple[m.FunctionalPyramidValidationFinding, ...],
        tuple[m.FunctionalPyramidFinding, ...],
    ]:
        refs: list[m.EvidenceRef] = []
        declarations: list[_DeclarationEntry] = []
        validation: list[m.FunctionalPyramidValidationFinding] = []
        graph: list[m.FunctionalPyramidFinding] = []
        available = True

        for request in requests:
            if request.ranges:
                validation.append(
                    _validation_finding(
                        m.FunctionalPyramidValidationReason.INVALID_DECLARATION_SOURCE,
                        repository_id,
                        "Functional Pyramid declaration source is ranged",
                        "select the complete declaration document",
                        declaration_locator=request.locator,
                    )
                )
                graph.append(
                    _graph_finding(
                        m.FunctionalPyramidFindingReason.INVALID_DECLARATION,
                        repository_id,
                        "Functional Pyramid declaration source is ranged",
                        "select the complete declaration document",
                        declaration_locator=request.locator,
                    )
                )
                continue

            try:
                result = self._declarations.read_declaration(repository_id, request)
            except FunctionalPyramidRepositoryUnavailable:
                available = False
                graph.append(
                    _graph_finding(
                        m.FunctionalPyramidFindingReason.REPOSITORY_UNAVAILABLE,
                        repository_id,
                        "Functional Pyramid member repository is unavailable",
                        "restore the registered member repository",
                        declaration_locator=request.locator,
                    )
                )
                break
            except FunctionalPyramidDeclarationInvalid:
                validation.append(
                    _validation_finding(
                        m.FunctionalPyramidValidationReason.INVALID_DECLARATION_SOURCE,
                        repository_id,
                        "Functional Pyramid declaration violates the Version-1 contract",
                        "correct the named declaration document",
                        declaration_locator=request.locator,
                    )
                )
                graph.append(
                    _graph_finding(
                        m.FunctionalPyramidFindingReason.INVALID_DECLARATION,
                        repository_id,
                        "Functional Pyramid declaration violates the Version-1 contract",
                        "correct the named declaration document",
                        declaration_locator=request.locator,
                    )
                )
                continue

            if isinstance(result, m.EvidenceSourceFailure):
                reason = (
                    m.FunctionalPyramidValidationReason.MISSING_DECLARATION_SOURCE
                    if result.kind is m.EvidenceSourceFailureKind.MISSING
                    else m.FunctionalPyramidValidationReason.INVALID_DECLARATION_SOURCE
                )
                validation.append(
                    _validation_finding(
                        reason,
                        repository_id,
                        "Functional Pyramid declaration source cannot be loaded",
                        "restore or correct the named declaration document",
                        declaration_locator=request.locator,
                    )
                )
                graph.append(
                    _graph_finding(
                        m.FunctionalPyramidFindingReason.INVALID_DECLARATION,
                        repository_id,
                        "Functional Pyramid declaration source cannot be loaded",
                        "restore or correct the named declaration document",
                        declaration_locator=request.locator,
                    )
                )
                continue

            evidence_ref, declaration = result
            refs.append(evidence_ref)
            declarations.append((repository_id, declaration))

        return (
            tuple(refs),
            tuple(declarations),
            available,
            tuple(validation),
            tuple(graph),
        )

    def load_candidate_members(
        self, intents: tuple[m.FunctionalPyramidMemberIntent, ...]
    ) -> tuple[
        tuple[m.FunctionalPyramidMemberView, ...],
        tuple[_DeclarationEntry, ...],
        frozenset[str],
        tuple[m.FunctionalPyramidValidationFinding, ...],
        tuple[m.FunctionalPyramidFinding, ...],
    ]:
        """Resolve candidate source requests without changing participation."""
        members: list[m.FunctionalPyramidMemberView] = []
        declarations: list[_DeclarationEntry] = []
        available: set[str] = set()
        validation: list[m.FunctionalPyramidValidationFinding] = []
        graph: list[m.FunctionalPyramidFinding] = []

        for intent in intents:
            refs, loaded, is_available, source_validation, source_graph = (
                self._load_requests(intent.repository_id, intent.declaration_sources)
            )
            if is_available:
                available.add(intent.repository_id)
            validation.extend(source_validation)
            graph.extend(source_graph)
            declarations.extend(loaded)
            if refs:
                members.append(
                    m.FunctionalPyramidMemberView(
                        repository_id=intent.repository_id,
                        declaration_refs=refs,
                        functional_scope=intent.functional_scope,
                        coverage=intent.coverage,
                    )
                )

        return (
            tuple(members),
            tuple(declarations),
            frozenset(available),
            tuple(validation),
            tuple(graph),
        )

    def _load_active_members(
        self, members: tuple[m.FunctionalPyramidMemberView, ...]
    ) -> tuple[
        tuple[m.FunctionalPyramidMemberView, ...],
        tuple[_DeclarationEntry, ...],
        frozenset[str],
        tuple[m.FunctionalPyramidFinding, ...],
    ]:
        current_members: list[m.FunctionalPyramidMemberView] = []
        declarations: list[_DeclarationEntry] = []
        available: set[str] = set()
        graph: list[m.FunctionalPyramidFinding] = []

        for member in members:
            requests = tuple(
                m.EvidenceRequest(ref.locator) for ref in member.declaration_refs
            )
            refs, loaded, is_available, _, source_graph = self._load_requests(
                member.repository_id, requests
            )
            if is_available:
                available.add(member.repository_id)
            graph.extend(source_graph)
            declarations.extend(loaded)
            current_members.append(
                m.FunctionalPyramidMemberView(
                    repository_id=member.repository_id,
                    declaration_refs=refs or member.declaration_refs,
                    functional_scope=member.functional_scope,
                    coverage=member.coverage,
                )
            )

        return (
            tuple(current_members),
            tuple(declarations),
            frozenset(available),
            tuple(graph),
        )

    def _authority_bindings(
        self,
        members: tuple[m.FunctionalPyramidMemberView, ...],
        declarations: tuple[_DeclarationEntry, ...],
        available: frozenset[str],
    ) -> tuple[_AuthorityMap, tuple[m.FunctionalPyramidFinding, ...]]:
        member_repositories = frozenset(member.repository_id for member in members)
        bindings: _AuthorityMap = {}
        findings: list[m.FunctionalPyramidFinding] = []

        for _, declaration in declarations:
            for rule in declaration.rules:
                owner = rule.owner
                if owner.repository_id not in member_repositories:
                    findings.append(
                        _graph_finding(
                            m.FunctionalPyramidFindingReason.INVALID_DECLARATION,
                            owner.repository_id,
                            "functional rule owner repository is outside the active pyramid",
                            "move the authority owner into the instance or correct the rule owner",
                            rule_id=rule.rule_id,
                        )
                    )
                    continue
                if owner.repository_id not in available:
                    findings.append(
                        _graph_finding(
                            m.FunctionalPyramidFindingReason.REPOSITORY_UNAVAILABLE,
                            owner.repository_id,
                            "functional rule authority owner repository is unavailable",
                            "restore the named member repository",
                            rule_id=rule.rule_id,
                        )
                    )
                    continue
                key = (owner.repository_id, owner.authority_ref)
                if key in bindings:
                    continue
                try:
                    bindings[key] = self._authority.resolve_authority(*key)
                except ValueError:
                    findings.append(
                        _graph_finding(
                            m.FunctionalPyramidFindingReason.INVALID_DECLARATION,
                            owner.repository_id,
                            "functional rule owner is not a declared authority binding",
                            "declare the canonical authority binding or correct the owner reference",
                            rule_id=rule.rule_id,
                        )
                    )

        return bindings, tuple(findings)

    def resolve(
        self,
        *,
        pyramid_id: m.FunctionalPyramidId,
        version: m.FunctionalPyramidVersion,
        members: tuple[m.FunctionalPyramidMemberView, ...],
        surface: m.SurfaceKey,
        semantic_scope: m.EvidenceScope,
    ) -> tuple[m.FunctionalPyramidView, m.FunctionalRouteIdentity]:
        """Load current declarations and resolve one route."""
        current_members, declarations, available, source_findings = (
            self._load_active_members(members)
        )
        authorities, authority_findings = self._authority_bindings(
            current_members, declarations, available
        )
        return _fp.resolve_functional_pyramid_route(
            pyramid_id=pyramid_id,
            version=version,
            members=current_members,
            surface=surface,
            semantic_scope=semantic_scope,
            declarations=declarations,
            available_repositories=available,
            authority_bindings=authorities,
            declaration_findings=source_findings + authority_findings,
        )

    def health(
        self, members: tuple[m.FunctionalPyramidMemberView, ...]
    ) -> tuple[m.FunctionalPyramidHealth, tuple[m.FunctionalPyramidFinding, ...]]:
        """Evaluate live structural health from current declarations."""
        current_members, declarations, available, source_findings = (
            self._load_active_members(members)
        )
        _, authority_findings = self._authority_bindings(
            current_members, declarations, available
        )
        return _fp.evaluate_functional_pyramid_health(
            current_members,
            declarations,
            available,
            source_findings + authority_findings,
        )
