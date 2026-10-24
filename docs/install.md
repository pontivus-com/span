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

Install the package, then run the installer:

```bash
pipx install span-mcp        # or: pip install span-mcp
span-install \
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
span-install \
  --repo <TARGET_REPO> \
  --dry-run
```

### From a source checkout

Contributors, and anyone pinning to a commit, install from the repository root:

```bash
git clone https://github.com/pontivus-com/span.git
cd span
python3 scripts/install-span.py \
  --repo <TARGET_REPO> \
  --data-dir <DATA_DIR>
```

A checkout installs the runtime from that source. A package install installs the
same released version into Span's runtime environment and reads the skills and
lifecycle snippet bundled in the package instead of the repository copies.

Installation establishes operational readiness only.

It does **not** mean Span already understands your repository.

---

## Supported hosts

Span works with any MCP-capable agent. Managed setup — registration, skills,
and lifecycle hooks — is implemented for Claude Code, Codex, and OpenCode
today; other hosts connect manually. Span never invokes an LLM, chooses a
model, stores provider credentials, edits source code, runs tests, or
autonomously reinterprets your repository. Its state lives in a data
directory outside the repositories it analyzes.

## Connect your coding agent

### Claude Code

The installer configures Claude Code automatically when the `claude` CLI is
present: a user-scope stdio registration, skills in `~/.claude/skills`, and
report-only lifecycle hooks in `~/.claude/settings.json`. Pass `--no-claude`
to skip all of it. Hooks are added to an existing settings file and never
created from nothing; if `~/.claude/settings.json` does not exist yet, start
Claude Code once and re-run the installer to wire them.

Register manually at user scope:

```bash
claude mcp add --scope user --transport stdio span -- \
  span-mcp \
  --data-dir <DATA_DIR> \
  --repo <TARGET_REPO>
```

Then verify:

```bash
claude mcp list
```

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
