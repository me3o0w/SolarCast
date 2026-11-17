import pandas as pd
import streamlit as st

from model_loader import model

# =========================================================
# LIVE PREDICTION
# =========================================================


def render_live_prediction(
    live_temperature,
    live_irradiation,
    estimated_module_temperature,
    live_hour,
    live_minute,
    live_day,
    live_month,
    live_day_of_week,
):

    st.header("🌐 Live SolarCast Prediction")

    if st.button(
        "🌐 Predict Using Live Data",
        use_container_width=True
    ):

        # Make sure live data is available
        if (
            live_temperature is not None
            and live_irradiation is not None
            and estimated_module_temperature is not None
        ):

            # Create input using LIVE values
            live_input = pd.DataFrame([{
                "IRRADIATION": live_irradiation,
                "AMBIENT_TEMPERATURE": live_temperature,
                "MODULE_TEMPERATURE": estimated_module_temperature,
                "HOUR": live_hour,
                "MINUTE": live_minute,
                "DAY": live_day,
                "MONTH": live_month,
                "DAY_OF_WEEK": live_day_of_week
            }])

            # Predict AC power
            live_prediction = model.predict(
                live_input
            )[0]

            # Prevent negative prediction
            live_prediction = max(
                0,
                live_prediction
            )


            # =============================================
            # GENERATION STATUS
            # =============================================

            if live_prediction < 300:

                live_status = "🔴 Low Generation"

            elif live_prediction < 700:

                live_status = "🟡 Moderate Generation"

            else:

                live_status = "🟢 High Generation"


            # =============================================
            # LIVE RESULTS
            # =============================================

            st.subheader(
                "⚡ Live SolarCast Result"
            )

            col1, col2 = st.columns(2)

            with col1:

                st.metric(
                    "Predicted AC Power",
                    f"{live_prediction:.2f}"
                )

            with col2:

                st.metric(
                    "Generation Status",
                    live_status
                )


            st.success(
                f"SolarCast predicts **{live_prediction:.2f} "
                f"AC power units** using the current live "
                f"environmental conditions."
            )


            # =============================================
            # SHOW MODEL INPUTS
            # =============================================

            st.subheader(
                "🤖 ML Model Input"
            )

            st.dataframe(
                live_input,
                use_container_width=True
            )

        else:

            st.error(
                "Live data is currently unavailable. "
                "Please refresh the application and try again."
            )