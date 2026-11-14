"""Wire ingress and egress codec."""

from __future__ import annotations

import dataclasses as _dataclasses
import types as _types
import typing as _typing


_PUBLIC_TYPE_TAGS: dict[str, str] = {
    "span.core.model.answers.Answer": "Answer",
    "span.core.model.answers.Gap": "Gap",
    "span.core.model.answers.AmbiguousSurface": "AmbiguousSurface",
    "span.core.model.answers.EvidencePage": "EvidencePage",
    "span.core.model.answers.Rejected": "Rejected",
    "span.core.model.answers.Unavailable": "Unavailable",
    "span.core.model.answers.Changed": "Changed",
    "span.core.model.answers.Challenged": "Challenged",
    "span.core.model.answers.SurfaceDeclared": "SurfaceDeclared",
    "span.core.model.outcomes.UnderstandingRecorded": "UnderstandingRecorded",
    "span.core.model.outcomes.VerificationRecorded": "VerificationRecorded",
    "span.core.model.understanding.RecordedQuestionSelector": "RecordedQuestionSelector",
    "span.core.model.understanding.CurrentUnderstandingSelector": "CurrentUnderstandingSelector",
    "span.core.model.understanding.UnderstandingSnapshotSelector": "UnderstandingSnapshotSelector",
    "span.core.model.understanding.ReceiptRetrievalSelector": "ReceiptRetrievalSelector",
    "span.core.model.understanding.SupportedConclusion": "SupportedConclusion",
    "span.core.model.understanding.WithdrawnConclusion": "WithdrawnConclusion",
    "span.core.model.understanding.UnresolvedChallengeRecord": "UnresolvedChallengeRecord",
    "span.core.model.understanding.ResolvedChallengeRecord": "ResolvedChallengeRecord",
    "span.core.model.support.SourceSupport": "SourceSupport",
    "span.core.model.support.AuthoritySupportDependency": "AuthoritySupport",
    "span.core.model.support.PremiseSupport": "PremiseSupport",
    "span.core.model.support.DiscoverySupport": "DiscoverySupport",
    "span.core.model.support.SupportUnavailable": "SupportUnavailable",
    "span.core.model.surfaces.SurfaceStatus": "SurfaceStatus",
    "span.core.model.surfaces.SurfaceStatusUnavailable": "SurfaceStatusUnavailable",
    "span.core.model.investigation.AdmittedEvidence": "AdmittedEvidence",
    "span.core.model.investigation.AlreadyAdmittedEvidence": "AlreadyAdmittedEvidence",
    "span.core.model.investigation.EvidenceSourceFailure": "EvidenceSourceFailure",
    "span.core.model.investigation.OmittedEvidence": "OmittedEvidence",
    "span.core.schema.record_wire.SourceSupportWire": "source",
    "span.core.schema.record_wire.AdmittedSourceSupportWire": "admitted_source",
    "span.core.schema.record_wire.AuthoritySupportWire": "authority",
    "span.core.schema.record_wire.PremiseSupportWire": "premise",
    "span.core.schema.record_wire.DiscoveryBoundarySupportWire": "discovery",
    "span.core.schema.record_wire.AdmittedDiscoverySupportWire": "admitted_discovery",
    "span.core.schema.record_wire.UnresolvedDispositionWire": "unresolved",
    "span.core.schema.record_wire.ResolvedDispositionWire": "resolved",
}

