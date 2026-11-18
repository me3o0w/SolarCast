"""Next-day weather-driven estimates for the existing inverter model."""

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import requests
import streamlit as st

from config import LATITUDE, LONGITUDE
from loading import PageLoading
from model_loader import model, module_temp_model
from weather_client import get_weather_json
from forecast_versions import display_forecast

LOCAL_TIME = timezone(timedelta(hours=8))
FEATURES = ["IRRADIATION", "AMBIENT_TEMPERATURE", "MODULE_TEMPERATURE",
            "HOUR", "MINUTE", "DAY", "MONTH", "DAY_OF_WEEK"]


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_forecast(day, latitude, longitude):
    payload = get_weather_json(
        "https://api.open-meteo.com/v1/forecast",
        params={"latitude": latitude, "longitude": longitude,
                "hourly": "temperature_2m,shortwave_radiation",
                "temperature_unit": "celsius", "timezone": "Asia/Manila",
                "start_date": day.isoformat(),
                "end_date": (day + timedelta(days=1)).isoformat()},
    )
    return payload, datetime.now(LOCAL_TIME).isoformat()


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
    st.caption(f"{day:%A, %d %B %Y}")
    with st.container(border=True):
        st.subheader("Forecast settings")
        settings, refresh = st.columns([3, 1], vertical_alignment="bottom")
        with settings:
            with st.expander("Forecast assumptions"):
                unit = st.selectbox("Training AC_POWER unit", ["kW", "W"], key="forecast_unit")
                st.caption("Irradiation: kW/m². Energy uses hourly average power.")
        with refresh:
            refresh_requested = st.button("Refresh forecast", key="refresh_forecast", use_container_width=True)
    st.caption("Experimental estimate for one inverter; not validated for this location.")
    if refresh_requested:
        loading = PageLoading("Next-day forecast", message="Refreshing tomorrow’s solar outlook")
    else:
        loading = st.spinner("Checking tomorrow's weather...")
    try:
        with loading:
            if refresh_requested:
                fetch_forecast.clear()
            payload, fetched = fetch_forecast(day, LATITUDE, LONGITUDE)
            forecast = predict_forecast(payload, day, model, module_temp_model, unit)
            st.session_state.solar_last_forecast = (day, LATITUDE, LONGITUDE, payload, fetched)
    except (requests.RequestException, ValueError, KeyError, TypeError, IndexError):
        recent = st.session_state.get("solar_last_forecast")
        if (recent is None or recent[:3] != (day, LATITUDE, LONGITUDE) or
                not timedelta(0) <= datetime.now(LOCAL_TIME) - datetime.fromisoformat(recent[4]) <= timedelta(hours=2)):
            st.warning("Tomorrow's forecast is unavailable or incomplete. Please refresh or try again later.")
            return
        _, _, _, payload, fetched = recent
        try:
            forecast = predict_forecast(payload, day, model, module_temp_model, unit)
        except (ValueError, KeyError, TypeError, IndexError):
            st.warning("Tomorrow's forecast is incomplete. Please refresh or try again later.")
            return
        retrieved = datetime.fromisoformat(fetched)
        st.warning(f"Weather refresh failed. Showing the forecast using weather retrieved at {retrieved:%I:%M %p}. "
                   "Refresh to retry.")
    forecast = display_forecast(forecast)
    peak = forecast.loc[forecast["Estimated power (kW)"].idxmax()]
    positive = peak["Estimated power (kW)"] > 0
    start = peak["Hour starting"]
    st.subheader("Tomorrow at a glance")
    energy_col, power_col, time_col = st.columns(3, border=True)
    energy_col.metric("Estimated daily energy", f'{forecast["Estimated energy (kWh)"].sum():,.1f} kWh')
    power_col.metric("Peak hourly power", f'{peak["Estimated power (kW)"]:,.1f} kW')
    time_col.metric("Peak production hour", f"{start:%I %p}–{start + timedelta(hours=1):%I %p}" if positive else "No generation")
    st.subheader("Hourly power outlook")
    st.line_chart(forecast.set_index("Hour starting")[["Estimated power (kW)"]])
    with st.expander("Hourly forecast details & download"):
        st.dataframe(forecast, hide_index=True, use_container_width=True)
        st.download_button("Download forecast CSV", forecast.to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"solarcast-forecast-{day}.csv", mime="text/csv")
    with st.container(border=True):
        st.caption(f"Updated {datetime.fromisoformat(fetched):%d %b %Y, %I:%M %p}")
        st.caption("Weather: [Open-Meteo](https://open-meteo.com/)")
