import time
from urllib.parse import urlencode

import httpx

from app.config import get_settings

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
SCOPES = ["https://www.googleapis.com/auth/business.manage", "openid", "email"]


def redirect_uri() -> str:
    return get_settings().base_url.rstrip("/") + "/oauth/callback"


def authorization_url(state: str) -> str:
    params = {
        "client_id": get_settings().google_client_id,
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def exchange_code(code: str) -> tuple[str, str]:
    """Return (email, refresh_token) for an authorization code."""
    s = get_settings()
    resp = httpx.post(TOKEN_URL, data={
        "code": code,
        "client_id": s.google_client_id,
        "client_secret": s.google_client_secret,
        "redirect_uri": redirect_uri(),
        "grant_type": "authorization_code",
    }, timeout=30)
    resp.raise_for_status()
    tokens = resp.json()
    if "refresh_token" not in tokens:
        raise RuntimeError("Google did not return a refresh token")
    info = httpx.get(USERINFO_URL, headers={"Authorization": f"Bearer {tokens['access_token']}"}, timeout=30)
    info.raise_for_status()
    return info.json().get("email", ""), tokens["refresh_token"]


class TokenProvider:
    def __init__(self, refresh_token: str):
        self._refresh_token = refresh_token
        self._access_token = ""
        self._expires_at = 0.0

    def access_token(self) -> str:
        if time.time() < self._expires_at - 60:
            return self._access_token
        s = get_settings()
        resp = httpx.post(TOKEN_URL, data={
            "client_id": s.google_client_id,
            "client_secret": s.google_client_secret,
            "refresh_token": self._refresh_token,
            "grant_type": "refresh_token",
        }, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data["access_token"]
        self._expires_at = time.time() + data.get("expires_in", 3600)
        return self._access_token
