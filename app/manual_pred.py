from datetime import datetime, time, timedelta, timezone
import math

import pandas as pd
import streamlit as st

from model_loader import model, module_temp_model
from prediction_history import save_prediction

# =========================================================
# CURRENT CONDITIONS - MANUAL TESTING
# =========================================================


def render_manual_test_conditions():

    st.header("🌤️ Manual Test Conditions")


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


def render_manual_prediction(store=None):
    st.header("Manual prediction")
    today = datetime.now(timezone(timedelta(hours=8))).date()

    with st.form("manual_prediction_form"):
        date_column, time_column = st.columns(2)
        with date_column:
            prediction_date = st.date_input("Date", value=today, format="DD/MM/YYYY", key="manual_date")
        with time_column:
            prediction_time = st.time_input("Time", value=time(12), step=timedelta(minutes=15),
                                            format="12h", key="manual_time")

        sunlight_column, temperature_column = st.columns(2)
        with sunlight_column:
            sunlight = st.number_input(
                "Sunlight (W/m²)", min_value=0.0, value=800.0, step=50.0,
                help="0 at night; around 800 in bright sunlight.", key="manual_sunlight",
            )
        with temperature_column:
            ambient = st.number_input("Air temperature (°C)", value=30.0, step=0.5,
                                      key="manual_ambient_temperature")

        with st.expander("Solar-panel temperature (optional)"):
            module = st.number_input(
                "Solar-panel temperature (°C)", value=None, step=0.5,
                placeholder="Automatic estimate", key="manual_module_temperature",
                help="Leave blank to estimate from sunlight and air temperature.",
            )
        submitted = st.form_submit_button("Predict solar power", type="primary", width="stretch",
                                         key="manual_prediction_button")

    if not submitted:
        return
    if prediction_date is None or prediction_time is None:
        st.warning("Choose a date and time.")
        return

    try:
        # The training models expect irradiation in kW/m².
        weather = pd.DataFrame([{"IRRADIATION": sunlight / 1000, "AMBIENT_TEMPERATURE": ambient}])
        estimated_module = module is None
        if estimated_module:
            module = float(module_temp_model.predict(weather)[0])
        if not math.isfinite(module):
            raise ValueError("Invalid panel temperature")
        features = weather.assign(
            MODULE_TEMPERATURE=module,
            HOUR=prediction_time.hour, MINUTE=prediction_time.minute,
            DAY=prediction_date.day, MONTH=prediction_date.month,
            DAY_OF_WEEK=prediction_date.weekday(),
        )
        prediction = float(model.predict(features)[0])
        if not math.isfinite(prediction):
            raise ValueError("Invalid prediction")
        prediction = max(0.0, prediction)
    except (ValueError, TypeError, IndexError):
        st.error("Unable to calculate a prediction. Check your inputs and try again.")
        return

    status = "Low generation" if prediction < 300 else "Moderate generation" if prediction < 700 else "High generation"
    st.subheader("Prediction result")
    st.caption(f"{prediction_date:%d %b %Y} · {prediction_time:%I:%M %p}")
    power_column, status_column = st.columns(2, border=True)
    power_column.metric("Predicted AC power", f"{prediction:,.2f}")
    status_column.metric("Generation", status)
    panel_label = "Estimated panel temperature" if estimated_module else "Panel temperature"
    st.caption(f"{panel_label}: {module:.1f} °C")
    if store is not None and save_prediction(
        store, source="Manual prediction",
        predicted_for=datetime.combine(prediction_date, prediction_time, timezone(timedelta(hours=8))),
        power=prediction, sunlight=sunlight, ambient=ambient, module=module,
    ):
        st.caption("Saved to your account.")
