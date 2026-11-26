"""Pure document-placement algebra and Functional Pyramid resolution."""

from __future__ import annotations

import collections as _collections
import collections.abc as _collections_abc
import hashlib as _hashlib
import json as _json
import posixpath as _posixpath

from span.core import containment as _containment
from span.core.model.classification import (
    FunctionalPyramidClassification,
    FunctionalPyramidClassificationDisposition,
    FunctionalPyramidClassificationExclusion,
    FunctionalPyramidClassificationRow,
    FunctionalPyramidDerivation,
)
from span.core.model.functional_pyramid import (
    FunctionalDirectoryScope,
    FunctionalDocumentDeclaration,
    FunctionalDocumentIdentity,
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
    FunctionalPyramidMemberIntent,
    FunctionalPyramidMemberView,
    FunctionalPyramidResolution,
    FunctionalPyramidRouteStatus,
    FunctionalPyramidSourceKind,
    FunctionalPyramidVersion,
    FunctionalPyramidView,
    FunctionalRouteIdentity,
    FunctionalRouteProvenance,
)
from span.core.model.investigation import EvidenceRequest, SourceRange
from span.core.model.primitives import (
    AuthorityApplicability,
    AuthorityBinding,
    AuthorityKind,
    AuthorityStatus,
    EvidenceId,
    EvidenceRef,
    EvidenceScope,
    EvidenceSourceKind,
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
    return directory_scope_contains(left, right) or directory_scope_contains(
        right, left
    )


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
    findings: _collections_abc.Iterable[FunctionalPyramidFinding],
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


def _decode_document_identity(value: object) -> FunctionalDocumentIdentity:
    raw = _require_json_object(value, frozenset({"repository_id", "document_ref"}))
    return FunctionalDocumentIdentity(
        repository_id=_require_json_string(
            raw["repository_id"], "FunctionalDocumentIdentity.repository_id"
        ),
        document_ref=_require_json_string(
            raw["document_ref"], "FunctionalDocumentIdentity.document_ref"
        ),
    )


def decode_functional_pyramid_classification(
    text: str, *, repository_id: str
) -> FunctionalPyramidClassification:
    """Decode one repository-owned Version-1 classification (FD-88A).

    Decode exact fields into the existing canonical row model. The repository
    routing identity is explicit; cross-repository governing identities are
    resolved only after combining the complete selected member set.
    """
    _require_non_empty("classification repository_id", repository_id)

    def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate classification JSON field: {key}")
            result[key] = value
        return result

    try:
        value = _json.loads(text, object_pairs_hook=unique_object)
    except _json.JSONDecodeError as exc:
        raise ValueError("Functional Pyramid classification is not valid JSON") from exc
    raw = _require_json_object(value, frozenset({"version", "rows"}))
    if type(raw["version"]) is not int or raw["version"] != 1:
        raise ValueError("classification.version must be 1")
    common = frozenset(
        {"declaring_repository_id", "repository_id", "document_ref", "disposition"}
    )
    rows: list[FunctionalPyramidClassificationRow] = []
    for item in _require_json_array(raw["rows"], "classification.rows"):
        if not isinstance(item, dict):
            raise ValueError("classification row must be an object")
        disposition = FunctionalPyramidClassificationDisposition(
            _require_json_string(item.get("disposition"), "row.disposition")
        )
        fields = (
            common | {"exclusion_reason"}
            if disposition is FunctionalPyramidClassificationDisposition.EXCLUDE
            else common
            | {
                "layer",
                "scope",
                "governing_documents",
                "authority_kind",
                "authority_status",
            }
        )
        row = _require_json_object(item, fields)
        declaring = _require_json_string(
            row["declaring_repository_id"], "row.declaring_repository_id"
        )
        owner = _require_json_string(row["repository_id"], "row.repository_id")
        if declaring != repository_id:
            raise ValueError(
                "classification row declaring repository identity mismatch"
            )
        document = _require_json_string(row["document_ref"], "row.document_ref")
        if disposition is FunctionalPyramidClassificationDisposition.EXCLUDE:
            rows.append(
                FunctionalPyramidClassificationRow(
                    declaring_repository_id=declaring,
                    repository_id=owner,
                    document_ref=document,
                    disposition=disposition,
                    exclusion_reason=_require_json_string(
                        row["exclusion_reason"], "row.exclusion_reason"
                    ),
                )
            )
            continue
        parents: list[tuple[str, FunctionalDocumentIdentity] | str] = []
        for parent in _require_json_array(
            row["governing_documents"], "row.governing_documents"
        ):
            if isinstance(parent, str):
                parents.append(parent)
            else:
                coordinates = _require_json_object(
                    parent,
                    frozenset(
                        {"declaring_repository_id", "repository_id", "document_ref"}
                    ),
                )
                parents.append(
                    (
                        _require_json_string(
                            coordinates["declaring_repository_id"],
                            "governing declaring repository",
                        ),
                        _decode_document_identity(
                            {
                                "repository_id": coordinates["repository_id"],
                                "document_ref": coordinates["document_ref"],
                            }
                        ),
                    )
                )
        rows.append(
            FunctionalPyramidClassificationRow(
                declaring_repository_id=declaring,
                repository_id=owner,
                document_ref=document,
                disposition=disposition,
                layer=FunctionalPyramidLayer(
                    _require_json_string(row["layer"], "row.layer")
                ),
                scope=_require_json_string(row["scope"], "row.scope"),
                governing_documents=tuple(parents),
                authority_kind=AuthorityKind(
                    _require_json_string(row["authority_kind"], "row.authority_kind")
                ),
                authority_status=AuthorityStatus(
                    _require_json_string(
                        row["authority_status"], "row.authority_status"
                    )
                ),
            )
        )
    return FunctionalPyramidClassification(rows=tuple(rows))


def decode_functional_pyramid_declaration(
    text: str,
    *,
    repository_id: str,
    declaration_locator: str,
) -> tuple[FunctionalPyramidDeclaration, tuple[FunctionalPyramidFinding, ...]]:
    """Strictly decode one Version-3 declaration and retain scope findings.

    JSON/version/kind/source-scope/membership-shape failures raise ValueError and
    are owned by the declaration-source validation path. Once a placement entry's
    non-scope coordinates are recoverable, a non-canonical placement scope is
    returned exclusively as INVALID_PLACEMENT_SCOPE and no invalid canonical
    placement is built.
    """
    try:
        value = _json.loads(text)
    except _json.JSONDecodeError as exc:
        raise ValueError("Functional Pyramid declaration is not valid JSON") from exc
    raw = _require_json_object(
        value,
        frozenset({"version", "source_id", "kind", "scope", "documents", "placements"}),
    )
    if raw["version"] != 3:
        raise ValueError("Functional Pyramid declaration version must be 3")
    source_id = _require_json_string(raw["source_id"], "declaration source_id")
    kind_token = _require_json_string(raw["kind"], "declaration kind")
    try:
        kind = FunctionalPyramidSourceKind(kind_token)
    except ValueError as exc:
        raise ValueError("unknown Functional Pyramid source kind") from exc
    source_scope_token = _require_json_string(raw["scope"], "declaration scope")
    try:
        source_scope = normalize_directory_scope(source_scope_token)
    except ValueError as exc:
        raise ValueError(
            "Functional Pyramid declaration source scope is not canonical "
            "repository-relative directory scope"
        ) from exc
    documents = tuple(
        _decode_document_identity(item)
        for item in _require_json_array(raw["documents"], "declaration documents")
    )

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
        FunctionalPyramidDeclaration(
            version=3,
            source_id=source_id,
            kind=kind,
            scope=source_scope,
            documents=documents,
            placements=tuple(declarations),
        ),
        _ordered_findings(findings),
    )


