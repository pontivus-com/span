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
Installer provisioning may build the provider-owned structural index when it is
missing, stale, or the working tree is dirty (the build then reflects the
current tree and freshness stays `UNVERIFIABLE`). MCP process startup
registration is read-only: it registers repository identity for discovery and
performs no structural build. Installer `--verify-only` is observational and
never initializes or rebuilds. There is no separate refresh operation in the
public surface.

The index lives at:

```text
<DATA_DIR>/structural/<repository-id>/.graph/wiring.json
```

Builds are wiring-only (`--no-deep`, no credentials, no target
writes: `--no-gitignore --no-ignore`). Explicit setup performs at
most one bounded rebuild. Ordinary reads (`ask`, `reconsider`), hooks, and
background paths never build.

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

Repository setup is explicit and is performed by the installer. Existing
authority configuration is preserved when no authority file is supplied. To
declare canonical authority during setup, pass canonical JSON lists using
`--authority-seeds-file` and/or `--authority-bindings-file`:

```bash
span-install \
  --repo <TARGET_REPO> \
  --authority-bindings-file <BINDINGS_JSON>
```

A bindings file is a JSON list of canonical `AuthorityBinding` values. For a
multi-repository install, items are partitioned by
`evidence_ref.repository_id`; every named repository must also be selected by
`--repo`. The installer validates each binding's exact source locator through
the canonical repository evidence boundary before registering it. Supplying an
empty list explicitly clears bindings for the selected repositories; omitting
the flag preserves the existing bindings.

It does **not** mean Span already understands your repository.

---

## Supported hosts

Managed registration, skills, and lifecycle hooks are implemented for Codex,
OpenCode, and Claude Code. These are the supported managed hosts. Claude's
registration and health are inspectable, while authenticated model-delivery
grammar and caller identity remain `UNVERIFIED`; registration does not prove
model delivery. Replay safety is claimed only where the host preserves request
identity (FD-50). Other MCP hosts connect manually without an assumed delivery
guarantee. See
[host status](../integrations/hosts/triggers.md). Span never invokes an LLM, chooses a
model, stores provider credentials, edits source code, runs tests, or
autonomously reinterprets your repository. Its state lives in a data
directory outside the repositories it analyzes.

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

### Claude Code

The installer registers Span through Claude Code's user-scope CLI command:

```bash
claude mcp add --scope user --transport stdio span -- \
  span-mcp \
  --data-dir <DATA_DIR> \
  --repo <TARGET_REPO>
```

`span-install` selects Claude automatically when its CLI or host footprint is
present. Use `--with-claude` or `--no-claude` to make that choice explicit.
Report-only lifecycle hooks are written only to an existing
`~/.claude/settings.json`; foreign settings and hooks are preserved, and every
hook command carries the installed `--data-dir`. Existing `~/.claude` roots
can receive the canonical Span skills. `--uninstall` removes only Span's
user-scope registration, hook entries, and ownership-marked skills. Doctor
inspection is read-only and reports registration/configuration separately from
the `UNVERIFIED` authenticated model-delivery state.

### OpenCode

The installer can configure OpenCode automatically.

For a fresh install, the default OpenCode plugin scope is `global`. When no
explicit MCP path is supplied and no local `./opencode.json` exists, the
installer uses the same global `~/.config/opencode/opencode.json` for both the
Span lifecycle plugin and the `mcp.servers.span` registration. The selection
precedence is:

1. explicit `--opencode-config PATH`;
2. the prior install receipt's MCP path, when upgrading an existing install;
3. local `./opencode.json` when present;
4. the global OpenCode config when the effective plugin scope is `global`;
5. no MCP selection for `local`/`none` scope without an explicit or local path.

`--no-hooks` skips lifecycle hook and plugin wiring only; it does not skip the
MCP server registration. A global registration is still rewritten with the
current data directory and every `--repo` binding.

Selected paths are stored as absolute receipt identities. A later bare install
therefore reuses the same MCP file even when launched from another directory.
An explicit path changes that selection; after the new registration succeeds,
the previous recorded Span registration is removed.

