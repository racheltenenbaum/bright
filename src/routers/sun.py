from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import requests
import os
from datetime import datetime

from src.auth import get_current_user
from src.models import User

router = APIRouter(prefix="/sun", tags=["sun"])

ASTRONOMY_API_KEY = os.getenv("ASTRONOMY_API_KEY")
ASTRONOMY_URL = "https://api.ipgeolocation.io/v2/astronomy"


class SunAnalyzeRequest(BaseModel):
    coordinates: list[list[float]]  # [[lat, lng], ...]
    datetime: str                   # ISO string e.g. "2026-05-14T15:30:00"


class SunAnalyzeResponse(BaseModel):
    sun_altitude: float
    sun_azimuth: float
    date: str


@router.post("/analyze", response_model=SunAnalyzeResponse)
def analyze_sun(
    body: SunAnalyzeRequest,
    current_user: User = Depends(get_current_user),
):
    if len(body.coordinates) < 2:
        raise HTTPException(status_code=400, detail="At least 2 coordinates required")

    mid = body.coordinates[len(body.coordinates) // 2]
    mid_lat, mid_lng = mid

    dt = datetime.fromisoformat(body.datetime)
    date_str = dt.strftime("%Y-%m-%d")
    time_str = dt.strftime("%H:%M:%S")

    resp = requests.get(
        ASTRONOMY_URL,
        params={
            "apiKey": ASTRONOMY_API_KEY,
            "lat": mid_lat,
            "long": mid_lng,
            "date": date_str,
            "time": time_str,
        },
        timeout=10,
    )

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Astronomy API request failed")

    data = resp.json()
    astronomy = data.get("astronomy", data)

    try:
        sun_altitude = float(astronomy["sun_altitude"])
        sun_azimuth = float(astronomy["sun_azimuth"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=502, detail="Unexpected response from astronomy API")

    return SunAnalyzeResponse(
        sun_altitude=sun_altitude,
        sun_azimuth=sun_azimuth,
        date=date_str,
    )
