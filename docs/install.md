# Install and connect

For a new repository:

1. install the package;
2. run `span-install` for the repository;
3. verify the installation;
4. reconnect your coding agent;
5. resolve Functional Pyramid participation for governed use; and
6. start a real task with [First investigation](onboarding-runbook.md).

Functional Pyramid participation is separate from repository installation. A
registered, ready repository starts UNCONFIGURED. Governed use proceeds after
activation reaches ACTIVE + VALID; a repository intentionally outside project
governance can be explicitly EXCLUDED.

## Requirements

The currently verified installation path requires:

- Python 3.12 or newer;
- Node.js plus npm; and
- Linux.

macOS and Windows paths are reserved but are not currently verified.

## Install Span

Install the package:

```bash
pipx install span-mcp        # or: pip install span-mcp
```

Then register and provision the repository:

```bash
span-install --repo <TARGET_REPO>
```

You may repeat `--repo` to install Span for several repositories in one
installation.

If `--data-dir` is omitted, Span uses the platform default. On Linux:

```text
~/.local/share/span/data
```

To choose it explicitly:

```bash
span-install \
  --repo <TARGET_REPO> \
  --data-dir <DATA_DIR>
```

Preview installation without changing anything:

```bash
span-install \
  --repo <TARGET_REPO> \
  --dry-run
```

The canonical repository ID is the selected repository root's basename. Keep
that identity available for lifecycle operations and administration.

### From a source checkout

Contributors, and anyone pinning to a commit, can install from the repository
root:

```bash
git clone https://github.com/pontivus-com/span.git
cd span
python3 scripts/install-span.py \
  --repo <TARGET_REPO> \
  --data-dir <DATA_DIR>
```

A source checkout installs the runtime from that checkout. A package install
uses the released package and its bundled lifecycle guidance. Verification
reports the revision observed in the installed build. Matching version numbers
alone do not establish that two builds are identical. If the build cannot be
verified, reinstall the requested revision and verify again.

## Verify the installation

Run:

```bash
span-install --verify-only
span-mcp --help
```

`--verify-only` is read-only. It reports runtime/store readiness and the host
registration information Span can inspect without changing the installation.

When run without `--repo`, it uses the repository bindings retained in the
current install receipt when those bindings are available.

After installer-driven MCP registration changes, reconnect or restart the
coding-agent host. If the complete Span tool set is not available, start a
fresh session. Registration alone is not proof of live tool availability.

A successful verification means Span is operational for the repository. It does
**not** mean Span already understands the repository.

The `activation_readiness` diagnostic distinguishes healthy participation or
ordinary descriptive use (`not_required`), intended governed initialization
(`requires_governed_install`), observed defects (`requires_repair`), incomplete
observation (`unavailable`) and pending setup/restore (`pending_recovery`).
A healthy ACTIVE instance does not need another initialization. Verification
of a selected ACTIVE member observes its complete retained instance.

Continue with [First investigation](onboarding-runbook.md). After the first
end-to-end workflow, use [Using Span](usage.md) for ordinary work.

## Connect your coding agent

Span runs locally over stdio.

Managed registration, skills, and lifecycle-hook integration exist for Codex,
OpenCode, and Claude Code. Other MCP hosts can connect to the stdio server
manually.

Registration and verified live model delivery are different claims. See
[host status](../integrations/hosts/triggers.md) for the current delivery
evidence.

### Codex

Register Span:

```bash
codex mcp add span -- \
  span-mcp \
  --data-dir <DATA_DIR> \
  --repo <TARGET_REPO>
```

Then verify the registration:

```bash
codex mcp list
```

Use the absolute path to `span-mcp` if it is not on Codex's `PATH`.

### Claude Code

The installer can register Span at Claude Code user scope. The equivalent
registration command is:

```bash
claude mcp add --scope user --transport stdio span -- \
  span-mcp \
  --data-dir <DATA_DIR> \
  --repo <TARGET_REPO>
```

`span-install` selects Claude automatically when its CLI or host footprint is
present. Use `--with-claude` or `--no-claude` to make that choice explicit.

Report-only lifecycle hooks are written only to an existing
`~/.claude/settings.json`. Foreign settings and hooks are preserved. Existing
`~/.claude` roots can receive the canonical Span skills.

`--uninstall` removes only Span's user-scope registration, Span-owned hook
entries, and ownership-marked skills.

Claude registration and health can be inspected, but authenticated model
delivery remains a separate verification claim.

### OpenCode

The installer can configure OpenCode automatically.

For a fresh install, the default plugin scope is `global`. When no explicit
MCP path is supplied and no local `./opencode.json` exists, the installer uses
the global `~/.config/opencode/opencode.json` for both the Span lifecycle
plugin and MCP registration.

The supported manual entry is:

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

`disabled` may be omitted or set to `false`.

Only `mcp.servers.span` is the supported manual registration shape. The older
flat `mcp.span` form is not supported.

