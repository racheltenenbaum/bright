from pydantic import BaseModel, EmailStr, field_validator
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


class UpdateUserRequest(BaseModel):
    first_name: str

    @field_validator("first_name")
    @classmethod
    def not_blank(cls, v):
        if not v.strip():
            raise ValueError("first_name cannot be blank")
        return v.strip()


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class ShareTokenResponse(BaseModel):
    share_token: str


class SharedRouteResponse(BaseModel):
    name: str
    description: str | None
    start_lat: float
    start_lng: float
    end_lat: float
    end_lng: float
    start_address: str | None
    end_address: str | None
    preference: str | None
    route_path: str | None

    model_config = {"from_attributes": True}


class RouteCreate(BaseModel):
    name: str
    description: str | None = None
    start_lat: float
    start_lng: float
    end_lat: float
    end_lng: float
    start_address: str | None = None
    end_address: str | None = None
    preference: str | None = None
    route_path: str | None = None


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
    preference: str | None
    route_path: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
