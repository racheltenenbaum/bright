from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
import bcrypt

from src.database import get_db
from src.limiter import limiter, RATE_LIMIT_LOGIN, RATE_LIMIT_REGISTER
from src.models import User
from src.schemas import UserCreate, UserResponse, LoginRequest, TokenResponse, UpdateUserRequest
from src.auth import create_access_token, get_current_user

router = APIRouter(prefix="/users", tags=["users"])


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
    if not user or not bcrypt.checkpw(credentials.password.encode(), user.hashed_password.encode()):
        raise HTTPException(status_code=401, detail="Invalid email or password")

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
