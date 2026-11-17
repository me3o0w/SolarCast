from datetime import datetime

import streamlit as st

# =========================================================
# LIVE TIME FEATURES
# =========================================================


def render_time_features():
    """
    Displays the current time features.

    Returns:
        (live_hour, live_minute, live_day, live_month, live_day_of_week)
    """

    current_time = datetime.now()

    live_hour = current_time.hour
    live_minute = current_time.minute
    live_day = current_time.day
    live_month = current_time.month
    live_day_of_week = current_time.weekday()

    st.subheader("🕐 Current Time Features")

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:

        st.metric(
            "Hour",
            live_hour
        )

    with col2:

        st.metric(
            "Minute",
            live_minute
        )

    with col3:

        st.metric(
            "Day",
            live_day
        )

    with col4:

        st.metric(
            "Month",
            live_month
        )

    with col5:

        st.metric(
            "Day of Week",
            live_day_of_week
        )

    return live_hour, live_minute, live_day, live_month, live_day_of_week