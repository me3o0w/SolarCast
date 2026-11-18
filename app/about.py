"""A short introduction to SolarCast and its main features."""

import streamlit as st


def render_about():
    st.title("About this")
    st.subheader("SolarCast")
    st.write(
        "SolarCast helps you explore solar power generation using weather data, "
        "machine-learning estimates, and historical records."
    )

    forecast_column, history_column = st.columns(2)
    with forecast_column, st.container(border=True):
        st.subheader("Forecast and predict")
        st.markdown(
            "- View the current solar generation outlook.\n"
            "- Explore next-day power and energy estimates.\n"
            "- Try your own weather inputs with manual prediction."
        )
    with history_column, st.container(border=True):
        st.subheader("Review and compare")
        st.markdown(
            "- Compare predictions saved to your account.\n"
            "- Review recorded power history.\n"
            "- Check model performance and download next-day forecasts."
        )

    st.subheader("How it works")
    st.write(
        "Weather comes from Open-Meteo. A temperature model estimates solar-panel "
        "temperature, and a Gradient Boosting Regression model estimates AC power."
    )
    st.caption("Forecasts are estimates, not measured output. See Terms and Conditions for usage details.")
