"""Bounded weather requests shared by current conditions and forecasts."""

import math

import requests

from config import API_URL


def get_weather_json(url, params=None):
    """Retry transient failures once, with no added sleep or animation delay."""
    for attempt in range(2):
        try:
            response = requests.get(url, params=params, timeout=(4, 8))
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or payload.get("error"):
                raise ValueError("Weather service returned an invalid response.")
            return payload
        except requests.HTTPError as error:
            status = error.response.status_code if error.response is not None else None
            if attempt or status not in (500, 502, 503, 504):
                raise
        except (requests.Timeout, requests.ConnectionError):
            if attempt:
                raise


def get_current_conditions():
    current = get_weather_json(API_URL)["current"]
    temperature = current["temperature_2m"]
    radiation = current["shortwave_radiation"]
    if (isinstance(temperature, bool) or isinstance(radiation, bool) or
            temperature is None or radiation is None):
        raise ValueError("Current weather readings are missing.")
    temperature, radiation = float(temperature), float(radiation)
    if not math.isfinite(temperature) or not math.isfinite(radiation) or radiation < 0:
        raise ValueError("Current weather readings are invalid.")
    return temperature, radiation
