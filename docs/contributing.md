# Contributing

Span is a small, standalone Python project. Contributions are welcome, but
the semantic contracts are deliberate: a change to what Span means needs a
contract change, not a local guess.

## Development setup

```bash
git clone https://github.com/pontivus-com/span.git
cd span
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[test,dev]'
```

Run the suite from the repository root:

```bash
pytest
```

Lint and format gates:

```bash
ruff check .
black --check .
```

Apply formatting with `black .` before opening a pull request.

Or with the standard-library runner:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

Node and npm are needed for the installer's structural-indexer
provisioning and for the installed-MCP integration lane. The managed indexer
version is a constant, not a lockfile entry, so
`python3 scripts/check_indexer_pin.py` compares it with npm; a scheduled
workflow runs the same check weekly. Bump the pin only after verifying the
upstream release against the structural fixtures.

## What to test

- **Unit** — core rules, carriers, serialization, ports, shells, paging,
  skills scan, initialization contract, isolation gate.
- **Integration** — vertical slices, MCP transport including the SDK
  round-trip, hooks.
- **Acceptance** — the public fixture model and the end-to-end contract paths.

A new carrier needs construction and serialization tests. New behavior needs
tests in the layer that owns it. A contract change updates the relevant public
document in the same change.

## Pull requests

- Keep the change focused. Unrelated refactors make review harder.
- Add or update tests for behavior you change.
- Update the affected public document when a contract changes.
- Sign off your commits with the Developer Certificate of Origin:

```bash
git commit -s
```

The sign-off is a statement that you wrote the change or have the right to
submit it under the project licence. There is no separate CLA.

## Dependencies and licences

`DEPENDENCY_LEDGER.md` is authoritative. Do not add a runtime dependency
without a verified identity, a compatible licence, and a ledger entry.

## Releases

The version lives in `src/span/__init__.py`; `pyproject.toml` reads it. A
release is an ordinary pull request that bumps it.

On merge to `master`, the `Release` workflow reads the version and acts only
when `v<version>` does not exist yet:

1. Build, attest, and publish `span-mcp` to PyPI.
2. Only after PyPI accepts the version, create the tag and the GitHub Release.
   The release body is the matching `## <version>` section of `CHANGELOG.md`,
   so release notes are written once.
3. Publish `server.json` to the MCP Registry from the same commit.

A push whose version is already tagged is a no-op, and development versions
containing `dev` are never tagged. A manual `v*` tag push runs the same path;
the tag must equal `v<__version__>`. Use `workflow_dispatch` on the `Release`
workflow to retry the resolve step, or re-run the failed job to retry a later
stage without republishing.

## Publication and provenance

No proprietary material belongs in the build, test fixtures, schemas, docs,
or runtime dependencies. Each public source and fixture must be
project-authored or have verified redistributable provenance.

Span is released under Apache-2.0. See `LICENSE` and `NOTICE`.
