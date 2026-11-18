-- Supabase default grants can give service_role all table privileges.
-- Forecast snapshots are append-only; the app only needs read and insert.
revoke all on public.solarcast_forecast_runs from service_role;
grant select, insert on public.solarcast_forecast_runs to service_role;
