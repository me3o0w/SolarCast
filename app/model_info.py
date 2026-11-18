import streamlit as st

# =========================================================
# ML MODEL PERFORMANCE
# =========================================================


def render_model_info():

    st.header("🧠 SolarCast ML Model")

    st.write(
        "Gradient Boosting Regression"
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "R² Score",
            "0.5543"
        )

    with col2:
        st.metric(
            "RMSE",
            "216.02"
        )

    with col3:
        st.metric(
            "MAE",
            "81.31"
        )

    st.caption(
        "Test results · Higher R² and lower RMSE/MAE are better."
    )

    st.info(
        "Top feature: **Irradiation (96.8%)**"
    )
