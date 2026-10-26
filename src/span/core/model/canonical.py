"""Deterministic canonical encode/decode.

Part of the canonical domain carrier package. Import through
``span.core.model`` rather than this module.
"""

from __future__ import annotations

import datetime as _datetime
import enum as _enum
import types as _types
import typing as _typing
from dataclasses import fields as _fields
from dataclasses import MISSING as _MISSING

from span.core.model.primitives import (
    CanonicalDecodeError,
)


def to_canonical(value: object) -> object:
    """Encode a canonical model value into plain JSON-compatible data."""
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, _enum.Enum):
        return value.value
    if isinstance(value, _datetime.datetime):
        return value.isoformat()
    if isinstance(value, (tuple, list)):
        return [to_canonical(item) for item in value]
    if hasattr(value, "__dataclass_fields__"):
        payload: dict[str, object] = {"$type": type(value).__name__}
        for f in _fields(value):
            payload[f.name] = to_canonical(getattr(value, f.name))
        return payload
    raise TypeError(f"cannot encode {type(value).__name__} canonically")


def _decode_union(members: tuple[object, ...], data: object) -> object:
    # Dataclass members dispatch on the explicit $type tag (never guessed).
    if isinstance(data, dict) and isinstance(data.get("$type"), str):
        tag = data["$type"]
        for member in members:
            if (
                isinstance(member, type)
                and hasattr(member, "__dataclass_fields__")
                and member.__name__ == tag
            ):
                return _decode_dataclass(member, data)
        raise CanonicalDecodeError(f"unknown $type tag: {tag!r}")
    failures = []
    for member in members:
        if member is type(None):
            if data is None:
                return None
            continue
        try:
            return _decode_value(member, data)
        except (CanonicalDecodeError, TypeError, ValueError) as exc:
            failures.append(str(exc))
    raise CanonicalDecodeError(f"no union member matched {data!r}: {failures}")


def _decode_value(hint: object, data: object) -> object:
    origin = _typing.get_origin(hint)
    args = _typing.get_args(hint)

    if hint is None or hint is type(None):
        if data is None:
            return None
        raise CanonicalDecodeError(f"expected null, got {data!r}")

    if origin is _typing.Union or origin is _types.UnionType:
        return _decode_union(args, data)

    if origin is _typing.Literal:
        if data in args:
            return data
        # Enum-valued Literal (S6 §5.6): wire strings map through the
        # literal enum members to the canonical member. Raw JSON
        # "DESCRIPTIVE" decodes to AssertionNature.DESCRIPTIVE, not a
        # failed identity test against enum instances.
        for arg in args:
            if isinstance(arg, _enum.Enum) and data == arg.value:
                return arg
        raise CanonicalDecodeError(f"expected one of {args!r}, got {data!r}")

    if isinstance(hint, type) and issubclass(hint, _enum.Enum):
        try:
            return hint(data)
        except ValueError:
            raise CanonicalDecodeError(
                f"unknown {hint.__name__} value: {data!r}"
            ) from None

    if hint is _datetime.datetime:
        if isinstance(data, str):
            try:
                parsed = _datetime.datetime.fromisoformat(data)
            except ValueError:
                raise CanonicalDecodeError(f"invalid datetime: {data!r}") from None
            return parsed
        raise CanonicalDecodeError(f"expected datetime string, got {data!r}")

    if hint is str:
        if isinstance(data, str):
            return data
        raise CanonicalDecodeError(f"expected string, got {data!r}")

    if hint is bool:
        if isinstance(data, bool):
            return data
        raise CanonicalDecodeError(f"expected bool, got {data!r}")

    if hint is int:
        if isinstance(data, int) and not isinstance(data, bool):
            return data
        raise CanonicalDecodeError(f"expected int, got {data!r}")

    if origin in (tuple, list) or hint in (tuple, list):
        if not isinstance(data, list):
            raise CanonicalDecodeError(f"expected list, got {data!r}")
        item_hint = args[0] if args else _typing.Any
        if item_hint is _typing.Any:
            raise CanonicalDecodeError("untyped collection decoding refused")
        decoded: list[object] = []
        faults: list[str] = []
        for index, item in enumerate(data):
            try:
                decoded.append(_decode_value(item_hint, item))
            except CanonicalDecodeError as exc:
                faults.append(str(exc.with_segment(f"[{index}]")))
        # Aggregate sibling member faults (one reported call, not one per
        # retry); a single fault keeps its exact previous text.
        if faults:
            raise CanonicalDecodeError("; ".join(faults))
        if origin is tuple or hint is tuple:
            return tuple(decoded)
        return decoded

    if isinstance(hint, type) and hasattr(hint, "__dataclass_fields__"):
        if not isinstance(data, dict):
            raise CanonicalDecodeError(f"expected object, got {data!r}")
        return _decode_dataclass(hint, data)

    raise CanonicalDecodeError(f"unsupported decode target: {hint!r}")


def _decode_dataclass(cls: type, data: dict) -> object:
    tag = data.get("$type")
    if tag != cls.__name__:
        raise CanonicalDecodeError(f"expected $type {cls.__name__!r}, got {tag!r}")
    try:
        hints = _typing.get_type_hints(cls)
    except Exception as exc:
        raise CanonicalDecodeError(f"cannot resolve {cls.__name__}: {exc}") from exc
    names = {f.name for f in _fields(cls)}
    unknown = sorted(key for key in data if key != "$type" and key not in names)
    faults: list[str] = []
    if unknown:
        faults.append(f"unknown fields for {cls.__name__}: {unknown}")
    kwargs: dict[str, object] = {}
    for f in _fields(cls):
        if f.name not in data:
            # Missing field is acceptable only when the dataclass supplies
            # a default; unknown fields are never accepted (strict).
            if f.default is _MISSING and f.default_factory is _MISSING:  # type: ignore[misc]
                faults.append(f"missing field {f.name!r} for {cls.__name__}")
            continue
        try:
            kwargs[f.name] = _decode_value(hints[f.name], data[f.name])
        except CanonicalDecodeError as exc:
            faults.append(str(exc.with_segment(f.name)))
    # Aggregate every fault in this object so one call reports all of
    # them; a single fault keeps its exact previous text.
    if faults:
        raise CanonicalDecodeError("; ".join(faults))
    try:
        return cls(**kwargs)  # type: ignore[arg-type]
    except (ValueError, TypeError) as exc:
        raise CanonicalDecodeError(f"invalid {cls.__name__}: {exc}") from exc


def from_canonical(cls: type, data: object) -> object:
    """Decode canonical data into the target model type (strict, exact)."""
    return _decode_value(cls, data)
