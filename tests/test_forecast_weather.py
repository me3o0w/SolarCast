"""Forecast refreshes preserve recent valid weather, but reject stale fallback."""

from datetime import datetime, timedelta
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import requests
import streamlit as st
from streamlit.testing.v1 import AppTest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import forecast


class ForecastWeatherTests(unittest.TestCase):
    def test_recent_fallback_retains_fetch_time_and_expired_fallback_is_rejected(self):
        day = datetime.now(forecast.LOCAL_TIME).date() + timedelta(days=1)
        fetched = datetime.now(forecast.LOCAL_TIME).isoformat()
        payload = {
            "hourly_units": {"temperature_2m": "°C", "shortwave_radiation": "W/m²"},
            "hourly": {
                "time": pd.date_range(day, periods=48, freq="h").strftime("%Y-%m-%dT%H:%M").tolist(),
                "temperature_2m": [30.] * 48,
                "shortwave_radiation": [800.] * 48,
            },
        }
        with patch.object(forecast, "fetch_forecast", return_value=(payload, fetched)) as fetch, patch(
            "supabase_store.requests.request"
        ) as database_request, patch.object(
            forecast, "model", Mock(predict=Mock(return_value=np.full(24, 2.)))
        ), patch.object(forecast, "module_temp_model", Mock(predict=Mock(return_value=np.full(24, 35.)))), patch(
            "loading.sleep"
        ) as delay, patch.object(forecast, "PageLoading", wraps=forecast.PageLoading) as loader:
            app = AppTest.from_string("from forecast import render_forecast\nrender_forecast()").run()
            self.assertEqual(len(app.exception), 0)
            loader.assert_not_called()

            app.button(key="refresh_forecast").click().run()
            self.assertEqual(len(app.exception), 0)
            loader.assert_called_once_with("Next-day forecast", message="Refreshing tomorrow’s solar outlook")
            fetch.clear.assert_called_once()
            delay.assert_called_once()

            fetch.side_effect = requests.Timeout()
            app.button(key="refresh_forecast").click().run()
            self.assertEqual(len(app.exception), 0)
            self.assertIn("Showing the forecast using weather retrieved", app.warning[0].value)
            self.assertEqual(app.session_state["solar_last_forecast"][4], fetched)

            expired = datetime.now(forecast.LOCAL_TIME) - timedelta(hours=3)
            app.session_state["solar_last_forecast"] = (day, forecast.LATITUDE, forecast.LONGITUDE, payload, expired.isoformat())
            app.button(key="refresh_forecast").click().run()
            self.assertEqual(len(app.exception), 0)
            self.assertIn("unavailable or incomplete", app.warning[0].value)
            database_request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