_PUBLIC_SCHEMA_NAMES: dict[str, str] = {
    "span.core.schema.record_wire.RangeWire": "Range",
    "span.core.schema.record_wire.SourceSupportWire": "SourceSupport",
    "span.core.schema.record_wire.AdmittedSourceSupportWire": "AdmittedSourceSupport",
    "span.core.schema.record_wire.AuthoritySupportWire": "AuthoritySupport",
    "span.core.schema.record_wire.PremiseSupportWire": "PremiseSupport",
    "span.core.schema.record_wire.DiscoveryScopeWire": "DiscoveryScope",
    "span.core.schema.record_wire.DiscoveryBoundarySupportWire": "DiscoveryBoundarySupport",
    "span.core.schema.record_wire.AdmittedDiscoverySupportWire": "AdmittedDiscoverySupport",
    "span.core.schema.record_wire.GapWire": "GapInput",
    "span.core.schema.record_wire.AddConclusionWire": "AddConclusion",
    "span.core.schema.record_wire.ConfirmConclusionWire": "ConfirmConclusion",
    "span.core.schema.record_wire.CorrectConclusionWire": "CorrectConclusion",
    "span.core.schema.record_wire.ReplaceActionWire": "ReplaceConclusion",
    "span.core.schema.record_wire.WithdrawActionWire": "WithdrawConclusion",
    "span.core.schema.record_wire.ConclusionRefWire": "ConclusionRef",
    "span.core.schema.record_wire.UnresolvedDispositionWire": "UnresolvedDisposition",
    "span.core.schema.record_wire.ResolvedDispositionWire": "ResolvedDisposition",
    "span.core.schema.record_wire.SurfaceKeyWire": "SurfaceKeyInput",
    "span.core.schema.record_wire.SurfaceBoundaryWire": "SurfaceBoundaryInput",
    "span.core.schema.record_wire.SurfaceWire": "SurfaceInput",
    "span.core.schema.record_wire.VerificationRunWire": "VerificationRunInput",
    "span.core.schema.record_wire.RecordActionsWire": "RecordActions",
    "span.core.schema.record_wire.RecordRequestWire": "RecordRequest",
}

def _type_key(cls: type) -> str:
    return f"{cls.__module__}.{cls.__qualname__}"


def public_type_tag(cls: type) -> str:
    key = _type_key(cls)
    try:
        return _PUBLIC_TYPE_TAGS[key]
    except KeyError:
        raise TypeError(
            "public union member has no declared protocol discriminator"
        ) from None


def public_schema_name(cls: type) -> str:
    key = _type_key(cls)
    return _PUBLIC_SCHEMA_NAMES.get(key, cls.__name__)


def from_wire(root: object, payload: dict) -> object:
    """Strict ingress for the compact agent-facing grammar (J-8/S6.2)."""
    from span.core import model as _m

    if not isinstance(payload, dict):
        raise ValueError("request payload must be an object")
    if "$type" in payload:
        raise ValueError("top-level $type is never supplied on the wire")
    tagged = _inject(root, payload, "")
    return _m.from_canonical(_typing.cast(type, root), tagged)


def _inject(hint: object, value: object, path: str) -> object:
    if value is None:
        return None
    origin = _typing.get_origin(hint)
    args = _typing.get_args(hint)
    if origin is _typing.Union or origin is _types.UnionType:
        dms = [a for a in args if isinstance(a, type) and _dataclasses.is_dataclass(a)]
        non_none = [a for a in args if a is not type(None)]
        if len(dms) >= 2:
            if not isinstance(value, dict) or not isinstance(value.get("$type"), str):
                accepted = ", ".join(public_type_tag(member) for member in dms)
                raise ValueError(
                    f"missing $type discriminator at {path or 'root'} "
                    f"(accepted: {accepted})"
                )
            tag = value["$type"]
            member = next((mm for mm in dms if public_type_tag(mm) == tag), None)
            if member is None:
                raise ValueError(f"unknown $type {tag!r} at {path or 'root'}")
            return _inject_dataclass(member, value, path, keep_tag=True)
        if len(dms) == 1 and len(non_none) == 1:
            return _inject_dataclass(dms[0], value, path, keep_tag=False)
        return value
    if isinstance(hint, type) and _dataclasses.is_dataclass(hint):
        return _inject_dataclass(hint, value, path, keep_tag=False)
    if origin in (tuple, list):
        if not isinstance(value, list):
            raise ValueError(f"expected list at {path or 'root'}, got {value!r}")
        item = args[0] if args else None
        # Aggregate sibling faults so one call reports every bad member
        # instead of the caller discovering them one round trip at a
        # time; a single fault keeps its exact previous text.
        injected: list[object] = []
        faults: list[str] = []
        for i, v in enumerate(value):
            try:
                injected.append(_inject(item, v, f"{path}[{i}]"))
            except ValueError as exc:
                faults.append(str(exc))
                injected.append(v)
        if faults:
            raise ValueError("; ".join(faults))
        return injected
    return value