Before an explicit relocation, the prior receipt-owned file must be valid JSON
and writable when it contains Span's registration. If that preflight fails, the
new configuration is not created.

The install receipt records the selected MCP and plugin configuration paths.
Bare `span-install --verify-only` reuses the recorded MCP path before checking
the local file, so verification does not require repeating the install flag.
Uninstall removes each owned artifact from its recorded configuration and leaves
foreign entries untouched. A present receipt that is not the current receipt
contract fails closed; it is not treated as a fresh installation.

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

`disabled` may be omitted or set to `false`. Only `mcp.servers.span` is
interpreted as Span's registration; other configuration keys are preserved.

The installer manages the Span lifecycle plugin under an explicit scope. The
scope is an end-user choice; the installer never infers it from what happens to
exist on disk:

| Scope | Global `opencode.json` | Span data-root plugin | Targets passed with `--repo` | Receipt target not selected | Unregistered repos | User-managed global dirs |
| --- | --- | --- | --- | --- | --- | --- |
| `global` | update | update | report Span-owned copies as conflicts | read-only; conflict if present | never | report; conflict if present |
| `local` | remove Span-owned entry | remove Span-owned dir | report only | read-only; report only | never | report only |
| `none` | remove Span-owned entry | remove Span-owned dir | report only | read-only; report only | never | report only |

A fresh install defaults to `global`, printed. An upgrade uses the scope in the
install receipt; when the receipt records no unambiguous scope, the installer
stops and requires `--opencode-plugin-scope global|local|none`. It does not
guess. A flag that changes the recorded scope prints the old and new values and
cleans Span's old registration.

Under `global`, the installer deploys the plugin under
`<DATA_DIR>/../../opencode-plugin` and registers that directory once in the
host's global `~/.config/opencode/opencode.json` (`plugins`). It does not write
the plugin into a target repository. For every target passed with `--repo`, a
Span plugin found under `.opencode/plugins` is reported as a conflict and left
untouched. A receipt target that is not passed with `--repo` is inspected
read-only; if a Span-owned copy remains there, the result is `conflict`, never
`wired`.

Under `local` and `none`, the target plugin is user-managed. Span removes only
its own global registration and the data-root plugin, reports every local copy
it finds, and leaves the target untouched. Exactly one user-managed copy is
`external`; more than one is `conflict`; none is `absent` (`local`) or `disabled`
(`none`).

The MCP server itself never edits a target repository; host integration belongs
to the installer. The current installer does not perform obsolete target-plugin
compatibility migration. The plugin waits a bounded three
seconds at prompt admission for the local MCP connection, so the first model
request already sees the Span tools, and injects the lifecycle notice at session
start for registered operational repositories, including cold stores. An edit-time notice names
the changed paths and the exact `reconsider(changed_paths=[...])` call on the
next context turn. The required agent lifecycle applies even if a notice is not delivered.

OpenCode exposes the server's tools to the agent directly (`ask`, `record`,
`reconsider`, prefixed by the server name). Its code-mode sandbox does not
include MCP tools, so an agent that routes Span through `execute` sees
`Unknown tool`; tell it to call the MCP tools directly, not through code mode.

Reload OpenCode after changing its MCP configuration.

### Upgrading an existing installation

The current installer reuses the receipt's absolute OpenCode MCP and plugin
configuration paths. If an upgrade receipt has no unambiguous plugin scope,
rerun with `--opencode-plugin-scope global|local|none`; the installer does not
guess. The current path does not migrate obsolete target-plugin copies. Use
`span-install --verify-only` to inspect the current registration and scope, then
restart the host after configuration changes.

When `--verify-only` is run without `--repo`, it also uses the repository
bindings in the current receipt. This keeps registration and runtime readiness
checks aligned with the installation being inspected.

---

## Verify the installation

```bash
span-install --verify-only
span-mcp --help
```

