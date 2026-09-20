import os

import requests
from fastapi import HTTPException
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from jose import jwt as jose_jwt
from jose.exceptions import JOSEError

GOOGLE_CLIENT_IDS = [c.strip() for c in os.getenv("GOOGLE_OAUTH_CLIENT_IDS", "").split(",") if c.strip()]
APPLE_CLIENT_IDS = [c.strip() for c in os.getenv("APPLE_OAUTH_CLIENT_IDS", "").split(",") if c.strip()]
APPLE_KEYS_URL = "https://appleid.apple.com/auth/keys"
APPLE_ISSUER = "https://appleid.apple.com"


def verify_google_token(token: str) -> dict:
    """Verify a Google ID token and return its claims, or raise 401."""
    try:
        idinfo = google_id_token.verify_oauth2_token(token, google_requests.Request())
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid Google token")

    if not GOOGLE_CLIENT_IDS or idinfo.get("aud") not in GOOGLE_CLIENT_IDS:
        raise HTTPException(status_code=401, detail="Invalid Google token")
    if not idinfo.get("email_verified"):
        raise HTTPException(status_code=401, detail="Google account email is not verified")
    return idinfo


def verify_apple_token(token: str) -> dict:
    """Verify an Apple ID token and return its claims, or raise 401."""
    try:
        unverified_header = jose_jwt.get_unverified_header(token)
        apple_keys = requests.get(APPLE_KEYS_URL, timeout=5).json().get("keys", [])
        key = next((k for k in apple_keys if k.get("kid") == unverified_header.get("kid")), None)
        if key is None:
            raise ValueError("No matching Apple signing key")
        # aud/iss are checked manually below (against a list of allowed
        # client IDs, one per platform) rather than passed to decode(),
        # which only supports a single expected audience.
        claims = jose_jwt.decode(token, key, algorithms=["RS256"], options={"verify_aud": False})
    except (JOSEError, ValueError, requests.RequestException):
        raise HTTPException(status_code=401, detail="Invalid Apple token")

    if claims.get("iss") != APPLE_ISSUER:
        raise HTTPException(status_code=401, detail="Invalid Apple token")
    if not APPLE_CLIENT_IDS or claims.get("aud") not in APPLE_CLIENT_IDS:
        raise HTTPException(status_code=401, detail="Invalid Apple token")
    return claims
