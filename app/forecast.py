"""Next-day weather-driven estimates for the existing inverter model."""

from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd
import requests
import streamlit as st

from config import LATITUDE, LONGITUDE, MODEL_PATH, MODULE_MODEL_PATH
from forecast_store import save_forecast
from model_loader import model, module_temp_model

LOCAL_TIME = timezone(timedelta(hours=8))
FEATURES = ["IRRADIATION", "AMBIENT_TEMPERATURE", "MODULE_TEMPERATURE",
            "HOUR", "MINUTE", "DAY", "MONTH", "DAY_OF_WEEK"]


@st.cache_data(show_spinner=False)
def model_version(power_bytes, temperature_bytes):
    return "forecast-v1:" + hashlib.sha256(power_bytes + temperature_bytes).hexdigest()


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_forecast(day, latitude, longitude):
    response = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={"latitude": latitude, "longitude": longitude,
                "hourly": "temperature_2m,shortwave_radiation",
                "temperature_unit": "celsius", "timezone": "Asia/Manila",
                "start_date": day.isoformat(),
                "end_date": (day + timedelta(days=1)).isoformat()},
        timeout=(3, 15),
    )
    response.raise_for_status()
    return response.json(), datetime.now(LOCAL_TIME).isoformat()


def predict_forecast(payload, day, power_model, temperature_model, power_unit="kW"):
    """Use hour-ending radiation, including the next midnight, for 24 intervals."""
    if power_unit not in ("kW", "W"):
        raise ValueError("Power unit must be kW or W.")
    units = payload["hourly_units"]
    if units["temperature_2m"] != "°C" or units["shortwave_radiation"] != "W/m²":
        raise ValueError("Unexpected weather units.")
    hourly = payload["hourly"]
    frame = pd.DataFrame({
        "end": pd.to_datetime(hourly["time"]),
        "temperature": hourly["temperature_2m"],
        "radiation": hourly["shortwave_radiation"],
    }).set_index("end")
    expected = pd.date_range(pd.Timestamp(day) + pd.Timedelta(hours=1), periods=24, freq="h")
    if frame.index.has_duplicates:
        raise ValueError("Weather contains duplicate hours.")
    frame = frame.reindex(expected)
    if not np.isfinite(frame.to_numpy(dtype=float)).all() or (frame.radiation < 0).any():
        raise ValueError("The forecast is incomplete. Please retry later.")
    # Training examples use irradiation around 0–1 (kW/m²).
    weather = pd.DataFrame({"IRRADIATION": frame.radiation.to_numpy() / 1000,
                            "AMBIENT_TEMPERATURE": frame.temperature.to_numpy()})
    midpoint = expected - pd.Timedelta(minutes=30)
    features = weather.assign(
        MODULE_TEMPERATURE=temperature_model.predict(weather),
        HOUR=midpoint.hour, MINUTE=midpoint.minute, DAY=midpoint.day,
        MONTH=midpoint.month, DAY_OF_WEEK=midpoint.day_of_week,
    )[FEATURES]
    power = np.asarray(power_model.predict(features), dtype=float)
    if not np.isfinite(power).all():
        raise ValueError("The model returned invalid predictions.")
    power = np.maximum(power, 0) / (1000 if power_unit == "W" else 1)
    power[frame.radiation.to_numpy() == 0] = 0
    return pd.DataFrame({
        "Hour starting (Asia/Manila)": expected - pd.Timedelta(hours=1),
        "Estimated power (kW)": power,
        "Estimated energy (kWh)": power,  # Each interval is exactly one hour.
        "Ambient temperature (°C)": frame.temperature.to_numpy(),
        "Solar irradiance (W/m²)": frame.radiation.to_numpy(),
    })


def render_forecast():
    day = datetime.now(LOCAL_TIME).date() + timedelta(days=1)
    st.title("Next-day forecast")
    st.caption(f"{day:%A, %d %B %Y} · Asia/Manila · {LATITUDE:.4f}, {LONGITUDE:.4f}")
    st.write("Tomorrow's expected solar production, based on forecast sunlight and temperature.")
    st.info("Experimental estimate for one inverter represented by the training data, "
            "not total plant output. The model has not been validated for this location.")
    with st.expander("Forecast assumptions"):
        unit = st.selectbox("Training AC_POWER unit", ["kW", "W"], key="forecast_unit")
        st.caption("Default assumes AC_POWER is kW and training IRRADIATION is kW/m². "
                   "Confirm these against your dataset documentation. Energy is an approximation "
                   "using one predicted average power value per hour; no confidence interval is available.")
    if st.button("Refresh forecast", key="refresh_forecast"):
        fetch_forecast.clear()
    try:
        with st.spinner("Checking tomorrow's weather..."):
            payload, fetched = fetch_forecast(day, LATITUDE, LONGITUDE)
            forecast = predict_forecast(payload, day, model, module_temp_model, unit)
    except (requests.RequestException, ValueError, KeyError, TypeError, IndexError):
        st.warning("Tomorrow's forecast is unavailable or incomplete. Please refresh or try again later.")
        return
    try:
        version = model_version(Path(MODEL_PATH).read_bytes(), Path(MODULE_MODEL_PATH).read_bytes())
        run_id = save_forecast(forecast, day, fetched, LATITUDE, LONGITUDE, unit, version)
        st.caption(f"Saved to Forecast history · version #{run_id}. Reopening this forecast will not create duplicates.")
    except (sqlite3.Error, OSError, ValueError):
        st.warning("The forecast is ready but could not be saved. Check database access and refresh to retry.")
    peak = forecast.loc[forecast["Estimated power (kW)"].idxmax()]
    positive = peak["Estimated power (kW)"] > 0
    start = peak["Hour starting (Asia/Manila)"]
    energy_col, power_col, time_col = st.columns(3)
    energy_col.metric("Estimated daily energy", f'{forecast["Estimated energy (kWh)"].sum():,.1f} kWh')
    power_col.metric("Peak hourly power", f'{peak["Estimated power (kW)"]:,.1f} kW')
    time_col.metric("Peak production hour", f"{start:%H:%M}–{start + timedelta(hours=1):%H:%M}" if positive else "No generation")
    st.line_chart(forecast.set_index("Hour starting (Asia/Manila)")[["Estimated power (kW)"]])
    st.caption("Each point estimates the average power for the hour starting at that time.")
    with st.expander("Hourly forecast details"):
        st.dataframe(forecast, hide_index=True, use_container_width=True)
    st.download_button("Download forecast CSV", forecast.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"solarcast-forecast-{day}.csv", mime="text/csv")
    st.caption(f"Weather retrieved {datetime.fromisoformat(fetched):%d %b %Y, %H:%M} Asia/Manila. "
               "Cached for 30 minutes; weather forecasts can change.")
    st.markdown("Weather: [Open-Meteo](https://open-meteo.com/) · "
                "[Forecast documentation](https://open-meteo.com/en/docs)")