def derive_functional_pyramid_declarations(
    classification: FunctionalPyramidClassification,
) -> FunctionalPyramidDerivation:
    """Materialise one classification into canonical Version-3 sources (FD-88A).

    Pure. The row owns the layer, scope, governing documents and disposition;
    this function derives source identity and kind, membership, placement
    identity, governing placement coordinates and ordering. Graph validity is
    evaluated separately through the source-set structural owner.
    """
    placed: dict[
        tuple[str, FunctionalDocumentIdentity], FunctionalPyramidClassificationRow
    ] = {}
    exclusions: list[FunctionalPyramidClassificationExclusion] = []
    for row in classification.rows:
        if row.disposition is FunctionalPyramidClassificationDisposition.EXCLUDE:
            assert row.exclusion_reason is not None
            exclusions.append(
                FunctionalPyramidClassificationExclusion(
                    declaring_repository_id=row.declaring_repository_id,
                    repository_id=row.repository_id,
                    document_ref=row.document_ref,
                    reason=row.exclusion_reason,
                )
            )
            continue
        placed[
            (
                row.declaring_repository_id,
                FunctionalDocumentIdentity(row.repository_id, row.document_ref),
            )
        ] = row

    represented = {row.declaring_repository_id for row in classification.rows}
    if any(row.repository_id not in represented for row in classification.rows):
        raise ValueError("canonical document owner is outside the selected member set")
    with_placements = {row.declaring_repository_id for row in placed.values()}
    missing = sorted(represented - with_placements)
    if missing:
        raise ValueError(
            "selected classification repositories require placed documents: "
            + ", ".join(missing)
        )

    def placement_for(
        row: FunctionalPyramidClassificationRow,
    ) -> FunctionalDocumentPlacement:
        assert row.layer is not None
        assert row.scope is not None
        return FunctionalDocumentPlacement(
            declaring_repository_id=row.declaring_repository_id,
            document=FunctionalDocumentRef(
                row.repository_id, row.document_ref, row.layer
            ),
            scope=row.scope,
        )

    def governing_for(
        row: FunctionalPyramidClassificationRow,
    ) -> tuple[FunctionalDocumentPlacement | str, ...]:
        if row.layer is FunctionalPyramidLayer.P0:
            return ("ROOT",)
        resolved: list[FunctionalDocumentPlacement] = []
        for parent in row.governing_documents:
            if isinstance(parent, str):
                raise ValueError("ROOT cannot govern a non-P0 placement")
            try:
                parent_row = placed[parent]
            except KeyError:
                raise ValueError(
                    "governing document is not a placed document in this "
                    f"classification: {parent[0]}:{parent[1].repository_id}:{parent[1].document_ref}"
                ) from None
            resolved.append(placement_for(parent_row))
        return tuple(sorted(resolved, key=_placement_sort_key))

    grouped: dict[tuple[str, str], list[FunctionalPyramidClassificationRow]] = {}
    for row in placed.values():
        assert row.scope is not None
        grouped.setdefault((row.declaring_repository_id, row.scope), []).append(row)

    declarations: list[tuple[str, FunctionalPyramidDeclaration]] = []
    for repository_id, scope in sorted(grouped):
        rows = grouped[(repository_id, scope)]
        entries = [
            FunctionalDocumentDeclaration(
                placement=placement_for(row),
                governing_placements=governing_for(row),
            )
            for row in rows
        ]
        entries.sort(key=lambda entry: _placement_sort_key(entry.placement))
        documents = tuple(
            sorted(
                (
                    FunctionalDocumentIdentity(row.repository_id, row.document_ref)
                    for row in rows
                ),
                key=lambda identity: (identity.repository_id, identity.document_ref),
            )
        )
        declarations.append(
            (
                repository_id,
                FunctionalPyramidDeclaration(
                    version=3,
                    source_id=f"{repository_id}:{scope}",
                    kind=(
                        FunctionalPyramidSourceKind.REPOSITORY
                        if scope == "."
                        else FunctionalPyramidSourceKind.AREA
                    ),
                    scope=scope,
                    documents=documents,
                    placements=tuple(entries),
                ),
            )
        )
    return FunctionalPyramidDerivation(
        declarations=tuple(declarations),
        exclusions=tuple(
            sorted(
                exclusions,
                key=lambda exclusion: (
                    exclusion.declaring_repository_id,
                    exclusion.repository_id,
                    exclusion.document_ref,
                ),
            )
        ),
    )


