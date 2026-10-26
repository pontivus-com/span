"""JSON Schema projection of canonical carriers."""

from __future__ import annotations

import dataclasses as _dataclasses
import datetime as _datetime
import enum as _enum
import types as _types
import typing as _typing


def _is_optional(hint: object) -> tuple[bool, object]:
    origin = _typing.get_origin(hint)
    args = _typing.get_args(hint)
    if origin is _typing.Union or origin is _types.UnionType:
        non_none = tuple(a for a in args if a is not type(None))
        if len(non_none) == len(args) - 1 and len(non_none) == 1:
            return True, non_none[0]
    return False, hint


def _project_hint(hint: object, defs: dict[str, dict], seen: set[str]) -> dict:
    nullable, inner = _is_optional(hint)
    schema = _project_inner(inner, defs, seen)
    if nullable:
        schema = {"anyOf": [schema, {"type": "null"}]}
    return schema


def _project_inner(hint: object, defs: dict[str, dict], seen: set[str]) -> dict:
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
            if isinstance(a, type) and hasattr(a, "__dataclass_fields__")
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
                    refs.append({"$ref": (f"#/$defs/{member.__name__}__tag")})
                else:
                    refs.append(_project_hint(member, defs, seen))
            if len(refs) == 1:
                return refs[0]
            return {"anyOf": refs}
        return {"anyOf": [_project_hint(a, defs, seen) for a in args]}
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


def _project_field(
    cls: type,
    field: _dataclasses.Field,
    hints: dict[str, object],
    defs: dict[str, dict],
    seen: set[str],
) -> tuple[dict, bool]:
    """Project one field the same way at the root and inside ``$defs``.

    Returns ``(schema, required)``. Both callers must use this: the top-level
    request and the nested carrier are the same field, and when this logic was
    duplicated the root silently lost the tag guidance and the defaults.
    """
    field_schema = _project_hint(hints.get(field.name, str), defs, seen)
    tags = _tag_names(field_schema)
    if len(tags) >= 2:
        field_schema = {
            **field_schema,
            "description": ("Allowed $type values: " + ", ".join(tags) + "."),
        }
    if cls.__name__ == "EvidenceScope" and field.name == "paths":
        # The decoder rejects a leading '/'; the schema has to say so.
        field_schema = {
            **field_schema,
            "description": (
                "Repository-relative paths. A leading '/' is rejected; "
                "an absolute path fails closed."
            ),
        }
    has_default = (
        field.default is not _dataclasses.MISSING
        or field.default_factory is not _dataclasses.MISSING  # type: ignore[misc]
    )
    if has_default and field.default is not _dataclasses.MISSING:
        try:
            default = field.default
            if isinstance(default, _enum.Enum):
                default = default.value
            elif isinstance(default, tuple):
                default = list(default)
            field_schema = {**field_schema, "default": default}
        except Exception:
            pass
    return field_schema, not has_default


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
        field_schema, is_required = _project_field(cls, field, hints, defs, seen)
        if is_required:
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
    return {name: definition for name, definition in defs.items() if name in used}


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
        field_schema, is_required = _project_field(root, field, hints, defs, set())
        properties[field.name] = field_schema
        if is_required:
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


def _project_result_hint(hint: object, defs: dict[str, dict]) -> dict:
    """Project a canonical result root with its discriminating tag."""
    nullable, inner = _is_optional(hint)
    origin = _typing.get_origin(inner)
    args = _typing.get_args(inner)
    if origin is _typing.Union or origin is _types.UnionType:
        branches = [_project_result_hint(arg, defs) for arg in args]
        result: dict = {"anyOf": branches}
    elif isinstance(inner, type) and hasattr(inner, "__dataclass_fields__"):
        _ensure_def(inner, defs, set())
        result = {"$ref": f"#/$defs/{inner.__name__}__tag"}
    else:
        result = _project_hint(inner, defs, set())
    if nullable:
        result = {"anyOf": [result, {"type": "null"}]}
    return result


def schema_for_result(root: object) -> dict:
    """Project one canonical result type or tagged result union.

    Result roots are always discriminated, including a single carrier. The
    dataclass definitions remain the sole source of field shape and closed
    object behavior.
    """
    defs: dict[str, dict] = {}
    projected = _project_result_hint(root, defs)
    # MCP 2.3.0 requires an object at the output-schema root. Keep the
    # canonical tagged root/union as the validation branch beneath it.
    if "$ref" in projected:
        schema = {"type": "object", "allOf": [projected]}
    else:
        schema = {"type": "object", **projected}
    full_defs = _prune_defs(schema, defs)
    if full_defs:
        schema = dict(schema)
        schema["$defs"] = full_defs
    return schema


def _collect_hint_defs(hint: object, defs: dict[str, dict], seen: set[str]) -> None:
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
