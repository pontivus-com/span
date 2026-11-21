"""Pure FunctionalScope algebra for Functional Pyramid resolution."""

from __future__ import annotations

import collections.abc as _collections
import hashlib as _hashlib
import json as _json

from span.core import containment as _containment
from span.core.model.functional_pyramid import (
    FunctionalContextDeclaration,
    FunctionalContextRoute,
    FunctionalGraphRef,
    FunctionalPyramidCoverage,
    FunctionalPyramidDeclaration,
    FunctionalPyramidFinding,
    FunctionalPyramidFindingReason,
    FunctionalPyramidHealth,
    FunctionalPyramidId,
    FunctionalPyramidLayer,
    FunctionalPyramidMemberView,
    FunctionalPyramidRouteStatus,
    FunctionalPyramidVersion,
    FunctionalPyramidView,
    FunctionalRouteIdentity,
    FunctionalRouteProvenance,
    FunctionalRuleDeclaration,
    FunctionalRuleOwner,
    FunctionalRuleRoute,
    FunctionalScope,
    FunctionalScopeRelation,
    FunctionalScopeSelector,
    FunctionalScopeSelectorKind,
)
from span.core.model.investigation import EvidenceRequest, SourceRange
from span.core.model.primitives import AuthorityBinding, EvidenceRef, EvidenceScope
from span.core.model.surfaces import SurfaceKey, SurfaceKind

_KIND_ORDER = (
    FunctionalScopeSelectorKind.REPOSITORY,
    FunctionalScopeSelectorKind.PREFIX,
    FunctionalScopeSelectorKind.PATH,
    FunctionalScopeSelectorKind.SYMBOL,
)


def _selector_sort_key(
    selector: FunctionalScopeSelector,
) -> tuple[int, str, str]:
    return (
        _KIND_ORDER.index(selector.kind),
        selector.path or "",
        selector.locator or "",
    )


