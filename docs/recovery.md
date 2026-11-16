# Backup and recovery

Span stores its retained understanding in a SQLite data directory outside any
target repository. This page is the canonical policy and operator runbook for
protecting that directory: what a recovery artifact contains, how to verify it,
how to restore it, and what Span deliberately does not back up.

## What is recoverable state

A recovery artifact holds the state Span cannot regenerate:

| Included | Why |
| --- | --- |
| every top-level `*.db` | conclusions, support, observations, surfaces, repository bindings |
| `install.json` | registered repositories and host registration |
| `structural-indexer.json` | managed indexer pointer |
| `manifest.json`, `manifest.sha256` | artifact identity and database facts |

Two data-directory trees are excluded, and the manifest records why:

| Excluded | Reason |
| --- | --- |
| `structural/` | a regenerable structural index; the installer rebuilds it from the target tree |
| `transitions/` | rollback archives of superseded stores; the transition command owns that path |

Excluding the structural index means a restored installation may re-index. That
is a rebuild, not lost understanding.

## Storage

Artifacts default to `<DATA_DIR>/backups/<UTC-timestamp>/`. Use
`--backup-root DIR` to place them on a different filesystem. A backup stored
inside the data directory does not survive loss of that directory, so keep at
least one copy elsewhere.

Artifacts are operator data, never Git content. Do not commit artifact
directories, raw restore captures, or verification transcripts. Report a
sanitized verification summary — artifact identity, schema, recovered
revisions — in release notes when a change needs recovery evidence.

Owner: the operator of this Span installation. Span is local and keeps no
server-side copy, so the recovery window is a property of the operator's change
and release process, not of this repository.

## Commands

```bash
# Take a verified artifact and print its path.
span-install --data-dir <DATA_DIR> --backup [--backup-root <DIR>]

# Verify identity, integrity and schema compatibility without changing state.
span-install --verify-backup <BACKUP_DIR>

# Restore one verified artifact. The confirmation repeats the directory name.
span-install --data-dir <DATA_DIR> \
  --restore-backup <BACKUP_DIR> --restore-confirm <BACKUP_DIR basename>

# Delete all but the newest KEEP recognized artifacts.
span-install --data-dir <DATA_DIR> --reap-backups <KEEP> [--backup-root <DIR>]
```

`--backup` uses the SQLite online backup API, so it is consistent under
concurrent readers. The installer also takes this backup immediately before a
reinstall mutation; the command exposes the same writer to the operator.

`--verify-backup` checks the manifest digest, every artifact's size and SHA-256,
each database's `PRAGMA integrity_check`, its `meta.schema_version`, and its
highest conclusion revision. It exits non-zero when any check fails.

## When to take one

- before any destructive change to the data directory, not only reinstalls;
- before a schema transition, in addition to the transition archive;
- at the boundary of a change that deletes or rewrites retained understanding,
  so the artifact covers the exact revisions the change relies on;
- before restoring, because the restore command snapshots the current directory
  automatically.

A backup taken at a different time does not prove coverage for a later change.

## Retention and reaping

Default policy: retain every artifact. Span never deletes a backup on its own.
There is no age threshold and no default retention interval, because the useful
recovery window is an operator decision that Span cannot observe.

`--reap-backups KEEP` is explicit and requires the count. It deletes only
directories carrying a valid Span manifest; any other directory is reported and
left untouched. Reaping a corrupt artifact is harmless, but reaping is still
only performed on request.

## Restore procedure

1. Stop every Span server and hook. The restore takes SQLite exclusive
   ownership of each store and refuses while a live connection holds one.
2. Verify the artifact with `--verify-backup` and record the manifest digest.
3. Restore into a disposable directory first:

   ```bash
   span-install --data-dir /tmp/span-restore-check \
     --restore-backup <BACKUP_DIR> --restore-confirm <name>
   span-install --data-dir /tmp/span-restore-check --verify-only
   ```

4. Request one recorded surface through the supported lifecycle
   (`ask`) and confirm the status reflects the restored revisions. A changed or
   missing source must produce a non-current result, not an unjustified current
   answer.
5. Only then restore into the live data directory. The command snapshots the
   current directory as a `pre-restore` artifact before replacing anything, and
   removes stale `-wal`, `-shm` and `-journal` files for each restored
   database.
6. Record the artifact identity, verify result, restored revisions and
   read-back result alongside the change that needed recovery.

The durable verification record is the artifact's own `manifest.json` plus a
sanitized summary in the change record that required recovery: manifest
digest, restored revisions, isolated target, and the lifecycle read-back
result. Keep the artifact directory out of Git; a summary is sufficient evidence
and the artifact itself is operator data.

## Compatibility

The current store schema is 11. An artifact holding schema 11 restores directly.
Schemas 7–10 are accepted as transition sources; after restoring one, run the
documented offline transition before use, as the restore output instructs.
Anything else fails verification and is not restorable.

The manifest records the installer version, the running Span code version (or
`null` when the package cannot be imported), and each database's schema version,
so compatibility is a recorded fact rather than an assumption about the
artifact's age. The manifest is a versioned typed carrier: an unknown format or
an unknown key is rejected instead of interpreted.
