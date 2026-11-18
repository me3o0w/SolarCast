-- Server-managed forecast history. No public read/write policies are created.
begin;

create table if not exists public.solarcast_forecast_runs (
    id bigint generated always as identity primary key,
    snapshot_key text not null unique check (snapshot_key ~ '^[a-f0-9]{64}$'),
    target_date date not null,
    saved_at timestamptz not null default now(),
    weather_fetched_at timestamptz not null,
    latitude double precision not null check (latitude between -90 and 90),
    longitude double precision not null check (longitude between -180 and 180),
    training_power_unit text not null check (training_power_unit in ('kW', 'W')),
    model_version text not null,
    daily_energy_kwh double precision not null check (daily_energy_kwh >= 0 and daily_energy_kwh < 'Infinity'::float8),
    peak_power_kw double precision not null check (peak_power_kw >= 0 and peak_power_kw < 'Infinity'::float8),
    hourly_json jsonb not null check (
        hourly_json ? 'data'
        and jsonb_typeof(hourly_json -> 'data') = 'array'
        and jsonb_array_length(hourly_json -> 'data') = 24
    )
);

create index if not exists solarcast_forecast_runs_history_idx
    on public.solarcast_forecast_runs (target_date desc, weather_fetched_at desc, id desc);

alter table public.solarcast_forecast_runs enable row level security;
revoke all on public.solarcast_forecast_runs from public, anon, authenticated, service_role;
grant select, insert on public.solarcast_forecast_runs to service_role;
grant usage, select on sequence public.solarcast_forecast_runs_id_seq to service_role;

commit;
