"""Pure location, filtering and parsing logic, independent of Home Assistant."""

from dataclasses import dataclass
from math import asin, cos, isfinite, radians, sin, sqrt
from typing import Any


def distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres, including the date line."""
    a = (
        sin(radians(lat2 - lat1) / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(radians(lon2 - lon1) / 2) ** 2
    )
    return 6371008.8 * 2 * asin(sqrt(min(1, max(0, a))))


def number(value: Any) -> float | None:
    """Reject missing, boolean, NaN and infinite coordinates/accuracy."""
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except ValueError, TypeError, OverflowError:
        return None
    return result if isfinite(result) else None


@dataclass(frozen=True)
class Location:
    """Validated observation."""

    latitude: float
    longitude: float
    accuracy: float | None


def location(
    attributes: dict, maximum: float, allow_missing: bool
) -> tuple[Location | None, str]:
    """Validate coordinates and maximum allowed location error."""
    lat, lon = number(attributes.get("latitude")), number(attributes.get("longitude"))
    if lat is None or lon is None or not -90 <= lat <= 90 or not -180 <= lon <= 180:
        return None, "invalid_location"
    accuracy = number(attributes.get("gps_accuracy"))
    if "gps_accuracy" in attributes and (accuracy is None or accuracy < 0):
        return None, "invalid_accuracy"
    if accuracy is None and not allow_missing:
        return None, "missing_accuracy"
    if accuracy is not None and accuracy > maximum:
        return None, "poor_accuracy"
    return Location(lat, lon, accuracy), "ok"


def normalize(value: str) -> str:
    """Exact case-insensitive matching with collapsed whitespace."""
    return " ".join(value.split()).casefold()


def parse_elements(payload: Any, key: str = "shop") -> list[dict[str, Any]]:
    """Parse nodes and centers of ways/relations; reject partial API results."""
    if (
        not isinstance(payload, dict)
        or payload.get("remark")
        or not isinstance(payload.get("elements"), list)
    ):
        raise ValueError("Invalid or partial Overpass response")
    result = []
    seen = set()
    for item in payload["elements"]:
        if not isinstance(item, dict):
            continue
        tags = item.get("tags")
        osm_type, osm_id = item.get("type"), item.get("id")
        if (
            not isinstance(tags, dict)
            or not isinstance(tags.get(key), str)
            or not tags[key]
        ):
            continue
        if osm_type not in ("node", "way", "relation") or not isinstance(osm_id, int):
            continue
        coords = item if osm_type == "node" else item.get("center", {})
        if not isinstance(coords, dict):
            continue
        point, _ = location(
            {"latitude": coords.get("lat"), "longitude": coords.get("lon")}, 0, True
        )
        identity = (osm_type, osm_id)
        if point is None or identity in seen:
            continue
        seen.add(identity)
        raw_name, raw_brand = tags.get("name"), tags.get("brand")
        name = raw_name if isinstance(raw_name, str) else ""
        brand = raw_brand if isinstance(raw_brand, str) else ""
        result.append(
            {
                "name": name.strip() or brand.strip() or tags[key],
                "brand": brand,
                "type": tags[key],
                "latitude": point.latitude,
                "longitude": point.longitude,
                "osm_id": osm_id,
                "osm_type": osm_type,
            }
        )
    return result


def filter_shops(pois: list[dict], point: Location, settings: dict) -> list[dict]:
    """Filter locally and conservatively deduplicate overlapping representations."""
    names = {normalize(name) for name in settings["names"] if normalize(name)}
    result: list[dict] = []
    for poi in pois:
        if (
            "all" not in settings["shop_types"]
            and poi["type"] not in settings["shop_types"]
        ):
            continue
        matched = bool({normalize(poi["name"]), normalize(poi["brand"])} & names)
        if (settings["name_filter"] == "include" and not matched) or (
            settings["name_filter"] == "exclude" and matched
        ):
            continue
        metres = distance(
            point.latitude, point.longitude, poi["latitude"], poi["longitude"]
        )
        if metres <= settings["radius"]:
            result.append({**poi, "distance": round(metres, 1)})
    result.sort(key=lambda shop: (shop["distance"], shop["osm_type"], shop["osm_id"]))
    unique: list[dict] = []
    groups: dict[tuple[str, str], list[dict]] = {}
    for shop in result:
        identity = (normalize(shop["name"]), shop["type"])
        candidates = groups.get(identity, [])
        if any(
            (shop["brand"] or shop["name"] != shop["type"])
            and distance(
                shop["latitude"],
                shop["longitude"],
                other["latitude"],
                other["longitude"],
            )
            <= 10
            for other in candidates
        ):
            continue
        unique.append(shop)
        groups.setdefault(identity, []).append(shop)
    return unique


def should_query(
    point: Location,
    previous: Location | None,
    elapsed: float,
    movement: float,
    interval: float,
) -> bool:
    """Movement OR elapsed time triggers a refresh (API has a separate safety throttle)."""
    return (
        previous is None
        or elapsed >= interval
        or distance(
            point.latitude, point.longitude, previous.latitude, previous.longitude
        )
        >= movement
    )
