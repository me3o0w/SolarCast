"""Email and password authentication for the Streamlit session."""

from base64 import urlsafe_b64encode
from contextlib import suppress
from dataclasses import dataclass, replace
import hmac
import logging
import os
import re
from time import time
import tomllib
from urllib.parse import urlsplit

import requests
import streamlit as st

import loading as loading_ui
import styles
from supabase_store import SECRETS_PATH


SESSION_KEY = "solar_auth_session"
RECOVERY_SESSION_KEY = "solar_password_recovery_session"
RECOVERY_EMAIL_KEY = "solar_password_recovery_email"
RECOVERY_UNCONFIRMED_KEY = "solar_password_recovery_unconfirmed"
RECOVERY_QUERY = "solar_recovery"
INVALID_RECOVERY_LINK = "This reset link is invalid, expired, or already used. Request a new one."
RECOVERY_CODES_UNAVAILABLE = "Password reset codes are unavailable until the email service is configured."
RECOVERY_LOADER = "Forgot password"
logger = logging.getLogger(__name__)


class AuthError(RuntimeError):
    """An authentication error safe to show in the app."""


class AuthReadTimeout(AuthError):
    """Supabase did not respond before the read deadline."""


@dataclass(frozen=True, repr=False)
class AuthSession:
    email: str
    access_token: str
    refresh_token: str
    expires_at: int
    pending_email: str | None = None


def _auth_response_data(response):
    try:
        data = response.json()
    except ValueError:
        data = None
    if not isinstance(data, dict):
        raise AuthError("The authentication service returned an unexpected response. Please try again.")
    return data


def _account_emails(user):
    email = user.get("email") if isinstance(user, dict) else None
    pending = user.get("new_email") if isinstance(user, dict) else None
    if not isinstance(email, str) or not email or (pending is not None and not isinstance(pending, str)):
        raise AuthError("The authentication service returned invalid account details. Please try again.")
    return email, pending or None


def _session_from_data(data):
    try:
        email, pending_email = _account_emails(data["user"])
        access_token = data["access_token"]
        refresh_token = data["refresh_token"]
        expires_at = data.get("expires_at")
        if expires_at is None:
            expires_in = data["expires_in"]
            if type(expires_in) is not int or expires_in <= 0:
                raise ValueError
            expires_at = int(time()) + expires_in
        if not all(isinstance(value, str) and value for value in (access_token, refresh_token)):
            raise ValueError
        if type(expires_at) is not int or expires_at <= time():
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise AuthError("The authentication service returned an invalid session. Please try again.") from None
    return AuthSession(email, access_token, refresh_token, expires_at, pending_email)


def _recovery_verifier(state):
    # Derive the PKCE verifier on the server so links work in a new browser session.
    key = st.get_option("server.cookieSecret").encode("utf-8")
    digest = hmac.digest(key, f"solarcast-password-recovery:{state}".encode("ascii"), "sha256")
    return urlsafe_b64encode(digest).decode("ascii").rstrip("=")


