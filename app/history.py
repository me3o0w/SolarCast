from pathlib import Path

import pandas as pd
import streamlit as st

from config import PLANT1_PATH


@st.cache_data
def load_hourly_power(path, modified_ns):
    data = pd.read_csv(path, usecols=["DATE_TIME", "AC_POWER"])
    data["DATE_TIME"] = pd.to_datetime(data["DATE_TIME"], dayfirst=True)
    readings = data.groupby("DATE_TIME")["AC_POWER"].mean()
    return readings.resample("h").mean().rename("Average AC power")


def render_history():
    st.header("Historical solar power")
    path = Path(PLANT1_PATH)
    try:
        hourly = load_hourly_power(str(path), path.stat().st_mtime_ns)
    except FileNotFoundError:
        st.warning("Add Plant_1_Generation_Data.csv to the data folder to show history.")
        return
    except (OSError, ValueError):
        st.error("Could not read the historical data. Check the DATE_TIME and AC_POWER columns.")
        return

    if hourly.dropna().empty:
        st.info("The dataset contains no power readings to plot.")
        return

    st.caption("Recorded AC power · Hourly averages")
    st.line_chart(hourly, height=340, color="#ffb95e")
