# AI Chat Agent

A FastAPI starter for a Google-authenticated GPT-OSS-120B support chat. It includes a SQLite conversation history, a 100-user-message UTC daily free tier, integration settings, and a bounded tool-calling agent. Integration credentials are encrypted at rest.

## Run locally

1. Use Python 3.11+ and create an environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   Copy-Item .env.example .env
   ```

2. Set `SECRET_KEY`, Google OAuth credentials, and `MODEL_API_KEY` in `.env`. Generate two independent keys:

   ```powershell
   py -c "import secrets; print(secrets.token_urlsafe(48))"
   py -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

   Use the first value for `SECRET_KEY` and the second for `API_KEY_ENCRYPTION_KEY`. Register `http://localhost:8000/auth/callback` as an authorized Google OAuth redirect URI.

3. Start the server:

   ```powershell
   uvicorn app.main:app --reload --env-file .env
   ```

   Open `http://localhost:8000`. API docs are available at `/docs`.

The model endpoint uses the OpenAI-compatible Chat Completions API. Adjust `MODEL_BASE_URL`, `MODEL_NAME`, and `MODEL_API_KEY` for the provider and account that offer GPT-OSS-120B.

## Agent tools

The model may call two server-controlled, read-only tools: check the signed-in user's quota and check whether that user's integrations are configured. Tool calls are limited to four model turns per request, and tools cannot access stored credentials.

## Integrations

The settings page stores a WhatsApp phone number/API key and an e-commerce platform/store URL/API key. This starter only stores those settings; it does not yet send WhatsApp messages or call store APIs. Use provider-issued credentials and keep all environment secrets private.

## Deploy to Render

1. Push this directory to a Git repository and create a Render Blueprint from `render.yaml`.
2. Set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `MODEL_API_KEY`, and `API_KEY_ENCRYPTION_KEY` in the Render service environment. Set `GOOGLE_REDIRECT_URI` to `https://<your-service>.onrender.com/auth/callback`, and add that exact URI in Google Cloud OAuth settings.
3. Preserve the generated `SECRET_KEY` and `API_KEY_ENCRYPTION_KEY`. Losing or changing the encryption key makes saved integration credentials unreadable.

The Render configuration mounts a persistent disk at `/data` for SQLite. For multiple application instances or higher traffic, move the database to a managed PostgreSQL service before scaling.

## Deploy the Streamlit frontend

The Streamlit app is a separate frontend for the FastAPI service; deploy the backend first (for example, using the Render instructions above).

1. In Streamlit Community Cloud, create an app from this repository and set `streamlit_app.py` as the entry point.
2. Generate a `STREAMLIT_AUTH_SECRET` with `python -c "import secrets; print(secrets.token_urlsafe(48))"`, then add these values in the app's Secrets:

   ```toml
   BACKEND_URL = "https://<your-service>.onrender.com"
   STREAMLIT_AUTH_SECRET = "<same-long-random-secret-configured-on-the-backend>"

   [auth]
   redirect_uri = "https://<your-streamlit-app>.streamlit.app/oauth2callback"
   cookie_secret = "<another-long-random-secret>"
   client_id = "<Google OAuth client ID>"
   client_secret = "<Google OAuth client secret>"
   server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
   ```

3. Configure the same `STREAMLIT_AUTH_SECRET` as a backend environment variable. Add the Streamlit `redirect_uri` to the authorized redirect URIs for the Google OAuth client. The frontend and backend must use HTTPS in production.

The Streamlit app authenticates users with Google and signs each backend request. Keep `STREAMLIT_AUTH_SECRET` private and identical in both deployments; do not expose it in browser code or commit it to the repository. The backend retains message history, quotas, and encrypted integration settings in its configured database.

## Notes

- The quota is counted by UTC date and applies to accepted user messages.
- Premium pricing/checkout is not configured; after the free quota, the API reports that upgrade options are unavailable.
- A new provider request is made for each user message. The stored credentials are not passed to the model.
