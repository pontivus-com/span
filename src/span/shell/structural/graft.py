"""Graft structural provider (plan Phase 2.2, against §5.2 only).

Maps Graft's structural index (nodes with repo-relative ids, spans,
signatures, body hashes; directed edges with relations) onto the
StructuralSource port. Structure-to-structure only: no semantic
interpretation, no authority, no meaning assignment. The semantic
model is not shaped around Graft; unknown Graft node kinds or
relations raise explicit typed errors instead of being guessed into
the canonical vocabulary.

Suitability record (plan Phase 2.1, license MIT verified Phase 0.4):

- generic-port fit: all five §5.2 operations served from wiring.json
  plus git (revision/dirty) plus target-repo file reads (fallback
  fingerprints);
- independence: separately installable npm package, no private code;
- build policy (lifecycle contract): `ensure_current` alone may run a
  provider-owned build into Span's data directory
  (``<data-dir>/structural/<repository-id>/`` via ``graft --dir``,
  no ``--deep``, no credentials, no target writes), then reload.
  Allowed only from explicit `initialize_repository` provisioning and
  explicit `refresh`. Forbidden from `status`, `explain`, `locate`,
  `neighbors`, hooks, background workers, and ordinary reads.
  Queries never build; missing indexes fail closed on reads.
"""

from __future__ import annotations

import hashlib as _hashlib
import json as _json
import os as _os
import pathlib as _pathlib
import shutil as _shutil
import subprocess as _subprocess
import threading as _threading

from span.core import model as m
from span.ports.structural import StaleContinuationError
from span.ports.structural import StructuralDirection
from span.shell import paging as _paging
from span.shell.structural.memory import (
    evidence_kind_for_path,
    fingerprint_content,
)

__all__ = [
    "GraftUnavailableError",
    "GraftShapeError",
    "GraftVocabularyError",
    "GraftStructuralSource",
    "STRUCTURAL_INDEXER_PACKAGE",
    "STRUCTURAL_INDEXER_VERSION",
    "artifact_snapshot",
    "provider_artifact_snapshot",
    "default_artifact_dir",
    "indexer_pointer_path",
    "read_indexer_pointer",
    "remove_provider_artifacts",
    "resolve_indexer_binary",
    "wiring_path_for",
    "NODE_SUBJECT_KIND",
    "RELATION_EDGE_KIND",
]


#: Managed structural-indexer identity. The installer provisions exactly
#: this npm package version into Span's tools directory; keep in sync
#: with ``STRUCTURAL_INDEXER_{PACKAGE,VERSION}`` in
#: ``span/shell/install.py`` (which must stay stdlib-only, so the
#: constants are duplicated, not imported).
STRUCTURAL_INDEXER_PACKAGE = "@nanonets/graft"
STRUCTURAL_INDEXER_VERSION = "0.25.0"

#: Env override for the indexer binary (contributor/debug use). The
#: normal path is the installer-written pointer under the data dir.
INDEXER_BINARY_ENV_VAR = "SPAN_GRAFT_BIN"

#: Pointer file, written by installation, naming the provisioned binary.
INDEXER_POINTER_FILENAME = "structural-indexer.json"


class GraftUnavailableError(Exception):
    """Graft CLI or its built index is unavailable (feeds §7 transport
    policy as provider-unavailable; never auto-remedied in queries)."""


class GraftShapeError(ValueError):
    """wiring.json does not match the expected structural contract."""


class GraftVocabularyError(ValueError):
    """A Graft node kind or edge relation has no closed mapping entry.
    Raised instead of guessing canonical semantics."""


#: Closed node-kind mapping (structural only). Files split by suffix
#: rule (shared with the deterministic source); symbols are code.
#: `enum` is a named type declaration like class/interface/type
#: (plan §4.1 CODE_SYMBOL; no new SubjectKind).
NODE_SUBJECT_KIND: dict[str, m.SubjectKind] = {
    "file": m.SubjectKind.COMPONENT,
    "function": m.SubjectKind.CODE_SYMBOL,
    "class": m.SubjectKind.CODE_SYMBOL,
    "method": m.SubjectKind.CODE_SYMBOL,
    "interface": m.SubjectKind.CODE_SYMBOL,
    "type": m.SubjectKind.CODE_SYMBOL,
    "enum": m.SubjectKind.CODE_SYMBOL,
    # A nominal data carrier, not a service: Go structs, Java records, and
    # Swift structs. The indexer re-kinds these away from "class" so a DTO
    # stays distinguishable from a service.
    "struct": m.SubjectKind.CODE_SYMBOL,
    # A module is a code container, the same role a file plays (Rust
    # `mod`). It is not a subsystem: it carries no semantic boundary.
    "module": m.SubjectKind.COMPONENT,
    # A named value declaration (Rust `const`/`static`). Like `enum` and
    # `type`, it is a named declaration in code rather than a callable or
    # a member of a type, so it belongs to the same bucket.
    "constant": m.SubjectKind.CODE_SYMBOL,
}

#: Closed edge-relation mapping (structural only). `extends`/`implements`
#: are compile-time dependencies (plan §5.2 DEPENDS_ON); structural
#: possibility only, never a semantic IMPLEMENTS claim (§4.5).
RELATION_EDGE_KIND: dict[str, m.StructuralEdgeKind] = {
    "contains": m.StructuralEdgeKind.DEFINES,
    "imports": m.StructuralEdgeKind.IMPORTS,
    "calls": m.StructuralEdgeKind.CALLS,
    "references": m.StructuralEdgeKind.REFERENCES,
    "depends_on": m.StructuralEdgeKind.DEPENDS_ON,
    "extends": m.StructuralEdgeKind.DEPENDS_ON,
    "implements": m.StructuralEdgeKind.DEPENDS_ON,
}

_DOCUMENT_SUFFIXES = (".md", ".rst", ".txt")

# Provider-local build locks: one per artifact/wiring location so two
# setup/refresh calls for the same repository never build concurrently
# in-process. Cross-process torn writes are handled by keeping the last
# good index on unreadable reload (see _ensure_fresh).
_BUILD_LOCKS_GUARD = _threading.Lock()
_BUILD_LOCKS: dict[str, _threading.Lock] = {}


def _build_lock_for(key: str) -> _threading.Lock:
    with _BUILD_LOCKS_GUARD:
        lock = _BUILD_LOCKS.get(key)
        if lock is None:
            lock = _threading.Lock()
            _BUILD_LOCKS[key] = lock
        return lock


def _sanitize_repository_id(repository_id: str) -> str:
    """Filesystem-safe directory name for one repository id."""
    cleaned = "".join(
        c if (c.isalnum() or c in ("-", "_", ".")) else "_" for c in repository_id
    ).strip("._")
    return cleaned or "repo"


def default_artifact_dir(
    data_dir: str | _pathlib.Path, repository_id: str
) -> _pathlib.Path:
    """Provider-owned cache root: <data-dir>/structural/<repository-id>/.

    Lives outside every target repository. Holds the graft graph dir
    (``.graph/wiring.json``), graft extraction caches, and provider-local
    Markdown cards. Only the machine-readable wiring graph is consumed
    by Span; generated prose is never semantic evidence.
    """
    return (
        _pathlib.Path(data_dir) / "structural" / _sanitize_repository_id(repository_id)
    )


def remove_provider_artifacts(artifact_dir: str | _pathlib.Path) -> None:
    """Delete one provider cache root (uninstall/repository removal).

    Best effort: missing directory is a no-op; failures raise OSError
    for the caller to report. Never touches target repositories.
    """
    root = _pathlib.Path(artifact_dir)
    if not root.exists() and not root.is_symlink():
        return
    if root.is_symlink() or root.is_file():
        root.unlink()
    else:
        _shutil.rmtree(root)