class SupabaseAuth:
    def __init__(self, url, key, *, redirect_url, recovery_codes_enabled=False):
        self.project_url = url
        self.endpoint = f"{url.rstrip('/')}/auth/v1"
        self.key = key
        self.redirect_url = redirect_url
        self.recovery_codes_enabled = recovery_codes_enabled

    def _request(self, send, path, *, params=None, payload=None, access_token=None, timeout=(5, 15)):
        headers = {"apikey": self.key}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        try:
            return send(
                f"{self.endpoint}/{path}", headers=headers, params=params, json=payload,
                timeout=timeout, allow_redirects=False,
            )
        except requests.ReadTimeout:
            logger.warning("Supabase Auth %s timed out waiting for a response", path)
            raise AuthReadTimeout("The authentication service took too long to respond. Please try again.") from None
        except requests.RequestException as error:
            logger.warning("Supabase Auth %s request failed (%s)", path, type(error).__name__)
            raise AuthError("Could not reach the authentication service. Please try again.") from None

    def _session(self, grant_type, payload):
        response = self._request(requests.post, "token", params={"grant_type": grant_type}, payload=payload)
        if response.status_code == 429:
            raise AuthError("Too many sign-in attempts. Wait a moment and try again.")
        if response.status_code in (400, 422) and grant_type == "password":
            raise AuthError("Sign-in failed. Check your email and password and confirm your email address.")
        if response.status_code != 200:
            raise AuthError("The sign-in service could not complete the request. Please try again.")
        return _session_from_data(_auth_response_data(response))

    def sign_in(self, email, password):
        return self._session("password", {"email": email, "password": password})

    def request_password_reset(self, email):
        if not self.recovery_codes_enabled:
            raise AuthError(RECOVERY_CODES_UNAVAILABLE)
        try:
            response = self._request(
                requests.post, "recover", payload={"email": email}, timeout=(5, 30),
            )
        except AuthReadTimeout:
            # Supabase may have already sent the email, so leave code entry available.
            return False
        # Keep the reply the same for all addresses, including mail delivery failures.
        if response.status_code >= 500:
            logger.warning("Supabase password recovery returned HTTP %d", response.status_code)
        return True

    def exchange_recovery_code(self, state, code):
        if not re.fullmatch(r"[A-Za-z0-9_-]{43}", state) or not code or len(code) > 256:
            raise AuthError(INVALID_RECOVERY_LINK)
        response = self._request(
            requests.post, "token", params={"grant_type": "pkce"},
            payload={"auth_code": code, "code_verifier": _recovery_verifier(state)},
        )
        if response.status_code != 200:
            raise AuthError(INVALID_RECOVERY_LINK)
        return _session_from_data(_auth_response_data(response))

    def verify_recovery_otp(self, email, code):
        response = self._request(
            requests.post, "verify", payload={"email": email, "token": code, "type": "recovery"},
        )
        if response.status_code == 429:
            raise AuthError("Too many attempts. Wait a moment and try again.")
        if response.status_code != 200:
            raise AuthError("This code is invalid, expired, or already used. Try again or request a new code.")
        return _session_from_data(_auth_response_data(response))

    def sign_up(self, email, password):
        """Return a session if Supabase signs in the new user immediately."""
        response = self._request(
            requests.post, "signup", params={"redirect_to": self.redirect_url},
            payload={"email": email, "password": password},
        )
        if response.status_code == 429:
            raise AuthError("Too many sign-up attempts. Wait a moment and try again.")

        data = _auth_response_data(response)
        if not 200 <= response.status_code < 300:
            code = data.get("error_code") or data.get("code")
            if code in ("user_already_exists", "email_exists"):
                return None
            messages = {
                "signup_disabled": "Sign-ups are currently disabled for SolarCast.",
                "email_address_invalid": "Enter a valid email address.",
                "weak_password": "Choose a longer or stronger password.",
                "email_address_not_authorized": "SolarCast can't send confirmation emails to this address.",
            }
            message = messages.get(code) if isinstance(code, str) else None
            raise AuthError(message or "Could not create an account. Check your details and try again.")

        if data.get("access_token") is not None or data.get("refresh_token") is not None:
            return _session_from_data(data)
        user = data.get("user", data)
        if isinstance(user, dict) and isinstance(user.get("id"), str) and user["id"]:
            return None
        raise AuthError("The authentication service returned an unexpected response. Please try again.")

    def refresh(self, session):
        return self._session("refresh_token", {"refresh_token": session.refresh_token})

    def change_email(self, session, new_email):
        response = self._request(
            requests.put, "user", params={"redirect_to": self.redirect_url},
            access_token=session.access_token, payload={"email": new_email},
        )
        if response.status_code == 429:
            raise AuthError("Too many requests. Wait a moment and try again.")
        data = _auth_response_data(response)
        if response.status_code != 200:
            code = data.get("error_code") or data.get("code")
            messages = {
                "email_address_invalid": "Enter a valid email address.",
                "email_address_not_authorized": "SolarCast can't send a confirmation email to this address.",
                "email_exists": "This email address is already in use.",
                "user_already_exists": "This email address is already in use.",
            }
            message = messages.get(code) if isinstance(code, str) else None
            raise AuthError(message or "Could not request an email change. Please try again.")
        email, pending_email = _account_emails(data)
        return replace(session, email=email, pending_email=pending_email)

    def email_status(self, session):
        response = self._request(requests.get, "user", access_token=session.access_token)
        if response.status_code != 200:
            raise AuthError("Could not check your email status. Please try again.")
        email, pending_email = _account_emails(_auth_response_data(response))
        return replace(session, email=email, pending_email=pending_email)

    def change_password(self, session, current_password, new_password):
        # Supabase's current-password check is configurable. A fresh sign-in
        # verifies the password and satisfies recent sign-in requirements.
        if session.pending_email:
            session = self.email_status(session)
        verified = self.sign_in(session.email, current_password)
        try:
            self._update_password(verified, new_password, current_password=current_password)
        except AuthError:
            with suppress(AuthError):
                self.sign_out(verified)
            raise
        # Supabase keeps the session that made the update and revokes the others.
        return verified

    def reset_password(self, recovery, new_password):
        self._update_password(recovery, new_password)
        with suppress(AuthError):
            self.sign_out(recovery)

    def _update_password(self, session, new_password, *, current_password=None):
        payload = {"password": new_password}
        if current_password is not None:
            payload["current_password"] = current_password
        response = self._request(requests.put, "user", access_token=session.access_token, payload=payload)
        if response.status_code == 200:
            return
        if response.status_code == 429:
            raise AuthError("Too many requests. Wait a moment and try again.")
        if current_password is None and response.status_code in (401, 403):
            raise AuthError("Your password reset session is no longer valid. Request a new code.")
        data = _auth_response_data(response)
        code = data.get("error_code") or data.get("code")
        messages = {
            "current_password_mismatch": "The current password is incorrect.",
            "same_password": "Choose a password different from your current password.",
            "weak_password": "Choose a longer or stronger password.",
        }
        message = messages.get(code) if isinstance(code, str) else None
        raise AuthError(message or "Could not change your password. Please try again.")

    def sign_out(self, session):
        response = self._request(
            requests.post, "logout", params={"scope": "local"}, access_token=session.access_token,
        )
        if response.status_code not in (204, 401, 403, 404):
            raise AuthError("Could not end the Supabase session.")