def _inject_dataclass(cls: type, value: object, path: str, *, keep_tag: bool) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"expected object at {path or cls.__name__}")
    hints = _typing.get_type_hints(cls)
    fields = {field.name: field for field in _dataclasses.fields(cls)}
    at = f"{path}: " if path else ""
    faults: list[str] = []
    if "$type" in value and not keep_tag and value["$type"] != public_type_tag(cls):
        # A redundant tag that names the only candidate carrier is accepted:
        # it carries no ambiguity. A tag naming anything else is a mistake.
        faults.append(
            "unexpected $type at unambiguous position: "
            f"{path or public_schema_name(cls)}; this position accepts "
            f"{public_schema_name(cls)} without a $type"
        )
    # The tagging pass is the first ingress pass, so it also reports the
    # field-shape faults the strict decoder would raise later; otherwise
    # a tag fault and an unknown/missing field cost two round trips.
    # Texts match the decoder's for the single-fault case.
    unknown = sorted(key for key in value if key != "$type" and key not in fields)
    if unknown:
        faults.append(f"{at}unknown fields for {cls.__name__}: {unknown}")
    for field in fields.values():
        if field.name in value:
            continue
        if (
            field.default is _dataclasses.MISSING
            and field.default_factory is _dataclasses.MISSING  # type: ignore[misc]
        ):
            faults.append(f"{at}missing field {field.name!r} for {cls.__name__}")
    out: dict = {"$type": cls.__name__}
    for key, v in value.items():
        if key == "$type" or key not in fields:
            continue
        child_path = f"{path}.{key}" if path else key
        try:
            out[key] = _inject(hints.get(key), v, child_path)
        except ValueError as exc:
            faults.append(str(exc))
            out[key] = v
    if faults:
        raise ValueError("; ".join(faults))
    return out


def to_wire(value: object, hint: object) -> object:
    """Project a canonical object to the compact grammar (S6.4)."""
    if value is None:
        return None
    origin = _typing.get_origin(hint)
    args = _typing.get_args(hint)
    if origin is _typing.Union or origin is _types.UnionType:
        dms = [a for a in args if isinstance(a, type) and _dataclasses.is_dataclass(a)]
        if len(dms) >= 2:
            tag = value.get("$type") if isinstance(value, dict) else None
            member = next((mm for mm in dms if mm.__name__ == tag), None)
            if member is None:
                return value
            return _compact_dataclass(member, value, keep_tag=True)
        if len(dms) == 1:
            return _compact_dataclass(dms[0], value, keep_tag=False)
        return value
    if isinstance(hint, type) and _dataclasses.is_dataclass(hint):
        return _compact_dataclass(hint, value, keep_tag=False)
    if origin in (tuple, list):
        if not isinstance(value, list):
            raise TypeError(f"expected canonical list, got {value!r}")
        item = args[0] if args else None
        return [to_wire(v, item) for v in value]
    return value


def to_wire_root(cls: type, canonical: object) -> object:
    """Egress root: retain the root result ``$type`` (S6.4)."""
    return _compact_dataclass(cls, canonical, keep_tag=True)


def _compact_dataclass(cls: type, value: object, *, keep_tag: bool) -> object:
    if not isinstance(value, dict):
        return value
    hints = _typing.get_type_hints(cls)
    out: dict = {}
    for key, v in value.items():
        if key == "$type":
            if keep_tag:
                out[key] = public_type_tag(cls)
            continue
        out[key] = to_wire(v, hints.get(key))
    return out


def compact_payload(root: type, payload: dict) -> dict:
    """Compact a fully-tagged transport payload to the agent-facing grammar.

    Wire projection mirroring ``from_wire``: a single-dataclass
    field drops ``$type``; a genuine dataclass union keeps it. Unknown
    transport-only keys pass through unchanged.
    """
    compacted = _compact_dataclass(root, payload, keep_tag=False)
    return compacted if isinstance(compacted, dict) else payload
