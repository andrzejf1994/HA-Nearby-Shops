"""Integration constants and extensible OSM shop catalogue."""

DOMAIN = "nearby_shops"
ENDPOINT = "https://overpass-api.de/api/interpreter"
SHOP_TYPES = (
    "supermarket",
    "convenience",
    "department_store",
    "mall",
    "bakery",
    "butcher",
    "greengrocer",
    "chemist",
    "pharmacy",
    "clothes",
    "shoes",
    "electronics",
    "hardware",
    "doityourself",
    "furniture",
    "mobile_phone",
    "computer",
    "pet",
    "sports",
    "bicycle",
    "car",
    "car_parts",
    "beauty",
    "cosmetics",
    "variety_store",
    "discount",
    "general",
    "kiosk",
    "books",
    "stationery",
    "toys",
)
DEFAULTS = {
    "location_entities": [],
    "shop_types": ["all"],
    "name_filter": "all",
    "names": [],
    "radius": 300,
    "max_accuracy": 100,
    "allow_missing_accuracy": True,
    "movement_threshold": 50,
    "minimum_query_interval": 60,
}
CACHE_TTL = 300
CACHE_MARGIN = 75
MAX_CACHE_ENTRIES = 128