def configured_auth():
    try:
        settings = {}
        if SECRETS_PATH.exists():
            with SECRETS_PATH.open("rb") as file:
                settings = tomllib.load(file).get("supabase", {})
        url = os.environ.get("SUPABASE_URL", settings.get("url", "")).strip()
        key = os.environ.get("SUPABASE_PUBLISHABLE_KEY", settings.get("publishable_key", "")).strip()
        redirect_url = os.environ.get(
            "SUPABASE_AUTH_REDIRECT_URL",
            settings.get("auth_redirect_url", f"http://localhost:{st.get_option('server.port')}"),
        ).strip()
        parsed = urlsplit(url)
        redirect = urlsplit(redirect_url)
    except (AttributeError, OSError, ValueError):
        raise AuthError("Unable to read the Supabase sign-in settings.") from None
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or
            parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/")
            or not key.startswith("sb_publishable_")):
        raise AuthError("To enable sign-in, configure the Supabase project URL and publishable key.")
    local_http = redirect.scheme == "http" and redirect.hostname in ("localhost", "127.0.0.1", "::1")
    if ((redirect.scheme != "https" and not local_http) or not redirect.hostname
            or redirect.username is not None or redirect.password is not None
            or redirect.query or redirect.fragment):
        raise AuthError("Set the confirmation redirect to SolarCast's HTTPS URL or a local HTTP URL.")
    return SupabaseAuth(
        url, key, redirect_url=redirect_url,
        recovery_codes_enabled=settings.get("password_recovery_codes_enabled") is True,
    )


