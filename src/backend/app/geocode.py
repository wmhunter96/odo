"""Optional, best-effort address geocoding via OpenStreetMap Nominatim.

This is the ONE place in Odo that talks to the internet. It's entirely
opt-in (Settings -> "Address Lookup", off by default) and never required
for the app to function -- every call here degrades silently back to
whatever OCR already extracted on any failure: no internet, a timeout, no
results, a malformed response. Callers never need to handle an error case
beyond "treat this like it never ran".

Purpose: OCR reads a house number wrong far more often than it gets the
street/city/state/zip wrong (see receipt_parser's address extraction --
digit-level misreads on a bare number have no structural signal to correct
the way a known letter/digit confusable does). A geocoder can sanity-check
and often correct that, and confirm the result is actually a fuel station
before trusting it -- exactly what was asked for, not a general-purpose
address-lookup feature.

Nominatim's usage policy
(https://operations.osmfoundation.org/policies/nominatim/) requires a
descriptive User-Agent and caps sustained use at ~1 request/second, both
trivially satisfied by a personal app doing at most one lookup per
fill-up. No API key, no cost -- it's the OpenStreetMap project's own free
public instance.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "Odo-GasTracker/1.0 (self-hosted personal fuel tracker; https://github.com/wmhunter96/odo)"
DEFAULT_TIMEOUT_SECONDS = 3.0


@dataclass
class GeocodeResult:
    address: str
    latitude: float
    longitude: float
    is_fuel_station: bool


def _format_address(components: dict) -> str | None:
    """Build a compact 'NUM Street, City, ST ZIP' string from Nominatim's
    address breakdown, matching the style the rest of the app uses --
    its own display_name field is much more verbose than that."""
    house_number = components.get("house_number")
    road = components.get("road")
    city = components.get("city") or components.get("town") or components.get("village")
    state = components.get("state_code") or components.get("state")
    postcode = components.get("postcode")

    if not road or not city:
        return None

    street = f"{house_number} {road}".strip() if house_number else road
    parts = [street, city]
    if state and postcode:
        parts.append(f"{state} {postcode}")
    elif state:
        parts.append(state)
    elif postcode:
        parts.append(postcode)
    return ", ".join(parts)


def _fetch_json(url: str, timeout: float) -> object:
    """Isolated so tests can mock just this, without reimplementing (or
    actually performing) the HTTP call."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def lookup_address(query: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> GeocodeResult | None:
    """Best-effort forward geocode of a (possibly OCR-garbled) address.
    Only returns a result when Nominatim's top match is tagged as an
    amenity=fuel point of interest -- if the address doesn't resolve to an
    actual gas station, this returns None rather than risk "correcting"
    the address to the wrong nearby business."""
    if not query or not query.strip():
        return None

    params = urllib.parse.urlencode(
        {"q": query, "format": "jsonv2", "limit": 1, "addressdetails": 1}
    )
    url = f"{NOMINATIM_URL}?{params}"

    try:
        data = _fetch_json(url, timeout)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None

    if not isinstance(data, list) or not data:
        return None

    top = data[0]
    if not isinstance(top, dict):
        return None
    if top.get("class") != "amenity" or top.get("type") != "fuel":
        return None

    try:
        lat = float(top["lat"])
        lon = float(top["lon"])
    except (KeyError, TypeError, ValueError):
        return None

    formatted = _format_address(top.get("address") or {})
    if not formatted:
        return None

    return GeocodeResult(address=formatted, latitude=lat, longitude=lon, is_fuel_station=True)