def _declaration_bytes(payload: dict[str, object]) -> bytes:
    """Stable bytes for the two existing untagged declaration carriers."""
    return (
        _json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _placement_payload(placement: FunctionalDocumentPlacement) -> dict[str, object]:
    return {
        "document": {
            "repository_id": placement.document.repository_id,
            "document_ref": placement.document.document_ref,
            "layer": placement.document.layer.value,
        },
        "scope": placement.scope,
    }


def encode_functional_pyramid_declaration(
    repository_id: str, declaration: FunctionalPyramidDeclaration
) -> bytes:
    """Encode the exact Version-3 source grammar consumed by the decoder."""
    entries: list[dict[str, object]] = []
    for entry in declaration.placements:
        if entry.placement.declaring_repository_id != repository_id:
            raise ValueError("declaration placement belongs to a different repository")
        entries.append(
            {
                **_placement_payload(entry.placement),
                "governing_placements": [
                    (
                        parent
                        if isinstance(parent, str)
                        else {
                            **_placement_payload(parent),
                            "declaring_repository_id": parent.declaring_repository_id,
                        }
                    )
                    for parent in entry.governing_placements
                ],
            }
        )
    return _declaration_bytes(
        {
            "version": declaration.version,
            "source_id": declaration.source_id,
            "kind": declaration.kind.value,
            "scope": declaration.scope,
            "documents": [
                {"repository_id": item.repository_id, "document_ref": item.document_ref}
                for item in declaration.documents
            ],
            "placements": entries,
        }
    )


def functional_pyramid_declaration_request(
    repository_id: str, declaration: FunctionalPyramidDeclaration
) -> EvidenceRequest:
    """Address immutable source bytes, not a mutable repository/scope filename."""
    digest = _hashlib.sha256(
        encode_functional_pyramid_declaration(repository_id, declaration)
    ).hexdigest()
    return EvidenceRequest(locator=f".span/functional-pyramid/{digest}.json")


def derive_functional_pyramid_member_intents(
    derivation: FunctionalPyramidDerivation,
) -> tuple[FunctionalPyramidMemberIntent, ...]:
    """Derive the complete member input from validated canonical sources."""
    findings = evaluate_functional_pyramid_source_structure(derivation.declarations)
    if findings:
        raise ValueError(
            "invalid derived Functional Pyramid: "
            + "; ".join(finding.detail for finding in findings)
        )
    requests: dict[str, list[EvidenceRequest]] = {}
    for repository_id, declaration in derivation.declarations:
        requests.setdefault(repository_id, []).append(
            functional_pyramid_declaration_request(repository_id, declaration)
        )
    return tuple(
        FunctionalPyramidMemberIntent(
            repository_id=repository_id,
            declaration_sources=tuple(requests[repository_id]),
        )
        for repository_id in sorted(requests)
    )


def encode_functional_pyramid_bootstrap(
    bootstrap: FunctionalPyramidBootstrap,
) -> bytes:
    """Encode the existing Version-2 navigation bootstrap, not a source."""
    return _declaration_bytes(
        {
            "version": bootstrap.version,
            "declaration_sources": [
                {
                    "locator": request.locator,
                    "ranges": [
                        {"start_line": item.start_line, "end_line": item.end_line}
                        for item in request.ranges
                    ],
                }
                for request in bootstrap.declaration_sources
            ],
        }
    )


def _binding_key(binding: AuthorityBinding) -> tuple[str, str]:
    reference = binding.evidence_ref
    return reference.repository_id, reference.evidence_id.value


def _binding_identity(binding: AuthorityBinding) -> FunctionalDocumentIdentity:
    reference = binding.evidence_ref
    return FunctionalDocumentIdentity(reference.repository_id, reference.locator)


def _classification_binding_matches(
    binding: AuthorityBinding, row: FunctionalPyramidClassificationRow
) -> bool:
    return (
        binding.authority_kind is row.authority_kind
        and binding.status is row.authority_status
        and binding.applicability == AuthorityApplicability()
        and binding.declared_precedence is None
    )


def _derived_authority_binding(
    row: FunctionalPyramidClassificationRow,
    fingerprint: str,
    existing: AuthorityBinding | None,
) -> AuthorityBinding:
    assert row.authority_kind is not None
    assert row.authority_status is not None
    digest = _hashlib.sha256(
        _declaration_bytes(
            {"repository_id": row.repository_id, "document_ref": row.document_ref}
        )
    ).hexdigest()
    identity = (
        existing.evidence_ref.evidence_id
        if existing is not None
        else EvidenceId(f"authority-document-{digest}")
    )
    return AuthorityBinding(
        evidence_ref=EvidenceRef(
            evidence_id=identity,
            repository_id=row.repository_id,
            source_kind=EvidenceSourceKind.DOCUMENTATION,
            locator=row.document_ref,
            revision_or_fingerprint=fingerprint,
        ),
        authority_kind=row.authority_kind,
        status=row.authority_status,
    )


def reconcile_functional_pyramid_bindings(
    classification: FunctionalPyramidClassification,
    *,
    fingerprints: _collections_abc.Mapping[FunctionalDocumentIdentity, str],
    registered: tuple[AuthorityBinding, ...],
    previously_owned: tuple[AuthorityBinding, ...],
) -> tuple[tuple[AuthorityBinding, ...], tuple[AuthorityBinding, ...]]:
    """Return reconciled bindings and exact FP-owned subset (FD-88A).

    The caller supplies observed source identities and prior accepted ownership
    evidence, not a naming heuristic. Equivalent independent bindings retain
    their original evidence identity and values.
    """
    current = {_binding_key(binding): binding for binding in registered}
    old_owned = {_binding_key(binding): binding for binding in previously_owned}
    if len(current) != len(registered) or len(old_owned) != len(previously_owned):
        raise ValueError("duplicate authority binding identity")
    for key, previous in old_owned.items():
        if previous.evidence_ref.section_or_span is not None:
            raise ValueError("invalid Functional Pyramid binding ownership evidence")
        if key in current and current[key] != previous:
            raise ValueError("Functional Pyramid binding ownership conflict")
    whole: dict[tuple[str, str], list[AuthorityBinding]] = {}
    for binding in registered:
        if binding.evidence_ref.section_or_span is None:
            reference = binding.evidence_ref
            whole.setdefault((reference.repository_id, reference.locator), []).append(
                binding
            )
    result = {key: value for key, value in current.items() if key not in old_owned}
    owned: dict[tuple[str, str], AuthorityBinding] = {}
    for row in classification.rows:
        document = FunctionalDocumentIdentity(row.repository_id, row.document_ref)
        fingerprint = fingerprints.get(document)
        if not fingerprint:
            raise ValueError(f"classified document is unavailable: {document}")
        if row.disposition is FunctionalPyramidClassificationDisposition.EXCLUDE:
            continue
        candidates = whole.get((document.repository_id, document.document_ref), [])
        if len(candidates) > 1:
            raise ValueError(f"competing whole-document authority bindings: {document}")
        existing = candidates[0] if candidates else None
        if existing is not None and _classification_binding_matches(existing, row):
            binding = existing
            is_owned = _binding_key(existing) in old_owned
        else:
            if existing is not None and _binding_key(existing) not in old_owned:
                raise ValueError(f"independent authority binding conflict: {document}")
            binding = _derived_authority_binding(row, fingerprint, existing)
            is_owned = True
        key = _binding_key(binding)
        if key in result and result[key] != binding:
            raise ValueError(f"authority binding identity collision: {document}")
        if key in old_owned and _binding_identity(old_owned[key]) != document:
            raise ValueError(f"authority binding ownership collision: {document}")
        result[key] = binding
        if is_owned:
            owned[key] = binding
    return (
        tuple(result[key] for key in sorted(result)),
        tuple(owned[key] for key in sorted(owned)),
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


def _governing_edge_is_valid(
    child: FunctionalDocumentPlacement,
    parent: FunctionalDocumentPlacement,
) -> bool:
    """Classify one declared governing-placement edge under FD-67."""
    if not _governing_layer_is_valid(
        child.document.layer,
        parent.document.layer,
    ):
        return False
    return (
        child.declaring_repository_id != parent.declaring_repository_id
        or directory_scope_contains(parent.scope, child.scope)
    )


def _indexes(
    declarations: tuple[tuple[str, FunctionalPyramidDeclaration], ...],
) -> tuple[
    dict[FunctionalDocumentPlacement, FunctionalDocumentDeclaration],
    tuple[FunctionalPyramidFinding, ...],
]:
    by_placement: dict[FunctionalDocumentPlacement, FunctionalDocumentDeclaration] = {}
    findings: list[FunctionalPyramidFinding] = []
    seen: set[FunctionalDocumentPlacement] = set()
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
            if placement in seen:
                findings.append(
                    _finding(
                        FunctionalPyramidFindingReason.DUPLICATE_DOCUMENT_PLACEMENT,
                        "one placement identity is declared more than once",
                        "retain one canonical declaration for the placement identity",
                        repository_id=repository_id,
                        placement=placement,
                    )
                )
                continue
            seen.add(placement)
            by_placement[placement] = entry
    return by_placement, _ordered_findings(findings)


def _member_availability_findings(
    member_ids: frozenset[str],
    available_repositories: frozenset[str],
) -> tuple[FunctionalPyramidFinding, ...]:
    return tuple(
        _finding(
            FunctionalPyramidFindingReason.REPOSITORY_UNAVAILABLE,
            "active Functional Pyramid member is unavailable",
            "restore the named member repository",
            repository_id=repository_id,
        )
        for repository_id in sorted(member_ids)
        if repository_id not in available_repositories
    )


def _placement_graph_findings(
    index: dict[FunctionalDocumentPlacement, FunctionalDocumentDeclaration],
    *,
    member_ids: frozenset[str],
    available_repositories: frozenset[str],
) -> tuple[FunctionalPyramidFinding, ...]:
    findings: list[FunctionalPyramidFinding] = []
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
        findings.extend(
            _governing_findings(
                placement,
                declaration,
                index=index,
                member_ids=member_ids,
                available_repositories=available_repositories,
            )
        )
    return tuple(findings)


def _governing_findings(
    placement: FunctionalDocumentPlacement,
    declaration: FunctionalDocumentDeclaration,
    *,
    index: dict[FunctionalDocumentPlacement, FunctionalDocumentDeclaration],
    member_ids: frozenset[str],
    available_repositories: frozenset[str],
) -> tuple[FunctionalPyramidFinding, ...]:
    findings: list[FunctionalPyramidFinding] = []
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
        elif parent.declaring_repository_id not in available_repositories:
            findings.append(
                _finding(
                    FunctionalPyramidFindingReason.REPOSITORY_UNAVAILABLE,
                    "governing placement member repository is unavailable",
                    "restore the named member repository",
                    repository_id=parent.declaring_repository_id,
                    placement=placement,
                )
            )
        elif parent not in index:
            findings.append(
                _finding(
                    FunctionalPyramidFindingReason.UNKNOWN_DOCUMENT,
                    "governing placement does not exist in the named available member",
                    "correct or declare the exact governing placement",
                    repository_id=parent.declaring_repository_id,
                    placement=placement,
                )
            )
        elif not _governing_edge_is_valid(placement, parent):
            findings.append(
                _finding(
                    FunctionalPyramidFindingReason.INVALID_GOVERNING_EDGE,
                    "governing placement is not admissible for the governed placement",
                    "declare a governing edge permitted by FD-67",
                    repository_id=placement.declaring_repository_id,
                    placement=placement,
                )
            )
    return tuple(findings)


def _cycle_findings(
    index: dict[FunctionalDocumentPlacement, FunctionalDocumentDeclaration],
) -> tuple[FunctionalPyramidFinding, ...]:
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
                if (
                    not isinstance(parent, str)
                    and parent in index
                    and _governing_edge_is_valid(node, parent)
                ):
                    visit(parent, stack + (node,))
        visiting.remove(node)
        visited.add(node)

    for placement in sorted(index, key=_placement_sort_key):
        visit(placement, ())
    return tuple(
        _finding(
            FunctionalPyramidFindingReason.DOCUMENT_CYCLE,
            "governing document placements form a cycle",
            "remove the cycle from the declaration graph",
            repository_id=placement.declaring_repository_id,
            placement=placement,
        )
        for placement in sorted(cycle_nodes, key=_placement_sort_key)
    )


def _source_set_findings(
    repository_id: str,
    declarations: tuple[FunctionalPyramidDeclaration, ...],
) -> tuple[FunctionalPyramidFinding, ...]:
    """Enforce S1-S5 source-set topology (FD-66/S-VALIDATE-01)."""
    findings: list[FunctionalPyramidFinding] = []
    source_ids = _collections.Counter(
        declaration.source_id for declaration in declarations
    )
    for source_id, count in sorted(source_ids.items()):
        if count > 1:
            findings.append(
                _finding(
                    FunctionalPyramidFindingReason.INVALID_DECLARATION,
                    f"declaration source identity {source_id!r} is declared "
                    f"{count} times in one declaring repository",
                    "retain one source identity per declaring repository",
                    repository_id=repository_id,
                )
            )
    source_scopes = _collections.Counter(
        declaration.scope for declaration in declarations
    )
    for scope, count in sorted(source_scopes.items()):
        if count > 1:
            findings.append(
                _finding(
                    FunctionalPyramidFindingReason.INVALID_DECLARATION,
                    f"declaration source scope {scope!r} is declared {count} times",
                    "retain one declaration source per scope",
                    repository_id=repository_id,
                    directory=scope,
                )
            )
    repository_sources = tuple(
        declaration
        for declaration in declarations
        if declaration.kind is FunctionalPyramidSourceKind.REPOSITORY
    )
    if len(repository_sources) != 1:
        findings.append(
            _finding(
                FunctionalPyramidFindingReason.INVALID_DECLARATION,
                "a declaring repository must have exactly one repository-kind "
                f"source; observed {len(repository_sources)}",
                "declare exactly one repository-kind source at scope '.'",
                repository_id=repository_id,
            )
        )
    for declaration in declarations:
        if (
            declaration.kind is FunctionalPyramidSourceKind.REPOSITORY
            and declaration.scope != "."
        ):
            findings.append(
                _finding(
                    FunctionalPyramidFindingReason.INVALID_DECLARATION,
                    "a repository-kind source must have scope '.'",
                    "move the repository-kind source to scope '.'",
                    repository_id=repository_id,
                    directory=declaration.scope,
                )
            )
        if (
            declaration.kind is FunctionalPyramidSourceKind.AREA
            and declaration.scope == "."
        ):
            findings.append(
                _finding(
                    FunctionalPyramidFindingReason.INVALID_DECLARATION,
                    "an area-kind source must have a non-root scope",
                    "declare the area source at its canonical directory scope",
                    repository_id=repository_id,
                    directory=declaration.scope,
                )
            )
    return tuple(findings)


def _source_local_findings(
    repository_id: str,
    declaration: FunctionalPyramidDeclaration,
) -> tuple[FunctionalPyramidFinding, ...]:
    """Enforce S6 (within source), S8, S9 and S10 for one source."""
    findings: list[FunctionalPyramidFinding] = []
    source_scope = declaration.scope
    for identity, count in sorted(
        _collections.Counter(declaration.documents).items(),
        key=lambda item: (item[0].repository_id, item[0].document_ref),
    ):
        if count > 1:
            findings.append(
                _finding(
                    FunctionalPyramidFindingReason.DUPLICATE_DOCUMENT_SOURCE,
                    f"{identity.repository_id}:{identity.document_ref} is listed "
                    f"{count} times in source {declaration.source_id!r}",
                    "list the canonical document exactly once in the source",
                    repository_id=repository_id,
                    directory=source_scope,
                )
            )
    listed = set(declaration.documents)
    for entry in declaration.placements:
        placement = entry.placement
        identity = placement.document.identity
        if placement.scope != source_scope:
            findings.append(
                _finding(
                    FunctionalPyramidFindingReason.DOCUMENT_SCOPE_MISMATCH,
                    f"{identity.repository_id}:{identity.document_ref} is placed at "
                    f"{placement.scope!r} but belongs to source "
                    f"{declaration.source_id!r} at {source_scope!r}",
                    "correct the placement scope or the declaration source",
                    repository_id=repository_id,
                    placement=placement,
                    directory=source_scope,
                )
            )
        if identity not in listed:
            findings.append(
                _finding(
                    FunctionalPyramidFindingReason.UNLISTED_AREA_DOCUMENT,
                    f"{identity.repository_id}:{identity.document_ref} is placed in "
                    f"source {declaration.source_id!r} but is absent from its "
                    "document membership",
                    "list the document in the source or remove the placement",
                    repository_id=repository_id,
                    placement=placement,
                    directory=source_scope,
                )
            )
    placed_at_source_scope = {
        entry.placement.document.identity
        for entry in declaration.placements
        if entry.placement.scope == source_scope
    }
    for identity in sorted(
        listed, key=lambda item: (item.repository_id, item.document_ref)
    ):
        if identity not in placed_at_source_scope:
            findings.append(
                _finding(
                    FunctionalPyramidFindingReason.MISSING_AREA_DOCUMENT,
                    f"{identity.repository_id}:{identity.document_ref} is listed in "
                    f"source {declaration.source_id!r} but has no placement at "
                    f"{source_scope!r}",
                    "place the listed document at the source scope",
                    repository_id=repository_id,
                    directory=source_scope,
                )
            )
    return tuple(findings)


def _complete_membership_findings(
    repository_id: str,
    declarations: tuple[FunctionalPyramidDeclaration, ...],
) -> tuple[FunctionalPyramidFinding, ...]:
    """Enforce cross-source membership and document identity uniqueness."""
    findings: list[FunctionalPyramidFinding] = []
    scopes_by_identity: dict[FunctionalDocumentIdentity, list[str]] = {}
    placements_by_identity: dict[
        FunctionalDocumentIdentity, list[FunctionalDocumentPlacement]
    ] = {}
    for declaration in declarations:
        for identity in declaration.documents:
            scopes_by_identity.setdefault(identity, []).append(declaration.scope)
        for entry in declaration.placements:
            placements_by_identity.setdefault(
                entry.placement.document.identity, []
            ).append(entry.placement)
    for identity in sorted(
        scopes_by_identity, key=lambda item: (item.repository_id, item.document_ref)
    ):
        delivered_scopes = sorted(set(scopes_by_identity[identity]))
        if len(delivered_scopes) <= 1:
            continue
        for scope in delivered_scopes:
            findings.append(
                _finding(
                    FunctionalPyramidFindingReason.DUPLICATE_DOCUMENT_SOURCE,
                    f"{identity.repository_id}:{identity.document_ref} is listed in "
                    "more than one declaration source: "
                    + ", ".join(repr(item) for item in delivered_scopes),
                    "list the canonical document in exactly one source",
                    repository_id=repository_id,
                    directory=scope,
                )
            )
    for identity in sorted(
        placements_by_identity, key=lambda item: (item.repository_id, item.document_ref)
    ):
        placements = placements_by_identity[identity]
        layers = {placement.document.layer for placement in placements}
        if len(layers) > 1:
            for placement in placements:
                findings.append(
                    _finding(
                        FunctionalPyramidFindingReason.DUPLICATE_DOCUMENT_LAYER,
                        f"{identity.repository_id}:{identity.document_ref} is placed "
                        "at more than one layer: "
                        + ", ".join(
                            layer.value for layer in _LAYER_ORDER if layer in layers
                        ),
                        "split or extract the content so each document owns one layer",
                        repository_id=repository_id,
                        placement=placement,
                    )
                )
        scopes = {placement.scope for placement in placements}
        if len(scopes) > 1:
            for placement in placements:
                findings.append(
                    _finding(
                        FunctionalPyramidFindingReason.DUPLICATE_DOCUMENT_SCOPE,
                        f"{identity.repository_id}:{identity.document_ref} is placed "
                        "at more than one scope: "
                        + ", ".join(repr(scope) for scope in sorted(scopes)),
                        "a canonical document occupies one scope",
                        repository_id=repository_id,
                        placement=placement,
                    )
                )
    return tuple(findings)


def _root_findings(
    repository_ids: frozenset[str],
    index: dict[FunctionalDocumentPlacement, FunctionalDocumentDeclaration],
    prior_findings: tuple[FunctionalPyramidFinding, ...],
    repositories_with_declarations: frozenset[str],
) -> tuple[FunctionalPyramidFinding, ...]:
    invalid_scope_repositories = {
        finding.repository_id
        for finding in prior_findings
        if finding.reason is FunctionalPyramidFindingReason.INVALID_PLACEMENT_SCOPE
        and finding.repository_id is not None
    }
    findings: list[FunctionalPyramidFinding] = []
    for repository_id in sorted(repository_ids):
        if repository_id not in repositories_with_declarations:
            continue
        if repository_id in invalid_scope_repositories:
            continue
        root_ok = any(
            placement.declaring_repository_id == repository_id
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
                    repository_id=repository_id,
                    directory=".",
                )
            )
    return tuple(findings)


def _structural_findings(
    declarations: tuple[tuple[str, FunctionalPyramidDeclaration], ...],
    *,
    member_ids: frozenset[str],
    available_repositories: frozenset[str],
    declaration_findings: tuple[FunctionalPyramidFinding, ...] = (),
) -> tuple[
    dict[FunctionalDocumentPlacement, FunctionalDocumentDeclaration],
    tuple[FunctionalPyramidFinding, ...],
]:
    by_repository: dict[str, list[FunctionalPyramidDeclaration]] = {}
    for repository_id, declaration in declarations:
        by_repository.setdefault(repository_id, []).append(declaration)
    source_findings: list[FunctionalPyramidFinding] = []
    for repository_id in sorted(by_repository):
        repository_declarations = tuple(by_repository[repository_id])
        source_findings.extend(
            _source_set_findings(repository_id, repository_declarations)
        )
        for declaration in repository_declarations:
            source_findings.extend(_source_local_findings(repository_id, declaration))
        source_findings.extend(
            _complete_membership_findings(repository_id, repository_declarations)
        )
    index, duplicate_findings = _indexes(declarations)
    findings = (
        *declaration_findings,
        *source_findings,
        *duplicate_findings,
        *_member_availability_findings(member_ids, available_repositories),
        *_placement_graph_findings(
            index,
            member_ids=member_ids,
            available_repositories=available_repositories,
        ),
        *_cycle_findings(index),
    )
    findings = (
        *findings,
        *_root_findings(
            member_ids,
            index,
            findings,
            frozenset(by_repository),
        ),
    )
    return index, _ordered_findings(findings)


def _graph_findings(
    members: tuple[FunctionalPyramidMemberView, ...],
    declarations: tuple[tuple[str, FunctionalPyramidDeclaration], ...],
    available_repositories: frozenset[str],
    declaration_findings: tuple[FunctionalPyramidFinding, ...] = (),
) -> tuple[
    dict[FunctionalDocumentPlacement, FunctionalDocumentDeclaration],
    tuple[FunctionalPyramidFinding, ...],
]:
    return _structural_findings(
        declarations,
        member_ids=frozenset(member.repository_id for member in members),
        available_repositories=available_repositories,
        declaration_findings=declaration_findings,
    )


def evaluate_functional_pyramid_source_structure(
    declarations: tuple[tuple[str, FunctionalPyramidDeclaration], ...],
    declaration_findings: tuple[FunctionalPyramidFinding, ...] = (),
) -> tuple[FunctionalPyramidFinding, ...]:
    """Pure structural validation over one declared source set (installer preflight)."""
    member_ids = frozenset(repository_id for repository_id, _ in declarations)
    _, findings = _structural_findings(
        declarations,
        member_ids=member_ids,
        available_repositories=member_ids,
        declaration_findings=declaration_findings,
    )
    return findings


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
        (
            FunctionalPyramidHealth.VALID
            if not findings
            else FunctionalPyramidHealth.DEGRADED
        ),
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
        and (directory is None or directory_scope_contains(placement.scope, directory))
    ]
    return tuple(sorted(selected, key=_placement_sort_key))


