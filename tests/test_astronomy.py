from datetime import datetime, timezone

from src.utils.astronomy import get_sun_position


def test_returns_two_floats():
    alt, az = get_sun_position(51.5, 0.0)
    assert isinstance(alt, float)
    assert isinstance(az, float)


def test_altitude_in_valid_range():
    alt, az = get_sun_position(51.5, 0.0)
    assert -90.0 <= alt <= 90.0


def test_azimuth_in_valid_range():
    alt, az = get_sun_position(51.5, 0.0)
    assert 0.0 <= az < 360.0


def test_sun_above_horizon_at_noon_london_summer():
    # London, solar noon on June 21 — sun should be well above horizon
    noon = datetime(2025, 6, 21, 12, 0, 0, tzinfo=timezone.utc)
    alt, _ = get_sun_position(51.5, 0.0, noon)
    assert alt > 30.0


def test_sun_below_horizon_at_midnight_london_winter():
    # London at midnight in January — definitely dark
    midnight = datetime(2025, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
    alt, _ = get_sun_position(51.5, 0.0, midnight)
    assert alt < 0.0


def test_sun_above_horizon_at_noon_equator():
    # Equator at noon UTC — sun should be very high
    noon = datetime(2025, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
    alt, _ = get_sun_position(0.0, 0.0, noon)
    assert alt > 60.0


def test_default_dt_runs_without_error():
    # Should not raise and return valid values using current UTC time
    alt, az = get_sun_position(51.5, 0.0)
    assert -90.0 <= alt <= 90.0
    assert 0.0 <= az < 360.0


def test_naive_dt_treated_as_utc():
    naive = datetime(2025, 6, 21, 12, 0, 0)
    aware = datetime(2025, 6, 21, 12, 0, 0, tzinfo=timezone.utc)
    alt_naive, az_naive = get_sun_position(51.5, 0.0, naive)
    alt_aware, az_aware = get_sun_position(51.5, 0.0, aware)
    assert abs(alt_naive - alt_aware) < 0.001
    assert abs(az_naive - az_aware) < 0.001
