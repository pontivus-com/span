"""Extract one version's section from CHANGELOG.md.

Used by the release workflow to create the GitHub Release body from the
canonical changelog, so release notes are not maintained twice.
"""

import argparse
import pathlib
import re
import sys


def extract(text: str, version: str) -> str:
    """Return the ``## <version>`` section, without the next section."""
    start = re.search(rf"^## {re.escape(version)}(?:\s|$)", text, re.M)
    if start is None:
        raise ValueError(f"no changelog section for {version}")
    tail = text[start.end() :]
    following = re.search(r"^## ", tail, re.M)
    end = start.end() + (following.start() if following else len(tail))
    return text[start.start() : end].strip() + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="release-notes",
        description="Print one CHANGELOG.md section for a GitHub Release.",
    )
    parser.add_argument("version")
    parser.add_argument(
        "--changelog", default="CHANGELOG.md", help="Path to CHANGELOG.md"
    )
    args = parser.parse_args(argv)
    try:
        text = pathlib.Path(args.changelog).read_text(encoding="utf-8")
        sys.stdout.write(extract(text, args.version))
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
