-- LMIO schema version 12: run-lineage records use the existing private,
-- service-role-only lmio_records store. No market rows or secrets are exposed.

insert into public.lmio_schema_versions(version)
values (12)
on conflict (version) do nothing;
