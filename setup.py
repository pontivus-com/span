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
    """Copy canonical generated assets and declare them as wheel outputs."""

    def run(self) -> None:
        super().run()
        self._span_generated_assets = sync_assets(
            pathlib.Path(self.build_lib) / "span" / "_assets"
        )

    def get_outputs(self, include_bytecode: bool = True) -> list[str]:
        outputs = list(super().get_outputs(include_bytecode=include_bytecode))
        generated = getattr(self, "_span_generated_assets", ())
        return outputs + [str(path) for path in generated]


setup(cmdclass={"build_py": build_py})
