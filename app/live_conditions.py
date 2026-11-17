import pandas as pd
import requests
import streamlit as st

from config import API_URL
from model_loader import module_temp_model

# =========================================================
# LIVE WEATHER DATA
# =========================================================


def render_live_conditions():
    """
    Fetches live weather data, estimates module temperature,
    and displays the results.

    Returns:
        (live_temperature, live_irradiation, estimated_module_temperature)
    """

    st.header("🌐 Live Solar Conditions")

    # Default values
    live_temperature = None
    live_irradiation = None
    estimated_module_temperature = None

    try:

        response = requests.get(
            API_URL,
            timeout=10
        )

        response.raise_for_status()

        live_data = response.json()

        current_data = live_data["current"]

        live_temperature = current_data["temperature_2m"]
        live_irradiation = current_data["shortwave_radiation"]


        # =================================================
        # ESTIMATE MODULE TEMPERATURE
        # =================================================

        module_input = pd.DataFrame([{
            "IRRADIATION": live_irradiation,
            "AMBIENT_TEMPERATURE": live_temperature
        }])

        estimated_module_temperature = module_temp_model.predict(
            module_input
        )[0]


        # =================================================
        # DISPLAY LIVE CONDITIONS
        # =================================================

        col1, col2, col3 = st.columns(3)

        with col1:

            st.metric(
                "🌡️ Live Ambient Temperature",
                f"{live_temperature:.1f} °C"
            )

        with col2:

            st.metric(
                "☀️ Live Solar Irradiation",
                f"{live_irradiation:.1f} W/m²"
            )

        with col3:

            st.metric(
                "🔥 Estimated Module Temperature",
                f"{estimated_module_temperature:.1f} °C"
            )


        st.caption(
            "Live weather and solar data provided by Open-Meteo. "
            "Module temperature is estimated using a trained "
            "secondary regression model."
        )

    except Exception as e:

        st.error(
            f"Unable to retrieve live weather data: {e}"
        )


    st.divider()

    return live_temperature, live_irradiation, estimated_module_temperature