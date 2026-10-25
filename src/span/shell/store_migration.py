"""Explicit offline store migration (schema 7 → 8).

Invoked by ``span-install --migrate-store <repository-id>`` under the
installed interpreter. The store itself never migrates at open: a version
mismatch fails closed, and this command is the only upgrade path.
"""

import argparse
import json
import pathlib
import sys

from span.shell.sqlite_store import migrate_store


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="span-store-migrate",
        description="Upgrade one Span semantic store to the current schema.",
    )
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--repository-id", required=True)
    args = parser.parse_args(argv)
    path = pathlib.Path(args.data_dir) / f"{args.repository_id}.db"
    try:
        report = migrate_store(path)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from None
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
