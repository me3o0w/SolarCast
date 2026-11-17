"""Check forecast interval alignment, units, and missing-data handling."""
import sys
from pathlib import Path
from datetime import date
import unittest
from unittest.mock import Mock

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from forecast import predict_forecast


class ForecastTests(unittest.TestCase):
    def setUp(self):
        self.day = date(2026, 11, 18)
        self.payload = {
            "hourly_units": {"temperature_2m": "°C", "shortwave_radiation": "W/m²"},
            "hourly": {
                "time": pd.date_range(self.day, periods=48, freq="h").strftime("%Y-%m-%dT%H:%M").tolist(),
                "temperature_2m": [30.] * 48,
                "shortwave_radiation": [800.] * 48,
            },
        }
        self.power = Mock()
        self.power.predict.return_value = np.full(24, 2000.)
        self.temperature = Mock()
        self.temperature.predict.return_value = np.full(24, 40.)

    def test_full_day_units_and_midpoint_features(self):
        result = predict_forecast(self.payload, self.day, self.power, self.temperature, "W")
        self.assertEqual(len(result), 24)
        self.assertEqual(result.iloc[0, 0], pd.Timestamp("2026-11-18 00:00"))
        self.assertEqual(result.iloc[-1, 0], pd.Timestamp("2026-11-18 23:00"))
        self.assertEqual(result["Estimated energy (kWh)"].sum(), 48.)
        features = self.power.predict.call_args.args[0]
        self.assertAlmostEqual(features.IRRADIATION.iloc[0], .8)
        self.assertEqual(features.HOUR.iloc[-1], 23)
        self.assertEqual(features.MINUTE.iloc[0], 30)

    def test_night_and_negative_output_are_zero(self):
        self.payload["hourly"]["shortwave_radiation"][1] = 0.
        self.power.predict.return_value[1] = -20.
        result = predict_forecast(self.payload, self.day, self.power, self.temperature)
        self.assertEqual(result["Estimated power (kW)"].iloc[:2].tolist(), [0., 0.])

    def test_missing_final_midnight_is_rejected(self):
        self.payload["hourly"]["temperature_2m"][24] = None
        with self.assertRaises(ValueError):
            predict_forecast(self.payload, self.day, self.power, self.temperature)

    def test_duplicate_hours_are_rejected(self):
        self.payload["hourly"]["time"][2] = self.payload["hourly"]["time"][1]
        with self.assertRaises(ValueError):
            predict_forecast(self.payload, self.day, self.power, self.temperature)


if __name__ == "__main__":
    unittest.main()
