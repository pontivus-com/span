"""Build hook: materialize the packaged assets from their canonical sources."""

from __future__ import annotations

import pathlib
import sys

from setuptools import setup
from setuptools.command.build_py import build_py as _build_py

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))

from sync_assets import sync_assets  # noqa: E402


class build_py(_build_py):
    """Copy the canonical skills and snippet into the built package."""

    def run(self) -> None:
        super().run()
        sync_assets(pathlib.Path(self.build_lib) / "span" / "_assets")


setup(cmdclass={"build_py": build_py})
