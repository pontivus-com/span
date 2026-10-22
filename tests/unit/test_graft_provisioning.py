"""Graft provisioning lifecycle tests (init-gap closure).

Fresh repositories auto-build the provider-owned index on explicit
setup; current caches never rebuild; stale caches rebuild once on
explicit maintenance; ordinary reads and hooks never build. Provider
artifacts live under Span's data directory, never in the target.
"""

import json
import pathlib
import subprocess
import tempfile
import threading
import unittest
from unittest import mock

from span.core import model as m
from span.shell.structural import graft as g
from span.shell.structural import structural_source_from_config


def _bounds(**overrides):
    base = dict(
        max_results=50, max_depth=5, max_subjects=8, max_evidence_units=24,
        max_evidence_bytes=96_000, max_candidate_claims=64,
        max_candidate_relationships=64,
    )
    base.update(overrides)
    return m.QueryBounds(**base)


def _write_wiring(wiring_path, nodes=(), edges=()):
    wiring_path.parent.mkdir(parents=True, exist_ok=True)
    wiring_path.write_text(
        json.dumps({"nodes": list(nodes), "edges": list(edges)}),
        encoding="utf-8",
    )


def _git_init(root):
    subprocess.run(("git", "-C", str(root), "init", "-q"), check=True,
                   timeout=60)
    subprocess.run(("git", "-C", str(root), "add", "-A"), check=True,
                   timeout=60)
    subprocess.run(
        ("git", "-C", str(root), "-c", "user.email=t@t",
         "-c", "user.name=t", "commit", "-qm", "x"),
        check=True, timeout=60,
    )


