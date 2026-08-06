-- LMIO schema version 11: news/price confirmations use the existing private record store.

insert into public.lmio_schema_versions(version)
values (11)
on conflict (version) do nothing;
