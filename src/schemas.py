from pydantic import BaseModel, EmailStr, field_validator
from datetime import datetime


VALID_SPOT_ICONS = frozenset({
    "faMugHot", "faMugSaucer", "faUtensils", "faPizzaSlice", "faBurger",
    "faDrumstickBite", "faFish", "faBowlFood", "faBreadSlice", "faCookieBite",
    "faCakeCandles", "faIceCream", "faEgg", "faCarrot", "faLeaf", "faLemon",
    "faBeerMugEmpty", "faWineGlass", "faMartiniGlassCitrus", "faGlassWhiskey",
    "faChampagneGlasses", "faHouse", "faBriefcase", "faDumbbell", "faGraduationCap",
    "faShoppingCart", "faHeart", "faStar", "faMapPin", "faBicycle", "faMusic",
    "faTree", "faPlane", "faTrain", "faBus", "faBed", "faCamera", "faBook", "faSun",
})


class UserCreate(BaseModel):
    first_name: str
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("password must be at least 8 characters")
        if not any(c.isdigit() for c in v):
            raise ValueError("password must contain at least one number")
        return v


class UserResponse(BaseModel):
    id: int
    first_name: str
    email: str
    created_at: datetime
    pref_max_detour: int = 30
    pref_mode: str = "sun"
    pref_map_controls: bool = False
    pref_map_type: str = "roadmap"

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UpdateUserRequest(BaseModel):
    first_name: str | None = None
    pref_max_detour: int | None = None
    pref_mode: str | None = None
    pref_map_controls: bool | None = None
    pref_map_type: str | None = None

    @field_validator("first_name")
    @classmethod
    def not_blank(cls, v):
        if v is None:
            return v
        if not v.strip():
            raise ValueError("first_name cannot be blank")
        return v.strip()

    @field_validator("pref_max_detour")
    @classmethod
    def valid_detour(cls, v):
        if v is not None and not (1 <= v <= 100):
            raise ValueError("pref_max_detour must be between 1 and 100")
        return v

    @field_validator("pref_mode")
    @classmethod
    def valid_mode(cls, v):
        if v is not None and v not in ("sun", "shade"):
            raise ValueError("pref_mode must be 'sun' or 'shade'")
        return v

    @field_validator("pref_map_type")
    @classmethod
    def valid_map_type(cls, v):
        if v is not None and v not in ("roadmap", "satellite", "terrain", "hybrid"):
            raise ValueError("pref_map_type must be roadmap, satellite, terrain, or hybrid")
        return v


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


class SharedSpotResponse(BaseModel):
    name: str
    address: str
    lat: float
    lng: float
    icon: str
    city: str
    description: str | None
    place_id: str | None

    model_config = {"from_attributes": True}


class SpotCreate(BaseModel):
    name: str
    address: str
    lat: float
    lng: float
    icon: str
    city: str
    description: str | None = None
    place_id: str | None = None

    @field_validator("icon")
    @classmethod
    def valid_icon(cls, v):
        if v not in VALID_SPOT_ICONS:
            raise ValueError(f"invalid icon key: {v}")
        return v

    @field_validator("lat")
    @classmethod
    def valid_lat(cls, v):
        if not -90 <= v <= 90:
            raise ValueError("lat must be between -90 and 90")
        return v

    @field_validator("lng")
    @classmethod
    def valid_lng(cls, v):
        if not -180 <= v <= 180:
            raise ValueError("lng must be between -180 and 180")
        return v


class SpotResponse(BaseModel):
    id: int
    name: str
    address: str
    lat: float
    lng: float
    icon: str
    city: str
    description: str | None
    place_id: str | None

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

    @field_validator("preference")
    @classmethod
    def valid_preference(cls, v):
        if v is not None and v not in ("sun", "shade"):
            raise ValueError("preference must be 'sun' or 'shade'")
        return v


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
