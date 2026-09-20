from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import os

from src.database import get_db
from src.models import User

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable is not set")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/login")
# auto_error=False: resolves to None instead of raising 401 when no
# Authorization header is sent, so get_current_user_optional can support
# anonymous use of endpoints that work fine without an account (routing,
# shadow-analyze, places, weather) while still personalizing for a logged-in
# user (e.g. pref_max_detour) when a valid token is present.
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/users/login", auto_error=False)


def create_access_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_password_reset_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        # Marks this as a single-purpose token so it can't double as a
        # bearer access token (get_current_user rejects anything carrying a
        # "purpose" claim) — a leaked reset-email link must not itself grant
        # login access to the account.
        "purpose": "password_reset",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_password_reset_token(token: str) -> int:
    """Returns the user id encoded in a password-reset token, or raises 400."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("purpose") != "password_reset":
            raise JWTError("not a password reset token")
        return int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("purpose"):
            raise JWTError("not an access token")
        user_id = int(payload["sub"])
    except (JWTError, KeyError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def get_current_user_optional(
    token: str | None = Depends(oauth2_scheme_optional), db: Session = Depends(get_db)
) -> User | None:
    """Like get_current_user, but returns None instead of raising for a
    missing, invalid, or expired token — for endpoints usable without an
    account. A malformed/expired token (e.g. a stale one left in
    localStorage) is treated the same as no token at all, not an error,
    since the point is to degrade to anonymous rather than block the
    request."""
    if token is None:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("purpose"):
            return None
        user_id = int(payload["sub"])
    except (JWTError, KeyError):
        return None
    return db.get(User, user_id)
