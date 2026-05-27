import math
from datetime import datetime, timezone


def get_sun_position(lat: float, lng: float, dt: datetime | None = None) -> tuple[float, float]:
    """Returns (sun_altitude_deg, sun_azimuth_deg from North clockwise) via local calculation."""
    if dt is None:
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    ts = dt.timestamp()
    jd = ts / 86400 + 2440587.5       # Julian Day
    n = jd - 2451545.0                # days since J2000.0

    L = (280.46 + 0.9856474 * n) % 360
    g = math.radians((357.528 + 0.9856003 * n) % 360)
    lam = math.radians(L + 1.915 * math.sin(g) + 0.02 * math.sin(2 * g))
    obliquity = math.radians(23.439)

    dec = math.asin(math.sin(obliquity) * math.sin(lam))
    ra = math.atan2(math.cos(obliquity) * math.sin(lam), math.cos(lam)) * (12 / math.pi)

    gmst = ((18.697374558 + 24.06570982441908 * n) % 24 + 24) % 24
    lha = (((gmst + lng / 15 - ra) % 24) + 24) % 24
    ha = math.radians(lha * 15)
    lat_rad = math.radians(lat)

    sin_alt = (
        math.sin(lat_rad) * math.sin(dec)
        + math.cos(lat_rad) * math.cos(dec) * math.cos(ha)
    )
    altitude = math.degrees(math.asin(max(-1.0, min(1.0, sin_alt))))

    azimuth = math.degrees(
        math.atan2(
            -math.sin(ha),
            math.tan(dec) * math.cos(lat_rad) - math.sin(lat_rad) * math.cos(ha),
        )
    ) % 360

    return altitude, azimuth
