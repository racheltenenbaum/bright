from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import src.routers.places as places_module
from src.routers.places import _road_sqlite_get, _road_sqlite_set
from src.shadow import (
    extract_roads_from_overpass,
    find_nearest_road_segment,
    _side_of_segment,
    _point_to_segment_dist_sq,
    place_is_sunny,
)

LAT, LNG = 51.5, -0.1
SUN_UP = (45.0, 180.0)
SUN_DOWN = (-5.0, 180.0)
BUILDINGS = []

OVERPASS_ROAD_RESPONSE = {
    "elements": [
        {"type": "node", "id": 1, "lat": 51.499, "lon": -0.101},
        {"type": "node", "id": 2, "lat": 51.501, "lon": -0.101},
        {"type": "way", "id": 10, "nodes": [1, 2], "tags": {"highway": "residential"}},
    ]
}

GOOGLE_PLACE = {
    "place_id": "abc123",
    "name": "Sunny Cafe",
    "geometry": {"location": {"lat": 51.5, "lng": -0.1}},
    "rating": 4.5,
    "user_ratings_total": 15,
    "vicinity": "10 Sun Street",
    "photos": [{"photo_reference": "ref_abc123"}],
}

GOOGLE_PLACE_2 = {
    "place_id": "def456",
    "name": "Shady Bar",
    "geometry": {"location": {"lat": 51.501, "lng": -0.102}},
    "rating": 3.8,
    "user_ratings_total": 20,
    "vicinity": "5 Dark Lane",
}


# ── Unit tests: extract_roads_from_overpass ────────────────────────────────────

def test_extract_roads_parses_way():
    roads = extract_roads_from_overpass(OVERPASS_ROAD_RESPONSE)
    assert len(roads) == 1
    seg = roads[0]
    assert seg["lat1"] == 51.499
    assert seg["lng1"] == -0.101
    assert seg["lat2"] == 51.501
    assert seg["lng2"] == -0.101


def test_extract_roads_no_highway_tag():
    data = {
        "elements": [
            {"type": "node", "id": 1, "lat": 51.0, "lon": 0.0},
            {"type": "node", "id": 2, "lat": 51.001, "lon": 0.0},
            {"type": "way", "id": 1, "nodes": [1, 2], "tags": {}},
        ]
    }
    assert extract_roads_from_overpass(data) == []


def test_extract_roads_missing_nodes_skipped():
    data = {
        "elements": [
            {"type": "node", "id": 1, "lat": 51.0, "lon": 0.0},
            # node 2 is missing
            {"type": "way", "id": 1, "nodes": [1, 2], "tags": {"highway": "residential"}},
        ]
    }
    # only one node → can't form a segment
    assert extract_roads_from_overpass(data) == []


def test_extract_roads_multiple_nodes_forms_multiple_segments():
    data = {
        "elements": [
            {"type": "node", "id": 1, "lat": 51.0, "lon": 0.0},
            {"type": "node", "id": 2, "lat": 51.001, "lon": 0.0},
            {"type": "node", "id": 3, "lat": 51.002, "lon": 0.0},
            {"type": "way", "id": 1, "nodes": [1, 2, 3], "tags": {"highway": "primary"}},
        ]
    }
    roads = extract_roads_from_overpass(data)
    assert len(roads) == 2


def test_extract_roads_empty_elements():
    assert extract_roads_from_overpass({"elements": []}) == []


# ── Unit tests: find_nearest_road_segment ─────────────────────────────────────

def test_find_nearest_road_segment_returns_closest():
    segments = [
        {"lat1": 51.49, "lng1": -0.10, "lat2": 51.51, "lng2": -0.10},  # close: same lng
        {"lat1": 55.0, "lng1": 0.0, "lat2": 55.01, "lng2": 0.0},       # far
    ]
    nearest = find_nearest_road_segment(51.5, -0.10, segments)
    assert nearest["lat1"] == 51.49


def test_find_nearest_road_segment_empty_returns_none():
    assert find_nearest_road_segment(51.5, -0.1, []) is None


def test_find_nearest_road_segment_single_segment():
    seg = {"lat1": 51.499, "lng1": -0.101, "lat2": 51.501, "lng2": -0.101}
    assert find_nearest_road_segment(51.5, -0.1005, [seg]) == seg


# ── Unit tests: _side_of_segment ──────────────────────────────────────────────

def test_side_of_segment_left_of_northbound_road():
    # Road goes south→north along lng=-0.10; point is west → left when facing north
    side = _side_of_segment(51.5, -0.11, 51.49, -0.10, 51.51, -0.10)
    assert side == "left"


