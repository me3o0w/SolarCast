from base64 import b64encode
from datetime import datetime, timedelta, timezone
from pathlib import Path
from html import escape
from importlib import reload

import pandas as pd
import requests
import streamlit as st

from auth import auth_session_needs_refresh, render_profile, render_sign_out, require_sign_in
from config import REFRESH_INTERVAL
from supabase_store import PREDICTION_TABLE, SupabaseStore
from weather_client import get_current_conditions
from history import render_history
from forecast import render_forecast
from prediction_history import overview_hour, render_prediction_history, save_prediction
import loading as loading_ui
import styles as theme_ui
from manual_pred import render_manual_prediction
from model_info import render_model_info
from terms import render_terms
from about import render_about
from model_loader import model, module_temp_model

# OneDrive can miss module-change notifications. Reload these stateless UI
# modules on each Streamlit rerun so the scene, timing, and CSS stay in sync.
SolarLoading = reload(loading_ui).SolarLoading
PageLoading = loading_ui.PageLoading
apply_styles = reload(theme_ui).apply_styles

LOGO_PATH = Path(__file__).with_name("logo.png")
LOGO_DATA = b64encode(LOGO_PATH.read_bytes()).decode("ascii")

st.set_page_config(
    page_title="SolarCast",
    page_icon=str(LOGO_PATH),
    layout="wide",
    initial_sidebar_state="auto",
)
auth, auth_session = require_sign_in()
apply_styles()


@st.cache_data(ttl=REFRESH_INTERVAL, show_spinner=False)
def fetch_weather():
    ambient, irradiation = get_current_conditions()
    return ambient, irradiation, datetime.now(timezone.utc)


def render_power_panel(now, output, status):
    status_symbols = {
        "Low generation": '<path d="M12 3 2 21h20L12 3Z"/><path d="M12 9v5"/><circle cx="12" cy="17" r=".7" fill="currentColor" stroke="none"/>',
        "Moderate generation": '<circle cx="12" cy="12" r="9"/><path d="M7 12h10"/>',
        "High generation": '<circle cx="12" cy="12" r="9"/><path d="M12 17V7m-4 4 4-4 4 4"/>',
    }
    symbol = status_symbols.get(status, '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>')
    st.markdown(
        '<section class="sc-hero" aria-label="Solar generation outlook">'
        '<div><h1 class="sc-title">Solar generation outlook</h1>'
        f'<time datetime="{now.isoformat()}">{now:%d %b %Y · %I:%M %p} local</time></div>'
        '<div><div class="sc-power-label">Predicted AC power</div>'
        f'<div class="sc-number">{escape(output)}</div>'
        '<div class="sc-status" role="status" aria-live="polite" aria-atomic="true">'
        '<svg class="sc-status-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">'
        f'{symbol}</svg><span>{escape(status)}</span></div></div></section>',
        unsafe_allow_html=True,
    )


def refresh_outlook():
    st.session_state.solar_refresh_requested = True
    fetch_weather.clear()


def account_predictions():
    return SupabaseStore(
        auth.project_url, auth.key, access_token=auth_session.access_token, account_table=PREDICTION_TABLE,
    )


