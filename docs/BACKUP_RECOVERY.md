# Backup and Recovery

This is the local V1 procedure for the versioned SQLite runtime store. A
production PostgreSQL/Supabase procedure must be approved and tested against
the selected deployment before it replaces this document.

## Backup

1. Stop the LMIO process or otherwise ensure no writer is active.
2. Record the application commit SHA and database migration version.
3. Create a timestamped copy of `LMIO_DATABASE_PATH` in an access-controlled
   backup location outside the working database path.
4. Hash the backup and record its byte size.
5. Open the copy read-only and run SQLite integrity verification.
6. Keep the source database until the backup is independently verified.

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