def test_side_of_segment_right_of_northbound_road():
    # Point is east → right when facing north
    side = _side_of_segment(51.5, -0.09, 51.49, -0.10, 51.51, -0.10)
    assert side == "right"


def test_side_of_segment_left_of_eastbound_road():
    # Road goes west→east along lat=51.5; point is north → left when facing east
    side = _side_of_segment(51.51, -0.10, 51.5, -0.11, 51.5, -0.09)
    assert side == "left"


def test_side_of_segment_right_of_eastbound_road():
    # Point is south → right when facing east
    side = _side_of_segment(51.49, -0.10, 51.5, -0.11, 51.5, -0.09)
    assert side == "right"


# ── Unit tests: place_is_sunny ─────────────────────────────────────────────────

def test_place_is_sunny_sun_below_horizon():
    assert place_is_sunny(51.5, -0.1, [], BUILDINGS, -5.0, 180.0) is False


def test_place_is_sunny_no_roads_no_buildings_is_sunny():
    # No roads → fallback to is_point_shaded; no buildings + sun up → sunny
    assert place_is_sunny(51.5, -0.1, [], BUILDINGS, 45.0, 180.0) is True


def test_place_is_sunny_on_sunny_side():
    segments = [{"lat1": 51.49, "lng1": -0.10, "lat2": 51.51, "lng2": -0.10}]
    with patch("src.shadow.which_side_sunny", return_value="right"):
        # point is east (right) of north-facing road → sunny
        result = place_is_sunny(51.5, -0.09, segments, BUILDINGS, 45.0, 180.0)
    assert result is True


def test_place_is_sunny_on_shaded_side():
    segments = [{"lat1": 51.49, "lng1": -0.10, "lat2": 51.51, "lng2": -0.10}]
    with patch("src.shadow.which_side_sunny", return_value="right"):
        # point is west (left) of north-facing road → shaded
        result = place_is_sunny(51.5, -0.11, segments, BUILDINGS, 45.0, 180.0)
    assert result is False


def test_place_is_sunny_both_sides():
    segments = [{"lat1": 51.49, "lng1": -0.10, "lat2": 51.51, "lng2": -0.10}]
    with patch("src.shadow.which_side_sunny", return_value="both"):
        result = place_is_sunny(51.5, -0.09, segments, BUILDINGS, 45.0, 180.0)
    assert result is True


def test_place_is_sunny_neither_side():
    segments = [{"lat1": 51.49, "lng1": -0.10, "lat2": 51.51, "lng2": -0.10}]
    with patch("src.shadow.which_side_sunny", return_value="neither"):
        result = place_is_sunny(51.5, -0.09, segments, BUILDINGS, 45.0, 180.0)
    assert result is False


# ── Unit tests: _fetch_roads_for_bbox ─────────────────────────────────────────

def test_fetch_roads_memory_cache_hit():
    key = places_module._bbox_key(52.0, -0.2, 52.1, 0.0)
    places_module._road_cache[key] = [{"lat1": 1.0, "lng1": 0.0, "lat2": 2.0, "lng2": 0.0}]
    try:
        result = places_module._fetch_roads_for_bbox(52.0, -0.2, 52.1, 0.0)
        assert result == [{"lat1": 1.0, "lng1": 0.0, "lat2": 2.0, "lng2": 0.0}]
    finally:
        places_module._road_cache.pop(key, None)


def test_fetch_roads_sqlite_cache_hit():
    key = places_module._bbox_key(53.0, -0.2, 53.1, 0.0)
    places_module._road_cache.pop(key, None)
    roads = [{"lat1": 53.0, "lng1": -0.2, "lat2": 53.1, "lng2": -0.2}]
    with patch("src.routers.places._road_sqlite_get", return_value=roads):
        result = places_module._fetch_roads_for_bbox(53.0, -0.2, 53.1, 0.0)
    assert result == roads
    places_module._road_cache.pop(key, None)


def test_fetch_roads_api_call():
    key = places_module._bbox_key(54.0, -0.2, 54.1, 0.0)
    places_module._road_cache.pop(key, None)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = OVERPASS_ROAD_RESPONSE
    with patch("src.routers.places._road_sqlite_get", return_value=None):
        with patch("src.routers.places.requests.post", return_value=mock_resp):
            result = places_module._fetch_roads_for_bbox(54.0, -0.2, 54.1, 0.0)
    assert len(result) == 1
    places_module._road_cache.pop(key, None)


def test_fetch_roads_api_exception_returns_empty():
    key = places_module._bbox_key(55.0, -0.2, 55.1, 0.0)
    places_module._road_cache.pop(key, None)
    with patch("src.routers.places._road_sqlite_get", return_value=None):
        with patch("src.routers.places.requests.post", side_effect=Exception("network")):
            result = places_module._fetch_roads_for_bbox(55.0, -0.2, 55.1, 0.0)
    assert result == []


