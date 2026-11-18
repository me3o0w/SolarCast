"""Organized saved forecasts, daily trends and hourly version comparisons."""
from datetime import datetime, timedelta, timezone
import sqlite3

import altair as alt
import pandas as pd
import streamlit as st

from forecast_store import StoreError, list_forecasts, load_forecast, storage_description
from forecast_versions import display_forecast, saved_version_name


COLORS = ["#ffbe6b", "#66c7d9", "#bd9dff", "#8acc9c", "#ee94b6"]


def ordered_predictions(runs):
    return runs.assign(
        fetched_order=pd.to_datetime(runs.weather_fetched_at, utc=True),
        saved_order=pd.to_datetime(runs.saved_at, utc=True),
    ).sort_values(["target_date", "fetched_order", "saved_order", "id"], ascending=False)


def latest_daily_predictions(runs):
    """Use one latest snapshot per date without adding repeated versions together."""
    return ordered_predictions(runs).drop_duplicates("target_date", keep="first").sort_values("target_date")


def local_timestamp(value):
    return pd.to_datetime(value, utc=True).tz_convert("Asia/Manila").strftime("%d %b %Y, %I:%M %p")


def organized_records(runs):
    records = ordered_predictions(runs)
    return pd.DataFrame({
        "Forecast date": pd.to_datetime(records.target_date).dt.strftime("%d %b %Y"),
        "Version": [saved_version_name(row.weather_fetched_at, row.id) for row in records.itertuples()],
        "Weather retrieved": records.weather_fetched_at.map(local_timestamp),
        "Saved": records.saved_at.map(local_timestamp),
        "Daily energy (kWh)": records.daily_energy_kwh,
        "Peak power (kW)": records.peak_power_kw,
        "Training power unit": records.training_power_unit,
    }).reset_index(drop=True)


def render_trends(daily):
    st.subheader("Daily forecast trends")
    st.caption("Latest prediction for each date.")
    chart_data = daily.assign(
        forecast_date=pd.to_datetime(daily.target_date),
        version_name=[saved_version_name(row.weather_fetched_at, row.id) for row in daily.itertuples()],
    )
    tooltips = [
        alt.Tooltip("forecast_date:T", title="Forecast date", format="%d %b %Y"),
        alt.Tooltip("daily_energy_kwh:Q", title="Daily energy (kWh)", format=",.2f"),
        alt.Tooltip("peak_power_kw:Q", title="Peak power (kW)", format=",.2f"),
        alt.Tooltip("version_name:N", title="Saved version"),
    ]
    energy_column, peak_column = st.columns(2)
    for column, field, title, color, bars in (
        (energy_column, "daily_energy_kwh", "Predicted daily energy (kWh)", COLORS[0], True),
        (peak_column, "peak_power_kw", "Peak hourly power (kW)", COLORS[1], False),
    ):
        with column:
            st.write(title)
            chart = alt.Chart(chart_data)
            chart = chart.mark_bar(size=28, cornerRadiusTopLeft=4, cornerRadiusTopRight=4, color=color) if bars else chart.mark_line(point=True, color=color)
            st.altair_chart(chart.encode(
                x=alt.X("forecast_date:T", title="Forecast date", axis=alt.Axis(format="%d %b", tickMinStep=86400000)),
                y=alt.Y(f"{field}:Q", title=title, scale=alt.Scale(zero=True)),
                tooltip=tooltips,
            ).properties(height=270), width="stretch")
    if len(daily) == 1:
        st.info("One forecast date saved so far.")


