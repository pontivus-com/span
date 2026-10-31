# Host-contract capture fixture

Status: **UNVERIFIED for live host delivery.** This directory is the
planned test-only owner for the 0.9.0 host-contract probe. It is not a
record of a successful Codex, OpenCode, or Claude conversion.

The automated lane is:

```sh
PYTHONPATH=src python3 -m pytest tests/integration/test_host_contract.py -v
```

That lane checks the local candidate grammar, generated schema, wire codec,
and closed branch obligations. It does **not** prove that a host converter
accepts or delivers the grammar.

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
# Codex / OpenCode / Claude: replace <host-cli>, <profile>, and <repo>.
<host-cli> --profile <isolated-profile> --mcp-server span-mcp --repo <repo>
```

A simulated converter, a stdio schema round-trip, or a clean install is not
live-host delivery evidence. G-0 remains open until the capture manifest
names a real host/version and preserves the raw events described above.
