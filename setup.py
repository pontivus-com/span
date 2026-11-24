"""Build hook: expose canonical external assets as generated package data."""

from __future__ import annotations

import pathlib
import sys

from setuptools import setup
from setuptools.command.build_py import build_py as _build_py

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))

from sync_assets import asset_manifest  # noqa: E402


class build_py(_build_py):
    """Map canonical assets directly into the wheel package-data build."""

    def get_data_files(self):
        files = list(super().get_data_files() or ())
        asset_root = pathlib.Path(self.build_lib) / "span" / "_assets"
        for source, relative in asset_manifest():
            files.append(
                (
                    "span",
                    str(source.parent),
                    str(asset_root / relative.parent),
                    [source.name],
                )
            )
        return files


setup(cmdclass={"build_py": build_py})
