"""Surface persistence and immutable boundary history (FD-1, FD-6–FD-8)."""

from __future__ import annotations

import datetime
import pathlib
import tempfile
import unittest

from span.core import model as m
from span.core.rejection import SurfaceConflict
from span.shell.sqlite_store.lifecycle import LifecycleStore, LifecycleStoreError

NOW = datetime.datetime(2026, 11, 1, 12, 0, tzinfo=datetime.timezone.utc)
RETENTION = m.LifecycleRetention(
    context_lifetime=datetime.timedelta(hours=1),
    replay_retention=datetime.timedelta(hours=4),
)


def _key(
    locator: str = "billing", kind: m.SurfaceKind = m.SurfaceKind.SERVICE
) -> m.SurfaceKey:
    return m.SurfaceKey(repository_id="repo-1", kind=kind, locator=locator)


def _surface(
    locator: str = "billing",
    *,
    kind: m.SurfaceKind = m.SurfaceKind.SERVICE,
    paths: tuple[str, ...] = ("src/billing",),
    version: int = 1,
) -> m.Surface:
    return m.Surface(
        key=_key(locator, kind),
        boundary=m.SurfaceBoundary(paths=paths),
        boundary_version=version,
    )


class SurfaceStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = str(pathlib.Path(self._tmp.name) / "lifecycle.sqlite3")
        self.store = LifecycleStore(self.path, retention=RETENTION, clock=lambda: NOW)
        self.store.register_repository("repo-1", "/repo")

    def test_put_get_list_round_trip(self) -> None:
        surface = _surface()
        self.assertEqual(self.store.put_surface(surface), surface)
        self.assertEqual(self.store.get_surface(_key()), surface)
        self.assertEqual(self.store.list_surfaces("repo-1"), (surface,))
        self.assertIsNone(self.store.find_surface(_key("missing")))
        with self.assertRaises(LifecycleStoreError):
            self.store.get_surface(_key("missing"))

    def test_put_is_idempotent_and_rejects_kind_conflict(self) -> None:
        surface = _surface()
        self.store.put_surface(surface)
        self.assertEqual(self.store.put_surface(surface), surface)
        with self.assertRaises(SurfaceConflict) as raised:
            self.store.put_surface(_surface(kind=m.SurfaceKind.DOMAIN))
        self.assertEqual(raised.exception.current_boundary_version, 1)

    def test_update_requires_expected_version(self) -> None:
        self.store.put_surface(_surface())
        with self.assertRaises(SurfaceConflict):
            self.store.update_surface(
                _surface(paths=("src",), version=2),
                expected_boundary_version=2,
            )
        with self.assertRaises(SurfaceConflict):
            self.store.update_surface(
                _surface(paths=("src",), version=2),
                expected_boundary_version=0,
            )
        self.store.update_surface(
            _surface(paths=("src",), version=2), expected_boundary_version=1
        )

    def test_update_must_advance_by_exactly_one(self) -> None:
        self.store.put_surface(_surface())
        with self.assertRaises(SurfaceConflict):
            self.store.update_surface(
                _surface(paths=("src",), version=3),
                expected_boundary_version=1,
            )

    def test_update_appends_immutable_boundary_history(self) -> None:
        first = _surface()
        self.store.put_surface(first)
        second = self.store.update_surface(
            _surface(paths=("src", "lib"), version=2),
            expected_boundary_version=1,
        )
        self.assertEqual(self.store.get_surface(_key()), second)
        history = self.store.surface_boundaries(_key())
        self.assertEqual(history, (first, second))
        self.assertEqual(history[0].boundary.paths, ("src/billing",))

    def test_surface_and_history_survive_reopen(self) -> None:
        self.store.put_surface(_surface())
        reopened = LifecycleStore(self.path, retention=RETENTION, clock=lambda: NOW)
        self.assertEqual(reopened.schema_version(), 11)
        self.assertEqual(reopened.get_surface(_key()).boundary.paths, ("src/billing",))
        self.assertEqual(reopened.surface_boundaries(_key())[0].boundary_version, 1)
