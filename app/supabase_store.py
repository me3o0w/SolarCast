"""Server-side Supabase forecast storage using the existing requests dependency."""

import base64
import json
import os
from pathlib import Path
import tomllib
from urllib.parse import urlsplit

import requests

from forecast_versions import hourly_slot


TABLE = "solarcast_forecast_runs"
ACCOUNT_TABLE = "solarcast_account_forecast_runs"
PREDICTION_TABLE = "solarcast_account_predictions"
SUMMARY_COLUMNS = [
    "id", "target_date", "weather_fetched_at", "saved_at", "latitude", "longitude",
    "training_power_unit", "model_version", "daily_energy_kwh", "peak_power_kw",
]
SECRETS_PATH = Path(__file__).resolve().parents[1] / ".streamlit" / "secrets.toml"


class StoreError(RuntimeError):
    """A safe-to-display configuration or storage error, without credentials."""


def configured_store():
    """Use Supabase when configured; incomplete configuration must never fall back."""
    settings = {}
    if SECRETS_PATH.exists():
        try:
            with SECRETS_PATH.open("rb") as file:
                settings = tomllib.load(file).get("supabase", {})
        except (OSError, ValueError):
            raise StoreError("Unable to read database settings in .streamlit/secrets.toml.") from None
    if not isinstance(settings, dict):
        raise StoreError("The supabase secrets section must contain url and secret_key.")
    url = os.environ.get("SUPABASE_URL", settings.get("url", ""))
    key = os.environ.get("SUPABASE_SECRET_KEY", settings.get("secret_key", ""))
    if not url and not key:
        return None
    if not isinstance(url, str) or not isinstance(key, str) or not url.strip() or not key.strip():
        raise StoreError("Set both SUPABASE_URL and SUPABASE_SECRET_KEY to connect the database.")
    return SupabaseStore(url.strip(), key.strip())


class SupabaseStore:
    def __init__(self, url, key, *, access_token=None, account_table=ACCOUNT_TABLE):
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or
                parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/")):
            raise StoreError("SUPABASE_URL must be the HTTPS project URL, without an API path.")
        self.account_scoped = access_token is not None
        table = account_table if self.account_scoped else TABLE
        self.endpoint = f"{url.rstrip('/')}/rest/v1/{table}"
        self.headers = {"apikey": key, "Accept": "application/json"}
        if self.account_scoped:
            if not key.startswith("sb_publishable_") or not access_token:
                raise StoreError("Account history requires a publishable key and an active sign-in.")
            self.headers["Authorization"] = f"Bearer {access_token}"
        elif not key.startswith("sb_secret_"):
            # Legacy service-role JWTs need the Authorization header as well.
            try:
                payload = key.split(".")[1]
                role = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))["role"]
            except (ValueError, IndexError, KeyError, TypeError):
                raise StoreError("Use a Supabase secret key or legacy service_role key on the server.") from None
            if role != "service_role":
                raise StoreError("Use a server secret key; a public key cannot access forecast history.")
            self.headers["Authorization"] = f"Bearer {key}"

    def request(self, method, params, payload=None, prefer=None):
        headers = dict(self.headers)
        if prefer:
            headers["Prefer"] = prefer
        try:
            response = requests.request(
                method, self.endpoint, headers=headers, params=params, json=payload,
                timeout=(3, 8), allow_redirects=False,
            )
            if response.status_code in (401, 403):
                if self.account_scoped:
                    raise StoreError("Account history access was denied. Sign in again or check database permissions.")
                raise StoreError("Supabase rejected database access. Check the server key and table permissions.")
            if response.status_code == 404:
                raise StoreError("The Supabase history table is missing. Apply the database migration first.")
            if not 200 <= response.status_code < 300:
                raise StoreError("Supabase could not complete the database request. Try again shortly.")
            rows = response.json()
            if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                raise StoreError("Supabase returned an unexpected database response.")
            return rows
        except (requests.RequestException, ValueError):
            # Do not expose request headers, response bodies, or secret values.
            raise StoreError("Unable to reach the Supabase database. Check the connection and retry.") from None

    def save(self, record):
        record = dict(record)
        key, start, end = hourly_slot(
            record["target_date"], record["weather_fetched_at"], record["latitude"], record["longitude"],
            record["training_power_unit"], record["model_version"],
        )
        existing = self.request("GET", {
            "select": "id", "target_date": f"eq.{record['target_date']}",
            "latitude": f"eq.{record['latitude']}", "longitude": f"eq.{record['longitude']}",
            "training_power_unit": f"eq.{record['training_power_unit']}",
            "model_version": f"eq.{record['model_version']}",
            "and": f"(weather_fetched_at.gte.{start.isoformat()},weather_fetched_at.lt.{end.isoformat()})",
            "order": "saved_at.asc,id.asc", "limit": 1,
        })
        if existing:
            if "id" not in existing[0]:
                raise StoreError("The saved forecast could not be confirmed. Please retry.")
            return existing[0]["id"]
        # All writers use this key, so concurrent same-hour inserts also deduplicate.
        record["snapshot_key"] = key
        if isinstance(record["hourly_json"], str):
            record["hourly_json"] = json.loads(record["hourly_json"])
        conflict_columns = "owner_id,snapshot_key" if self.account_scoped else "snapshot_key"
        rows = self.request(
            "POST", {"on_conflict": conflict_columns, "select": "id"}, record,
            prefer="resolution=ignore-duplicates,return=representation,missing=default",
        )
        if not rows:
            rows = self.request("GET", {
                "snapshot_key": f"eq.{record['snapshot_key']}", "select": "id", "limit": 1,
            })
        if not rows or "id" not in rows[0]:
            raise StoreError("The saved forecast could not be confirmed. Please retry.")
        return rows[0]["id"]

    def list(self, *, columns=SUMMARY_COLUMNS, order="target_date.desc,weather_fetched_at.desc,id.desc"):
        result = []
        while True:
            rows = self.request("GET", {
                "select": ",".join(columns),
                "order": order,
                "limit": 500, "offset": len(result),
            })
            result.extend(rows)
            # A server may impose a page size smaller than the requested size.
            if not rows:
                return result

    def load(self, run_id):
        rows = self.request("GET", {"id": f"eq.{int(run_id)}", "select": "hourly_json", "limit": 1})
        if not rows:
            raise ValueError("Forecast was not found.")
        return json.dumps(rows[0]["hourly_json"])