def _path_in_prefix(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(prefix + "/")


def functional_scope_selector_contains(
    outer: FunctionalScopeSelector,
    inner: FunctionalScopeSelector,
) -> bool:
    """Whether outer wholly contains inner under the Version-1 symbolic algebra."""
    if outer.kind is FunctionalScopeSelectorKind.REPOSITORY:
        return True

    if outer.kind is FunctionalScopeSelectorKind.PREFIX:
        if inner.kind is FunctionalScopeSelectorKind.REPOSITORY:
            return False
        assert outer.path is not None
        assert inner.path is not None
        return _path_in_prefix(inner.path, outer.path)

    if outer.kind is FunctionalScopeSelectorKind.PATH:
        if inner.kind is FunctionalScopeSelectorKind.PATH:
            return outer.path == inner.path
        if inner.kind is FunctionalScopeSelectorKind.SYMBOL:
            return outer.path == inner.path
        return False

    if outer.kind is FunctionalScopeSelectorKind.SYMBOL:
        return (
            inner.kind is FunctionalScopeSelectorKind.SYMBOL
            and outer.path == inner.path
            and outer.locator == inner.locator
        )

    raise AssertionError(f"unhandled selector kind: {outer.kind!r}")


def functional_scope_selector_intersects(
    left: FunctionalScopeSelector,
    right: FunctionalScopeSelector,
) -> bool:
    """Two selectors intersect iff either wholly contains the other."""
    return functional_scope_selector_contains(
        left, right
    ) or functional_scope_selector_contains(right, left)


def normalize_functional_scope(
    selectors: _collections.Iterable[FunctionalScopeSelector],
) -> FunctionalScope:
    """Deduplicate and remove selectors wholly contained by broader selectors."""
    unique = tuple(sorted(set(selectors), key=_selector_sort_key))
    if not unique:
        raise ValueError("FunctionalScope normalization requires selectors")

    retained: list[FunctionalScopeSelector] = []
    for selector in unique:
        if any(
            functional_scope_selector_contains(existing, selector)
            for existing in retained
        ):
            continue
        retained = [
            existing
            for existing in retained
            if not functional_scope_selector_contains(selector, existing)
        ]
        retained.append(selector)

    return FunctionalScope(selectors=tuple(retained))


def functional_scope_contains(outer: FunctionalScope, inner: FunctionalScope) -> bool:
    """Whether every normalized inner selector is contained by an outer selector."""
    normalized_outer = normalize_functional_scope(outer.selectors)
    normalized_inner = normalize_functional_scope(inner.selectors)
    return all(
        any(
            functional_scope_selector_contains(outer_selector, inner_selector)
            for outer_selector in normalized_outer.selectors
        )
        for inner_selector in normalized_inner.selectors
    )


def functional_scope_intersects(left: FunctionalScope, right: FunctionalScope) -> bool:
    """Whether any selector from the two normalized scopes intersects."""
    normalized_left = normalize_functional_scope(left.selectors)
    normalized_right = normalize_functional_scope(right.selectors)
    return any(
        functional_scope_selector_intersects(left_selector, right_selector)
        for left_selector in normalized_left.selectors
        for right_selector in normalized_right.selectors
    )


def functional_scope_union(
    scopes: _collections.Iterable[FunctionalScope],
) -> FunctionalScope:
    """Canonical symbolic union of one or more FunctionalScopes."""
    selectors: list[FunctionalScopeSelector] = []
    supplied = False
    for scope in scopes:
        supplied = True
        selectors.extend(scope.selectors)
    if not supplied:
        raise ValueError("FunctionalScope union requires at least one scope")
    return normalize_functional_scope(selectors)


def functional_scope_uncovered(
    member_scope: FunctionalScope,
    coverage_scopes: _collections.Iterable[FunctionalScope],
) -> tuple[FunctionalScopeSelector, ...]:
    """Return member selectors not wholly covered by the declared coverage union.

    Version 1 deliberately returns uncovered member selectors rather than
    inventing complement globs or enumerating current repository files.
    """
    normalized_member = normalize_functional_scope(member_scope.selectors)
    supplied = tuple(coverage_scopes)
    if not supplied:
        return normalized_member.selectors
    coverage = functional_scope_union(supplied)
    return tuple(
        selector
        for selector in normalized_member.selectors
        if not any(
            functional_scope_selector_contains(covering, selector)
            for covering in coverage.selectors
        )
    )


def _require_json_object(
    value: object, required: frozenset[str], optional: frozenset[str] = frozenset()
) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError("Functional Pyramid JSON value must be an object")
    keys = frozenset(str(key) for key in value)
    allowed = required | optional
    if keys - allowed:
        raise ValueError(
            "unknown Functional Pyramid JSON fields: "
            + ", ".join(sorted(keys - allowed))
        )
    missing = required - keys
    if missing:
        raise ValueError(
            "missing Functional Pyramid JSON fields: "
            + ", ".join(sorted(missing))
        )
    if any(not isinstance(key, str) for key in value):
        raise ValueError("Functional Pyramid JSON object keys must be strings")
    return value


def _require_json_array(value: object, name: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be an array")
    return value


def _require_json_string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _decode_scope_selector(value: object) -> FunctionalScopeSelector:
    raw = _require_json_object(value, frozenset({"kind"}), frozenset({"path", "locator"}))
    try:
        kind = FunctionalScopeSelectorKind(
            _require_json_string(raw["kind"], "FunctionalScopeSelector.kind")
        )
    except ValueError as exc:
        raise ValueError("unknown FunctionalScopeSelector.kind") from exc

    expected = {
        FunctionalScopeSelectorKind.REPOSITORY: frozenset({"kind"}),
        FunctionalScopeSelectorKind.PATH: frozenset({"kind", "path"}),
        FunctionalScopeSelectorKind.PREFIX: frozenset({"kind", "path"}),
        FunctionalScopeSelectorKind.SYMBOL: frozenset({"kind", "path", "locator"}),
    }[kind]
    if frozenset(raw) != expected:
        raise ValueError(f"{kind.value} selector has invalid fields")
    path = raw.get("path")
    locator = raw.get("locator")
    return FunctionalScopeSelector(
        kind=kind,
        path=None if path is None else _require_json_string(path, "selector path"),
        locator=(
            None
            if locator is None
            else _require_json_string(locator, "selector locator")
        ),
    )


def decode_functional_scope(value: object) -> FunctionalScope:
    """Strictly decode and normalize one Version-1 FunctionalScope array."""
    selectors = tuple(
        _decode_scope_selector(item)
        for item in _require_json_array(value, "FunctionalScope")
    )
    return normalize_functional_scope(selectors)


def _decode_graph_ref(value: object) -> FunctionalGraphRef:
    raw = _require_json_object(
        value, frozenset({"repository_id", "identity"})
    )
    return FunctionalGraphRef(
        repository_id=_require_json_string(
            raw["repository_id"], "FunctionalGraphRef.repository_id"
        ),
        identity=_require_json_string(raw["identity"], "FunctionalGraphRef.identity"),
    )


def _decode_evidence_request(value: object) -> EvidenceRequest:
    raw = _require_json_object(
        value, frozenset({"locator"}), frozenset({"ranges"})
    )
    ranges: list[SourceRange] = []
    for item in _require_json_array(raw.get("ranges", []), "EvidenceRequest.ranges"):
        range_raw = _require_json_object(
            item, frozenset({"start_line", "end_line"})
        )
        start = range_raw["start_line"]
        end = range_raw["end_line"]
        if not isinstance(start, int) or isinstance(start, bool):
            raise ValueError("SourceRange.start_line must be an integer")
        if not isinstance(end, int) or isinstance(end, bool):
            raise ValueError("SourceRange.end_line must be an integer")
        ranges.append(SourceRange(start_line=start, end_line=end))
    return EvidenceRequest(
        locator=_require_json_string(raw["locator"], "EvidenceRequest.locator"),
        ranges=tuple(ranges),
    )


def decode_functional_pyramid_bootstrap(text: str):
    """Decode the optional navigation bootstrap into the canonical carrier."""
    from span.core.model.functional_pyramid import FunctionalPyramidBootstrap

    try:
        value = _json.loads(text)
    except _json.JSONDecodeError as exc:
        raise ValueError("Functional Pyramid bootstrap is not valid JSON") from exc
    raw = _require_json_object(
        value,
        frozenset(
            {"version", "functional_scope", "coverage", "declaration_sources"}
        ),
    )
    if raw["version"] != 1:
        raise ValueError("Functional Pyramid bootstrap version must be 1")
    coverage_raw = _require_json_string(raw["coverage"], "bootstrap coverage")
    try:
        coverage = FunctionalPyramidCoverage(coverage_raw)
    except ValueError as exc:
        raise ValueError("unknown Functional Pyramid coverage mode") from exc
    sources = tuple(
        _decode_evidence_request(item)
        for item in _require_json_array(
            raw["declaration_sources"], "bootstrap declaration_sources"
        )
    )
    return FunctionalPyramidBootstrap(
        version=1,
        functional_scope=decode_functional_scope(raw["functional_scope"]),
        coverage=coverage,
        declaration_sources=sources,
    )


def decode_functional_pyramid_declaration(text: str) -> FunctionalPyramidDeclaration:
    """Strictly decode one repository-owned Functional Pyramid declaration."""
    try:
        value = _json.loads(text)
    except _json.JSONDecodeError as exc:
        raise ValueError("Functional Pyramid declaration is not valid JSON") from exc
    raw = _require_json_object(
        value, frozenset({"version", "contexts", "rules"})
    )
    if raw["version"] != 1:
        raise ValueError("Functional Pyramid declaration version must be 1")

    contexts: list[FunctionalContextDeclaration] = []
    for item in _require_json_array(raw["contexts"], "declaration contexts"):
        context = _require_json_object(
            item, frozenset({"context_id", "coverage", "inherits", "rules"})
        )
        contexts.append(
            FunctionalContextDeclaration(
                context_id=_require_json_string(
                    context["context_id"], "context_id"
                ),
                coverage=decode_functional_scope(context["coverage"]),
                inherits=tuple(
                    _decode_graph_ref(value)
                    for value in _require_json_array(
                        context["inherits"], "context inherits"
                    )
                ),
                rules=tuple(
                    _decode_graph_ref(value)
                    for value in _require_json_array(
                        context["rules"], "context rules"
                    )
                ),
            )
        )

    rules: list[FunctionalRuleDeclaration] = []
    for item in _require_json_array(raw["rules"], "declaration rules"):
        rule = _require_json_object(
            item,
            frozenset(
                {"rule_id", "layer", "owner", "governing_rule_ids"}
            ),
        )
        owner = _require_json_object(
            rule["owner"], frozenset({"repository_id", "authority_ref"})
        )
        try:
            layer = FunctionalPyramidLayer(
                _require_json_string(rule["layer"], "rule layer")
            )
        except ValueError as exc:
            raise ValueError("unknown Functional Pyramid layer") from exc
        governing: list[FunctionalGraphRef | str] = []
        for value in _require_json_array(
            rule["governing_rule_ids"], "rule governing_rule_ids"
        ):
            if isinstance(value, str):
                if value != "ROOT":
                    raise ValueError("the only string governing terminal is ROOT")
                governing.append(value)
            else:
                governing.append(_decode_graph_ref(value))
        rules.append(
            FunctionalRuleDeclaration(
                rule_id=_require_json_string(rule["rule_id"], "rule_id"),
                layer=layer,
                owner=FunctionalRuleOwner(
                    repository_id=_require_json_string(
                        owner["repository_id"], "rule owner repository_id"
                    ),
                    authority_ref=_require_json_string(
                        owner["authority_ref"], "rule owner authority_ref"
                    ),
                ),
                governing_rule_ids=tuple(governing),
            )
        )

    return FunctionalPyramidDeclaration(
        version=1, contexts=tuple(contexts), rules=tuple(rules)
    )


def _layer_rank(layer: FunctionalPyramidLayer) -> int:
    if layer is FunctionalPyramidLayer.P0:
        return 0
    if layer is FunctionalPyramidLayer.P1:
        return 1
    if layer in (FunctionalPyramidLayer.P2S, FunctionalPyramidLayer.P2W):
        return 2
    if layer is FunctionalPyramidLayer.P3:
        return 3
    return 4


def _finding_sort_key(
    finding: FunctionalPyramidFinding,
) -> tuple[str, str, str, str, str, str]:
    return (
        finding.reason.value,
        finding.repository_id or "",
        finding.context_id or "",
        finding.rule_id or "",
        finding.declaration_locator or "",
        finding.detail,
    )


def _ordered_findings(
    findings: _collections.Iterable[FunctionalPyramidFinding],
) -> tuple[FunctionalPyramidFinding, ...]:
    return tuple(sorted(set(findings), key=_finding_sort_key))


def _finding(
    reason: FunctionalPyramidFindingReason,
    detail: str,
    recovery: str,
    *,
    repository_id: str | None = None,
    context_id: str | None = None,
    rule_id: str | None = None,
    declaration_locator: str | None = None,
) -> FunctionalPyramidFinding:
    return FunctionalPyramidFinding(
        reason=reason,
        repository_id=repository_id,
        context_id=context_id,
        rule_id=rule_id,
        declaration_locator=declaration_locator,
        detail=detail,
        recovery=recovery,
    )


def _declaration_indexes(
    declarations: tuple[tuple[str, FunctionalPyramidDeclaration], ...],
) -> tuple[
    dict[tuple[str, str], FunctionalContextDeclaration],
    dict[tuple[str, str], FunctionalRuleDeclaration],
    frozenset[str],
    frozenset[str],
]:
    contexts: dict[tuple[str, str], FunctionalContextDeclaration] = {}
    rules: dict[tuple[str, str], FunctionalRuleDeclaration] = {}
    context_owner: dict[str, tuple[str, FunctionalContextDeclaration]] = {}
    rule_owner: dict[str, tuple[str, FunctionalRuleDeclaration]] = {}
    duplicate_contexts: set[str] = set()
    duplicate_rules: set[str] = set()

    for repository_id, declaration in declarations:
        for context in declaration.contexts:
            key = (repository_id, context.context_id)
            previous = contexts.get(key)
            if previous is not None and previous != context:
                duplicate_contexts.add(context.context_id)
            contexts.setdefault(key, context)
            owner = context_owner.get(context.context_id)
            if owner is None:
                context_owner[context.context_id] = (repository_id, context)
            elif owner != (repository_id, context):
                duplicate_contexts.add(context.context_id)

        for rule in declaration.rules:
            key = (repository_id, rule.rule_id)
            previous = rules.get(key)
            if previous is not None and previous != rule:
                duplicate_rules.add(rule.rule_id)
            rules.setdefault(key, rule)
            owner = rule_owner.get(rule.rule_id)
            if owner is None:
                rule_owner[rule.rule_id] = (repository_id, rule)
            elif owner != (repository_id, rule):
                duplicate_rules.add(rule.rule_id)

    return contexts, rules, frozenset(duplicate_contexts), frozenset(duplicate_rules)


def _semantic_atoms(
    surface: SurfaceKey, scope: EvidenceScope
) -> tuple[tuple[EvidenceScope, FunctionalScopeSelector], ...]:
    if surface.kind is SurfaceKind.FILE:
        if any(path != surface.locator for path in scope.paths) or any(
            ref.repository_id != surface.repository_id
            or ref.locator != surface.locator
            for ref in scope.evidence_refs
        ):
            raise ValueError("FILE semantic scope conflicts with its owning surface")
        return (
            (
                EvidenceScope(paths=(surface.locator,)),
                FunctionalScopeSelector(
                    FunctionalScopeSelectorKind.PATH, path=surface.locator
                ),
            ),
        )

    if surface.kind is SurfaceKind.SYMBOL:
        path = _containment.surface_file_locator(surface.locator)
        if path is None:
            raise ValueError("SYMBOL surface has no canonical owning path")
        if any(value != path for value in scope.paths) or any(
            ref.repository_id != surface.repository_id
            or ref.locator not in (surface.locator, path)
            for ref in scope.evidence_refs
        ):
            raise ValueError("SYMBOL semantic scope conflicts with its owning surface")
        return (
            (
                EvidenceScope(paths=(path,)),
                FunctionalScopeSelector(
                    FunctionalScopeSelectorKind.SYMBOL,
                    path=path,
                    locator=surface.locator,
                ),
            ),
        )

    if not scope.paths and not scope.evidence_refs:
        return (
            (
                EvidenceScope(),
                FunctionalScopeSelector(FunctionalScopeSelectorKind.REPOSITORY),
            ),
        )

    atoms: list[tuple[EvidenceScope, FunctionalScopeSelector]] = []
    for path in scope.paths:
        atoms.append(
            (
                EvidenceScope(paths=(path,)),
                FunctionalScopeSelector(
                    FunctionalScopeSelectorKind.PREFIX, path=path
                ),
            )
        )
    for ref in scope.evidence_refs:
        if ref.repository_id != surface.repository_id:
            raise ValueError("semantic scope crosses its owning repository")
        symbol_path = _containment.surface_file_locator(ref.locator)
        selector = (
            FunctionalScopeSelector(
                FunctionalScopeSelectorKind.SYMBOL,
                path=symbol_path,
                locator=ref.locator,
            )
            if symbol_path is not None
            else FunctionalScopeSelector(
                FunctionalScopeSelectorKind.PATH, path=ref.locator
            )
        )
        atoms.append((EvidenceScope(evidence_refs=(ref,)), selector))
    return tuple(atoms)


def _intersection_selectors(
    semantic: FunctionalScopeSelector, member_scope: FunctionalScope
) -> tuple[FunctionalScopeSelector, ...]:
    found: list[FunctionalScopeSelector] = []
    for member in normalize_functional_scope(member_scope.selectors).selectors:
        if not functional_scope_selector_intersects(semantic, member):
            continue
        found.append(
            semantic
            if functional_scope_selector_contains(member, semantic)
            else member
        )
    if not found:
        return ()
    return normalize_functional_scope(found).selectors


def _semantic_has_outside_remainder(
    semantic: FunctionalScopeSelector, member_scope: FunctionalScope
) -> bool:
    return not any(
        functional_scope_selector_contains(member, semantic)
        for member in normalize_functional_scope(member_scope.selectors).selectors
    )


def _ref_finding(
    ref: FunctionalGraphRef,
    *,
    member_repositories: frozenset[str],
    available_repositories: frozenset[str],
    contexts: dict[tuple[str, str], FunctionalContextDeclaration],
    rules: dict[tuple[str, str], FunctionalRuleDeclaration],
    context: bool,
) -> FunctionalPyramidFinding | None:
    if ref.repository_id not in member_repositories:
        return _finding(
            FunctionalPyramidFindingReason.INVALID_DECLARATION,
            "graph reference targets a repository outside the active pyramid",
            "correct the repository-qualified declaration edge",
            repository_id=ref.repository_id,
            context_id=ref.identity if context else None,
            rule_id=None if context else ref.identity,
        )
    if ref.repository_id not in available_repositories:
        return _finding(
            FunctionalPyramidFindingReason.REPOSITORY_UNAVAILABLE,
            "referenced Functional Pyramid member is unavailable",
            "restore the named member repository and retry",
            repository_id=ref.repository_id,
            context_id=ref.identity if context else None,
            rule_id=None if context else ref.identity,
        )
    key = (ref.repository_id, ref.identity)
    if context and key not in contexts:
        return _finding(
            FunctionalPyramidFindingReason.UNKNOWN_CONTEXT,
            "referenced context does not exist in the named available member",
            "correct the context reference or declaration",
            repository_id=ref.repository_id,
            context_id=ref.identity,
        )
    if not context and key not in rules:
        return _finding(
            FunctionalPyramidFindingReason.UNKNOWN_RULE,
            "referenced rule does not exist in the named available member",
            "correct the rule reference or declaration",
            repository_id=ref.repository_id,
            rule_id=ref.identity,
        )
    return None


def _graph_structural_findings(
    members: tuple[FunctionalPyramidMemberView, ...],
    declarations: tuple[tuple[str, FunctionalPyramidDeclaration], ...],
    available_repositories: frozenset[str],
    declaration_findings: tuple[FunctionalPyramidFinding, ...] = (),
) -> tuple[FunctionalPyramidFinding, ...]:
    contexts, rules, duplicate_contexts, duplicate_rules = _declaration_indexes(
        declarations
    )
    member_repositories = frozenset(member.repository_id for member in members)
    findings: list[FunctionalPyramidFinding] = list(declaration_findings)

    for member in members:
        if member.repository_id not in available_repositories:
            findings.append(
                _finding(
                    FunctionalPyramidFindingReason.REPOSITORY_UNAVAILABLE,
                    "active Functional Pyramid member is unavailable",
                    "restore the member repository and its declarations",
                    repository_id=member.repository_id,
                )
            )

    for identity in sorted(duplicate_contexts):
        findings.append(
            _finding(
                FunctionalPyramidFindingReason.DUPLICATE_CONTEXT_OWNER,
                "context identity has more than one declaration owner",
                "retain exactly one canonical context declaration",
                context_id=identity,
            )
        )
    for identity in sorted(duplicate_rules):
        findings.append(
            _finding(
                FunctionalPyramidFindingReason.DUPLICATE_RULE_OWNER,
                "rule identity has more than one declaration owner",
                "retain exactly one canonical rule declaration",
                rule_id=identity,
            )
        )

    for (repository_id, context_id), context_value in contexts.items():
        for ref in context_value.inherits:
            ref_finding = _ref_finding(
                ref,
                member_repositories=member_repositories,
                available_repositories=available_repositories,
                contexts=contexts,
                rules=rules,
                context=True,
            )
            if ref_finding is not None:
                findings.append(ref_finding)
        for ref in context_value.rules:
            ref_finding = _ref_finding(
                ref,
                member_repositories=member_repositories,
                available_repositories=available_repositories,
                contexts=contexts,
                rules=rules,
                context=False,
            )
            if ref_finding is not None:
                findings.append(ref_finding)

        seen: set[tuple[str, str]] = set()
        active: set[tuple[str, str]] = set()

        def walk_context(key: tuple[str, str]) -> None:
            if key in active:
                findings.append(
                    _finding(
                        FunctionalPyramidFindingReason.CONTEXT_CYCLE,
                        "context inheritance contains a cycle",
                        "remove the cyclic inheritance edge",
                        repository_id=key[0],
                        context_id=key[1],
                    )
                )
                return
            if key in seen:
                return
            seen.add(key)
            active.add(key)
            current = contexts.get(key)
            if current is not None:
                for ref in current.inherits:
                    if (
                        ref.repository_id in available_repositories
                        and (ref.repository_id, ref.identity) in contexts
                    ):
                        walk_context((ref.repository_id, ref.identity))
            active.remove(key)

        walk_context((repository_id, context_id))

    for (repository_id, rule_id), rule_value in rules.items():
        parents = rule_value.governing_rule_ids
        if rule_value.layer is FunctionalPyramidLayer.P0:
            if parents != ("ROOT",):
                findings.append(
                    _finding(
                        FunctionalPyramidFindingReason.INVALID_GOVERNING_EDGE,
                        "P0 rule must be governed by ROOT exactly",
                        "declare ROOT as the sole P0 governing terminal",
                        repository_id=repository_id,
                        rule_id=rule_id,
                    )
                )
        elif not parents:
            findings.append(
                _finding(
                    FunctionalPyramidFindingReason.UNRESOLVED_RULE_PARENT,
                    "non-P0 rule has no governing rule",
                    "declare at least one valid higher governing rule",
                    repository_id=repository_id,
                    rule_id=rule_id,
                )
            )

        for parent in parents:
            if isinstance(parent, str):
                if rule_value.layer is not FunctionalPyramidLayer.P0:
                    findings.append(
                        _finding(
                            FunctionalPyramidFindingReason.INVALID_GOVERNING_EDGE,
                            "ROOT may govern only a P0 rule",
                            "replace ROOT with a valid higher governing rule",
                            repository_id=repository_id,
                            rule_id=rule_id,
                        )
                    )
                continue
            ref_finding = _ref_finding(
                parent,
                member_repositories=member_repositories,
                available_repositories=available_repositories,
                contexts=contexts,
                rules=rules,
                context=False,
            )
            if ref_finding is not None:
                findings.append(ref_finding)
                continue
            target = rules[(parent.repository_id, parent.identity)]
            if _layer_rank(target.layer) >= _layer_rank(rule_value.layer):
                findings.append(
                    _finding(
                        FunctionalPyramidFindingReason.INVALID_GOVERNING_EDGE,
                        "governing edge does not point to a higher pyramid layer",
                        "point the edge to a valid higher governing rule",
                        repository_id=repository_id,
                        rule_id=rule_id,
                    )
                )

        seen_rules: set[tuple[str, str]] = set()
        active_rules: set[tuple[str, str]] = set()

        def walk_rule(key: tuple[str, str]) -> None:
            if key in active_rules:
                findings.append(
                    _finding(
                        FunctionalPyramidFindingReason.RULE_CYCLE,
                        "governing rules contain a cycle",
                        "remove the cyclic governing edge",
                        repository_id=key[0],
                        rule_id=key[1],
                    )
                )
                return
            if key in seen_rules:
                return
            seen_rules.add(key)
            active_rules.add(key)
            current = rules.get(key)
            if current is not None:
                for parent in current.governing_rule_ids:
                    if (
                        isinstance(parent, FunctionalGraphRef)
                        and parent.repository_id in available_repositories
                        and (parent.repository_id, parent.identity) in rules
                    ):
                        walk_rule((parent.repository_id, parent.identity))
            active_rules.remove(key)

        walk_rule((repository_id, rule_id))

    for member in members:
        if member.coverage is not FunctionalPyramidCoverage.COMPLETE:
            continue
        coverage = tuple(
            context.coverage
            for (repository_id, _), context in contexts.items()
            if repository_id == member.repository_id
        )
        uncovered = functional_scope_uncovered(member.functional_scope, coverage)
        if uncovered:
            findings.append(
                _finding(
                    FunctionalPyramidFindingReason.UNCOVERED_PATH,
                    "COMPLETE member FunctionalScope has uncovered selectors",
                    "add applicable Functional Context coverage or revise coverage mode",
                    repository_id=member.repository_id,
                )
            )

    return _ordered_findings(findings)


def evaluate_functional_pyramid_health(
    members: tuple[FunctionalPyramidMemberView, ...],
    declarations: tuple[tuple[str, FunctionalPyramidDeclaration], ...],
    available_repositories: frozenset[str],
    declaration_findings: tuple[FunctionalPyramidFinding, ...] = (),
) -> tuple[FunctionalPyramidHealth, tuple[FunctionalPyramidFinding, ...]]:
    """Compute FD-83 live structural health without persisting it."""
    findings = _graph_structural_findings(
        members,
        declarations,
        available_repositories,
        declaration_findings,
    )
    health = (
        FunctionalPyramidHealth.VALID
        if not findings
        else FunctionalPyramidHealth.DEGRADED
    )
    return health, findings


def _context_direct_refs(
    repository_id: str,
    selector: FunctionalScopeSelector,
    contexts: dict[tuple[str, str], FunctionalContextDeclaration],
    duplicate_contexts: frozenset[str],
) -> tuple[FunctionalGraphRef, ...]:
    refs: list[FunctionalGraphRef] = []
    for (owner_repository, context_id), context in contexts.items():
        if owner_repository != repository_id or context_id in duplicate_contexts:
            continue
        if any(
            functional_scope_selector_intersects(selector, coverage)
            for coverage in context.coverage.selectors
        ):
            refs.append(FunctionalGraphRef(owner_repository, context_id))
    return tuple(refs)


def _resolve_context_refs(
    direct_refs: tuple[FunctionalGraphRef, ...],
    *,
    contexts: dict[tuple[str, str], FunctionalContextDeclaration],
    rules: dict[tuple[str, str], FunctionalRuleDeclaration],
    duplicate_contexts: frozenset[str],
    member_repositories: frozenset[str],
    available_repositories: frozenset[str],
) -> tuple[
    tuple[tuple[FunctionalGraphRef, bool], ...],
    tuple[FunctionalPyramidFinding, ...],
]:
    ordered: list[tuple[FunctionalGraphRef, bool]] = []
    direct_keys = {(ref.repository_id, ref.identity) for ref in direct_refs}
    emitted: set[tuple[str, str]] = set()
    findings: list[FunctionalPyramidFinding] = []

    def visit(ref: FunctionalGraphRef, stack: tuple[tuple[str, str], ...]) -> None:
        key = (ref.repository_id, ref.identity)
        if ref.identity in duplicate_contexts:
            findings.append(
                _finding(
                    FunctionalPyramidFindingReason.DUPLICATE_CONTEXT_OWNER,
                    "context identity has more than one declaration owner",
                    "retain exactly one canonical context declaration",
                    repository_id=ref.repository_id,
                    context_id=ref.identity,
                )
            )
            return
        ref_finding = _ref_finding(
            ref,
            member_repositories=member_repositories,
            available_repositories=available_repositories,
            contexts=contexts,
            rules=rules,
            context=True,
        )
        if ref_finding is not None:
            findings.append(ref_finding)
            return
        if key in stack:
            findings.append(
                _finding(
                    FunctionalPyramidFindingReason.CONTEXT_CYCLE,
                    "context inheritance contains a cycle",
                    "remove the cyclic inheritance edge",
                    repository_id=ref.repository_id,
                    context_id=ref.identity,
                )
            )
            return
        if key not in emitted:
            emitted.add(key)
            ordered.append((ref, key in direct_keys))
        context = contexts[key]
        for inherited in context.inherits:
            visit(inherited, stack + (key,))

    for ref in direct_refs:
        visit(ref, ())
    return tuple(ordered), _ordered_findings(findings)


def _resolve_rule_refs(
    initial_refs: tuple[FunctionalGraphRef, ...],
    *,
    contexts: dict[tuple[str, str], FunctionalContextDeclaration],
    rules: dict[tuple[str, str], FunctionalRuleDeclaration],
    duplicate_rules: frozenset[str],
    member_repositories: frozenset[str],
    available_repositories: frozenset[str],
) -> tuple[
    tuple[FunctionalGraphRef, ...],
    tuple[FunctionalPyramidFinding, ...],
]:
    emitted: list[FunctionalGraphRef] = []
    seen: set[tuple[str, str]] = set()
    active: set[tuple[str, str]] = set()
    findings: list[FunctionalPyramidFinding] = []

    def visit(ref: FunctionalGraphRef) -> None:
        key = (ref.repository_id, ref.identity)
        if ref.identity in duplicate_rules:
            findings.append(
                _finding(
                    FunctionalPyramidFindingReason.DUPLICATE_RULE_OWNER,
                    "rule identity has more than one declaration owner",
                    "retain exactly one canonical rule declaration",
                    repository_id=ref.repository_id,
                    rule_id=ref.identity,
                )
            )
            return
        ref_finding = _ref_finding(
            ref,
            member_repositories=member_repositories,
            available_repositories=available_repositories,
            contexts=contexts,
            rules=rules,
            context=False,
        )
        if ref_finding is not None:
            findings.append(ref_finding)
            return
        if key in active:
            findings.append(
                _finding(
                    FunctionalPyramidFindingReason.RULE_CYCLE,
                    "governing rules contain a cycle",
                    "remove the cyclic governing edge",
                    repository_id=ref.repository_id,
                    rule_id=ref.identity,
                )
            )
            return
        if key in seen:
            return
        seen.add(key)
        active.add(key)
        emitted.append(ref)
        rule = rules[key]
        if rule.layer is FunctionalPyramidLayer.P0:
            if rule.governing_rule_ids != ("ROOT",):
                findings.append(
                    _finding(
                        FunctionalPyramidFindingReason.INVALID_GOVERNING_EDGE,
                        "P0 rule must be governed by ROOT exactly",
                        "declare ROOT as the sole P0 governing terminal",
                        repository_id=ref.repository_id,
                        rule_id=ref.identity,
                    )
                )
        elif not rule.governing_rule_ids:
            findings.append(
                _finding(
                    FunctionalPyramidFindingReason.UNRESOLVED_RULE_PARENT,
                    "non-P0 rule has no governing rule",
                    "declare at least one valid higher governing rule",
                    repository_id=ref.repository_id,
                    rule_id=ref.identity,
                )
            )
        for parent in rule.governing_rule_ids:
            if isinstance(parent, str):
                if rule.layer is not FunctionalPyramidLayer.P0:
                    findings.append(
                        _finding(
                            FunctionalPyramidFindingReason.INVALID_GOVERNING_EDGE,
                            "ROOT may govern only a P0 rule",
                            "replace ROOT with a valid higher governing rule",
                            repository_id=ref.repository_id,
                            rule_id=ref.identity,
                        )
                    )
                continue
            parent_finding = _ref_finding(
                parent,
                member_repositories=member_repositories,
                available_repositories=available_repositories,
                contexts=contexts,
                rules=rules,
                context=False,
            )
            if parent_finding is not None:
                findings.append(parent_finding)
                continue
            target = rules[(parent.repository_id, parent.identity)]
            if _layer_rank(target.layer) >= _layer_rank(rule.layer):
                findings.append(
                    _finding(
                        FunctionalPyramidFindingReason.INVALID_GOVERNING_EDGE,
                        "governing edge does not point to a higher pyramid layer",
                        "point the edge to a valid higher governing rule",
                        repository_id=ref.repository_id,
                        rule_id=ref.identity,
                    )
                )
                continue
            visit(parent)
        active.remove(key)

    for ref in initial_refs:
        visit(ref)
    return tuple(emitted), _ordered_findings(findings)


def _downstream_rule_ids(
    key: tuple[str, str],
    rules: dict[tuple[str, str], FunctionalRuleDeclaration],
) -> tuple[str, ...]:
    found: set[tuple[str, str]] = set()
    frontier = [key]
    while frontier:
        current = frontier.pop()
        for candidate_key, rule in rules.items():
            if candidate_key in found or candidate_key == key:
                continue
            if any(
                isinstance(parent, FunctionalGraphRef)
                and (parent.repository_id, parent.identity) == current
                for parent in rule.governing_rule_ids
            ):
                found.add(candidate_key)
                frontier.append(candidate_key)
    return tuple(sorted(identity for _, identity in found))


def _downstream_context_ids(
    rule_ids: frozenset[str],
    contexts: dict[tuple[str, str], FunctionalContextDeclaration],
) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                context_id
                for (_, context_id), context in contexts.items()
                if any(ref.identity in rule_ids for ref in context.rules)
            }
        )
    )