The doctor is read-only. It reports runtime verification, store readiness, and
supported host-registration observability. OpenCode and Claude are inspected
from their user configuration when available; Codex registration is reported
as `manual` because Span's read-only contract cannot deterministically inspect
it. Registration health does not establish authenticated model delivery.
Installation establishes operational readiness only; it does not mean Span
already understands your repository. Continue with the [usage guide](usage.md).

---

## Back up, deploy and recover

Span has two artifact classes.

**Repository-portable** — one repository's store inside that repository at
`.span/backups/`, intended to be committed with the code and loaded on a fresh
deployment:

```bash
span-install --backup-repository <REPO_ROOT>
span-install --verify-repository-backup <ARTIFACT_DIR>
span-install --load-repository-backup <TARGET_ROOT>
```

The clone directory basename must match the repository id. Load verifies the
artifact, snapshots the current data directory, replaces the store and
explicitly rebinds its recorded root to the clone. Install first, then load:

```bash
span-install --repo .
span-install --load-repository-backup .
span-install --verify-only
```

**Full data-directory** — the whole installation, including the receipt,
written outside Git:

```bash
span-install --data-dir <DATA_DIR> --backup
span-install --verify-backup <BACKUP_DIR>
span-install --data-dir <DATA_DIR> \
  --restore-backup <BACKUP_DIR> --restore-confirm <name>
```

The installer takes the same full backup before a reinstall mutation.
`structural/` is regenerable and excluded; the artifact records that reason.
Retention is explicit (`--reap-backups KEEP`,
`--reap-repository-backups <REPO_ROOT> <KEEP>`) and is never applied
automatically. Stop every Span process before restoring or loading. The full
policy, storage guidance, security consequence and isolated restore procedure
are in [backup and recovery](recovery.md).

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

Version 1 uses repository schema 14. The runtime never migrates at open; a
supported older repository store fails closed with the explicit transition
action. The separate installation Functional Pyramid store is created or
verified by installer/setup and is not manufactured by repository runtime open.

Stop every process using the repository stores, then run one phase at a time
for each repository ID:

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
through activation, archives a WAL-consistent copy, writes the lossless export
and report, stages schema 14, verifies it, and atomically activates it.
Supported source repository schemas are 7 through 13.

The schema-13 → schema-14 mapping preserves the existing durable semantic and
audit tables without reinterpretation. It adds the repository-local
`functional_route_dependency_index`, derived only from
`FunctionalRouteSupport` already present in retained conclusions. It does not
invent Functional Pyramid participation, installation receipts, route support
or canonical authority support. After transition, a registered repository is
therefore still UNCONFIGURED until participation is explicitly recorded.

Earlier source schemas retain their documented preservation/mapping behavior.
In particular, schema-12 context binding cannot be reconstructed from the old
request digest, schema-10/11 use their durable mappings, and schemas 7–9 keep
only the repository binding and declared authority seeds as current state while
legacy semantic material remains in the transition export.

After repository transition, run normal installer/setup for the current
candidate so `<DATA_DIR>/installation/functional-pyramid.db` exists with the
current installation-store schema. That database owns Functional Pyramid
participation, instance versions, exclusions and installation-scoped receipts;
it is intentionally separate from every repository lifecycle database.

Roll back a repository transition before or after activation:

```bash
span-install --data-dir <DATA_DIR> \
  --transition-store <repository-id> --transition-phase rollback
```

Before activation, rollback discards only owned staging. After activation, it
preserves writes made by the new-format repository store as
`new-format-*.db` and restores the previous store. Restart the old binary
after rollback. Functional Pyramid installation state has its own installation
database and is not smuggled into a repository rollback artifact.

The archive, export, mapping, report and restart-safe manifest live under
`<DATA_DIR>/transitions/<repository-id>/`. Keep them until the new store and
installation have been verified and retained according to your policy.

Known limitation: an idle old process holding no SQLite lock cannot be detected,
so the operator must stop old Span processes before transition. Rehearse on a
disposable copy before a live upgrade.
