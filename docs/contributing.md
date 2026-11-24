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

The OpenCode edit-time notice has a named delivery test:

```bash
node --test tests/plugin/test_span_hooks_notice.mjs
```

Node and npm are needed for the installer's structural-indexer
provisioning and for the installed-MCP integration lane. The managed indexer
version is a constant, not a lockfile entry, so
`python3 scripts/check_indexer_pin.py` compares it with npm; a scheduled
workflow runs the same check weekly. Bump the pin only after verifying the
upstream release against the structural fixtures.


For the current candidate, also run `python scripts/typecheck.py`: the configured
mypy run and recorded baseline must both have zero errors. The pinned
structural indexer is required for its integration lane; an indexer-version
skip is deferred verification, not a full pass. Installed-process checks do
not replace real Codex delivery or comparative product-acceptance evidence.

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

A merge, push, green CI run, or completed implementation does **not** publish
Span.

Publication is a separate release-owner decision.

The package version lives in `src/span/__init__.py`; release identity is
resolved through `scripts/release_identity.py` for the package version, Git
tag, registry version, release title, and prerelease state.

The `Release` workflow is **manual-only**:

1. Obtain explicit release-owner authorization for the exact reviewed
   `master` commit/version.
2. Dispatch the `Release` workflow from `master`.
3. Supply `confirm_version` equal to the exact package version.
4. The workflow refuses any non-`master` dispatch or mismatched version
   confirmation.
5. If the release tag already exists, the workflow performs no release. A
   development version is also not published.
6. For an authorized release, the workflow builds and attests the distribution.
7. PyPI publication happens before the release tag is created.
8. After PyPI accepts the version, the workflow creates the Git tag and GitHub
   Release using the matching changelog section.
9. The MCP Registry publication runs from the same resolved release identity.

Do not create or push a manual release tag as a substitute for the authorized
workflow.

A failed later stage may be re-run according to the workflow's idempotent
release checks, but retry is not new authorization for a different SHA or
version.

## Publication and provenance

Raw acceptance captures, transcripts, receipts and manifests are private local
working material. They must remain ignored and untracked; include only sanitized
verification summaries in PRs and release notes.

No proprietary material belongs in the build, test fixtures, schemas, docs,
or runtime dependencies. Each public source and fixture must be
project-authored or have verified redistributable provenance.

Span is released under Apache-2.0. See `LICENSE` and `NOTICE`.
