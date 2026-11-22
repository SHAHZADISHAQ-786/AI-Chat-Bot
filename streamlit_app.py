import os
import time
from urllib.parse import urlparse

import httpx
import streamlit as st
from dotenv import load_dotenv

from app.streamlit_auth import sign_streamlit_identity


load_dotenv()


class BackendError(RuntimeError):
    def __init__(self, message: str, payload: object = None) -> None:
        super().__init__(message)
        self.payload = payload


st.set_page_config(page_title="Support AI", page_icon="💬")
st.title("Support AI")
st.caption("Ask a question and get a helpful AI-powered answer.")


def configured_value(name: str) -> str:
    try:
        return st.secrets.get(name, os.getenv(name, ""))
    except FileNotFoundError:
        return os.getenv(name, "")


backend_url = configured_value("BACKEND_URL").rstrip("/")
auth_secret = configured_value("STREAMLIT_AUTH_SECRET")
if not backend_url:
    st.error("Set BACKEND_URL in Streamlit Secrets to your FastAPI service URL.")
    st.stop()
parsed_backend_url = urlparse(backend_url)
if parsed_backend_url.scheme != "https" and parsed_backend_url.hostname not in {
    "localhost",
    "127.0.0.1",
}:
    st.error("BACKEND_URL must use HTTPS.")
    st.stop()
if not auth_secret:
    st.error("Set STREAMLIT_AUTH_SECRET in Streamlit Secrets.")
    st.stop()

if not st.user.is_logged_in:
    st.info("Sign in with your Google account to continue.")
    st.button("Continue with Google", on_click=st.login)
    st.stop()

user = st.user
subject = str(user.get("sub", ""))
email = str(user.get("email", ""))
name = str(user.get("name") or email)
email_verified = str(user.get("email_verified", "")).lower()
if not subject or not email or email_verified != "true":
    st.error("A verified Google account is required.")
    st.stop()

if st.session_state.get("identity_subject") != subject:
    st.session_state.pop("messages", None)
    st.session_state.pop("usage", None)
    st.session_state.identity_subject = subject

timestamp = str(int(time.time()))
signature = sign_streamlit_identity(
    auth_secret, subject, email, name, email_verified, timestamp
)
headers = {
    "X-Streamlit-Subject": subject,
    "X-Streamlit-Email": email,
    "X-Streamlit-Name": name,
    "X-Streamlit-Email-Verified": email_verified,
    "X-Streamlit-Timestamp": timestamp,
    "X-Streamlit-Signature": signature,
}


def backend_request(method: str, path: str, **kwargs: object) -> dict:
    try:
        response = httpx.request(
            method,
            f"{backend_url}{path}",
            headers=headers,
            timeout=30,
            **kwargs,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        try:
            payload = exc.response.json()
        except ValueError:
            payload = None
        detail = payload.get("detail") if isinstance(payload, dict) else None
        message = detail.get("message") if isinstance(detail, dict) else detail
        raise BackendError(
            str(message or exc.response.text or "Backend request failed."),
            payload,
        ) from exc
    except httpx.HTTPError as exc:
        raise BackendError(f"Unable to reach the FastAPI backend: {exc}") from exc
    return response.json()


try:
    profile = backend_request("GET", "/api/me")
except BackendError as exc:
    st.error(str(exc))
    st.stop()

st.sidebar.caption(f"Signed in as {profile['name']}")
st.sidebar.button("Sign out", on_click=st.logout)
usage = st.session_state.get("usage", profile["usage"])
st.caption(
    f"{usage['remaining']} of {usage['limit']} free messages left today"
)

with st.sidebar.expander("Integrations"):
    try:
        integrations = backend_request("GET", "/api/integrations")
    except BackendError as exc:
        st.error(str(exc))
    else:
        ecommerce_options = ["", "shopify", "woocommerce", "other"]
        ecommerce_value = integrations["ecommerce_type"] or ""
        if ecommerce_value not in ecommerce_options:
            ecommerce_value = ""
        st.caption(
            f"WhatsApp key {'saved' if integrations['whatsapp_api_key_set'] else 'not set'}"
            f" · Store key {'saved' if integrations['ecommerce_api_key_set'] else 'not set'}"
        )
        with st.form("integration_settings"):
            whatsapp_phone = st.text_input(
                "WhatsApp phone number", value=integrations["whatsapp_phone"] or ""
            )
            whatsapp_api_key = st.text_input(
                "WhatsApp API key", type="password", placeholder="Leave blank to keep saved key"
            )
            ecommerce_type = st.selectbox(
                "E-commerce platform",
                ecommerce_options,
                index=ecommerce_options.index(ecommerce_value),
            )
            ecommerce_url = st.text_input(
                "Store URL", value=integrations["ecommerce_url"] or ""
            )
            ecommerce_api_key = st.text_input(
                "Store API key", type="password", placeholder="Leave blank to keep saved key"
            )
            save_integrations = st.form_submit_button("Save settings")
        if save_integrations:
            try:
                backend_request(
                    "PUT",
                    "/api/integrations",
                    json={
                        "whatsapp_phone": whatsapp_phone or None,
                        "whatsapp_api_key": whatsapp_api_key or None,
                        "ecommerce_type": ecommerce_type or None,
                        "ecommerce_url": ecommerce_url or None,
                        "ecommerce_api_key": ecommerce_api_key or None,
                    },
                )
            except BackendError as exc:
                st.error(str(exc))
            else:
                st.success("Settings saved.")

if "messages" not in st.session_state:
    try:
        st.session_state.messages = backend_request("GET", "/api/messages")["messages"]
    except BackendError as exc:
        st.error(str(exc))
        st.stop()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

prompt = st.chat_input("Type your message...", max_chars=4000)
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                result = backend_request(
                    "POST", "/api/chat", json={"message": prompt}
                )
            except BackendError as exc:
                payload = exc.payload
                detail = payload.get("detail") if isinstance(payload, dict) else None
                if isinstance(detail, dict) and "usage" in detail:
                    st.session_state.usage = detail["usage"]
                st.error(str(exc))
            else:
                st.session_state.messages.append(
                    {"role": "assistant", "content": result["reply"]}
                )
                st.session_state.usage = result["usage"]
                st.markdown(result["reply"])
