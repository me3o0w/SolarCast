from datetime import date
from pathlib import Path
import sys
import tempfile
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from forecast_store import save_forecast, list_forecasts, load_forecast, connect


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "history.db"
        self.frame = pd.DataFrame({
            "Hour starting (Asia/Manila)": pd.date_range("2026-11-18", periods=24, freq="h"),
            "Estimated power (kW)": [2.] * 24,
            "Estimated energy (kWh)": [2.] * 24,
        })

    def save(self, fetched="2026-11-17T12:00:00+08:00", unit="kW", model="v1"):
        return save_forecast(self.frame, date(2026, 11, 18), fetched,
                             8.4542, 124.6319, unit, model, self.path)

    def test_persists_after_reopening_and_round_trips(self):
        run_id = self.save()
        runs = list_forecasts(self.path)
        self.assertEqual(runs.iloc[0].daily_energy_kwh, 48.)
        self.assertEqual(runs.iloc[0].target_date, "2026-11-18")
        pd.testing.assert_frame_equal(load_forecast(run_id, self.path), self.frame, check_dtype=False)

    def test_cached_rerun_does_not_duplicate(self):
        self.assertEqual(self.save(), self.save())
        self.assertEqual(len(list_forecasts(self.path)), 1)

    def test_same_hour_keeps_first_forecast_even_when_weather_changes(self):
        first = self.save(fetched="2026-11-17T12:00:00+08:00")
        self.frame["Estimated power (kW)"] = 3.
        self.frame["Estimated energy (kWh)"] = 3.
        self.assertEqual(self.save(fetched="2026-11-17T12:59:59.999999+08:00"), first)
        self.assertEqual(load_forecast(first, self.path)["Estimated energy (kWh)"].sum(), 48.)
        second = self.save(fetched="2026-11-17T13:00:00+08:00")
        self.assertNotEqual(second, first)
        self.assertEqual(len(list_forecasts(self.path)), 2)
        self.assertEqual(load_forecast(second, self.path)["Estimated energy (kWh)"].sum(), 72.)

    def test_equivalent_timezone_offsets_share_one_hour(self):
        first = self.save(fetched="2026-11-17T12:05:00+08:00")
        self.assertEqual(self.save(fetched="2026-11-17T04:55:00Z"), first)

    def test_existing_same_hour_records_are_preserved_and_grouped(self):
        first = self.save()
        with connect(self.path) as db:
            db.execute("UPDATE forecast_runs SET snapshot_key = ? WHERE id = ?", ("a" * 64, first))
            db.execute("""INSERT INTO forecast_runs
                (snapshot_key, target_date, saved_at, weather_fetched_at, latitude, longitude,
                 training_power_unit, model_version, daily_energy_kwh, peak_power_kw, hourly_json)
                SELECT ?, target_date, saved_at, ?, latitude, longitude,
                 training_power_unit, model_version, daily_energy_kwh, peak_power_kw, hourly_json
                FROM forecast_runs WHERE id = ?""", ("b" * 64, "2026-11-17T12:30:00+08:00", first))
        self.assertEqual(self.save(fetched="2026-11-17T12:45:00+08:00"), first)
        self.assertEqual(list_forecasts(self.path).id.tolist(), [first])
        with connect(self.path) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM forecast_runs").fetchone()[0], 2)

    def test_refresh_and_changed_assumptions_preserve_versions(self):
        first = self.save()
        self.save(fetched="2026-11-17T13:00:00+08:00")
        self.save(unit="W")
        self.save(model="v2")
        self.assertEqual(len(list_forecasts(self.path)), 4)
        self.assertEqual(len(load_forecast(first, self.path)), 24)

    def test_empty_history_and_missing_run(self):
        self.assertTrue(list_forecasts(self.path).empty)
        with self.assertRaises(ValueError):
            load_forecast(123, self.path)

    def test_partial_day_is_not_stored(self):
        self.frame = self.frame.iloc[:12]
        with self.assertRaises(ValueError):
            self.save()
        self.assertTrue(list_forecasts(self.path).empty)


if __name__ == "__main__":
    unittest.main()
