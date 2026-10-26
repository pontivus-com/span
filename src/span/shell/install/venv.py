"""Virtualenv creation, install, and runtime verification (stdlib only)."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

from span.shell.install.constants import (
    _VERSION_PROBE,
)
from span.shell.install.paths import (
    distribution_version,
    install_mode,
)


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
    """Verify-fast-path ([design note E](docs/design-references.md#e) §9.2): compare source against venv.

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
