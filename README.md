<h1 align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/pontivus-com/span/master/assets/span-logo-full-color-dark.png">
    <img src="https://raw.githubusercontent.com/pontivus-com/span/master/assets/span-logo-full-color-light.png" alt="Span" width="360">
  </picture>
</h1>

<p align="center">
  <strong>Persistent codebase understanding for coding agents.</strong>
</p>

<p align="center">
  Span is a local MCP server that keeps what your agent learned about your
  repository tied to the code it came from, and marks it stale when the
  supporting evidence changes.
</p>

<p align="center">
  <a href="https://modelcontextprotocol.io"><img src="https://img.shields.io/badge/MCP-server-111B21?style=flat-square" alt="MCP server"></a>
  <a href="https://github.com/pontivus-com/span/actions/workflows/ci.yml"><img src="https://github.com/pontivus-com/span/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-blue?style=flat-square" alt="Apache-2.0"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue?style=flat-square" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/platform-Linux%20verified-lightgrey?style=flat-square" alt="Linux verified">
  <img src="https://img.shields.io/badge/status-beta-orange?style=flat-square" alt="Beta">
  <a href="https://github.com/pontivus-com/span/stargazers"><img src="https://img.shields.io/github/stars/pontivus-com/span?style=flat-square" alt="GitHub stars"></a>
</p>

<p align="center">
  <a href="#quick-start"><strong>Quick start</strong></a> ·
  <a href="#how-it-works"><strong>How it works</strong></a> ·
  <a href="docs/"><strong>Docs</strong></a>
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/pontivus-com/span/master/assets/span-product-concept-1600x900.png" alt="Repository evidence flows into Span, which returns CURRENT, STALE, or UNVERIFIABLE understanding" width="900">
</p>

## The problem

Coding agents either trust documentation and memory that may no longer match
the repository, or they re-read the same source, tests, contracts, and
configuration every session and reconstruct the same understanding.

Nothing normally fails when a note becomes wrong. The file still looks valid,
the agent still reads it, and the next session starts from the same
uncertainty.

Span gives the agent a third option: established understanding, stored with
the evidence that supports it, and an explicit answer about whether that
support is still current.

## See it

This is a real exchange from the current build, against a two-file fixture.
The client is a scripted MCP client, not a model; it shows the wire and
freshness behaviour, not model judgement. Raw records:
[current MCP acceptance evidence](docs/acceptance-evidence/mcp-current-2026-10-23/README.md).

```text
> explain src/alpha.py
Pending cont-1  CQ-01
  "VALUE = 1"

> submit_interpretation cont-1
PURPOSE  alpha computes the value
  CURRENT

> explain src/alpha.py
PURPOSE  alpha computes the value
  CURRENT

# edit src/alpha.py

> status src/alpha.py
PURPOSE  alpha computes the value
  STALE
  evidence changed
  scope: src/alpha.py

> refresh src/alpha.py
Pending cont-6  CQ-01
  "VALUE = 1 # touched"

> submit_interpretation cont-6
PURPOSE  alpha computes the value
  CURRENT
predecessor  STALE
```

The first call suspends with a bounded task. The submission establishes the
purpose, and the next explain reads it back as current. After the file changes,
status reports the purpose as stale, with the changed file and the scope to
re-check. Refresh re-examines that one scope; the new result becomes current
while the predecessor stays recorded as stale.

Stale means the supporting evidence changed. It does not mean Span has proved
the old conclusion false.

The edit did not invalidate the whole repository, and it did not leave the old
conclusion looking current. Span does not remove the first investigation; it
keeps that work from being discarded when the session ends.

## How it works

Like tests give code a feedback loop, Span gives codebase understanding one.

1. **Establish.** The agent investigates a bounded area. Span keeps the
   conclusion together with the evidence and authority it used.
2. **Reuse.** Later agents get the established understanding while its support
   is still current.
3. **Invalidate narrowly.** When supporting evidence changes, only the
   understanding that depended on it becomes `STALE`.
4. **Re-check.** The agent investigates the affected scope and submits a new
   result. Unaffected understanding stays current; the predecessor remains as
   history.

