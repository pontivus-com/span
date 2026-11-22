"""Derive release serializations from the canonical package version.

The package version in src/span/__init__.py remains the sole version owner.
This module only derives the Git tag, GitHub release presentation and MCP
Registry SemVer required by Technical Design section 21.
"""

from __future__ import annotations

import argparse
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "src" / "span" / "__init__.py"
VERSION_LINE = re.compile(r'^__version__ = "([^"]+)"$', re.M)
PEP440_RELEASE = re.compile(
    r"^(?P<base>\d+\.\d+\.\d+)"
    r"(?:(?P<pre>a|b|rc)(?P<pre_number>\d+))?"
    r"(?:\.dev(?P<dev_number>\d+))?$"
)


def read_package_version(path: pathlib.Path = VERSION_FILE) -> str:
    match = VERSION_LINE.search(path.read_text(encoding="utf-8"))
    if match is None:
        raise ValueError(f"no canonical package version in {path}")
    return match.group(1)


def derive(version: str) -> dict[str, str]:
    match = PEP440_RELEASE.fullmatch(version)
    if match is None:
        raise ValueError(f"unsupported release version: {version}")

    base = match.group("base")
    pre = match.group("pre")
    pre_number = match.group("pre_number")
    dev_number = match.group("dev_number")

    semver_parts: list[str] = []
    title_parts: list[str] = []
    if pre is not None:
        semver_label, title_label = {
            "a": ("alpha", "Alpha"),
            "b": ("beta", "Beta"),
            "rc": ("rc", "RC"),
        }[pre]
        semver_parts.extend((semver_label, pre_number))
        title_parts.extend((title_label, pre_number))
    if dev_number is not None:
        semver_parts.extend(("dev", dev_number))
        title_parts.extend(("Dev", dev_number))

    registry_version = base
    if semver_parts:
        registry_version += "-" + ".".join(semver_parts)

    release_title = f"Span {base}"
    if title_parts:
        release_title += " " + " ".join(title_parts)

    return {
        "package_version": version,
        "tag": f"v{version}",
        "registry_version": registry_version,
        "release_title": release_title,
        "prerelease": "true" if semver_parts else "false",
        "development": "true" if dev_number is not None else "false",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-version")
    parser.add_argument(
        "--field",
        required=True,
        choices=(
            "package_version",
            "tag",
            "registry_version",
            "release_title",
            "prerelease",
            "development",
        ),
    )
    args = parser.parse_args(argv)
    version = args.package_version or read_package_version()
    try:
        print(derive(version)[args.field])
    except ValueError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
