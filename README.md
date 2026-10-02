# Nearby Shops

Custom integration for **Home Assistant 2026.9+** and **HACS**, version `0.1.0`.
Finds OpenStreetMap `shop=*` POIs around multiple people, GPS trackers or any
entities with valid latitude/longitude. Configuration is entirely through the UI,
with English and Polish translations.

## Install through HACS

1. Open **HACS** in the sidebar → three-dot menu → **Custom repositories**.
2. URL: `https://github.com/andrzejf1994/HA-Nearby-Shops`.
3. Type/category: **Integration** → **Add**.
4. Find **Nearby Shops** → open → **Download**.
5. Restart Home Assistant.
6. **Settings → Devices & services → Add integration → Nearby Shops**.

HACS 2 uses a unified dashboard, so an Integrations tab is not necessary.
The repository must be public. HACS discovers published GitHub Releases, not
merely tags. This integration ships its own `brand/` images, supported by HA since
2026.3 and accepted by current HACS validation. CI must pass before release.
See [validation results](VALIDATION.md) for what has actually been verified.

## Manual installation

Copy `custom_components/nearby_shops` into your HA configuration directory under
`custom_components/nearby_shops`. Restart HA and add the integration in Devices &
services. YAML configuration is not required or supported.

## Configuration

Initial setup and **Configure** (Options Flow) share three screens. Options
automatically reload the integration and preserve the ConfigEntry identity.

| Screen | Settings |
| --- | --- |
| Locations | Multiple person/device_tracker entities, or other entities currently exposing valid coordinates |
| Shops | OSM types, All shop types, All / Include only / Exclude, multiple custom names |
| Range and updates | Radius, accuracy limit, missing accuracy policy, movement threshold, interval |

Config Flow screenshot placeholders (capture from a running HA instance):

- [ ] `images/config-locations.png`: entity selector
- [ ] `images/config-shops.png`: shop types and name filters
- [ ] `images/config-settings.png`: range, accuracy and update settings

| Setting | Default | Range / behavior |
| --- | --- | --- |
| Radius | 300 m | 50–5000 m |
| Maximum allowed location error | 100 m | 0–5000 m; smaller gps_accuracy is better |
| Allow missing accuracy | On | Off skips sources without gps_accuracy |
| Movement threshold | 50 m | 1–5000 m from last successful search location |
| Refresh interval | 60 s | 60–86400 s |

Movement **OR** elapsed interval permits a new search. A 15-second timer handles
stationary locations and recovery. State events are coalesced by the coordinator.
An independent five-second shared network safety throttle protects the API during
teleports and bursts. Distant sources queue fairly behind the shared API lock.

Missing coordinates, unknown/unavailable states, negative/nonfinite GPS accuracy,
or poor accuracy prevent searching. Last-good results stay available with `stale`
and a diagnostic status. Before the first good result, entities are unavailable.
Last-good snapshots are in memory, and do not survive restart/options reload.

Names and brands match exactly, ignoring case and redundant whitespace. Either
`name` or `brand` can match. `Lidl` matches brand Lidl when a name is Lidl Warszawa;
without that brand it does not match Lidl Warszawa. No fuzzy or substring matching
is used. Accents remain significant. Display name falls back to brand, then type.

The pharmacy option searches **shop=pharmacy**, not the more common
**amenity=pharmacy**, which is outside this release's scope. Extend `SHOP_TYPES`
in const.py and regenerate translations to add options; All accepts any nonempty
shop value.

## Sensors and attributes

Each source creates three entities. Entity IDs below are examples; HA may add suffixes.

| Entity | State | Attributes |
| --- | --- | --- |
| sensor.andrzej_nearby_shops | Number of matching shops | shops, sorted by distance |
| sensor.andrzej_nearest_shop | Nearest name, unknown if none | Nearest POI fields |
| binary_sensor.andrzej_near_shop | on if at least one match, otherwise off | nearest_shop, nearest_distance, shop_count |

Each shop has `name`, `brand`, `type`, `distance` (metres), `latitude`, `longitude`,
`osm_id`, `osm_type`. Haversine distance is calculated locally. Nodes use their
coordinates; ways/relations use Overpass center, not an entrance or boundary.
Only centers within the radius count.

Common attributes: `radius`, `location_entity`, `latitude`, `longitude`,
`location_accuracy`, `observed_accuracy`, `last_successful_update`,
`last_query_attempt`, `update_status`, `last_error`, `stale`.
Coordinates/accuracy describe the last successful source observation; failed
searches do not mislabel retained shops with a new location. `observed_accuracy`
describes the current reported error. Attempt timestamps include cache/backoff
decisions. Timestamps are absent before the first attempt.

Statuses: updated, cache_hit, movement_threshold, poor_accuracy, invalid_accuracy,
missing_accuracy, invalid_location, location_unavailable, api_error.
Error codes include http_429, http_503, timeout, connection_error,
invalid_response and backoff. A successful empty response gives count 0,
binary off and nearest unknown.

## Automation: notify me near an interesting shop

Configure Include only with Lidl, Kaufland, Biedronka and Aldi, then:

```yaml
alias: Notify me near an interesting shop
triggers:
  - trigger: state
    entity_id: binary_sensor.andrzej_near_shop
    to: "on"
conditions:
  - condition: template
    value_template: "{{ not state_attr('binary_sensor.andrzej_near_shop', 'stale') }}"
actions:
  - action: notify.mobile_app_your_phone
    data:
      title: Nearby shop
      message: >-
        {{ state_attr('binary_sensor.andrzej_near_shop', 'nearest_shop') }}
        is {{ state_attr('binary_sensor.andrzej_near_shop', 'nearest_distance') }} m away.
mode: single
```

Replace the source ID and notification action. This fires when entering proximity,
not on every change of the nearest shop.

## Cache, Overpass, limitations and privacy

The shared memory cache holds up to 128 circles for five minutes. Queries cover
radius + 75 m; another source reuses a response only if its entire requested
circle fits in that coverage and tag/types match. Local distances, names and
radius filtering always use the actual source. Name lists are not sent to Overpass.
A 60-second refresh can use cached OSM data up to five minutes old.

Requests use HA's aiohttp session and https://overpass-api.de/api/interpreter,
with 35-second client and 25-second query timeouts. HTTP errors, partial responses
with `remark`, malformed JSON and outages retain good data. Numeric Retry-After
on 429 and bounded exponential backoff prevent retry bursts. Public Overpass has
no availability guarantee; keep radii and source counts modest.

OSM coverage/classification depends on volunteer mapping. Duplicate OSM identities
are removed; named POIs of the same type within 10 m are conservatively collapsed.
Distinct shops can share names/coordinates, so deduplication cannot be perfect.
These sensors are intended for personal automations, not safety-critical geofencing.

GPS coordinates are sent to Overpass and appear in sensor attributes/history.
Consider recorder exclusions if location history is unwanted. Downloadable
diagnostics redact coordinates, source IDs, name filters and shop lists; they retain
accuracy, timestamps, counts, API status and cache statistics. Logs do not contain
coordinates or person IDs.

Data: **© [OpenStreetMap contributors](https://www.openstreetmap.org/copyright)**,
available under ODbL. No map tiles are downloaded.