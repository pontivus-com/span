# Backup and recovery

Span stores its retained understanding in a SQLite data directory outside any
target repository. This page is the canonical policy and operator runbook for
protecting that directory and for deploying a repository with its retained
understanding.

Span stores evidence **references and hashes**, not source-file copies. A
recovery artifact therefore carries conclusions, support, observations,
declared surfaces, repository bindings and the content hashes those
observations reference. The repository files remain the authority and are
re-read when delivery or support evaluation needs them.

## Two artifact classes

| Class | Location | Git | Purpose |
| --- | --- | --- | --- |
| **Repository-portable** | `<repo>/.span/backups/<UTC timestamp>/` | **Committed** | Deploy the repository with its Span understanding |
| **Full data-directory** | `<DATA_DIR>/backups/<UTC timestamp>/` | Not committed | Recover the whole installation, including `install.json` |

### Repository-portable artifact

```text
<REPO_ROOT>/.span/backups/<UTC timestamp>/
  <repository-id>.db
  manifest.json
  manifest.sha256
```

- One repository's store only; no `install.json`, `structural/` or
  `transitions/`.
- `manifest.json` uses `span-repository-backup/1`: repository id, source root,
  created at, running code version, artifact path/hash/size, schema version,
  integrity and highest conclusion revision.
- The artifact is intended to be committed with the code. Span writes it; the
  operator runs `git add` / `git commit`. Span never invokes Git.
- The store contains recorded conclusions and evidence text references; it does
  not contain source-file copies. Committing it exposes the recorded
  understanding to everyone with repository access and in history. Commit only
  to a repository whose access controls are appropriate.
- `structural/` is regenerable and excluded; install rebuilds it.

```bash
# Write one artifact into the repository.
span-install --backup-repository <REPO_ROOT>

# Verify it without changing anything.
span-install --verify-repository-backup <ARTIFACT_DIR>

# Remove older working-tree artifacts; Git history is unaffected.
span-install --reap-repository-backups <REPO_ROOT> <KEEP>
```

`KEEP` is explicit; there is no default retention interval. Reaping removes
only directories carrying a valid Span repository manifest and leaves any other
directory untouched.

### Deploy a repository with its Span data

```bash
git clone <remote> pontivus-awb
cd pontivus-awb
span-install --repo .
span-install --load-repository-backup .
span-install --verify-only
```

1. `--repo .` installs the runtime, receipt, host registration, AGENTS block and
   structural index, and binds the clone's canonical root.
2. `--load-repository-backup .` verifies the newest artifact, snapshots the
   current data directory, replaces `<DATA_DIR>/<repository-id>.db`, and
   explicitly rebinds the store's recorded root from the artifact's
   `source_root` to the clone's canonical root.
3. `--verify-only` reports readiness. The agent can then ask a recorded surface
   and receive the retained conclusions.

Rules:

- The clone directory basename must equal the artifact's `repository_id`.
  Renamed clones are refused because Span's repository identity is the basename.
- Load never rewrites `install.json`; install first.
- Load refuses a store held by a live process, a tampered artifact, a legacy
  schema and a third recorded root. It snapshots the current data directory
  before replacing anything.
- A `pre-load` snapshot is written to the full data-directory backup location.

### Full data-directory artifact

The full artifact is the disaster-recovery path for the whole installation. It
contains every top-level `*.db`, `install.json`, `structural-indexer.json`, a
manifest of sizes, SHA-256 digests and per-database facts, and its digest. It is
not committed.

```bash
span-install --data-dir <DATA_DIR> --backup [--backup-root <DIR>]
span-install --verify-backup <BACKUP_DIR>
span-install --data-dir <DATA_DIR> \
  --restore-backup <BACKUP_DIR> --restore-confirm <name>
span-install --data-dir <DATA_DIR> --reap-backups <KEEP>
```

`structural/` (regenerable) and `transitions/` (superseded-store rollback
archives) are excluded with the reason recorded in the manifest. The restore
requires the artifact directory name as explicit confirmation, refuses a
live-held store, snapshots the current data directory, clears stale
WAL/SHM/journal files and re-hashes every restored file. Stop every Span process
before restoring.

## Integrity and compatibility

- The repository and full artifacts verify the manifest digest, every file's
  size and SHA-256, each database's `PRAGMA integrity_check`, its
  `meta.schema_version` and its highest conclusion revision.
- The current store schema is 12. An artifact holding schema 12 loads directly.
  Older supported schemas (7–11) are transition sources; after restoring one,
  run the documented offline transition before use.
- The manifest records the installer version, the running Span code version (or
  `null` when the package cannot be imported), and each database's schema
  version.

## Verification record

The durable verification record is the artifact's own `manifest.json` plus a
sanitized summary in the change record that required recovery: manifest digest,
restored revisions, isolated target, and the lifecycle read-back result. Keep a full data-directory artifact out of Git; a repository-portable artifact
is committed by design. A sanitized summary is sufficient evidence for the
full data-directory artifact.

## Owner and triggers

Owner: the operator of this Span installation. Span keeps no server-side copy.
Take a repository artifact when the retained understanding must travel with the
code; take a full data-directory artifact before a destructive change to the
installation, before a schema transition, and before restoring.
