import json
from pathlib import Path
import sys
from time import time
import unittest
from unittest.mock import Mock, patch

import pyarrow as pa
import requests
import streamlit as st
from streamlit.testing.v1 import AppTest


APP_DIR = Path(__file__).resolve().parents[1] / "app"


class AuthTests(unittest.TestCase):
    def test_unconfigured_recovery_never_requests_a_link(self):
        with patch.object(sys, "path", [str(APP_DIR), *sys.path]):
            from auth import AuthError, SupabaseAuth

            auth = SupabaseAuth(
                "https://example.supabase.co", "sb_publishable_test", redirect_url="http://localhost:8501",
            )
            with patch("auth.configured_auth", return_value=auth), patch("auth.requests.post") as post:
                app = AppTest.from_file(str(APP_DIR / "app.py"), default_timeout=15)
                app.query_params["forgot_password"] = "1"
                app.run()
                self.assertFalse(app.exception)
                self.assertIn("reset codes are unavailable", app.warning[0].value)
                self.assertFalse(app.button)
                with self.assertRaisesRegex(AuthError, "reset codes are unavailable"):
                    auth.request_password_reset("test@example.com")
                post.assert_not_called()

    def test_password_reset_read_timeout_keeps_code_entry_available(self):
        with patch.object(sys, "path", [str(APP_DIR), *sys.path]):
            from auth import SupabaseAuth

            auth = SupabaseAuth(
                "https://example.supabase.co", "sb_publishable_test", redirect_url="http://localhost:8501",
                recovery_codes_enabled=True,
            )
            with patch("auth.configured_auth", return_value=auth), patch(
                "auth.requests.post", side_effect=requests.ReadTimeout,
            ) as post:
                app = AppTest.from_file(str(APP_DIR / "app.py"), default_timeout=15)
                app.query_params["forgot_password"] = "1"
                app.run()
                app.text_input[0].set_value("test@example.com")
                app.button[0].click().run()
                self.assertFalse(app.exception)
                self.assertEqual(app.text_input[0].label, "Reset code")
                self.assertIn("took too long", app.warning[0].value)
                self.assertEqual(post.call_args.kwargs["timeout"], (5, 30))
                post.assert_called_once()

    def test_password_reset_code_verifies_before_allowing_password_change(self):
        with patch.object(sys, "path", [str(APP_DIR), *sys.path]):
            from auth import RECOVERY_SESSION_KEY, SESSION_KEY, SupabaseAuth

            auth = SupabaseAuth(
                "https://example.supabase.co", "sb_publishable_test", redirect_url="http://localhost:8501",
                recovery_codes_enabled=True,
            )
            email = "test@example.com"
            recovery = Mock(status_code=200, json=Mock(return_value={
                "user": {"email": email},
                "access_token": "recovery-access",
                "refresh_token": "recovery-refresh",
                "expires_in": 3600,
            }))
            with patch("auth.configured_auth", return_value=auth), patch(
                "auth.requests.post", side_effect=[
                    Mock(status_code=200), Mock(status_code=200), Mock(status_code=403), recovery, Mock(status_code=204),
                ],
            ) as post, patch("auth.requests.put", return_value=Mock(status_code=200)) as put:
                app = AppTest.from_file(str(APP_DIR / "app.py"), default_timeout=15)
                app.query_params["forgot_password"] = "1"
                app.run()
                app.text_input[0].set_value(email)
                app.button[0].click().run()
                self.assertFalse(app.exception)
                self.assertEqual(post.call_args.args[0], f"{auth.endpoint}/recover")
                self.assertEqual(post.call_args.kwargs["json"], {"email": email})
                self.assertIsNone(post.call_args.kwargs["params"])
                self.assertEqual(app.text_input[0].label, "Reset code")
                app.button(key="solar_resend_reset_code").click().run()
                self.assertEqual(post.call_args.args[0], f"{auth.endpoint}/recover")

                for code in ("123", "654321", "012345"):
                    app.text_input[0].set_value(code)
                    next(button for button in app.button if button.label == "Verify code").click().run()
                    self.assertFalse(app.exception)
                    if code != "012345":
                        self.assertNotIn(RECOVERY_SESSION_KEY, app.session_state)
                        self.assertTrue(app.error)
                self.assertEqual(post.call_count, 4)
                self.assertEqual(post.call_args.args[0], f"{auth.endpoint}/verify")
                self.assertEqual(post.call_args.kwargs["json"], {"type": "recovery", "email": email, "token": "012345"})
                put.assert_not_called()
                self.assertNotIn(SESSION_KEY, app.session_state)
                self.assertNotIn("forgot_password", app.query_params)

                app.text_input[0].set_value("new-password")
                app.text_input[1].set_value("new-password")
                app.button[0].click().run()
                self.assertFalse(app.exception)
                self.assertEqual(put.call_args.kwargs["headers"]["Authorization"], "Bearer recovery-access")
                self.assertEqual(put.call_args.kwargs["json"], {"password": "new-password"})
                self.assertIn("Password reset", app.success[0].value)
                self.assertEqual(app.button[0].label, "Sign in")
                self.assertNotIn(SESSION_KEY, app.session_state)

    def test_password_reset_link_works_in_a_new_session_without_signing_in(self):
        with patch.object(sys, "path", [str(APP_DIR), *sys.path]):
            from auth import RECOVERY_QUERY, RECOVERY_SESSION_KEY, SESSION_KEY, SupabaseAuth

            auth = SupabaseAuth(
                "https://example.supabase.co", "sb_publishable_test", redirect_url="http://localhost:8501",
            )
            email = "test@example.com"
            recovery = Mock(status_code=200, json=Mock(return_value={
                "user": {"email": email},
                "access_token": "recovery-access",
                "refresh_token": "recovery-refresh",
                "expires_in": 3600,
            }))
            with patch("auth.configured_auth", return_value=auth), patch(
                "auth.requests.post", side_effect=[recovery, Mock(status_code=204), Mock(status_code=404)],
            ) as post, patch("auth.requests.put", return_value=Mock(status_code=200)) as put:
                state = "A" * 43
                reset = AppTest.from_file(str(APP_DIR / "app.py"), default_timeout=15)
                reset.query_params[RECOVERY_QUERY] = state
                reset.query_params["code"] = "one-time-code"
                reset.run()
                self.assertFalse(reset.exception)
                self.assertFalse(reset.sidebar.button)
                self.assertNotIn(SESSION_KEY, reset.session_state)
                self.assertIn(RECOVERY_SESSION_KEY, reset.session_state)
                self.assertEqual(reset.text[0].value, email)
                self.assertNotIn("code", reset.query_params)
                self.assertNotIn(RECOVERY_QUERY, reset.query_params)
                exchange = post.call_args
                self.assertEqual(exchange.kwargs["params"], {"grant_type": "pkce"})
                self.assertEqual(exchange.kwargs["json"]["auth_code"], "one-time-code")

                for confirmation in ("mismatch", "new-password"):
                    reset.text_input[0].set_value("new-password")
                    reset.text_input[1].set_value(confirmation)
                    next(button for button in reset.button if button.label == "Reset password").click().run()
                    self.assertFalse(reset.exception)
                    if confirmation == "mismatch":
                        put.assert_not_called()
                        self.assertIn("confirm it", reset.error[0].value)

                self.assertEqual(put.call_args.kwargs["json"], {"password": "new-password"})
                self.assertEqual(put.call_args.kwargs["headers"]["Authorization"], "Bearer recovery-access")
                self.assertEqual(post.call_args.args[0], f"{auth.endpoint}/logout")
                self.assertNotIn(RECOVERY_SESSION_KEY, reset.session_state)
                self.assertNotIn(SESSION_KEY, reset.session_state)
                self.assertIn("Password reset", reset.success[0].value)

                reset.query_params[RECOVERY_QUERY] = state
                reset.query_params["code"] = "one-time-code"
                reset.run()
                self.assertFalse(reset.exception)
                self.assertIn("invalid, expired, or already used", reset.warning[0].value)
                self.assertNotIn(RECOVERY_SESSION_KEY, reset.session_state)

    def test_profile_email_changes_only_after_confirmation(self):
        with patch.object(sys, "path", [str(APP_DIR), *sys.path]):
            from auth import SESSION_KEY, AuthSession, SupabaseAuth

            auth = SupabaseAuth(
                "https://example.supabase.co", "sb_publishable_test", redirect_url="http://localhost:8501",
            )
            initial = AuthSession("old@example.com", "access", "refresh", int(time()) + 3600)
            requested = "new@example.com"
            pending = Mock(status_code=200, json=Mock(return_value={
                "email": initial.email, "new_email": requested,
            }))
            confirmed = Mock(status_code=200, json=Mock(return_value={"email": requested}))
            with patch("auth.configured_auth", return_value=auth), patch(
                "auth.requests.put", return_value=pending,
            ) as put, patch("auth.requests.get", side_effect=[pending, confirmed]) as get:
                app = AppTest.from_file(str(APP_DIR / "app.py"), default_timeout=15)
                app.session_state[SESSION_KEY] = initial
                app.session_state["solar_page"] = "My Profile"
                app.run()
                self.assertFalse(app.exception)

                def submit(address):
                    next(field for field in app.main.text_input if field.label == "New email address").set_value(address)
                    next(button for button in app.main.button if button.label == "Send confirmation").click().run()
                    self.assertFalse(app.exception)

                submit(initial.email.upper())
                self.assertIn("different email", app.error[0].value)
                put.assert_not_called()

                submit(requested)
                put.assert_called_once()
                self.assertEqual(put.call_args.args[0], f"{auth.endpoint}/user")
                self.assertEqual(put.call_args.kwargs["headers"]["Authorization"], "Bearer access")
                self.assertEqual(put.call_args.kwargs["params"], {"redirect_to": auth.redirect_url})
                self.assertEqual(put.call_args.kwargs["json"], {"email": requested})
                self.assertEqual(app.main.text[0].value, initial.email)
                self.assertEqual(app.session_state[SESSION_KEY].pending_email, requested)

                app.main.button(key="solar_check_email").click().run()
                self.assertFalse(app.exception)
                self.assertEqual(app.session_state[SESSION_KEY].email, initial.email)
                self.assertFalse(app.success)

                app.main.button(key="solar_check_email").click().run()
                self.assertFalse(app.exception)
                self.assertEqual(get.call_args.args[0], f"{auth.endpoint}/user")
                self.assertEqual(get.call_args.kwargs["headers"]["Authorization"], "Bearer access")
                self.assertEqual(app.main.text[0].value, requested)
                self.assertEqual(app.session_state[SESSION_KEY].email, requested)
                self.assertIsNone(app.session_state[SESSION_KEY].pending_email)
                self.assertEqual(app.success[0].value, "Account email updated.")

    def test_profile_changes_password_with_verified_session_and_hides_sidebar_email(self):
        with patch.object(sys, "path", [str(APP_DIR), *sys.path]):
            from auth import SESSION_KEY, AuthSession, SupabaseAuth

            auth = SupabaseAuth(
                "https://example.supabase.co", "sb_publishable_test", redirect_url="http://localhost:8501",
            )
            initial = AuthSession("test@example.com", "old-access", "old-refresh", int(time()) + 3600)
            verified = Mock(status_code=200, json=Mock(return_value={
                "user": {"email": initial.email},
                "access_token": "verified-access",
                "refresh_token": "verified-refresh",
                "expires_in": 3600,
            }))
            with patch("auth.configured_auth", return_value=auth), patch(
                "auth.requests.post", return_value=verified,
            ) as post, patch("auth.requests.put") as put:
                app = AppTest.from_file(str(APP_DIR / "app.py"), default_timeout=15)
                app.session_state[SESSION_KEY] = initial
                app.session_state["solar_page"] = "My Profile"
                app.run()
                self.assertFalse(app.exception)
                self.assertFalse(app.sidebar.text)
                self.assertEqual(app.main.text[0].value, initial.email)

                def submit(confirmation):
                    fields = {field.label: field for field in app.main.text_input}
                    fields["Current password"].set_value("current-pass")
                    fields["New password"].set_value("new-strong-pass")
                    fields["Confirm new password"].set_value(confirmation)
                    next(button for button in app.main.button if button.label == "Update password").click().run()
                    self.assertFalse(app.exception)

                submit("mismatch")
                self.assertEqual(app.error[0].value, "The new passwords do not match.")
                post.assert_not_called()
                put.assert_not_called()

                post.return_value = Mock(status_code=400)
                submit("new-strong-pass")
                self.assertIn("Sign-in failed", app.error[0].value)
                put.assert_not_called()

                post.side_effect = [verified, Mock(status_code=204), verified]
                put.side_effect = [
                    Mock(status_code=422, json=Mock(return_value={"error_code": "weak_password"})),
                    Mock(status_code=200),
                ]
                submit("new-strong-pass")
                self.assertIn("stronger password", app.error[0].value)
                self.assertEqual(post.call_args.args[0], f"{auth.endpoint}/logout")
                self.assertEqual(app.session_state[SESSION_KEY], initial)

                submit("new-strong-pass")
                self.assertIn("Password updated", app.success[0].value)
                self.assertEqual(post.call_args.kwargs["json"], {"email": initial.email, "password": "current-pass"})
                self.assertEqual(put.call_args.args[0], f"{auth.endpoint}/user")
                self.assertEqual(put.call_args.kwargs["headers"]["Authorization"], "Bearer verified-access")
                self.assertEqual(put.call_args.kwargs["json"], {
                    "current_password": "current-pass", "password": "new-strong-pass",
                })
                self.assertEqual(app.session_state[SESSION_KEY].access_token, "verified-access")

    def test_dashboard_requires_sign_in_and_sign_out_clears_session(self):
        with patch.object(sys, "path", [str(APP_DIR), *sys.path]):
            from auth import SESSION_KEY, AuthSession, SupabaseAuth

            auth = SupabaseAuth(
                "https://example.supabase.co", "sb_publishable_test", redirect_url="http://localhost:8501",
            )
            response = Mock(status_code=400)
            with patch("auth.configured_auth", return_value=auth), patch(
                "auth.requests.post", return_value=response
            ) as post, patch("auth.st.spinner", wraps=st.spinner) as spinner:
                app = AppTest.from_file(str(APP_DIR / "app.py")).run()
                self.assertEqual(len(app.exception), 0)
                self.assertEqual(app.button[0].label, "Sign in")
                self.assertFalse(app.sidebar.button)

                def submit():
                    app.text_input[0].set_value("test@example.com")
                    app.text_input[1].set_value("test-password")
                    app.button[0].click().run()

                submit()
                self.assertIn("Sign-in failed", app.error[0].value)
                self.assertFalse(app.sidebar.button)
                spinner.assert_called_once_with("Signing in…")

                response.status_code = 200
                response.json.return_value = {
                    "user": {"email": "test@example.com"},
                    "access_token": "test-access",
                    "refresh_token": "test-refresh",
                    "expires_in": 3600,
                }
                app.session_state["solar_page"] = "About this"
                submit()
                self.assertEqual(len(app.exception), 0)
                self.assertIn(SESSION_KEY, app.session_state)
                self.assertEqual(post.call_args.kwargs["params"], {"grant_type": "password"})

                app.session_state[SESSION_KEY] = AuthSession(
                    "test@example.com", "old-access", "old-refresh", int(time()) - 1,
                )
                app.run()
                self.assertEqual(post.call_args.kwargs["params"], {"grant_type": "refresh_token"})
                self.assertEqual(app.session_state[SESSION_KEY].access_token, "test-access")

                history = [
                    {
                        "id": prediction_id, "source": source, "predicted_power": power,
                        "predicted_for": "2026-11-18T08:00:00Z" if prediction_id != 2 else "2026-11-18T16:00:00Z",
                        "saved_at": "2026-11-18T08:15:00.123Z",
                        "sunlight": 600, "air_temperature": 30, "panel_temperature": 40,
                    }
                    for prediction_id, source, power in [(3, "Overview", 500), (2, "Manual prediction", 400), (1, "Overview", 300)]
                ]
                with patch("supabase_store.requests.request") as request:
                    request.side_effect = [
                        Mock(status_code=200, json=Mock(return_value=rows))
                        for rows in (history, [])
                    ]
                    app.sidebar.button(key="solar_nav_Prediction history").click().run()
                    self.assertEqual(len(app.exception), 0)
                    self.assertTrue(request.call_args.args[1].endswith("/solarcast_account_predictions"))
                    self.assertEqual(request.call_args.kwargs["headers"]["Authorization"], "Bearer test-access")
                    chart = app.get("vega_lite_chart")[0].proto
                    line = json.loads(chart.spec)["layer"][0]
                    self.assertEqual(line["mark"]["type"], "line")
                    self.assertEqual(line["encoding"]["color"]["field"], "prediction_date")
                    self.assertFalse(line["encoding"]["x"]["axis"]["grid"])
                    plotted = pa.ipc.open_stream(chart.datasets[0].data.data).read_all()
                    self.assertEqual(plotted.column("id").to_pylist(), [3, 2, 1])
                    self.assertEqual(plotted.column("chart_time").to_pylist(), ["2026-11-18T16:00:00.000000Z"] * 3)
                    self.assertEqual(app.dataframe[0].value.iloc[0]["Time"], "18 Nov 2026, 04:00 PM")
                    self.assertEqual(app.dataframe[0].value["Predicted AC power"].tolist(), [500])
                    self.assertEqual(plotted.column("prediction_date").to_pylist(), ["2026-11-18", "2026-11-19", "2026-11-18"])
                    self.assertEqual(app.dataframe[0].value.iloc[0]["Prediction for"], "18 Nov 2026, 04:00 PM")

                response.status_code = 204
                app.sidebar.button(key="solar_sign_out").click().run()
                self.assertEqual(len(app.exception), 0)
                self.assertEqual(post.call_args.kwargs["params"], {"scope": "local"})
                self.assertNotIn(SESSION_KEY, app.session_state)
                self.assertEqual(app.button[0].label, "Sign in")

    def test_sign_up_requires_matching_passwords_and_waits_for_email_confirmation(self):
        with patch.object(sys, "path", [str(APP_DIR), *sys.path]):
            from auth import SESSION_KEY, SupabaseAuth

            auth = SupabaseAuth(
                "https://example.supabase.co", "sb_publishable_test", redirect_url="http://localhost:8501",
            )
            response = Mock(status_code=200)
            response.json.return_value = {"id": "test-user", "email": "test@example.com"}
            with patch("auth.configured_auth", return_value=auth), patch(
                "auth.requests.post", return_value=response
            ) as post, patch("auth.st.spinner", wraps=st.spinner) as spinner:
                app = AppTest.from_file(str(APP_DIR / "app.py")).run()
                app.segmented_control(key="solar_auth_action").set_value("Sign up").run()
                self.assertEqual(app.button[0].label, "Sign up")

                def submit(confirmation):
                    app.text_input[0].set_value("test@example.com")
                    app.text_input[1].set_value("test-password")
                    app.text_input[2].set_value(confirmation)
                    app.button[0].click().run()

                submit("different-password")
                self.assertEqual(app.error[0].value, "Passwords must match.")
                post.assert_not_called()
                spinner.assert_not_called()

                submit("test-password")
                self.assertEqual(len(app.exception), 0)
                spinner.assert_called_once_with("Creating your account…")
                self.assertIn("check your inbox", app.info[0].value)
                self.assertNotIn(SESSION_KEY, app.session_state)
                self.assertFalse(app.sidebar.button)
                self.assertEqual(post.call_args.args[0], f"{auth.endpoint}/signup")
                self.assertEqual(post.call_args.kwargs["params"], {"redirect_to": "http://localhost:8501"})
                self.assertEqual(post.call_args.kwargs["json"], {
                    "email": "test@example.com",
                    "password": "test-password",
                })

                response.status_code = 200
                response.json.return_value = {
                    "user": {"email": "test@example.com"},
                    "access_token": "test-access",
                    "refresh_token": "test-refresh",
                    "expires_in": 3600,
                }
                app.session_state["solar_page"] = "About this"
                submit("test-password")
                self.assertEqual(len(app.exception), 0)
                self.assertEqual(app.session_state[SESSION_KEY].email, "test@example.com")
                self.assertTrue(app.sidebar.button(key="solar_sign_out"))
