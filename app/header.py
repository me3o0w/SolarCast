import streamlit as st

# =========================================================
# SOLARCAST HEADER
# =========================================================


def render_header():

    st.title("☀️ SolarCast")

    st.markdown(
        "### Machine Learning-Based Solar Power Generation "
        "Prediction and Monitoring System"
    )

    st.caption(
        "Real-time environmental monitoring and machine-learning "
        "based solar power prediction."
    )

    st.divider()