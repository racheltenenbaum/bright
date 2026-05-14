from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime

from src.auth import get_current_user
from src.models import User
from src.utils.astronomy import get_sun_position

router = APIRouter(prefix="/sun", tags=["sun"])


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
    dt = datetime.fromisoformat(body.datetime)
    date_str = dt.strftime("%Y-%m-%d")
    time_str = dt.strftime("%H:%M:%S")

    sun_altitude, sun_azimuth = get_sun_position(mid[0], mid[1], date_str, time_str)

    return SunAnalyzeResponse(
        sun_altitude=sun_altitude,
        sun_azimuth=sun_azimuth,
        date=date_str,
    )
