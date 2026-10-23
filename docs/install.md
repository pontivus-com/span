# Install and connect

Span runs locally over stdio. The installer provisions its own virtual
environment, links the `span-mcp` and `span-hooks` executables, provisions the
managed structural indexer, and registers supported hosts.

## Requirements

Span currently requires:

- Python 3.12 or newer;
- Node.js plus npm (installation provisions the managed structural
  indexer into Span's tools directory; no separate indexer download);
- Linux for the currently verified installation path.

Span uses a managed structural wiring graph as structural evidence.
Explicit `initialize_repository` and installer verification may build the
provider-owned structural index when it is missing, stale, or the working
tree is dirty (the build then reflects the current tree and freshness stays
`UNVERIFIABLE`). MCP process startup
registration is read-only: it registers repository identity for discovery
and performs no structural build. Explicit `refresh` remains the other
provider-owned rebuild path.

The index lives at:

```text
<DATA_DIR>/structural/<repository-id>/.graph/wiring.json
```

Builds are wiring-only (`--no-deep`, no credentials, no target
writes: `--no-gitignore --no-ignore`). Explicit `refresh` performs at
most one bounded rebuild. Ordinary reads (`status`, `explain`,
`locate`, `neighbors`), hooks, and background paths never build.

macOS and Windows paths are reserved but are not currently verified.

---

## Install

Clone Span, then run the installer from the checkout:

```bash
git clone https://github.com/pontivus-com/span.git
cd span
python3 scripts/install-span.py \
  --repo <TARGET_REPO> \
  --data-dir <DATA_DIR>
```

`--repo` may be repeated for multiple target repositories.

If `--data-dir` is omitted, Span uses the platform default.

On Linux:

```text
~/.local/share/span/data
```

Preview installation without changing anything:

```bash
python3 scripts/install-span.py \
  --repo <TARGET_REPO> \
  --dry-run
```

If you run the installer from outside the checkout, pass
`--span-repo /path/to/span`.

Installation establishes operational readiness only.

It does **not** mean Span already understands your repository.

---

## Supported hosts

Span works with any MCP-capable agent. Managed setup — registration, skills,
and lifecycle hooks — is implemented for Codex and OpenCode today; other hosts
connect manually. Span never invokes an LLM, chooses a model, stores provider
credentials, edits source code, runs tests, or autonomously reinterprets your
repository. Its state lives in a data directory outside the repositories it
analyzes.

## Connect your coding agent

### Codex

Register Span:

```bash
codex mcp add span -- \
  span-mcp \
  --data-dir <DATA_DIR> \
  --repo <TARGET_REPO>
```

Then verify:

```bash
codex mcp list
```

Use the absolute path to `span-mcp` if it is not on Codex's `PATH`.

### OpenCode

The installer can configure OpenCode automatically.

The supported manual `opencode.json` entry is:

```json
{
  "mcp": {
    "servers": {
      "span": {
        "type": "local",
        "command": [
          "span-mcp",
          "--data-dir",
          "<DATA_DIR>",
          "--repo",
          "<TARGET_REPO>"
        ],
        "codemode": false
      }
    }
  }
}
```

`disabled` may be omitted or set to `false`. Do not use the legacy
flat `mcp.span` registration.

Reload OpenCode after changing its MCP configuration.

---

## Verify the installation

```bash
span-install --verify-only
span-mcp --help
```

The doctor is read-only. It reports runtime verification, repository readiness,
and supported host-registration observability. OpenCode is inspected from its
JSON config when one is available; Codex registration is reported as `manual`
because Span's read-only contract cannot deterministically inspect it.
Installation establishes operational readiness only; it does not mean Span
already understands your repository. Continue with the [usage guide](usage.md).
