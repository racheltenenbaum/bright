def test_list_regions_no_auth_required(client):
    response = client.get("/regions")
    assert response.status_code == 200


def test_list_regions_returns_all_covered_regions(client):
    response = client.get("/regions")
    data = response.json()
    ids = {region["id"] for region in data["regions"]}
    assert ids == {"vienna", "nyc", "la", "telaviv"}


def test_list_regions_shape(client):
    response = client.get("/regions")
    data = response.json()
    for region in data["regions"]:
        assert set(region.keys()) == {"id", "name", "bounds"}
        assert set(region["bounds"].keys()) == {"south", "west", "north", "east"}
        assert isinstance(region["bounds"]["south"], float)


def test_list_regions_display_names(client):
    response = client.get("/regions")
    by_id = {region["id"]: region["name"] for region in response.json()["regions"]}
    assert by_id["vienna"] == "Vienna"
    assert by_id["nyc"] == "New York City"
    assert by_id["la"] == "Los Angeles"
    assert by_id["telaviv"] == "Tel Aviv"


def test_notify_me_requires_auth(client):
    response = client.post("/regions/notify", json={"lat": 48.85, "lng": 2.35})
    assert response.status_code == 401


def test_notify_me_creates_record(client, auth_headers, db, test_user):
    from unittest.mock import patch
    from src.models import RegionNotifyRequest

    with patch("src.routers.regions._send_notify_confirmation_email") as mock_send:
        response = client.post(
            "/regions/notify", json={"lat": 48.85, "lng": 2.35}, headers=auth_headers,
        )
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert db.query(RegionNotifyRequest).count() == 1
    entry = db.query(RegionNotifyRequest).first()
    assert entry.user_id == test_user.id
    assert entry.email == test_user.email
    assert entry.lat == 48.85
    assert entry.lng == 2.35
    assert entry.fulfilled is False
    assert entry.notified is False
    mock_send.assert_called_once_with(test_user.email)


def test_notify_me_saved_even_if_email_fails(client, auth_headers, db):
    from unittest.mock import patch
    from src.models import RegionNotifyRequest

    with patch("src.routers.regions._send_notify_confirmation_email", side_effect=Exception("boom")):
        response = client.post(
            "/regions/notify", json={"lat": 48.85, "lng": 2.35}, headers=auth_headers,
        )
    assert response.status_code == 200
    assert db.query(RegionNotifyRequest).count() == 1


def test_send_notify_confirmation_email_resend_configured():
    from unittest.mock import MagicMock, patch
    import src.routers.regions as regions_module

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    with patch.object(regions_module, "_RESEND_API_KEY", "re_test_key"), \
         patch("requests.post", return_value=mock_resp) as mock_post:
        regions_module._send_notify_confirmation_email("someone@example.com")
    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer re_test_key"
    assert kwargs["json"]["to"] == "someone@example.com"
    assert kwargs["json"]["from"] == regions_module._RESEND_FROM
    mock_resp.raise_for_status.assert_called_once()


def test_send_notify_confirmation_email_no_credentials_is_noop():
    from unittest.mock import patch
    import src.routers.regions as regions_module

    with patch.object(regions_module, "_RESEND_API_KEY", None), \
         patch("requests.post") as mock_post:
        regions_module._send_notify_confirmation_email("someone@example.com")
    mock_post.assert_not_called()