@st.fragment(run_every=REFRESH_INTERVAL)
def render_overview():
    if auth_session_needs_refresh():
        st.rerun()
    with st.container(key="overview_actions", horizontal=True, horizontal_alignment="right"):
        st.button("Refresh outlook", icon=":material/refresh:", key="refresh_weather", on_click=refresh_outlook)
    now = datetime.now()
    conditions = None
    using_recent_weather = False
    show_refresh = st.session_state.pop("solar_refresh_requested", False)
    show_intro = not st.session_state.get("solar_intro_shown", False)
    st.session_state.solar_intro_shown = True
    with (
        PageLoading("Overview", enabled=show_refresh, message="Refreshing your solar generation outlook"),
        SolarLoading(minimum_duration=12.0, enabled=show_intro and not show_refresh) as loading,
    ):
        try:
            conditions = fetch_weather()
            st.session_state.solar_last_weather = conditions
        except (requests.RequestException, ValueError, KeyError, TypeError):
            recent = st.session_state.get("solar_last_weather")
            if recent is not None and timedelta(0) <= datetime.now(timezone.utc) - recent[2] <= timedelta(minutes=15):
                conditions = recent
                using_recent_weather = True

        if conditions is not None:
            ambient, irradiation = conditions[:2]
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
        st.button("Retry weather", icon=":material/refresh:", key="retry_weather", on_click=refresh_outlook)
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
    hour = overview_hour(conditions[2])
    if not using_recent_weather and st.session_state.get("solar_saved_overview_hour") != hour:
        if save_prediction(
            account_predictions(), source="Overview", predicted_for=now.astimezone(), power=power,
            sunlight=irradiation, ambient=ambient, module=module, weather_fetched_at=conditions[2],
        ):
            st.session_state.solar_saved_overview_hour = hour
    retrieved = conditions[2].astimezone(timezone(timedelta(hours=8)))
    if using_recent_weather:
        st.warning(f"Weather refresh failed. Showing readings retrieved at {retrieved:%I:%M %p}. "
                   "Try Refresh outlook again for current conditions.")
    weather_icon = (
        '<svg class="sc-weather-icon" viewBox="0 0 32 32" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">'
        '<circle cx="11" cy="10" r="5"/>'
        '<path d="M11 1v2M11 17v2M2 10h2M18 10h2M4.6 3.6 6 5m10 10 1.4 1.4M4.6 16.4 6 15M16 5l1.4-1.4"/>'
        '<path d="M11 27h13a6 6 0 0 0 .3-12 8 8 0 0 0-15.1 1.6A5.3 5.3 0 0 0 11 27Z" '
        'fill="#141f2e" stroke="#d3dfeb"/></svg>'
    )
    rows = "".join(
        f'<div class="sc-reading{css_class}"><span>{escape(label)}</span>'
        f'<div class="sc-reading-value">{weather_icon if css_class == " sc-weather" else ""}'
        f'<strong>{escape(value)}</strong></div></div>'
        for (label, value), css_class in zip(readings, (" sc-weather", " sc-solar", ""))
    )
    st.markdown(
        f'<div class="sc-readings">{rows}</div>'
        f'<p class="sc-source">Weather: Open-Meteo · Cagayan de Oro · '
        f'Checked {retrieved:%I:%M %p} PHT · Estimated power and module temperature</p>',
        unsafe_allow_html=True,
    )

    with st.expander("Prediction inputs"):
        st.dataframe(features, hide_index=True)


with st.sidebar, st.container(key="solar_sidebar_layout"):
    st.markdown(
        '<div class="sc-brand">'
        f'<img src="data:image/png;base64,{LOGO_DATA}" alt="SolarCast logo" '
        'width="54" height="54" style="flex:0 0 54px;object-fit:contain;">'
        '<div class="sc-wordmark">Solar<span>Cast</span>'
        '<small>Solar power monitoring</small></div></div>',
        unsafe_allow_html=True,
    )
    navigation = (
        ("Overview", ":material/dashboard:"),
        ("Next-day forecast", ":material/wb_sunny:"),
        ("Prediction history", ":material/history:"),
        ("Manual prediction", ":material/tune:"),
        ("My Profile", ":material/person:"),
    )
    footer_navigation = (
        ("Power history", ":material/show_chart:"),
        ("Model performance", ":material/analytics:"),
        ("Terms and Conditions", ":material/gavel:"),
        ("About this", ":material/info:"),
    )
    if "solar_page" not in st.session_state:
        st.session_state.solar_page = "Overview"
    elif st.session_state.solar_page == "Forecast history":
        st.session_state.solar_page = "Prediction history"

    def select_page(label):
        st.session_state.solar_page = label
        st.session_state.solar_navigation_loading = label

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

    with st.container(key="solar_sidebar_footer", horizontal=True, wrap=False, gap="small"):
        for label, icon in footer_navigation:
            st.button(
                label,
                key=f"solar_nav_{label}",
                icon=icon,
                help=label,
                type="primary" if page == label else "secondary",
                width="stretch",
                on_click=select_page,
                args=(label,),
            )
    render_sign_out(auth, auth_session)

pending_page = st.session_state.pop("solar_navigation_loading", None)
with PageLoading(page, enabled=page in loading_ui.PAGE_LOADERS and pending_page == page):
    if page == "Overview":
        render_overview()
    elif page == "Next-day forecast":
        render_forecast()
    elif page == "Prediction history":
        render_prediction_history(account_predictions())
    elif page == "Manual prediction":
        render_manual_prediction(account_predictions())
    elif page == "My Profile":
        render_profile(auth, auth_session)
    elif page == "Power history":
        render_history()
    elif page == "Model performance":
        render_model_info()
    elif page == "Terms and Conditions":
        render_terms()
    elif page == "About this":
        render_about()
