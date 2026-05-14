from pydantic import BaseModel, EmailStr
from datetime import datetime


class UserCreate(BaseModel):
    first_name: str
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    first_name: str
    email: str
    created_at: datetime

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class RouteCreate(BaseModel):
    name: str
    description: str | None = None
    start_lat: float
    start_lng: float
    end_lat: float
    end_lng: float
    start_address: str | None = None
    end_address: str | None = None


class RouteResponse(BaseModel):
    id: int
    name: str
    description: str | None
    start_lat: float
    start_lng: float
    end_lat: float
    end_lng: float
    start_address: str | None
    end_address: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
