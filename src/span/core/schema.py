"""Canonical schema projection (Addendum I S3 §5.3).

Deterministic type projection using dataclass fields, evaluated type
hints, enums, literals, tuples, defaults, and tagged unions. Uses
$defs references and $type constants. Rejects unknown fields with
additionalProperties:false. Top-level transport requests omit the
carrier tag as today; nested carriers retain theirs. Generates only
the reachable definition closure for each operation. A generated
schema is a projection, not a second domain contract: the canonical
decoder remains the only ingress parser.
"""

from __future__ import annotations

import dataclasses as _dataclasses
import datetime as _datetime
import enum as _enum
import types as _types
import typing as _typing

__all__ = [
    "schema_for_request",
    "definition_closure",
    "from_wire",
    "to_wire",
    "to_wire_root",
    "compact_payload",
]


def _is_optional(hint: object) -> tuple[bool, object]:
    origin = _typing.get_origin(hint)
    args = _typing.get_args(hint)
    if origin is _typing.Union or origin is _types.UnionType:
        non_none = tuple(a for a in args if a is not type(None))
        if len(non_none) == len(args) - 1 and len(non_none) == 1:
            return True, non_none[0]
    return False, hint


def _project_hint(
    hint: object, defs: dict[str, dict], seen: set[str]
) -> dict:
    nullable, inner = _is_optional(hint)
    schema = _project_inner(inner, defs, seen)
    if nullable:
        schema = {"anyOf": [schema, {"type": "null"}]}
    return schema


def _project_inner(
    hint: object, defs: dict[str, dict], seen: set[str]
) -> dict:
    origin = _typing.get_origin(hint)
    args = _typing.get_args(hint)
    if hint is None or hint is type(None):
        return {"type": "null"}
    if hint is str:
        return {"type": "string"}
    if hint is bool:
        return {"type": "boolean"}
    if hint is int:
        return {"type": "integer"}
    if hint is float:
        return {"type": "number"}
    if hint is _datetime.datetime:
        return {"type": "string", "format": "date-time"}
    if isinstance(hint, type) and issubclass(hint, _enum.Enum):
        return {
            "type": "string",
            "enum": [member.value for member in hint],
        }
    if origin is _typing.Literal:
        values: list[str] = []
        for arg in args:
            if isinstance(arg, _enum.Enum):
                values.append(arg.value)
            else:
                values.append(arg)
        # JSON Schema string enum; decoder maps wire strings back to
        # canonical enum members (S6 §5.6 codec fix).
        return {"type": "string", "enum": sorted(set(values), key=str)}
    if origin in (tuple, list) or hint in (tuple, list):
        item_hint = args[0] if args else _typing.Any
        if item_hint is _typing.Any:
            return {"type": "array", "items": {}}
        return {
            "type": "array",
            "items": _project_hint(item_hint, defs, seen),
        }
    if origin is _typing.Union or origin is _types.UnionType:
        # Tagged dataclass unions dispatch on $type; other unions are anyOf.
        dataclass_members = [
            a
            for a in args
            if isinstance(a, type)
            and hasattr(a, "__dataclass_fields__")
        ]
        if dataclass_members and all(
            isinstance(a, type) for a in args if a is not type(None)
        ):
            refs = []
            for member in args:
                if member is type(None):
                    refs.append({"type": "null"})
                elif isinstance(member, type) and hasattr(
                    member, "__dataclass_fields__"
                ):
                    _ensure_def(member, defs, seen)
                    refs.append({
                        "$ref": (
                            f"#/$defs/{member.__name__}__tag"
                        )
                    })
                else:
                    refs.append(_project_hint(member, defs, seen))
            if len(refs) == 1:
                return refs[0]
            return {"anyOf": refs}
        return {
            "anyOf": [
                _project_hint(a, defs, seen) for a in args
            ]
        }
    if isinstance(hint, type) and hasattr(hint, "__dataclass_fields__"):
        _ensure_def(hint, defs, seen)
        return {"$ref": f"#/$defs/{hint.__name__}"}
    # No opaque-object fallback: every canonical carrier hint has an
    # explicit projection above. An unprojectable hint is a programming
    # defect and must fail deterministically, never advertise a shape
    # the decoder does not implement.
    raise ValueError(f"unprojectable schema hint: {hint!r}")


def _tag_names(schema: dict) -> list[str]:
    """Canonical member names advertised by a tagged union projection."""
    names: list[str] = []
    ref = schema.get("$ref")
    if isinstance(ref, str) and ref.endswith("__tag"):
        names.append(ref.rsplit("/", 1)[-1][: -len("__tag")])
    for key in ("anyOf", "oneOf"):
        for branch in schema.get(key, []) or []:
            if isinstance(branch, dict):
                names.extend(_tag_names(branch))
    if schema.get("type") == "array":
        items = schema.get("items")
        if isinstance(items, dict):
            names.extend(_tag_names(items))
    return list(dict.fromkeys(names))


