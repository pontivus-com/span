# Backup and recovery

Span has two different backup jobs:

1. **Move one repository together with its retained Span knowledge.**
2. **Recover an entire Span installation.**

Choose the artifact that matches the job. They are intentionally different.

Span stores references and hashes for source evidence rather than copying source
files into its knowledge store. The repository remains the source of those
bytes.

## Which backup do I need?

| Need | Artifact | Location | Commit to Git? |
| --- | --- | --- | --- |
| Move/deploy one repository with its retained Span knowledge | **Repository-portable backup** | `<repo>/.span/backups/<UTC timestamp>/` | **Yes, when repository access is appropriate for the retained knowledge** |
| Recover the whole Span installation | **Full data-directory backup** | `<DATA_DIR>/backups/<UTC timestamp>/` | **No** |

Repository-portable backups intentionally do not carry installation-level
Functional Pyramid participation. Full installation backups do.

## Repository-portable backup

Use this when retained knowledge should travel with a repository.

Create the artifact:

```bash
span-install --backup-repository <REPO_ROOT>
```

Verify it without changing anything:

```bash
span-install --verify-repository-backup <ARTIFACT_DIR>
```

Remove older working-tree artifacts when you choose:

```bash
span-install --reap-repository-backups <REPO_ROOT> <KEEP>
```

There is no default retention interval. Reaping touches only directories with a
valid Span repository-backup manifest.

A repository-portable artifact contains:

```text
<REPO_ROOT>/.span/backups/<UTC timestamp>/
  <repository-id>.db
  manifest.json
  manifest.sha256
```

It contains one repository's retained semantic/audit state. It does **not**
contain:

- the installation receipt;
- the managed structural index;
- store-transition artifacts; or
- Functional Pyramid participation, pyramid versions, exclusions, or
  installation-scoped receipts.

Those belong to the installation.

### Security consequence

The repository backup contains retained conclusions and evidence references.
Committing it exposes that maintained knowledge to everyone who can read the
repository and to repository history.

Commit repository-portable backups only where those access controls are
appropriate.

Span writes the artifact. The operator decides whether to add and commit it;
Span does not invoke Git.

## Deploy a repository with retained Span knowledge

For a repository carrying a repository-portable backup:

```bash
git clone <remote> repository-clone
cd repository-clone
span-install --repo .
span-install --load-repository-backup .
span-install --verify-only
```

The order matters:

1. **Install first.** This establishes the runtime, receipt, host integration,
   canonical repository root, and structural index.
2. **Load the repository backup.** Span verifies the artifact, snapshots the
   current data directory, replaces that repository's lifecycle store, and
   rebinds the recorded repository root to the clone.
3. **Verify.** Confirm the restored installation is operational before using it.

The clone directory basename must match the artifact's repository ID. A renamed
clone is refused rather than silently treated as the same repository.

Loading also refuses tampered artifacts, unsupported direct-load schemas, live
store ownership, and conflicting recorded roots.

A pre-load snapshot is written to the full data-directory backup location before
the repository store is replaced.

## Full installation backup

Use a full data-directory backup before destructive installation changes, store
transitions, or restore operations.

Create one:

```bash
span-install --data-dir <DATA_DIR> --backup [--backup-root <DIR>]
```

Verify it:

```bash
span-install --verify-backup <BACKUP_DIR>
```

Restore it:

```bash
span-install --data-dir <DATA_DIR> \
  --restore-backup <BACKUP_DIR> --restore-confirm <name>
```

Reap older full backups explicitly:

```bash
span-install --data-dir <DATA_DIR> --reap-backups <KEEP>
```

Stop every Span process before restoring.

The full artifact carries the installation state needed for disaster recovery,
including:

- every top-level repository lifecycle database;
- `installation/functional-pyramid.db`;
- `install.json`;
- `structural-indexer.json`; and
- a manifest containing file digests and database facts.

The managed `structural/` directory is regenerable and is excluded.
`transitions/` is also excluded because transition rollback artifacts have
their own lifecycle. The manifest records those exclusions.

Restore snapshots the current data directory first, rejects live-held stores,
clears stale SQLite sidecar files, restores the artifact, and verifies the
restored content.

## Interrupted governed installation

Use the exact pending receipt and its original classification input to resume.
If participation was accepted, complete the original operation and retain its
effects rather than abandoning it. For an unaccepted pending setup with a
verified pre-setup backup, stop every Span server and hook, then explicitly
confirm restoration of that original backup using the full restore command
above. The installer verifies the generated-file preimages and absences,
selected repository state and installation state before changing anything.
It retains the recovery snapshot and restores the receipt last; unrelated
repository stores are not rolled back. If interrupted during restoration,
repeat the same confirmed restore, not another initialization or backup.

Unknown ownership, changed independent state, missing verified preimages or
unavailable ownership are conflicts. An older pending receipt created before
preimage protection cannot establish safe abandonment; resume its original
input if possible. Do not manually delete generated declarations or stores
on the assumption that they belong to a failed operation.

## Integrity and compatibility

Both artifact classes verify:

- manifest integrity;
- file size and SHA-256;
- SQLite integrity;
- recorded schema identity; and
- the highest retained conclusion revision.

For the Beta-3 line, the current repository lifecycle schema is **15**.
A repository-portable artifact must contain schema 15 to load directly.

Repository schemas 7 through 14 are supported as **offline transition sources**,
not as direct Beta-3 repository-backup loads. Follow
[Install and connect — Upgrade an existing store](install.md#upgrade-an-existing-store)
before treating an older store as current.

The installation Functional Pyramid database has its own schema identity and is
verified independently from repository lifecycle databases.

## What verification proves

A verified backup proves that the artifact matches its manifest and that its
databases pass the defined integrity/compatibility checks.

It does not prove that every retained semantic conclusion is correct. After a
restore or repository deployment, normal Span support checks still determine
whether retained knowledge remains reusable against the current repository.

For audit, retain the artifact's own `manifest.json` and a sanitized recovery
summary where the operation needs to be recorded.

Full data-directory artifacts remain outside Git. Repository-portable artifacts
are designed to be committed when appropriate.

## When to take a backup

Take a **repository-portable backup** when retained Span knowledge needs to
travel with the repository.

Take a **full installation backup**:

- before a destructive installation change;
- before a repository store transition;
- before restoring another artifact; or
- whenever your installation recovery policy requires one.

The operator owns backup retention. Span keeps no remote/server-side copy of
these artifacts.
