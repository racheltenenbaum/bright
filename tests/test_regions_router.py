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
