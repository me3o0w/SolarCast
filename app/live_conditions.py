import streamlit as st

from weather_client import get_current_conditions

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

        live_temperature, live_irradiation = get_current_conditions()


        # =================================================
        # ESTIMATE MODULE TEMPERATURE (Empirical Formula)
        # =================================================
        # T_module = T_ambient + (0.025 × irradiance in W/m²)
        estimated_module_temperature = live_temperature + (0.025 * live_irradiation)


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
            "Module temperature is estimated from ambient temperature and solar irradiance."
        )

    except Exception as e:

        st.error(
            f"Unable to retrieve live weather data: {e}"
        )


    st.divider()

    return live_temperature, live_irradiation, estimated_module_temperature
