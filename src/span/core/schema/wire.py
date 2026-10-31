"""Wire ingress and egress codec."""

from __future__ import annotations

import dataclasses as _dataclasses
import types as _types
import typing as _typing


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
                accepted = ", ".join(member.__name__ for member in dms)
                raise ValueError(
                    f"missing $type discriminator at {path or 'root'} "
                    f"(accepted: {accepted})"
                )
            tag = value["$type"]
            member = next((mm for mm in dms if mm.__name__ == tag), None)
            if member is None:
                raise ValueError(f"unknown $type {tag!r} at {path or 'root'}")
            return _inject_dataclass(member, value, path, keep_tag=True)
        if len(dms) == 1 and len(non_none) == 1:
            return _inject_dataclass(dms[0], value, path, keep_tag=False)
        return value
    if isinstance(hint, type) and _dataclasses.is_dataclass(hint):
        return _inject_dataclass(hint, value, path, keep_tag=False)
    if origin in (tuple, list):
        item = args[0] if args else None
        # Aggregate sibling faults so one call reports every bad member
        # instead of the caller discovering them one round trip at a
        # time; a single fault keeps its exact previous text.
        injected: list[object] = []
        faults: list[str] = []
        for i, v in enumerate(value):  # type: ignore[union-attr]
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
    if "$type" in value and not keep_tag and value["$type"] != cls.__name__:
        # A redundant tag that names the only candidate carrier is accepted:
        # it carries no ambiguity. A tag naming anything else is a mistake.
        faults.append(
            f"unexpected $type at unambiguous position: {path or cls.__name__}; "
            f"this position accepts {cls.__name__} without a $type"
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
        item = args[0] if args else None
        return [to_wire(v, item) for v in value]  # type: ignore[union-attr]
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
                out[key] = v
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