def _route_identity(
    surface: SurfaceKey,
    semantic_scope: EvidenceScope,
    contexts: tuple[FunctionalContextRoute, ...],
    rule_refs: tuple[FunctionalGraphRef, ...],
    rules: dict[tuple[str, str], FunctionalRuleDeclaration],
) -> FunctionalRouteIdentity:
    payload = {
        "surface": (
            surface.repository_id,
            surface.kind.value,
            surface.locator,
        ),
        "scope": {
            "paths": list(semantic_scope.paths),
            "refs": [
                (
                    ref.repository_id,
                    ref.evidence_id.value,
                    ref.locator,
                    ref.section_or_span,
                )
                for ref in semantic_scope.evidence_refs
            ],
        },
        "contexts": [
            (
                context.repository_id,
                context.context_id,
                context.direct,
                [
                    (selector.kind.value, selector.path, selector.locator)
                    for selector in context.coverage.selectors
                ],
                tuple(context.inherits),
                tuple(context.rule_ids),
            )
            for context in contexts
        ],
        "rules": [
            (
                ref.repository_id,
                ref.identity,
                rules[(ref.repository_id, ref.identity)].layer.value,
                rules[(ref.repository_id, ref.identity)].owner.repository_id,
                rules[(ref.repository_id, ref.identity)].owner.authority_ref,
                [
                    (
                        parent
                        if isinstance(parent, str)
                        else (parent.repository_id, parent.identity)
                    )
                    for parent in rules[
                        (ref.repository_id, ref.identity)
                    ].governing_rule_ids
                ],
            )
            for ref in rule_refs
            if (ref.repository_id, ref.identity) in rules
        ],
        "members": sorted(
            {surface.repository_id}
            | {context.repository_id for context in contexts}
            | {ref.repository_id for ref in rule_refs}
            | {
                rules[(ref.repository_id, ref.identity)].owner.repository_id
                for ref in rule_refs
                if (ref.repository_id, ref.identity) in rules
            }
        ),
    }
    encoded = _json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return FunctionalRouteIdentity(_hashlib.sha256(encoded).hexdigest())


