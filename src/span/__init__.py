"""Span — maintained codebase understanding for coding agents.

Package layout follows plan §14 (core/ports/shell):

- ``span.core`` — pure, deterministic, strictly typed semantic core.
  No side-effect imports (plan I-01).
- ``span.ports`` — typed interfaces only.
- ``span.shell`` — effects and strict ingress/egress.
- ``span.service`` — coordinates ports/core; owns no semantic rules.
"""

__version__ = "0.8.2"
