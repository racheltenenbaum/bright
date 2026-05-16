import os
import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.auth import get_current_user
from src.models import User

router = APIRouter(prefix="/weather", tags=["weather"])

GOOGLE_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")


class WeatherRequest(BaseModel):
    lat: float
    lng: float


class WeatherResponse(BaseModel):
    temperature: float | None
    uv_index: int | None
    cloud_cover: int | None
    icon_url: str | None
    condition: str | None


@router.post("/current", response_model=WeatherResponse)
def get_current_weather(
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

    data = resp.json()
    weather_condition = data.get("weatherCondition", {})
    icon_base = weather_condition.get("iconBaseUri")
    return WeatherResponse(
        temperature=data.get("temperature", {}).get("degrees"),
        uv_index=data.get("uvIndex"),
        cloud_cover=data.get("cloudCover"),
        icon_url=f"{icon_base}.png" if icon_base else None,
        condition=weather_condition.get("description", {}).get("text"),
    )
