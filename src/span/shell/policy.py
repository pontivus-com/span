"""Shipped operational policy for the lifecycle runtime (§8.4, D-12).

These are finite operator-facing lifetimes, not semantic thresholds. They
never decide whether understanding is current; support evaluation and source
identity do that. Values are chosen from the ordinary working horizon they
serve:

- a context lives for one working day, which covers a resumed investigation
  inside a normal session;
- a receipt stays replayable for one week, so a host that lost a response can
  recover the committed result after a restart without re-running the write;
- hook diagnostics are bounded per event, because a hook is an optional notice
  and must never become repository-scale work.
"""

from __future__ import annotations

import datetime as _datetime

from span.core import model as m

__all__ = [
    "DEFAULT_LIFECYCLE_RETENTION",
    "HOOK_DIAGNOSTIC_LIMIT",
]


_CONTEXT_LIFETIME = _datetime.timedelta(days=1)
_REPLAY_RETENTION = _datetime.timedelta(days=7)

DEFAULT_LIFECYCLE_RETENTION = m.LifecycleRetention(
    context_lifetime=_CONTEXT_LIFETIME,
    replay_retention=_REPLAY_RETENTION,
)

#: Maximum diagnostics one hook event may report (bounded notice, not work).
HOOK_DIAGNOSTIC_LIMIT = 8
