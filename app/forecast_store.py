"""Persistent forecast snapshots. SQLite is included with Python."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

import pandas as pd

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


def save_forecast(frame, day, fetched, latitude, longitude, unit, model_version, path=DB_PATH):
    if len(frame) != 24:
        raise ValueError("Only complete 24-hour forecasts can be saved.")
    hourly = frame.to_json(orient="table", date_format="iso", index=False)
    metadata = [str(day), fetched, latitude, longitude, unit, model_version, hourly]
    key = hashlib.sha256(json.dumps(metadata).encode()).hexdigest()
    with connect(path) as db:
        db.execute("""INSERT OR IGNORE INTO forecast_runs
            (snapshot_key, target_date, saved_at, weather_fetched_at, latitude, longitude,
             training_power_unit, model_version, daily_energy_kwh, peak_power_kw, hourly_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (key, str(day), datetime.now(timezone.utc).isoformat(), fetched, latitude, longitude,
             unit, model_version, float(frame["Estimated energy (kWh)"].sum()),
             float(frame["Estimated power (kW)"].max()), hourly))
        return db.execute("SELECT id FROM forecast_runs WHERE snapshot_key = ?", (key,)).fetchone()[0]


def list_forecasts(path=DB_PATH):
    with connect(path) as db:
        return pd.read_sql_query("""SELECT id, target_date, weather_fetched_at, saved_at,
            latitude, longitude, training_power_unit, model_version,
            daily_energy_kwh, peak_power_kw FROM forecast_runs
            ORDER BY target_date DESC, weather_fetched_at DESC, id DESC""", db)


def load_forecast(run_id, path=DB_PATH):
    from io import StringIO
    with connect(path) as db:
        row = db.execute("SELECT hourly_json FROM forecast_runs WHERE id = ?", (int(run_id),)).fetchone()
    if row is None:
        raise ValueError("Forecast was not found.")
    return pd.read_json(StringIO(row[0]), orient="table")
