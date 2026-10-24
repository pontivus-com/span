"""Cross-platform-capable Span installer (Linux implemented).

Stdlib only. No ``span.*`` imports at module top level: this module
must run from a source checkout (via ``scripts/install-span.py``)
before Span is installed, and post-install as the ``span-install``
entry point. All Span imports are lazy inside verification paths.

OS specifics live exclusively in ``PLATFORM_PATHS``; ``linux`` is
fully specified, ``darwin``/``win32`` are structurally reserved.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

INSTALL_VERSION = 1

#: Managed structural-indexer identity (npm). The installer provisions
#: exactly this package version into Span's tools directory so users
#: never install or name the indexer themselves. Keep in sync with
#: ``STRUCTURAL_INDEXER_{PACKAGE,VERSION}`` in
#: ``span/shell/structural/graft.py`` (duplicated, not imported: this
#: module must stay stdlib-only at top level).
STRUCTURAL_INDEXER_PACKAGE = "@nanonets/graft"
STRUCTURAL_INDEXER_VERSION = "0.25.0"

# Only this table varies by OS. Everything else is platform-neutral.
PLATFORM_PATHS = {
    "linux": {
        "venv_dir": ("~/.local/share/span/venv",),
        "data_dir": ("~/.local/share/span/data",),
        "bin_dir": ("~/.local/bin",),
        "supported": True,
    },
    "darwin": {
        "venv_dir": ("~/Library/Application Support/span/venv",),
        "data_dir": ("~/Library/Application Support/span/data",),
        "bin_dir": ("~/.local/bin",),
        "supported": False,
        "note": "paths reserved; runner verification pending",
    },
    "win32": {
        "venv_dir": ("%LOCALAPPDATA%/span/venv",),
        "data_dir": ("%LOCALAPPDATA%/span/data",),
        "bin_dir": ("%APPDATA%/span/bin",),
        "supported": False,
        "note": "paths reserved; shim strategy pending (.cmd, no symlink)",
    },
}

SCHEMA_SENTINEL = "SCHEMA_VERSION"

AGENTS_START = "<!-- span:start -->"
AGENTS_END = "<!-- span:end -->"


def platform_paths(platform=None):
    """Resolve install locations for one platform key.

    Raises SystemExit with a clear message on unsupported platforms
    instead of guessing paths.
    """
    key = platform or sys.platform
    try:
        entry = PLATFORM_PATHS[key]
    except KeyError:
        raise SystemExit(f"unsupported platform for install: {key}")
    if not entry.get("supported", False):
        raise SystemExit(
            f"install paths reserved but not yet verified for: {key} "
            f"({entry.get('note', 'no note')})"
        )
    return {
        name: Path(os.path.expandvars(os.path.expanduser(value[0])))
        for name, value in entry.items()
        if isinstance(value, tuple)
    }


def check_prereqs():
    """Fail closed naming the first missing prerequisite."""
    errors = []
    if sys.version_info < (3, 12):
        errors.append(f"python >= 3.12 required, found {sys.version.split()[0]}")
    # Node and npm provision the managed structural indexer at install
    # time; the indexer itself is never a user prerequisite.
    for tool in ("node", "npm"):
        if shutil.which(tool) is None:
            errors.append(f"required tool missing from PATH: {tool}")
    if errors:
        raise SystemExit("prerequisites missing:\n- " + "\n- ".join(errors))


def default_tools_dir(venv_dir):
    """Span-owned tools directory holding the managed indexer install."""
    return Path(venv_dir).parent / "tools"


def indexer_binary_path(tools_dir):
    """Expected indexer binary inside a tools directory."""
    return Path(tools_dir) / "node_modules" / ".bin" / "graft"


def _redact_provider(text):
    """Keep the managed provider name out of end-user output."""
    text = text.replace(STRUCTURAL_INDEXER_PACKAGE, "structural indexer")
    return text.replace("graft", "structural-indexer")


def ensure_structural_indexer(venv_dir, dry_run=False):
    """Provision the pinned structural indexer (auto-install, no bundle).

    Installs exactly ``STRUCTURAL_INDEXER_PACKAGE @ VERSION`` via npm
    into Span's tools directory (never global, never into targets).
    Idempotent: skips reinstall only when the managed binary and its
    installed package metadata both name this exact version. Returns the
    binary path.
    """
    tools_dir = default_tools_dir(venv_dir)
    binary = indexer_binary_path(tools_dir)
    package_json = (
        tools_dir / "node_modules" / STRUCTURAL_INDEXER_PACKAGE / "package.json"
    )
    installed_version = None
    try:
        metadata = json.loads(package_json.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        metadata = None
    if isinstance(metadata, dict):
        if metadata.get("name") == STRUCTURAL_INDEXER_PACKAGE:
            installed_version = metadata.get("version")
    if binary.is_file() and installed_version == STRUCTURAL_INDEXER_VERSION:
        return str(binary)
    print(
        f"+ provision structural indexer "
        f"{STRUCTURAL_INDEXER_VERSION} -> {tools_dir}"
    )
    if dry_run:
        return str(binary)
    cmd = [
        "npm",
        "install",
        "--prefix",
        str(tools_dir),
        "--no-audit",
        "--no-fund",
        f"{STRUCTURAL_INDEXER_PACKAGE}@{STRUCTURAL_INDEXER_VERSION}",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        detail = _redact_provider(proc.stderr.strip() or proc.stdout.strip())
        raise SystemExit(
            f"structural indexer provisioning failed " f"({proc.returncode}): {detail}"
        )
    if not binary.is_file():
        raise SystemExit(
            "structural indexer provisioning produced no binary in "
            "the managed tools directory"
        )
    return str(binary)


def write_indexer_pointer(data_dir, binary, dry_run=False):
    """Record the provisioned indexer pointer under the data dir."""
    payload = {
        "package": STRUCTURAL_INDEXER_PACKAGE,
        "version": STRUCTURAL_INDEXER_VERSION,
        "binary": str(binary),
    }
    print(f"+ write indexer pointer: {Path(data_dir) / 'structural-indexer.json'}")
    if dry_run:
        return payload
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    (Path(data_dir) / "structural-indexer.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )
    return payload


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="span-install",
        description=(
            "Install span-mcp, register host MCP entries, initialize "
            "target repositories, and verify readiness. Linux only; "
            "other platforms are structurally reserved, not silently attempted."
        ),
    )
    parser.add_argument(
        "--repo",
        action="append",
        default=[],
        metavar="TARGET_DIR",
        help=(
            "Target repository root (repeatable). Provisioning builds "
            "the structural index into Span's data directory when "
            "needed (no --deep, no credentials, no target writes)."
        ),
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="SQLite store directory (default: platform data dir). "
        "Refused when inside any target repo.",
    )
    parser.add_argument(
        "--venv-dir",
        default=None,
        help="Virtualenv location (default: platform venv dir).",
    )
    parser.add_argument(
        "--bin-dir",
        default=None,
        help="Directory receiving the span-mcp symlink " "(default: platform bin dir).",
    )
    parser.add_argument(
        "--span-repo",
        default=".",
        help="Span source checkout to install (default: cwd).",
    )
    parser.add_argument(
        "--opencode-config",
        default=None,
        help="opencode.json to merge the span MCP entry into. "
        "Default: ./opencode.json when present, else skipped.",
    )
    parser.add_argument(
        "--with-codex",
        action="store_true",
        default=None,
        help="Register via `codex mcp add` (default: automatic when "
        "the codex CLI is present; --no-codex to skip).",
    )
    parser.add_argument(
        "--no-codex",
        action="store_true",
        help="Skip all Codex integration even when detected.",
    )
    parser.add_argument(
        "--with-claude",
        action="store_true",
        default=None,
        help="Register via `claude mcp add` (default: automatic when "
        "the claude CLI is present; --no-claude to skip).",
    )
    parser.add_argument(
        "--no-claude",
        action="store_true",
        help="Skip all Claude Code integration even when detected.",
    )
    parser.add_argument(
        "--with-hooks",
        action="store_true",
        default=None,
        help="Wire report-only lifecycle hooks (default: automatic "
        "when a supported host is detected; --no-hooks to skip). "
        "Hooks only report readiness/dependents/closure; they never "
        "write, interpret, refresh, or initialize.",
    )
    parser.add_argument(
        "--no-hooks",
        action="store_true",
        help="Skip hook wiring even when hosts are detected.",
    )
    parser.add_argument(
        "--no-skills",
        action="store_true",
        help="Skip skill deployment even when hosts are detected.",
    )
    parser.add_argument(
        "--authority-seeds-file",
        default=None,
        help="JSON file with canonical EvidenceRef items for init. "
        "Absent means no seeds; seeds are never invented.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned actions; execute nothing.",
    )
    parser.add_argument(
        "--snapshot-census",
        default=None,
        metavar="OUT_JSON",
        help="Write a read-only target artifact census snapshot and exit.",
    )
    parser.add_argument(
        "--compare-census",
        nargs=2,
        default=None,
        metavar=("BEFORE", "AFTER"),
        help="Diff two census snapshots with a readable verdict and exit.",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Skip install; verify an existing installation and exit.",
    )
    return parser.parse_args(argv)


def _run(cmd, cwd=None, dry_run=False, label=None):
    print("+", label if label is not None else " ".join(str(c) for c in cmd))
    if dry_run:
        return None
    proc = subprocess.run(
        [str(c) for c in cmd], cwd=cwd, capture_output=True, text=True
    )
    if proc.returncode != 0:
        raise SystemExit(
            f"command failed ({proc.returncode}): {' '.join(str(c) for c in cmd)}\n"
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc.stdout


def ensure_venv(venv_dir, dry_run=False):
    venv_dir = Path(venv_dir)
    if (venv_dir / "bin" / "python").exists():
        print(f"venv exists, reusing: {venv_dir}")
        return venv_dir / "bin" / "python"
    # Prefer `uv venv` when available: some system pythons ship
    # without pip bootstrap or with relocated stdlib layouts that
    # `python -m venv` cannot reproduce. Fall back to stdlib venv.
    uv = shutil.which("uv")
    if uv is not None:
        _run([uv, "venv", str(venv_dir)], dry_run=dry_run)
        return venv_dir / "bin" / "python"
    try:
        _run([sys.executable, "-m", "venv", str(venv_dir)], dry_run=dry_run)
    except SystemExit:
        # Debian-style pythons ship without pip bootstrap; retry
        # without pip and install through uv when available.
        print("venv pip bootstrap unavailable; retrying --without-pip")
        _run(
            [sys.executable, "-m", "venv", "--without-pip", str(venv_dir)],
            dry_run=dry_run,
        )
    return venv_dir / "bin" / "python"


def _has_venv_pip(venv_python, dry_run=False):
    if dry_run:
        return True
    proc = subprocess.run(
        [str(venv_python), "-m", "pip", "--version"],
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


def _hash_tree(root):
    """Map relative .py paths to sha256 bytes (verify-fast-path)."""
    out = {}
    for path in sorted(root.rglob("*.py")):
        try:
            data = path.read_bytes()
        except OSError:
            continue
        out[str(path.relative_to(root))] = hashlib.sha256(data).digest()
    return out


def source_venv_in_sync(span_repo, venv_python):
    """Verify-fast-path (Addendum E §9.2): compare source against venv.

    Returns (in_sync, files_checked, extra_files). Every source file
    must exist in the venv with identical bytes. Extra venv files
    (stale remnants pip reinstall never removes) are reported, not
    synced-away: they cannot be fixed by reinstalling, only by
    recreating the venv, so they warn instead of forcing reinstall
    loops. Missing venv tree or unreadable files count as drift.
    """
    venv_site = Path(venv_python).parent.parent / "lib"
    candidates = sorted(venv_site.glob("python*/site-packages/span"))
    if not candidates:
        return False, 0, ()
    source = _hash_tree(Path(span_repo) / "src" / "span")
    installed = _hash_tree(candidates[0])
    if not source:
        return False, 0, ()
    extra = sorted(set(installed) - set(source))
    in_sync = all(
        name in installed and installed[name] == digest
        for name, digest in source.items()
    )
    return in_sync, len(source), tuple(extra)


def backup_data_dir(data_dir, dry_run=False):
    """Online SQLite backup before mutation (Addendum E §9.2).

    Copies every ``*.db`` under the data dir into a timestamped
    ``backups/`` subdirectory using the sqlite3 online backup API
    (consistent under concurrent readers). Returns the backup dir, or
    None when there is nothing to back up. Never touches targets.
    """
    data_dir = Path(data_dir)
    if dry_run or not data_dir.is_dir():
        return None
    dbs = sorted(data_dir.glob("*.db"))
    if not dbs:
        return None
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S")
    dest_dir = data_dir / "backups" / stamp
    try:
        dest_dir.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        raise SystemExit(f"cannot create backup dir {dest_dir}: {exc}")
    for db in dbs:
        try:
            src = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            try:
                dst = sqlite3.connect(str(dest_dir / db.name))
                try:
                    src.backup(dst)
                finally:
                    dst.close()
            finally:
                src.close()
        except Exception as exc:
            raise SystemExit(f"backup failed for {db}: {exc}")
    print(f"data dir backed up: {dest_dir} ({len(dbs)} databases).")
    return str(dest_dir)


def snapshot_census(targets, out_path, dry_run=False):
    """Write a read-only artifact census snapshot (Addendum E §9.2)."""
    payload = {str(t): target_artifact_snapshot(t) for t in targets}
    print(f"+ snapshot census: {out_path}")
    if dry_run:
        return payload
    Path(out_path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


def compare_census(path_a, path_b):
    """Diff two census snapshots with a readable verdict (E §9.2).

    Evidence only, never a gate: a changed wiring mtime may be a
    legitimate offline rebuild. Always exits 0; the verdict is in the
    printed lines.
    """

    def _load(path):
        try:
            data = json.loads(Path(path).read_text())
        except (OSError, ValueError) as exc:
            raise SystemExit(f"cannot read census snapshot {path}: {exc}")
        if not isinstance(data, dict):
            raise SystemExit(f"census snapshot is not an object: {path}")
        return data

    before, after = _load(path_a), _load(path_b)
    changed = []
    for target in sorted(set(before) | set(after)):
        old, new = before.get(target), after.get(target)
        if old != new:
            changed.append(target)
            print(f"CHANGED: {target}")
            print(f"  before: {json.dumps(old, sort_keys=True)}")
            print(f"  after:  {json.dumps(new, sort_keys=True)}")
        else:
            print(f"UNCHANGED: {target}")
    if changed:
        print(f"census verdict: {len(changed)} target(s) changed.")
    else:
        print("census verdict: no changes.")
    return changed


def _clean_build_staging(span_repo, dry_run=False):
    """Remove regenerable build staging (Addendum E §9.2).

    A stale ``build/`` directory or egg-info from before a refactor
    flip is reused by setuptools and ships deleted modules into the
    venv — the exact silent-staleness class tier 1 exists to kill.
    Both paths are gitignored regenerables; removing them can only
    force a clean build, never lose source.
    """
    removed = []
    for candidate in (
        Path(span_repo) / "build",
        *Path(span_repo, "src").glob("*.egg-info"),
    ):
        if not candidate.exists() and not candidate.is_symlink():
            continue
        print(f"+ clean build staging: {candidate}")
        if dry_run:
            removed.append(str(candidate))
            continue
        if candidate.is_symlink() or candidate.is_file():
            candidate.unlink()
        else:
            shutil.rmtree(candidate)
        removed.append(str(candidate))
    return removed


#: Stdlib-only version probe run inside the runtime venv. Used only in
#: distribution mode, where there is no source tree to hash.
_VERSION_PROBE = "import importlib.metadata as m; print(m.version('span-mcp'))"


def install_mode(span_repo):
    """Where the runtime comes from: a source checkout or a distribution.

    ``span-install`` is reachable in both cases. Only a checkout has
    ``src/span``, the build staging setuptools reuses, and the canonical
    ``skills`` and ``docs/agents-snippet.md``. A wheel install has none
    of them, so those steps resolve against the assets bundled inside the
    package instead of failing or guessing a path.
    """
    checkout = Path(span_repo) / "src" / "span"
    return "checkout" if checkout.is_dir() else "distribution"


def distribution_version():
    """Version of the ``span-mcp`` distribution this installer came from."""
    from importlib import metadata

    try:
        return metadata.version("span-mcp")
    except metadata.PackageNotFoundError:
        raise SystemExit(
            "span-install cannot determine its own distribution version; "
            "reinstall with `pip install span-mcp`."
        )


def bundled_assets_root():
    """Installer assets shipped inside the installed package."""
    return Path(__file__).resolve().parent.parent / "_assets"


def canonical_skills_dir(span_repo):
    """Directory holding the canonical skills for this installation mode."""
    if install_mode(span_repo) == "checkout":
        return Path(span_repo) / "skills"
    return bundled_assets_root() / "skills"


def agents_snippet_path(span_repo):
    """Canonical lifecycle snippet for this installation mode."""
    if install_mode(span_repo) == "checkout":
        return Path(span_repo) / "docs" / "agents-snippet.md"
    return bundled_assets_root() / "agents-snippet.md"


def distribution_venv_in_sync(venv_python):
    """Fast path for a distribution install: compare versions.

    There is no source tree to hash, so the only meaningful equality is
    "the runtime venv holds the distribution version this installer came
    from". Returns the same three-tuple shape as
    ``source_venv_in_sync`` so the caller stays single-shaped.
    """
    expected = distribution_version()
    try:
        proc = subprocess.run(
            [str(venv_python), "-c", _VERSION_PROBE],
            capture_output=True,
            text=True,
        )
    except OSError:
        return False, 0, ()
    if proc.returncode != 0 or proc.stdout.strip() != expected:
        return False, 0, ()
    return True, 1, ()


def pip_install(venv_python, span_repo, dry_run=False):
    mode = install_mode(span_repo)
    if mode == "checkout":
        target = str(span_repo)
    else:
        # A wheel install has no package to build from the working
        # directory: install the exact distribution the user already
        # has, so the runtime venv matches `pip install span-mcp`.
        target = f"span-mcp=={distribution_version()}"
    # --no-cache on both paths: the package version is static, so a
    # warm wheel cache can serve a stale build that no byte check would
    # otherwise catch before install. Cache must never decide content.
    if _has_venv_pip(venv_python, dry_run):
        _run(
            [
                str(venv_python),
                "-m",
                "pip",
                "install",
                "--force-reinstall",
                "--no-cache-dir",
                target,
            ],
            dry_run=dry_run,
        )
        return
    uv = shutil.which("uv")
    if uv is None:
        raise SystemExit(
            "venv has no pip and no `uv` on PATH; install pip or uv, " "then re-run."
        )
    _run(
        [
            uv,
            "pip",
            "install",
            "--reinstall",
            "--no-cache",
            "--python",
            str(venv_python),
            target,
        ],
        dry_run=dry_run,
    )


def verify_installed(span_repo, venv_python):
    """Post-install re-verification (tier-1 closeout).

    Compares installed bytes against source AFTER pip runs: a stale
    build cache or packaging quirk must fail loudly here, never ship
    silently. Returns (ok, detail); callers fail closed on not-ok.

    A distribution install has no source tree to compare, so the proof
    is the runtime venv holding the exact version this installer came
    from — still a positive check, never a skip.
    """
    if install_mode(span_repo) == "distribution":
        expected = distribution_version()
        try:
            proc = subprocess.run(
                [str(venv_python), "-c", _VERSION_PROBE],
                capture_output=True,
                text=True,
            )
        except OSError as exc:
            return False, f"cannot run the runtime venv: {exc}"
        actual = proc.stdout.strip()
        if proc.returncode != 0 or not actual:
            return False, "span-mcp is not installed in the runtime venv"
        if actual != expected:
            return False, (
                f"runtime venv has span-mcp {actual}, " f"expected {expected}"
            )
        return True, f"span-mcp {actual} installed from the distribution"
    in_sync, checked, extra = source_venv_in_sync(span_repo, venv_python)
    if not in_sync:
        return False, (
            f"installed tree does not match source " f"({checked} files checked)"
        )
    if extra:
        return False, (
            "stale files installed that source does not contain: " + ", ".join(extra)
        )
    return True, f"{checked} files match source"


def expose_binary(venv_dir, bin_dir, dry_run=False):
    # span-install is linked too: a checkout install is verified with
    # `span-install --verify-only`, so the command has to be on PATH
    # afterwards, exactly as it is after a package install.
    for name in ("span-mcp", "span-install", "span-hooks"):
        src = Path(venv_dir) / "bin" / name
        dst = Path(bin_dir) / name
        print(f"+ link {dst} -> {src}")
        if dry_run:
            continue
        Path(bin_dir).mkdir(parents=True, exist_ok=True)
        if dst.is_symlink() or dst.exists():
            dst.unlink()
        dst.symlink_to(src)
    resolved = shutil.which("span-mcp")
    print(f"span-mcp resolves to: {resolved}")
    return Path(bin_dir) / "span-mcp"


def target_artifact_snapshot(target):
    """Read-only census of the target structural-index tree (E-14).

    Stdlib-only duplicate of the provider census: counts Markdown cards
    beside the machine-readable index and records wiring identity. Creates
    nothing, builds nothing, writes nothing.
    """
    root = Path(target)
    wiring = root / "graft" / ".graph" / "wiring.json"
    try:
        stat = wiring.stat()
        wiring_info = {
            "present": True,
            "mtime_ns": stat.st_mtime_ns,
            "size_bytes": stat.st_size,
        }
    except OSError:
        wiring_info = {
            "present": False,
            "mtime_ns": None,
            "size_bytes": None,
        }
    cards = 0
    index_md = False
    graph_dir = root / "graft"
    if graph_dir.is_dir():
        try:
            paths = sorted(graph_dir.rglob("*"))
        except OSError:
            paths = []
        for path in paths:
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


def load_seeds(path, dry_run=False):
    if path is None:
        return []
    print(f"+ read authority seeds: {path}")
    if dry_run:
        return []
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        raise SystemExit(f"cannot read seeds file {path}: {exc}")
    if not isinstance(data, list):
        raise SystemExit(f"seeds file must hold a JSON list: {path}")
    # Addendum G §4.6: early seed-shape validation via the canonical
    # decoder, before any mutation. The bootstrap shim
    # (scripts/install-span.py) puts `src/` on `sys.path`, and the
    # installed `span-install` entry point has Span installed, so the
    # canonical decoder is always obtainable in supported paths. Shape
    # only; no locator resolution against the store and no structural
    # provider contact. Unknown locators stay rejected at
    # initialize_repository provisioning, the authoritative boundary.
    # A missing decoder is a broken checkout or install and fails
    # closed here; validation is never skipped.
    try:
        _m = importlib.import_module("span.core.model")
    except ImportError as exc:
        raise SystemExit(
            f"cannot validate seeds file {path}: canonical decoder "
            f"unavailable ({exc}); refusing to install with unchecked "
            f"authority seeds"
        ) from None
    validated: list[object] = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise SystemExit(
                f"seeds file {path}: seeds[{index}]: expected object, "
                f"got {type(item).__name__}"
            )
        payload = dict(item)
        payload.setdefault("$type", "EvidenceRef")
        try:
            validated.append(_m.from_canonical(_m.EvidenceRef, payload))
        except _m.CanonicalDecodeError as exc:
            raise SystemExit(
                f"seeds file {path}: seeds[{index}]: invalid "
                f"EvidenceRef arguments: {exc}"
            ) from None
    return data


def preflight_facts(targets, seeds_path=None):
    """Read-only non-gating preflight facts (Addendum G §4.6).

    Reports git dirty/HEAD where available and seed-file facts. Never
    gates installation: provisioning triggers the single bounded
    provider build when the cache is missing or stale. Stdlib and git
    CLI only; no store, no provider writes.
    """
    facts: dict = {}
    for target in targets:
        entry: dict = {}
        try:
            head = subprocess.run(
                ["git", "-C", str(target), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if head.returncode == 0:
                entry["git_head"] = head.stdout.strip() or None
                status = subprocess.run(
                    ["git", "-C", str(target), "status", "--short"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                entry["git_dirty"] = bool(status.stdout.strip())
                log = subprocess.run(
                    ["git", "-C", str(target), "log", "-1", "--format=%ct"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                try:
                    entry["git_head_time"] = int(log.stdout.strip())
                except (ValueError, AttributeError):
                    entry["git_head_time"] = None
            else:
                entry["git_head"] = None
                entry["git_dirty"] = None
                entry["git_head_time"] = None
        except (OSError, subprocess.SubprocessError):
            entry["git_head"] = None
            entry["git_dirty"] = None
            entry["git_head_time"] = None
        facts[str(target)] = entry
    if seeds_path is not None:
        try:
            text = Path(seeds_path).read_text()
            parsed = json.loads(text)
            facts["seeds_file"] = {
                "supplied": True,
                "readable": True,
                "shape_valid": isinstance(parsed, list),
                "item_count": (len(parsed) if isinstance(parsed, list) else None),
            }
        except (OSError, ValueError):
            facts["seeds_file"] = {
                "supplied": True,
                "readable": False,
                "shape_valid": False,
                "item_count": None,
            }
    else:
        facts["seeds_file"] = {
            "supplied": False,
            "readable": False,
            "shape_valid": False,
            "item_count": 0,
        }
    return facts


def merge_opencode_config(config_path, span_cmd, dry_run=False):
    """Write the one supported OpenCode V2 Span registration.

    The only supported contract is ``mcp.servers.span`` with
    ``type: local``, the installed command, ``codemode: false``, and
    ``disabled`` absent or false. An unsupported flat ``mcp.span``
    registration is rejected, never migrated; the operator removes it
    and reruns. Unknown MCP entries are left untouched: Span owns only
    its own registration and performs no cross-server cleanup.
    """
    print(f"+ merge opencode config: {config_path}")
    if dry_run:
        return {"status": "skipped", "reason": "dry-run"}
    path = Path(config_path)
    try:
        config = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise SystemExit(f"cannot read opencode config {config_path}: {exc}")
    mcp = config.setdefault("mcp", {})
    servers = mcp.get("servers")
    if not isinstance(servers, dict):
        servers = {}
    if isinstance(mcp.get("span"), dict):
        raise SystemExit(
            f"unsupported flat mcp.span registration in {config_path}; "
            "remove it and register Span under mcp.servers.span"
        )
    servers["span"] = {
        "type": "local",
        "command": list(span_cmd),
        "codemode": False,
    }
    mcp["servers"] = servers
    path.write_text(json.dumps(config, indent=2) + "\n")
    print(f"opencode config updated: {config_path}")
    return {
        "status": "merged",
        "config": str(config_path),
    }


def register_codex(span_cmd, dry_run=False):
    if shutil.which("codex") is None:
        print("codex CLI absent; skipping codex registration.")
        return {"status": "skipped", "reason": "codex CLI absent"}
    if dry_run:
        print("+ register codex (dry-run, skipped)")
        return {"status": "skipped", "reason": "dry-run"}
    try:
        _run(["codex", "mcp", "add", "span", "--"] + span_cmd, dry_run=dry_run)
    except SystemExit as exc:
        # The local Codex config itself can be broken (e.g. an
        # invalid service_tier); that error is outside Span. Warn
        # and continue instead of aborting the install.
        print(f"codex registration failed, continuing: {exc}")
        return {"status": "failed", "error": str(exc)}
    return {"status": "registered"}


def register_claude(span_cmd, dry_run=False):
    """Register Span with Claude Code at user scope.

    Claude Code owns its registration format, so the supported surface is
    its CLI rather than a config file Span writes itself. User scope makes
    the server available in every project instead of binding it to the
    directory the installer happened to run in.

    Span owns the ``span`` entry, so an existing one is removed before it
    is re-added: that is convergence on the exact command, and it never
    touches another server.
    """
    if shutil.which("claude") is None:
        print("claude CLI absent; skipping claude registration.")
        return {"status": "skipped", "reason": "claude CLI absent"}
    if dry_run:
        print("+ register claude (dry-run, skipped)")
        return {"status": "skipped", "reason": "dry-run"}
    # Absent entry is the normal first-install case; a non-zero exit
    # here is expected and carries no signal.
    subprocess.run(
        ["claude", "mcp", "remove", "span", "--scope", "user"],
        capture_output=True,
        text=True,
    )
    try:
        _run(
            [
                "claude",
                "mcp",
                "add",
                "--scope",
                "user",
                "--transport",
                "stdio",
                "span",
                "--",
            ]
            + span_cmd,
            dry_run=dry_run,
        )
    except SystemExit as exc:
        # A broken Claude configuration is outside Span: warn and
        # continue instead of aborting the whole install.
        print(f"claude registration failed, continuing: {exc}")
        return {"status": "failed", "error": str(exc)}
    return {"status": "registered", "scope": "user"}


def _hook_bin(venv_dir, bin_dir):
    direct = Path(bin_dir) / "span-hooks"
    if direct.exists():
        return str(direct)
    fallback = Path(venv_dir) / "bin" / "span-hooks"
    return str(fallback)


def wire_codex_hooks(hook_bin, dry_run=False):
    """Append report-only span entries to the user's codex hooks."""
    hooks_path = Path(os.path.expanduser("~")) / ".codex" / "hooks.json"
    print(f"+ wire codex hooks: {hooks_path}")
    if dry_run:
        return {"status": "skipped", "reason": "dry-run"}
    if not hooks_path.exists():
        print("no codex hooks.json; skipping codex hook wiring.")
        return {"status": "skipped", "reason": "no codex hooks.json"}
    try:
        config = json.loads(hooks_path.read_text())
    except ValueError as exc:
        raise SystemExit(f"cannot parse codex hooks.json: {exc}")
    backup = hooks_path.with_suffix(".json.bak-span")
    if not backup.exists():
        shutil.copy2(hooks_path, backup)
        print(f"codex hooks backed up: {backup}")
    entries = [
        ("SessionStart", "startup|resume|compact", [hook_bin, "session-start"]),
        (
            "PostToolUse",
            "apply_patch|Write|Edit|MultiEdit",
            [hook_bin, "source-changed"],
        ),
        ("Stop", "", [hook_bin, "session-stop"]),
    ]
    added = 0
    hooks = config.setdefault("hooks", {})
    for event, matcher, cmd in entries:
        command = " ".join(cmd)
        group = hooks.setdefault(event, [])
        duplicate = any(
            block.get("matcher", "") == matcher
            and any(h.get("command", "") == command for h in block.get("hooks", []))
            for block in group
        )
        if duplicate:
            continue
        group.append(
            {
                "matcher": matcher,
                "hooks": [
                    {
                        "type": "command",
                        "command": command,
                        "timeout": 10,
                        "statusMessage": "Span lifecycle notice",
                    }
                ],
            }
        )
        added += 1
    hooks_path.write_text(json.dumps(config, indent=2) + "\n")
    print(f"codex hooks updated ({added} entries).")
    return {"status": "wired", "added": added}


