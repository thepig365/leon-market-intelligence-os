-- Count the research-only option records stored in the existing isolated table.
-- No order, account, balance or position table is introduced.

create or replace function public.lmio_runtime_counts()
returns jsonb
language sql
stable
security definer
set search_path = public
as $$
  select jsonb_build_object(
    'universe_runs', count(*) filter (where kind = 'universe_runs'),
    'screen_runs', count(*) filter (where kind = 'screen_runs'),
    'valuation_runs', count(*) filter (where kind = 'valuation_runs'),
    'news_events', (select count(*) from public.lmio_news_events),
    'reports', count(*) filter (where kind = 'reports'),
    'signal_outcomes', count(*) filter (where kind = 'signal_outcomes'),
    'telegram_deliveries', (select count(*) from public.lmio_telegram_deliveries),
    'system_events', count(*) filter (where kind = 'system_events'),
    'ai_usage', count(*) filter (where kind = 'ai_usage'),
    'research_packs', count(*) filter (where kind = 'research_packs'),
    'conditional_plans', count(*) filter (where kind = 'conditional_plans'),
    'provider_health', count(*) filter (where kind = 'provider_health'),
    'symbols', (select count(*) from public.lmio_symbols),
    'provider_snapshots', count(*) filter (where kind = 'provider_snapshots'),
    'candidate_transitions', count(*) filter (where kind = 'candidate_transitions'),
    'trade_plan_transitions', count(*) filter (where kind = 'trade_plan_transitions'),
    'ownership_events', count(*) filter (where kind = 'ownership_events'),
    'signals', count(*) filter (where kind = 'signals'),
    'user_feedback', count(*) filter (where kind = 'user_feedback'),
    'strategy_performance', count(*) filter (where kind = 'strategy_performance'),
    'watchlists', count(*) filter (where kind = 'watchlists'),
    'watchlist_members', count(*) filter (where kind = 'watchlist_members'),
    'top3_evaluations', count(*) filter (where kind = 'top3_evaluations'),
    'pipeline_runs', count(*) filter (where kind = 'pipeline_runs'),
    'pipeline_stages', count(*) filter (where kind = 'pipeline_stages'),
    'news_price_confirmations', count(*) filter (where kind = 'news_price_confirmations'),
    'top10_rankings', count(*) filter (where kind = 'top10_rankings'),
    'valuation_input_records', count(*) filter (where kind = 'valuation_input_records'),
    'operational_lineage', count(*) filter (where kind = 'operational_lineage'),
    'market_regimes', count(*) filter (where kind = 'market_regimes'),
    'options_flow', count(*) filter (where kind = 'options_flow')
  )
  from public.lmio_records;
$$;

revoke all on function public.lmio_runtime_counts() from public, anon, authenticated;
grant execute on function public.lmio_runtime_counts() to service_role;

insert into public.lmio_schema_versions(version)
values (13)
on conflict (version) do nothing;
