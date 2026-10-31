"""Project-authored host-contract fixture component.

This file exists only so a host probe has a real, bounded source target.
"""


class ProbeComponent:
    """Owns the probe fixture behavior."""

    def describe(self) -> str:
        return "probe component"


def probe_entrypoint() -> str:
    return ProbeComponent().describe()