def wire_claude_hooks(hook_bin, data_dir, dry_run=False):
    """Append report-only span entries to Claude Code's user settings.

    Uses the same three lifecycle events the Claude-style adapter maps:
    ``SessionStart``, post-edit ``PostToolUse``, and ``Stop``. Only the
    ``hooks`` key is touched; every other setting and every foreign hook
    entry is preserved, and the file is backed up before the first write.

    ``--data-dir`` is part of every command: without it the runner falls
    back to the platform default and would inspect a different store than
    the one this install registered.
    """
    settings_path = Path(os.path.expanduser("~")) / ".claude" / "settings.json"
    print(f"+ wire claude hooks: {settings_path}")
    if dry_run:
        return {"status": "skipped", "reason": "dry-run"}
    if not settings_path.exists():
        print("no claude settings.json; skipping claude hook wiring.")
        return {"status": "skipped", "reason": "no claude settings.json"}
    try:
        config = json.loads(settings_path.read_text())
    except ValueError as exc:
        raise SystemExit(f"cannot parse claude settings.json: {exc}")
    backup = settings_path.with_suffix(".json.bak-span")
    if not backup.exists():
        shutil.copy2(settings_path, backup)
        print(f"claude settings backed up: {backup}")
    entries = [
        (
            "SessionStart",
            "startup|resume|compact",
            [hook_bin, "session-start", "--data-dir", str(data_dir)],
        ),
        (
            "PostToolUse",
            "Write|Edit|MultiEdit",
            [hook_bin, "source-changed", "--data-dir", str(data_dir)],
        ),
        ("Stop", "", [hook_bin, "session-stop", "--data-dir", str(data_dir)]),
    ]
    added = 0
    hooks = config.setdefault("hooks", {})
    for event, matcher, cmd in entries:
        command = " ".join(cmd)
        group = hooks.setdefault(event, [])
        # Span owns every command that invokes this hook binary, so an
        # older Span entry is replaced instead of accumulating beside the
        # new one. Foreign commands and foreign matchers are untouched.
        kept_blocks = []
        for block in group:
            block_hooks = block.get("hooks", [])
            kept = [
                hook
                for hook in block_hooks
                if str(hook.get("command", "")).split()[:1] != [hook_bin]
            ]
            if kept:
                block = {**block, "hooks": kept}
                kept_blocks.append(block)
        group[:] = kept_blocks
        duplicate = any(
            block.get("matcher", "") == matcher
            and any(h.get("command", "") == command for h in block.get("hooks", []))
            for block in group
        )
        if duplicate:
            continue
        group.append(
            {
                "matcher": matcher,
                "hooks": [
                    {
                        "type": "command",
                        "command": command,
                        "timeout": 10,
                        "statusMessage": "Span lifecycle notice",
                    }
                ],
            }
        )
        added += 1
    settings_path.write_text(json.dumps(config, indent=2) + "\n")
    print(f"claude hooks updated ({added} entries).")
    return {"status": "wired", "added": added}


