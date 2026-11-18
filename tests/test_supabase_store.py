"""Supabase transport, backend selection, and local history migration checks."""

from datetime import date
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT / "scripts"))
import forecast_store
import supabase_store
from supabase_database import migrate_local


class SupabaseTests(unittest.TestCase):
    def setUp(self):
        self.store = supabase_store.SupabaseStore("https://example.supabase.co", "sb_secret_test")
        self.frame = pd.DataFrame({
            "Hour starting (Asia/Manila)": pd.date_range("2026-11-18", periods=24, freq="h"),
            "Estimated power (kW)": [2.] * 24,
            "Estimated energy (kWh)": [2.] * 24,
        })
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "history.db"

    def response(self, rows, code=200):
        return Mock(status_code=code, json=Mock(return_value=rows))

    def save(self, path=None):
        return forecast_store.save_forecast(
            self.frame, date(2026, 11, 18), "2026-11-17T12:00:00+08:00",
            8.4542, 124.6319, "kW", "v1", path,
        )

    def test_remote_save_roundtrip_and_conflict_returns_existing_id(self):
        with patch.object(forecast_store, "configured_store", return_value=self.store), patch(
            "supabase_store.requests.request"
        ) as request:
            request.side_effect = [self.response([]), self.response([{"id": 17}])]
            self.assertEqual(self.save(), 17)
            record = request.call_args.kwargs["json"]
            self.assertEqual(len(record["hourly_json"]["data"]), 24)
            self.assertEqual(record["daily_energy_kwh"], 48.)
            self.assertNotIn("Authorization", request.call_args.kwargs["headers"])
            self.assertFalse(request.call_args.kwargs["allow_redirects"])

            request.side_effect = [self.response([]), self.response([]), self.response([{"id": 17}])]
            self.assertEqual(self.save(), 17)
            self.assertEqual(request.call_args.kwargs["params"]["snapshot_key"], f"eq.{record['snapshot_key']}")

            request.side_effect = None
            request.return_value = self.response([{"hourly_json": record["hourly_json"]}])
            pd.testing.assert_frame_equal(forecast_store.load_forecast(17), self.frame, check_dtype=False)

    def test_existing_remote_hour_is_reused_without_inserting(self):
        with patch.object(forecast_store, "configured_store", return_value=self.store), patch(
            "supabase_store.requests.request", return_value=self.response([{"id": 17}])
        ) as request:
            self.assertEqual(self.save(), 17)
            request.assert_called_once()
            self.assertEqual(request.call_args.args[0], "GET")
            params = request.call_args.kwargs["params"]
            self.assertEqual(params["limit"], 1)
            self.assertIn("weather_fetched_at.gte.2026-11-17T04:00:00+00:00", params["and"])
            self.assertIn("weather_fetched_at.lt.2026-11-17T05:00:00+00:00", params["and"])

    def test_account_save_and_load_use_only_user_credentials(self):
        store = supabase_store.SupabaseStore(
            "https://example.supabase.co", "sb_publishable_test", access_token="user-token",
        )
        with patch.object(forecast_store, "configured_store") as shared_store, patch(
            "supabase_store.requests.request", side_effect=[self.response([]), self.response([{"id": 42}])]
        ) as request:
            run_id = forecast_store.save_forecast(
                self.frame, date(2026, 11, 18), "2026-11-17T12:00:00+08:00",
                8.4542, 124.6319, "kW", "v1", store=store,
            )
            self.assertEqual(run_id, 42)
            insert = request.call_args.kwargs
            self.assertEqual(insert["params"]["on_conflict"], "owner_id,snapshot_key")
            self.assertIn("missing=default", insert["headers"]["Prefer"])
            self.assertNotIn("owner_id", insert["json"])

            request.side_effect = [
                self.response([{"hourly_json": insert["json"]["hourly_json"]}]), self.response([]),
            ]
            pd.testing.assert_frame_equal(
                forecast_store.load_forecast(run_id, store=store), self.frame, check_dtype=False,
            )
            with self.assertRaisesRegex(ValueError, "not found"):
                forecast_store.load_forecast(99, store=store)

            shared_store.assert_not_called()
            for call in request.call_args_list:
                self.assertTrue(call.args[1].endswith("/solarcast_account_forecast_runs"))
                self.assertEqual(call.kwargs["headers"]["apikey"], "sb_publishable_test")
                self.assertEqual(call.kwargs["headers"]["Authorization"], "Bearer user-token")

    def test_pagination_handles_server_page_cap_and_empty_history(self):
        with patch.object(self.store, "request", side_effect=[[{"id": 3}], [{"id": 2}], []]) as request:
            self.assertEqual([row["id"] for row in self.store.list()], [3, 2])
            self.assertEqual([call.args[1]["offset"] for call in request.call_args_list], [0, 1, 2])
        with patch.object(forecast_store, "configured_store", return_value=self.store), patch.object(
            self.store, "request", return_value=[]
        ):
            runs = forecast_store.list_forecasts()
            self.assertTrue(runs.empty)
            self.assertIn("target_date", runs.columns)
            with self.assertRaisesRegex(ValueError, "not found"):
                forecast_store.load_forecast(900)

    def test_bad_configuration_is_rejected_without_local_fallback(self):
        with patch.object(supabase_store, "SECRETS_PATH", Path(self.temp.name) / "missing.toml"), patch.dict(
            "os.environ", {}, clear=True
        ):
            self.assertIsNone(supabase_store.configured_store())
            with patch.dict("os.environ", {"SUPABASE_URL": "https://example.supabase.co"}):
                with self.assertRaises(supabase_store.StoreError):
                    forecast_store.list_forecasts()
            with patch.dict("os.environ", {
                "SUPABASE_URL": "https://example.supabase.co", "SUPABASE_SECRET_KEY": "sb_publishable_public"
            }):
                with self.assertRaises(supabase_store.StoreError):
                    supabase_store.configured_store()
        with self.assertRaises(supabase_store.StoreError):
            supabase_store.SupabaseStore("http://example.supabase.co", "sb_secret_test")

    def test_secrets_file_and_environment_precedence(self):
        path = Path(self.temp.name) / "secrets.toml"
        path.write_text('[supabase]\nurl="https://file.supabase.co"\nsecret_key="sb_secret_file"\n')
        with patch.object(supabase_store, "SECRETS_PATH", path), patch.dict("os.environ", {}, clear=True):
            self.assertIn("file.supabase.co", supabase_store.configured_store().endpoint)
            with patch.dict("os.environ", {"SUPABASE_URL": "https://env.supabase.co"}):
                self.assertIn("env.supabase.co", supabase_store.configured_store().endpoint)

    def test_database_errors_hide_credentials_and_do_not_save_locally(self):
        for code in (401, 403, 404, 500, 302):
            with self.subTest(code=code), patch("supabase_store.requests.request", return_value=self.response([], code)):
                with self.assertRaises(supabase_store.StoreError) as error:
                    self.store.list()
                self.assertNotIn("sb_secret_test", str(error.exception))
        with patch.object(forecast_store, "configured_store", return_value=self.store), patch(
            "supabase_store.requests.request", side_effect=requests.Timeout("sb_secret_test")
        ), patch.object(forecast_store, "connect") as connect:
            with self.assertRaises(supabase_store.StoreError) as error:
                self.save()
            connect.assert_not_called()
            self.assertNotIn("sb_secret_test", str(error.exception))

    def test_migration_preserves_snapshot_keys_and_local_database(self):
        local_id = self.save(self.path)
        remote = Mock()
        self.assertEqual(migrate_local(remote, self.path), 1)
        record = remote.save.call_args.args[0]
        self.assertNotIn("id", record)
        self.assertEqual(len(json.loads(record["hourly_json"])["data"]), 24)
        key = record["snapshot_key"]
        self.assertEqual(migrate_local(remote, self.path), 1)
        self.assertEqual(remote.save.call_args.args[0]["snapshot_key"], key)
        self.assertEqual(len(forecast_store.list_forecasts(self.path)), 1)
        pd.testing.assert_frame_equal(forecast_store.load_forecast(local_id, self.path), self.frame, check_dtype=False)


if __name__ == "__main__":
    unittest.main()