def auth_session_needs_refresh():
    session = st.session_state.get(SESSION_KEY)
    return session is not None and session.expires_at <= time()


def _render_reset_request(auth):
    st.subheader("Forgot password?")
    email = st.session_state.get(RECOVERY_EMAIL_KEY)
    if email is None and not auth.recovery_codes_enabled:
        st.warning(RECOVERY_CODES_UNAVAILABLE)
    elif email is None:
        with st.form("solar_request_password_reset", clear_on_submit=True, border=False):
            address = st.text_input("Account email", autocomplete="email").strip()
            submitted = st.form_submit_button("Send code", type="primary", width="stretch")
        if submitted:
            if not re.fullmatch(r"[^@\s]+@[^@\s]+", address):
                st.error("Enter a valid email address.")
            else:
                try:
                    with loading_ui.PageLoading(RECOVERY_LOADER, message="Requesting a reset code"):
                        responded = auth.request_password_reset(address)
                    st.session_state[RECOVERY_UNCONFIRMED_KEY] = not responded
                    st.session_state[RECOVERY_EMAIL_KEY] = address
                    st.rerun()
                except AuthError as error:
                    st.error(str(error))
    else:
        _render_recovery_code(auth, email)
    st.html('<a class="sc-auth-link" href="?">Back to sign in</a>')


def _render_recovery_code(auth, email):
    st.text(email)
    st.info(
        "If an account exists for this address, you'll receive a reset code. Check your inbox and spam folder."
    )
    with st.form("solar_verify_password_reset", clear_on_submit=True, border=False):
        code = st.text_input("Reset code", autocomplete="one-time-code", max_chars=10).strip()
        submitted = st.form_submit_button("Verify code", type="primary", width="stretch")
    with st.container(horizontal=True, gap="small"):
        resend = st.button("Resend code", key="solar_resend_reset_code", disabled=not auth.recovery_codes_enabled)
        if st.button("Use a different email", key="solar_change_reset_email"):
            st.session_state.pop(RECOVERY_EMAIL_KEY, None)
            st.session_state.pop(RECOVERY_UNCONFIRMED_KEY, None)
            st.rerun()
    try:
        if resend:
            with loading_ui.PageLoading(RECOVERY_LOADER, message="Requesting a reset code"):
                responded = auth.request_password_reset(email)
            st.session_state[RECOVERY_UNCONFIRMED_KEY] = not responded
            if responded:
                st.caption("Check your inbox for the latest reset email.")
        elif submitted:
            if not re.fullmatch(r"[0-9]{6,10}", code):
                raise AuthError("Enter the numbers from your reset email.")
            with loading_ui.PageLoading(RECOVERY_LOADER, message="Verifying your code"):
                st.session_state[RECOVERY_SESSION_KEY] = auth.verify_recovery_otp(email, code)
            st.session_state.pop(RECOVERY_EMAIL_KEY, None)
            st.session_state.pop(RECOVERY_UNCONFIRMED_KEY, None)
            st.query_params.pop("forgot_password", None)
            st.rerun()
    except AuthError as error:
        st.error(str(error))
    if st.session_state.get(RECOVERY_UNCONFIRMED_KEY):
        st.warning("Supabase took too long to respond. If an email arrives, use it before requesting another code.")


