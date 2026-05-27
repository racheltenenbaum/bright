import os
import requests
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator

from src.auth import get_current_user
from src.limiter import limiter, RATE_LIMIT_WEATHER
from src.models import User
from src.utils.astronomy import get_sun_position

router = APIRouter(prefix="/weather", tags=["weather"])

GOOGLE_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")


class WeatherRequest(BaseModel):
    lat: float
    lng: float

    @field_validator("lat")
    @classmethod
    def validate_lat(cls, v):
        if not -90 <= v <= 90:
            raise ValueError("lat must be between -90 and 90")
        return v

    @field_validator("lng")
    @classmethod
    def validate_lng(cls, v):
        if not -180 <= v <= 180:
            raise ValueError("lng must be between -180 and 180")
        return v


class WeatherResponse(BaseModel):
    temperature: float | None
    uv_index: int | None
    cloud_cover: int | None
    icon_url: str | None
    condition: str | None
    sun_altitude: float


@router.post("/current", response_model=WeatherResponse)
@limiter.limit(RATE_LIMIT_WEATHER)
def get_current_weather(
    request: Request,
    body: WeatherRequest,
    current_user: User = Depends(get_current_user),
):
    resp = requests.get(
        "https://weather.googleapis.com/v1/currentConditions:lookup",
        params={
            "key": GOOGLE_API_KEY,
            "location.latitude": body.lat,
            "location.longitude": body.lng,
            "unitsSystem": "METRIC",
        },
        timeout=5,
    )
    if not resp.ok:
        raise HTTPException(status_code=502, detail="Weather API error")

    sun_altitude, _ = get_sun_position(body.lat, body.lng)

    data = resp.json()
    weather_condition = data.get("weatherCondition", {})
    icon_base = weather_condition.get("iconBaseUri")
    return WeatherResponse(
        temperature=data.get("temperature", {}).get("degrees"),
        uv_index=data.get("uvIndex"),
        cloud_cover=data.get("cloudCover"),
        icon_url=f"{icon_base}.png" if icon_base else None,
        condition=weather_condition.get("description", {}).get("text"),
        sun_altitude=sun_altitude,
    )
