# Migration Verification Report

## Scope

Migrations `007_provenance_isolation.sql` through
`012_operational_lineage.sql` were reviewed against the generic private LMIO
record store and schema-version chain.

## Confirmed locally

- a new isolated SQLite store reaches schema versions 1–12;
- schema version 12 is required by the Supabase store health check;
- migrations are additive and contain no destructive table drop;
- Telegram claim function privileges are revoked from public, anonymous and
  authenticated roles and granted only to `service_role`;
- local backup refuses overwrite, records a digest and passes integrity checks;
- restore rehearsal tests operate on an isolated target and preserve the source.

Fresh RC1 rehearsal evidence was produced on 2 August 2026 in a disposable
local directory. The isolated database reported schema version 12, the backup
contained 352,256 bytes, its integrity check returned `ok`, and its SHA-256
digest was recorded by the backup command. The rehearsal ran with
`synthetic_replay` data and confirmed that trading remained disabled. The
temporary path and digest are operational evidence only; they are not a
production backup and are intentionally not committed to the repository.

## Protected Supabase status

`awaiting_isolated_supabase_target`

No approved isolated Supabase target and no fresh usable production backup were
available to this run. Therefore migrations 007–012 were **not** applied to the
protected production project. RLS, RPC privileges and schema version 12 must be
verified in an isolated Supabase target before production migration. This is a
truthful pending gate, not a failed migration.

## Production gate

Before any protected migration: create and verify a logical export, confirm the
target project, apply 007–012 in order, verify `lmio_schema_versions`, RLS,
anonymous/authenticated denial, service-role access and rollback evidence. Leon
must separately approve the protected action.
