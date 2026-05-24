import pytest
from src.models import Spot

SPOT_PAYLOAD = {
    "name": "Home",
    "address": "123 Main St",
    "lat": 51.5,
    "lng": -0.1,
    "icon": "faHouse",
    "city": "London",
}


def test_create_spot_with_description(client, auth_headers):
    payload = {**SPOT_PAYLOAD, "description": "Great coffee, go on weekday mornings"}
    response = client.post("/spots", json=payload, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["description"] == "Great coffee, go on weekday mornings"


def test_create_spot_description_optional(client, auth_headers):
    response = client.post("/spots", json=SPOT_PAYLOAD, headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["description"] is None


def test_update_spot_description(client, auth_headers, test_user, db):
    spot = Spot(name="Café", address="Bean St", lat=51.5, lng=-0.1,
                icon="faMugHot", city="London", user_id=test_user.id)
    db.add(spot)
    db.commit()

    response = client.patch(
        f"/spots/{spot.id}",
        json={**SPOT_PAYLOAD, "description": "Best flat white in the area"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["description"] == "Best flat white in the area"


def test_update_spot_clear_description(client, auth_headers, test_user, db):
    spot = Spot(name="Café", address="Bean St", lat=51.5, lng=-0.1,
                icon="faMugHot", description="Old note", user_id=test_user.id)
    db.add(spot)
    db.commit()

    response = client.patch(
        f"/spots/{spot.id}",
        json={**SPOT_PAYLOAD, "description": None},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["description"] is None


def test_create_spot(client, auth_headers):
    response = client.post("/spots", json=SPOT_PAYLOAD, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Home"
    assert data["address"] == "123 Main St"
    assert data["icon"] == "faHouse"
    assert data["lat"] == 51.5
    assert "id" in data


def test_create_spot_unauthenticated(client):
    response = client.post("/spots", json=SPOT_PAYLOAD)
    assert response.status_code == 401


def test_get_spots_empty(client, auth_headers):
    response = client.get("/spots", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


def test_get_spots_returns_own_spots(client, auth_headers, test_user, db):
    spot = Spot(name="Work", address="Office Rd", lat=51.51, lng=-0.09,
                icon="faBriefcase", city="London", user_id=test_user.id)
    db.add(spot)
    db.commit()

    response = client.get("/spots", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Work"


def test_get_spots_unauthenticated(client):
    response = client.get("/spots")
    assert response.status_code == 401


def test_update_spot(client, auth_headers, test_user, db):
    spot = Spot(name="Home", address="Old St", lat=51.5, lng=-0.1,
                icon="faHouse", city="London", user_id=test_user.id)
    db.add(spot)
    db.commit()

    response = client.patch(f"/spots/{spot.id}",
                            json={"name": "My Home", "address": "New St", "lat": 51.5, "lng": -0.1, "icon": "faHouse", "city": "London"},
                            headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["name"] == "My Home"
    assert response.json()["address"] == "New St"


def test_update_spot_wrong_user(client, db):
    from src.auth import create_access_token
    from src.models import User
    import bcrypt

    other = User(first_name="Other", email="other2@example.com",
                 hashed_password=bcrypt.hashpw(b"pass", bcrypt.gensalt()).decode())
    db.add(other)
    db.commit()
    db.refresh(other)

    spot = Spot(name="Home", address="St", lat=51.5, lng=-0.1,
                icon="faHouse", city="London", user_id=other.id)
    db.add(spot)
    db.commit()

    headers = {"Authorization": f"Bearer {create_access_token(other.id + 999)}"}
    response = client.patch(f"/spots/{spot.id}", json=SPOT_PAYLOAD, headers=headers)
    assert response.status_code in (401, 404)


def test_delete_spot(client, auth_headers, test_user, db):
    spot = Spot(name="Gym", address="Gym St", lat=51.5, lng=-0.1,
                icon="faDumbbell", city="London", user_id=test_user.id)
    db.add(spot)
    db.commit()

    response = client.delete(f"/spots/{spot.id}", headers=auth_headers)
    assert response.status_code == 204


def test_delete_spot_wrong_user(client, auth_headers, db):
    from src.auth import create_access_token
    from src.models import User
    import bcrypt

    other = User(first_name="Other", email="other3@example.com",
                 hashed_password=bcrypt.hashpw(b"pass", bcrypt.gensalt()).decode())
    db.add(other)
    db.commit()
    db.refresh(other)

    spot = Spot(name="Home", address="St", lat=51.5, lng=-0.1,
                icon="faHouse", city="London", user_id=other.id)
    db.add(spot)
    db.commit()

    response = client.delete(f"/spots/{spot.id}", headers=auth_headers)
    assert response.status_code == 204
    # Spot should still exist (wrong user's delete is a no-op)
    assert db.get(Spot, spot.id) is not None


def test_create_spot_with_place_id(client, auth_headers):
    payload = {**SPOT_PAYLOAD, "place_id": "ChIJN1t_tDeuEmsRUsoyG83frY4"}
    response = client.post("/spots", json=payload, headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["place_id"] == "ChIJN1t_tDeuEmsRUsoyG83frY4"


def test_create_spot_place_id_optional(client, auth_headers):
    response = client.post("/spots", json=SPOT_PAYLOAD, headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["place_id"] is None


def test_update_spot_sets_place_id(client, auth_headers, test_user, db):
    spot = Spot(name="Café", address="Bean St", lat=51.5, lng=-0.1,
                icon="faMugHot", city="London", user_id=test_user.id)
    db.add(spot)
    db.commit()

    response = client.patch(
        f"/spots/{spot.id}",
        json={**SPOT_PAYLOAD, "place_id": "ChIJN1t_tDeuEmsRUsoyG83frY4"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["place_id"] == "ChIJN1t_tDeuEmsRUsoyG83frY4"


def test_spots_isolated_between_users(client, db):
    from src.auth import create_access_token
    from src.models import User
    import bcrypt

    u1 = User(first_name="U1", email="u1@example.com",
              hashed_password=bcrypt.hashpw(b"pass", bcrypt.gensalt()).decode())
    u2 = User(first_name="U2", email="u2@example.com",
              hashed_password=bcrypt.hashpw(b"pass", bcrypt.gensalt()).decode())
    db.add_all([u1, u2])
    db.commit()
    db.refresh(u1); db.refresh(u2)

    db.add(Spot(name="Home", address="St", lat=51.5, lng=-0.1,
                icon="faHouse", city="London", user_id=u1.id))
    db.commit()

    headers2 = {"Authorization": f"Bearer {create_access_token(u2.id)}"}
    response = client.get("/spots", headers=headers2)
    assert response.json() == []


def test_create_spot_city_stored_and_returned(client, auth_headers):
    response = client.post("/spots", json={**SPOT_PAYLOAD, "city": "Paris"}, headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["city"] == "Paris"


def test_create_spot_city_required(client, auth_headers):
    payload = {k: v for k, v in SPOT_PAYLOAD.items() if k != "city"}
    response = client.post("/spots", json=payload, headers=auth_headers)
    assert response.status_code == 422


def test_update_spot_city(client, auth_headers, test_user, db):
    spot = Spot(name="Café", address="Bean St", lat=51.5, lng=-0.1,
                icon="faMugHot", city="London", user_id=test_user.id)
    db.add(spot)
    db.commit()

    response = client.patch(
        f"/spots/{spot.id}",
        json={**SPOT_PAYLOAD, "city": "Manchester"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["city"] == "Manchester"
