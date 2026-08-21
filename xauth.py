import base64
import hashlib
import os
import secrets
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv

load_dotenv()

AUTHORIZE_URL = "https://twitter.com/i/oauth2/authorize"
TOKEN_URL = "https://api.twitter.com/2/oauth2/token"

CLIENT_ID = os.environ.get("X_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("X_CLIENT_SECRET", "")
REDIRECT_URI = os.environ.get("X_REDIRECT_URI", "")
SCOPES = "tweet.read tweet.write users.read like.write offline.access"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def new_state() -> str:
    return secrets.token_urlsafe(24)


def new_pkce_pair() -> tuple[str, str]:
    verifier = _b64url(secrets.token_bytes(32))
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


def build_authorize_url(state: str, code_challenge: str) -> str:
    if not CLIENT_ID or not REDIRECT_URI:
        raise RuntimeError(
            "Faltan X_CLIENT_ID y/o X_REDIRECT_URI en las variables de entorno."
        )
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def _token_request(data: dict) -> dict:
    auth = (CLIENT_ID, CLIENT_SECRET) if CLIENT_SECRET else None
    if auth is None:
        data = {**data, "client_id": CLIENT_ID}
    response = requests.post(TOKEN_URL, data=data, auth=auth, timeout=15)
    response.raise_for_status()
    return response.json()


def exchange_code(code: str, code_verifier: str) -> dict:
    return _token_request(
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": code_verifier,
        }
    )


def refresh_access_token(refresh_token_value: str) -> dict:
    return _token_request(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token_value,
        }
    )