def _closure(
    initial: _collections_abc.Iterable[FunctionalDocumentPlacement],
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
            if (
                not isinstance(parent, str)
                and parent in index
                and _governing_edge_is_valid(placement, parent)
            ):
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
                and _governing_edge_is_valid(child, placement)
            ),
            key=_placement_sort_key,
        )
    )


def _relevant_findings(
    findings: tuple[FunctionalPyramidFinding, ...],
    *,
    repository_id: str,
    closure: tuple[FunctionalDocumentPlacement, ...],
    selected_directories: tuple[str, ...],
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
        if finding.directory is not None and finding.repository_id is not None:
            repository_relevant = (
                finding.repository_id == repository_id
                or finding.repository_id in relevant_repositories
            )
            source_affects_selection = any(
                directory_scope_contains(finding.directory, directory)
                for directory in selected_directories
            )
            governs_closure = any(
                placement.declaring_repository_id == finding.repository_id
                and directory_scope_contains(finding.directory, placement.scope)
                for placement in closure
            )
            if repository_relevant and (source_affects_selection or governs_closure):
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
                "parents": (
                    [
                        (
                            "ROOT"
                            if isinstance(parent, str)
                            else {
                                "declaring_repository_id": parent.declaring_repository_id,
                                "document_repository_id": parent.document.repository_id,
                                "document_ref": parent.document.document_ref,
                                "layer": parent.document.layer.value,
                                "scope": parent.scope,
                            }
                        )
                        for parent in index[placement].governing_placements
                    ]
                    if placement in index
                    else []
                ),
            }
            for placement in closure
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
    repository_id: str,
    seeds: tuple[tuple[str | None, EvidenceScope | None], ...],
    selection: str | EvidenceScope,
    index: dict[FunctionalDocumentPlacement, FunctionalDocumentDeclaration],
    structural: tuple[FunctionalPyramidFinding, ...],
    authority_bindings: dict[tuple[str, str], AuthorityBinding],
) -> FunctionalPyramidResolution:
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
    selected_directories = tuple(
        dict.fromkeys("." if directory is None else directory for directory, _ in seeds)
    )
    unresolved = _relevant_findings(
        structural,
        repository_id=repository_id,
        closure=closure,
        selected_directories=selected_directories,
    )
    routes = tuple(
        FunctionalDocumentRoute(
            placement=placement,
            authority=authority_bindings[
                (placement.document.repository_id, placement.document.document_ref)
            ],
            governing_placements=index[placement].governing_placements,
            downstream_placements=_downstream(placement, index),
        )
        for placement in closure
        if placement in index
        and (
            placement.document.repository_id,
            placement.document.document_ref,
        )
        in authority_bindings
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
    if isinstance(selection, str):
        directory_selection = selection
        semantic_selection = None
        selection_identity: object = {"directory": selection}
    else:
        directory_selection = None
        semantic_selection = selection
        selection_identity = {
            "semantic_scope": {
                "paths": list(selection.paths),
                "evidence": [
                    (
                        ref.repository_id,
                        ref.locator,
                        ref.revision_or_fingerprint,
                    )
                    for ref in selection.evidence_refs
                ],
            }
        }
    identity = _route_identity(
        repository_id=repository_id,
        selection=selection_identity,
        closure=closure,
        index=index,
    )
    return FunctionalPyramidResolution(
        view=FunctionalPyramidView(
            pyramid_id=pyramid_id,
            version=version,
            status=status,
            directory=directory_selection,
            semantic_scope=semantic_selection,
            placements=closure,
            unresolved=unresolved,
            declared_layers=declared,
            absent_layers=absent,
        ),
        identity=identity,
        routes=routes,
        provenance=tuple(provenance),
    )


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
) -> FunctionalPyramidResolution:
    """Resolve the exact effective semantic scope through document placements."""
    index, structural = _graph_findings(
        members,
        declarations,
        available_repositories,
        declaration_findings,
    )
    seeds = tuple(
        (directory, portion)
        for directory, portion in _semantic_seeds(surface, semantic_scope)
    )
    return _resolve(
        pyramid_id=pyramid_id,
        version=version,
        repository_id=surface.repository_id,
        seeds=seeds,
        selection=semantic_scope,
        index=index,
        structural=structural,
        authority_bindings=authority_bindings,
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
) -> FunctionalPyramidResolution:
    """Resolve one exact directory as a point in the repository tree."""
    normalized = normalize_directory_scope(directory)
    index, structural = _graph_findings(
        members,
        declarations,
        available_repositories,
        declaration_findings,
    )
    return _resolve(
        pyramid_id=pyramid_id,
        version=version,
        repository_id=repository_id,
        seeds=((normalized, None),),
        selection=normalized,
        index=index,
        structural=structural,
        authority_bindings=authority_bindings,
    )
