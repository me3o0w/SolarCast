"""Exercise the actual refresh and retry buttons without network or intro delays."""

from pathlib import Path
import importlib
import sys
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
            ):
                self.check_refresh_buttons(get, sleep)

    def check_refresh_buttons(self, get, sleep):
            st.cache_data.clear()
            app = AppTest.from_file(str(APP_DIR / "app.py")).run()
            self.assertEqual(len(app.exception), 0)
            self.assertTrue(sleep.called, "Opening the app should play the intro")
            self.assertEqual(get.call_count, 1)

            for expected_calls in (2, 3):
                sleep.reset_mock()
                app.button(key="refresh_weather").click().run()
                self.assertEqual(len(app.exception), 0)
                self.assertEqual(get.call_count, expected_calls)
                sleep.assert_not_called()

            get.side_effect = requests.RequestException("Weather unavailable")
            app.button(key="refresh_weather").click().run()
            self.assertEqual(len(app.exception), 0)
            sleep.assert_not_called()

            get.side_effect = None
            app.button(key="retry_weather").click().run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(get.call_count, 5)
            sleep.assert_not_called()
            self.assertTrue(app.session_state["solar_intro_shown"])
            st.cache_data.clear()


if __name__ == "__main__":
    unittest.main()
