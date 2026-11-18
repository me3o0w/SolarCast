"""One saved version per weather hour, forecast date, location and assumptions."""

import hashlib
import json

import pandas as pd


def saved_version_name(fetched, run_id):
    """Name an hourly forecast update by its local time of day."""
    fetched = pd.Timestamp(fetched)
    if pd.isna(fetched) or fetched.tzinfo is None:
        raise ValueError("The forecast update time must include its timezone.")
    local = fetched.tz_convert("Asia/Manila")
    if 5 <= local.hour < 12:
        period = "Morning"
    elif 12 <= local.hour < 17:
        period = "Afternoon"
    elif 17 <= local.hour < 21:
        period = "Evening"
    else:
        period = "Night"
    hour = local.strftime("%I %p").lstrip("0")
    return f"{period} forecast - {local:%d %b %Y}, {hour} (#{int(run_id)})"


def display_forecast(frame):
    """Clean visible labels while supporting previously saved hourly data."""
    return frame.rename(columns={
        "Hour starting (Asia/Manila)": "Hour starting",
        "Hour ending (Asia/Manila)": "Hour ending",
    })


def hourly_slot(day, fetched, latitude, longitude, unit, model_version):
    fetched = pd.Timestamp(fetched)
    if pd.isna(fetched) or fetched.tzinfo is None:
        raise ValueError("The weather retrieval time must include its timezone.")
    start = fetched.tz_convert("UTC").floor("h")
    end = start + pd.Timedelta(hours=1)
    metadata = ["hourly-v1", str(day), start.isoformat(), float(latitude), float(longitude), unit, model_version]
    key = hashlib.sha256(json.dumps(metadata).encode()).hexdigest()
    return key, start, end


def hourly_versions(runs):
    """Keep the first stored version in each hour, including legacy snapshots."""
    if runs.empty:
        return runs.copy()
    ordered = runs.assign(
        _hour=pd.to_datetime(runs.weather_fetched_at, utc=True).dt.floor("h"),
        _fetched=pd.to_datetime(runs.weather_fetched_at, utc=True),
        _saved=pd.to_datetime(runs.saved_at, utc=True),
    ).sort_values(["_saved", "id"])
    return ordered.drop_duplicates(
        ["target_date", "latitude", "longitude", "training_power_unit", "model_version", "_hour"], keep="first"
    ).sort_values(["target_date", "_fetched", "id"], ascending=False).drop(columns=["_hour", "_fetched", "_saved"]).reset_index(drop=True)