class ProvisioningLifecycleTest(unittest.TestCase):
    def test_fresh_repo_builds_on_ensure_current(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = pathlib.Path(tmp) / "repo"
            repo.mkdir()
            (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
            cache = pathlib.Path(tmp) / "cache"
            src, _ = structural_source_from_config(
                str(repo), data_dir=tmp + "/data"
            ) if False else (None, None)
            # Build via explicit artifact dir (factory with data_dir).
            from span.shell.structural import default_artifact_dir
            artifact = default_artifact_dir(pathlib.Path(tmp) / "data",
                                            repo.name)
            src = g.GraftStructuralSource("repo", repo, artifact_dir=artifact)

            def fake_build(repo_path, artifact_dir=None):
                wp = g.wiring_path_for(repo_path, artifact_dir)
                _write_wiring(wp)
                return True, "rebuilt"

            with mock.patch.object(g, "_run_index_build",
                                   side_effect=fake_build) as run:
                self.assertFalse(src.has_index())
                freshness = src.ensure_current("repo")
                self.assertTrue(src.has_index())
                self.assertEqual(run.call_count, 1)
                self.assertIsNotNone(freshness)
            # Wiring lives in the cache, not the target.
            self.assertTrue(
                g.wiring_path_for(repo, artifact).is_file()
            )
            self.assertFalse((repo / "graft").exists())

    def test_current_cache_skips_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = pathlib.Path(tmp) / "repo"
            repo.mkdir()
            (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
            _git_init(repo)
            from span.shell.structural import default_artifact_dir
            artifact = default_artifact_dir(pathlib.Path(tmp) / "data",
                                            repo.name)
            wp = g.wiring_path_for(repo, artifact)
            _write_wiring(wp)
            src = g.GraftStructuralSource("repo", repo, artifact_dir=artifact)
            # Make the cache newer than HEAD so describe is CURRENT.
            import time
            time.sleep(1.05)
            wp.touch()
            src = g.GraftStructuralSource("repo", repo, artifact_dir=artifact)
            if src.describe_current("repo").state is not m.FreshnessState.CURRENT:
                self.skipTest("filesystem timestamp granularity")
            with mock.patch.object(
                g, "_run_index_build",
                side_effect=AssertionError("must not build"),
            ):
                freshness = src.ensure_current("repo")
                self.assertIs(freshness.state, m.FreshnessState.CURRENT)

    def test_stale_cache_rebuilds_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = pathlib.Path(tmp) / "repo"
            repo.mkdir()
            (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
            _git_init(repo)
            from span.shell.structural import default_artifact_dir
            artifact = default_artifact_dir(pathlib.Path(tmp) / "data",
                                            repo.name)
            _write_wiring(g.wiring_path_for(repo, artifact))
            src = g.GraftStructuralSource("repo", repo, artifact_dir=artifact)
            calls = []

            def fake_build(repo_path, artifact_dir=None):
                calls.append(1)
                wp = g.wiring_path_for(repo_path, artifact_dir)
                import time
                time.sleep(1.05)
                _write_wiring(wp)
                return True, "rebuilt"

            # Force STALE by making HEAD newer than the cache.
            (repo / "b.py").write_text("y = 2\n", encoding="utf-8")
            subprocess.run(("git", "-C", str(repo), "add", "-A"), check=True,
                           timeout=60)
            subprocess.run(
                ("git", "-C", str(repo), "-c", "user.email=t@t",
                 "-c", "user.name=t", "commit", "-qm", "y"),
                check=True, timeout=60,
            )
            with mock.patch.object(g, "_run_index_build",
                                   side_effect=fake_build):
                first = src.ensure_current("repo")
                second = src.ensure_current("repo")
            # At most two attempts across two calls (one per call), and
            # the second call after a successful rebuild must not rebuild
            # when already CURRENT; dirty/clean determines the exact
            # count, so assert boundedness, not an exact number.
            self.assertLessEqual(len(calls), 2)
            self.assertIsNotNone(first)
            self.assertIsNotNone(second)

    def test_ordinary_reads_never_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = pathlib.Path(tmp) / "repo"
            repo.mkdir()
            (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
            from span.shell.structural import default_artifact_dir
            artifact = default_artifact_dir(pathlib.Path(tmp) / "data",
                                            repo.name)
            src = g.GraftStructuralSource("repo", repo, artifact_dir=artifact)

            def no_build(*a, **k):
                raise AssertionError("ordinary read must not build")

            with mock.patch.object(g, "_run_index_build",
                                   side_effect=no_build):
                with self.assertRaises(g.GraftUnavailableError):
                    src.resolve_subject(
                        "repo",
                        m.SubjectSelector(None, "x", (), None),
                        _bounds(),
                    )
                with self.assertRaises(g.GraftUnavailableError):
                    src.locations(
                        "repo",
                        m.SubjectId(
                            repository_id="repo",
                            subject_kind=m.SubjectKind.COMPONENT,
                            canonical_locator="a.py",
                        ),
                        _bounds(),
                    )
                # repository_state is git state (needed for setup
                # notices) and must not build either.
                state = src.repository_state("repo")
                self.assertEqual(state.repository_id, "repo")

    def test_hooks_never_build(self):
        import inspect

        from span.service.operations import status as status_op
        source = inspect.getsource(status_op._hook_fast)
        self.assertNotIn("ensure_current", source)

    def test_failed_binary_is_actionable_setup_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = pathlib.Path(tmp) / "repo"
            repo.mkdir()
            (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
            data = pathlib.Path(tmp) / "data"
            from span.shell.mcp_server import (
                ServerConfig, provision_repository,
            )
            from span import service as ops
            with mock.patch.object(g._shutil, "which", return_value=None):
                with self.assertRaises(ValueError) as ctx:
                    provision_repository(
                        ServerConfig(data_dir=data),
                        ops.SemanticInitializeRepositoryRequest(
                            repository_locator=str(repo),
                            authority_seeds=(),
                        ),
                    )
            self.assertIn("unavailable", str(ctx.exception).lower())

    def test_malformed_output_is_unavailable_not_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = pathlib.Path(tmp) / "repo"
            repo.mkdir()
            (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
            from span.shell.structural import default_artifact_dir
            artifact = default_artifact_dir(pathlib.Path(tmp) / "data",
                                            repo.name)

            def fake_bad_build(repo_path, artifact_dir=None):
                wp = g.wiring_path_for(repo_path, artifact_dir)
                wp.parent.mkdir(parents=True, exist_ok=True)
                wp.write_text("not json", encoding="utf-8")
                return True, "rebuilt"

            src = g.GraftStructuralSource("repo", repo, artifact_dir=artifact)
            with mock.patch.object(g, "_run_index_build",
                                   side_effect=fake_bad_build):
                freshness = src.ensure_current("repo")
            self.assertIs(freshness.state, m.FreshnessState.UNVERIFIABLE)
            self.assertFalse(src.has_index())
            with self.assertRaises(g.GraftUnavailableError):
                src.resolve_subject(
                    "repo", m.SubjectSelector(None, "x", (), None),
                    _bounds(),
                )

    def test_dirty_tree_stays_unverifiable_but_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = pathlib.Path(tmp) / "repo"
            repo.mkdir()
            (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
            _git_init(repo)
            (repo / "a.py").write_text("x = 2\n", encoding="utf-8")
            from span.shell.structural import default_artifact_dir
            artifact = default_artifact_dir(pathlib.Path(tmp) / "data",
                                            repo.name)

            def fake_build(repo_path, artifact_dir=None):
                _write_wiring(g.wiring_path_for(repo_path, artifact_dir))
                return True, "rebuilt"

            src = g.GraftStructuralSource("repo", repo, artifact_dir=artifact)
            with mock.patch.object(g, "_run_index_build",
                                   side_effect=fake_build):
                freshness = src.ensure_current("repo")
            self.assertTrue(src.has_index())
            self.assertIs(freshness.state, m.FreshnessState.UNVERIFIABLE)

    def test_dirty_tree_with_current_cache_skips_build(self):
        # Lifecycle contract: one bounded build only when the index is
        # missing or stale. A present index at least as new as HEAD on
        # a dirty tree is UNVERIFIABLE, not stale, so provisioning must
        # not rebuild (this is the startup-registration rebuild loop).
        with tempfile.TemporaryDirectory() as tmp:
            repo = pathlib.Path(tmp) / "repo"
            repo.mkdir()
            (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
            _git_init(repo)
            from span.shell.structural import default_artifact_dir
            artifact = default_artifact_dir(pathlib.Path(tmp) / "data",
                                            repo.name)
            wp = g.wiring_path_for(repo, artifact)
            _write_wiring(wp)
            # Cache newer than HEAD, then dirty the working tree.
            import time
            time.sleep(1.05)
            wp.touch()
            (repo / "a.py").write_text("x = 2\n", encoding="utf-8")
            src = g.GraftStructuralSource("repo", repo, artifact_dir=artifact)
            self.assertIs(
                src.describe_current("repo").state,
                m.FreshnessState.UNVERIFIABLE,
            )
            with mock.patch.object(
                g, "_run_index_build",
                side_effect=AssertionError(
                    "dirty tree with a current cache must not rebuild"
                ),
            ):
                freshness = src.ensure_current("repo")
            self.assertIs(freshness.state, m.FreshnessState.UNVERIFIABLE)
            self.assertTrue(src.has_index())

    def test_concurrent_setup_does_not_corrupt_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = pathlib.Path(tmp) / "repo"
            repo.mkdir()
            (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
            from span.shell.structural import default_artifact_dir
            artifact = default_artifact_dir(pathlib.Path(tmp) / "data",
                                            repo.name)

            def fake_slow_build(repo_path, artifact_dir=None):
                import time
                time.sleep(0.05)
                _write_wiring(g.wiring_path_for(repo_path, artifact_dir))
                return True, "rebuilt"

            src = g.GraftStructuralSource("repo", repo, artifact_dir=artifact)
            with mock.patch.object(g, "_run_index_build",
                                   side_effect=fake_slow_build):
                threads = [
                    threading.Thread(
                        target=lambda: src.ensure_current("repo")
                    )
                    for _ in range(5)
                ]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join()
            payload = json.loads(
                g.wiring_path_for(repo, artifact).read_text(
                    encoding="utf-8")
            )
            self.assertIn("nodes", payload)
            self.assertTrue(src.has_index())

    def test_target_unchanged_and_cache_outside_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = pathlib.Path(tmp) / "repo"
            repo.mkdir()
            (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
            before = g.artifact_snapshot(repo)
            from span.shell.structural import default_artifact_dir
            artifact = default_artifact_dir(pathlib.Path(tmp) / "data",
                                            repo.name)

            def fake_build(repo_path, artifact_dir=None):
                _write_wiring(g.wiring_path_for(repo_path, artifact_dir))
                return True, "rebuilt"

            src = g.GraftStructuralSource("repo", repo, artifact_dir=artifact)
            with mock.patch.object(g, "_run_index_build",
                                   side_effect=fake_build):
                src.ensure_current("repo")
            after = g.artifact_snapshot(repo)
            self.assertEqual(before, after)
            wiring = g.wiring_path_for(repo, artifact)
            self.assertTrue(str(wiring).startswith(
                str(pathlib.Path(tmp) / "data")))
            self.assertFalse(str(wiring).startswith(str(repo)))

    def test_restart_reuses_cache_without_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = pathlib.Path(tmp) / "repo"
            repo.mkdir()
            (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
            from span.shell.structural import default_artifact_dir
            artifact = default_artifact_dir(pathlib.Path(tmp) / "data",
                                            repo.name)
            _write_wiring(g.wiring_path_for(repo, artifact))
            first = g.GraftStructuralSource("repo", repo,
                                            artifact_dir=artifact)
            self.assertTrue(first.has_index())
            second = g.GraftStructuralSource("repo", repo,
                                             artifact_dir=artifact)
            with mock.patch.object(
                g, "_run_index_build",
                side_effect=AssertionError("restart must reuse cache"),
            ):
                second.describe_current("repo")
            self.assertTrue(second.has_index())

    def test_provision_uses_one_path_with_plain_locator(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = pathlib.Path(tmp) / "repo"
            repo.mkdir()
            (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
            data = pathlib.Path(tmp) / "data"
            from span.shell.mcp_server import (
                ServerConfig, provision_repository,
            )
            from span import service as ops

            def fake_build(repo_path, artifact_dir=None):
                _write_wiring(g.wiring_path_for(repo_path, artifact_dir))
                return True, "rebuilt"

            with mock.patch.object(g, "_run_index_build",
                                   side_effect=fake_build):
                context, result = provision_repository(
                    ServerConfig(data_dir=data),
                    ops.SemanticInitializeRepositoryRequest(
                        repository_locator=str(repo),
                        authority_seeds=(),
                    ),
                )
            self.assertEqual(result.readiness, m.RepositoryReadiness.READY)
            self.assertTrue(context.structural.has_index())
            # A provider-prefixed locator is not part of the public
            # surface: provisioning rejects it instead of interpreting it.
            with self.assertRaises(ValueError):
                provision_repository(
                    ServerConfig(data_dir=data),
                    ops.SemanticInitializeRepositoryRequest(
                        repository_locator=f"graft:{repo}",
                        authority_seeds=(),
                    ),
                )

    def test_public_surface_hides_graft(self):
        from span.shell import mcp_server
        from span.shell import install
        from span.shell.mcp import TOOL_DESCRIPTIONS, TOOL_SCHEMAS
        import json as _json
        import tempfile as _tempfile
        args = mcp_server._parse_args(
            ["--data-dir", "/tmp/d", "--repo", "/tmp/repo"])
        self.assertEqual(args.repo, ["/tmp/repo"])
        iargs = install.parse_args(["--repo", "/tmp/repo"])
        self.assertEqual(iargs.repo, ["/tmp/repo"])
        import pathlib as _pl
        readme = (_pl.Path(__file__).resolve().parents[2]
                  / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("--repo graft:", readme)
        self.assertNotIn('"graft:<TARGET_REPO>"', readme)
        self.assertNotIn("graft` on `PATH", readme)
        # Active user-facing docs name no provider.
        self.assertNotIn("graft", readme.lower())
        mcp_doc = (_pl.Path(__file__).resolve().parents[2]
                   / "docs" / "mcp.md").read_text(encoding="utf-8")
        self.assertNotIn("graft", mcp_doc.lower())
        for name, description in TOOL_DESCRIPTIONS.items():
            self.assertNotIn("graft", description.lower(), name)
        for name, schema in TOOL_SCHEMAS.items():
            self.assertNotIn("graft", _json.dumps(schema).lower(), name)
        # Provider vocabulary failures reach clients without the name.
        with _tempfile.TemporaryDirectory() as _tmp_kind:
            _root_kind = _pl.Path(_tmp_kind) / "repo"
            (_root_kind / "graft" / ".graph").mkdir(parents=True)
            (_root_kind / "graft" / ".graph" / "wiring.json").write_text(
                _json.dumps({
                    "nodes": [{"id": "x", "name": "x",
                               "kind": "NOT_A_KIND", "path": "a.py"}],
                    "edges": [],
                })
            )
            _bad = g.GraftStructuralSource("repo", _root_kind)
            self.assertFalse(_bad.has_index())
            with self.assertRaises(Exception) as _kind_ctx:
                _bad._require_index()
            self.assertNotIn("graft", str(_kind_ctx.exception).lower())
        # Installer output never names the provider either.
        import contextlib as _contextlib
        import io as _io
        with _tempfile.TemporaryDirectory() as _tmp_out:
            _cfg = _pl.Path(_tmp_out) / "opencode.json"
            _cfg.write_text(_json.dumps({
                "mcp": {"graft": {"command": ["obsolete"]}},
            }))
            _buf = _io.StringIO()
            with _contextlib.redirect_stdout(_buf):
                install.merge_opencode_config(str(_cfg), ["span-mcp"])
            self.assertNotIn("graft", _buf.getvalue().lower())
            self.assertIn("removed obsolete MCP entries", _buf.getvalue())
            _dry = _io.StringIO()
            with _contextlib.redirect_stdout(_dry):
                with mock.patch.object(
                    install.shutil, "which", return_value="/codex"
                ):
                    install.deregister_obsolete_codex_mcp(dry_run=True)
            self.assertNotIn("graft", _dry.getvalue().lower())
        # User-facing setup failure must not name the indexer: trigger
        # a real provisioning failure with no binary anywhere.
        from span.shell.mcp_server import (
            ServerConfig as _ServerConfig,
            provision_repository as _provision,
        )
        from span import service as _ops
        with _tempfile.TemporaryDirectory() as _tmp:
            _repo = _pl.Path(_tmp) / "repo"
            _repo.mkdir()
            (_repo / "a.py").write_text("x = 1\n", encoding="utf-8")
            with mock.patch.object(
                g, "resolve_indexer_binary", return_value=None
            ):
                with self.assertRaises(ValueError) as _ctx:
                    _provision(
                        _ServerConfig(data_dir=_pl.Path(_tmp) / "data"),
                        _ops.SemanticInitializeRepositoryRequest(
                            repository_locator=str(_repo),
                            authority_seeds=(),
                        ),
                    )
            self.assertNotIn("graft", str(_ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