| State | Meaning |
| --- | --- |
| `CURRENT` | The recorded understanding is still supported by the evidence and premises it depends on. |
| `STALE` | Relevant support changed after the understanding was established. Re-check it before treating it as current. |
| `UNVERIFIABLE` | Span cannot currently establish whether the required support remains valid. The gap stays visible. |

## Quick start

Span currently requires Linux (the verified installation path), Python 3.12 or
newer, and Node.js with npm.

```bash
git clone https://github.com/pontivus-com/span.git
cd span
python3 scripts/install-span.py --repo /path/to/your/repo
```

The installer creates Span's environment, provisions the managed structural
indexer, and registers supported hosts. Restart or reload your coding agent
after installation.

Verify the installation:

```bash
span-install --verify-only
```

Installation establishes operational readiness, not repository understanding.
For the full install path, the manual Codex command, and the OpenCode entry, see
[install and connect](docs/install.md).

## Works with

| Host | Setup |
| --- | --- |
| Codex | Managed by the installer when the Codex CLI is present. Manual registration is in [install and connect](docs/install.md). |
| OpenCode | Managed when an `opencode.json` is present. The supported manual entry is in [install and connect](docs/install.md). |
| Other MCP hosts | Connect over stdio with `span-mcp --data-dir <DATA_DIR> --repo <TARGET_REPO>`. |

Span runs locally over stdio. It does not call an LLM, choose a model, or store
provider credentials. Its state lives in a data directory outside the
repositories it analyzes.

## Why it is different

Documentation records an answer. Agent memory remembers. Search finds evidence.
Span maintains the interpretation layer between them: the conclusion, its
evidence, its authority, its dependencies, and its freshness.

| Approach | Persists interpreted understanding | Tracks whether it is still supported | Surfaces what changed, with its scope | Supports scoped semantic re-check |
| --- | --- | --- | --- | --- |
| Traditional or generated documentation | Yes | Not inherently | No | No |
| General agent memory | Yes | Not inherently | No | Not inherently |
| Citation-validated agent memory | Yes | Yes, per fact | No — unverified items are withheld | No |
| Code search / structural graph | Different purpose | Source or structure only | Structural only | Not semantic reassessment |
| **Span** | **Yes** | **Yes, per item, premise, and discovery scope** | **Yes, with the reason** | **Yes** |

The detailed comparison, including the difference between validation and
scoped doubt, is in [scope and boundaries](docs/scope.md).

## What it is not

- Not a documentation generator.
- Not general agent memory, validated or otherwise.
- Not code search or a structural graph.
- Not an LLM service: it never invokes a model or stores provider credentials.
- Not autonomous: it does not edit code, run tests, or make stale
  understanding current by itself.

See [scope and boundaries](docs/scope.md) for the full list.

## Status

Span is beta. Linux is the currently verified installation path; macOS and
Windows paths are reserved but not verified. The public operation surface is
eleven MCP operations; see the [MCP reference](docs/mcp.md). Recorded acceptance
runs are in [acceptance evidence](docs/acceptance-evidence/).

If Span is useful to you, a star helps other developers find it. Feedback and
issues are welcome.

## Documentation

- [Install and connect](docs/install.md)
- [Using Span](docs/usage.md)
- [MCP reference](docs/mcp.md)
- [Freshness and refresh](docs/freshness.md)
- [Evidence, authority, trust](docs/authority-trust.md)
- [Scope, boundaries, and differentiation](docs/scope.md)
- [FAQ](docs/faq.md)
- [Architecture](docs/architecture.md)
- [Full documentation index](docs/README.md)
- [Changelog](CHANGELOG.md)

## Contributing

See [the contributing guide](docs/contributing.md). Changes should preserve the
central contract: established understanding remains reusable only while its
required supporting evidence remains current. Security reports are handled
through [SECURITY.md](SECURITY.md).

## License

Span is licensed under the **Apache License 2.0** (`Apache-2.0`). See
[LICENSE](LICENSE).

## In one sentence

**Span gives coding agents codebase understanding that cannot go stale
silently: reuse what is still current, and re-check only what changed.**