def _ensure_def(cls: type, defs: dict[str, dict], seen: set[str]) -> None:
    name = cls.__name__
    if name in defs or name in seen:
        return
    seen.add(name)
    # Fail fast on unresolvable annotations: advertised defaults must
    # equal decoder behavior, and a guessed projection would violate
    # schema/decoder agreement.
    hints = _typing.get_type_hints(cls)
    properties: dict[str, dict] = {}
    required: list[str] = []
    for field in _dataclasses.fields(cls):
        field_schema = _project_hint(
            hints.get(field.name, str), defs, seen
        )
        tags = _tag_names(field_schema)
        if len(tags) >= 2:
            field_schema = {
                **field_schema,
                "description": (
                    "Allowed $type values: " + ", ".join(tags) + "."
                ),
            }
        # Defaults advertised equal canonical decoder defaults.
        if (
            field.default is not _dataclasses.MISSING
            or field.default_factory is not _dataclasses.MISSING  # type: ignore[misc]
        ):
            if field.default is not _dataclasses.MISSING:
                try:
                    default = field.default
                    if isinstance(default, _enum.Enum):
                        default = default.value
                    elif isinstance(default, tuple):
                        default = list(default)
                    field_schema = dict(field_schema)
                    field_schema["default"] = default
                except Exception:
                    pass
        else:
            required.append(field.name)
        properties[field.name] = field_schema
    # J-8/S6.2: the tag is a property of the field POSITION, not the
    # definition. Each carrier projects an untagged ingress form for
    # statically unambiguous use sites and a tagged ingress form for
    # genuine dataclass-union branches. The accepted grammar is
    # unchanged; only the advertised representation differs.
    definition: dict[str, object] = {
        "type": "object",
        "properties": properties,
        "required": sorted(required),
        "additionalProperties": False,
    }
    defs[name] = definition
    tagged_properties = dict(properties)
    tagged_properties["$type"] = {"const": name}
    defs[f"{name}__tag"] = {
        "type": "object",
        "properties": tagged_properties,
        "required": sorted([*required, "$type"]),
        "additionalProperties": False,
    }


def definition_closure(root: type) -> dict[str, dict]:
    """Reachable definition closure for one root carrier."""
    defs: dict[str, dict] = {}
    _ensure_def(root, defs, set())
    return defs


def _prune_defs(schema: dict, defs: dict[str, dict]) -> dict[str, dict]:
    """Keep only definitions reachable from the root schema."""
    used: set[str] = set()

    def walk(node: object) -> None:
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/$defs/"):
                name = ref.rsplit("/", 1)[-1]
                if name in defs and name not in used:
                    used.add(name)
                    walk(defs[name])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(schema)
    return {name: definition for name, definition in defs.items()
            if name in used}


def schema_for_request(
    root: type,
    *,
    omit_type_tag: bool = True,
    description: str = "",
) -> dict:
    """Project one top-level transport request schema.

    The top-level omits the carrier tag as today; nested carriers
    retain theirs. Only the reachable closure is emitted.
    """
    defs: dict[str, dict] = {}
    hints = _typing.get_type_hints(root)
    properties: dict[str, dict] = {}
    required: list[str] = []
    for field in _dataclasses.fields(root):
        field_schema = _project_hint(
            hints.get(field.name, str), defs, set()
        )
        # Merge nested defs discovered during projection.
        # _project_hint populates a throwaway defs; re-collect via closure.
        properties[field.name] = field_schema
        if (
            field.default is _dataclasses.MISSING
            and field.default_factory is _dataclasses.MISSING  # type: ignore[misc]
        ):
            required.append(field.name)
    # Collect reachable defs from all field types.
    full_defs: dict[str, dict] = {}
    for field in _dataclasses.fields(root):
        hint = hints.get(field.name, str)
        _collect_hint_defs(hint, full_defs, set())
    # Also include the root's own nested closure for dataclass fields.
    schema: dict[str, object] = {
        "type": "object",
        "description": description,
        "properties": properties,
        "required": sorted(required),
        "additionalProperties": False,
    }
    full_defs = _prune_defs(schema, full_defs)
    if full_defs:
        schema["$defs"] = full_defs
    if not omit_type_tag:
        schema["properties"] = dict(properties)
        schema["properties"]["$type"] = {"const": root.__name__}
    return schema


