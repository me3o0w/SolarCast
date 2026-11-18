"""Account prediction records and their comparison chart."""

from datetime import timezone
from uuid import uuid4

import altair as alt
import pandas as pd
import streamlit as st

from supabase_store import StoreError


FIELDS = {
    "saved_at": "Time",
    "predicted_for": "Prediction for",
    "predicted_power": "Predicted AC power",
    "sunlight": "Sunlight (W/m²)",
    "air_temperature": "Air temperature (°C)",
    "panel_temperature": "Panel temperature (°C)",
}


def overview_hour(weather_fetched_at):
    return weather_fetched_at.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)


def save_prediction(store, *, source, predicted_for, power, sunlight, ambient, module, weather_fetched_at=None):
    snapshot_key = (
        f"overview:{overview_hour(weather_fetched_at).isoformat()}"
        if weather_fetched_at is not None else f"manual:{uuid4()}"
    )
    try:
        store.request(
            "POST", {"on_conflict": "owner_id,snapshot_key", "select": "id"},
            {
                "snapshot_key": snapshot_key, "source": source, "predicted_for": predicted_for.isoformat(),
                "predicted_power": float(power), "sunlight": float(sunlight),
                "air_temperature": float(ambient), "panel_temperature": float(module),
            },
            prefer="resolution=ignore-duplicates,return=representation,missing=default",
        )
    except StoreError as error:
        st.warning(f"The prediction is ready but could not be saved. {error}")
        return False
    return True


def render_prediction_history(store):
    st.title("Prediction history")
    try:
        rows = store.list(columns=("id", *FIELDS), order="saved_at.desc,id.desc")
    except StoreError as error:
        st.error(str(error))
        return
    if not rows:
        st.info("No saved predictions yet. Open Overview or run a Manual prediction to save one.")
        return

    history = pd.DataFrame(rows)
    for column in ("saved_at", "predicted_for"):
        history[column] = pd.to_datetime(history[column], utc=True, format="ISO8601").dt.tz_convert("Asia/Manila")
    comparison = history.loc[:, ["id", *FIELDS]].copy()
    comparison["prediction_date"] = comparison["predicted_for"].dt.strftime("%Y-%m-%d")
    comparison["saved_at"] = comparison["saved_at"].dt.floor("h")
    time_scale = alt.Scale(type="utc")
    first_day = comparison["saved_at"].min().normalize()
    if first_day == comparison["saved_at"].max().normalize():
        time_scale.domain = [
            alt.DateTime(year=day.year, month=day.month, date=day.day, utc=True)
            for day in (first_day, first_day + pd.Timedelta(days=1))
        ]
    power_scale = alt.Scale(zero=True)
    if comparison["predicted_power"].max() == 0:
        power_scale.domain = [0, 1]
    # Use a UTC chart scale for Manila wall time so the axis is independent of the browser time zone.
    comparison["chart_time"] = comparison["saved_at"].dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    comparison["hours_in_series"] = comparison.groupby("prediction_date")["chart_time"].transform("nunique")
    for column in ("saved_at", "predicted_for"):
        comparison[column] = comparison[column].dt.strftime("%d %b %Y, %I:%M %p")
    st.caption("Times shown in Asia/Manila")

    st.subheader("Compare predictions")
    chart = alt.Chart(alt.InlineData(values=comparison.to_dict("records"))).encode(
        x=alt.X("chart_time:T", title=FIELDS["saved_at"], scale=time_scale,
                axis=alt.Axis(
                    tickMinStep=3_600_000, tickCount=12, grid=False,
                    labelExpr="utchours(datum.value) === 0 ? utcFormat(datum.value, '%a %d') : utcFormat(datum.value, '%I %p')",
                )),
        y=alt.Y("predicted_power:Q", title=FIELDS["predicted_power"], scale=power_scale,
                axis=alt.Axis(grid=True, tickCount=9, format="~s")),
        order=[alt.Order("chart_time:T"), alt.Order("id:Q")],
        color=alt.Color(
            "prediction_date:N", title="Prediction date",
            scale=alt.Scale(range=["#79c5ff", "#ffbe6b", "#5dd4b5", "#c2a4ff", "#ff93aa", "#f2df84"]),
            legend=alt.Legend(orient="top", labelColor="#dbe6f3", titleColor="#dbe6f3"),
        ),
        tooltip=[
            alt.Tooltip(f"{field}:N", title=FIELDS[field])
            for field in ("predicted_for", "saved_at")
        ] + [
            alt.Tooltip(f"{field}:Q", title=FIELDS[field], format=",.2f")
            for field in ("predicted_power", "sunlight", "air_temperature", "panel_temperature")
        ],
    )
    lines = chart.mark_line(strokeWidth=2)
    hover = alt.selection_point(fields=["id"], nearest=True, on="pointerover", clear="pointerout", empty=False)
    points = chart.mark_circle(size=42).encode(
        opacity=alt.when(hover).then(alt.value(1)).when(
            alt.datum.hours_in_series == 1
        ).then(alt.value(1)).otherwise(alt.value(0)),
    ).add_params(hover)
    comparison_chart = (lines + points).properties(height=320, background="#0e1621").configure_view(
        stroke=None
    ).configure_axis(
        domain=False, ticks=False, labelPadding=12, labelColor="#dbe6f3", titleColor="#dbe6f3",
        gridColor="#293440",
    )
    st.altair_chart(comparison_chart, width="stretch", theme=None)

    st.subheader("Saved results")
    hourly_results = comparison.drop_duplicates(subset="chart_time")
    st.dataframe(
        hourly_results[["prediction_date", *FIELDS]].rename(columns={"prediction_date": "Prediction date", **FIELDS}),
        hide_index=True,
    )