def wire_opencode_plugin(span_repo, project_dir, dry_run=False):
    """Refuse per-target plugin deployment (Addendum E §3/E-02).

    Span is read-only with respect to the target repository: no Span path
    writes target artifacts. Deploying ``.opencode/plugins/span-hooks.js``
    into the target would violate that boundary, so this entry point fails
    closed. Host-level wiring (codex hooks, host MCP config, host skills)
    remains outside the target and is unaffected.
    """
    if dry_run:
        return {
            "status": "skipped",
            "reason": "target writes prohibited by Addendum E §3",
        }
    raise SystemExit(
        "refusing target write "
        f"{Path(project_dir) / '.opencode' / 'plugins' / 'span-hooks.js'}: "
        "Span never writes into target repositories (Addendum E §3/E-02). "
        "Host plugin deployment into targets is removed; use host-level "
        "MCP registration instead."
    )


def ensure_agents_rule(span_repo, target, dry_run=False):
    """Deploy the canonical lifecycle block into a target AGENTS.md.

    The block is copied verbatim from ``docs/agents-snippet.md`` between
    Span-owned markers. The installer never parses it for decisions and
    preserves all content outside the managed block. No other target
    artifact is created or modified.
    """
    dst = Path(target) / "AGENTS.md"
    print(f"+ ensure agents rule: {dst}")
    if dry_run:
        return {
            "status": "skipped",
            "reason": "dry-run",
            "path": str(dst),
        }
    src = agents_snippet_path(span_repo)
    if not src.is_file():
        raise SystemExit(f"agents snippet source missing: {src}")
    snippet = src.read_text().rstrip("\n") + "\n"
    if "## Span lifecycle" not in snippet:
        raise SystemExit(f"agents snippet source malformed: {src}")
    block = f"{AGENTS_START}\n{snippet}{AGENTS_END}"
    if not dst.is_file():
        dst.write_text(block + "\n")
        print(f"agents rule created: {dst}")
        return {"status": "wired", "path": str(dst)}
    existing = dst.read_text()
    if existing.count(AGENTS_START) > 1 or existing.count(AGENTS_END) > 1:
        raise SystemExit(
            f"agents block markers duplicated in {dst}; "
            "inspect the file before rerunning."
        )
    start = existing.find(AGENTS_START)
    end = existing.find(AGENTS_END)
    if (start != -1) != (end != -1) or (start != -1 and end != -1 and end < start):
        raise SystemExit(
            f"agents block markers malformed in {dst}; "
            "inspect the file before rerunning."
        )
    if start != -1:
        new_text = existing[:start] + block + existing[end + len(AGENTS_END) :]
    elif existing.strip():
        new_text = existing.rstrip("\n") + "\n\n" + block + "\n"
    else:
        new_text = block + "\n"
    if new_text == existing:
        return {"status": "converged", "path": str(dst)}
    dst.write_text(new_text)
    print(f"agents rule deployed: {dst}")
    return {"status": "wired", "path": str(dst)}