def _collect_hint_defs(
    hint: object, defs: dict[str, dict], seen: set[str]
) -> None:
    origin = _typing.get_origin(hint)
    args = _typing.get_args(hint)
    nullable, inner = _is_optional(hint)
    if nullable:
        _collect_hint_defs(inner, defs, seen)
        return
    if origin in (tuple, list):
        for arg in args:
            _collect_hint_defs(arg, defs, seen)
        return
    if origin is _typing.Union or origin is _types.UnionType:
        for arg in args:
            if arg is type(None):
                continue
            _collect_hint_defs(arg, defs, seen)
        return
    if origin is _typing.Literal:
        return
    if isinstance(hint, type):
        if issubclass(hint, _enum.Enum):
            return
        if hasattr(hint, "__dataclass_fields__"):
            _ensure_def(hint, defs, seen)
            # Recurse into field hints to close the reachable set.
            try:
                hints = _typing.get_type_hints(hint)
            except Exception:
                return
            for field_hint in hints.values():
                _collect_hint_defs(field_hint, defs, seen)


# ---------------------------------------------------------------------------
# Compact wire codec (J-8/S6). Tagging is a property of the field POSITION.
# ---------------------------------------------------------------------------

def _dataclass_members(hint: object) -> list:
    origin = _typing.get_origin(hint)
    args = _typing.get_args(hint)
    if origin is _typing.Union or origin is _types.UnionType:
        return [
            a for a in args
            if isinstance(a, type) and _dataclasses.is_dataclass(a)
        ]
    return []


def from_wire(root: type, payload: dict) -> object:
    """Strict ingress for the compact agent-facing grammar (J-8/S6.2)."""
    from span.core import model as _m

    if not isinstance(payload, dict):
        raise ValueError("request payload must be an object")
    if "$type" in payload:
        raise ValueError("top-level $type is never supplied on the wire")
    tagged = _inject(root, payload, "")
    return _m.from_canonical(root, tagged)


def _inject(hint: object, value: object, path: str) -> object:
    if value is None:
        return None
    origin = _typing.get_origin(hint)
    args = _typing.get_args(hint)
    if origin is _typing.Union or origin is _types.UnionType:
        dms = [
            a for a in args
            if isinstance(a, type) and _dataclasses.is_dataclass(a)
        ]
        non_none = [a for a in args if a is not type(None)]
        if len(dms) >= 2:
            if not isinstance(value, dict) or not isinstance(
                value.get("$type"), str
            ):
                raise ValueError(
                    f"missing $type discriminator at {path or 'root'}"
                )
            tag = value["$type"]
            member = next((mm for mm in dms if mm.__name__ == tag), None)
            if member is None:
                raise ValueError(
                    f"unknown $type {tag!r} at {path or 'root'}"
                )
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


def _inject_dataclass(
    cls: type, value: object, path: str, *, keep_tag: bool
) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"expected object at {path or cls.__name__}")
    hints = _typing.get_type_hints(cls)
    fields = {field.name: field for field in _dataclasses.fields(cls)}
    at = f"{path}: " if path else ""
    faults: list[str] = []
    if "$type" in value and not keep_tag:
        faults.append(
            "unexpected $type at unambiguous position: "
            f"{path or cls.__name__}"
        )
    # The tagging pass is the first ingress pass, so it also reports the
    # field-shape faults the strict decoder would raise later; otherwise
    # a tag fault and an unknown/missing field cost two round trips.
    # Texts match the decoder's for the single-fault case.
    unknown = sorted(
        key for key in value if key != "$type" and key not in fields
    )
    if unknown:
        faults.append(f"{at}unknown fields for {cls.__name__}: {unknown}")
    for field in fields.values():
        if field.name in value:
            continue
        if (
            field.default is _dataclasses.MISSING
            and field.default_factory is _dataclasses.MISSING  # type: ignore[misc]
        ):
            faults.append(
                f"{at}missing field {field.name!r} for {cls.__name__}"
            )
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
        dms = [
            a for a in args
            if isinstance(a, type) and _dataclasses.is_dataclass(a)
        ]
        if len(dms) >= 2:
            tag = value.get("$type") if isinstance(value, dict) else None
            member = next(
                (mm for mm in dms if mm.__name__ == tag), None
            )
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
        return [
            to_wire(v, item)
            for v in value  # type: ignore[union-attr]
        ]
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

    Migration/utility projection mirroring ``from_wire``: a single-dataclass
    field drops ``$type``; a genuine dataclass union keeps it. Unknown
    transport-only keys pass through unchanged.
    """
    compacted = _compact_dataclass(root, payload, keep_tag=False)
    return compacted if isinstance(compacted, dict) else payload
