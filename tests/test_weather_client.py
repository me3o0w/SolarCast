"""Transient failures recover without unbounded retries or fake readings."""

from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from weather_client import get_weather_json, get_current_conditions


class WeatherClientTests(unittest.TestCase):
    def response(self, payload):
        return Mock(json=Mock(return_value=payload))

    def test_timeout_recovers_on_second_attempt_without_sleeping(self):
        response = self.response({"current": {"temperature_2m": 30, "shortwave_radiation": 600}})
        with patch("weather_client.requests.get", side_effect=[requests.Timeout(), response]) as get, patch("time.sleep") as sleep:
            self.assertEqual(get_current_conditions(), (30., 600.))
            self.assertEqual(get.call_count, 2)
            self.assertEqual(get.call_args.kwargs["timeout"], (4, 8))
            sleep.assert_not_called()

    def test_server_errors_retry_but_bad_requests_and_rate_limits_do_not(self):
        for status in (400, 401, 429, 500, 502, 503, 504):
            failure = requests.HTTPError(response=Mock(status_code=status))
            with self.subTest(status=status), patch("weather_client.requests.get", side_effect=[failure, self.response({"ok": True})]) as get:
                if status >= 500:
                    self.assertEqual(get_weather_json("https://example.com"), {"ok": True})
                    self.assertEqual(get.call_count, 2)
                else:
                    with self.assertRaises(requests.HTTPError):
                        get_weather_json("https://example.com")
                    self.assertEqual(get.call_count, 1)

    def test_network_failures_stop_after_two_attempts(self):
        for failure in (requests.Timeout(), requests.ConnectionError()):
            with self.subTest(failure=type(failure).__name__), patch("weather_client.requests.get", side_effect=failure) as get:
                with self.assertRaises(type(failure)):
                    get_weather_json("https://example.com")
                self.assertEqual(get.call_count, 2)

    def test_invalid_payloads_are_not_treated_as_weather(self):
        for payload in (None, [], {"error": True}):
            with self.subTest(payload=payload), patch("weather_client.requests.get", return_value=self.response(payload)):
                with self.assertRaises(ValueError):
                    get_weather_json("https://example.com")

    def test_missing_or_nonfinite_current_readings_are_rejected(self):
        for temperature, radiation in ((None, 1), (30, None), (float("nan"), 0), (30, float("inf")), (30, -1), (True, 0)):
            payload = {"current": {"temperature_2m": temperature, "shortwave_radiation": radiation}}
            with self.subTest(temperature=temperature, radiation=radiation), patch("weather_client.requests.get", return_value=self.response(payload)):
                with self.assertRaises(ValueError):
                    get_current_conditions()


if __name__ == "__main__":
    unittest.main()
