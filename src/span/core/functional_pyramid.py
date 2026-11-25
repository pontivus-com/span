"""Pure document-placement algebra and Functional Pyramid resolution."""

from __future__ import annotations

import collections as _collections
import hashlib as _hashlib
import json as _json
import posixpath as _posixpath

from span.core import containment as _containment
from span.core.model.functional_pyramid import (
    FunctionalDirectoryScope,
    FunctionalDocumentDeclaration,
    FunctionalDocumentPlacement,
    FunctionalDocumentRef,
    FunctionalDocumentRoute,
    FunctionalPyramidBootstrap,
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
)
from span.core.model.investigation import EvidenceRequest
from span.core.model.primitives import (
    AuthorityBinding,
    EvidenceScope,
    SourceRange,
    _require_non_empty,
)
from span.core.model.surfaces import SurfaceKey, SurfaceKind

_LAYER_ORDER = (
    FunctionalPyramidLayer.P0,
    FunctionalPyramidLayer.P1,
    FunctionalPyramidLayer.P2S,
    FunctionalPyramidLayer.P2W,
    FunctionalPyramidLayer.P3,
    FunctionalPyramidLayer.P4,
)
_LAYER_RANK = {layer: index for index, layer in enumerate(_LAYER_ORDER)}


def normalize_directory_scope(value: str) -> str:
    """Validate and return one canonical repository-relative directory scope."""
    return FunctionalDirectoryScope(value).value


def directory_scope_contains(outer: str, inner: str) -> bool:
    """Return whether directory scope outer contains inner."""
    outer = normalize_directory_scope(outer)
    inner = normalize_directory_scope(inner)
    return outer == "." or inner == outer or inner.startswith(outer + "/")


def directory_scope_intersects(left: str, right: str) -> bool:
    """Directory scopes intersect exactly when one contains the other."""
    return directory_scope_contains(left, right) or directory_scope_contains(right, left)


def _placement_sort_key(
    placement: FunctionalDocumentPlacement,
) -> tuple[int, str, str, str, str]:
    return (
        _LAYER_RANK[placement.document.layer],
        placement.declaring_repository_id,
        placement.document.repository_id,
        placement.document.document_ref,
        placement.scope,
    )


def _finding_sort_key(
    finding: FunctionalPyramidFinding,
) -> tuple[str, str, tuple[int, str, str, str, str], str, str, str]:
    placement_key = (
        (-1, "", "", "", "")
        if finding.placement is None
        else _placement_sort_key(finding.placement)
    )
    return (
        finding.reason.value,
        finding.repository_id or "",
        placement_key,
        finding.directory or "",
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
    declaration_locator: str | None = None,
    placement: FunctionalDocumentPlacement | None = None,
    directory: str | None = None,
) -> FunctionalPyramidFinding:
    return FunctionalPyramidFinding(
        reason=reason,
        repository_id=repository_id,
        declaration_locator=declaration_locator,
        placement=placement,
        directory=directory,
        detail=detail,
        recovery=recovery,
    )


def _require_json_object(
    value: object, required: frozenset[str], optional: frozenset[str] = frozenset()
) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError("Functional Pyramid JSON value must be an object")
    if any(not isinstance(key, str) for key in value):
        raise ValueError("Functional Pyramid JSON object keys must be strings")
    keys = frozenset(value)
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
    return value


