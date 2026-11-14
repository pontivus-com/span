"""Shared structural request rules for decoding and JSON Schema projection."""

from __future__ import annotations

import dataclasses as _dataclasses
import enum as _enum
import typing as _typing


@_dataclasses.dataclass(frozen=True)
class PresenceField:
    """One field whose active/absent state participates in a structural rule."""

    name: str
    non_empty: bool = False


@_dataclasses.dataclass(frozen=True)
class EqualsCondition:
    """Apply a rule when one field equals the declared wire value."""

    name: str
    value: object


@_dataclasses.dataclass(frozen=True)
class PresenceCondition:
    """Apply a rule when one field is active or inactive."""

    field: PresenceField
    present: bool


StructuralCondition = EqualsCondition | PresenceCondition


@_dataclasses.dataclass(frozen=True)
class PresenceRule:
    """Constrain how many fields are active under optional conditions."""

    fields: tuple[PresenceField, ...]
    minimum: int
    maximum: int
    when: tuple[StructuralCondition, ...] = ()
    label: str = "structural fields"

    def __post_init__(self) -> None:
        if self.minimum < 0 or self.maximum < self.minimum:
            raise ValueError("invalid structural presence bounds")
        if self.maximum > len(self.fields):
            raise ValueError("structural presence maximum exceeds field count")


def _wire_value(value: object) -> object:
    return value.value if isinstance(value, _enum.Enum) else value


def _path_value(value: object, name: str) -> object:
    """Resolve one canonical dotted field path without inventing a second shape."""
    current: object = value
    for part in name.split("."):
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(part)
            continue
        try:
            current = vars(current).get(part)
        except TypeError:
            return None
    return current


def _field_value(value: object, field: PresenceField) -> object:
    return _path_value(value, field.name)


def _present(value: object, field: PresenceField) -> bool:
    current = _field_value(value, field)
    if field.non_empty:
        return bool(current)
    return current is not None


def _condition_matches(value: object, condition: StructuralCondition) -> bool:
    if isinstance(condition, EqualsCondition):
        return _wire_value(_path_value(value, condition.name)) == _wire_value(
            condition.value
        )
    return _present(value, condition.field) is condition.present


def validate_structural_rules(value: object) -> None:
    """Apply all canonical structural declarations before stateful work."""

    declared = vars(type(value)).get("__structural_rules__", ())
    rules = _typing.cast(tuple[PresenceRule, ...], declared)
    faults: list[str] = []
    for rule in rules:
        if rule.when and not all(
            _condition_matches(value, condition) for condition in rule.when
        ):
            continue
        active = tuple(field.name for field in rule.fields if _present(value, field))
        count = len(active)
        if count < rule.minimum:
            expected = ", ".join(field.name for field in rule.fields)
            faults.append(
                f"{rule.label} requires at least {rule.minimum} active field(s) "
                f"from: {expected}"
            )
        elif count > rule.maximum:
            names = ", ".join(active)
            faults.append(
                f"{rule.label} permits at most {rule.maximum} active field(s); "
                f"active: {names}"
            )
    if faults:
        raise ValueError("; ".join(faults))


def _nested_field_schema(
    name: str,
    leaf_schema: dict[str, object],
) -> dict[str, object]:
    """Project one dotted canonical field path into object constraints."""
    parts = name.split(".")
    leaf = parts[-1]
    schema: dict[str, object] = {
        "type": "object",
        "required": [leaf],
        "properties": {leaf: leaf_schema},
    }
    for part in reversed(parts[:-1]):
        schema = {
            "type": "object",
            "required": [part],
            "properties": {part: schema},
        }
    return schema


def _active_schema(field: PresenceField) -> dict[str, object]:
    value_schema: dict[str, object]
    if field.non_empty:
        # The runtime rule is truthiness for public string/array/object fields.
        # Reject the JSON empty forms from the same declaration rather than
        # guessing a container kind here.
        value_schema = {"not": {"enum": [None, "", [], {}]}}
    else:
        value_schema = {"not": {"type": "null"}}
    return _nested_field_schema(field.name, value_schema)


def _condition_schema(condition: StructuralCondition) -> dict[str, object]:
    if isinstance(condition, EqualsCondition):
        return _nested_field_schema(
            condition.name,
            {"const": _wire_value(condition.value)},
        )
    active = _active_schema(condition.field)
    return active if condition.present else {"not": active}


def _presence_schema(rule: PresenceRule) -> dict[str, object]:
    field_count = len(rule.fields)
    if rule.minimum == 0 and rule.maximum == field_count:
        return {}
    if rule.minimum == 1 and rule.maximum == field_count:
        return {"anyOf": [_active_schema(field) for field in rule.fields]}
    if rule.minimum == 0 and rule.maximum == 0:
        return {"allOf": [{"not": _active_schema(field)} for field in rule.fields]}
    if rule.minimum == field_count and rule.maximum == field_count:
        return {"allOf": [_active_schema(field) for field in rule.fields]}

    options: list[dict[str, object]] = []
    for mask in range(1 << field_count):
        active_count = mask.bit_count()
        if not rule.minimum <= active_count <= rule.maximum:
            continue
        options.append(
            {
                "allOf": [
                    (
                        _active_schema(field)
                        if mask & (1 << index)
                        else {"not": _active_schema(field)}
                    )
                    for index, field in enumerate(rule.fields)
                ]
            }
        )
    if len(options) == 1:
        return options[0]
    return {"oneOf": options}


def structural_schema_constraints(cls: type) -> list[dict[str, object]]:
    """Compile the same canonical rules into JSON Schema constraints."""

    declared = vars(cls).get("__structural_rules__", ())
    rules = _typing.cast(tuple[PresenceRule, ...], declared)
    constraints: list[dict[str, object]] = []
    for rule in rules:
        consequence = _presence_schema(rule)
        if rule.when:
            constraints.append(
                {
                    "if": {
                        "allOf": [
                            _condition_schema(condition) for condition in rule.when
                        ]
                    },
                    "then": consequence,
                }
            )
        else:
            constraints.append(consequence)
    return constraints
