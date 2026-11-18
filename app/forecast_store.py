"""Forecast snapshots in Supabase, with SQLite for unconfigured local use."""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

import pandas as pd

from supabase_store import StoreError, SUMMARY_COLUMNS, configured_store
from forecast_versions import hourly_slot, hourly_versions

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "solarcast.db"


@contextmanager
def connect(path=DB_PATH):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    try:
        connection.execute("""CREATE TABLE IF NOT EXISTS forecast_runs (
            id INTEGER PRIMARY KEY,
            snapshot_key TEXT NOT NULL UNIQUE,
            target_date TEXT NOT NULL,
            saved_at TEXT NOT NULL,
            weather_fetched_at TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            training_power_unit TEXT NOT NULL,
            model_version TEXT NOT NULL,
            daily_energy_kwh REAL NOT NULL,
            peak_power_kw REAL NOT NULL,
            hourly_json TEXT NOT NULL
        )""")
        with connection:
            yield connection
    finally:
        connection.close()


def _selected_store(path, store):
    if path is not None:
        return None
    return configured_store() if store is None else store


def save_forecast(frame, day, fetched, latitude, longitude, unit, model_version, path=None, *, store=None):
    if len(frame) != 24:
        raise ValueError("Only complete 24-hour forecasts can be saved.")
    hourly = frame.to_json(orient="table", date_format="iso", index=False)
    key, hour_start, _ = hourly_slot(day, fetched, latitude, longitude, unit, model_version)
    saved_at = datetime.now(timezone.utc).isoformat()
    store = _selected_store(path, store)
    if store is not None:
        return store.save({
            "snapshot_key": key, "target_date": str(day), "saved_at": saved_at,
            "weather_fetched_at": fetched, "latitude": latitude, "longitude": longitude,
            "training_power_unit": unit, "model_version": model_version,
            "daily_energy_kwh": float(frame["Estimated energy (kWh)"].sum()),
            "peak_power_kw": float(frame["Estimated power (kW)"].max()), "hourly_json": hourly,
        })
    with connect(DB_PATH if path is None else path) as db:
        # Honor snapshots saved before hourly keys were introduced, too.
        existing = db.execute("""SELECT id, weather_fetched_at FROM forecast_runs
            WHERE target_date = ? AND latitude = ? AND longitude = ?
                AND training_power_unit = ? AND model_version = ?
            ORDER BY saved_at ASC, id ASC""", (str(day), latitude, longitude, unit, model_version))
        for run_id, weather_time in existing:
            if pd.Timestamp(weather_time).tz_convert("UTC").floor("h") == hour_start:
                return run_id
        db.execute("""INSERT OR IGNORE INTO forecast_runs
            (snapshot_key, target_date, saved_at, weather_fetched_at, latitude, longitude,
             training_power_unit, model_version, daily_energy_kwh, peak_power_kw, hourly_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (key, str(day), saved_at, fetched, latitude, longitude,
             unit, model_version, float(frame["Estimated energy (kWh)"].sum()),
             float(frame["Estimated power (kW)"].max()), hourly))
        return db.execute("SELECT id FROM forecast_runs WHERE snapshot_key = ?", (key,)).fetchone()[0]


def list_forecasts(path=None, *, store=None):
    store = _selected_store(path, store)
    if store is not None:
        return hourly_versions(pd.DataFrame(store.list(), columns=SUMMARY_COLUMNS))
    with connect(DB_PATH if path is None else path) as db:
        runs = pd.read_sql_query("""SELECT id, target_date, weather_fetched_at, saved_at,
            latitude, longitude, training_power_unit, model_version,
            daily_energy_kwh, peak_power_kw FROM forecast_runs
            ORDER BY target_date DESC, weather_fetched_at DESC, id DESC""", db)
    return hourly_versions(runs)


def load_forecast(run_id, path=None, *, store=None):
    from io import StringIO
    store = _selected_store(path, store)
    if store is not None:
        return pd.read_json(StringIO(store.load(run_id)), orient="table")
    with connect(DB_PATH if path is None else path) as db:
        row = db.execute("SELECT hourly_json FROM forecast_runs WHERE id = ?", (int(run_id),)).fetchone()
    if row is None:
        raise ValueError("Forecast was not found.")
    return pd.read_json(StringIO(row[0]), orient="table")


def storage_description():
    if configured_store() is not None:
        return "Forecast history is stored in Supabase."
    return f"Stored locally in {DB_PATH}. Back up this file to keep your history."
