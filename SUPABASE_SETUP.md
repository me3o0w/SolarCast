# SolarCast database

SolarCast saves completed live Overview and manual predictions to the signed-in
account in Supabase. **Prediction history** shows those results and lets you
compare their estimated AC power. Next-day forecasts are available on screen and
as CSV downloads.

## Connect a project

The SolarCast project has been created in Singapore under `me3o0w's Org`,
and its migrations have been applied.

- [Project dashboard](https://supabase.com/dashboard/project/ypwcuspzylvrefurponv)
- [API Keys settings](https://supabase.com/dashboard/project/ypwcuspzylvrefurponv/settings/api-keys)
- Project URL: `https://ypwcuspzylvrefurponv.supabase.co`

1. Create a Supabase project at https://supabase.com/dashboard, or connect the
   Supabase integration in Codex so the project and schema can be provisioned there.
2. Apply the SQL files in `supabase/migrations/` in filename order in the project's SQL editor.
3. Configure sign-in and sign-up below, then restart Streamlit.
4. Sign in, run **Manual prediction**, and open **Prediction history** to verify
   that the result appears in your account.

## Shared archive maintenance

The archive commands use the project's server secret key or legacy `service_role`
key. Set `secret_key` in the gitignored `.streamlit/secrets.toml` file or set
`SUPABASE_SECRET_KEY` in the server environment.

```powershell
.venv/Scripts/python.exe scripts/supabase_database.py check
.venv/Scripts/python.exe scripts/supabase_database.py migrate-local
```

`migrate-local` copies SQLite snapshots into the shared archive, skips duplicate
snapshots on reruns, and preserves the original SQLite records.

## Set up sign-in and sign-up

1. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`. Set `url`
   to the project's HTTPS URL and `publishable_key` to the project's
   `sb_publishable_…` key from **Settings → API Keys**.
   You can also set `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` in the server environment.
2. In Supabase Authentication settings, enable the Email provider and allow
   new users to sign up. SolarCast sends its local URL (normally
   `http://localhost:8501`) as the confirmation redirect. For a hosted app, set
   `auth_redirect_url` in the `[supabase]` secrets section or set
   `SUPABASE_AUTH_REDIRECT_URL` to the deployed HTTPS URL. Use the app URL as
   the **Site URL** or add it under **Redirect URLs** in Supabase **URL Configuration**.
3. When email confirmation is enabled, configure custom SMTP to send confirmation
   emails to users outside the Supabase project team. Supabase's built-in mail
   service only sends to team addresses. [Supabase SMTP setup](https://supabase.com/docs/guides/auth/auth-smtp)
4. Open SolarCast, choose **Sign up**, and enter your email and password.
   If confirmation is enabled, follow the link in your email and return to
   SolarCast to choose **Sign in**. Use **Sign out** in the sidebar to end your
   session. Reloading the browser starts a new Streamlit session.

If an existing confirmation link opens an unreachable page, open SolarCast
directly and try signing in. Supabase may have confirmed your email before
redirecting your browser. New confirmation emails use the redirect configured
when they are sent.

**Forgot password?** accepts a one-time code from the Supabase recovery email.
Enable custom SMTP in Supabase and edit **Authentication → Emails → Reset password**
to use the subject **Your SolarCast password reset code** and this body:

```html
<h2>Reset your SolarCast password</h2>
<p>Enter this one-time code in SolarCast:</p>
<p><strong>{{ .Token }}</strong></p>
<p>If you did not request a password reset, you can ignore this email.</p>
```

Save the template, then set `password_recovery_codes_enabled = true` under
`[supabase]` in SolarCast's secrets. The app keeps recovery email requests
disabled until this setting is enabled.

## Data and access

`public.solarcast_account_predictions` stores each account's results, model
inputs, and prediction and save times. Supabase assigns ownership from the active
session. Row Level Security lets accounts read and insert only their own rows.
Overview saves the first result from fresh weather each hour per account while
Overview is open. Manual results save on submission. Times are displayed in
Asia/Manila.

Previously saved next-day forecasts remain in their existing Supabase tables
and local SQLite archive.

References: [Supabase API keys](https://supabase.com/docs/guides/getting-started/api-keys),
[Data REST API](https://supabase.com/docs/guides/api),
[PostgREST upsert](https://docs.postgrest.org/en/stable/references/api/tables_views.html#upsert).
