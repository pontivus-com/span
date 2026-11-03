"""Installer constants (stdlib only; no span imports at import time)."""

from __future__ import annotations

INSTALL_VERSION = 1


STRUCTURAL_INDEXER_PACKAGE = "@nanonets/graft"


STRUCTURAL_INDEXER_VERSION = "0.25.0"


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


#: Skills replaced by the three-moment surface. The installer removes these
#: on upgrade; it never merges or keeps a second lifecycle grammar.
RETIRED_SKILLS = ("span", "span-change-context", "span-document")


AGENTS_START = "<!-- span:start -->"


AGENTS_END = "<!-- span:end -->"


_VERSION_PROBE = "import importlib.metadata as m; print(m.version('span-mcp'))"

#: O-3 measured response budgets in delivered wire bytes. OpenCode delivered
#: 51,133 bytes inline and saved a 62,589-byte result to a file; Codex
#: delivered 62,589 bytes inline. The values are recorded observations, not
#: invented thresholds.
HOST_RESPONSE_BUDGETS = {
    "codex": 62_589,
    "opencode": 51_133,
}
