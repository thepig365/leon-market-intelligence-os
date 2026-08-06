-- LMIO schema version 10: atomic Telegram outbox claims and scheduler evidence.

alter table public.lmio_telegram_deliveries
    add column if not exists claim_token text,
    add column if not exists claimed_at timestamptz;

create or replace function public.lmio_claim_telegram_deliveries(
    p_claim_token text,
    p_limit integer,
    p_max_attempts integer
)
returns table(dedupe_key text, payload jsonb, attempt_count integer)
language plpgsql
security definer
set search_path = public
as $$
begin
  return query
  with claimed as (
    select delivery.dedupe_key
    from public.lmio_telegram_deliveries delivery
    where delivery.status in ('queued_not_configured', 'failed', 'suppressed_rate_limit')
      and delivery.attempt_count < p_max_attempts
    order by delivery.created_at asc
    for update skip locked
    limit greatest(1, least(p_limit, 50))
  ), updated as (
    update public.lmio_telegram_deliveries delivery
    set status = 'claimed',
        claim_token = p_claim_token,
        claimed_at = now()
    from claimed
    where delivery.dedupe_key = claimed.dedupe_key
    returning delivery.dedupe_key, delivery.payload, delivery.attempt_count
  )
  select updated.dedupe_key, updated.payload, updated.attempt_count from updated;
end;
$$;

revoke all on function public.lmio_claim_telegram_deliveries(text, integer, integer)
from public, anon, authenticated;
grant execute on function public.lmio_claim_telegram_deliveries(text, integer, integer)
to service_role;

insert into public.lmio_schema_versions(version)
values (10)
on conflict (version) do nothing;
