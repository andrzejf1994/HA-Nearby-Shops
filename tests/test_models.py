"""Pure geospatial and OSM filtering regression tests."""

import pytest

from custom_components.nearby_shops.const import DEFAULTS
from custom_components.nearby_shops.models import (
    Location,
    distance,
    filter_shops,
    location,
    parse_elements,
    should_query,
)


def element(osm_type="node", osm_id=1, **tags):
    """Build a small OSM element."""
    return {
        "type": osm_type,
        "id": osm_id,
        "tags": {"shop": "supermarket", **tags},
        **(
            {"lat": 50, "lon": 20}
            if osm_type == "node"
            else {"center": {"lat": 50, "lon": 20}}
        ),
    }


def test_distance():
    assert distance(50, 20, 50, 20) == 0
    assert distance(0, 0, 0, 1) == pytest.approx(111195, abs=1)
    assert distance(0, 179.999, 0, -179.999) < 223
    assert distance(0, 0, 0, 180) == pytest.approx(20015114, abs=1)


@pytest.mark.parametrize("kind", ["node", "way", "relation"])
def test_parser_geometry(kind):
    poi = parse_elements({"elements": [element(kind, name="Lidl")]})[0]
    assert (poi["osm_type"], poi["latitude"], poi["longitude"]) == (kind, 50, 20)


def test_name_fallback():
    shops = parse_elements({"elements": [element(brand="Lidl"), element(osm_id=2)]})
    assert [shop["name"] for shop in shops] == ["Lidl", "supermarket"]


@pytest.mark.parametrize(
    "payload", [None, {}, {"elements": {}}, {"elements": [], "remark": "timeout"}]
)
def test_invalid_response(payload):
    with pytest.raises(ValueError):
        parse_elements(payload)


def test_invalid_elements_and_osm_identity():
    assert (
        parse_elements(
            {
                "elements": [
                    None,
                    {"type": "node"},
                    element(shop=""),
                    {**element(), "lat": float("nan")},
                ]
            }
        )
        == []
    )
    assert (
        len(parse_elements({"elements": [element(), element(), element("way")]})) == 2
    )


@pytest.mark.parametrize(
    "mode,names,expected",
    [
        ("all", [], 2),
        ("include", ["  LIDL "], 1),
        ("exclude", ["lidl"], 1),
        ("include", ["Carrefour   Express"], 1),
        ("include", ["Carrefour"], 0),
    ],
)
def test_name_filter(mode, names, expected):
    pois = parse_elements(
        {
            "elements": [
                element(name="Lidl Warszawa", brand="Lidl"),
                element(osm_id=2, name="Carrefour Express"),
            ]
        }
    )
    assert (
        len(
            filter_shops(
                pois,
                Location(50, 20, 5),
                {**DEFAULTS, "names": names, "name_filter": mode},
            )
        )
        == expected
    )


def test_type_radius_and_sorting():
    pois = parse_elements(
        {
            "elements": [
                element(name="A"),
                {**element(osm_id=2, name="B"), "lat": 50.001},
                {**element(osm_id=3, name="C"), "lat": 51},
                element(osm_id=4, name="D", shop="bakery"),
            ]
        }
    )
    result = filter_shops(
        pois, Location(50, 20, None), {**DEFAULTS, "shop_types": ["supermarket"]}
    )
    assert [shop["name"] for shop in result] == ["A", "B"]
    assert result[0]["distance"] <= result[1]["distance"]


def test_deduplication():
    pois = parse_elements(
        {
            "elements": [
                element(name="Lidl"),
                element("way", name="Lidl"),
                element("relation", name="Lidl"),
            ]
        }
    )
    assert len(filter_shops(pois, Location(50, 20, None), DEFAULTS)) == 1
    unnamed = parse_elements({"elements": [element(), element("way")]})
    assert len(filter_shops(unnamed, Location(50, 20, None), DEFAULTS)) == 2


@pytest.mark.parametrize(
    "accuracy,allow,status",
    [
        (15, True, "ok"),
        (100, True, "ok"),
        (120, True, "poor_accuracy"),
        (None, True, "ok"),
        (None, False, "missing_accuracy"),
        (-1, True, "invalid_accuracy"),
        (float("nan"), True, "invalid_accuracy"),
    ],
)
def test_accuracy(accuracy, allow, status):
    attrs = {"latitude": 50, "longitude": 20}
    if accuracy is not None:
        attrs["gps_accuracy"] = accuracy
    assert location(attrs, 100, allow)[1] == status


@pytest.mark.parametrize(
    "attrs",
    [
        {},
        {"latitude": 91, "longitude": 20},
        {"latitude": True, "longitude": 20},
        {"latitude": "unknown", "longitude": 20},
    ],
)
def test_invalid_location(attrs):
    assert location(attrs, 100, True)[0] is None


def test_movement_or_time():
    point = Location(50, 20, None)
    assert should_query(point, None, 0, 50, 60)
    assert not should_query(point, point, 59, 50, 60)
    assert should_query(point, point, 60, 50, 60)
    assert should_query(Location(51, 21, None), point, 1, 50, 60)
