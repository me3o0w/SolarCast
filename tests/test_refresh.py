"""Exercise the actual refresh and retry buttons without network or intro delays."""

from pathlib import Path
import importlib
from datetime import datetime, timedelta, timezone
import sys
from time import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import requests
import streamlit as st
from streamlit.testing.v1 import AppTest


APP_DIR = Path(__file__).resolve().parents[1] / "app"


class RefreshTests(unittest.TestCase):
    def test_refresh_and_retry_fetch_weather_without_intro_delays(self):
        models = SimpleNamespace(
            model=Mock(predict=Mock(return_value=[500.0])),
            module_temp_model=Mock(predict=Mock(return_value=[35.0])),
        )
        response = Mock()
        response.json.return_value = {
            "current": {"temperature_2m": 30.0, "shortwave_radiation": 600.0}
        }
        with patch.dict(sys.modules, model_loader=models), patch.object(
            sys, "path", [str(APP_DIR), *sys.path]
        ), patch("requests.get", return_value=response) as get:
            loading = importlib.import_module("loading")
            with patch.object(loading, "sleep") as sleep, patch(
                "importlib.reload", side_effect=lambda module: module
            ), patch("auth.configured_auth", return_value=SimpleNamespace(
                project_url="https://example.supabase.co", key="sb_publishable_test",
            )), patch("prediction_history.save_prediction", return_value=True) as save, patch(
                "prediction_history.overview_hour", return_value=datetime(2026, 11, 19, tzinfo=timezone.utc)
            ) as hour:
                self.check_refresh_buttons(get, sleep, save, hour)

    def check_refresh_buttons(self, get, sleep, save, hour):
            st.cache_data.clear()
            app = AppTest.from_file(str(APP_DIR / "app.py"))
            app.session_state["solar_auth_session"] = SimpleNamespace(
                email="test@example.com", expires_at=time() + 3600, access_token="user-token",
            )
            app.run()
            self.assertEqual(len(app.exception), 0)
            self.assertTrue(sleep.called, "Opening the app should play the intro")
            self.assertEqual(get.call_count, 1)
            self.assertEqual(save.call_count, 1)
            self.assertEqual(save.call_args.kwargs["source"], "Overview")

            for expected_calls in (2, 3):
                sleep.reset_mock()
                app.button(key="refresh_weather").click().run()
                self.assertEqual(len(app.exception), 0)
                self.assertEqual(get.call_count, expected_calls)
                sleep.assert_called_once()
                self.assertLessEqual(sleep.call_args.args[0], 1.2)

            sleep.reset_mock()
            app.run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(get.call_count, 3)
            self.assertEqual(save.call_count, 1)
            sleep.assert_not_called()

            get.side_effect = requests.RequestException("Weather unavailable")
            app.button(key="refresh_weather").click().run()
            self.assertEqual(len(app.exception), 0)
            self.assertIn("Showing readings retrieved", app.warning[0].value)
            self.assertEqual(save.call_count, 1)
            sleep.assert_called_once()

            # Expired readings must not masquerade as current weather.
            sleep.reset_mock()
            app.session_state["solar_last_weather"] = (30., 600., datetime.now(timezone.utc) - timedelta(minutes=16))
            app.button(key="refresh_weather").click().run()
            self.assertEqual(len(app.exception), 0)
            self.assertIn("Current weather is unavailable", app.warning[0].value)
            sleep.assert_called_once()

            sleep.reset_mock()
            get.side_effect = None
            hour.return_value += timedelta(hours=1)
            app.button(key="retry_weather").click().run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(get.call_count, 6)
            self.assertEqual(save.call_count, 2)
            sleep.assert_called_once()
            self.assertTrue(app.session_state["solar_intro_shown"])

            app.button(key="solar_nav_About this").click().run()
            self.assertEqual(len(app.exception), 0)
            for _ in range(2):
                sleep.reset_mock()
                app.button(key="solar_nav_Overview").click().run()
                self.assertEqual(len(app.exception), 0)
                sleep.assert_called_once()
                self.assertLessEqual(sleep.call_args.args[0], 1.2)
                self.assertEqual(get.call_count, 6)

            st.cache_data.clear()


if __name__ == "__main__":
    unittest.main()
