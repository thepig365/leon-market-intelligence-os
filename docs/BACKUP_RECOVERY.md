# Backup and Recovery

SQLite is the local development procedure. Production uses the approved
Supabase project and must follow the managed export/recovery procedure below.

## Backup

1. Record the application commit SHA.
2. Run the consistent SQLite backup command to a new timestamped path:

   ```bash
   uv run python -m lmio.cli backup --file /approved/backup/path/lmio.sqlite3
   ```

3. Preserve the returned hash, byte size, schema versions, record counts and
   integrity result with the operating evidence.
4. Store the new file in an access-controlled location outside the working
   database path.
5. Keep the source database until the backup is independently verified.

The command uses SQLite's online backup API and refuses to overwrite an
existing file or use the active database as its destination.

Never commit a database, credential, portfolio context or private research
record to Git.

## Recovery rehearsal

1. Work in an isolated temporary directory.
2. Copy, never move, the selected backup.
3. Verify its recorded hash.
4. Run SQLite integrity verification.
5. Start the matching LMIO commit against the recovered copy.
6. Check `/health`, `/ready`, record counts and the latest report timestamp.
7. Run the replay and automated tests without touching the original store.
8. Record the rehearsal result.

## Incident recovery

If the active store is corrupted, stop writers and preserve it as evidence.
Restore only from a verified copy after Leon approves replacement of the active
store. Do not merge partially recovered records into permanent history without
a documented reconciliation.

No untested recovery time or data-loss guarantee is claimed by V1.

## Supabase production procedure

1. Confirm the project backup/export feature available on the current plan
   without purchasing an upgrade.
2. Before each schema change, export only the `lmio_*` tables and record the
   application commit and migration version.
3. Verify the export is readable in an isolated environment; never overwrite
   the active tables as a test.
4. For an incident, stop LMIO writers, preserve the affected rows, and restore
   into isolated replacement tables first.
5. Compare counts, schema version, latest timestamps and representative
   payloads before Leon approves any cutover.
6. Keep Bayview OS project memory separate from LMIO runtime recovery.

If the existing Supabase plan does not provide the required backup capability,
the runtime remains review-only until a no-cost export process is proven or
Leon separately approves a paid recovery option.