def indexer_pointer_path(data_dir: str | _pathlib.Path) -> _pathlib.Path:
    """Location of the installer-written indexer pointer file."""
    return _pathlib.Path(data_dir) / INDEXER_POINTER_FILENAME


def read_indexer_pointer(
    data_dir: str | _pathlib.Path,
) -> dict[str, object] | None:
    """Read the installer-written indexer pointer, if usable.

    Returns the parsed payload when it names an existing binary file,
    else None. Never raises: a missing or corrupt pointer simply means
    the managed binary is not established.
    """
    try:
        payload = _json.loads(
            indexer_pointer_path(data_dir).read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    binary = payload.get("binary")
    if not isinstance(binary, str) or not binary:
        return None
    try:
        if not _pathlib.Path(binary).is_file():
            return None
    except OSError:
        return None
    return payload


def resolve_indexer_binary(
    data_dir: str | _pathlib.Path | None = None,
) -> str | None:
    """Resolve the structural-indexer binary without user configuration.

    Order: explicit ``SPAN_GRAFT_BIN`` env override, installer-managed
    pointer under ``data_dir``, then ``PATH`` fallback (transitional for
    pre-managed installs). Returns the binary path or None.
    """
    override = _os.environ.get(INDEXER_BINARY_ENV_VAR)
    if override:
        return override
    if data_dir is not None:
        pointer = read_indexer_pointer(data_dir)
        if pointer is not None:
            binary = pointer.get("binary")
            if isinstance(binary, str) and binary:
                return binary
    return _shutil.which("graft")


def _data_dir_from_artifact_dir(
    artifact_dir: str | _pathlib.Path,
) -> _pathlib.Path | None:
    """Recover the data dir from a ``<data>/structural/<id>`` cache path."""
    artifact = _pathlib.Path(artifact_dir)
    if artifact.parent.name == "structural":
        return artifact.parent.parent
    return None


def wiring_path_for(
    artifact_dir: str | _pathlib.Path,
) -> _pathlib.Path:
    """Location of the built Graft structural index for a repository.

    The only location is the provider-owned cache
    ``<artifact>/.graph/wiring.json`` outside the target.
    """
    return _pathlib.Path(artifact_dir) / ".graph" / "wiring.json"


def artifact_snapshot(repo_path: str | _pathlib.Path) -> dict[str, object]:
    """Read-only census of the target structural-index tree (isolation evidence).

    Counts generated Markdown cards beside the machine-readable index and
    records the index identity. Creates nothing, builds nothing, writes
    nothing: Span runs must leave target trees unchanged — provider
    artifacts live under Span's data directory, never in the target.
    Card ownership is the host's business; this census never deletes.
    """
    root = _pathlib.Path(repo_path)
    graph_dir = root / "graft"
    wiring = root / "graft" / ".graph" / "wiring.json"
    try:
        stat = wiring.stat()
        wiring_info: dict[str, object] = {
            "present": True,
            "mtime_ns": stat.st_mtime_ns,
            "size_bytes": stat.st_size,
        }
    except OSError:
        wiring_info = {"present": False, "mtime_ns": None, "size_bytes": None}
    cards = 0
    index_md = False
    if graph_dir.is_dir():
        for path in sorted(graph_dir.rglob("*")):
            try:
                if not path.is_file():
                    continue
            except OSError:
                continue
            if path.suffix != ".md":
                continue
            if path.name == "INDEX.md" and path.parent == graph_dir:
                index_md = True
            cards += 1
    return {
        "wiring": wiring_info,
        "markdown_cards": cards,
        "index_md": index_md,
    }


def provider_artifact_snapshot(
    artifact_dir: str | _pathlib.Path,
) -> dict[str, object]:
    """Read-only census of one provider-owned cache root.

    Records wiring presence/identity plus generated-card counts inside
    the cache. Creates nothing. Used for retention diagnostics and
    restart-behavior evidence; never a semantic claim.
    """
    root = _pathlib.Path(artifact_dir)
    wiring = root / ".graph" / "wiring.json"
    try:
        stat = wiring.stat()
        wiring_info: dict[str, object] = {
            "present": True,
            "mtime_ns": stat.st_mtime_ns,
            "size_bytes": stat.st_size,
        }
    except OSError:
        wiring_info = {"present": False, "mtime_ns": None, "size_bytes": None}
    cards = 0
    index_md = False
    if root.is_dir():
        for path in sorted(root.rglob("*")):
            try:
                if not path.is_file():
                    continue
            except OSError:
                continue
            if path.suffix != ".md":
                continue
            if path.name == "INDEX.md" and path.parent == root:
                index_md = True
            cards += 1
    return {
        "wiring": wiring_info,
        "markdown_cards": cards,
        "index_md": index_md,
    }


def _git_revision(repo_path: _pathlib.Path) -> tuple[str | None, bool]:
    """HEAD hash plus dirty boolean in a single subprocess.

    One `git status --porcelain=v2 --branch` call yields both the
    `# branch.oid` header and the entry lines; any entry line means
    a dirty tree. This halves process spawns versus rev-parse plus
    status Rhe separately (perf: repository_state fans out per page).
    """
    try:
        proc = _subprocess.run(
            [
                "git",
                "-C",
                str(repo_path),
                "status",
                "--porcelain=v2",
                "--branch",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, _subprocess.SubprocessError):
        return None, False
    if proc.returncode != 0:
        return None, False
    oid: str | None = None
    dirty = False
    for line in proc.stdout.splitlines():
        if line.startswith("# branch.oid "):
            value = line[len("# branch.oid ") :].strip()
            if value and value != "(initial)":
                oid = value
        elif line.startswith("#"):
            continue
        elif line.strip():
            dirty = True
    return oid, dirty


def _git_head_time(repo_path: _pathlib.Path) -> int | None:
    """HEAD commit timestamp (unix epoch) for scope-coverage checks."""
    try:
        proc = _subprocess.run(
            ["git", "-C", str(repo_path), "log", "-1", "--format=%ct"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, _subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    try:
        return int(proc.stdout.strip())
    except ValueError:
        return None


def _git_scope_baseline_time(
    repo_path: _pathlib.Path, scope_paths: tuple[str, ...]
) -> int | None:
    """Most recent commit time touching the scope (J-7 scoped baseline).

    ``git log -1 --format=%ct -- <pathspecs>``. When no commit touched
    the scope, fall back to the repository-global HEAD time.
    """
    if not scope_paths:
        return _git_head_time(repo_path)
    try:
        proc = _subprocess.run(
            [
                "git",
                "-C",
                str(repo_path),
                "log",
                "-1",
                "--format=%ct",
                "--",
                *scope_paths,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, _subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    out = proc.stdout.strip()
    if not out:
        return _git_head_time(repo_path)
    try:
        return int(out)
    except ValueError:
        return None


def _git_scope_dirty(
    repo_path: _pathlib.Path, scope_paths: tuple[str, ...]
) -> bool | None:
    """Scoped working-tree dirtiness including untracked (J-7).

    ``git status --porcelain -- <pathspecs>``; any entry means a
    changed/untracked path intersecting the scope. None when git cannot
    answer.
    """
    if not scope_paths:
        return None
    try:
        proc = _subprocess.run(
            [
                "git",
                "-C",
                str(repo_path),
                "status",
                "--porcelain",
                "--",
                *scope_paths,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, _subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return bool(proc.stdout.strip())


def _run_index_build(
    repo_path: _pathlib.Path,
    artifact_dir: str | _pathlib.Path,
) -> tuple[bool, str]:
    """Run one provider-owned index build (lifecycle contract).

    Builds into the provider cache (indexer ``--dir <cache> build``).
    Flags: ``--no-gitignore --no-ignore`` (never write target
    dotfiles), never ``--deep`` (wiring only, no LLM), never provider /
    model / API-key flags (no credentials). Bounded 600s timeout.
    The binary resolves without user configuration (installer-managed
    pointer, then ``PATH`` fallback). Returns (ok, detail) with
    provider-neutral details; never raises.

    ``DO_NOT_TRACK=1`` is part of the environment. The provider's
    telemetry mints a per-repository id on first use and stores it at
    ``<repo>/graft/.cache/telemetry-repo-id.json``; on a host that has
    never run the indexer before, that bootstrap would write a
    directory into the target. The cross-tool opt-out closes the
    telemetry gate before the id is minted, so the build stays confined
    to the provider cache. An automated background build is also not a
    user interaction to report.
    """
    data_dir = _data_dir_from_artifact_dir(artifact_dir)
    binary = resolve_indexer_binary(data_dir)
    if binary is None:
        return False, (
            "structural indexer unavailable: rerun installation to " "provision it"
        )
    try:
        _pathlib.Path(artifact_dir).mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return False, f"cannot create provider cache: {exc}"
    cmd = [
        binary,
        "--dir",
        str(artifact_dir),
        "build",
        "--no-gitignore",
        "--no-ignore",
        str(repo_path),
    ]
    env = {k: v for k, v in _os.environ.items() if k != "GRAFT_API_KEY"}
    env["DO_NOT_TRACK"] = "1"
    try:
        proc = _subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            env=env,
        )
    except (OSError, _subprocess.SubprocessError) as exc:
        return False, f"build process failed to start: {exc}"
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()
        return False, f"build exited {proc.returncode}: {' '.join(tail[-2:])}"
    return True, "rebuilt"


class GraftStructuralSource:
    """StructuralSource over a provider-owned Graft index.

    Lifecycle: construction never builds and never fails for a missing
    index (setup must be able to run). Ordinary structural reads fail
    closed with GraftUnavailableError when no index is loaded.
    `describe_current` is read-only. `ensure_current` performs at most
    one bounded provider-owned build (explicit init/refresh only),
    reloads, validates, and reports currency.
    """

    def __init__(
        self,
        repository_id: str,
        repo_path: str | _pathlib.Path,
        wiring: dict | None = None,
        artifact_dir: str | _pathlib.Path | None = None,
    ) -> None:
        self._repository_id = repository_id
        self._repo_path = _pathlib.Path(repo_path)
        if wiring is None and artifact_dir is None:
            raise ValueError("file-backed structural source requires artifact_dir")
        self._artifact_dir = (
            _pathlib.Path(artifact_dir) if artifact_dir is not None else None
        )
        self._wiring_path: _pathlib.Path | None = None
        self._wiring_mtime_ns: int | None = None
        self._wiring_size: int | None = None
        self._loaded = False
        self._load_error: Exception | None = None
        if wiring is not None:
            # Injected wiring (tests): strict, pathless, never builds.
            self._nodes = self._parse_nodes(wiring)
            self._edges = self._parse_edges(wiring)
            self._file_hashes = self._rebuild_file_hashes()
            self._loaded = True
        else:
            # File-backed: the provider cache is the only index
            # location. Construction never reads the target repository.
            assert self._artifact_dir is not None
            path = wiring_path_for(self._artifact_dir)
            try:
                is_file = path.is_file()
            except OSError:
                is_file = False
            if is_file:
                try:
                    raw = _json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError) as exc:
                    self._load_error = GraftShapeError(
                        f"cannot read wiring.json: {exc}"
                    )
                    raw = None
                if raw is not None:
                    try:
                        nodes = self._parse_nodes(raw)
                        # _parse_edges needs self._nodes for the file map.
                        self._nodes = nodes
                        edges = self._parse_edges(raw)
                    except (GraftShapeError, GraftVocabularyError) as exc:
                        self._load_error = exc
                    else:
                        self._edges = edges
                        self._file_hashes = self._rebuild_file_hashes()
                        self._wiring_path = path
                        try:
                            stat = path.stat()
                        except OSError:
                            stat = None
                        if stat is not None:
                            self._wiring_mtime_ns = stat.st_mtime_ns
                            self._wiring_size = stat.st_size
                        self._loaded = True
                        self._load_error = None
            if not self._loaded:
                # No usable index yet: construction succeeds so explicit
                # setup can run `ensure_current`. Reads fail closed via
                # _require_index; describe reports UNVERIFIABLE.
                self._nodes = {}
                self._edges = []
                self._file_hashes = {}
                # Watch the cache location so a later build is seen.
                self._wiring_path = path
        # Fingerprint memo: the node set derives byte-for-byte from the
        # wiring file, so (mtime, size) keys the cached digest exactly.
        # Must precede _compute_index_version, which reads it. Never
        # served across index content changes (keyed, and _ensure_fresh
        # reloads on stat change first).
        self._state_fingerprint_memo: tuple[int | None, int | None, str] | None = None
        self._index_version = self._compute_index_version()

    def has_index(self) -> bool:
        """Whether a usable structural index is currently loaded."""
        return self._loaded

    def _require_index(self) -> None:
        if not self._loaded:
            detail = f": {self._load_error}" if self._load_error is not None else ""
            raise GraftUnavailableError(
                f"no usable structural index for repository "
                f"{self._repository_id!r}{detail}; run "
                f"initialize_repository setup (or refresh) to build it"
            )

    def _load_from_disk(self) -> bool:
        """Force-reload the preferred wiring file; True on success.

        Keeps the last good index on torn/malformed writes. Returns
        False when no usable index is on disk.
        """
        if self._wiring_path is None:
            return self._loaded
        path = self._wiring_path
        try:
            if not path.is_file():
                return self._loaded
            raw = _json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return self._loaded
        try:
            nodes = self._parse_nodes(raw)
            self._nodes = nodes
            edges = self._parse_edges(raw)
        except (GraftShapeError, GraftVocabularyError):
            return self._loaded
        self._edges = edges
        self._file_hashes = self._rebuild_file_hashes()
        try:
            stat = path.stat()
        except OSError:
            stat = None
        if stat is not None:
            self._wiring_mtime_ns = stat.st_mtime_ns
            self._wiring_size = stat.st_size
        else:
            self._wiring_mtime_ns = None
            self._wiring_size = None
        self._state_fingerprint_memo = None
        self._index_version = self._compute_index_version()
        self._loaded = True
        self._load_error = None
        return True

    def _rebuild_file_hashes(self) -> dict[str, str | None]:
        """Recorded whole-file hashes by path (Addendum F §4.0).

        Only file-kind nodes carry a comparable hash; symbols are never
        compared against file bytes.
        """
        hashes: dict[str, str | None] = {}
        for node in self._nodes.values():
            if node["kind"] != "file":
                continue
            path = str(node["path"])
            body = node.get("body_hash")
            hashes[path] = body if isinstance(body, str) and body else None
        return hashes

    def _compute_index_version(self) -> str:
        """Listing version binding query cursors (Addendum F §4.3)."""
        return f"{self._wiring_mtime_ns or 0}-{self._state_fingerprint()[:16]}"

    def _ensure_fresh(self) -> None:
        """Reload rule: re-read the index when the wiring file changed.

        Read-only reload — parsing only, never a build. Injected wiring
        (tests) has no path to watch. A previously missing index is
        picked up when a build lands. Unreadable/malformed new bytes
        keep serving the last good index rather than failing on a torn
        write.
        """
        if self._wiring_path is None:
            return
        if not self._loaded:
            self._load_from_disk()
            return
        try:
            stat = self._wiring_path.stat()
        except OSError:
            # Current file vanished: keep serving the loaded index.
            return
        if (
            stat.st_mtime_ns == self._wiring_mtime_ns
            and stat.st_size == self._wiring_size
        ):
            return
        try:
            wiring = _json.loads(self._wiring_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # Unreadable new index: keep serving the loaded one rather
            # than failing the operation on a torn write.
            return
        try:
            nodes = self._parse_nodes(wiring)
            self._nodes = nodes
            edges = self._parse_edges(wiring)
        except (GraftShapeError, GraftVocabularyError):
            return
        self._nodes = nodes
        self._edges = edges
        self._file_hashes = self._rebuild_file_hashes()
        self._wiring_mtime_ns = stat.st_mtime_ns
        self._wiring_size = stat.st_size
        self._index_version = self._compute_index_version()

    def _live_file_fingerprint(self, path: str) -> str | None:
        """Current whole-file fingerprint; None when unreadable."""
        try:
            return fingerprint_content(
                (self._repo_path / path).read_text(encoding="utf-8")
            )
        except OSError:
            return None

    def _verify_exact_files(
        self, files: tuple[str, ...] | list[str]
    ) -> tuple[list[str], list[str]]:
        """Per-file live verification with no repository-wide gate (S2.1)."""
        stale: list[str] = []
        unverifiable: list[str] = []
        for path in dict.fromkeys(files):
            recorded = self._file_hashes.get(path)
            if recorded is None:
                unverifiable.append(path)
                continue
            live = self._live_file_fingerprint(path)
            if live is None or live != recorded:
                stale.append(path)
        return stale, unverifiable

    def _repository_population_current(self) -> bool:
        """Whole-repository candidate population is unchanged (S2.1).

        True only when the tree is git-clean and the loaded index is at
        least as new as HEAD. Used for open-world queries whose
        completeness a changed or untracked file could alter. Injected
        wiring and non-git trees cannot establish this (honest
        UNVERIFIED, never assumed).
        """
        if self._wiring_mtime_ns is None:
            return False
        revision, dirty = _git_revision(self._repo_path)
        if revision is None or dirty:
            return False
        head_time = _git_head_time(self._repo_path)
        if head_time is None:
            return False
        return self._wiring_mtime_ns >= head_time * 1_000_000_000

    def _scope_inventory_current(self, scope_paths: tuple[str, ...]) -> bool:
        """Exact-scope currentness: scoped committed baseline + scoped status.

        The baseline is the most recent commit touching the scope
        (`git log -1 --format=%ct -- <pathspecs>`), never
        repository-global HEAD, so a newer unrelated commit cannot make a
        current scoped index look old (J-7). Any staged/unstaged/deleted/
        untracked path intersecting the scope makes it unproven; non-git
        or unprovable scopes are False, never assumed.
        """
        if self._wiring_mtime_ns is None or not scope_paths:
            return False
        revision, _dirty = _git_revision(self._repo_path)
        if revision is None:
            return False
        baseline = _git_scope_baseline_time(self._repo_path, scope_paths)
        if baseline is None:
            return False
        if self._wiring_mtime_ns < baseline * 1_000_000_000:
            return False
        return _git_scope_dirty(self._repo_path, scope_paths) is False

    def _file_detail(
        self,
        stale: list[str] | tuple[str, ...],
        unverifiable: list[str] | tuple[str, ...],
    ) -> str:
        """File-only diagnostic tokens (no tree/population tokens)."""
        tokens: list[str] = []
        if stale:
            tokens.append("touched-file-mismatch")
        if unverifiable:
            tokens.append("unverifiable-file")
        if not tokens:
            return "clean-verified"
        return "+".join(tokens)

    def _join_detail(self, tokens: list[str] | tuple[str, ...]) -> str:
        """Join diagnostic tokens in the closed fixed order (J-11)."""
        order = {
            "non-git-tree": 0,
            "injected-index": 1,
            "dirty-tree": 2,
            "touched-file-mismatch": 3,
            "unverifiable-file": 4,
            "index-older-than-head": 5,
            "repository-population-unverified": 6,
        }
        toks = sorted(set(tokens), key=lambda t: order[t])
        return "clean-verified" if not toks else "+".join(toks)

    def _repository_detail_tokens(self) -> list[str]:
        tokens: list[str] = []
        if self._wiring_path is None:
            return ["injected-index"]
        revision, dirty = _git_revision(self._repo_path)
        if revision is None:
            return ["non-git-tree"]
        if dirty:
            return ["dirty-tree"]
        head_time = _git_head_time(self._repo_path)
        if head_time is None:
            return ["non-git-tree"]
        if (
            self._wiring_mtime_ns is not None
            and self._wiring_mtime_ns < head_time * 1_000_000_000
        ):
            tokens.append("index-older-than-head")
        if not self._repository_population_current():
            tokens.append("repository-population-unverified")
        return tokens

    def _coverage_detail(
        self,
        stale: list[str] | tuple[str, ...],
        unverifiable: list[str] | tuple[str, ...],
    ) -> str:
        """Closed diagnostic tokens for the freshness verdict (G §4.2a).

        Projects facts already held by the provider; computes no new
        freshness. Fixed join order: non-git-tree, injected-index,
        dirty-tree, touched-file-mismatch, unverifiable-file,
        index-older-than-head. `clean-verified` only when coverage is
        VERIFIED.
        """
        tokens = self._repository_detail_tokens()
        if stale:
            tokens.append("touched-file-mismatch")
        if unverifiable:
            tokens.append("unverifiable-file")
        return self._join_detail(tokens)

    def verify_files(
        self,
        repository_id: str,
        files: tuple[str, ...],
    ) -> m.StructuralFreshnessReport:
        """File-set freshness verdict (Addendum F §4.0 port)."""
        self._check_repository(repository_id)
        self._ensure_fresh()
        self._require_index()
        stale, unverifiable = self._verify_exact_files(files)
        coverage = (
            m.ScopeCoverage.VERIFIED
            if not stale and not unverifiable and self._repository_population_current()
            else m.ScopeCoverage.UNVERIFIED
        )
        detail = (
            "clean-verified"
            if coverage is m.ScopeCoverage.VERIFIED
            else self._coverage_detail(stale, unverifiable)
        )
        return m.StructuralFreshnessReport(
            stale_files=tuple(stale),
            unverifiable_files=tuple(unverifiable),
            coverage=coverage,
            coverage_detail=detail,
        )

    def _scoped_version(self, scope: m.EvidenceScope | None) -> str:
        """Index version bound to the exact scope (J-10 token identity)."""
        if scope is None or not (scope.paths or scope.evidence_refs):
            return self._index_version
        return f"{self._index_version}|{m.evidence_scope_fingerprint(scope)}"

    def _versioned_offset(
        self, page_token: str | None, version: str | None = None
    ) -> int:
        """Decode a version-bound cursor; drift becomes StaleContinuation."""
        try:
            return _paging.parse_versioned_token(
                page_token,
                version=self._index_version if version is None else version,
            )
        except ValueError as exc:
            if str(exc).startswith("stale listing continuation"):
                raise StaleContinuationError(str(exc)) from None
            raise

    def _versioned_page(
        self,
        items: tuple[object, ...],
        offset: int,
        max_results: int,
        category: str,
        version: str | None = None,
    ) -> tuple[tuple[object, ...], m.BoundInfo]:
        kept = items[offset : offset + max_results]
        remaining = len(items) - (offset + len(kept))
        truncated = remaining > 0
        token_version = self._index_version if version is None else version
        return tuple(kept), m.BoundInfo(
            requested_max_results=max_results,
            requested_max_depth=0,
            returned_results=len(kept),
            truncated=truncated,
            truncated_category=category if truncated else None,
            continuation_token=(
                _paging.format_versioned_token(token_version, offset + len(kept))
                if truncated
                else None
            ),
        )

    def search_symbols(
        self,
        repository_id: str,
        query: str,
        match: m.StructuralLocateMatch,
        bounds: m.QueryBounds,
        page_token: str | None = None,
        scope: m.EvidenceScope | None = None,
    ) -> m.StructuralSearchPage:
        """Paginated name/locator search (Addendum F §4.0 port; J-10)."""
        self._check_repository(repository_id)
        self._ensure_fresh()
        self._require_index()
        if not query:
            raise ValueError("search query must be non-empty")
        version = self._scoped_version(scope)
        offset = self._versioned_offset(page_token, version=version)
        if match is m.StructuralLocateMatch.EXACT:
            locators = [query] if query in self._nodes else []
            ranked = [(loc, m.CandidateRankBasis.EXACT_LOCATOR) for loc in locators]
            if not ranked:
                # Bare symbol names never equal a path#symbol node id;
                # fall through to exact-name matching (F-01 recall fix).
                # Still exact-only: no substring matching in this mode.
                for node_id, node in self._nodes.items():
                    name = str(node.get("name") or "")
                    if query == name and query:
                        rank = (
                            m.CandidateRankBasis.EXACT_DECLARATION
                            if node["kind"] != "file"
                            else m.CandidateRankBasis.EXACT_NAME
                        )
                        ranked.append((node_id, rank))
                        continue
                    basename = node_id.split("#")[-1].rsplit("/", 1)[-1]
                    if query == basename:
                        ranked.append((node_id, m.CandidateRankBasis.EXACT_NAME))
                order = {
                    m.CandidateRankBasis.EXACT_LOCATOR: 0,
                    m.CandidateRankBasis.EXACT_DECLARATION: 1,
                    m.CandidateRankBasis.EXACT_NAME: 2,
                }
                ranked.sort(key=lambda x: (order[x[1]], x[0]))
        else:
            selector = m.SubjectSelector(
                exact_subject_id=None,
                name_or_locator=query,
                expected_kinds=(),
                retrieval_scope_hint=None,
            )
            ranked = [(loc, rank) for loc, rank in self._match_name(selector)]
            order = {
                m.CandidateRankBasis.EXACT_LOCATOR: 0,
                m.CandidateRankBasis.EXACT_DECLARATION: 1,
                m.CandidateRankBasis.EXACT_NAME: 2,
                m.CandidateRankBasis.PARTIAL_NAME: 3,
                m.CandidateRankBasis.STRUCTURAL_PROXIMITY: 4,
            }
            ranked.sort(key=lambda x: (order[x[1]], x[0]))
        if scope is not None:
            # J-10: filter the candidate population to the exact scope
            # BEFORE ranking materialisation and pagination so an
            # out-of-scope global match cannot consume a page or hide an
            # in-scope result.
            ranked = [
                (loc, rank)
                for loc, rank in ranked
                if m.evidence_scope_allows(loc, scope)
            ]
        candidates = tuple(
            m.StructuralSearchHit(
                candidate=m.SubjectCandidate(
                    subject=self._to_subject(loc),
                    structural_evidence=(),
                    rank_basis=rank,
                ),
                span_text=(str(node["span"]) if self._nodes[loc].get("span") else None),
                signature_text=(
                    str(node["signature"])
                    if isinstance(self._nodes[loc].get("signature"), str)
                    else None
                ),
            )
            for loc, rank in ranked
            for node in (self._nodes[loc],)
        )
        kept, bound_info = self._versioned_page(
            candidates, offset, bounds.max_results, "search", version=version
        )
        # Verify-then-exclude on the kept page: offsets advance over the
        # stable index list, so live drift only shrinks pages (counted),
        # never skips or duplicates entries.
        if scope is not None:
            # J-10: scope-local completeness. Verify all indexable files
            # inside the exact scope and prove scope currency against the
            # scoped committed baseline + scoped status — never global HEAD.
            scope_paths = tuple(sorted(scope.paths))
            scoped_files = tuple(
                sorted(
                    p for p in self._file_hashes if m.evidence_scope_allows(p, scope)
                )
            )
            stale, unverifiable = self._verify_exact_files(scoped_files)
            population_ok = self._scope_inventory_current(scope_paths)
        else:
            # Unscoped: whole-result completeness requires the repository
            # candidate population to be proven current.
            stale, unverifiable = self._verify_exact_files(
                tuple(
                    sorted(
                        {
                            self._node_path(
                                h.candidate.subject.subject_id.canonical_locator
                            )
                            for h in kept
                        }
                    )
                )
            )
            population_ok = self._repository_population_current()
        stale_set = set(stale)
        live_items = tuple(
            h
            for h in kept
            if self._node_path(h.candidate.subject.subject_id.canonical_locator)
            not in stale_set
        )
        stale_omitted = len(kept) - len(live_items)
        if not stale and not unverifiable and population_ok:
            coverage = m.ScopeCoverage.VERIFIED
            detail: str | None = "clean-verified"
        else:
            coverage = m.ScopeCoverage.UNVERIFIED
            if scope is not None:
                tokens: list[str] = []
                if not population_ok:
                    dirty = _git_scope_dirty(self._repo_path, scope_paths)
                    tokens.append(
                        "dirty-tree" if dirty else "repository-population-unverified"
                    )
                if stale:
                    tokens.append("touched-file-mismatch")
                if unverifiable:
                    tokens.append("unverifiable-file")
                detail = self._join_detail(tokens)
            else:
                detail = self._coverage_detail(stale, unverifiable)
        return m.StructuralSearchPage(
            items=live_items,  # type: ignore[arg-type]
            repository_state=self.repository_state(repository_id),
            bound_info=bound_info,
            unsupported=False,
            stale_omitted=stale_omitted,
            coverage=coverage,
            coverage_detail=detail,
        )

    def _node_path(self, locator: str) -> str:
        return str(self._nodes[locator]["path"])

    def file_outline(
        self,
        repository_id: str,
        locator: str,
        bounds: m.QueryBounds,
        page_token: str | None = None,
    ) -> m.StructuralOutlinePage:
        """Symbols defined in one file (Addendum F §4.0 port)."""
        self._check_repository(repository_id)
        self._ensure_fresh()
        self._require_index()
        offset = self._versioned_offset(page_token)
        members = sorted(
            node_id
            for node_id, node in self._nodes.items()
            if str(node["path"]) == locator
        )
        if not members:
            # Indexed-nothing here: empty, with coverage reflecting
            # whether a live file exists that the index missed.
            try:
                on_disk = (self._repo_path / locator).is_file()
            except OSError:
                on_disk = False
            coverage = (
                m.ScopeCoverage.UNVERIFIED if on_disk else m.ScopeCoverage.VERIFIED
            )
            kept, bound_info = self._versioned_page((), offset, 1, "outline")
            if coverage is m.ScopeCoverage.VERIFIED:
                detail: str | None = "clean-verified"
            else:
                detail = "unverifiable-file"
            return m.StructuralOutlinePage(
                items=(),
                repository_state=self.repository_state(repository_id),
                bound_info=bound_info,
                unsupported=False,
                stale_omitted=0,
                coverage=coverage,
                coverage_detail=detail,
            )
        entries = tuple(
            m.StructuralOutlineEntry(
                subject=self._to_subject(node_id),
                span_text=(
                    str(node["span"]) if self._nodes[node_id].get("span") else None
                ),
                signature_text=(
                    str(node["signature"])
                    if isinstance(self._nodes[node_id].get("signature"), str)
                    else None
                ),
            )
            for node_id in members
            for node in (self._nodes[node_id],)
        )
        kept, bound_info = self._versioned_page(
            entries, offset, bounds.max_results, "outline"
        )
        report = self.verify_files(repository_id, (locator,))
        stale_set = set(report.stale_files)
        live_items = () if locator in stale_set else kept  # type: ignore[assignment]
        stale_omitted = 0 if live_items else len(kept)
        # S2.2: a file outline is VERIFIED when the requested file matches
        # the loaded index; unrelated dirty files are irrelevant (J-7).
        if report.stale_files or report.unverifiable_files:
            coverage = m.ScopeCoverage.UNVERIFIED
            detail: str | None = self._file_detail(
                list(report.stale_files), list(report.unverifiable_files)
            )
        else:
            coverage = m.ScopeCoverage.VERIFIED
            detail = "clean-verified"
        return m.StructuralOutlinePage(
            items=tuple(live_items),  # type: ignore[arg-type]
            repository_state=self.repository_state(repository_id),
            bound_info=bound_info,
            unsupported=False,
            stale_omitted=stale_omitted,
            coverage=coverage,
            coverage_detail=detail,
        )

    # -- parsing ----------------------------------------------------------

    def _parse_nodes(self, wiring: dict) -> dict[str, dict]:
        try:
            raw_nodes = wiring["nodes"]
        except (KeyError, TypeError) as exc:
            raise GraftShapeError("wiring.json has no nodes list") from exc
        if not isinstance(raw_nodes, list):
            raise GraftShapeError("wiring.json nodes is not a list")
        nodes: dict[str, dict] = {}
        for node in raw_nodes:
            try:
                node_id = node["id"]
                kind = node["kind"]
                _ = node["path"]  # required key; the raw node carries it
            except (KeyError, TypeError) as exc:
                raise GraftShapeError(f"node missing id/kind/path: {node!r}") from exc
            if kind not in NODE_SUBJECT_KIND:
                raise GraftVocabularyError(f"unknown structural node kind: {kind}")
            nodes[node_id] = node
        return nodes

    def _resolve_dotted(self, endpoint: str, file_ids: dict[str, str]) -> str | None:
        """Map a dotted module id to a known file node, or None.

        Provider-local evidence join (Addendum G follow-up): import
        edges recorded against dotted module ids (``pkg.mod``) attach
        to the file node they denote, so file-level traversal sees
        them. ``file_ids`` maps file paths to node ids, built once per
        parse (never per endpoint). Rules, in order: symbol fragments
        (``#``) never map; longest dotted suffix wins; a ``mod.py``
        versus ``mod/__init__.py`` tie stays unmapped rather than
        guessed; anything else stays unmapped and the edge is skipped
        exactly as before. Only FILE-kind nodes are targets.
        """
        if "#" in endpoint:
            return None
        parts = endpoint.split(".")
        for i in range(len(parts)):
            rel = "/".join(parts[i:])
            if not rel:
                continue
            module = rel + ".py"
            package = rel + "/__init__.py"
            has_module = module in file_ids
            has_package = package in file_ids
            if has_module and has_package:
                return None
            if has_module:
                return file_ids[module]
            if has_package:
                return file_ids[package]
        return None

    def _parse_edges(self, wiring: dict) -> list[tuple[str, str, str]]:
        raw_edges = wiring.get("edges", [])
        if not isinstance(raw_edges, list):
            raise GraftShapeError("wiring.json edges is not a list")
        # File-node path map, built once per parse: dotted-module
        # resolution below consults it per missing endpoint without
        # rebuilding (startup-cost bound; see DottedModuleMappingTest).
        file_ids: dict[str, str] = {}
        for node_id, node in self._nodes.items():
            if node.get("kind") == "file" and node.get("path"):
                file_ids.setdefault(str(node.get("path")), node_id)
        edges: list[tuple[str, str, str]] = []
        for edge in raw_edges:
            try:
                source, target, relation = (
                    edge["source"],
                    edge["target"],
                    edge["relation"],
                )
            except (KeyError, TypeError) as exc:
                raise GraftShapeError(
                    f"edge missing source/target/relation: {edge!r}"
                ) from exc
            if relation not in RELATION_EDGE_KIND:
                raise GraftVocabularyError(
                    f"unknown structural edge relation: {relation}"
                )
            # Dangling edges reference modules outside the index
            # (stdlib/third-party imports, unindexed supertypes).
            # A StructuralEdge needs canonical SubjectIds for both
            # ends (§4.2), so unresolvable endpoints are skipped,
            # never guessed into identity. Dotted module ids get one
            # resolution attempt against known file nodes first; the
            # path map is built once per parse above, never per edge.
            if source not in self._nodes:
                mapped = self._resolve_dotted(source, file_ids)
                if mapped is None:
                    continue
                source = mapped
            if target not in self._nodes:
                mapped = self._resolve_dotted(target, file_ids)
                if mapped is None:
                    continue
                target = mapped
            edges.append((source, target, relation))
        return edges

    # -- mapping ------------------------------------------------------------

    def _subject_kind_of(self, node: dict) -> m.SubjectKind:
        if node["kind"] == "file" and str(node["path"]).endswith(_DOCUMENT_SUFFIXES):
            return m.SubjectKind.DOCUMENT
        return NODE_SUBJECT_KIND[node["kind"]]

    def _subject_id_of(self, node_id: str) -> m.SubjectId:
        node = self._nodes[node_id]
        return m.SubjectId(
            repository_id=self._repository_id,
            subject_kind=self._subject_kind_of(node),
            canonical_locator=node_id,
        )

    def _to_subject(self, node_id: str) -> m.Subject:
        node = self._nodes[node_id]
        return m.Subject(
            subject_id=self._subject_id_of(node_id),
            display_name=str(node.get("name") or node_id),
            declared_kind=None,
        )

    def fingerprint_for(self, path: str, body_hash: str | None) -> str | None:
        """Body hash preferred; target file content fallback; None when
        neither is available (downstream classifies UNVERIFIABLE)."""
        if body_hash:
            return body_hash
        try:
            return fingerprint_content(
                (self._repo_path / path).read_text(encoding="utf-8")
            )
        except OSError:
            return None

    def _evidence_ref(self, node_id: str) -> m.EvidenceRef:
        node = self._nodes[node_id]
        path = str(node["path"])
        return m.EvidenceRef(
            evidence_id=m.EvidenceId(f"ev-{path}"),
            repository_id=self._repository_id,
            source_kind=evidence_kind_for_path(path),
            locator=path,
            revision_or_fingerprint=self.fingerprint_for(
                path,
                (
                    node.get("body_hash")
                    if isinstance(node.get("body_hash"), str)
                    else None
                ),
            ),
            section_or_span=(str(node["span"]) if node.get("span") else None),
        )

    def _to_edge(self, source: str, target: str, relation: str) -> m.StructuralEdge:
        return m.StructuralEdge(
            source=self._subject_id_of(source),
            kind=RELATION_EDGE_KIND[relation],
            target=self._subject_id_of(target),
            evidence=self._evidence_ref(source),
        )

    def _state_fingerprint(self) -> str:
        key = (self._wiring_mtime_ns, self._wiring_size)
        memo = self._state_fingerprint_memo
        if memo is not None and (memo[0], memo[1]) == key:
            return memo[2]
        parts = sorted(
            f"{node_id}:{node.get('body_hash') or ''}"
            for node_id, node in self._nodes.items()
        )
        digest = _hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
        self._state_fingerprint_memo = (
            self._wiring_mtime_ns,
            self._wiring_size,
            digest,
        )
        return digest

    def _check_repository(self, repository_id: str) -> None:
        if repository_id != self._repository_id:
            raise ValueError(f"unknown repository: {repository_id}")

    # -- StructuralSource port --------------------------------------------

    def repository_state(self, repository_id: str) -> m.RepositoryState:
        self._check_repository(repository_id)
        self._ensure_fresh()
        import datetime as _datetime

        revision, dirty = _git_revision(self._repo_path)
        return m.RepositoryState(
            repository_id=self._repository_id,
            revision_id=revision,
            dirty=dirty,
            state_fingerprint=self._state_fingerprint(),
            observed_at=_datetime.datetime.now(_datetime.timezone.utc),
        )

    def describe_current(
        self,
        repository_id: str,
    ) -> m.Freshness:
        """Index currency verdict (lifecycle contract).

        Read-only: never builds. No usable index reports UNVERIFIABLE
        (setup has not produced one yet). Dirty trees and non-git/
        injected indexes report UNVERIFIABLE (completeness unprovable);
        an index older than HEAD reports STALE.
        """
        self._check_repository(repository_id)
        self._ensure_fresh()
        if not self._loaded:
            return m.Freshness(
                state=m.FreshnessState.UNVERIFIABLE,
                reason="no structural index built yet",
            )
        if self._wiring_path is None:
            return m.Freshness(
                state=m.FreshnessState.UNVERIFIABLE,
                reason="injected index has no on-disk build to verify",
            )
        revision, dirty = _git_revision(self._repo_path)
        if revision is None:
            return m.Freshness(
                state=m.FreshnessState.UNVERIFIABLE,
                reason="non-git tree: index currency unestablishable",
            )
        if dirty:
            return m.Freshness(
                state=m.FreshnessState.UNVERIFIABLE,
                reason="dirty tree: index cannot prove completeness",
            )
        head_time = _git_head_time(self._repo_path)
        if head_time is None:
            return m.Freshness(
                state=m.FreshnessState.UNVERIFIABLE,
                reason="HEAD time unreadable: index currency unestablishable",
            )
        if (
            self._wiring_mtime_ns is not None
            and self._wiring_mtime_ns < head_time * 1_000_000_000
        ):
            return m.Freshness(
                state=m.FreshnessState.STALE,
                reason="index-older-than-head",
            )
        return m.Freshness(
            state=m.FreshnessState.CURRENT,
            reason="index covers tree",
        )

    def _index_missing_or_stale(self) -> bool:
        """Whether an explicit setup/refresh call warrants one bounded build.

        Missing means nothing usable is loaded or there is no provable
        build time. Stale means the index predates HEAD. A dirty working
        tree also warrants one bounded build when the caller explicitly
        asked for currency (`initialize_repository`, `refresh`): the
        build indexes the current working tree instead of leaving a
        graph that still represents pre-edit topology. The resulting
        freshness stays UNVERIFIABLE because a dirty tree cannot prove
        completeness; that limit must not be used to keep serving an
        intentionally old graph. Ordinary reads never reach this method.
        """
        if not self._loaded:
            return True
        if self._wiring_mtime_ns is None:
            return True
        revision, dirty = _git_revision(self._repo_path)
        if revision is None:
            return False
        if dirty:
            return True
        head_time = _git_head_time(self._repo_path)
        if head_time is None:
            return False
        return self._wiring_mtime_ns < head_time * 1_000_000_000

    def ensure_current(
        self,
        repository_id: str,
    ) -> m.Freshness:
        """Refresh the provider index into the provider cache, then report.

        Provider-owned execution (lifecycle contract): one bounded
        ``graft --dir <cache> build`` for this adapter's repo root — no
        ``--deep`` pass, no credentials, no target writes — and only
        when the index is missing, stale, or the working tree is dirty
        (``_index_missing_or_stale``).
        At most one build attempt, guarded by a provider-local lock per
        cache location; concurrent callers serialize on the lock.
        Reloads and validates after a successful build. Build failures
        and malformed/missing output return UNVERIFIABLE with a reason;
        never raise. Invoked only from `initialize_repository`
        provisioning and explicit `refresh`, never from ordinary reads.
        """
        self._check_repository(repository_id)
        current = self.describe_current(repository_id)
        if current.state is m.FreshnessState.CURRENT:
            return current
        if not self._index_missing_or_stale():
            return current
        lock_key = str(
            self._wiring_path if self._wiring_path is not None else self._repo_path
        )
        lock = _build_lock_for(lock_key)
        with lock:
            # Re-check under the lock: a concurrent setup may have
            # already rebuilt.
            current = self.describe_current(repository_id)
            if current.state is m.FreshnessState.CURRENT:
                return current
            if not self._index_missing_or_stale():
                return current
            assert self._artifact_dir is not None
            ok, detail = _run_index_build(self._repo_path, self._artifact_dir)
            if not ok:
                return m.Freshness(
                    state=m.FreshnessState.UNVERIFIABLE,
                    reason=f"index rebuild unavailable: {detail}",
                )
            self._load_from_disk()
            if not self._loaded:
                return m.Freshness(
                    state=m.FreshnessState.UNVERIFIABLE,
                    reason="index rebuild produced no usable wiring.json",
                )
            return self.describe_current(repository_id)

    def resolve_subject(
        self,
        repository_id: str,
        selector: m.SubjectSelector,
        bounds: m.QueryBounds,
    ) -> m.SubjectResolution:
        self._check_repository(repository_id)
        self._ensure_fresh()
        self._require_index()
        if selector.exact_subject_id is not None:
            locator = selector.exact_subject_id.canonical_locator
            matches = [
                (locator, m.CandidateRankBasis.EXACT_LOCATOR)
                for locator in [locator]
                if locator in self._nodes
            ]
        else:
            matches = self._match_name(selector)
        if selector.expected_kinds:
            wanted = set(selector.expected_kinds)
            filtered: list[tuple[str, m.CandidateRankBasis]] = []
            for locator, rank in matches:
                node = self._nodes.get(locator)
                if node is None:
                    continue
                if self._subject_kind_of(node) in wanted:
                    filtered.append((locator, rank))
            matches = filtered
        order = {
            m.CandidateRankBasis.EXACT_LOCATOR: 0,
            m.CandidateRankBasis.EXACT_DECLARATION: 1,
            m.CandidateRankBasis.EXACT_NAME: 2,
            m.CandidateRankBasis.PARTIAL_NAME: 3,
            m.CandidateRankBasis.STRUCTURAL_PROXIMITY: 4,
        }
        matches.sort(key=lambda x: (order[x[1]], x[0]))
        candidates = tuple(
            m.SubjectCandidate(
                subject=self._to_subject(locator),
                structural_evidence=(),
                rank_basis=rank,
            )
            for locator, rank in matches
        )
        if not candidates:
            ambiguity = m.ResolutionAmbiguity.NOT_FOUND
        elif len(candidates) == 1:
            ambiguity = m.ResolutionAmbiguity.RESOLVED
        else:
            ambiguity = m.ResolutionAmbiguity.AMBIGUOUS
        kept = candidates[: bounds.max_subjects]
        return m.SubjectResolution(
            candidates=kept,
            ambiguity=ambiguity,
            bound_info=m.BoundInfo(
                requested_max_results=bounds.max_subjects,
                requested_max_depth=0,
                returned_results=len(kept),
                truncated=len(kept) < len(candidates),
                truncated_category=(
                    "candidates" if len(kept) < len(candidates) else None
                ),
                continuation_token=None,
            ),
        )

    def _match_name(
        self, selector: m.SubjectSelector
    ) -> list[tuple[str, m.CandidateRankBasis]]:
        query = selector.name_or_locator
        if not query:
            return []
        # §4.2 identity: exact node id is identity, not a ranking input.
        exact = [
            (node_id, m.CandidateRankBasis.EXACT_LOCATOR)
            for node_id in self._nodes
            if query == node_id
        ]
        if exact:
            return exact
        matches: list[tuple[str, m.CandidateRankBasis]] = []
        for node_id, node in self._nodes.items():
            name = str(node.get("name") or "")
            if query == name and query:
                rank = (
                    m.CandidateRankBasis.EXACT_DECLARATION
                    if node["kind"] != "file"
                    else m.CandidateRankBasis.EXACT_NAME
                )
                matches.append((node_id, rank))
                continue
            basename = node_id.split("#")[-1].rsplit("/", 1)[-1]
            if query == basename:
                matches.append((node_id, m.CandidateRankBasis.EXACT_NAME))
            elif query in name or query in node_id:
                matches.append((node_id, m.CandidateRankBasis.PARTIAL_NAME))
        return matches

    def locations(
        self,
        repository_id: str,
        subject: m.SubjectId,
        bounds: m.QueryBounds,
        page_token: str | None = None,
    ) -> m.StructuralLocationPage:
        self._check_repository(repository_id)
        self._ensure_fresh()
        self._require_index()
        node = self._nodes.get(subject.canonical_locator)
        items: tuple[m.StructuralLocation, ...] = ()
        if node is not None:
            items = (
                m.StructuralLocation(
                    subject=subject,
                    location=self._evidence_ref(subject.canonical_locator),
                ),
            )
        kept, bound_info = _paging.paginate(
            items, bounds.max_results, "locations", page_token
        )
        return m.StructuralLocationPage(
            items=tuple(kept),  # type: ignore[arg-type]
            repository_state=self.repository_state(repository_id),
            bound_info=bound_info,
            unsupported=False,
        )

    def edges(
        self,
        repository_id: str,
        subject: m.SubjectId,
        edge_kinds: tuple[m.StructuralEdgeKind, ...],
        direction: StructuralDirection,
        bounds: m.QueryBounds,
        page_token: str | None = None,
    ) -> m.StructuralEdgePage:
        self._check_repository(repository_id)
        self._ensure_fresh()
        self._require_index()
        locator = subject.canonical_locator
        kinds = set(edge_kinds) if edge_kinds else set(m.StructuralEdgeKind)
        found: list[m.StructuralEdge] = []
        for source, target, relation in self._edges:
            edge = self._to_edge(source, target, relation)
            if edge.kind not in kinds:
                continue
            if (
                direction
                in (
                    StructuralDirection.DOWNSTREAM,
                    StructuralDirection.BOTH,
                )
                and source == locator
            ):
                found.append(edge)
            elif (
                direction
                in (
                    StructuralDirection.UPSTREAM,
                    StructuralDirection.BOTH,
                )
                and target == locator
            ):
                found.append(edge)
        found.sort(
            key=lambda e: (
                e.kind.value,
                e.source.canonical_locator,
                e.target.canonical_locator,
            )
        )
        kept, bound_info = _paging.paginate(
            tuple(found), bounds.max_results, "edges", page_token
        )
        return m.StructuralEdgePage(
            items=tuple(kept),  # type: ignore[arg-type]
            repository_state=self.repository_state(repository_id),
            bound_info=bound_info,
            unsupported=False,
        )

    def _all_edges(
        self,
        repository_id: str,
        subject: m.SubjectId,
        edge_kinds: tuple[m.StructuralEdgeKind, ...],
        direction: StructuralDirection,
        bounds: m.QueryBounds,
    ) -> list[m.StructuralEdge]:
        """Consume every adjacency page for one node (Addendum F §4.2).

        Single-page reads silently drop branches past the page limit;
        traversal always exhausts continuations. Defensive against a
        non-advancing token (breaks rather than loops forever).
        """
        out: list[m.StructuralEdge] = []
        seen_tokens: set[str | None] = {None}
        token: str | None = None
        while True:
            page = self.edges(
                repository_id,
                subject,
                edge_kinds,
                direction,
                bounds,
                token,
            )
            out.extend(page.items)
            if not page.bound_info.truncated:
                break
            token = page.bound_info.continuation_token
            if token in seen_tokens:
                break
            seen_tokens.add(token)
        return out

    def reach(
        self,
        repository_id: str,
        subject: m.SubjectId,
        edge_kinds: tuple[m.StructuralEdgeKind, ...],
        direction: StructuralDirection,
        max_depth: int,
        bounds: m.QueryBounds,
        page_token: str | None = None,
    ) -> m.StructuralReachPage:
        self._check_repository(repository_id)
        self._ensure_fresh()
        self._require_index()
        limit = min(max_depth, bounds.max_depth)
        if subject.canonical_locator not in self._nodes:
            # Semantic-only area subjects are never structural nodes.
            # Return the empty page (consistent with locations()/edges()
            # for unresolvable identity: skipped, never guessed) instead
            # of leaking KeyError; callers such as impact treat empty
            # reach as claims-only coverage with explicit limits.
            kept, bound_info = _paging.paginate(
                (),
                bounds.max_results,
                "reach",
                page_token,
                requested_max_depth=limit,
            )
            return m.StructuralReachPage(
                items=tuple(kept),  # type: ignore[arg-type]
                repository_state=self.repository_state(repository_id),
                bound_info=bound_info,
                unsupported=False,
            )
        seen = {subject.canonical_locator}
        via: dict[str, m.StructuralEdge | None] = {subject.canonical_locator: None}
        frontier = [subject.canonical_locator]
        nodes: list[m.StructuralReachNode] = []
        # Exhaustion rule (Addendum F §4.2): every adjacency page of
        # every visited node is consumed — a single first page would
        # silently drop whole branches past the page limit. The visited
        # cap bounds total work; hitting it truncates explicitly.
        visit_cap = bounds.max_subjects
        capped = False
        for depth in range(1, limit + 1):
            nxt: list[str] = []
            for current in frontier:
                if len(seen) >= visit_cap:
                    capped = True
                    break
                current_id = m.SubjectId(
                    repository_id=self._repository_id,
                    subject_kind=self._subject_kind_of(self._nodes[current]),
                    canonical_locator=current,
                )
                for edge in self._all_edges(
                    repository_id,
                    current_id,
                    edge_kinds,
                    direction,
                    bounds,
                ):
                    other = (
                        edge.target.canonical_locator
                        if edge.source.canonical_locator == current
                        else edge.source.canonical_locator
                    )
                    if other not in seen and other in self._nodes:
                        seen.add(other)
                        via[other] = edge
                        nxt.append(other)
            nxt.sort()
            for locator in nxt:
                nodes.append(
                    m.StructuralReachNode(
                        subject=self._subject_id_of(locator),
                        depth=depth,
                        via=via[locator],
                    )
                )
            frontier = nxt
            if not frontier or capped:
                break
        kept, bound_info = _paging.paginate(
            tuple(nodes),
            bounds.max_results,
            "reach",
            page_token,
            requested_max_depth=limit,
        )
        if capped and not bound_info.truncated:
            bound_info = m.BoundInfo(
                requested_max_results=bound_info.requested_max_results,
                requested_max_depth=bound_info.requested_max_depth,
                returned_results=bound_info.returned_results,
                truncated=True,
                truncated_category="reach",
                continuation_token=bound_info.continuation_token,
            )
        return m.StructuralReachPage(
            items=tuple(kept),  # type: ignore[arg-type]
            repository_state=self.repository_state(repository_id),
            bound_info=bound_info,
            unsupported=False,
        )