# ── Unit tests: _fetch_places_from_google ─────────────────────────────────────

def test_fetch_places_passes_keyword_to_google():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"results": [GOOGLE_PLACE]}
    with patch("src.routers.places.requests.get", return_value=mock_resp) as mock_get:
        places_module._fetch_places_from_google(LAT, LNG, 500, "cafe", "pret")
    assert mock_get.call_args[1]["params"]["keyword"] == "pret"


def test_fetch_places_no_keyword_omits_param():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"results": [GOOGLE_PLACE]}
    with patch("src.routers.places.requests.get", return_value=mock_resp) as mock_get:
        places_module._fetch_places_from_google(LAT, LNG, 500, "cafe", None)
    assert "keyword" not in mock_get.call_args[1]["params"]


def test_keyword_search_returns_all_results_regardless_of_sun_shade(client, auth_headers):
    """When keyword is set, both sunny and shaded places are returned (no preference filter)."""
    with patch("src.routers.places.get_sun_position", return_value=SUN_UP), \
         patch("src.routers.places._fetch_places_from_google", return_value=[GOOGLE_PLACE, GOOGLE_PLACE_2]), \
         patch("src.routers.places._fetch_buildings_for_bbox", return_value=[]), \
         patch("src.routers.places.is_point_shaded", side_effect=[False, True]):
        response = client.post("/places/search", json={
            "lat": LAT, "lng": LNG, "radius": 500,
            "preference": "sun", "types": ["cafe"], "keyword": "pret"
        }, headers=auth_headers)
    assert response.status_code == 200
    places = response.json()["places"]
    assert len(places) == 2
    assert places[0]["is_sunny"] is True
    assert places[1]["is_sunny"] is False


def test_no_keyword_still_filters_by_preference(client, auth_headers):
    """Without keyword, the original preference filter applies."""
    with patch("src.routers.places.get_sun_position", return_value=SUN_UP), \
         patch("src.routers.places._fetch_places_from_google", return_value=[GOOGLE_PLACE, GOOGLE_PLACE_2]), \
         patch("src.routers.places._fetch_buildings_for_bbox", return_value=[]), \
         patch("src.routers.places.is_point_shaded", side_effect=[False, True]):
        response = client.post("/places/search", json={
            "lat": LAT, "lng": LNG, "radius": 500, "preference": "sun", "types": ["cafe"]
        }, headers=auth_headers)
    assert response.status_code == 200
    places = response.json()["places"]
    assert len(places) == 1
    assert places[0]["is_sunny"] is True


def test_fetch_places_from_google_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"results": [GOOGLE_PLACE]}
    with patch("src.routers.places.requests.get", return_value=mock_resp):
        results = places_module._fetch_places_from_google(LAT, LNG, 500, "cafe")
    assert len(results) == 1
    assert results[0]["place_id"] == "abc123"


def test_fetch_places_from_google_api_failure_returns_empty():
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    with patch("src.routers.places.requests.get", return_value=mock_resp):
        results = places_module._fetch_places_from_google(LAT, LNG, 500, "cafe")
    assert results == []


def test_fetch_places_from_google_exception_returns_empty():
    with patch("src.routers.places.requests.get", side_effect=Exception("network")):
        results = places_module._fetch_places_from_google(LAT, LNG, 500, "cafe")
    assert results == []


def test_fetch_places_no_api_key_returns_empty():
    with patch("src.routers.places.GOOGLE_MAPS_API_KEY", None):
        results = places_module._fetch_places_from_google(LAT, LNG, 500, "cafe")
    assert results == []


def test_fetch_places_excludes_gas_stations():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"results": [
        {**GOOGLE_PLACE, "types": ["cafe", "food", "establishment"]},
        {"place_id": "gas123", "name": "BP Forecourt Cafe",
         "geometry": {"location": {"lat": 51.5, "lng": -0.1}},
         "vicinity": "Gas Station Road",
         "types": ["gas_station", "cafe", "establishment"]},
    ]}
    with patch("src.routers.places.requests.get", return_value=mock_resp):
        results = places_module._fetch_places_from_google(LAT, LNG, 500, "cafe")
    assert len(results) == 1
    assert results[0]["place_id"] == GOOGLE_PLACE["place_id"]


def test_fetch_places_excludes_convenience_stores():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"results": [
        {"place_id": "cvs123", "name": "CVS with Coffee",
         "geometry": {"location": {"lat": 51.5, "lng": -0.1}},
         "vicinity": "High Street",
         "types": ["convenience_store", "cafe", "establishment"]},
    ]}
    with patch("src.routers.places.requests.get", return_value=mock_resp):
        results = places_module._fetch_places_from_google(LAT, LNG, 500, "cafe")
    assert results == []


