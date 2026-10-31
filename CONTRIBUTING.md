# Contributing to Span

Thanks for taking a look. Span is a small project with deliberately explicit
semantic contracts, so the most useful contributions are focused fixes,
tests, and documentation corrections.

## Quick start

```bash
git clone https://github.com/pontivus-com/span.git
cd span
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[test,dev]'
pytest
```

The installed-MCP acceptance lane also needs `uv`, Node, and npm. Before a pull
request, run `ruff check .` and `black --check .` (or `black .`).


For the 0.9.0 beta, also run `python scripts/typecheck.py`: the configured
mypy run and recorded baseline must both have zero errors. The pinned
structural indexer is required for its integration lane; an indexer-version
skip is deferred verification, not a full pass. Installed-process checks do
not replace real Codex delivery or comparative product-acceptance evidence.

## Before you open a pull request

- Keep the change scoped to one behavior or contract.
- Add or update tests.
- Update the public document that owns the contract.
- Sign off your commits with the Developer Certificate of Origin:

```bash
git commit -s
```

The sign-off certifies that you wrote the change or have the right to submit
it under the project licence. There is no separate CLA.

## Where the details are

- [Repository overview](docs/overview.md) — the code map and request path.
- [Contributing guide](docs/contributing.md) — setup, tests, dependencies,
  provenance.
- [Architecture](docs/architecture.md) — where code belongs.
- [MCP reference](docs/mcp.md) — the public operation surface.
- [Support](SUPPORT.md) — where to ask and what to expect.
- [Security policy](SECURITY.md) — private reporting.

## Licence

Span is released under Apache-2.0. By contributing, you agree that your
contribution is licensed under the same terms.