def _render_auth_form(auth):
    heading = st.empty()
    action = st.segmented_control(
        "Account access", ("Sign in", "Sign up"), default="Sign in", required=True,
        key="solar_auth_action", label_visibility="collapsed", width="stretch",
    )
    signing_up = action == "Sign up"
    heading.title("Create account" if signing_up else "Sign in", anchor=False)
    form_key = "solar_sign_up" if signing_up else "solar_sign_in"
    with st.form(form_key, clear_on_submit=True):
        email = st.text_input(
            "Email", autocomplete="email" if signing_up else "username",
            placeholder="Email address", label_visibility="collapsed", icon=":material/person:",
        ).strip()
        password = st.text_input(
            "Password", type="password", autocomplete="new-password" if signing_up else "current-password",
            placeholder="Password", label_visibility="collapsed", icon=":material/lock:",
        )
        confirmation = password
        if signing_up:
            confirmation = st.text_input(
                "Confirm password", type="password", autocomplete="new-password",
                placeholder="Confirm password", label_visibility="collapsed", icon=":material/lock:",
            )
        else:
            st.html(
                '<div class="sc-auth-forgot"><a class="sc-auth-link" href="?forgot_password=1">'
                'Forgot password?</a></div>'
            )
        submitted = st.form_submit_button(action, type="primary", width="stretch")
    if not submitted:
        return
    if not email or not password:
        st.error("Enter your email and password.")
        return
    if confirmation != password:
        st.error("Passwords must match.")
        return

    try:
        message = "Creating your account…" if signing_up else "Signing in…"
        with st.spinner(message):
            session = auth.sign_up(email, password) if signing_up else auth.sign_in(email, password)
    except AuthError as error:
        st.error(str(error))
        return
    if session is None:
        st.info(
            "If your email needs confirmation, check your inbox for the confirmation link. "
            "The link opens SolarCast, where you can select **Sign in**."
        )
        return
    st.session_state[SESSION_KEY] = session
    st.rerun()


def _accept_recovery_link(auth):
    query = st.query_params
    if RECOVERY_QUERY not in query:
        return None
    state, code = query[RECOVERY_QUERY], query.get("code", "")
    for key in (RECOVERY_QUERY, "code", "error", "error_code", "error_description"):
        query.pop(key, None)
    st.session_state.pop(RECOVERY_SESSION_KEY, None)
    try:
        st.session_state[RECOVERY_SESSION_KEY] = auth.exchange_recovery_code(state, code)
    except AuthError as error:
        return str(error)
    return None


def _render_password_reset(auth, recovery):
    st.subheader("Reset password")
    st.text(recovery.email)
    with st.form("solar_reset_password", clear_on_submit=True):
        new = st.text_input("New password", type="password", autocomplete="new-password")
        confirm = st.text_input("Confirm new password", type="password", autocomplete="new-password")
        submitted = st.form_submit_button("Reset password", type="primary", width="stretch")
    if st.button("Back to sign in", key="solar_cancel_password_reset"):
        st.session_state.pop(RECOVERY_SESSION_KEY, None)
        with suppress(AuthError):
            auth.sign_out(recovery)
        st.rerun()
    if not submitted:
        return
    if not new or new != confirm:
        st.error("Enter a new password and confirm it.")
        return
    try:
        with loading_ui.PageLoading(RECOVERY_LOADER, message="Resetting your password"):
            auth.reset_password(recovery, new)
    except AuthError as error:
        st.error(str(error))
        return

    st.session_state.pop(RECOVERY_SESSION_KEY, None)
    active = st.session_state.get(SESSION_KEY)
    if active is not None and active.email.casefold() == recovery.email.casefold():
        st.session_state.clear()
    st.session_state.solar_password_reset_complete = True
    st.rerun()


