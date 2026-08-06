-- LMIO schema version 9: canonical pipeline evidence uses the existing
-- service-role-only generic record store. No browser role receives access.

insert into public.lmio_schema_versions(version)
values (9)
on conflict (version) do nothing;