def deploy_agents_rules(span_repo, targets, dry_run=False):
    """Synchronize the managed lifecycle block for every target."""
    return {
        str(target): ensure_agents_rule(span_repo, target, dry_run=dry_run)
        for target in targets
    }


def write_receipt(data_dir, payload, dry_run=False):
    receipt = Path(data_dir) / "install.json"
    print(f"+ write receipt: {receipt}")
    if dry_run:
        return
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def git_rev(span_repo):
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(span_repo),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return "unknown"
    return proc.stdout.strip()


def verify_installation(venv_python, data_dir, repos, dry_run=False):
    """Provision + readiness via a helper module executed under the installed interpreter.

    Operational readiness only (A1): sequential per-target provisioning
    with the settled READY predicate. Never invokes ``explain`` and never
    establishes semantic knowledge.
    """
    cmd = [
        str(venv_python),
        "-m",
        "span.shell.install_verify",
        "--data-dir",
        str(data_dir),
    ]
    for repo in repos:
        cmd += ["--repo", str(repo)]
    out = _run(cmd, dry_run=dry_run)
    if dry_run:
        return {"dry_run": True}
    try:
        return json.loads(out)
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"verify step returned non-JSON output: {exc}")


def detect_hosts():
    """Detect supported agent hosts without changing anything."""
    hosts = {"opencode": True}  # MCP config merge is file-local.
    home = Path(os.path.expanduser("~"))
    hosts["codex"] = shutil.which("codex") is not None or (home / ".codex").exists()
    hosts["claude"] = (
        shutil.which("claude") is not None
        or (home / ".claude").exists()
        or (home / ".claude.json").exists()
    )
    return hosts


