from base64 import b64encode
from datetime import datetime
from pathlib import Path
from html import escape
from importlib import reload

import pandas as pd
import requests
import streamlit as st

from config import API_URL
from history import render_history
from forecast import render_forecast
from forecast_history import render_forecast_history
import loading as loading_ui
import styles as theme_ui
from manual_pred import render_manual_prediction
from model_info import render_model_info
from model_loader import model, module_temp_model

# OneDrive can miss module-change notifications. Reload these stateless UI
# modules on each Streamlit rerun so the scene, timing, and CSS stay in sync.
SolarLoading = reload(loading_ui).SolarLoading
apply_styles = reload(theme_ui).apply_styles

LOGO_PATH = Path(__file__).with_name("logo.png")
LOGO_DATA = b64encode(LOGO_PATH.read_bytes()).decode("ascii")

st.set_page_config(
    page_title="SolarCast",
    page_icon=str(LOGO_PATH),
    layout="wide",
    initial_sidebar_state="auto",
)
apply_styles()


@st.cache_data(ttl=60, show_spinner=False)
def fetch_weather():
    response = requests.get(API_URL, timeout=(3, 5))
    response.raise_for_status()
    current = response.json()["current"]
    return float(current["temperature_2m"]), float(current["shortwave_radiation"])


def render_power_panel(now, output, status):
    st.markdown(
        '<section class="sc-hero" aria-label="Solar generation outlook">'
        '<div><h1 class="sc-title">Solar generation outlook</h1>'
        f'<time datetime="{now.isoformat()}">{now:%d %b %Y · %I:%M %p} local</time></div>'
        '<div><div class="sc-power-label">Predicted AC power</div>'
        f'<div class="sc-number">{escape(output)}</div>'
        f'<div class="sc-status">{escape(status)}</div></div></section>',
        unsafe_allow_html=True,
    )


def refresh_outlook():
    # Refreshes fetch new weather without replaying the opening scene.
    st.session_state.solar_intro_shown = True
    fetch_weather.clear()


@st.fragment
def render_overview():
    now = datetime.now()
    conditions = None
    show_intro = not st.session_state.get("solar_intro_shown", False)
    st.session_state.solar_intro_shown = True
    with SolarLoading(minimum_duration=12.0, enabled=show_intro) as loading:
        try:
            conditions = fetch_weather()
        except (requests.RequestException, ValueError, KeyError, TypeError):
            pass

        if conditions is not None:
            ambient, irradiation = conditions
            loading.update(1)
            weather = pd.DataFrame([{
                "IRRADIATION": irradiation,
                "AMBIENT_TEMPERATURE": ambient,
            }])
            module = module_temp_model.predict(weather)[0]
            loading.update(2)
            features = weather.assign(
                MODULE_TEMPERATURE=module, HOUR=now.hour, MINUTE=now.minute,
                DAY=now.day, MONTH=now.month, DAY_OF_WEEK=now.weekday(),
            )
            power = max(0, model.predict(features)[0])
            loading.update(3)
    if conditions is None:
        render_power_panel(now, "—", "Waiting for current weather")
        st.warning("Current weather is unavailable. Try again or use Manual prediction.")
        st.button("Retry weather", key="retry_weather", on_click=refresh_outlook)
        return
    if power < 300:
        status = "Low generation"
    elif power < 700:
        status = "Moderate generation"
    else:
        status = "High generation"

    readings = (
        ("Ambient temperature", f"{ambient:.1f} °C"),
        ("Solar irradiance", f"{irradiation:.1f} W/m²"),
        ("Estimated module temperature", f"{module:.1f} °C"),
    )
    render_power_panel(now, f"{power:,.2f}", status)
    rows = "".join(
        f'<div class="sc-reading{css_class}"><span>{escape(label)}</span>'
        f'<strong>{escape(value)}</strong></div>'
        for (label, value), css_class in zip(readings, ("", " sc-solar", ""))
    )
    st.markdown(
        f'<div class="sc-readings">{rows}</div>'
        '<p class="sc-source">Open-Meteo weather · Module temperature and AC power are model estimates.</p>',
        unsafe_allow_html=True,
    )

    with st.expander("Prediction inputs"):
        st.dataframe(features, hide_index=True)
    st.button("Refresh outlook", key="refresh_weather", on_click=refresh_outlook)


with st.sidebar:
    st.markdown(
        '<div class="sc-brand">'
        f'<img src="data:image/png;base64,{LOGO_DATA}" alt="SolarCast logo" '
        'width="46" height="46" style="flex:0 0 46px;object-fit:contain;">'
        '<div class="sc-wordmark">Solar<span>Cast</span>'
        '<small>Solar power monitoring</small></div></div>',
        unsafe_allow_html=True,
    )
    navigation = (
        ("Overview", ":material/dashboard:"),
        ("Next-day forecast", ":material/wb_sunny:"),
        ("Forecast history", ":material/history:"),
        ("Manual prediction", ":material/tune:"),
        ("Power history", ":material/show_chart:"),
        ("Model performance", ":material/analytics:"),
    )
    if "solar_page" not in st.session_state:
        st.session_state.solar_page = "Overview"

    def select_page(label):
        st.session_state.solar_page = label

    page = st.session_state.solar_page
    for label, icon in navigation:
        st.button(
            label,
            key=f"solar_nav_{label}",
            icon=icon,
            type="primary" if page == label else "secondary",
            use_container_width=True,
            on_click=select_page,
            args=(label,),
        )

if page == "Overview":
    render_overview()
elif page == "Next-day forecast":
    render_forecast()
elif page == "Forecast history":
    render_forecast_history()
elif page == "Manual prediction":
    render_manual_prediction()
elif page == "Power history":
    render_history()
else:
    render_model_info()
