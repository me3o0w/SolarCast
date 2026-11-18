-- Preserve the old shared archive without assigning its rows to any account.
begin;

create table public.solarcast_account_forecast_runs (
    like public.solarcast_forecast_runs including defaults including constraints including identity,
    owner_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
    primary key (id),
    unique (owner_id, snapshot_key)
);

create index solarcast_account_forecast_runs_history_idx
    on public.solarcast_account_forecast_runs
    (owner_id, target_date desc, weather_fetched_at desc, id desc);

alter table public.solarcast_account_forecast_runs enable row level security;

revoke all on public.solarcast_account_forecast_runs from public, anon, authenticated, service_role;
revoke all on sequence public.solarcast_account_forecast_runs_id_seq
    from public, anon, authenticated, service_role;
grant select, insert on public.solarcast_account_forecast_runs to authenticated;
grant usage on sequence public.solarcast_account_forecast_runs_id_seq to authenticated;

create policy "Read own forecasts" on public.solarcast_account_forecast_runs
    for select to authenticated
    using ((select auth.uid()) = owner_id);

create policy "Insert own forecasts" on public.solarcast_account_forecast_runs
    for insert to authenticated
    with check ((select auth.uid()) = owner_id);

commit;
