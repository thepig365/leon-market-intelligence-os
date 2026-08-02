-- Report RLS configuration honestly without equating it to data integrity.

create or replace function public.lmio_rls_check()
returns jsonb
language sql
security definer
set search_path = public
as $$
  select jsonb_build_object(
    'status', case when bool_and(c.relrowsecurity) then 'ok' else 'failed' end,
    'tables_checked', count(*),
    'rls_enabled', count(*) filter (where c.relrowsecurity)
  )
  from pg_class c
  join pg_namespace n on n.oid = c.relnamespace
  where n.nspname = 'public'
    and c.relkind = 'r'
    and c.relname like 'lmio\_%' escape '\';
$$;

revoke all on function public.lmio_rls_check() from public, anon, authenticated;
grant execute on function public.lmio_rls_check() to service_role;

insert into public.lmio_schema_versions(version)
values (8)
on conflict (version) do nothing;