def _require_json_array(value: object, name: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be an array")
    return value


def _require_json_string(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    return _require_non_empty(name, value)


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
    """Decode the optional Version-2 initialization bootstrap."""
    try:
        value = _json.loads(text)
    except _json.JSONDecodeError as exc:
        raise ValueError("Functional Pyramid bootstrap is not valid JSON") from exc
    raw = _require_json_object(value, frozenset({"version", "declaration_sources"}))
    if raw["version"] != 2:
        raise ValueError("Functional Pyramid bootstrap version must be 2")
    sources = tuple(
        _decode_evidence_request(item)
        for item in _require_json_array(
            raw["declaration_sources"], "bootstrap declaration_sources"
        )
    )
    return FunctionalPyramidBootstrap(version=2, declaration_sources=sources)


def _decode_document_ref(value: object) -> FunctionalDocumentRef:
    raw = _require_json_object(
        value, frozenset({"repository_id", "document_ref", "layer"})
    )
    try:
        layer = FunctionalPyramidLayer(
            _require_json_string(raw["layer"], "FunctionalDocumentRef.layer")
        )
    except ValueError as exc:
        raise ValueError("unknown Functional Pyramid layer") from exc
    return FunctionalDocumentRef(
        repository_id=_require_json_string(
            raw["repository_id"], "FunctionalDocumentRef.repository_id"
        ),
        document_ref=_require_json_string(
            raw["document_ref"], "FunctionalDocumentRef.document_ref"
        ),
        layer=layer,
    )


def _decode_placement(
    value: object,
    *,
    declaring_repository_id: str,
    declaration_locator: str,
    allow_explicit_owner: bool,
) -> tuple[FunctionalDocumentPlacement | None, FunctionalPyramidFinding | None]:
    required = (
        {"declaring_repository_id", "document", "scope"}
        if allow_explicit_owner
        else {"document", "scope"}
    )
    raw = _require_json_object(value, frozenset(required))
    explicit_owner = raw.get("declaring_repository_id")
    if allow_explicit_owner:
        declaring_repository_id = _require_json_string(
            explicit_owner,
            "FunctionalDocumentPlacement.declaring_repository_id",
        )
    document = _decode_document_ref(raw["document"])
    scope = _require_json_string(raw["scope"], "FunctionalDocumentPlacement.scope")
    try:
        normalized = normalize_directory_scope(scope)
    except ValueError:
        return None, _finding(
            FunctionalPyramidFindingReason.INVALID_PLACEMENT_SCOPE,
            f"placement scope {scope!r} is not canonical repository-relative directory scope",
            "declare '.' or a canonical POSIX repository-relative directory scope",
            repository_id=declaring_repository_id,
            declaration_locator=declaration_locator,
        )
    return (
        FunctionalDocumentPlacement(
            declaring_repository_id=declaring_repository_id,
            document=document,
            scope=normalized,
        ),
        None,
    )


def decode_functional_pyramid_declaration(
    text: str,
    *,
    repository_id: str,
    declaration_locator: str,
) -> tuple[FunctionalPyramidDeclaration, tuple[FunctionalPyramidFinding, ...]]:
    """Strictly decode one Version-2 declaration and retain scope graph findings.

    JSON/version/structural failures raise ValueError and are owned by the
    declaration-source validation path. Once a placement's non-scope coordinates
    are recoverable, a non-canonical scope is returned exclusively as
    INVALID_PLACEMENT_SCOPE and no invalid canonical placement is built.
    """
    try:
        value = _json.loads(text)
    except _json.JSONDecodeError as exc:
        raise ValueError("Functional Pyramid declaration is not valid JSON") from exc
    raw = _require_json_object(value, frozenset({"version", "placements"}))
    if raw["version"] != 2:
        raise ValueError("Functional Pyramid declaration version must be 2")

    declarations: list[FunctionalDocumentDeclaration] = []
    findings: list[FunctionalPyramidFinding] = []
    for item in _require_json_array(raw["placements"], "declaration placements"):
        entry = _require_json_object(
            item, frozenset({"document", "scope", "governing_placements"})
        )
        placement, placement_finding = _decode_placement(
            {"document": entry["document"], "scope": entry["scope"]},
            declaring_repository_id=repository_id,
            declaration_locator=declaration_locator,
            allow_explicit_owner=False,
        )
        if placement_finding is not None:
            findings.append(placement_finding)
            continue
        assert placement is not None

        governing: list[FunctionalDocumentPlacement | str] = []
        invalid_parent_scope = False
        for parent_raw in _require_json_array(
            entry["governing_placements"], "placement governing_placements"
        ):
            if isinstance(parent_raw, str):
                if parent_raw != "ROOT":
                    raise ValueError("the only string governing terminal is ROOT")
                governing.append("ROOT")
                continue
            parent, parent_finding = _decode_placement(
                parent_raw,
                declaring_repository_id=repository_id,
                declaration_locator=declaration_locator,
                allow_explicit_owner=True,
            )
            if parent_finding is not None:
                findings.append(parent_finding)
                invalid_parent_scope = True
                continue
            assert parent is not None
            governing.append(parent)
        if invalid_parent_scope and not governing:
            continue
        declarations.append(
            FunctionalDocumentDeclaration(
                placement=placement,
                governing_placements=tuple(governing),
            )
        )

    return (
        FunctionalPyramidDeclaration(version=2, placements=tuple(declarations)),
        _ordered_findings(findings),
    )


def _governing_layer_is_valid(
    child: FunctionalPyramidLayer, parent: FunctionalPyramidLayer
) -> bool:
    if child is FunctionalPyramidLayer.P0:
        return False
    if child is FunctionalPyramidLayer.P1:
        return parent is FunctionalPyramidLayer.P0
    if child is FunctionalPyramidLayer.P2S:
        return parent in (FunctionalPyramidLayer.P0, FunctionalPyramidLayer.P1)
    if child is FunctionalPyramidLayer.P2W:
        return parent in (
            FunctionalPyramidLayer.P0,
            FunctionalPyramidLayer.P1,
            FunctionalPyramidLayer.P2S,
        )
    if child is FunctionalPyramidLayer.P3:
        return parent in (
            FunctionalPyramidLayer.P0,
            FunctionalPyramidLayer.P1,
            FunctionalPyramidLayer.P2S,
            FunctionalPyramidLayer.P2W,
        )
    return parent in (
        FunctionalPyramidLayer.P0,
        FunctionalPyramidLayer.P1,
        FunctionalPyramidLayer.P2S,
        FunctionalPyramidLayer.P2W,
        FunctionalPyramidLayer.P3,
    )


def _indexes(
    declarations: tuple[tuple[str, FunctionalPyramidDeclaration], ...],
) -> tuple[
    dict[FunctionalDocumentPlacement, FunctionalDocumentDeclaration],
    tuple[FunctionalPyramidFinding, ...],
]:
    by_placement: dict[FunctionalDocumentPlacement, FunctionalDocumentDeclaration] = {}
    findings: list[FunctionalPyramidFinding] = []
    for repository_id, declaration in declarations:
        for entry in declaration.placements:
            placement = entry.placement
            if placement.declaring_repository_id != repository_id:
                findings.append(
                    _finding(
                        FunctionalPyramidFindingReason.INVALID_DECLARATION,
                        "placement owner does not match the repository-owned declaration",
                        "correct the declaration placement owner",
                        repository_id=repository_id,
                        placement=placement,
                    )
                )
                continue
            previous = by_placement.get(placement)
            if previous is not None and previous != entry:
                findings.append(
                    _finding(
                        FunctionalPyramidFindingReason.DUPLICATE_DOCUMENT_PLACEMENT,
                        "one placement identity has conflicting governing relationships",
                        "retain one canonical declaration for the placement identity",
                        repository_id=repository_id,
                        placement=placement,
                    )
                )
                continue
            by_placement.setdefault(placement, entry)
    return by_placement, _ordered_findings(findings)


def _graph_findings(
    members: tuple[FunctionalPyramidMemberView, ...],
    declarations: tuple[tuple[str, FunctionalPyramidDeclaration], ...],
    available_repositories: frozenset[str],
    declaration_findings: tuple[FunctionalPyramidFinding, ...] = (),
) -> tuple[
    dict[FunctionalDocumentPlacement, FunctionalDocumentDeclaration],
    tuple[FunctionalPyramidFinding, ...],
]:
    member_ids = frozenset(member.repository_id for member in members)
    index, duplicate_findings = _indexes(declarations)
    findings: list[FunctionalPyramidFinding] = [
        *declaration_findings,
        *duplicate_findings,
    ]

    for member in members:
        if member.repository_id not in available_repositories:
            findings.append(
                _finding(
                    FunctionalPyramidFindingReason.REPOSITORY_UNAVAILABLE,
                    "active Functional Pyramid member is unavailable",
                    "restore the named member repository",
                    repository_id=member.repository_id,
                )
            )

    for placement, declaration in index.items():
        document_repository = placement.document.repository_id
        if document_repository not in member_ids:
            findings.append(
                _finding(
                    FunctionalPyramidFindingReason.INVALID_DOCUMENT_REFERENCE,
                    "document reference targets a repository outside the Functional Pyramid instance",
                    "reference a canonical document owned by an instance member",
                    repository_id=document_repository,
                    placement=placement,
                )
            )
        elif document_repository not in available_repositories:
            findings.append(
                _finding(
                    FunctionalPyramidFindingReason.REPOSITORY_UNAVAILABLE,
                    "document owner repository is unavailable",
                    "restore the named member repository",
                    repository_id=document_repository,
                    placement=placement,
                )
            )

        if placement.document.layer is FunctionalPyramidLayer.P0:
            if declaration.governing_placements != ("ROOT",):
                findings.append(
                    _finding(
                        FunctionalPyramidFindingReason.INVALID_GOVERNING_EDGE,
                        "P0 placement must have exactly ROOT as its governing relationship",
                        "declare exactly ROOT for the P0 placement",
                        repository_id=placement.declaring_repository_id,
                        placement=placement,
                    )
                )
        elif "ROOT" in declaration.governing_placements:
            findings.append(
                _finding(
                    FunctionalPyramidFindingReason.INVALID_GOVERNING_EDGE,
                    "only P0 placements may be governed directly by ROOT",
                    "declare a permitted governing placement under FD-67",
                    repository_id=placement.declaring_repository_id,
                    placement=placement,
                )
            )

        for parent in declaration.governing_placements:
            if isinstance(parent, str):
                continue
            if parent.declaring_repository_id not in member_ids:
                findings.append(
                    _finding(
                        FunctionalPyramidFindingReason.INVALID_DOCUMENT_REFERENCE,
                        "governing placement targets a repository outside the instance",
                        "correct the repository-qualified governing placement",
                        repository_id=parent.declaring_repository_id,
                        placement=placement,
                    )
                )
                continue
            if parent.declaring_repository_id not in available_repositories:
                findings.append(
                    _finding(
                        FunctionalPyramidFindingReason.REPOSITORY_UNAVAILABLE,
                        "governing placement member repository is unavailable",
                        "restore the named member repository",
                        repository_id=parent.declaring_repository_id,
                        placement=placement,
                    )
                )
                continue
            if parent not in index:
                findings.append(
                    _finding(
                        FunctionalPyramidFindingReason.UNKNOWN_DOCUMENT,
                        "governing placement does not exist in the named available member",
                        "correct or declare the exact governing placement",
                        repository_id=parent.declaring_repository_id,
                        placement=placement,
                    )
                )
                continue
            if not _governing_layer_is_valid(
                placement.document.layer, parent.document.layer
            ):
                findings.append(
                    _finding(
                        FunctionalPyramidFindingReason.INVALID_GOVERNING_EDGE,
                        "governing placement layer is not admissible for the governed placement",
                        "declare a governing edge permitted by FD-67",
                        repository_id=placement.declaring_repository_id,
                        placement=placement,
                    )
                )
            if (
                parent.declaring_repository_id == placement.declaring_repository_id
                and not directory_scope_contains(parent.scope, placement.scope)
            ):
                findings.append(
                    _finding(
                        FunctionalPyramidFindingReason.INVALID_GOVERNING_EDGE,
                        "same-repository governing placement has narrower scope than the governed placement",
                        "widen the governing placement scope or narrow the governed placement",
                        repository_id=placement.declaring_repository_id,
                        placement=placement,
                    )
                )

    cycle_nodes: set[FunctionalDocumentPlacement] = set()
    visiting: set[FunctionalDocumentPlacement] = set()
    visited: set[FunctionalDocumentPlacement] = set()

    def visit(
        node: FunctionalDocumentPlacement,
        stack: tuple[FunctionalDocumentPlacement, ...],
    ) -> None:
        if node in visiting:
            start = stack.index(node) if node in stack else 0
            cycle_nodes.update(stack[start:])
            cycle_nodes.add(node)
            return
        if node in visited:
            return
        visiting.add(node)
        entry = index.get(node)
        if entry is not None:
            for parent in entry.governing_placements:
                if not isinstance(parent, str) and parent in index:
                    visit(parent, stack + (node,))
        visiting.remove(node)
        visited.add(node)

    for placement in sorted(index, key=_placement_sort_key):
        visit(placement, ())
    for placement in sorted(cycle_nodes, key=_placement_sort_key):
        findings.append(
            _finding(
                FunctionalPyramidFindingReason.DOCUMENT_CYCLE,
                "governing document placements form a cycle",
                "remove the cycle from the declaration graph",
                repository_id=placement.declaring_repository_id,
                placement=placement,
            )
        )

    invalid_scope_repositories = {
        finding.repository_id
        for finding in findings
        if finding.reason is FunctionalPyramidFindingReason.INVALID_PLACEMENT_SCOPE
        and finding.repository_id is not None
    }
    for member in members:
        if member.repository_id in invalid_scope_repositories:
            continue
        root_ok = any(
            placement.declaring_repository_id == member.repository_id
            and placement.scope == "."
            and placement.document.layer is FunctionalPyramidLayer.P0
            and declaration.governing_placements == ("ROOT",)
            for placement, declaration in index.items()
        )
        if not root_ok:
            findings.append(
                _finding(
                    FunctionalPyramidFindingReason.MISSING_ROOT_PLACEMENT,
                    "member declaration graph has no root-scoped P0 placement governed by ROOT",
                    "declare at least one scope='.' P0 placement governed exactly by ROOT",
                    repository_id=member.repository_id,
                    directory=".",
                )
            )

    return index, _ordered_findings(findings)


def evaluate_functional_pyramid_health(
    members: tuple[FunctionalPyramidMemberView, ...],
    declarations: tuple[tuple[str, FunctionalPyramidDeclaration], ...],
    available_repositories: frozenset[str],
    declaration_findings: tuple[FunctionalPyramidFinding, ...] = (),
) -> tuple[FunctionalPyramidHealth, tuple[FunctionalPyramidFinding, ...]]:
    """Evaluate current structural graph health without authority/support currency."""
    _, findings = _graph_findings(
        members, declarations, available_repositories, declaration_findings
    )
    return (
        FunctionalPyramidHealth.VALID
        if not findings
        else FunctionalPyramidHealth.DEGRADED,
        findings,
    )


def _directory_for_file(path: str) -> str:
    parent = _posixpath.dirname(path)
    return "." if parent in ("", ".") else normalize_directory_scope(parent)


def _semantic_seeds(
    surface: SurfaceKey, semantic_scope: EvidenceScope
) -> tuple[tuple[str | None, EvidenceScope], ...]:
    if surface.kind is SurfaceKind.FILE:
        return ((_directory_for_file(surface.locator), semantic_scope),)
    if surface.kind is SurfaceKind.SYMBOL:
        owner = _containment.surface_file_locator(surface.locator)
        if owner is None:
            raise ValueError("SYMBOL surface has no canonical owning file")
        return ((_directory_for_file(owner), semantic_scope),)
    if not semantic_scope.paths and not semantic_scope.evidence_refs:
        return ((None, semantic_scope),)

    seeds: list[tuple[str | None, EvidenceScope]] = []
    for path in semantic_scope.paths:
        owner = _containment.surface_file_locator(path)
        directory = (
            _directory_for_file(owner)
            if owner is not None
            else normalize_directory_scope(path)
        )
        seeds.append((directory, EvidenceScope(paths=(path,))))
    for ref in semantic_scope.evidence_refs:
        if ref.repository_id != surface.repository_id:
            raise ValueError("semantic scope crosses its owning repository")
        owner = _containment.surface_file_locator(ref.locator)
        locator = owner if owner is not None else ref.locator
        seeds.append(
            (
                _directory_for_file(locator),
                EvidenceScope(evidence_refs=(ref,)),
            )
        )
    return tuple(seeds)


def _direct_selection(
    *,
    repository_id: str,
    directory: str | None,
    index: dict[FunctionalDocumentPlacement, FunctionalDocumentDeclaration],
) -> tuple[FunctionalDocumentPlacement, ...]:
    selected = [
        placement
        for placement in index
        if placement.declaring_repository_id == repository_id
        and (
            directory is None
            or directory_scope_contains(placement.scope, directory)
        )
    ]
    return tuple(sorted(selected, key=_placement_sort_key))


def _closure(
    initial: _collections.Iterable[FunctionalDocumentPlacement],
    index: dict[FunctionalDocumentPlacement, FunctionalDocumentDeclaration],
) -> tuple[FunctionalDocumentPlacement, ...]:
    seen: set[FunctionalDocumentPlacement] = set()
    stack = list(initial)
    while stack:
        placement = stack.pop()
        if placement in seen:
            continue
        seen.add(placement)
        declaration = index.get(placement)
        if declaration is None:
            continue
        for parent in declaration.governing_placements:
            if not isinstance(parent, str) and parent in index:
                stack.append(parent)
    return tuple(sorted(seen, key=_placement_sort_key))


def _downstream(
    placement: FunctionalDocumentPlacement,
    index: dict[FunctionalDocumentPlacement, FunctionalDocumentDeclaration],
) -> tuple[FunctionalDocumentPlacement, ...]:
    return tuple(
        sorted(
            (
                child
                for child, declaration in index.items()
                if placement in declaration.governing_placements
            ),
            key=_placement_sort_key,
        )
    )


def _relevant_findings(
    findings: tuple[FunctionalPyramidFinding, ...],
    *,
    repository_id: str,
    closure: tuple[FunctionalDocumentPlacement, ...],
) -> tuple[FunctionalPyramidFinding, ...]:
    closure_set = set(closure)
    relevant_repositories = {repository_id}
    for placement in closure:
        relevant_repositories.add(placement.declaring_repository_id)
        relevant_repositories.add(placement.document.repository_id)
    selected: list[FunctionalPyramidFinding] = []
    for finding in findings:
        if finding.placement is not None:
            if finding.placement in closure_set:
                selected.append(finding)
            continue
        if finding.reason is FunctionalPyramidFindingReason.MISSING_ROOT_PLACEMENT:
            if finding.repository_id == repository_id:
                selected.append(finding)
            continue
        if finding.repository_id in relevant_repositories and finding.reason in (
            FunctionalPyramidFindingReason.REPOSITORY_UNAVAILABLE,
            FunctionalPyramidFindingReason.INVALID_DECLARATION,
            FunctionalPyramidFindingReason.INVALID_PLACEMENT_SCOPE,
        ):
            selected.append(finding)
    return _ordered_findings(selected)


def _route_identity(
    *,
    repository_id: str,
    selection: object,
    closure: tuple[FunctionalDocumentPlacement, ...],
    index: dict[FunctionalDocumentPlacement, FunctionalDocumentDeclaration],
    members: tuple[FunctionalPyramidMemberView, ...],
) -> FunctionalRouteIdentity:
    payload = {
        "repository_id": repository_id,
        "selection": selection,
        "placements": [
            {
                "declaring_repository_id": placement.declaring_repository_id,
                "document_repository_id": placement.document.repository_id,
                "document_ref": placement.document.document_ref,
                "layer": placement.document.layer.value,
                "scope": placement.scope,
                "parents": [
                    "ROOT"
                    if isinstance(parent, str)
                    else {
                        "declaring_repository_id": parent.declaring_repository_id,
                        "document_repository_id": parent.document.repository_id,
                        "document_ref": parent.document.document_ref,
                        "layer": parent.document.layer.value,
                        "scope": parent.scope,
                    }
                    for parent in index[placement].governing_placements
                ]
                if placement in index
                else [],
            }
            for placement in closure
        ],
        "members": [
            member.repository_id
            for member in sorted(members, key=lambda value: value.repository_id)
        ],
    }
    digest = _hashlib.sha256(
        _json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return FunctionalRouteIdentity(digest)


def _resolve(
    *,
    pyramid_id: FunctionalPyramidId,
    version: FunctionalPyramidVersion,
    members: tuple[FunctionalPyramidMemberView, ...],
    repository_id: str,
    seeds: tuple[tuple[str | None, EvidenceScope | None], ...],
    directory_selection: str | None,
    semantic_selection: EvidenceScope | None,
    declarations: tuple[tuple[str, FunctionalPyramidDeclaration], ...],
    available_repositories: frozenset[str],
    authority_bindings: dict[tuple[str, str], AuthorityBinding],
    declaration_findings: tuple[FunctionalPyramidFinding, ...] = (),
) -> tuple[FunctionalPyramidView, FunctionalRouteIdentity]:
    index, structural = _graph_findings(
        members, declarations, available_repositories, declaration_findings
    )
    health = (
        FunctionalPyramidHealth.VALID
        if not structural
        else FunctionalPyramidHealth.DEGRADED
    )

    provenance: list[FunctionalRouteProvenance] = []
    direct: set[FunctionalDocumentPlacement] = set()
    for directory, semantic_portion in seeds:
        selected = _direct_selection(
            repository_id=repository_id,
            directory=directory,
            index=index,
        )
        direct.update(selected)
        provenance.append(
            FunctionalRouteProvenance(
                directory="." if directory is None else directory,
                semantic_scope=semantic_portion,
                placements=selected,
            )
        )
    closure = _closure(direct, index)
    unresolved = _relevant_findings(
        structural,
        repository_id=repository_id,
        closure=closure,
    )

    routes: list[FunctionalDocumentRoute] = []
    for placement in closure:
        declaration = index.get(placement)
        if declaration is None:
            continue
        authority = authority_bindings.get(
            (placement.document.repository_id, placement.document.document_ref)
        )
        if authority is None:
            continue
        routes.append(
            FunctionalDocumentRoute(
                placement=placement,
                authority=authority,
                governing_placements=declaration.governing_placements,
                downstream_placements=_downstream(placement, index),
            )
        )

    declared = tuple(
        layer
        for layer in _LAYER_ORDER
        if any(placement.document.layer is layer for placement in closure)
    )
    absent = tuple(layer for layer in _LAYER_ORDER if layer not in declared)
    status = (
        FunctionalPyramidRouteStatus.RESOLVED
        if not unresolved
        else FunctionalPyramidRouteStatus.UNRESOLVED
    )

    if directory_selection is not None:
        selection_identity: object = {"directory": directory_selection}
    else:
        selection_identity = {
            "semantic_scope": {
                "paths": list(
                    semantic_selection.paths if semantic_selection is not None else ()
                ),
                "evidence": [
                    (
                        ref.repository_id,
                        ref.locator,
                        ref.revision_or_fingerprint,
                    )
                    for ref in (
                        semantic_selection.evidence_refs
                        if semantic_selection is not None
                        else ()
                    )
                ],
            }
        }
    identity = _route_identity(
        repository_id=repository_id,
        selection=selection_identity,
        closure=closure,
        index=index,
        members=members,
    )
    view = FunctionalPyramidView(
        pyramid_id=pyramid_id,
        version=version,
        health=health,
        status=status,
        directory=directory_selection,
        semantic_scope=semantic_selection,
        placements=closure,
        routes=tuple(routes),
        provenance=tuple(provenance),
        unresolved=unresolved,
        declared_layers=declared,
        absent_layers=absent,
    )
    return view, identity


def resolve_functional_pyramid_route(
    *,
    pyramid_id: FunctionalPyramidId,
    version: FunctionalPyramidVersion,
    members: tuple[FunctionalPyramidMemberView, ...],
    surface: SurfaceKey,
    semantic_scope: EvidenceScope,
    declarations: tuple[tuple[str, FunctionalPyramidDeclaration], ...],
    available_repositories: frozenset[str],
    authority_bindings: dict[tuple[str, str], AuthorityBinding],
    declaration_findings: tuple[FunctionalPyramidFinding, ...] = (),
) -> tuple[FunctionalPyramidView, FunctionalRouteIdentity]:
    """Resolve the exact effective semantic scope through document placements."""
    seeds = tuple(
        (directory, portion)
        for directory, portion in _semantic_seeds(surface, semantic_scope)
    )
    return _resolve(
        pyramid_id=pyramid_id,
        version=version,
        members=members,
        repository_id=surface.repository_id,
        seeds=seeds,
        directory_selection=None,
        semantic_selection=semantic_scope,
        declarations=declarations,
        available_repositories=available_repositories,
        authority_bindings=authority_bindings,
        declaration_findings=declaration_findings,
    )


def resolve_functional_pyramid_directory_route(
    *,
    pyramid_id: FunctionalPyramidId,
    version: FunctionalPyramidVersion,
    members: tuple[FunctionalPyramidMemberView, ...],
    repository_id: str,
    directory: str,
    declarations: tuple[tuple[str, FunctionalPyramidDeclaration], ...],
    available_repositories: frozenset[str],
    authority_bindings: dict[tuple[str, str], AuthorityBinding],
    declaration_findings: tuple[FunctionalPyramidFinding, ...] = (),
) -> tuple[FunctionalPyramidView, FunctionalRouteIdentity]:
    """Resolve one exact directory as a point in the repository tree."""
    normalized = normalize_directory_scope(directory)
    return _resolve(
        pyramid_id=pyramid_id,
        version=version,
        members=members,
        repository_id=repository_id,
        seeds=((normalized, None),),
        directory_selection=normalized,
        semantic_selection=None,
        declarations=declarations,
        available_repositories=available_repositories,
        authority_bindings=authority_bindings,
        declaration_findings=declaration_findings,
    )