# ── /places/search endpoint ────────────────────────────────────────────────────

def test_search_places_unauthenticated(client):
    response = client.post("/places/search", json={
        "lat": LAT, "lng": LNG, "radius": 500, "preference": "sun", "types": ["cafe"]
    })
    assert response.status_code == 401


def test_search_places_invalid_preference(client, auth_headers):
    response = client.post("/places/search", json={
        "lat": LAT, "lng": LNG, "radius": 500, "preference": "fog", "types": ["cafe"]
    }, headers=auth_headers)
    assert response.status_code == 422


def test_search_places_invalid_type(client, auth_headers):
    response = client.post("/places/search", json={
        "lat": LAT, "lng": LNG, "radius": 500, "preference": "sun", "types": ["disco"]
    }, headers=auth_headers)
    assert response.status_code == 422


def test_search_places_empty_types(client, auth_headers):
    response = client.post("/places/search", json={
        "lat": LAT, "lng": LNG, "radius": 500, "preference": "sun", "types": []
    }, headers=auth_headers)
    assert response.status_code == 422


def test_search_places_sun_below_horizon(client, auth_headers):
    mock_buildings = MagicMock()
    with patch("src.routers.places.get_sun_position", return_value=SUN_DOWN), \
         patch("src.routers.places._fetch_places_from_google", return_value=[GOOGLE_PLACE]), \
         patch("src.routers.places._fetch_buildings_for_bbox", mock_buildings):
        response = client.post("/places/search", json={
            "lat": LAT, "lng": LNG, "radius": 500, "preference": "sun", "types": ["cafe"]
        }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["sun_altitude"] < 0
    # All places returned unfiltered at night (no sun to filter by), all marked is_sunny=False
    assert len(data["places"]) == 1
    assert all(not p["is_sunny"] for p in data["places"])
    # Overpass should not be called when sun is below horizon
    mock_buildings.assert_not_called()


def test_search_places_no_buildings_no_roads_sunny(client, auth_headers):
    with patch("src.routers.places.get_sun_position", return_value=SUN_UP), \
         patch("src.routers.places._fetch_places_from_google", return_value=[GOOGLE_PLACE]), \
         patch("src.routers.places._fetch_buildings_for_bbox", return_value=[]):
        response = client.post("/places/search", json={
            "lat": LAT, "lng": LNG, "radius": 500, "preference": "sun", "types": ["cafe"]
        }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["sun_altitude"] == 45.0
    assert len(data["places"]) == 1
    assert data["places"][0]["name"] == "Sunny Cafe"
    assert data["places"][0]["is_sunny"] is True


def test_search_places_deduplicates_by_place_id(client, auth_headers):
    # Same place returned for both types — should appear only once
    with patch("src.routers.places.get_sun_position", return_value=SUN_UP), \
         patch("src.routers.places._fetch_places_from_google", return_value=[GOOGLE_PLACE]), \
         patch("src.routers.places._fetch_buildings_for_bbox", return_value=[]):
        response = client.post("/places/search", json={
            "lat": LAT, "lng": LNG, "radius": 500,
            "preference": "sun", "types": ["cafe", "restaurant"]
        }, headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()["places"]) == 1


def test_search_places_multiple_places_returned(client, auth_headers):
    with patch("src.routers.places.get_sun_position", return_value=SUN_UP), \
         patch("src.routers.places._fetch_places_from_google", return_value=[GOOGLE_PLACE, GOOGLE_PLACE_2]), \
         patch("src.routers.places._fetch_buildings_for_bbox", return_value=[]):
        response = client.post("/places/search", json={
            "lat": LAT, "lng": LNG, "radius": 500, "preference": "sun", "types": ["cafe"]
        }, headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()["places"]) == 2


def test_search_places_no_api_key_returns_empty(client, auth_headers):
    with patch("src.routers.places.get_sun_position", return_value=SUN_UP), \
         patch("src.routers.places.GOOGLE_MAPS_API_KEY", None), \
         patch("src.routers.places._fetch_buildings_for_bbox", return_value=[]):
        response = client.post("/places/search", json={
            "lat": LAT, "lng": LNG, "radius": 500, "preference": "sun", "types": ["cafe"]
        }, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["places"] == []


def test_search_places_result_has_expected_fields(client, auth_headers):
    with patch("src.routers.places.get_sun_position", return_value=SUN_UP), \
         patch("src.routers.places._fetch_places_from_google", return_value=[GOOGLE_PLACE]), \
         patch("src.routers.places._fetch_buildings_for_bbox", return_value=[]):
        response = client.post("/places/search", json={
            "lat": LAT, "lng": LNG, "radius": 500, "preference": "sun", "types": ["cafe"]
        }, headers=auth_headers)
    place = response.json()["places"][0]
    assert "place_id" in place
    assert "name" in place
    assert "lat" in place
    assert "lng" in place
    assert "address" in place
    assert "rating" in place
    assert "photo_reference" in place
    assert "type" in place
    assert "is_sunny" in place


def test_search_places_photo_reference_passed_through(client, auth_headers):
    with patch("src.routers.places.get_sun_position", return_value=SUN_UP), \
         patch("src.routers.places._fetch_places_from_google", return_value=[GOOGLE_PLACE]), \
         patch("src.routers.places._fetch_buildings_for_bbox", return_value=[]):
        response = client.post("/places/search", json={
            "lat": LAT, "lng": LNG, "radius": 500, "preference": "sun", "types": ["cafe"]
        }, headers=auth_headers)
    assert response.json()["places"][0]["photo_reference"] == "ref_abc123"


def test_search_places_photo_reference_none_when_absent(client, auth_headers):
    place_no_photo = {k: v for k, v in GOOGLE_PLACE.items() if k != "photos"}
    with patch("src.routers.places.get_sun_position", return_value=SUN_UP), \
         patch("src.routers.places._fetch_places_from_google", return_value=[place_no_photo]), \
         patch("src.routers.places._fetch_buildings_for_bbox", return_value=[]):
        response = client.post("/places/search", json={
            "lat": LAT, "lng": LNG, "radius": 500, "preference": "sun", "types": ["cafe"]
        }, headers=auth_headers)
    assert response.json()["places"][0]["photo_reference"] is None


def test_search_places_place_without_rating(client, auth_headers):
    place_no_rating = {**GOOGLE_PLACE, "place_id": "xyz999"}
    place_no_rating.pop("rating", None)
    with patch("src.routers.places.get_sun_position", return_value=SUN_UP), \
         patch("src.routers.places._fetch_places_from_google", return_value=[place_no_rating]), \
         patch("src.routers.places._fetch_buildings_for_bbox", return_value=[]):
        response = client.post("/places/search", json={
            "lat": LAT, "lng": LNG, "radius": 500, "preference": "sun", "types": ["cafe"]
        }, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["places"][0]["rating"] is None


def test_search_places_preference_sun_excludes_shaded(client, auth_headers):
    with patch("src.routers.places.get_sun_position", return_value=SUN_UP), \
         patch("src.routers.places._fetch_places_from_google", return_value=[GOOGLE_PLACE, GOOGLE_PLACE_2]), \
         patch("src.routers.places._fetch_buildings_for_bbox", return_value=[]), \
         patch("src.routers.places.is_point_shaded", return_value=True):
        response = client.post("/places/search", json={
            "lat": LAT, "lng": LNG, "radius": 500, "preference": "sun", "types": ["cafe"]
        }, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["places"] == []


def test_search_places_preference_shade_excludes_sunny(client, auth_headers):
    with patch("src.routers.places.get_sun_position", return_value=SUN_UP), \
         patch("src.routers.places._fetch_places_from_google", return_value=[GOOGLE_PLACE]), \
         patch("src.routers.places._fetch_buildings_for_bbox", return_value=[]), \
         patch("src.routers.places.is_point_shaded", return_value=False):
        response = client.post("/places/search", json={
            "lat": LAT, "lng": LNG, "radius": 500, "preference": "shade", "types": ["cafe"]
        }, headers=auth_headers)
    assert response.status_code == 200
    # place is not shaded (is_sunny=True) but preference is shade → excluded
    assert response.json()["places"] == []


def test_search_places_sunny_when_not_shaded(client, auth_headers):
    with patch("src.routers.places.get_sun_position", return_value=SUN_UP), \
         patch("src.routers.places._fetch_places_from_google", return_value=[GOOGLE_PLACE]), \
         patch("src.routers.places._fetch_buildings_for_bbox", return_value=[]), \
         patch("src.routers.places.is_point_shaded", return_value=False):
        response = client.post("/places/search", json={
            "lat": LAT, "lng": LNG, "radius": 500, "preference": "sun", "types": ["cafe"]
        }, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["places"][0]["is_sunny"] is True


CAFE_LATE = {
    "place_id": "cafe_late_01",
    "name": "Evening Cafe",
    "geometry": {"location": {"lat": 51.5, "lng": -0.1}},
    "rating": 4.3,
    "user_ratings_total": 120,
    "vicinity": "5 Night Street",
}


def _make_fetch(by_type: dict):
    """Return a side_effect callable that dispatches on place_type."""
    def _fetch(lat, lng, radius, place_type, keyword=None):
        return by_type.get(place_type, [])
    return _fetch


# ── Café-to-bar evening logic ─────────────────────────────────────────────────

def _mock_utc_hour(hour):
    """Return a MagicMock for datetime.now(timezone.utc) returning the given UTC hour (lng=0)."""
    m = MagicMock()
    m.now.return_value = datetime(2025, 6, 1, hour, 0, 0, tzinfo=timezone.utc)
    return m


def test_cafe_included_as_bar_at_or_after_20h(client, auth_headers):
    # LNG=0 so local_hour == UTC hour; 20 UTC → evening == True
    with patch("src.routers.places.datetime", _mock_utc_hour(20)), \
         patch("src.routers.places.get_sun_position", return_value=SUN_UP), \
         patch("src.routers.places._fetch_places_from_google", side_effect=_make_fetch({"cafe": [CAFE_LATE]})), \
         patch("src.routers.places._fetch_buildings_for_bbox", return_value=[]):
        response = client.post("/places/search", json={
            "lat": LAT, "lng": 0.0, "radius": 500, "preference": "sun", "types": ["bar"]
        }, headers=auth_headers)
    assert response.status_code == 200
    places = response.json()["places"]
    assert len(places) == 1
    assert places[0]["place_id"] == "cafe_late_01"
    assert places[0]["type"] == "bar"


def test_cafe_not_included_as_bar_before_20h(client, auth_headers):
    # 19 UTC at lng=0 → local_hour=19 → not evening
    with patch("src.routers.places.datetime", _mock_utc_hour(19)), \
         patch("src.routers.places.get_sun_position", return_value=SUN_UP), \
         patch("src.routers.places._fetch_places_from_google", side_effect=_make_fetch({"cafe": [CAFE_LATE]})), \
         patch("src.routers.places._fetch_buildings_for_bbox", return_value=[]):
        response = client.post("/places/search", json={
            "lat": LAT, "lng": 0.0, "radius": 500, "preference": "sun", "types": ["bar"]
        }, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["places"] == []


def test_cafe_already_in_types_not_double_counted(client, auth_headers):
    """When both cafe and bar are requested, the cafe is not counted twice."""
    with patch("src.routers.places.datetime", _mock_utc_hour(21)), \
         patch("src.routers.places.get_sun_position", return_value=SUN_UP), \
         patch("src.routers.places._fetch_places_from_google", side_effect=_make_fetch({"cafe": [CAFE_LATE], "bar": []})), \
         patch("src.routers.places._fetch_buildings_for_bbox", return_value=[]):
        response = client.post("/places/search", json={
            "lat": LAT, "lng": 0.0, "radius": 500, "preference": "sun", "types": ["cafe", "bar"]
        }, headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()["places"]) == 1


# ── Review-count filter ───────────────────────────────────────────────────────

PLACE_FEW_REVIEWS = {
    "place_id": "few_reviews_01",
    "name": "Tiny Cafe",
    "geometry": {"location": {"lat": 51.5, "lng": -0.1}},
    "rating": 4.8,
    "user_ratings_total": 9,
    "vicinity": "1 Quiet Lane",
}

PARK_FEW_REVIEWS = {
    "place_id": "park_few_01",
    "name": "Small Park",
    "geometry": {"location": {"lat": 51.5, "lng": -0.1}},
    "rating": 4.0,
    "user_ratings_total": 3,
    "vicinity": "Green St",
}


def test_venue_with_fewer_than_10_reviews_hidden(client, auth_headers):
    with patch("src.routers.places.get_sun_position", return_value=SUN_UP), \
         patch("src.routers.places._fetch_places_from_google", return_value=[PLACE_FEW_REVIEWS]), \
         patch("src.routers.places._fetch_buildings_for_bbox", return_value=[]):
        response = client.post("/places/search", json={
            "lat": LAT, "lng": LNG, "radius": 500, "preference": "sun", "types": ["cafe"]
        }, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["places"] == []


def test_venue_with_exactly_10_reviews_hidden(client, auth_headers):
    place_10 = {**PLACE_FEW_REVIEWS, "user_ratings_total": 10}
    with patch("src.routers.places.get_sun_position", return_value=SUN_UP), \
         patch("src.routers.places._fetch_places_from_google", return_value=[place_10]), \
         patch("src.routers.places._fetch_buildings_for_bbox", return_value=[]):
        response = client.post("/places/search", json={
            "lat": LAT, "lng": LNG, "radius": 500, "preference": "sun", "types": ["cafe"]
        }, headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()["places"]) == 0


def test_park_with_fewer_than_10_reviews_shown(client, auth_headers):
    with patch("src.routers.places.get_sun_position", return_value=SUN_UP), \
         patch("src.routers.places._fetch_places_from_google", return_value=[PARK_FEW_REVIEWS]), \
         patch("src.routers.places._fetch_buildings_for_bbox", return_value=[]):
        response = client.post("/places/search", json={
            "lat": LAT, "lng": LNG, "radius": 500, "preference": "sun", "types": ["park"]
        }, headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()["places"]) == 1


def test_venue_missing_ratings_total_hidden(client, auth_headers):
    """Places with no user_ratings_total field are filtered out (treated as 0 reviews)."""
    place_no_count = {k: v for k, v in GOOGLE_PLACE.items() if k != "user_ratings_total"}
    with patch("src.routers.places.get_sun_position", return_value=SUN_UP), \
         patch("src.routers.places._fetch_places_from_google", return_value=[place_no_count]), \
         patch("src.routers.places._fetch_buildings_for_bbox", return_value=[]):
        response = client.post("/places/search", json={
            "lat": LAT, "lng": LNG, "radius": 500, "preference": "sun", "types": ["cafe"]
        }, headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()["places"]) == 0


# ── Unit tests: _road_sqlite_get / _road_sqlite_set ───────────────────────────

def test_road_sqlite_get_miss():
    assert _road_sqlite_get("key_that_does_not_exist_road_xyz") is None


def test_road_sqlite_get_exception():
    with patch("sqlite3.connect", side_effect=Exception("fail")):
        assert _road_sqlite_get("any") is None


def test_road_sqlite_set_exception():
    with patch("sqlite3.connect", side_effect=Exception("fail")):
        _road_sqlite_set("any", [])  # must not raise


def test_road_sqlite_set_then_get():
    key = "test_road_set_get_key"
    roads = [{"lat1": 51.0, "lng1": 0.0, "lat2": 51.001, "lng2": 0.0}]
    _road_sqlite_set(key, roads)
    assert _road_sqlite_get(key) == roads



# ── Unit tests: _point_to_segment_dist_sq degenerate case ─────────────────────

def test_point_to_segment_dist_sq_degenerate_segment():
    # Both endpoints at the same location → distance is to that single point
    dist_sq = _point_to_segment_dist_sq(51.5, -0.1, 51.5, -0.1, 51.5, -0.1)
    assert dist_sq == 0.0


# ── /places/{place_id}/details endpoint ───────────────────────────────────────

PLACE_DETAILS_RESPONSE = {
    "result": {
        "name": "Sunny Cafe",
        "rating": 4.5,
        "user_ratings_total": 234,
        "price_level": 2,
        "formatted_phone_number": "+44 20 7946 0958",
        "website": "https://sunnycafe.co.uk",
        "address_components": [
            {"short_name": "GB", "types": ["country", "political"]},
            {"short_name": "W1A 1AA", "types": ["postal_code"]},
        ],
        "opening_hours": {
            "open_now": True,
            "weekday_text": [
                "Monday: 8:00 AM – 6:00 PM",
                "Tuesday: 8:00 AM – 6:00 PM",
                "Wednesday: 8:00 AM – 6:00 PM",
                "Thursday: 8:00 AM – 6:00 PM",
                "Friday: 8:00 AM – 7:00 PM",
                "Saturday: 9:00 AM – 5:00 PM",
                "Sunday: 10:00 AM – 4:00 PM",
            ],
        },
        "photos": [
            {"photo_reference": "ref1"},
            {"photo_reference": "ref2"},
            {"photo_reference": "ref3"},
        ],
        "reviews": [
            {
                "author_name": "Alice B.",
                "rating": 5,
                "text": "Best coffee in town!",
                "relative_time_description": "2 weeks ago",
            },
            {
                "author_name": "Bob C.",
                "rating": 4,
                "text": "Great spot for a sunny afternoon.",
                "relative_time_description": "last month",
            },
        ],
    }
}


def test_place_details_success(client, auth_headers):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = PLACE_DETAILS_RESPONSE
    with patch("src.routers.places.requests.get", return_value=mock_resp):
        response = client.get("/places/abc123/details", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Sunny Cafe"
    assert data["rating"] == 4.5
    assert data["user_ratings_total"] == 234
    assert data["price_level"] == 2
    assert data["formatted_phone_number"] == "+44 20 7946 0958"
    assert data["website"] == "https://sunnycafe.co.uk"
    assert data["open_now"] is True
    assert len(data["weekday_text"]) == 7
    assert data["photo_references"] == ["ref1", "ref2", "ref3"]
    assert data["currency_symbol"] == "£"
    assert data["postal_code"] == "W1A 1AA"
    assert len(data["reviews"]) == 2
    assert data["reviews"][0]["author_name"] == "Alice B."
    assert data["reviews"][0]["rating"] == 5
    assert data["reviews"][0]["text"] == "Best coffee in town!"
    assert data["reviews"][0]["relative_time"] == "2 weeks ago"


def test_place_details_unauthenticated(client):
    response = client.get("/places/abc123/details")
    assert response.status_code == 401


def test_place_details_no_api_key(client, auth_headers):
    with patch("src.routers.places.GOOGLE_MAPS_API_KEY", None):
        response = client.get("/places/abc123/details", headers=auth_headers)
    assert response.status_code == 503


def test_place_details_api_non_200(client, auth_headers):
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    with patch("src.routers.places.requests.get", return_value=mock_resp):
        response = client.get("/places/abc123/details", headers=auth_headers)
    assert response.status_code == 502


def test_place_details_api_exception(client, auth_headers):
    with patch("src.routers.places.requests.get", side_effect=Exception("network")):
        response = client.get("/places/abc123/details", headers=auth_headers)
    assert response.status_code == 502


def test_place_details_limits_photos_to_five(client, auth_headers):
    many_photos = {"result": {**PLACE_DETAILS_RESPONSE["result"],
                               "photos": [{"photo_reference": f"ref{i}"} for i in range(10)]}}
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = many_photos
    with patch("src.routers.places.requests.get", return_value=mock_resp):
        response = client.get("/places/abc123/details", headers=auth_headers)
    assert len(response.json()["photo_references"]) == 5


def test_place_details_limits_reviews_to_five(client, auth_headers):
    many_reviews = {"result": {**PLACE_DETAILS_RESPONSE["result"],
                                "reviews": [{"author_name": f"User{i}", "rating": 4,
                                              "text": "Good", "relative_time_description": "1 week ago"}
                                             for i in range(8)]}}
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = many_reviews
    with patch("src.routers.places.requests.get", return_value=mock_resp):
        response = client.get("/places/abc123/details", headers=auth_headers)
    assert len(response.json()["reviews"]) == 5


def test_place_details_missing_optional_fields(client, auth_headers):
    minimal = {"result": {"name": "Bare Cafe"}}
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = minimal
    with patch("src.routers.places.requests.get", return_value=mock_resp):
        response = client.get("/places/abc123/details", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Bare Cafe"
    assert data["rating"] is None
    assert data["formatted_phone_number"] is None
    assert data["website"] is None
    assert data["open_now"] is None
    assert data["photo_references"] == []
    assert data["reviews"] == []
    assert data["currency_symbol"] == "$"


def test_place_details_unknown_country_defaults_currency(client, auth_headers):
    response_data = {"result": {**PLACE_DETAILS_RESPONSE["result"],
                                 "address_components": [{"short_name": "XX", "types": ["country", "political"]}]}}
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = response_data
    with patch("src.routers.places.requests.get", return_value=mock_resp):
        response = client.get("/places/abc123/details", headers=auth_headers)
    assert response.json()["currency_symbol"] == "$"


# ── sun-check endpoint ─────────────────────────────────────────────────────────

def test_sun_check_returns_sunny(client, auth_headers):
    with patch("src.routers.places.get_sun_position", return_value=(45.0, 180.0)), \
         patch("src.routers.places._fetch_buildings_for_bbox", return_value=[]), \
         patch("src.routers.places.place_is_sunny", return_value=True):
        response = client.post("/places/sun-check", json={"lat": 51.5, "lng": -0.1}, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["is_sunny"] is True
    assert data["sun_altitude"] == 45.0


def test_sun_check_returns_shaded(client, auth_headers):
    with patch("src.routers.places.get_sun_position", return_value=(30.0, 90.0)), \
         patch("src.routers.places._fetch_buildings_for_bbox", return_value=[]), \
         patch("src.routers.places.place_is_sunny", return_value=False):
        response = client.post("/places/sun-check", json={"lat": 51.5, "lng": -0.1}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["is_sunny"] is False


def test_sun_check_nighttime_skips_buildings(client, auth_headers):
    with patch("src.routers.places.get_sun_position", return_value=(-5.0, 180.0)) as mock_sun, \
         patch("src.routers.places._fetch_buildings_for_bbox") as mock_buildings:
        response = client.post("/places/sun-check", json={"lat": 51.5, "lng": -0.1}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["is_sunny"] is False
    mock_buildings.assert_not_called()


def test_sun_check_unauthenticated(client):
    response = client.post("/places/sun-check", json={"lat": 51.5, "lng": -0.1})
    assert response.status_code == 401
