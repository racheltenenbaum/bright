import os
import requests
from fastapi import HTTPException

ASTRONOMY_API_KEY = os.getenv("ASTRONOMY_API_KEY")
ASTRONOMY_URL = "https://api.ipgeolocation.io/v2/astronomy"


def get_sun_position(lat: float, lng: float, date_str: str, time_str: str) -> tuple[float, float]:
    """Returns (sun_altitude_deg, sun_azimuth_deg). Raises HTTPException(502) on failure."""
    resp = requests.get(
        ASTRONOMY_URL,
        params={
            "apiKey": ASTRONOMY_API_KEY,
            "lat": lat,
            "long": lng,
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

    return sun_altitude, sun_azimuth
