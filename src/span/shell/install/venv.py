"""Virtualenv creation, install, and runtime verification (stdlib only)."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from span.shell.install.build_identity import (
    decode_build_identity,
    installed_build_identity,
    read_build_identity,
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


def _hash_tree(root: Path) -> dict[str, bytes]:
    """Compare installed Python sources without skipping unreadable files."""
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).digest()
        for path in sorted(root.rglob("*.py"))
    }


def _source_identity(span_repo: str | Path) -> dict[str, str] | None:
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(Path(span_repo) / "scripts/build_identity.py"),
                "--inspect",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return decode_build_identity(result.stdout)


def requested_build_identity(span_repo: str | Path) -> dict[str, str] | None:
    if install_mode(span_repo) == "checkout":
        return _source_identity(span_repo)
    return installed_build_identity()


def source_venv_in_sync(
    span_repo: str | Path,
    venv_python: str | Path,
    *,
    expected_identity: dict[str, str] | None = None,
) -> tuple[bool, int, tuple[str, ...]]:
    """Prove observed build identity and installed source bytes agree."""
    venv_site = Path(venv_python).parent.parent / "lib"
    candidates = sorted(venv_site.glob("python*/site-packages/span"))
    if not candidates:
        return False, 0, ()
    try:
        source = _hash_tree(Path(span_repo) / "src" / "span")
        installed = _hash_tree(candidates[0])
    except OSError:
        return False, 0, ()
    current = _source_identity(span_repo)
    expected = current if expected_identity is None else expected_identity
    extra = tuple(sorted(set(installed) - set(source)))
    in_sync = (
        bool(source)
        and expected is not None
        and expected == current == read_build_identity(candidates[0])
        and installed == source
    )
    return in_sync, len(source), extra


def distribution_venv_in_sync(
    venv_python: str | Path,
    *,
    expected_identity: dict[str, str] | None = None,
) -> tuple[bool, int, tuple[str, ...]]:
    """Require the same distribution version and actual packaged identity."""
    current = installed_build_identity()
    expected = current if expected_identity is None else expected_identity
    if expected is None or current != expected:
        return False, 0, ()
    probe = (
        "import json; from importlib.metadata import version; "
        "from span.shell.install.build_identity import installed_build_identity; "
        "print(json.dumps([version('span-mcp'), installed_build_identity()]))"
    )
    try:
        result = subprocess.run(
            [str(venv_python), "-c", probe],
            capture_output=True,
            text=True,
            check=True,
        )
        actual = json.loads(result.stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        return False, 0, ()
    if actual != [distribution_version(), expected]:
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


def verify_installed(
    span_repo: str | Path,
    venv_python: str | Path,
    *,
    expected_identity: dict[str, str] | None = None,
) -> tuple[bool, str]:
    """Use the same exact proof after installation as on the reuse path."""
    if install_mode(span_repo) == "distribution":
        in_sync, _, _ = distribution_venv_in_sync(
            venv_python, expected_identity=expected_identity
        )
        if in_sync:
            return True, f"span-mcp {distribution_version()} build verified"
        return (
            False,
            "installed build differs or cannot be verified; reinstall the requested Span build",
        )
    in_sync, checked, extra = source_venv_in_sync(
        span_repo, venv_python, expected_identity=expected_identity
    )
    if extra:
        return False, "obsolete runtime files remain; recreate the runtime environment"
    if not in_sync:
        return (
            False,
            "installed build differs or cannot be verified; reinstall the requested Span build",
        )
    return True, f"{checked} files match source and build identity"


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
