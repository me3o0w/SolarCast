import pandas as pd
import streamlit as st

from model_loader import model

# =========================================================
# CURRENT CONDITIONS - MANUAL TESTING
# =========================================================


def render_manual_test_conditions():

    st.header("🌤️ Manual Test Conditions")

    st.caption(
        "Use these controls to manually test the trained "
        "SolarCast model."
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        irradiation = st.number_input(
            "☀️ Solar Irradiation",
            min_value=0.0,
            value=0.8,
            step=0.1
        )

    with col2:

        ambient_temperature = st.number_input(
            "🌡️ Ambient Temperature (°C)",
            value=30.0,
            step=0.5
        )

    with col3:

        module_temperature = st.number_input(
            "🔥 Module Temperature (°C)",
            value=40.0,
            step=0.5
        )


# =========================================================
# MANUAL PREDICTION
# =========================================================


def render_manual_prediction():

    st.header("🧪 Manual Test Prediction")

    st.caption(
        "Use manual inputs to test the trained SolarCast model."
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        irradiation = st.number_input(
            "☀️ Solar Irradiation",
            min_value=0.0,
            value=0.8,
            step=0.1,
            key="manual_irradiation"
        )

    with col2:
        ambient_temperature = st.number_input(
            "🌡️ Ambient Temperature (°C)",
            value=30.0,
            step=0.5,
            key="manual_ambient_temperature"
        )

    with col3:
        module_temperature = st.number_input(
            "🔥 Module Temperature (°C)",
            value=40.0,
            step=0.5,
            key="manual_module_temperature"
        )


    col1, col2, col3, col4 = st.columns(4)

    with col1:
        hour = st.number_input(
            "Hour",
            min_value=0,
            max_value=23,
            value=12,
            key="manual_hour"
        )

    with col2:
        minute = st.number_input(
            "Minute",
            min_value=0,
            max_value=59,
            value=0,
            key="manual_minute"
        )

    with col3:
        day = st.number_input(
            "Day",
            min_value=1,
            max_value=31,
            value=15,
            key="manual_day"
        )

    with col4:
        month = st.number_input(
            "Month",
            min_value=1,
            max_value=12,
            value=6,
            key="manual_month"
        )

    day_of_week = st.number_input(
        "Day of Week (0 = Monday, 6 = Sunday)",
        min_value=0,
        max_value=6,
        value=0,
        key="manual_day_of_week"
    )


    if st.button(
        "☀️ Predict Manual Input",
        use_container_width=True,
        key="manual_prediction_button"
    ):

        input_data = pd.DataFrame([{
            "IRRADIATION": irradiation,
            "AMBIENT_TEMPERATURE": ambient_temperature,
            "MODULE_TEMPERATURE": module_temperature,
            "HOUR": hour,
            "MINUTE": minute,
            "DAY": day,
            "MONTH": month,
            "DAY_OF_WEEK": day_of_week
        }])

        prediction = model.predict(
            input_data
        )[0]

        prediction = max(
            0,
            prediction
        )

        if prediction < 300:
            status = "🔴 Low Generation"

        elif prediction < 700:
            status = "🟡 Moderate Generation"

        else:
            status = "🟢 High Generation"


        st.subheader(
            "⚡ Manual Prediction Result"
        )

        col1, col2 = st.columns(2)

        with col1:
            st.metric(
                "Predicted AC Power",
                f"{prediction:.2f}"
            )

        with col2:
            st.metric(
                "Generation Status",
                status
            )