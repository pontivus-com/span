# Host-contract capture fixture

Status: **HISTORICAL/VOID for the current `ask`/`record`/`reconsider` surface.**

This directory holds test-only schema diagnostics for host delivery.
`schema_lab_server.py` is a generic schema-construction diagnostic; it does not
certify live host delivery for the current surface.

The delivered three-tool journey, exact surface selection, declared surfaces,
continuation, replay/restart, and challenge settlement are covered by:

```sh
PYTHONPATH=src python3 -m pytest tests/integration/test_lifecycle_mcp.py -v
```

That lane drives the installed `span-mcp` over stdio. It does **not** prove that
a host converter accepts or delivers the grammar.

To record a live capture for one host/version, use an isolated host profile
and a project-authored fixture repository. Do not modify a user's live Span
configuration. Capture, at minimum:

- Span source revision/build identity and generated schema digest;
- installed `span-mcp` package/path and the host/model/version;
- the exact host-native invocation and reconnect command;
- the advertised tool schema and the model-delivered declaration;
- the submitted request and delivered response;
- a lost-response, retry, restart, and concurrent-invocation case;
- outcome `observed`, `failed`, or `unverified`, plus unobserved limits.

Template command placeholders (fill with the exact tested values):

```sh
# Codex / OpenCode: replace <host-cli>, <profile>, and <repo>.
<host-cli> --profile <isolated-profile> --mcp-server span-mcp --repo <repo>
```

A simulated converter, a stdio schema round-trip, or a clean install is not
live-host delivery evidence. G-0 remains open until the capture manifest
names a real host/version and preserves the raw events described above.