OpenCode exposes Span's `ask`, `record`, and `reconsider` tools directly.
Its code-mode sandbox does not include MCP tools, so call the Span MCP tools
directly rather than routing them through code-mode execution.

Reload OpenCode after changing its MCP configuration.

For plugin scope, path selection, relocation, and upgrade rules, see
[Advanced OpenCode configuration](#advanced-opencode-configuration).

## Governed installation (Beta-5)

Provide the repository-owned Functional Pyramid classification document described
in [lifecycle §7.1](lifecycle-contract.md#71-functional-pyramid-initializationadoption-lifecycle)
and [technical design §17.2](technical-design.md#172-functional-pyramid-initialization-import).
The sole initialization command is:

```bash
span-install --repo /work/repo-a \
  --functional-pyramid-classification-file repo-a /work/repo-a/.span/functional-pyramid-classification.json
```

For multiple members, repeat `--repo` and the classification mapping for each
explicitly selected member. Span performs all mechanical initialization and
reports the verified outcome or exact blocker/semantic-effect handoff. Do not
prepare or commit derived declaration, bootstrap or binding files or issue a
separate activation command. Ordinary installation without governed input
remains non-activating. The generated Version-3 sources and Version-2 navigation bootstrap are internal;
there is no raw bootstrap setup option or fresh MCP activation path.

## Optional ordinary project-authority configuration

Use this independent input for explicit ordinary authority seeds or bindings.
Do not provide a competing authority-binding input for a governed member.

Authority input is repository-qualified:

```bash
span-install \
  --repo /work/repo-a \
  --repo /work/repo-b \
  --authority-seeds-file repo-a /config/repo-a-seeds.json \
  --authority-bindings-file repo-b /config/repo-b-bindings.json \
  --data-dir <DATA_DIR>
```

Each seeds file is a strict JSON list of canonical `EvidenceRef` values. Each
bindings file is a strict JSON list of canonical `AuthorityBinding` values.

The repository ID in every item must match the repository-qualified CLI
mapping, and every locator must resolve inside the selected repository root.
Duplicate mappings, unselected repository IDs, malformed canonical content,
identity mismatches, or unknown locators are rejected rather than guessed.

For each repository and authority family:

- no mapping preserves the configured value;
- a mapped `[]` clears it; and
- a mapped non-empty list replaces it exactly.

All deterministic decoding, routing and exact repository-qualified authority
validation completes before pending setup publication, generated declaration
publication or repository-store mutation. The complete configuration is the
validation unit: evidence-delivery pagination does not limit administrative
authority capacity. Do not batch or reduce governance to fit a query budget.

Ordinary provisioning does not activate Functional Pyramid participation.
Explicit governed installation continues through the initialization contract
above; registration by itself is not governed initialization completion.

## What installation provisions

The installer provisions Span's runtime environment, executable links, managed
structural indexer, repository stores, lifecycle guidance, and supported host
integration selected for the installation.

Span uses a managed structural wiring graph as structural evidence. Installer
provisioning may build the provider-owned structural index when it is missing,
stale, or the working tree is dirty.

The index lives under:

```text
<DATA_DIR>/structural/<repository-id>/.graph/wiring.json
```

Structural builds are wiring-only and use no credentials or target-source
writes. Ordinary `ask`, `reconsider`, hook delivery, and MCP process startup
do not rebuild the structural index.

`--verify-only` is observational and never initializes or rebuilds.

The MCP runtime itself does not edit target source, invoke an LLM, choose a
model, store provider credentials, or run application tests. Host integration
and managed lifecycle guidance belong to the installer.

## Advanced OpenCode configuration

OpenCode MCP configuration selection follows this precedence:

1. explicit `--opencode-config PATH`;
2. the prior install receipt's MCP path when upgrading;
3. local `./opencode.json` when present;
4. global `~/.config/opencode/opencode.json` when the effective plugin scope
   is `global`;
5. no MCP selection for `local` or `none` scope without an explicit or local
   path.

`--no-hooks` skips lifecycle hook/plugin wiring only. It does not skip MCP
server registration.

Selected paths are stored as absolute receipt identities. A later bare install
therefore reuses the recorded MCP file. An explicit path changes the selection;
after the new registration succeeds, the previous recorded Span registration is
removed.

Before an explicit relocation, a prior receipt-owned file that contains Span's
registration must be valid JSON and writable. If that preflight fails, the new
configuration is not created.

The installer manages the Span lifecycle plugin under an explicit scope:

| Scope | Global `opencode.json` | Span data-root plugin | Targets passed with `--repo` | Receipt target not selected | Unregistered repos | User-managed global dirs |
| --- | --- | --- | --- | --- | --- | --- |
| `global` | update | update | report Span-owned copies as conflicts | read-only; conflict if present | never | report; conflict if present |
| `local` | remove Span-owned entry | remove Span-owned dir | report only | read-only; report only | never | report only |
| `none` | remove Span-owned entry | remove Span-owned dir | report only | read-only; report only | never | report only |

A fresh install defaults to `global` and prints that choice. An upgrade uses
the scope in the install receipt. If the receipt does not identify an
unambiguous scope, rerun with:

```text
--opencode-plugin-scope global|local|none
```

The installer does not infer scope from incidental files on disk.

Under `global`, the installer deploys the plugin under
`<DATA_DIR>/../../opencode-plugin` and registers that directory once in the
global OpenCode configuration. It does not write the plugin into a target
repository.

A Span plugin already found under a selected target's
`.opencode/plugins` is reported as a conflict and left untouched.

Under `local` and `none`, target plugins are user-managed. Span removes only
its own global registration and data-root plugin, reports local copies, and
leaves the target untouched.

The current installer does not perform obsolete target-plugin compatibility
migration.

The plugin waits a bounded three seconds at prompt admission for the local MCP
connection so the first model request can see the Span tools. It also provides
lifecycle notices for registered operational repositories. Correctness does not
depend on those notices being delivered.

## Upgrade an existing installation

Re-run `span-install` with the current package or source checkout.

For OpenCode, the installer reuses the receipt's recorded MCP and plugin
configuration paths. If an upgrade receipt has no unambiguous plugin scope,
supply `--opencode-plugin-scope global|local|none`.

Use:

```bash
span-install --verify-only
```

to inspect the resulting registration and scope, then restart the coding-agent
host after configuration changes.

A package upgrade by itself does not imply that older repository-store schemas
have been transitioned. See [Upgrade an existing store](#upgrade-an-existing-store)
when the runtime reports an explicit store transition requirement.

## Back up or recover an installation

Backup, repository-portable deployment, restore, retention, and recovery are
owned by [Backup and recovery](recovery.md).

Use that guide before a store transition or any operation where you need a
restorable artifact. The installer also takes its defined backup before
reinstall mutation according to the recovery contract.

## Remove or purge

Nothing is removed automatically.

To remove Span-owned host integration:

```bash
span-install --uninstall
```

`--uninstall` reverses only Span-owned host-side writes: MCP registration,
hook entries, managed agent guidance/skills, and the install receipt. It does
not remove repository data stores or structural indexes. Repeating it is a
no-op.

A malformed or duplicated managed marker is left for review rather than guessed
at.

To remove one repository's stored runtime data:

```bash
span-install --purge <repository-id>
```

This removes only that repository ID's lifecycle database/SQLite sidecars and
structural directory. Repository IDs containing path separators or traversal
are rejected.

To inspect unreceipted repository IDs without deleting anything:

```bash
span-install --list-orphans
```

An orphan report means an ID exists on disk but is absent from the current
receipt. It is not proof that the data is unused.

## Upgrade an existing store

Beta 3 uses repository schema 15. Runtime open never performs an implicit store
migration. A supported older repository store fails closed with an explicit
transition action.

The separate installation Functional Pyramid store remains at installation
schema 1.

Stop every process using the repository stores, then run one phase at a time for
each repository ID:

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

`inspect` and `verify` are observational.

`apply` requires an explicit repository root whose basename matches the
repository ID. It holds exclusive store ownership through activation, archives
a WAL-consistent copy, writes the lossless export/report, stages schema 15,
verifies it, and atomically activates it.

Supported source repository schemas are 7 through 14.

### What the transition preserves

For schema 14, the Beta-3 transition copies retained semantic, audit, governance,
and route-index state without reinterpretation. It creates zero curation
approvals. A migrated revision that is still support-current therefore begins
as captured/pending knowledge rather than being silently approved for shared
reuse.

For schema 13, durable semantic/audit rows are copied and the repository-local
route dependency index is derived only from already-retained route support.
Functional Pyramid participation, installation receipts, authority support, or
curation approval are not invented.

Earlier supported schemas retain their documented preservation boundaries while
targeting schema 15. Older information that cannot be reconstructed remains in
the transition export rather than being fabricated as current state.

After repository transition, run normal installer/setup for the current
candidate so the separate installation Functional Pyramid database is present
and verified. Repository transition does not manufacture participation state.

### Roll back

Rollback is explicit:

```bash
span-install --data-dir <DATA_DIR> \
  --transition-store <repository-id> --transition-phase rollback
```

Before activation, rollback discards owned staging. After activation, it
preserves writes made by the new-format repository store as a new-format
artifact and restores the previous store.

Restart the old binary after rollback.

Transition artifacts live under:

```text
<DATA_DIR>/transitions/<repository-id>/
```

Keep the archive, export, mapping, report, and restart-safe manifest until the
new store and installation have been verified and retained according to your
policy.

Known limitation: an idle old process holding no SQLite lock cannot be detected.
Stop old Span processes before transition and rehearse on a disposable copy
before a live upgrade.
