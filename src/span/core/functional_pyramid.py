"""Pure FunctionalScope algebra for Functional Pyramid resolution."""

from __future__ import annotations

import collections.abc as _collections
import hashlib as _hashlib
import json as _json

from span.core import containment as _containment
from span.core.model.functional_pyramid import (
    FunctionalContextDeclaration,
    FunctionalContextRoute,
    FunctionalDocumentDeclaration,
    FunctionalDocumentRef,
    FunctionalDocumentRoute,
    FunctionalGraphRef,
    FunctionalPyramidBootstrap,
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
    FunctionalScope,
    FunctionalScopeRelation,
    FunctionalScopeSelector,
    FunctionalScopeSelectorKind,
)
from span.core.model.investigation import EvidenceRequest, SourceRange
from span.core.model.primitives import (
    AuthorityBinding,
    EvidenceScope,
    _require_non_empty,
)
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
            "missing Functional Pyramid JSON fields: " + ", ".join(sorted(missing))
        )
    if any(not isinstance(key, str) for key in value):
        raise ValueError("Functional Pyramid JSON object keys must be strings")
    return value


def _require_json_array(value: object, name: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be an array")
    return value


def _require_json_string(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    return _require_non_empty(name, value)


def _decode_scope_selector(value: object) -> FunctionalScopeSelector:
    raw = _require_json_object(
        value, frozenset({"kind"}), frozenset({"path", "locator"})
    )
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
    raw = _require_json_object(value, frozenset({"repository_id", "identity"}))
    return FunctionalGraphRef(
        repository_id=_require_json_string(
            raw["repository_id"], "FunctionalGraphRef.repository_id"
        ),
        identity=_require_json_string(raw["identity"], "FunctionalGraphRef.identity"),
    )


def _decode_document_ref(value: object) -> FunctionalDocumentRef:
    raw = _require_json_object(
        value,
        frozenset({"repository_id", "document_ref", "layer"}),
    )
    try:
        layer = FunctionalPyramidLayer(
            _require_json_string(raw["layer"], "document layer")
        )
    except ValueError as exc:
        raise ValueError("unknown Functional Pyramid layer") from exc
    return FunctionalDocumentRef(
        repository_id=_require_json_string(
            raw["repository_id"], "document repository_id"
        ),
        document_ref=_require_json_string(
            raw["document_ref"], "document reference"
        ),
        layer=layer,
    )


def _decode_evidence_request(value: object) -> EvidenceRequest:
    raw = _require_json_object(value, frozenset({"locator"}), frozenset({"ranges"}))
    ranges: list[SourceRange] = []
    for item in _require_json_array(raw.get("ranges", []), "EvidenceRequest.ranges"):
        range_raw = _require_json_object(item, frozenset({"start_line", "end_line"}))
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


def decode_functional_pyramid_bootstrap(text: str) -> FunctionalPyramidBootstrap:
    """Decode the optional navigation bootstrap into the canonical carrier."""

    try:
        value = _json.loads(text)
    except _json.JSONDecodeError as exc:
        raise ValueError("Functional Pyramid bootstrap is not valid JSON") from exc
    raw = _require_json_object(
        value,
        frozenset({"version", "functional_scope", "coverage", "declaration_sources"}),
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
        value, frozenset({"version", "contexts", "documents"})
    )
    if raw["version"] != 2:
        raise ValueError("Functional Pyramid declaration version must be 2")

    contexts: list[FunctionalContextDeclaration] = []
    for item in _require_json_array(raw["contexts"], "declaration contexts"):
        context = _require_json_object(
            item, frozenset({"context_id", "coverage", "inherits", "documents"})
        )
        contexts.append(
            FunctionalContextDeclaration(
                context_id=_require_json_string(context["context_id"], "context_id"),
                coverage=decode_functional_scope(context["coverage"]),
                inherits=tuple(
                    _decode_graph_ref(value)
                    for value in _require_json_array(
                        context["inherits"], "context inherits"
                    )
                ),
                documents=tuple(
                    _decode_document_ref(value)
                    for value in _require_json_array(
                        context["documents"], "context documents"
                    )
                ),
            )
        )

    documents: list[FunctionalDocumentDeclaration] = []
    for item in _require_json_array(raw["documents"], "declaration documents"):
        document = _require_json_object(
            item,
            frozenset({"document", "governing_documents"}),
        )
        governing: list[FunctionalDocumentRef | str] = []
        for value in _require_json_array(
            document["governing_documents"], "document governing_documents"
        ):
            if isinstance(value, str):
                if value != "ROOT":
                    raise ValueError("the only string governing terminal is ROOT")
                governing.append(value)
            else:
                governing.append(_decode_document_ref(value))
        documents.append(
            FunctionalDocumentDeclaration(
                document=_decode_document_ref(document["document"]),
                governing_documents=tuple(governing),
            )
        )

    return FunctionalPyramidDeclaration(
        version=2, contexts=tuple(contexts), documents=tuple(documents)
    )


def _layer_rank(layer: FunctionalPyramidLayer) -> int:
    if layer is FunctionalPyramidLayer.P0:
        return 0
    if layer is FunctionalPyramidLayer.P1:
        return 1
    if layer is FunctionalPyramidLayer.P2S:
        return 2
    if layer is FunctionalPyramidLayer.P2W:
        return 3
    if layer is FunctionalPyramidLayer.P3:
        return 4
    return 5


def _document_sort_key(
    document: FunctionalDocumentRef,
) -> tuple[int, str, str]:
    return (
        _layer_rank(document.layer),
        document.repository_id,
        document.document_ref,
    )


def _governing_edge_is_valid(
    child_layer: FunctionalPyramidLayer,
    parent_layer: FunctionalPyramidLayer,
) -> bool:
    if child_layer is FunctionalPyramidLayer.P1:
        return parent_layer is FunctionalPyramidLayer.P0
    if child_layer is FunctionalPyramidLayer.P2S:
        return parent_layer in (
            FunctionalPyramidLayer.P0,
            FunctionalPyramidLayer.P1,
        )
    if child_layer is FunctionalPyramidLayer.P2W:
        return parent_layer in (
            FunctionalPyramidLayer.P0,
            FunctionalPyramidLayer.P1,
            FunctionalPyramidLayer.P2S,
        )
    if child_layer is FunctionalPyramidLayer.P3:
        return parent_layer in (
            FunctionalPyramidLayer.P0,
            FunctionalPyramidLayer.P1,
            FunctionalPyramidLayer.P2S,
            FunctionalPyramidLayer.P2W,
        )
    if child_layer is FunctionalPyramidLayer.P4:
        return parent_layer in (
            FunctionalPyramidLayer.P0,
            FunctionalPyramidLayer.P1,
            FunctionalPyramidLayer.P2S,
            FunctionalPyramidLayer.P2W,
            FunctionalPyramidLayer.P3,
        )
    return False


def _finding_sort_key(
    finding: FunctionalPyramidFinding,
) -> tuple[str, str, str, str, str, str, str]:
    document = finding.document
    return (
        finding.reason.value,
        finding.repository_id or "",
        finding.context_id or "",
        "" if document is None else document.repository_id,
        "" if document is None else document.document_ref,
        "" if document is None else document.layer.value,
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
    document: FunctionalDocumentRef | None = None,
    declaration_locator: str | None = None,
) -> FunctionalPyramidFinding:
    return FunctionalPyramidFinding(
        reason=reason,
        repository_id=repository_id,
        context_id=context_id,
        document=document,
        declaration_locator=declaration_locator,
        detail=detail,
        recovery=recovery,
    )


def _declaration_indexes(
    declarations: tuple[tuple[str, FunctionalPyramidDeclaration], ...],
) -> tuple[
    dict[tuple[str, str], FunctionalContextDeclaration],
    dict[FunctionalDocumentRef, FunctionalDocumentDeclaration],
    frozenset[str],
    frozenset[FunctionalDocumentRef],
]:
    contexts: dict[tuple[str, str], FunctionalContextDeclaration] = {}
    documents: dict[FunctionalDocumentRef, FunctionalDocumentDeclaration] = {}
    context_owner: dict[str, tuple[str, FunctionalContextDeclaration]] = {}
    duplicate_contexts: set[str] = set()
    duplicate_documents: set[FunctionalDocumentRef] = set()

    for repository_id, declaration in declarations:
        for context in declaration.contexts:
            key = (repository_id, context.context_id)
            previous_context = contexts.get(key)
            if previous_context is not None and previous_context != context:
                duplicate_contexts.add(context.context_id)
            contexts.setdefault(key, context)
            context_owner_entry = context_owner.get(context.context_id)
            if context_owner_entry is None:
                context_owner[context.context_id] = (repository_id, context)
            elif context_owner_entry != (repository_id, context):
                duplicate_contexts.add(context.context_id)

        for document in declaration.documents:
            if document.document.repository_id != repository_id:
                duplicate_documents.add(document.document)
                continue
            previous = documents.get(document.document)
            if previous is not None and previous != document:
                duplicate_documents.add(document.document)
            documents.setdefault(document.document, document)

    return (
        contexts,
        documents,
        frozenset(duplicate_contexts),
        frozenset(duplicate_documents),
    )


def _semantic_atoms(
    surface: SurfaceKey, scope: EvidenceScope
) -> tuple[tuple[EvidenceScope, FunctionalScopeSelector], ...]:
    if surface.kind is SurfaceKind.FILE:
        if any(path != surface.locator for path in scope.paths) or any(
            ref.repository_id != surface.repository_id or ref.locator != surface.locator
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
        symbol_path = _containment.surface_file_locator(path)
        selector = (
            FunctionalScopeSelector(
                FunctionalScopeSelectorKind.SYMBOL,
                path=symbol_path,
                locator=path,
            )
            if symbol_path is not None
            else FunctionalScopeSelector(
                FunctionalScopeSelectorKind.PREFIX,
                path=path,
            )
        )
        atoms.append((EvidenceScope(paths=(path,)), selector))
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
            semantic if functional_scope_selector_contains(member, semantic) else member
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


def _context_ref_finding(
    ref: FunctionalGraphRef,
    *,
    member_repositories: frozenset[str],
    available_repositories: frozenset[str],
    contexts: dict[tuple[str, str], FunctionalContextDeclaration],
) -> FunctionalPyramidFinding | None:
    if ref.repository_id not in member_repositories:
        return _finding(
            FunctionalPyramidFindingReason.INVALID_DECLARATION,
            "graph reference targets a repository outside the active pyramid",
            "correct the repository-qualified declaration edge",
            repository_id=ref.repository_id,
            context_id=ref.identity,
        )
    if ref.repository_id not in available_repositories:
        return _finding(
            FunctionalPyramidFindingReason.REPOSITORY_UNAVAILABLE,
            "referenced Functional Pyramid member is unavailable",
            "restore the named member repository and retry",
            repository_id=ref.repository_id,
            context_id=ref.identity,
        )
    key = (ref.repository_id, ref.identity)
    if key not in contexts:
        return _finding(
            FunctionalPyramidFindingReason.UNKNOWN_CONTEXT,
            "referenced context does not exist in the named available member",
            "correct the context reference or declaration",
            repository_id=ref.repository_id,
            context_id=ref.identity,
        )
    return None


def _document_ref_finding(
    ref: FunctionalDocumentRef,
    *,
    member_repositories: frozenset[str],
    available_repositories: frozenset[str],
    documents: dict[FunctionalDocumentRef, FunctionalDocumentDeclaration],
) -> FunctionalPyramidFinding | None:
    if ref.repository_id not in member_repositories:
        return _finding(
            FunctionalPyramidFindingReason.INVALID_DECLARATION,
            "document reference targets a repository outside the active pyramid",
            "correct the repository-qualified document edge",
            repository_id=ref.repository_id,
            document=ref,
        )
    if ref.repository_id not in available_repositories:
        return _finding(
            FunctionalPyramidFindingReason.REPOSITORY_UNAVAILABLE,
            "referenced Functional Pyramid member is unavailable",
            "restore the named member repository and retry",
            repository_id=ref.repository_id,
            document=ref,
        )
    if ref not in documents:
        return _finding(
            FunctionalPyramidFindingReason.UNKNOWN_DOCUMENT,
            "referenced document placement does not exist in the named member",
            "correct the document reference or declaration",
            repository_id=ref.repository_id,
            document=ref,
        )
    return None


def _availability_findings(
    members: tuple[FunctionalPyramidMemberView, ...],
    available_repositories: frozenset[str],
) -> list[FunctionalPyramidFinding]:
    return [
        _finding(
            FunctionalPyramidFindingReason.REPOSITORY_UNAVAILABLE,
            "active Functional Pyramid member is unavailable",
            "restore the member repository and its declarations",
            repository_id=member.repository_id,
        )
        for member in members
        if member.repository_id not in available_repositories
    ]


def _duplicate_identity_findings(
    duplicate_contexts: frozenset[str],
    duplicate_documents: frozenset[FunctionalDocumentRef],
) -> list[FunctionalPyramidFinding]:
    findings = [
        _finding(
            FunctionalPyramidFindingReason.DUPLICATE_CONTEXT_OWNER,
            "context identity has more than one declaration owner",
            "retain exactly one canonical context declaration",
            context_id=identity,
        )
        for identity in sorted(duplicate_contexts)
    ]
    findings.extend(
        _finding(
            FunctionalPyramidFindingReason.DUPLICATE_DOCUMENT_PLACEMENT,
            "document placement has conflicting declarations",
            "retain exactly one declaration for the document placement",
            repository_id=document.repository_id,
            document=document,
        )
        for document in sorted(
            duplicate_documents,
            key=lambda item: (
                item.repository_id,
                item.document_ref,
                item.layer.value,
            ),
        )
    )
    return findings


def _context_reference_findings(
    contexts: dict[tuple[str, str], FunctionalContextDeclaration],
    documents: dict[FunctionalDocumentRef, FunctionalDocumentDeclaration],
    member_repositories: frozenset[str],
    available_repositories: frozenset[str],
) -> list[FunctionalPyramidFinding]:
    findings: list[FunctionalPyramidFinding] = []
    for context in contexts.values():
        for ref in context.inherits:
            found = _context_ref_finding(
                ref,
                member_repositories=member_repositories,
                available_repositories=available_repositories,
                contexts=contexts,
            )
            if found is not None:
                findings.append(found)
        for ref in context.documents:
            found = _document_ref_finding(
                ref,
                member_repositories=member_repositories,
                available_repositories=available_repositories,
                documents=documents,
            )
            if found is not None:
                findings.append(found)
    return findings


def _context_cycle_findings(
    contexts: dict[tuple[str, str], FunctionalContextDeclaration],
    member_repositories: frozenset[str],
    available_repositories: frozenset[str],
) -> list[FunctionalPyramidFinding]:
    findings: list[FunctionalPyramidFinding] = []
    complete: set[tuple[str, str]] = set()

    def walk(key: tuple[str, str], stack: tuple[tuple[str, str], ...]) -> None:
        if key in stack:
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
        if key in complete:
            return
        current = contexts.get(key)
        if current is None:
            return
        next_stack = stack + (key,)
        for ref in current.inherits:
            target = (ref.repository_id, ref.identity)
            if (
                ref.repository_id in member_repositories
                and ref.repository_id in available_repositories
                and target in contexts
            ):
                walk(target, next_stack)
        complete.add(key)

    for key in contexts:
        walk(key, ())
    return findings


def _document_edge_findings(
    declaration: FunctionalDocumentDeclaration,
    *,
    documents: dict[FunctionalDocumentRef, FunctionalDocumentDeclaration],
    member_repositories: frozenset[str],
    available_repositories: frozenset[str],
) -> list[FunctionalPyramidFinding]:
    document = declaration.document
    if document.layer is FunctionalPyramidLayer.P0:
        if declaration.governing_documents == ("ROOT",):
            return []
        return [
            _finding(
                FunctionalPyramidFindingReason.INVALID_GOVERNING_EDGE,
                "P0 document placement must be governed by ROOT exactly",
                "declare ROOT as the sole P0 governing terminal",
                repository_id=document.repository_id,
                document=document,
            )
        ]

    if not declaration.governing_documents:
        return [
            _finding(
                FunctionalPyramidFindingReason.UNRESOLVED_DOCUMENT_PARENT,
                "non-P0 document placement has no governing document",
                "declare at least one valid higher governing document",
                repository_id=document.repository_id,
                document=document,
            )
        ]

    findings: list[FunctionalPyramidFinding] = []
    for parent in declaration.governing_documents:
        if isinstance(parent, str):
            findings.append(
                _finding(
                    FunctionalPyramidFindingReason.INVALID_GOVERNING_EDGE,
                    "ROOT may govern only a P0 document placement",
                    "replace ROOT with a valid higher governing document",
                    repository_id=document.repository_id,
                    document=document,
                )
            )
            continue
        found = _document_ref_finding(
            parent,
            member_repositories=member_repositories,
            available_repositories=available_repositories,
            documents=documents,
        )
        if found is not None:
            findings.append(found)
            continue
        target = documents[parent].document
        if not _governing_edge_is_valid(document.layer, target.layer):
            findings.append(
                _finding(
                    FunctionalPyramidFindingReason.INVALID_GOVERNING_EDGE,
                    "governing edge violates the Functional Pyramid layer relation",
                    "point the edge to a valid higher governing document",
                    repository_id=document.repository_id,
                    document=document,
                )
            )
    return findings


def _document_cycle_findings(
    documents: dict[FunctionalDocumentRef, FunctionalDocumentDeclaration],
    member_repositories: frozenset[str],
    available_repositories: frozenset[str],
) -> list[FunctionalPyramidFinding]:
    findings: list[FunctionalPyramidFinding] = []
    complete: set[FunctionalDocumentRef] = set()

    def walk(
        document: FunctionalDocumentRef,
        stack: tuple[FunctionalDocumentRef, ...],
    ) -> None:
        if document in stack:
            findings.append(
                _finding(
                    FunctionalPyramidFindingReason.DOCUMENT_CYCLE,
                    "governing documents contain a cycle",
                    "remove the cyclic governing edge",
                    repository_id=document.repository_id,
                    document=document,
                )
            )
            return
        if document in complete:
            return
        current = documents.get(document)
        if current is None:
            return
        next_stack = stack + (document,)
        for parent in current.governing_documents:
            if not isinstance(parent, FunctionalDocumentRef):
                continue
            if (
                parent.repository_id in member_repositories
                and parent.repository_id in available_repositories
                and parent in documents
            ):
                walk(parent, next_stack)
        complete.add(document)

    for document in documents:
        walk(document, ())
    return findings


def _complete_coverage_findings(
    members: tuple[FunctionalPyramidMemberView, ...],
    contexts: dict[tuple[str, str], FunctionalContextDeclaration],
) -> list[FunctionalPyramidFinding]:
    findings: list[FunctionalPyramidFinding] = []
    for member in members:
        if member.coverage is not FunctionalPyramidCoverage.COMPLETE:
            continue
        coverage = tuple(
            context.coverage
            for (repository_id, _), context in contexts.items()
            if repository_id == member.repository_id
        )
        if not functional_scope_uncovered(member.functional_scope, coverage):
            continue
        findings.append(
            _finding(
                FunctionalPyramidFindingReason.UNCOVERED_PATH,
                "COMPLETE member FunctionalScope has uncovered selectors",
                "add applicable Functional Context coverage or revise coverage mode",
                repository_id=member.repository_id,
            )
        )
    return findings


def _graph_structural_findings(
    members: tuple[FunctionalPyramidMemberView, ...],
    declarations: tuple[tuple[str, FunctionalPyramidDeclaration], ...],
    available_repositories: frozenset[str],
    declaration_findings: tuple[FunctionalPyramidFinding, ...] = (),
) -> tuple[FunctionalPyramidFinding, ...]:
    contexts, documents, duplicate_contexts, duplicate_documents = (
        _declaration_indexes(declarations)
    )
    member_repositories = frozenset(member.repository_id for member in members)
    findings: list[FunctionalPyramidFinding] = list(declaration_findings)
    findings.extend(_availability_findings(members, available_repositories))
    findings.extend(
        _duplicate_identity_findings(duplicate_contexts, duplicate_documents)
    )
    findings.extend(
        _context_reference_findings(
            contexts, documents, member_repositories, available_repositories
        )
    )
    findings.extend(
        _context_cycle_findings(contexts, member_repositories, available_repositories)
    )
    for declaration in documents.values():
        findings.extend(
            _document_edge_findings(
                declaration,
                documents=documents,
                member_repositories=member_repositories,
                available_repositories=available_repositories,
            )
        )
    findings.extend(
        _document_cycle_findings(
            documents, member_repositories, available_repositories
        )
    )
    findings.extend(_complete_coverage_findings(members, contexts))
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
        if owner_repository != repository_id:
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
    duplicate_contexts: frozenset[str],
    member_repositories: frozenset[str],
    available_repositories: frozenset[str],
) -> tuple[
    tuple[tuple[FunctionalGraphRef, bool], ...],
    tuple[FunctionalPyramidFinding, ...],
]:
    ordered: list[tuple[FunctionalGraphRef, bool]] = []
    emitted: set[tuple[str, str]] = set()
    valid_direct: list[FunctionalGraphRef] = []
    findings: list[FunctionalPyramidFinding] = []

    def validate(ref: FunctionalGraphRef) -> bool:
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
            return False
        ref_finding = _context_ref_finding(
            ref,
            member_repositories=member_repositories,
            available_repositories=available_repositories,
            contexts=contexts,
        )
        if ref_finding is not None:
            findings.append(ref_finding)
            return False
        return True

    # FD-72: every direct context precedes every inherited context.
    for ref in direct_refs:
        key = (ref.repository_id, ref.identity)
        if key in emitted or not validate(ref):
            continue
        emitted.add(key)
        valid_direct.append(ref)
        ordered.append((ref, True))

    def visit_inherited(
        ref: FunctionalGraphRef, stack: tuple[tuple[str, str], ...]
    ) -> None:
        key = (ref.repository_id, ref.identity)
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
        if not validate(ref):
            return
        if key not in emitted:
            emitted.add(key)
            ordered.append((ref, False))
        context = contexts[key]
        for inherited in context.inherits:
            visit_inherited(inherited, stack + (key,))

    for ref in valid_direct:
        key = (ref.repository_id, ref.identity)
        for inherited in contexts[key].inherits:
            visit_inherited(inherited, (key,))

    return tuple(ordered), _ordered_findings(findings)


def _resolve_document_refs(
    initial_refs: tuple[FunctionalDocumentRef, ...],
    *,
    documents: dict[FunctionalDocumentRef, FunctionalDocumentDeclaration],
    duplicate_documents: frozenset[FunctionalDocumentRef],
    member_repositories: frozenset[str],
    available_repositories: frozenset[str],
) -> tuple[
    tuple[FunctionalDocumentRef, ...],
    tuple[FunctionalPyramidFinding, ...],
]:
    emitted: list[FunctionalDocumentRef] = []
    seen: set[FunctionalDocumentRef] = set()
    active: set[FunctionalDocumentRef] = set()
    findings: list[FunctionalPyramidFinding] = []

    def visit(ref: FunctionalDocumentRef) -> None:
        if ref in duplicate_documents:
            findings.append(
                _finding(
                    FunctionalPyramidFindingReason.DUPLICATE_DOCUMENT_PLACEMENT,
                    "document placement has conflicting declarations",
                    "retain exactly one declaration for the document placement",
                    repository_id=ref.repository_id,
                    document=ref,
                )
            )
            return
        ref_finding = _document_ref_finding(
            ref,
            member_repositories=member_repositories,
            available_repositories=available_repositories,
            documents=documents,
        )
        if ref_finding is not None:
            findings.append(ref_finding)
            return
        if ref in active:
            findings.append(
                _finding(
                    FunctionalPyramidFindingReason.DOCUMENT_CYCLE,
                    "governing documents contain a cycle",
                    "remove the cyclic governing edge",
                    repository_id=ref.repository_id,
                    document=ref,
                )
            )
            return
        if ref in seen:
            return
        seen.add(ref)
        active.add(ref)
        emitted.append(ref)
        declaration = documents[ref]
        if ref.layer is FunctionalPyramidLayer.P0:
            if declaration.governing_documents != ("ROOT",):
                findings.append(
                    _finding(
                        FunctionalPyramidFindingReason.INVALID_GOVERNING_EDGE,
                        "P0 document placement must be governed by ROOT exactly",
                        "declare ROOT as the sole P0 governing terminal",
                        repository_id=ref.repository_id,
                        document=ref,
                    )
                )
        elif not declaration.governing_documents:
            findings.append(
                _finding(
                    FunctionalPyramidFindingReason.UNRESOLVED_DOCUMENT_PARENT,
                    "non-P0 document placement has no governing document",
                    "declare at least one valid higher governing document",
                    repository_id=ref.repository_id,
                    document=ref,
                )
            )
        for parent in declaration.governing_documents:
            if isinstance(parent, str):
                if ref.layer is not FunctionalPyramidLayer.P0:
                    findings.append(
                        _finding(
                            FunctionalPyramidFindingReason.INVALID_GOVERNING_EDGE,
                            "ROOT may govern only a P0 document placement",
                            "replace ROOT with a valid higher governing document",
                            repository_id=ref.repository_id,
                            document=ref,
                        )
                    )
                continue
            parent_finding = _document_ref_finding(
                parent,
                member_repositories=member_repositories,
                available_repositories=available_repositories,
                documents=documents,
            )
            if parent_finding is not None:
                findings.append(parent_finding)
                continue
            if not _governing_edge_is_valid(ref.layer, parent.layer):
                findings.append(
                    _finding(
                        FunctionalPyramidFindingReason.INVALID_GOVERNING_EDGE,
                        "governing edge violates the Functional Pyramid layer relation",
                        "point the edge to a valid higher governing document",
                        repository_id=ref.repository_id,
                        document=ref,
                    )
                )
                continue
            visit(parent)
        active.remove(ref)

    for ref in initial_refs:
        visit(ref)
    return tuple(emitted), _ordered_findings(findings)


def _downstream_documents(
    document: FunctionalDocumentRef,
    documents: dict[FunctionalDocumentRef, FunctionalDocumentDeclaration],
) -> tuple[FunctionalDocumentRef, ...]:
    found: set[FunctionalDocumentRef] = set()
    frontier = [document]
    while frontier:
        current = frontier.pop()
        for candidate, declaration in documents.items():
            if candidate in found or candidate == document:
                continue
            if current in declaration.governing_documents:
                found.add(candidate)
                frontier.append(candidate)
    return tuple(sorted(found, key=_document_sort_key))


def _downstream_context_ids(
    document_refs: frozenset[FunctionalDocumentRef],
    contexts: dict[tuple[str, str], FunctionalContextDeclaration],
) -> tuple[str, ...]:
    found: set[tuple[str, str]] = {
        key
        for key, context in contexts.items()
        if any(ref in document_refs for ref in context.documents)
    }
    frontier = list(found)
    while frontier:
        current = frontier.pop()
        for candidate_key, context in contexts.items():
            if candidate_key in found:
                continue
            if any(
                (inherited.repository_id, inherited.identity) == current
                for inherited in context.inherits
            ):
                found.add(candidate_key)
                frontier.append(candidate_key)
    return tuple(sorted(identity for _, identity in found))


def _route_identity(
    repository_id: str,
    semantic_scope: EvidenceScope | None,
    directory: str | None,
    contexts: tuple[FunctionalContextRoute, ...],
    document_refs: tuple[FunctionalDocumentRef, ...],
    documents: dict[FunctionalDocumentRef, FunctionalDocumentDeclaration],
) -> FunctionalRouteIdentity:
    payload = {
        "selection": {
            "directory": directory,
            "paths": () if semantic_scope is None else tuple(semantic_scope.paths),
            "refs": [
                (
                    ref.repository_id,
                    ref.locator,
                    ref.section_or_span,
                )
                for ref in (() if semantic_scope is None else semantic_scope.evidence_refs)
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
                [
                    (ref.repository_id, ref.document_ref, ref.layer.value)
                    for ref in context.documents
                ],
            )
            for context in contexts
        ],
        "documents": [
            (
                ref.repository_id,
                ref.document_ref,
                ref.layer.value,
                [
                    (
                        parent
                        if isinstance(parent, str)
                        else (
                            parent.repository_id,
                            parent.document_ref,
                            parent.layer.value,
                        )
                    )
                    for parent in documents[ref].governing_documents
                ],
            )
            for ref in document_refs
            if ref in documents
        ],
        "members": sorted(
            {repository_id}
            | {context.repository_id for context in contexts}
            | {ref.repository_id for ref in document_refs}
        ),
    }
    encoded = _json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return FunctionalRouteIdentity(_hashlib.sha256(encoded).hexdigest())


def _unique_graph_refs(
    refs: _collections.Iterable[FunctionalGraphRef],
) -> tuple[FunctionalGraphRef, ...]:
    result: list[FunctionalGraphRef] = []
    seen: set[tuple[str, str]] = set()
    for ref in refs:
        key = (ref.repository_id, ref.identity)
        if key in seen:
            continue
        seen.add(key)
        result.append(ref)
    return tuple(result)


def _semantic_portions(
    surface: SurfaceKey,
    semantic_scope: EvidenceScope,
    member_scope: FunctionalScope,
    contexts: dict[tuple[str, str], FunctionalContextDeclaration],
    duplicate_contexts: frozenset[str],
) -> tuple[
    tuple[
        tuple[
            EvidenceScope,
            FunctionalScopeSelector | None,
            FunctionalScopeRelation,
            tuple[FunctionalGraphRef, ...],
        ],
        ...,
    ],
    tuple[FunctionalGraphRef, ...],
    tuple[FunctionalPyramidFinding, ...],
]:
    portions: list[
        tuple[
            EvidenceScope,
            FunctionalScopeSelector | None,
            FunctionalScopeRelation,
            tuple[FunctionalGraphRef, ...],
        ]
    ] = []
    direct_refs: list[FunctionalGraphRef] = []
    findings: list[FunctionalPyramidFinding] = []

    for atom_scope, semantic_selector in _semantic_atoms(surface, semantic_scope):
        intersections = _intersection_selectors(semantic_selector, member_scope)
        if not intersections:
            portions.append(
                (
                    atom_scope,
                    None,
                    FunctionalScopeRelation.OUTSIDE_FUNCTIONAL_SCOPE,
                    (),
                )
            )
            continue

        if _semantic_has_outside_remainder(semantic_selector, member_scope):
            portions.append(
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
            portions.append((atom_scope, intersection, relation, direct))
            direct_refs.extend(direct)
            if direct:
                continue
            findings.append(
                _finding(
                    FunctionalPyramidFindingReason.UNCOVERED_PATH,
                    "functional semantic scope has no applicable context",
                    "declare applicable Functional Context coverage",
                    repository_id=surface.repository_id,
                )
            )

    return tuple(portions), _unique_graph_refs(direct_refs), _ordered_findings(findings)


def _context_projection(
    resolved_contexts: tuple[tuple[FunctionalGraphRef, bool], ...],
    contexts: dict[tuple[str, str], FunctionalContextDeclaration],
) -> tuple[
    tuple[FunctionalContextRoute, ...],
    tuple[FunctionalDocumentRef, ...],
    frozenset[tuple[str, str]],
]:
    routes: list[FunctionalContextRoute] = []
    document_refs: list[FunctionalDocumentRef] = []
    keys: set[tuple[str, str]] = set()
    for ref, direct in resolved_contexts:
        key = (ref.repository_id, ref.identity)
        keys.add(key)
        context = contexts[key]
        routes.append(
            FunctionalContextRoute(
                context_id=ref.identity,
                repository_id=ref.repository_id,
                direct=direct,
                coverage=context.coverage,
                inherits=tuple(value.identity for value in context.inherits),
                documents=context.documents,
            )
        )
        document_refs.extend(context.documents)
    return tuple(routes), tuple(dict.fromkeys(document_refs)), frozenset(keys)


def _canonical_owner_document_refs(
    *,
    repository_id: str,
    semantic_scope: EvidenceScope,
    documents: dict[FunctionalDocumentRef, FunctionalDocumentDeclaration],
    authority_bindings: _collections.Mapping[tuple[str, str], AuthorityBinding],
) -> tuple[FunctionalDocumentRef, ...]:
    """Seed FD-88 reverse navigation from an exact canonical owner selection."""
    exact_locators = set(semantic_scope.paths)
    exact_locators.update(ref.locator for ref in semantic_scope.evidence_refs)
    if not exact_locators:
        return ()

    refs: list[FunctionalDocumentRef] = []
    for document in documents:
        if document.repository_id != repository_id:
            continue
        authority = authority_bindings.get(
            (document.repository_id, document.document_ref)
        )
        if authority is None:
            continue
        if authority.evidence_ref.locator not in exact_locators:
            continue
        refs.append(document)
    return tuple(dict.fromkeys(refs))


def _document_projection(
    resolved_documents: tuple[FunctionalDocumentRef, ...],
    *,
    documents: dict[FunctionalDocumentRef, FunctionalDocumentDeclaration],
    contexts: dict[tuple[str, str], FunctionalContextDeclaration],
    authority_bindings: _collections.Mapping[tuple[str, str], AuthorityBinding],
) -> tuple[
    tuple[FunctionalDocumentRoute, ...],
    tuple[FunctionalDocumentRef, ...],
    tuple[FunctionalPyramidFinding, ...],
]:
    routes: list[FunctionalDocumentRoute] = []
    valid_refs: list[FunctionalDocumentRef] = []
    findings: list[FunctionalPyramidFinding] = []

    for ref in resolved_documents:
        declaration = documents[ref]
        authority = authority_bindings.get(
            (ref.repository_id, ref.document_ref)
        )
        if authority is None:
            findings.append(
                _finding(
                    FunctionalPyramidFindingReason.INVALID_DECLARATION,
                    "canonical document does not resolve to an authority binding",
                    "declare the canonical document authority or correct the reference",
                    repository_id=ref.repository_id,
                    document=ref,
                )
            )
            continue
        if authority.evidence_ref.repository_id != ref.repository_id:
            findings.append(
                _finding(
                    FunctionalPyramidFindingReason.INVALID_DECLARATION,
                    "canonical document binding belongs to another repository",
                    "correct the document reference or authority binding",
                    repository_id=ref.repository_id,
                    document=ref,
                )
            )
            continue

        valid_refs.append(ref)
        downstream = frozenset(_downstream_documents(ref, documents))
        routes.append(
            FunctionalDocumentRoute(
                document=ref,
                authority=authority,
                governing_documents=declaration.governing_documents,
                downstream_documents=tuple(sorted(downstream, key=_document_sort_key)),
                downstream_context_ids=_downstream_context_ids(
                    downstream | frozenset({ref}), contexts
                ),
            )
        )

    routes.sort(key=lambda item: _document_sort_key(item.document))
    return tuple(routes), tuple(valid_refs), _ordered_findings(findings)


def _provenance_projection(
    portions: tuple[
        tuple[
            EvidenceScope,
            FunctionalScopeSelector | None,
            FunctionalScopeRelation,
            tuple[FunctionalGraphRef, ...],
        ],
        ...,
    ],
    *,
    contexts: dict[tuple[str, str], FunctionalContextDeclaration],
    rules: dict[tuple[str, str], FunctionalRuleDeclaration],
    duplicate_contexts: frozenset[str],
    duplicate_rules: frozenset[str],
    member_repositories: frozenset[str],
    available_repositories: frozenset[str],
    resolved_context_keys: frozenset[tuple[str, str]],
    resolved_rule_keys: frozenset[tuple[str, str]],
) -> tuple[FunctionalRouteProvenance, ...]:
    projection: list[FunctionalRouteProvenance] = []
    for atom_scope, _, relation, direct_refs in portions:
        if relation is FunctionalScopeRelation.OUTSIDE_FUNCTIONAL_SCOPE:
            projection.append(
                FunctionalRouteProvenance(
                    semantic_scope=atom_scope,
                    relation=relation,
                )
            )
            continue

        portion_contexts, _ = _resolve_context_refs(
            direct_refs,
            contexts=contexts,
            rules=rules,
            duplicate_contexts=duplicate_contexts,
            member_repositories=member_repositories,
            available_repositories=available_repositories,
        )
        context_keys = tuple(
            (ref.repository_id, ref.identity)
            for ref, _ in portion_contexts
            if (ref.repository_id, ref.identity) in resolved_context_keys
        )
        initial_rules = (ref for key in context_keys for ref in contexts[key].rules)
        portion_rules, _ = _resolve_rule_refs(
            _unique_graph_refs(initial_rules),
            contexts=contexts,
            rules=rules,
            duplicate_rules=duplicate_rules,
            member_repositories=member_repositories,
            available_repositories=available_repositories,
        )
        projection.append(
            FunctionalRouteProvenance(
                semantic_scope=atom_scope,
                relation=relation,
                context_ids=tuple(identity for _, identity in context_keys),
                rule_ids=tuple(
                    ref.identity
                    for ref in portion_rules
                    if (ref.repository_id, ref.identity) in resolved_rule_keys
                ),
            )
        )
    return tuple(projection)


def _scope_relation(
    provenance: tuple[FunctionalRouteProvenance, ...],
) -> FunctionalScopeRelation:
    relations = frozenset(item.relation for item in provenance)
    if relations == frozenset({FunctionalScopeRelation.OUTSIDE_FUNCTIONAL_SCOPE}):
        return FunctionalScopeRelation.OUTSIDE_FUNCTIONAL_SCOPE
    if relations == frozenset({FunctionalScopeRelation.COVERED}):
        return FunctionalScopeRelation.COVERED
    if relations == frozenset({FunctionalScopeRelation.UNCOVERED}):
        return FunctionalScopeRelation.UNCOVERED
    return FunctionalScopeRelation.MIXED


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

    health, _ = evaluate_functional_pyramid_health(
        members, declarations, available_repositories, declaration_findings
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

    portions, direct_refs, scope_findings = _semantic_portions(
        surface,
        semantic_scope,
        selected.functional_scope,
        contexts,
        duplicate_contexts,
    )
    route_findings.extend(scope_findings)

    resolved_contexts, context_findings = _resolve_context_refs(
        direct_refs,
        contexts=contexts,
        rules=rules,
        duplicate_contexts=duplicate_contexts,
        member_repositories=member_repositories,
        available_repositories=available_repositories,
    )
    route_findings.extend(context_findings)
    context_routes, initial_rules, context_keys = _context_projection(
        resolved_contexts, contexts
    )
    owner_rules = _canonical_owner_rule_refs(
        surface=surface,
        semantic_scope=semantic_scope,
        rules=rules,
        authority_bindings=authority_bindings,
    )

    resolved_rules, rule_findings = _resolve_rule_refs(
        _unique_graph_refs((*initial_rules, *owner_rules)),
        contexts=contexts,
        rules=rules,
        duplicate_rules=duplicate_rules,
        member_repositories=member_repositories,
        available_repositories=available_repositories,
    )
    route_findings.extend(rule_findings)
    rule_routes, valid_rule_refs, authority_findings = _rule_projection(
        resolved_rules,
        rules=rules,
        contexts=contexts,
        authority_bindings=authority_bindings,
    )
    route_findings.extend(authority_findings)

    resolved_rule_keys = frozenset(
        (ref.repository_id, ref.identity) for ref in resolved_rules
    )
    provenance = _provenance_projection(
        portions,
        contexts=contexts,
        rules=rules,
        duplicate_contexts=duplicate_contexts,
        duplicate_rules=duplicate_rules,
        member_repositories=member_repositories,
        available_repositories=available_repositories,
        resolved_context_keys=context_keys,
        resolved_rule_keys=resolved_rule_keys,
    )
    relation = _scope_relation(provenance)
    unresolved = _ordered_findings(route_findings)
    status = (
        FunctionalPyramidRouteStatus.RESOLVED
        if not unresolved
        else FunctionalPyramidRouteStatus.UNRESOLVED
    )
    if relation is FunctionalScopeRelation.OUTSIDE_FUNCTIONAL_SCOPE:
        context_routes = ()
        rule_routes = ()
        unresolved = ()
        status = FunctionalPyramidRouteStatus.RESOLVED

    identity = _route_identity(
        surface, semantic_scope, context_routes, resolved_rules, rules
    )
    return (
        FunctionalPyramidView(
            pyramid_id=pyramid_id,
            version=version,
            health=health,
            coverage=selected.coverage,
            scope_relation=relation,
            status=status,
            semantic_scope=semantic_scope,
            contexts=context_routes,
            rules=rule_routes,
            provenance=provenance,
            unresolved=unresolved,
        ),
        identity,
    )
