"""Plain-language usage terms for SolarCast."""

import streamlit as st


def render_terms():
    st.title("Terms and Conditions")
    st.caption("Last updated: 18 Nov 2026")

    with st.container(border=True):
        st.subheader("1. Using SolarCast")
        st.write(
            "SolarCast provides solar power estimates, weather-based forecasts, "
            "and historical comparisons for monitoring and informational use. "
            "By using the system, you agree to these terms."
        )

        st.subheader("2. Forecast accuracy")
        st.write(
            "Predictions are model estimates, not measured power or guaranteed output. "
            "Weather, location, equipment, and input data can affect results. "
            "Verify important decisions against actual readings and qualified advice."
        )

        st.subheader("3. Your inputs and decisions")
        st.write(
            "Check the values and units you enter. You are responsible for decisions "
            "made using the results. Do not use SolarCast as the sole basis for "
            "electrical safety, equipment control, or financial commitments."
        )

        st.subheader("4. Saved predictions and downloads")
        st.write(
            "SolarCast saves live Overview and manual prediction results to your account "
            "when storage is available. Saved records include prediction times, weather "
            "inputs, and estimated power. You can download next-day forecasts."
        )

        st.subheader("5. Weather and availability")
        st.write(
            "Weather is supplied by Open-Meteo. Weather services, forecasts, "
            "and saved history may be delayed or unavailable. When recent cached "
            "weather is used after a failed refresh, SolarCast displays a notice."
        )

        st.subheader("6. Responsible use")
        st.write(
            "Use the system lawfully. Do not attempt unauthorized access, "
            "disrupt the service, alter records without permission, "
            "or present estimates as verified measurements."
        )