def require_sign_in():
    try:
        auth = configured_auth()
    except AuthError as error:
        st.error(str(error))
        st.stop()

    recovery_notice = _accept_recovery_link(auth)
    recovery = st.session_state.get(RECOVERY_SESSION_KEY)
    if recovery is not None and recovery.expires_at <= time():
        st.session_state.pop(RECOVERY_SESSION_KEY, None)
        recovery = None
        recovery_notice = "Your password reset session expired. Request a new code."
    session_ended = False
    session = st.session_state.get(SESSION_KEY)
    if recovery is None and auth_session_needs_refresh():
        try:
            session = auth.refresh(session)
            st.session_state[SESSION_KEY] = session
        except AuthError:
            st.session_state.clear()
            session = None
            session_ended = True
    if recovery is None and session:
        return auth, session

    styles.apply_auth_styles()
    with st.container(key="solar_auth_panel", width=420):
        requesting_reset = st.query_params.get("forgot_password") == "1"
        if recovery is not None or requesting_reset:
            st.title("SolarCast", anchor=False)
        if session_ended:
            st.warning("Your session ended. Please sign in again.")
        notice = st.session_state.pop("solar_sign_out_notice", None)
        if notice:
            st.warning(notice)
        if recovery_notice:
            st.warning(recovery_notice)
        if st.session_state.pop("solar_password_reset_complete", False):
            st.success("Password reset. Sign in with your new password.")
        if recovery is not None:
            _render_password_reset(auth, recovery)
        elif requesting_reset:
            opening = not st.session_state.get("solar_recovery_page_opened", False)
            st.session_state.solar_recovery_page_opened = True
            with loading_ui.PageLoading(RECOVERY_LOADER, enabled=opening):
                _render_reset_request(auth)
        else:
            _render_auth_form(auth)
    st.stop()


def render_sign_out(auth, session, *, button_key="solar_sign_out"):
    if st.button("Sign out", key=button_key, icon=":material/logout:", width="stretch"):
        st.session_state.clear()
        try:
            auth.sign_out(session)
        except AuthError:
            st.session_state.solar_sign_out_notice = (
                "Signed out of SolarCast. Supabase could not confirm session revocation."
            )
        st.rerun()


def _render_email_settings(auth, session):
    st.caption("Email address")
    with st.container(
        key="solar_profile_email_row", horizontal=True, wrap=False,
        vertical_alignment="center", horizontal_alignment="distribute",
    ):
        address = st.empty()
        with st.popover("Change email"):
            with st.form("solar_change_email", clear_on_submit=True, border=False):
                new_email = st.text_input("New email address", autocomplete="email").strip()
                submitted = st.form_submit_button("Send confirmation", type="primary", width="stretch")

    previous = session
    if submitted:
        try:
            if not new_email or new_email.casefold() == session.email.casefold():
                raise AuthError("Enter a different email address.")
            with st.spinner("Requesting an email change…"):
                session = auth.change_email(session, new_email)
        except AuthError as error:
            st.error(str(error))
    if session.pending_email and st.button("Check confirmation status", key="solar_check_email"):
        try:
            with st.spinner("Checking email confirmation…"):
                session = auth.email_status(session)
            if not session.pending_email and session.email == previous.email:
                st.info("There is no pending email change. Enter the new address to request another confirmation.")
        except AuthError as error:
            st.error(str(error))

    if session != previous:
        st.session_state[SESSION_KEY] = session
    address.text(session.email)
    if session.email != previous.email:
        st.success("Account email updated.")
    if session.pending_email:
        st.caption("Pending email address")
        st.text(session.pending_email)
        st.info("Follow the confirmation links from Supabase. Check both your current and new inboxes.")
    return session


def render_profile(auth, session):
    st.title("My Profile")
    with st.container(border=True, width=440):
        st.subheader("Account")
        session = _render_email_settings(auth, session)
        render_sign_out(auth, session, button_key="solar_profile_sign_out")

    with st.container(border=True, width=440):
        st.subheader("Change password")
        with st.form("solar_change_password", clear_on_submit=True, border=False):
            current = st.text_input("Current password", type="password", autocomplete="current-password")
            new = st.text_input("New password", type="password", autocomplete="new-password")
            confirm = st.text_input("Confirm new password", type="password", autocomplete="new-password")
            submitted = st.form_submit_button("Update password", type="primary", width="stretch")
        if not submitted:
            return
        if not current or not new or not confirm:
            st.error("Complete all three password fields.")
        elif new != confirm:
            st.error("The new passwords do not match.")
        elif new == current:
            st.error("Choose a password different from your current password.")
        else:
            try:
                with st.spinner("Updating your password…"):
                    st.session_state[SESSION_KEY] = auth.change_password(session, current, new)
            except AuthError as error:
                st.error(str(error))
            else:
                st.success("Password updated. Use your new password the next time you sign in.")
