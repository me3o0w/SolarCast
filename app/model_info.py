import streamlit as st

# =========================================================
# ML MODEL PERFORMANCE
# =========================================================


def render_model_info():

    st.divider()

    st.header("🧠 SolarCast ML Model")

    st.write(
        "SolarCast uses a Gradient Boosting Regression model "
        "to predict solar AC power generation."
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
        "Model evaluation was performed using the held-out test dataset. "
        "Higher R² indicates better explanatory performance, while "
        "lower RMSE and MAE indicate lower prediction error."
    )

    st.info(
        "⭐ The most influential feature in the trained model is "
        "**IRRADIATION**, which accounts for approximately "
        "**96.8% of the model's feature importance**."
    )