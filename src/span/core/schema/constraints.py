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


def _field_value(value: object, field: PresenceField) -> object:
    return vars(value).get(field.name)


def _present(value: object, field: PresenceField) -> bool:
    current = _field_value(value, field)
    if field.non_empty:
        return bool(current)
    return current is not None


def _condition_matches(value: object, condition: StructuralCondition) -> bool:
    if isinstance(condition, EqualsCondition):
        return _wire_value(vars(value).get(condition.name)) == _wire_value(
            condition.value
        )
    return _present(value, condition.field) is condition.present


def validate_structural_rules(value: object) -> None:
    """Apply the value's canonical structural declarations before stateful work."""

    declared = vars(type(value)).get("__structural_rules__", ())
    rules = _typing.cast(tuple[PresenceRule, ...], declared)
    for rule in rules:
        if rule.when and not all(
            _condition_matches(value, condition) for condition in rule.when
        ):
            continue
        count = sum(_present(value, field) for field in rule.fields)
        if count < rule.minimum:
            raise ValueError(
                f"{rule.label} requires at least {rule.minimum} active field(s)"
            )
        if count > rule.maximum:
            raise ValueError(
                f"{rule.label} permits at most {rule.maximum} active field(s); "
                "received more than one"
            )


def _active_schema(field: PresenceField) -> dict[str, object]:
    value_schema: dict[str, object]
    if field.non_empty:
        value_schema = {"minItems": 1}
    else:
        value_schema = {"not": {"type": "null"}}
    return {
        "required": [field.name],
        "properties": {field.name: value_schema},
    }


def _condition_schema(condition: StructuralCondition) -> dict[str, object]:
    if isinstance(condition, EqualsCondition):
        return {
            "required": [condition.name],
            "properties": {condition.name: {"const": _wire_value(condition.value)}},
        }
    active = _active_schema(condition.field)
    return active if condition.present else {"not": active}


def _presence_schema(rule: PresenceRule) -> dict[str, object]:
    options: list[dict[str, object]] = []
    field_count = len(rule.fields)
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
