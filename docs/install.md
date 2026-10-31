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
Explicit `initialize_repository` may build the provider-owned structural
index when it is missing, stale, or the working tree is dirty (the build then
reflects the current tree and freshness stays `UNVERIFIABLE`). MCP process
startup registration is read-only: it registers repository identity for
discovery and performs no structural build. Installer `--verify-only` is
observational and never initializes or rebuilds. No separate `refresh`
operation exists in 0.9.0.

The index lives at:

```text
<DATA_DIR>/structural/<repository-id>/.graph/wiring.json
```

Builds are wiring-only (`--no-deep`, no credentials, no target
writes: `--no-gitignore --no-ignore`). Explicit setup performs at
most one bounded rebuild. Ordinary reads (`understand_*`, `locate`,
`neighbors`), hooks, and background paths never build.

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

Managed registration and skills are implemented for Claude Code, Codex, and
OpenCode, with host-specific optional hooks. Codex is the live beta validation
target. OpenCode has earlier trial evidence without final-package revalidation;
Claude model-delivered grammar and caller identity remain UNVERIFIED under the
owner waiver. Other MCP hosts connect manually without an assumed delivery
guarantee. See [host status](../integrations/hosts/triggers.md). Span never invokes an LLM, chooses a
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

The doctor is read-only. It reports runtime verification, store readiness,
and supported host-registration observability. OpenCode is inspected from its
JSON config when one is available; Codex registration is reported as `manual`
because Span's read-only contract cannot deterministically inspect it.
Installation establishes operational readiness only; it does not mean Span
already understands your repository. Continue with the [usage guide](usage.md).

---

## Remove or purge

Installation has an explicit terminal. Nothing is removed automatically.

```bash
span-install --uninstall
span-install --purge <repository-id>
span-install --list-orphans
```

`--uninstall` reverses only the host-side writes: the OpenCode/Codex/Claude MCP
entry, Span's hook entries, the managed `AGENTS.md` block in each registered
target, deployed skills carrying Span's origin marker, and the receipt. It never
touches repository data (stores, structural indexes), and running it twice is a
no-op. A malformed or duplicated `AGENTS.md` marker pair is left untouched for
review rather than guessed at.

`--purge <repository-id>` removes exactly that ID's
`<data-dir>/<id>.db` (with any SQLite sidecars) and
`<data-dir>/structural/<id>/`. The ID is one directory name; separators and
traversal are rejected. Nothing else in the data directory is touched, so
purging an unattributable store is also the recovery path for a repository
identity conflict: re-initialize the same root afterwards.

`--list-orphans` reports IDs present on disk and absent from the receipt. It
deletes nothing. A repository can be registered through `--repo` alone, so
absence from a receipt is evidence of an unreceipted ID, not proof that its
data is unused.

## Upgrade an existing store

Span 0.9.0 uses schema 10. The runtime never migrates at open; an older store
fails closed with a transition action. `--migrate-store` is removed.

Stop every process using the store, then run one phase at a time for each
repository ID:

```bash
span-install --data-dir <DATA_DIR> \
  --transition-store <repository-id> --transition-phase inspect \
  --transition-root <TARGET_REPO>

span-install --data-dir <DATA_DIR> \
  --transition-store <repository-id> --transition-phase apply \
  --transition-root <TARGET_REPO>

span-install --data-dir <DATA_DIR> \
  --transition-store <repository-id> --transition-phase verify \
  --transition-root <TARGET_REPO>
```

`inspect` and `verify` are observational. `apply` requires an explicit root
whose basename matches the repository ID, holds exclusive store ownership
through activation, archives a WAL-consistent copy, writes a lossless raw
export and readable report, stages schema 10, verifies it, and atomically
activates it. Supported source schemas are 7, 8, and 9. Refusals (live writer,
unsupported schema, failed integrity, insufficient space, wrong root) change
nothing.

Only the repository root binding and declared authority seeds are carried
forward. Legacy claims, campaigns, coverages, and targets remain historical
export; they are not promoted as current understanding. Re-record current
understanding through the lifecycle tools and re-declare explicit authority
bindings in setup.

Roll back before or after activation:

```bash
span-install --data-dir <DATA_DIR> \
  --transition-store <repository-id> --transition-phase rollback
```

Before activation, rollback discards only owned staging. After activation, it
preserves any schema-10 writes as `new-format-*.db` and restores the previous
store. Restart the old binary afterward.

The archive, export, report, and restart-safe manifest live under
`<DATA_DIR>/transitions/<repository-id>/`. Do not delete them until the new
store has been verified and retained according to your own policy.

Known limitations: an idle old server that holds no SQLite lock is not
detected, so the operator must stop all old processes; interrupted-transition
runtime fencing is not yet proven in production. Rehearse on a disposable
copy before a live upgrade.
