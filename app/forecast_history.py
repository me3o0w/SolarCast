"""Browse saved forecasts without contacting the weather service."""
import sqlite3

import streamlit as st

from forecast_store import DB_PATH, list_forecasts, load_forecast


def render_forecast_history():
    st.title("Forecast history")
    st.write("Saved predictions remain available after their forecast date has passed.")
    st.caption("These are model estimates, not measured production. Each weather refresh is kept as a separate version.")
    try:
        runs = list_forecasts()
        if runs.empty:
            st.info("No saved forecasts yet. Open Next-day forecast to create and save one.")
            return
        target = st.selectbox("Forecast date", runs.target_date.drop_duplicates().tolist())
        versions = runs[runs.target_date == target].set_index("id")

        def label(run_id):
            row = versions.loc[run_id]
            return (f'Weather retrieved {row.weather_fetched_at} · '
                    f'{row.latitude:.4f}, {row.longitude:.4f} · training unit {row.training_power_unit} · #{run_id}')

        run_id = st.selectbox("Saved version (latest first)", versions.index.tolist(), format_func=label)
        selected = versions.loc[run_id]
        frame = load_forecast(run_id)
        energy, peak = st.columns(2)
        energy.metric("Estimated daily energy", f"{selected.daily_energy_kwh:,.1f} kWh")
        peak.metric("Peak hourly power", f"{selected.peak_power_kw:,.1f} kW")
        st.line_chart(frame.set_index("Hour starting (Asia/Manila)")[["Estimated power (kW)"]])
        st.dataframe(frame, hide_index=True, use_container_width=True)
        st.download_button("Download saved forecast CSV", frame.to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"solarcast-{target}-version-{run_id}.csv", mime="text/csv")
        st.caption(f"Saved at {selected.saved_at} · Model version: {selected.model_version}")
    except (sqlite3.Error, OSError, ValueError):
        st.error("Unable to read forecast history. Check that the database is available and try again.")
    st.caption(f"Stored locally in {DB_PATH}. Back up this file to keep your history.")