def render_comparison(runs, store=None):
    st.subheader("Compare predictions")
    filters = st.container(border=True)
    date_column, version_column = filters.columns([1, 2])
    with date_column:
        target = st.selectbox("Forecast date", sorted(runs.target_date.unique(), reverse=True),
                              format_func=lambda day: pd.Timestamp(day).strftime("%d %b %Y"))
    versions = ordered_predictions(runs[runs.target_date == target]).set_index("id")

    def short_label(version):
        return saved_version_name(versions.loc[version].weather_fetched_at, version)

    with version_column:
        run_id = st.selectbox("Saved hourly version (latest first)", versions.index.tolist(), format_func=short_label)
    other_versions = [version for version in versions.index if version != run_id]
    compare = []
    if other_versions:
        with filters:
            compare = st.multiselect(
                "Compare with", other_versions,
                default=other_versions[:1], format_func=short_label, max_selections=4,
            )
    selected = versions.loc[run_id]
    frame = display_forecast(load_forecast(run_id, store=store)).sort_values("Hour starting")
    energy, peak, count = st.columns(3, border=True)
    energy.metric("Estimated daily energy", f"{selected.daily_energy_kwh:,.1f} kWh")
    peak.metric("Peak hourly power", f"{selected.peak_power_kw:,.1f} kW")
    count.metric("Versions for this date", len(versions))
    chart_panel = st.container(border=True)
    with chart_panel:
        measure = st.radio("Show", ["Power (kW)", "Hourly energy (kWh)", "Accumulated energy (kWh)"], horizontal=True)
    field = {"Power (kW)": "Estimated power (kW)", "Hourly energy (kWh)": "Estimated energy (kWh)",
             "Accumulated energy (kWh)": "Accumulated energy (kWh)"}[measure]
    curves = []
    # Preserve comparison order even if versions are selected in a different order.
    active_versions = [run_id, *[version for version in other_versions if version in compare]]
    for version in active_versions:
        hourly = frame.copy() if version == run_id else display_forecast(
            load_forecast(version, store=store)
        ).sort_values("Hour starting").copy()
        hourly["Accumulated energy (kWh)"] = hourly["Estimated energy (kWh)"].cumsum()
        hourly["Hour ending"] = pd.to_datetime(hourly["Hour starting"]) + pd.Timedelta(hours=1)
        curves.append(hourly.assign(
            prediction=short_label(version),
            role="Selected" if version == run_id else "Comparison",
            retrieved=local_timestamp(versions.loc[version].weather_fetched_at),
        ))
    comparison = pd.concat(curves, ignore_index=True)
    time_field = "Hour ending" if measure == "Accumulated energy (kWh)" else "Hour starting"
    version_names = [short_label(version) for version in active_versions]
    focus = alt.selection_point(fields=["prediction"], bind="legend")
    chart = alt.Chart(comparison).mark_line(
        point=alt.OverlayMarkDef(size=35, filled=True), clip=True,
    ).encode(
        x=alt.X(f"{time_field}:T", title=time_field,
                scale=alt.Scale(domain=[pd.Timestamp(target).isoformat(),
                                        (pd.Timestamp(target) + pd.Timedelta(days=1)).isoformat()]),
                axis=alt.Axis(format="%I %p", tickCount=8, labelAngle=0, labelOverlap=True, titlePadding=14)),
        y=alt.Y(f"{field}:Q", title=measure, scale=alt.Scale(zero=True)),
        color=alt.Color("prediction:N", title=None, sort=version_names,
                        scale=alt.Scale(domain=version_names, range=COLORS[:len(version_names)]),
                        legend=alt.Legend(orient="bottom", direction="vertical", columns=1,
                                          labelLimit=420, columnPadding=24, rowPadding=10,
                                          offset=20, symbolStrokeWidth=3)),
        strokeWidth=alt.StrokeWidth("role:N", scale=alt.Scale(domain=["Selected", "Comparison"], range=[3.5, 2]), legend=None),
        strokeDash=alt.StrokeDash("role:N", scale=alt.Scale(domain=["Selected", "Comparison"], range=[[1, 0], [6, 4]]), legend=None),
        opacity=alt.condition(focus, alt.value(1), alt.value(.18)),
        order=alt.Order(f"{time_field}:T"),
        tooltip=[
            alt.Tooltip("prediction:N", title="Saved prediction"),
            alt.Tooltip("role:N", title="Series"),
            alt.Tooltip("retrieved:N", title="Weather retrieved"),
            alt.Tooltip(f"{time_field}:T", title=time_field, format="%d %b %Y, %I:%M %p"),
            alt.Tooltip(f"{field}:Q", title=measure, format=",.2f"),
        ],
    ).add_params(focus).properties(height=390).configure_axis(
        gridOpacity=.12, labelPadding=8, titleFontWeight=500,
    ).configure_view(stroke=None)
    with chart_panel:
        st.altair_chart(chart, width="stretch")
    return target, run_id, selected, frame


