#!/usr/bin/env python3
"""First-run shim: `python3 scripts/install-span.py ...` from a checkout.

Adds `src/` to the path and delegates to span.shell.install (which
itself imports no span modules at top level, so it runs before Span
is installed).
"""

import os
import sys

sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"),
)

from span.shell.install import main

if __name__ == "__main__":
    main()
