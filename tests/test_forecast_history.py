"""Saved history graphs must compare real versions without double-counting dates."""

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import forecast_history as history


class HistoryGraphTests(unittest.TestCase):
    def setUp(self):
        clock = patch.object(history, "datetime", wraps=datetime)
        self.clock = clock.start()
        self.addCleanup(clock.stop)
        self.clock.now.return_value = datetime(2026, 11, 18, 0, 15, tzinfo=timezone(timedelta(hours=8)))
        self.runs = pd.DataFrame([
            {"id": 1, "target_date": "2026-11-17", "weather_fetched_at": "2026-11-16T12:00:00+08:00",
             "saved_at": "2026-11-16T04:01:00Z", "daily_energy_kwh": 24., "peak_power_kw": 1.},
            {"id": 2, "target_date": "2026-11-18", "weather_fetched_at": "2026-11-17T04:00:00Z",
             "saved_at": "2026-11-17T04:01:00Z", "daily_energy_kwh": 48., "peak_power_kw": 2.},
            {"id": 3, "target_date": "2026-11-18", "weather_fetched_at": "2026-11-17T13:00:00+08:00",
             "saved_at": "2026-11-17T05:01:00Z", "daily_energy_kwh": 72., "peak_power_kw": 3.},
        ]).assign(latitude=8.4542, longitude=124.6319, training_power_unit="kW", model_version="v1")

    def frame(self, version, *, store=None):
        day = self.runs.set_index("id").loc[version].target_date
        return pd.DataFrame({
            "Hour starting (Asia/Manila)": pd.date_range(day, periods=24, freq="h"),
            "Estimated power (kW)": [float(version)] * 24,
            "Estimated energy (kWh)": [float(version)] * 24,
        })

    def test_daily_graph_uses_latest_weather_version_per_date_in_date_order(self):
        # 13:00 +08:00 is later than 04:00 Z despite their string sort order.
        result = history.latest_daily_predictions(self.runs.iloc[::-1])
        self.assertEqual(result.id.tolist(), [1, 3])
        self.assertEqual(result.daily_energy_kwh.tolist(), [24., 72.])

    def test_version_names_are_unique_and_stable_when_records_are_filtered(self):
        records = history.organized_records(self.runs)
        self.assertTrue(records.Version.is_unique)
        subset = history.organized_records(self.runs[self.runs.id == 2])
        self.assertEqual(subset.Version.iloc[0], "Afternoon forecast - 17 Nov 2026, 12 PM (#2)")
        self.assertIn(subset.Version.iloc[0], records.Version.tolist())

    def test_time_names_use_local_hour_and_remain_distinct_for_same_hour(self):
        for utc_time, expected in (
            ("2026-11-17T21:00:00Z", "Morning forecast - 18 Nov 2026, 5 AM"),
            ("2026-11-18T04:00:00Z", "Afternoon forecast - 18 Nov 2026, 12 PM"),
            ("2026-11-18T09:00:00Z", "Evening forecast - 18 Nov 2026, 5 PM"),
            ("2026-11-18T16:00:00Z", "Night forecast - 19 Nov 2026, 12 AM"),
        ):
            with self.subTest(time=utc_time):
                self.assertEqual(history.saved_version_name(utc_time, 7), f"{expected} (#7)")
                self.assertNotEqual(history.saved_version_name(utc_time, 7), history.saved_version_name(utc_time, 8))

    def test_graphs_allow_older_version_and_date_selection(self):
        with patch.object(history, "list_forecasts", return_value=self.runs), patch.object(
            history, "load_forecast", side_effect=self.frame
        ) as load, patch.object(history, "storage_description", return_value="Saved history"):
            app = AppTest.from_string("from forecast_history import render_forecast_history\nrender_forecast_history()").run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(len(app.get("vega_lite_chart")), 3)
            self.assertEqual([tab.label for tab in app.tabs], ["Trends", "Compare predictions", "Saved data"])
            spec = json.loads(app.get("vega_lite_chart")[2].proto.spec)
            self.assertEqual(spec["encoding"]["x"]["axis"]["format"], "%I %p")

            app.selectbox[0].select("2026-11-18").run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(app.selectbox[1].value, 3)
            self.assertEqual(app.selectbox[1].options[0], "Afternoon forecast - 17 Nov 2026, 1 PM (#3)")
            self.assertEqual(app.multiselect[0].value, [2])
            self.assertEqual([call.args[0] for call in load.call_args_list][-2:], [3, 2])
            app.selectbox[1].select(2).run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(next(m.value for m in app.metric if m.label == "Estimated daily energy"), "48.0 kWh")

    def test_training_power_unit_defaults_to_kw_and_can_be_changed(self):
        watts_run = self.runs.iloc[[1]].assign(id=4, training_power_unit="W")
        self.runs = pd.concat([self.runs, watts_run], ignore_index=True)
        with patch.object(history, "list_forecasts", return_value=self.runs), patch.object(
            history, "load_forecast", side_effect=self.frame
        ), patch.object(history, "storage_description", return_value="Saved history"):
            app = AppTest.from_string("from forecast_history import render_forecast_history\nrender_forecast_history()").run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(app.selectbox[0].value, "kW")
            self.assertEqual(app.dataframe[0].value["Training power unit"].unique().tolist(), ["kW"])

            app.selectbox[0].select("W").run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(app.dataframe[0].value["Training power unit"].unique().tolist(), ["W"])

    def test_date_filter_updates_summaries_and_saved_records(self):
        with patch.object(history, "list_forecasts", return_value=self.runs), patch.object(
            history, "load_forecast", side_effect=self.frame
        ), patch.object(history, "storage_description", return_value="Saved history"):
            app = AppTest.from_string("from forecast_history import render_forecast_history\nrender_forecast_history()").run()
            app.date_input[0].set_value((date(2026, 11, 18), date(2026, 11, 18))).run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(next(m.value for m in app.metric if m.label == "Forecast dates"), "1")
            self.assertEqual(next(m.value for m in app.metric if m.label == "Saved versions"), "2")
            self.assertEqual(next(m.value for m in app.metric if m.label == "Average predicted daily energy"), "72.0 kWh")
            records = app.dataframe[0].value
            self.assertEqual(records["Version"].tolist(), ["Afternoon forecast - 17 Nov 2026, 1 PM (#3)", "Afternoon forecast - 17 Nov 2026, 12 PM (#2)"])
            self.assertTrue(any("Afternoon forecast - 17 Nov 2026, 1 PM (#3)" in heading.value for heading in app.subheader))
            self.assertTrue(all("PM" in value for value in records["Weather retrieved"]))
            self.assertEqual(app.dataframe[1].value.iloc[0]["Hour starting"], "12:00 AM")
            self.assertFalse(any("Asia" in column or "Manila" in column for column in records.columns))

    def test_default_range_is_seven_calendar_days_and_excludes_older_records(self):
        older = self.runs.iloc[[0]].assign(id=4, target_date="2026-11-01")
        self.runs = pd.concat([self.runs, older], ignore_index=True)
        with patch.object(history, "list_forecasts", return_value=self.runs), patch.object(
            history, "load_forecast", side_effect=self.frame
        ):
            app = AppTest.from_string("from forecast_history import render_forecast_history\nrender_forecast_history()").run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(app.date_input[0].value, (date(2026, 11, 18), date(2026, 11, 24)))
            self.assertEqual(len(app.dataframe[0].value), 2)
            self.assertEqual(self.clock.now.call_args.args[0], timezone(timedelta(hours=8)))
            self.assertNotIn("Afternoon forecast - 16 Nov 2026, 12 PM (#4)", app.dataframe[0].value.Version.tolist())
            # Older records remain accessible through the date picker.
            app.date_input[0].set_value((date(2026, 11, 1), date(2026, 11, 1))).run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(app.dataframe[0].value.Version.tolist(), ["Afternoon forecast - 16 Nov 2026, 12 PM (#4)"])

    def test_accumulated_energy_is_labeled_with_hour_ending(self):
        with patch.object(history, "list_forecasts", return_value=self.runs), patch.object(
            history, "load_forecast", side_effect=self.frame
        ), patch.object(history, "storage_description", return_value="Saved history"):
            app = AppTest.from_string("from forecast_history import render_forecast_history\nrender_forecast_history()").run()
            app.radio[0].set_value("Accumulated energy (kWh)").run()
            self.assertEqual(len(app.exception), 0)
            spec = json.loads(app.get("vega_lite_chart")[2].proto.spec)
            self.assertEqual(spec["encoding"]["x"]["field"], "Hour ending")
            self.assertEqual(spec["encoding"]["y"]["field"], "Accumulated energy (kWh)")

    def test_empty_and_single_date_histories_do_not_invent_predictions(self):
        for runs in (self.runs.iloc[:0], self.runs.iloc[1:2]):
            with self.subTest(records=len(runs)), patch.object(history, "list_forecasts", return_value=runs), patch.object(
                history, "load_forecast", side_effect=self.frame
            ), patch.object(history, "storage_description", return_value="Saved history"):
                app = AppTest.from_string("from forecast_history import render_forecast_history\nrender_forecast_history()").run()
                self.assertEqual(len(app.exception), 0)
                self.assertEqual(len(app.multiselect), 0)
                if runs.empty:
                    self.assertIn("No saved forecasts yet", app.info[0].value)
                    self.assertEqual(len(app.get("vega_lite_chart")), 0)
                else:
                    self.assertTrue(any("One forecast date saved" in c.value for c in app.info))
                    self.assertEqual(len(app.get("vega_lite_chart")), 3)

    def test_past_only_history_keeps_today_range_without_inventing_forecasts(self):
        with patch.object(history, "list_forecasts", return_value=self.runs.iloc[:1]), patch.object(
            history, "load_forecast"
        ) as load:
            app = AppTest.from_string("from forecast_history import render_forecast_history\nrender_forecast_history()").run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(app.date_input[0].value, (date(2026, 11, 18), date(2026, 11, 24)))
            self.assertIn("No saved forecasts in this date range", app.info[0].value)
            load.assert_not_called()


if __name__ == "__main__":
    unittest.main()
