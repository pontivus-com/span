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
pip install -e '.[test]'
```

Run the suite from the repository root:

```bash
pytest
```

Or with the standard-library runner:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

Node and npm are needed for the installer's structural-indexer
provisioning and for the installed-MCP integration lane.

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

## Publication and provenance

No proprietary material belongs in the build, test fixtures, schemas, docs,
or runtime dependencies. Each public source and fixture must be
project-authored or have verified redistributable provenance.

Span is released under Apache-2.0. See `LICENSE` and `NOTICE`.