def render_saved_data(runs, target, run_id, selected, frame):
    st.subheader("Saved forecast records")
    records = organized_records(runs)
    st.dataframe(records, hide_index=True, width="stretch", column_config={
        "Daily energy (kWh)": st.column_config.NumberColumn(format="%.2f"),
        "Peak power (kW)": st.column_config.NumberColumn(format="%.2f"),
    })
    st.download_button("Download forecast records CSV", records.to_csv(index=False).encode("utf-8-sig"),
                       file_name="solarcast-forecast-records.csv", mime="text/csv")
    version_name = saved_version_name(selected.weather_fetched_at, run_id)
    st.subheader(f"Hourly details · {version_name}")
    displayed = frame.copy()
    displayed["Hour starting"] = pd.to_datetime(frame["Hour starting"]).dt.strftime("%I:%M %p")
    numeric_columns = {column: st.column_config.NumberColumn(format="%.2f") for column in frame.select_dtypes("number").columns}
    st.dataframe(displayed, hide_index=True, width="stretch", column_config=numeric_columns)
    st.download_button("Download saved forecast CSV", frame.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"Forecast for {target} - {version_name}.csv", mime="text/csv")
    with st.expander("Prediction information"):
        st.write(f"Saved version: {version_name}")
        st.write(f"Weather retrieved: {local_timestamp(selected.weather_fetched_at)}")
        st.write(f"Saved: {local_timestamp(selected.saved_at)}")
        st.write(f"Location: {selected.latitude:.4f}, {selected.longitude:.4f}")
        st.write(f"Training power unit: {selected.training_power_unit}")
        st.caption(f"Model version: {selected.model_version}")


def render_forecast_history(store=None):
    st.title("Forecast history")
    st.caption("Model estimates · One saved version per hour")
    try:
        runs = list_forecasts(store=store)
        if runs.empty:
            st.info("No saved forecasts yet. Open Next-day forecast to create and save one.")
            return
        with st.container(border=True):
            locations = runs[["latitude", "longitude"]].drop_duplicates()
            if len(locations) > 1:
                location = st.selectbox("Location", list(locations.itertuples(index=False, name=None)),
                                       format_func=lambda point: f"{point[0]:.4f}, {point[1]:.4f}")
                runs = runs[(runs.latitude == location[0]) & (runs.longitude == location[1])]
            units = sorted(runs.training_power_unit.unique())
            if len(units) > 1:
                unit = st.selectbox("Training power unit", units,
                                   index=units.index("kW") if "kW" in units else 0,
                                   help="Keep forecasts made with the same training-unit assumption together.")
                runs = runs[runs.training_power_unit == unit]
            dates = pd.to_datetime(runs.target_date).dt.date
            range_start = datetime.now(timezone(timedelta(hours=8))).date()
            range_end = range_start + timedelta(days=6)
            date_range = st.date_input("Forecast date range", value=(range_start, range_end),
                                       min_value=min(dates.min(), range_start),
                                       max_value=max(dates.max(), range_end), format="DD/MM/YYYY")
            if len(date_range) != 2:
                st.info("Choose both a start date and an end date to view forecast history.")
                return
            runs = runs[(dates >= date_range[0]) & (dates <= date_range[1])]
        if runs.empty:
            st.info("No saved forecasts in this date range. Choose another range.")
            return
        daily = latest_daily_predictions(runs)
        dates_count, versions_count, energy, peak = st.columns(4, border=True)
        dates_count.metric("Forecast dates", len(daily))
        versions_count.metric("Saved versions", len(runs))
        energy.metric("Average predicted daily energy", f"{daily.daily_energy_kwh.mean():,.1f} kWh")
        peak.metric("Highest predicted peak", f"{daily.peak_power_kw.max():,.1f} kW")
        trends_tab, comparison_tab, data_tab = st.tabs(["Trends", "Compare predictions", "Saved data"])
        with trends_tab:
            render_trends(daily)
        with comparison_tab:
            target, run_id, selected, frame = render_comparison(runs, store=store)
        with data_tab:
            render_saved_data(runs, target, run_id, selected, frame)
    except StoreError as error:
        st.error(str(error))
    except (sqlite3.Error, OSError, ValueError):
        st.error("Unable to read forecast history. Check that the database is available and try again.")
