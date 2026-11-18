-- Persistent Overview inputs, separate from next-day forecast snapshots.
begin;

create table if not exists public.solarcast_prediction_inputs (
    id bigint generated always as identity primary key,
    snapshot_key text not null unique check (snapshot_key ~ '^[a-f0-9]{64}$'),
    predicted_at timestamptz not null,
    weather_fetched_at timestamptz not null,
    latitude double precision not null check (latitude between -90 and 90),
    longitude double precision not null check (longitude between -180 and 180),
    input_features jsonb not null check (
        jsonb_typeof(input_features) = 'object'
        and input_features ?& array['IRRADIATION', 'AMBIENT_TEMPERATURE', 'MODULE_TEMPERATURE',
                                   'HOUR', 'MINUTE', 'DAY', 'MONTH', 'DAY_OF_WEEK']
    ),
    predicted_ac_power double precision not null
        check (predicted_ac_power >= 0 and predicted_ac_power < 'Infinity'::float8)
);

create index if not exists solarcast_prediction_inputs_location_time_idx
    on public.solarcast_prediction_inputs (latitude, longitude, predicted_at desc, id desc);

alter table public.solarcast_prediction_inputs enable row level security;
revoke all on public.solarcast_prediction_inputs from public, anon, authenticated, service_role;
grant select, insert on public.solarcast_prediction_inputs to service_role;
grant usage, select on sequence public.solarcast_prediction_inputs_id_seq to service_role;

commit;
