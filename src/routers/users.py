from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
import bcrypt

from src.database import get_db
from src.limiter import limiter, RATE_LIMIT_LOGIN, RATE_LIMIT_REGISTER
from src.models import User, Route, Spot
from src.schemas import (
    UserCreate, UserResponse, LoginRequest, TokenResponse, UpdateUserRequest,
    GoogleAuthRequest, AppleAuthRequest,
)
from src.auth import create_access_token, get_current_user
from src.oauth import verify_google_token, verify_apple_token

router = APIRouter(prefix="/users", tags=["users"])

# Used when a new OAuth account has no real name to fall back on (Apple only
# sends a name on the very first authorization, and a Hide My Email address
# has no usable local-part) — friendlier than an email-derived string like a
# private relay's random "fm4w7tyrjj". The frontend treats this value
# specially (My Account shows an "Add name" prompt instead of it).
PLACEHOLDER_FIRST_NAME = "there"


def _login_or_create_oauth_user(db: Session, email: str, first_name: str, provider_field: str, provider_sub: str) -> User:
    user = db.query(User).filter(getattr(User, provider_field) == provider_sub).first()
    if user:
        return user

    # Same email already registered (via password or another provider) —
    # link this identity to it rather than erroring, per product decision.
    user = db.query(User).filter(User.email == email).first()
    if user:
        setattr(user, provider_field, provider_sub)
        db.commit()
        db.refresh(user)
        return user

    user = User(first_name=first_name, email=email, hashed_password=None)
    setattr(user, provider_field, provider_sub)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/register", response_model=TokenResponse, status_code=201)
@limiter.limit(RATE_LIMIT_REGISTER)
def register(request: Request, user: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed = bcrypt.hashpw(user.password.encode(), bcrypt.gensalt()).decode()
    new_user = User(
        first_name=user.first_name,
        email=user.email,
        hashed_password=hashed,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    token = create_access_token(new_user.id)
    return {"access_token": token, "token_type": "bearer", "user": new_user}


@router.post("/login", response_model=TokenResponse)
@limiter.limit(RATE_LIMIT_LOGIN)
def login(request: Request, credentials: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == credentials.email).first()
    if (
        not user
        or not user.hashed_password
        or not bcrypt.checkpw(credentials.password.encode(), user.hashed_password.encode())
    ):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(user.id)
    return {"access_token": token, "token_type": "bearer", "user": user}


@router.post("/auth/google", response_model=TokenResponse)
@limiter.limit(RATE_LIMIT_LOGIN)
def google_auth(request: Request, body: GoogleAuthRequest, db: Session = Depends(get_db)):
    idinfo = verify_google_token(body.id_token)
    email = idinfo["email"]
    first_name = idinfo.get("given_name") or (idinfo.get("name") or "").split(" ")[0] or PLACEHOLDER_FIRST_NAME
    user = _login_or_create_oauth_user(db, email, first_name, "google_sub", idinfo["sub"])
    token = create_access_token(user.id)
    return {"access_token": token, "token_type": "bearer", "user": user}


@router.post("/auth/apple", response_model=TokenResponse)
@limiter.limit(RATE_LIMIT_LOGIN)
def apple_auth(request: Request, body: AppleAuthRequest, db: Session = Depends(get_db)):
    claims = verify_apple_token(body.id_token)
    email = claims.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Apple did not provide an email for this account")
    first_name = body.first_name or PLACEHOLDER_FIRST_NAME
    user = _login_or_create_oauth_user(db, email, first_name, "apple_sub", claims["sub"])
    token = create_access_token(user.id)
    return {"access_token": token, "token_type": "bearer", "user": user}


@router.patch("/me", response_model=UserResponse)
def update_me(
    body: UpdateUserRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.first_name is not None:
        current_user.first_name = body.first_name
    if body.pref_max_detour is not None:
        current_user.pref_max_detour = body.pref_max_detour
    if body.pref_mode is not None:
        current_user.pref_mode = body.pref_mode
    if body.pref_map_controls is not None:
        current_user.pref_map_controls = body.pref_map_controls
    if body.pref_map_type is not None:
        current_user.pref_map_type = body.pref_map_type
    db.commit()
    db.refresh(current_user)
    return current_user


@router.delete("/me", status_code=204)
def delete_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db.query(Route).filter(Route.user_id == current_user.id).delete()
    db.query(Spot).filter(Spot.user_id == current_user.id).delete()
    db.delete(current_user)
    db.commit()
