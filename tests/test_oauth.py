from unittest.mock import patch, MagicMock

import pytest
from fastapi import HTTPException
from jose import jwt as jose_jwt

from src import oauth


# --- Google ---

def test_verify_google_token_success():
    idinfo = {"aud": "web-client-id", "email": "a@example.com", "email_verified": True, "sub": "g-123"}
    with patch.object(oauth, "GOOGLE_CLIENT_IDS", ["web-client-id"]), \
         patch("src.oauth.google_id_token.verify_oauth2_token", return_value=idinfo):
        result = oauth.verify_google_token("some-token")
    assert result == idinfo


def test_verify_google_token_invalid_raises_401():
    with patch("src.oauth.google_id_token.verify_oauth2_token", side_effect=ValueError("bad token")):
        with pytest.raises(HTTPException) as exc_info:
            oauth.verify_google_token("bad-token")
    assert exc_info.value.status_code == 401


def test_verify_google_token_wrong_audience_raises_401():
    idinfo = {"aud": "someone-elses-client-id", "email": "a@example.com", "email_verified": True, "sub": "g-123"}
    with patch.object(oauth, "GOOGLE_CLIENT_IDS", ["web-client-id"]), \
         patch("src.oauth.google_id_token.verify_oauth2_token", return_value=idinfo):
        with pytest.raises(HTTPException) as exc_info:
            oauth.verify_google_token("some-token")
    assert exc_info.value.status_code == 401


def test_verify_google_token_unverified_email_raises_401():
    idinfo = {"aud": "web-client-id", "email": "a@example.com", "email_verified": False, "sub": "g-123"}
    with patch.object(oauth, "GOOGLE_CLIENT_IDS", ["web-client-id"]), \
         patch("src.oauth.google_id_token.verify_oauth2_token", return_value=idinfo):
        with pytest.raises(HTTPException) as exc_info:
            oauth.verify_google_token("some-token")
    assert exc_info.value.status_code == 401


def test_verify_google_token_no_configured_client_ids_raises_401():
    idinfo = {"aud": "web-client-id", "email": "a@example.com", "email_verified": True, "sub": "g-123"}
    with patch.object(oauth, "GOOGLE_CLIENT_IDS", []), \
         patch("src.oauth.google_id_token.verify_oauth2_token", return_value=idinfo):
        with pytest.raises(HTTPException) as exc_info:
            oauth.verify_google_token("some-token")
    assert exc_info.value.status_code == 401


# --- Apple ---

def _apple_jwk_and_token(claims, kid="test-kid"):
    from cryptography.hazmat.primitives.asymmetric import rsa
    from jose.backends.cryptography_backend import CryptographyRSAKey
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    rsa_key = CryptographyRSAKey(key, algorithm="RS256")
    public_jwk = rsa_key.public_key().to_dict()
    public_jwk["kid"] = kid
    token = jose_jwt.encode(claims, key, algorithm="RS256", headers={"kid": kid})
    return public_jwk, token


def _mock_apple_keys_response(jwks):
    m = MagicMock()
    m.json.return_value = {"keys": jwks}
    return m


def test_verify_apple_token_success():
    claims = {"iss": "https://appleid.apple.com", "aud": "com.racheltenenbaum.bright", "sub": "a-123", "email": "a@example.com"}
    jwk, token = _apple_jwk_and_token(claims)
    with patch.object(oauth, "APPLE_CLIENT_IDS", ["com.racheltenenbaum.bright"]), \
         patch("src.oauth.requests.get", return_value=_mock_apple_keys_response([jwk])):
        result = oauth.verify_apple_token(token)
    assert result["sub"] == "a-123"
    assert result["email"] == "a@example.com"


def test_verify_apple_token_no_matching_key_raises_401():
    claims = {"iss": "https://appleid.apple.com", "aud": "com.racheltenenbaum.bright", "sub": "a-123", "email": "a@example.com"}
    _jwk, token = _apple_jwk_and_token(claims, kid="key-a")
    other_jwk, _ = _apple_jwk_and_token(claims, kid="key-b")
    with patch.object(oauth, "APPLE_CLIENT_IDS", ["com.racheltenenbaum.bright"]), \
         patch("src.oauth.requests.get", return_value=_mock_apple_keys_response([other_jwk])):
        with pytest.raises(HTTPException) as exc_info:
            oauth.verify_apple_token(token)
    assert exc_info.value.status_code == 401


def test_verify_apple_token_wrong_issuer_raises_401():
    claims = {"iss": "https://evil.example.com", "aud": "com.racheltenenbaum.bright", "sub": "a-123", "email": "a@example.com"}
    jwk, token = _apple_jwk_and_token(claims)
    with patch.object(oauth, "APPLE_CLIENT_IDS", ["com.racheltenenbaum.bright"]), \
         patch("src.oauth.requests.get", return_value=_mock_apple_keys_response([jwk])):
        with pytest.raises(HTTPException) as exc_info:
            oauth.verify_apple_token(token)
    assert exc_info.value.status_code == 401


def test_verify_apple_token_wrong_audience_raises_401():
    claims = {"iss": "https://appleid.apple.com", "aud": "some.other.app", "sub": "a-123", "email": "a@example.com"}
    jwk, token = _apple_jwk_and_token(claims)
    with patch.object(oauth, "APPLE_CLIENT_IDS", ["com.racheltenenbaum.bright"]), \
         patch("src.oauth.requests.get", return_value=_mock_apple_keys_response([jwk])):
        with pytest.raises(HTTPException) as exc_info:
            oauth.verify_apple_token(token)
    assert exc_info.value.status_code == 401


def test_verify_apple_token_malformed_token_raises_401():
    with patch("src.oauth.requests.get", return_value=_mock_apple_keys_response([])):
        with pytest.raises(HTTPException) as exc_info:
            oauth.verify_apple_token("not-a-real-jwt")
    assert exc_info.value.status_code == 401


def test_verify_apple_token_apple_keys_request_fails_raises_401():
    import requests as requests_module
    with patch("src.oauth.requests.get", side_effect=requests_module.RequestException("timeout")):
        with pytest.raises(HTTPException) as exc_info:
            oauth.verify_apple_token("irrelevant")
    assert exc_info.value.status_code == 401
