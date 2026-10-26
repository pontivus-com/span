"""Install receipt read/write (stdlib only)."""

from __future__ import annotations

import json
from pathlib import Path


def write_receipt(data_dir, payload, dry_run=False):
    receipt = Path(data_dir) / "install.json"
    print(f"+ write receipt: {receipt}")
    if dry_run:
        return
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def read_receipt(data_dir):
    """Read the install receipt, or None when absent/unreadable."""
    try:
        return json.loads((Path(data_dir) / "install.json").read_text())
    except (OSError, ValueError):
        return None
