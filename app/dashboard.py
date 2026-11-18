import pandas as pd
import streamlit as st

from model_loader import model

# =========================================================
# SOLARCAST LIVE DASHBOARD
# =========================================================


@st.fragment(run_every=60)
def live_dashboard():

    st.divider()
    st.header("SolarCast Live Dashboard")


def render_dashboard(
    live_temperature,
    live_irradiation,
    estimated_module_temperature,
    live_hour,
    live_minute,
    live_day,
    live_month,
    live_day_of_week,
):

    if (
        live_temperature is not None
        and live_irradiation is not None
        and estimated_module_temperature is not None
    ):

        # -------------------------------------------------
        # LIVE ENVIRONMENTAL CONDITIONS
        # -------------------------------------------------

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "Ambient Temperature",
                f"{live_temperature:.1f} °C"
            )

        with col2:
            st.metric(
                "Solar Irradiation",
                f"{live_irradiation:.1f} W/m²"
            )

        with col3:
            st.metric(
                "Module Temperature",
                f"{estimated_module_temperature:.1f} °C"
            )

        st.divider()

        # -------------------------------------------------
        # AUTOMATIC LIVE PREDICTION
        # -------------------------------------------------

        live_dashboard_input = pd.DataFrame([{
            "IRRADIATION": live_irradiation,
            "AMBIENT_TEMPERATURE": live_temperature,
            "MODULE_TEMPERATURE": estimated_module_temperature,
            "HOUR": live_hour,
            "MINUTE": live_minute,
            "DAY": live_day,
            "MONTH": live_month,
            "DAY_OF_WEEK": live_day_of_week
        }])

        dashboard_prediction = model.predict(
            live_dashboard_input
        )[0]

        dashboard_prediction = max(
            0,
            dashboard_prediction
        )

        # -------------------------------------------------
        # GENERATION STATUS
        # -------------------------------------------------

        if dashboard_prediction < 300:

            dashboard_status = "Low Generation"

        elif dashboard_prediction < 700:

            dashboard_status = "Moderate Generation"

        else:

            dashboard_status = "High Generation"

        # -------------------------------------------------
        # DISPLAY PREDICTION
        # -------------------------------------------------

        st.subheader("⚡ Current Solar Power Prediction")

        st.metric(
            "Predicted AC Power",
            f"{dashboard_prediction:.2f}"
        )
        st.markdown(
            f"### {dashboard_status}"
        )

        if dashboard_prediction < 300:

            st.warning(
                "Solar generation is currently low."
            )
        elif dashboard_prediction < 700:
            st.info(
                "Solar generation is currently moderate."
            )

        else:

            st.success(
                "Solar generation is currently high."
            )

        with col1:
            st.metric(
                "Predicted AC Power",
                f"{dashboard_prediction:.2f}"
            )

        with col2:
            st.metric(
                "Generation Status",
                dashboard_status
            )

        st.caption(
            "Prediction is generated using the trained "
            "Gradient Boosting regression model and the "
            "current live environmental conditions."
        )

    else:

        st.warning(
            "Live environmental data is currently unavailable."
        )