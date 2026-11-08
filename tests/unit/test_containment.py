"""Shared containment resolver invariants (FD-5, FD-7, FD-17, FD-21)."""

from __future__ import annotations

import unittest

from span.core import containment
from span.core import model as m


def key(kind: m.SurfaceKind, locator: str) -> m.SurfaceKey:
    return m.SurfaceKey(repository_id="repo-1", kind=kind, locator=locator)


def surface(
    kind: m.SurfaceKind,
    locator: str,
    *,
    paths: tuple[str, ...] = (),
    symbols: tuple[str, ...] = (),
) -> m.Surface:
    return m.Surface(
        key=key(kind, locator),
        boundary=m.SurfaceBoundary(paths=paths, symbols=symbols),
    )


BILLING = surface(
    m.SurfaceKind.SERVICE,
    "billing",
    paths=("src/billing",),
    symbols=("src/shared/money.py::Money",),
)
PLATFORM = surface(m.SurfaceKind.DOMAIN, "platform", paths=("src",))
UNRELATED = surface(m.SurfaceKind.SERVICE, "auth", paths=("src/auth",))


class ContainmentTest(unittest.TestCase):
    def test_path_boundary_is_prefix_exact_or_nested(self) -> None:
        boundary = m.SurfaceBoundary(paths=("src/billing",))
        for locator in ("src/billing", "src/billing/rates.py", "src/billing/x/y.py"):
            self.assertTrue(containment.boundary_contains_path(boundary, locator))
        for locator in ("src/billing_extra/x.py", "src/other.py", "src", ""):
            self.assertFalse(containment.boundary_contains_path(boundary, locator))

    def test_symbol_and_self_membership(self) -> None:
        symbol = key(m.SurfaceKind.SYMBOL, "src/shared/money.py::Money")
        self.assertTrue(containment.surface_contains(BILLING, symbol))
        self.assertTrue(containment.surface_contains(BILLING, BILLING.key))
        self.assertFalse(
            containment.surface_contains(
                BILLING, key(m.SurfaceKind.SYMBOL, "src/shared/money.py::Rate")
            )
        )

    def test_cross_repository_never_contains(self) -> None:
        other = m.SurfaceKey(
            repository_id="repo-2",
            kind=m.SurfaceKind.FILE,
            locator="src/billing/rates.py",
        )
        self.assertFalse(containment.surface_contains(BILLING, other))

    def test_containing_surfaces_is_narrow_to_wide_and_complete(self) -> None:
        member = containment.path_surface("repo-1", "src/billing/rates.py")
        resolved = containment.containing_surfaces(
            (PLATFORM, UNRELATED, BILLING), member
        )
        self.assertEqual(
            resolved,
            (
                member,
                key(m.SurfaceKind.SERVICE, "billing"),
                key(m.SurfaceKind.DOMAIN, "platform"),
            ),
        )

    def test_parent_does_not_create_membership(self) -> None:
        # A parent link with a boundary that excludes the member adds nothing.
        child = m.Surface(
            key=key(m.SurfaceKind.SERVICE, "billing"),
            boundary=m.SurfaceBoundary(paths=("src/billing",)),
            parent=key(m.SurfaceKind.DOMAIN, "platform"),
        )
        member = containment.path_surface("repo-1", "src/auth/login.py")
        self.assertEqual(
            containment.containing_surfaces((child, UNRELATED), member),
            (member, key(m.SurfaceKind.SERVICE, "auth")),
        )

    def test_complete_scope_members_preserve_path_kind_and_reference_repository(self):
        reference = m.EvidenceRef(
            evidence_id=m.EvidenceId("exact-ref"),
            repository_id="repo-2",
            source_kind=m.EvidenceSourceKind.SOURCE_CODE,
            locator="src/a.py::f",
        )
        scope = m.EvidenceScope(
            paths=("src/a.py", "src/a.py::f"), evidence_refs=(reference,)
        )
        members = containment.scope_surfaces("repo-1", scope)
        self.assertEqual(
            set(members),
            {
                key(m.SurfaceKind.FILE, "src/a.py"),
                key(m.SurfaceKind.SYMBOL, "src/a.py::f"),
                m.SurfaceKey("repo-2", m.SurfaceKind.SYMBOL, "src/a.py::f"),
            },
        )
        self.assertFalse(
            containment.surface_contains(
                m.Surface(key=key(m.SurfaceKind.SYMBOL, "src/a.py::f")),
                next(member for member in members if member.repository_id == "repo-2"),
            )
        )

    def test_path_owner_agreement_requires_every_scope_member(self):
        file = m.Surface(key=key(m.SurfaceKind.FILE, "src/a.py"))
        symbol = m.Surface(key=key(m.SurfaceKind.SYMBOL, "src/a.py::f"))
        for owner, paths, expected in (
            (file, ("src/a.py",), True),
            (file, ("src/a.py", "src/b.py"), False),
            (symbol, ("src/a.py::f",), True),
            (symbol, ("src/a.py",), False),
            (symbol, ("src/a.py::g",), False),
        ):
            with self.subTest(owner=owner.key, paths=paths):
                members = containment.scope_surfaces(
                    "repo-1", m.EvidenceScope(paths=paths)
                )
                self.assertEqual(
                    all(
                        containment.surface_contains(owner, member)
                        for member in members
                    ),
                    expected,
                )

    def test_order_is_deterministic_and_deduplicated(self) -> None:
        keys = [
            key(m.SurfaceKind.DOMAIN, "platform"),
            key(m.SurfaceKind.FILE, "src/b"),
            key(m.SurfaceKind.SYMBOL, "src/a.py::f"),
            key(m.SurfaceKind.FILE, "src/b"),
        ]
        self.assertEqual(
            containment.order_surfaces(keys),
            (
                key(m.SurfaceKind.SYMBOL, "src/a.py::f"),
                key(m.SurfaceKind.FILE, "src/b"),
                key(m.SurfaceKind.DOMAIN, "platform"),
            ),
        )