def resolve_functional_pyramid_route(
    *,
    pyramid_id: FunctionalPyramidId,
    version: FunctionalPyramidVersion,
    members: tuple[FunctionalPyramidMemberView, ...],
    surface: SurfaceKey,
    semantic_scope: EvidenceScope,
    declarations: tuple[tuple[str, FunctionalPyramidDeclaration], ...],
    available_repositories: frozenset[str],
    authority_bindings: _collections.Mapping[tuple[str, str], AuthorityBinding],
    declaration_findings: tuple[FunctionalPyramidFinding, ...] = (),
) -> tuple[FunctionalPyramidView, FunctionalRouteIdentity]:
    """Resolve one governing route from explicit declarations only."""
    selected = next(
        (member for member in members if member.repository_id == surface.repository_id),
        None,
    )
    if selected is None:
        raise ValueError("selected surface repository is not an active pyramid member")

    health, health_findings = evaluate_functional_pyramid_health(
        members,
        declarations,
        available_repositories,
        declaration_findings,
    )
    contexts, rules, duplicate_contexts, duplicate_rules = _declaration_indexes(
        declarations
    )
    member_repositories = frozenset(member.repository_id for member in members)
    route_findings: list[FunctionalPyramidFinding] = [
        finding
        for finding in declaration_findings
        if finding.repository_id in (None, surface.repository_id)
    ]

    try:
        atoms = _semantic_atoms(surface, semantic_scope)
    except ValueError as exc:
        route_findings.append(
            _finding(
                FunctionalPyramidFindingReason.UNRESOLVED_SCOPE_INTERSECTION,
                str(exc),
                "supply a semantic scope consistent with the selected surface",
                repository_id=surface.repository_id,
            )
        )
        identity = _route_identity(
            surface, semantic_scope, (), (), rules
        )
        return (
            FunctionalPyramidView(
                pyramid_id=pyramid_id,
                version=version,
                health=health,
                coverage=selected.coverage,
                scope_relation=FunctionalScopeRelation.MIXED,
                status=FunctionalPyramidRouteStatus.UNRESOLVED,
                semantic_scope=semantic_scope,
                unresolved=_ordered_findings(route_findings),
            ),
            identity,
        )

    portion_records: list[
        tuple[
            EvidenceScope,
            FunctionalScopeSelector | None,
            FunctionalScopeRelation,
            tuple[FunctionalGraphRef, ...],
        ]
    ] = []
    direct_refs: list[FunctionalGraphRef] = []

    for atom_scope, semantic_selector in atoms:
        intersections = _intersection_selectors(
            semantic_selector, selected.functional_scope
        )
        if not intersections:
            portion_records.append(
                (
                    atom_scope,
                    None,
                    FunctionalScopeRelation.OUTSIDE_FUNCTIONAL_SCOPE,
                    (),
                )
            )
            continue

        if _semantic_has_outside_remainder(
            semantic_selector, selected.functional_scope
        ):
            portion_records.append(
                (
                    atom_scope,
                    None,
                    FunctionalScopeRelation.OUTSIDE_FUNCTIONAL_SCOPE,
                    (),
                )
            )

        for intersection in intersections:
            direct = _context_direct_refs(
                surface.repository_id,
                intersection,
                contexts,
                duplicate_contexts,
            )
            relation = (
                FunctionalScopeRelation.COVERED
                if direct
                else FunctionalScopeRelation.UNCOVERED
            )
            portion_records.append((atom_scope, intersection, relation, direct))
            direct_refs.extend(direct)
            if not direct:
                route_findings.append(
                    _finding(
                        FunctionalPyramidFindingReason.UNCOVERED_PATH,
                        "functional semantic scope has no applicable context",
                        "declare applicable Functional Context coverage",
                        repository_id=surface.repository_id,
                    )
                )

    dedup_direct: list[FunctionalGraphRef] = []
    seen_direct: set[tuple[str, str]] = set()
    for ref in direct_refs:
        key = (ref.repository_id, ref.identity)
        if key not in seen_direct:
            seen_direct.add(key)
            dedup_direct.append(ref)

    resolved_contexts, context_findings = _resolve_context_refs(
        tuple(dedup_direct),
        contexts=contexts,
        rules=rules,
        duplicate_contexts=duplicate_contexts,
        member_repositories=member_repositories,
        available_repositories=available_repositories,
    )
    route_findings.extend(context_findings)

    rule_initial: list[FunctionalGraphRef] = []
    context_routes: list[FunctionalContextRoute] = []
    resolved_context_keys = {
        (ref.repository_id, ref.identity) for ref, _ in resolved_contexts
    }
    for ref, direct in resolved_contexts:
        context = contexts[(ref.repository_id, ref.identity)]
        context_routes.append(
            FunctionalContextRoute(
                context_id=ref.identity,
                repository_id=ref.repository_id,
                direct=direct,
                coverage=context.coverage,
                inherits=tuple(value.identity for value in context.inherits),
                rule_ids=tuple(value.identity for value in context.rules),
            )
        )
        rule_initial.extend(context.rules)

    dedup_rules: list[FunctionalGraphRef] = []
    seen_rule_keys: set[tuple[str, str]] = set()
    for ref in rule_initial:
        key = (ref.repository_id, ref.identity)
        if key not in seen_rule_keys:
            seen_rule_keys.add(key)
            dedup_rules.append(ref)

    resolved_rules, rule_findings = _resolve_rule_refs(
        tuple(dedup_rules),
        contexts=contexts,
        rules=rules,
        duplicate_rules=duplicate_rules,
        member_repositories=member_repositories,
        available_repositories=available_repositories,
    )
    route_findings.extend(rule_findings)

    rule_routes: list[FunctionalRuleRoute] = []
    valid_rule_refs: list[FunctionalGraphRef] = []
    for ref in resolved_rules:
        key = (ref.repository_id, ref.identity)
        rule = rules[key]
        authority = authority_bindings.get(
            (rule.owner.repository_id, rule.owner.authority_ref)
        )
        if authority is None:
            route_findings.append(
                _finding(
                    FunctionalPyramidFindingReason.INVALID_DECLARATION,
                    "functional rule owner does not resolve to a declared authority binding",
                    "declare the exact canonical authority binding or correct the owner",
                    repository_id=rule.owner.repository_id,
                    rule_id=rule.rule_id,
                )
            )
            continue
        if authority.evidence_ref.repository_id != rule.owner.repository_id:
            route_findings.append(
                _finding(
                    FunctionalPyramidFindingReason.INVALID_DECLARATION,
                    "functional rule authority binding belongs to another repository",
                    "correct the rule owner or canonical authority binding",
                    repository_id=rule.owner.repository_id,
                    rule_id=rule.rule_id,
                )
            )
            continue
        valid_rule_refs.append(ref)
        downstream = frozenset(_downstream_rule_ids(key, rules))
        rule_routes.append(
            FunctionalRuleRoute(
                rule_id=rule.rule_id,
                layer=rule.layer,
                authority=authority,
                governing_rule_ids=tuple(
                    value
                    if isinstance(value, str)
                    else value.identity
                    for value in rule.governing_rule_ids
                ),
                downstream_rule_ids=tuple(sorted(downstream)),
                downstream_context_ids=_downstream_context_ids(
                    downstream | frozenset({rule.rule_id}), contexts
                ),
            )
        )

    rule_routes.sort(key=lambda item: (_layer_rank(item.layer), item.rule_id))

    context_by_key = {
        (item.repository_id, item.context_id): item for item in context_routes
    }
    valid_rule_keys = {
        (ref.repository_id, ref.identity) for ref in valid_rule_refs
    }
    provenance: list[FunctionalRouteProvenance] = []
    for atom_scope, _, relation, portion_direct in portion_records:
        if relation is FunctionalScopeRelation.OUTSIDE_FUNCTIONAL_SCOPE:
            provenance.append(
                FunctionalRouteProvenance(
                    semantic_scope=atom_scope,
                    relation=relation,
                )
            )
            continue

        portion_contexts, _ = _resolve_context_refs(
            portion_direct,
            contexts=contexts,
            rules=rules,
            duplicate_contexts=duplicate_contexts,
            member_repositories=member_repositories,
            available_repositories=available_repositories,
        )
        portion_context_keys = tuple(
            (ref.repository_id, ref.identity)
            for ref, _ in portion_contexts
            if (ref.repository_id, ref.identity) in resolved_context_keys
        )
        portion_rule_refs: list[FunctionalGraphRef] = []
        for key in portion_context_keys:
            portion_rule_refs.extend(contexts[key].rules)
        portion_rules, _ = _resolve_rule_refs(
            tuple(portion_rule_refs),
            contexts=contexts,
            rules=rules,
            duplicate_rules=duplicate_rules,
            member_repositories=member_repositories,
            available_repositories=available_repositories,
        )
        provenance.append(
            FunctionalRouteProvenance(
                semantic_scope=atom_scope,
                relation=relation,
                context_ids=tuple(
                    context_by_key[key].context_id
                    for key in portion_context_keys
                    if key in context_by_key
                ),
                rule_ids=tuple(
                    ref.identity
                    for ref in portion_rules
                    if (ref.repository_id, ref.identity) in valid_rule_keys
                ),
            )
        )

    relations = frozenset(item.relation for item in provenance)
    if relations == frozenset({FunctionalScopeRelation.OUTSIDE_FUNCTIONAL_SCOPE}):
        scope_relation = FunctionalScopeRelation.OUTSIDE_FUNCTIONAL_SCOPE
    elif relations == frozenset({FunctionalScopeRelation.COVERED}):
        scope_relation = FunctionalScopeRelation.COVERED
    elif relations == frozenset({FunctionalScopeRelation.UNCOVERED}):
        scope_relation = FunctionalScopeRelation.UNCOVERED
    else:
        scope_relation = FunctionalScopeRelation.MIXED

    unresolved = _ordered_findings(route_findings)
    status = (
        FunctionalPyramidRouteStatus.RESOLVED
        if not unresolved
        else FunctionalPyramidRouteStatus.UNRESOLVED
    )
    if scope_relation is FunctionalScopeRelation.OUTSIDE_FUNCTIONAL_SCOPE:
        context_routes = []
        rule_routes = []
        unresolved = ()
        status = FunctionalPyramidRouteStatus.RESOLVED

    identity = _route_identity(
        surface,
        semantic_scope,
        tuple(context_routes),
        tuple(valid_rule_refs),
        rules,
    )
    return (
        FunctionalPyramidView(
            pyramid_id=pyramid_id,
            version=version,
            health=health,
            coverage=selected.coverage,
            scope_relation=scope_relation,
            status=status,
            semantic_scope=semantic_scope,
            contexts=tuple(context_routes),
            rules=tuple(rule_routes),
            provenance=tuple(provenance),
            unresolved=unresolved,
        ),
        identity,
    )