def deploy_skills(span_repo, dry_run=False):
    """Copy span skills into each detected host's skills directory.

    Skill directories are copied whole as opaque artifacts; content
    is never parsed or used for decisions here (implementation
    ignores skills as semantic authority). A `.span-origin.json`
    beside each skill records the source rev so doctor can detect
    drift. Nothing is merged into host-owned files.
    """

    skills_dir = canonical_skills_dir(span_repo)
    if not skills_dir.is_dir():
        print(f"no skills directory for {span_repo}; skipping.")
        return []
    names = sorted(p.name for p in skills_dir.iterdir() if p.is_dir())
    if not names:
        print("no skills found; skipping.")
        return []
    home = Path(os.path.expanduser("~"))
    # Readiness is the host's own directory, not the skills subdirectory:
    # a fresh host has no skills directory yet, and skipping there would
    # silently deploy nothing for the host that was just detected. The
    # host root always pre-exists, so this never fabricates a host.
    destinations = [
        home / ".config" / "opencode",
        home / ".codex",
        home / ".claude",
    ]
    mode = install_mode(span_repo)
    version = distribution_version() if mode == "distribution" else None
    deployed = []
    try:
        rev_proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(span_repo),
            capture_output=True,
            text=True,
        )
        rev = rev_proc.stdout.strip() if rev_proc.returncode == 0 else "unknown"
    except OSError:
        rev = "unknown"
    for host_root in destinations:
        if not host_root.is_dir():
            print(f"host directory absent, skipping: {host_root}")
            continue
        dest_root = host_root / "skills"
        if not dry_run:
            dest_root.mkdir(exist_ok=True)
        for name in names:
            src = skills_dir / name
            dst_dir = dest_root / name
            print(f"+ deploy skill {name} -> {dst_dir}")
            if dry_run:
                continue
            shutil.copytree(src, dst_dir, dirs_exist_ok=True)
            (dst_dir / ".span-origin.json").write_text(
                json.dumps(
                    {
                        "skill": name,
                        "install_mode": mode,
                        "span_repo": str(span_repo) if mode == "checkout" else None,
                        "distribution_version": version,
                        "span_rev": rev,
                        "installed_at": datetime.datetime.now(
                            datetime.timezone.utc
                        ).isoformat(),
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            )
            deployed.append(str(dst_dir))
    return deployed


def check_skills(dry_run=False):
    """Doctor helper: report deployed skills and origin drift."""
    home = Path(os.path.expanduser("~"))
    for dest_root in (
        home / ".config" / "opencode" / "skills",
        home / ".codex" / "skills",
        home / ".claude" / "skills",
    ):
        if not dest_root.is_dir():
            continue
        for skill_dir in sorted(dest_root.iterdir()):
            origin = skill_dir / ".span-origin.json"
            if not origin.exists() or dry_run:
                continue
            try:
                record = json.loads(origin.read_text())
            except ValueError:
                print(f"skills: {skill_dir} has unreadable origin.")
                continue
            source = record.get("span_repo")
            if source is None:
                source = f"span-mcp {record.get('distribution_version')}"
            print(f"skills: {skill_dir} from {source} rev {record.get('span_rev')}")


def expected_span_command(span_mcp, data_dir, repos):
    """Installed invocation shape used for host-registration inspection."""
    command = [str(span_mcp), "--data-dir", str(data_dir)]
    for repo in repos:
        command += ["--repo", str(repo)]
    return command


def inspect_opencode_registration(config_path, span_cmd):
    """Read-only OpenCode ``mcp.servers.span`` registration inspection.

    Returns exactly one of ``matched``, ``mismatched``, ``missing``, or
    ``unreadable``. Never calls ``merge_opencode_config`` and never
    writes the config. A missing config path means no OpenCode config is
    available; an explicitly supplied but unreadable path is reported as
    unreadable rather than guessed.
    """
    expected = list(span_cmd)
    result = {
        "status": "missing",
        "config": None if config_path is None else str(config_path),
        "expected_command": expected,
    }
    if config_path is None:
        result["reason"] = "no OpenCode config available"
        return result
    path = Path(config_path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        result["status"] = "unreadable"
        result["reason"] = f"cannot read OpenCode config: {exc}"
        return result
    try:
        config = json.loads(text)
    except ValueError as exc:
        result["status"] = "unreadable"
        result["reason"] = f"cannot parse OpenCode config: {exc}"
        return result
    mcp = config.get("mcp") if isinstance(config, dict) else None
    servers = mcp.get("servers") if isinstance(mcp, dict) else None
    nested = servers.get("span") if isinstance(servers, dict) else None
    flat = mcp.get("span") if isinstance(mcp, dict) else None
    if isinstance(flat, dict) and isinstance(nested, dict):
        result["status"] = "mismatched"
        result["reason"] = (
            "duplicate Span registrations: both mcp.span and "
            "mcp.servers.span exist; normalize to mcp.servers.span"
        )
        return result
    if isinstance(flat, dict):
        result["status"] = "mismatched"
        result["configured_command"] = flat.get("command")
        result["reason"] = (
            "unsupported flat mcp.span registration; use " "mcp.servers.span"
        )
        return result
    if not isinstance(nested, dict):
        result["reason"] = "no mcp.servers.span entry"
        return result
    result["configured_command"] = nested.get("command")
    if nested.get("type") != "local":
        result["status"] = "mismatched"
        result["reason"] = "mcp.servers.span type must be local"
        return result
    if nested.get("disabled") is True:
        result["status"] = "mismatched"
        result["reason"] = "mcp.servers.span entry is disabled"
        return result
    # OpenCode must expose Span's raw tool schemas; Code Mode wraps them
    # and makes the advertised grammar unusable.
    if nested.get("codemode") is not False:
        result["status"] = "mismatched"
        result["reason"] = (
            "mcp.servers.span entry has Code Mode enabled; codemode " "must be false"
        )
        return result
    if nested.get("command") == expected:
        result["status"] = "matched"
        return result
    result["status"] = "mismatched"
    result["reason"] = (
        "mcp.servers.span command does not match the installed invocation"
    )
    return result


def inspect_codex_registration():
    """Report Codex registration observability honestly.

    The repository establishes no stable Codex MCP configuration-file
    contract, so this read-only check never inspects or executes the
    Codex CLI: detection reports ``manual``, absence reports
    ``skipped``.
    """
    if detect_hosts()["codex"]:
        return {
            "status": "manual",
            "reason": (
                "installer receipt may record prior registration, but "
                "current Codex MCP registration is not deterministically "
                "inspectable by Span's read-only contract"
            ),
        }
    return {"status": "skipped", "reason": "codex CLI not detected"}


def inspect_claude_registration(span_cmd):
    """Read-only inspection of Claude Code's user-scope MCP entry.

    ``~/.claude.json`` is the documented user-scope store, so this check
    reads it directly and never runs the CLI. Missing file, missing
    entry, unreadable JSON, and a differing command are reported
    distinctly; nothing is written.
    """
    config_path = Path(os.path.expanduser("~")) / ".claude.json"
    expected = [str(part) for part in span_cmd]
    result = {
        "status": "missing",
        "config": str(config_path),
        "expected_command": expected,
    }
    try:
        raw = config_path.read_text()
    except OSError:
        return result
    try:
        config = json.loads(raw)
    except ValueError:
        result["status"] = "unreadable"
        return result
    servers = config.get("mcpServers")
    entry = servers.get("span") if isinstance(servers, dict) else None
    if not isinstance(entry, dict):
        return result
    actual = [str(entry.get("command", ""))] + [
        str(arg) for arg in entry.get("args", [])
    ]
    result["actual_command"] = actual
    result["status"] = "matched" if actual == expected else "mismatched"
    return result


def doctor(venv_python, data_dir, repos, opencode_config, dry_run=False):
    """Re-verify an existing installation without changing anything."""
    print("== span install doctor ==")
    resolved = shutil.which("span-mcp")
    print(f"span-mcp on PATH: {resolved}")
    if resolved is None and not dry_run:
        raise SystemExit("span-mcp not found on PATH")
    receipt_path = Path(data_dir) / "install.json"
    if receipt_path.exists() and not dry_run:
        print(f"receipt: {receipt_path}")
    else:
        print(f"no receipt at: {receipt_path}")
    check_skills(dry_run=dry_run)
    # Read-only host-registration inspection: file inspection only, no
    # MCP registry/process enumeration and no host configuration writes.
    selected_config = opencode_config
    if selected_config is None and Path("opencode.json").exists():
        selected_config = "opencode.json"
    span_cmd = expected_span_command(
        resolved if resolved is not None else "span-mcp", data_dir, repos
    )
    opencode_state = inspect_opencode_registration(selected_config, span_cmd)
    codex_state = inspect_codex_registration()
    claude_state = inspect_claude_registration(span_cmd)
    print(f"opencode registration: {opencode_state['status']}")
    if opencode_state.get("reason"):
        print(f"  {opencode_state['reason']}")
    print(
        f"codex registration: {codex_state['status']} "
        f"({codex_state.get('reason', '')})"
    )
    print(
        f"claude registration: {claude_state['status']} "
        f"({claude_state.get('config', '')})"
    )
    report = verify_installation(venv_python, data_dir, repos, dry_run)
    print(f"runtime verification: span-mcp={resolved}")
    readiness = report.get("repos", []) if isinstance(report, dict) else []
    print(f"repository readiness: {readiness}")
    return {
        "runtime_verification": {
            "span_mcp": resolved,
            "dry_run": bool(dry_run),
        },
        "repository_readiness": report,
        "opencode_registration": opencode_state,
        "codex_registration": codex_state,
        "claude_registration": claude_state,
    }


def main(argv=None):
    args = parse_args(argv)
    paths = platform_paths()
    venv_dir = Path(args.venv_dir) if args.venv_dir else paths["venv_dir"]
    data_dir = Path(args.data_dir) if args.data_dir else paths["data_dir"]
    bin_dir = Path(args.bin_dir) if args.bin_dir else paths["bin_dir"]
    span_repo = Path(args.span_repo).resolve()
    targets = [Path(r).resolve() for r in args.repo]
    dry = args.dry_run

    for target in targets:
        if str(data_dir).startswith(str(target) + os.sep) or data_dir == target:
            raise SystemExit(
                f"data dir must live outside every target repo: {data_dir}"
            )

    if args.verify_only:
        venv_python = venv_dir / "bin" / "python"
        doctor(
            venv_python,
            data_dir,
            targets,
            args.opencode_config,
            dry,
        )
        return

    if args.snapshot_census is not None:
        snapshot_census(targets, args.snapshot_census, dry_run=dry)
        return

    if args.compare_census is not None:
        compare_census(*args.compare_census)
        return

    check_prereqs()
    # The standalone structural server is gone, so the E-14
    # process/registry scan is deleted with it. The preflight is the
    # read-only target census below (proving targets stay unchanged)
    # plus git/seed facts; provisioning performs the one bounded
    # provider build when needed.
    opencode_config = args.opencode_config
    if opencode_config is None and Path("opencode.json").exists():
        opencode_config = "opencode.json"
    target_census: dict = {}
    for target in targets:
        target_census[str(target)] = target_artifact_snapshot(target)
    # Addendum G §4.6: early seed-shape validation before any mutation,
    # plus read-only non-gating preflight facts. Shape failure closes
    # before mutation; locator resolution stays at provisioning.
    seeds = load_seeds(args.authority_seeds_file, dry_run=dry)
    preflight = preflight_facts(targets, args.authority_seeds_file)
    print(f"preflight facts: {json.dumps(preflight, sort_keys=True)}")
    venv_python = ensure_venv(venv_dir, dry_run=dry)
    indexer_binary = ensure_structural_indexer(venv_dir, dry_run=dry)
    indexer_pointer = write_indexer_pointer(data_dir, indexer_binary, dry_run=dry)
    # Tier-1 verify-fast-path (E §9.2): skip reinstall when the venv
    # already matches the install source, with proof. The check itself
    # is read-only and runs on dry-run too; backup precedes mutation
    # only. A distribution install proves version equality because it
    # has no source tree to hash.
    mode = install_mode(span_repo)
    if mode == "checkout":
        in_sync, files_checked, extra_files = source_venv_in_sync(
            span_repo, venv_python
        )
        match_detail = f"source ({files_checked} files)"
    else:
        in_sync, files_checked, extra_files = distribution_venv_in_sync(venv_python)
        match_detail = f"span-mcp {distribution_version()}"
    data_backup = None
    post_install_verified = None
    if in_sync:
        print(f"venv matches {match_detail}; skipping reinstall with proof.")
        reinstalled = False
    else:
        data_backup = backup_data_dir(data_dir, dry_run=dry)
        if mode == "checkout":
            # Build staging only exists for a source build; cleaning it in
            # a distribution install would touch whatever `build/` happens
            # to sit in the caller's working directory.
            _clean_build_staging(span_repo, dry_run=dry)
        pip_install(venv_python, span_repo, dry_run=dry)
        reinstalled = not dry
        if reinstalled:
            ok, detail = verify_installed(span_repo, venv_python)
            if not ok:
                raise SystemExit(
                    f"installed runtime failed verification: {detail}. "
                    "The install is refused rather than recorded; "
                    "fix the build and rerun."
                )
            print(f"installed runtime verified: {detail}.")
            post_install_verified = detail
    if extra_files:
        print(
            "warning: stale files in venv pip reinstall never removes: "
            + ", ".join(extra_files)
            + ". Recreate the venv to clear them."
        )
    source_venv_sync = {
        "in_sync_before_install": bool(in_sync),
        "files_checked": files_checked,
        "extra_venv_files": list(extra_files),
        "reinstalled": bool(reinstalled),
    }
    expose_binary(venv_dir, bin_dir, dry_run=dry)
    if seeds:
        # Verification provisions without seeds (no new flags per
        # Addendum D ACT-D-02); seeds enter through a setup-session
        # initialize_repository call with authority_seeds.
        print(
            f"loaded {len(seeds)} authority seeds "
            "(provision them via a setup-session "
            "initialize_repository call; verification "
            "provisions without seeds)"
        )

    data_cmd = ["--data-dir", str(data_dir)]
    resolved_mcp = shutil.which("span-mcp")
    if resolved_mcp is None:
        # Not yet on PATH in this process; the server entry needs an
        # absolute path, so resolve the just-linked binary directly.
        resolved_mcp = str(Path(bin_dir) / "span-mcp")
    span_cmd = [resolved_mcp] + data_cmd
    for target in targets:
        span_cmd += ["--repo", str(target)]
    host_registration: dict = {}
    if opencode_config is not None:
        try:
            host_registration["opencode"] = merge_opencode_config(
                opencode_config, span_cmd, dry_run=dry
            )
        except SystemExit as exc:
            host_registration["opencode"] = {
                "status": "failed",
                "error": str(exc),
            }
            raise
    else:
        print(
            "no opencode.json found; skipping host registration "
            "(pass --opencode-config PATH)."
        )
        host_registration["opencode"] = {
            "status": "skipped",
            "reason": "no opencode.json found (pass --opencode-config PATH)",
        }
    if args.with_codex is None:
        args.with_codex = detect_hosts()["codex"] and not args.no_codex
    elif args.no_codex:
        args.with_codex = False
    if args.with_hooks is None:
        args.with_hooks = not args.no_hooks
    if args.with_codex:
        host_registration["codex"] = register_codex(span_cmd, dry_run=dry)
    else:
        if args.no_codex:
            _codex_reason = "codex disabled (--no-codex)"
        else:
            _codex_reason = "codex CLI not detected"
        print(f"skipping codex registration ({_codex_reason}).")
        host_registration["codex"] = {
            "status": "skipped",
            "reason": _codex_reason,
        }
    if args.with_claude is None:
        args.with_claude = detect_hosts()["claude"] and not args.no_claude
    elif args.no_claude:
        args.with_claude = False
    if args.with_claude:
        host_registration["claude"] = register_claude(span_cmd, dry_run=dry)
    else:
        if args.no_claude:
            _claude_reason = "claude disabled (--no-claude)"
        else:
            _claude_reason = "claude CLI not detected"
        print(f"skipping claude registration ({_claude_reason}).")
        host_registration["claude"] = {
            "status": "skipped",
            "reason": _claude_reason,
        }
    if args.with_hooks:
        hook_bin = _hook_bin(venv_dir, bin_dir)
        try:
            _codex_hooks = wire_codex_hooks(hook_bin, dry_run=dry)
        except SystemExit as exc:
            _codex_hooks = {"status": "failed", "error": str(exc)}
            host_registration["hooks"] = {
                "codex": _codex_hooks,
                "opencode_plugin": {},
            }
            raise
        if args.with_claude:
            try:
                _claude_hooks = wire_claude_hooks(hook_bin, data_dir, dry_run=dry)
            except SystemExit as exc:
                _claude_hooks = {"status": "failed", "error": str(exc)}
                host_registration["hooks"] = {
                    "codex": _codex_hooks,
                    "claude": _claude_hooks,
                    "opencode_plugin": {},
                }
                raise
        else:
            _claude_hooks = {
                "status": "skipped",
                "reason": "claude integration not enabled",
            }
        # Addendum E §3/E-02: per-target opencode plugin deployment would
        # write into target repositories and is therefore removed. Host
        # hooks outside targets remain allowed.
        _plugin = {
            str(target): {
                "status": "skipped",
                "reason": "target writes prohibited by Addendum E §3/E-02",
            }
            for target in targets
        }
        print(
            "per-target opencode plugin deployment removed "
            "(Addendum E §3/E-02: Span never writes into targets)."
        )
        host_registration["hooks"] = {
            "codex": _codex_hooks,
            "claude": _claude_hooks,
            "opencode_plugin": _plugin,
        }
    else:
        print("skipping hook wiring (--no-hooks).")
        host_registration["hooks"] = {
            "codex": {
                "status": "skipped",
                "reason": "hooks disabled (--no-hooks)",
            },
            "claude": {
                "status": "skipped",
                "reason": "hooks disabled (--no-hooks)",
            },
            "opencode_plugin": {},
        }
    if not args.no_skills:
        host_registration["skills"] = deploy_skills(span_repo, dry_run=dry)
    else:
        print("skipping skill deployment (--no-skills).")
        host_registration["skills"] = []
    host_registration["agents"] = deploy_agents_rules(span_repo, targets, dry_run=dry)

    report = verify_installation(venv_python, data_dir, targets, dry)
    receipt = {
        "install_version": INSTALL_VERSION,
        "span_repo": str(span_repo),
        "span_rev": git_rev(span_repo) if not dry else "dry-run",
        "venv_dir": str(venv_dir),
        "data_dir": str(data_dir),
        "repos": [str(t) for t in targets],
        "verify": report,
        "host_registration": host_registration,
        "target_census": target_census,
        "structural_indexer": {
            # Neutral summary only: the managed binary path is internal
            # state and never part of the operator-facing receipt.
            "managed": bool(indexer_pointer),
            "version": (indexer_pointer or {}).get("version"),
        },
        "source_venv_sync": source_venv_sync,
        "post_install_verified": post_install_verified,
        "data_backup": data_backup,
        "seeds_file_supplied_and_readable": bool(seeds),
        "seeds_shape_valid": bool(seeds),
        "seeds_resolved_and_active": False,
        "preflight_facts": preflight,
        # Deterministic installer performs no host exchange (A1 only).
        "a2": "not_run",
        "installed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    write_receipt(data_dir, receipt, dry_run=dry)
    print("install complete.")


if __name__ == "__main__":
    main()
