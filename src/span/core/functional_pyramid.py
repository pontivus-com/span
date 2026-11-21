"""Pure FunctionalScope algebra for Functional Pyramid resolution."""

from __future__ import annotations

import collections.abc as _collections

from span.core.model.functional_pyramid import (
    FunctionalScope,
    FunctionalScopeSelector,
    FunctionalScopeSelectorKind,
)


_KIND_ORDER = {
    FunctionalScopeSelectorKind.REPOSITORY: 0,
    FunctionalScopeSelectorKind.PREFIX: 1,
    FunctionalScopeSelectorKind.PATH: 2,
    FunctionalScopeSelectorKind.SYMBOL: 3,
}


def _selector_sort_key(
    selector: FunctionalScopeSelector,
) -> tuple[int, str, str]:
    return (
        _KIND_ORDER[selector.kind],
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
