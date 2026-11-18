begin;

create table public.solarcast_account_predictions (
    id bigint generated always as identity primary key,
    owner_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
    snapshot_key text not null,
    source text not null check (source in ('Overview', 'Manual prediction')),
    predicted_for timestamptz not null,
    saved_at timestamptz not null default now(),
    sunlight double precision not null check (sunlight >= 0 and sunlight < 'Infinity'::float8),
    air_temperature double precision not null check (abs(air_temperature) < 'Infinity'::float8),
    panel_temperature double precision not null check (abs(panel_temperature) < 'Infinity'::float8),
    predicted_power double precision not null check (predicted_power >= 0 and predicted_power < 'Infinity'::float8),
    unique (owner_id, snapshot_key)
);

create index solarcast_account_predictions_history_idx
    on public.solarcast_account_predictions (owner_id, saved_at desc, id desc);

alter table public.solarcast_account_predictions enable row level security;
revoke all on public.solarcast_account_predictions from public, anon, authenticated, service_role;
revoke all on sequence public.solarcast_account_predictions_id_seq from public, anon, authenticated, service_role;
grant select, insert on public.solarcast_account_predictions to authenticated;
grant usage on sequence public.solarcast_account_predictions_id_seq to authenticated;

create policy "Read own predictions" on public.solarcast_account_predictions
    for select to authenticated using ((select auth.uid()) = owner_id);

create policy "Insert own predictions" on public.solarcast_account_predictions
    for insert to authenticated with check ((select auth.uid()) = owner_id);

commit;
