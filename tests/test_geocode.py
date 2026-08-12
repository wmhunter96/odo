"""app.geocode.lookup_address() must degrade silently on every failure
mode -- no internet, a timeout, no results, a non-fuel-station match,
malformed data -- since it's an optional enhancement layered on top of
OCR, never something the core fill-up flow can depend on succeeding.

_fetch_json() is the only network-touching function; every test here
mocks it directly rather than hitting the real Nominatim service (slow,
flaky in CI, and against a free public service's usage policy to hammer
from a test suite).
"""
from unittest.mock import patch

from app import geocode


def _mock_response(class_="amenity", type_="fuel", lat="34.05", lon="-118.25", address=None):
    return [
        {
            "class": class_,
            "type": type_,
            "lat": lat,
            "lon": lon,
            "address": address
            or {
                "house_number": "1004",
                "road": "South La Cienega Boulevard",
                "city": "Los Angeles",
                "state_code": "CA",
                "postcode": "90035",
            },
        }
    ]


def test_lookup_address_returns_result_for_confirmed_fuel_station():
    with patch.object(geocode, "_fetch_json", return_value=_mock_response()):
        result = geocode.lookup_address("4904 $ LA CIENEGA BL, LOS ANGELES, CA 90035")
    assert result is not None
    assert result.is_fuel_station is True
    assert result.latitude == 34.05
    assert result.longitude == -118.25
    assert "1004" in result.address
    assert "La Cienega" in result.address
    assert "90035" in result.address


def test_lookup_address_rejects_non_fuel_station_match():
    # A geocoder finding *some* nearby business isn't good enough --
    # only trust it when the match is actually tagged as a gas station.
    with patch.object(geocode, "_fetch_json", return_value=_mock_response(class_="shop", type_="convenience")):
        result = geocode.lookup_address("some address")
    assert result is None


def test_lookup_address_returns_none_on_empty_results():
    with patch.object(geocode, "_fetch_json", return_value=[]):
        assert geocode.lookup_address("nonexistent address") is None


def test_lookup_address_returns_none_on_network_failure():
    import urllib.error

    with patch.object(geocode, "_fetch_json", side_effect=urllib.error.URLError("no network")):
        assert geocode.lookup_address("1004 S La Cienega Blvd") is None


def test_lookup_address_returns_none_on_timeout():
    with patch.object(geocode, "_fetch_json", side_effect=TimeoutError):
        assert geocode.lookup_address("1004 S La Cienega Blvd") is None


def test_lookup_address_returns_none_on_malformed_response():
    with patch.object(geocode, "_fetch_json", return_value={"not": "a list"}):
        assert geocode.lookup_address("1004 S La Cienega Blvd") is None


def test_lookup_address_returns_none_on_missing_coordinates():
    bad = _mock_response()
    del bad[0]["lat"]
    with patch.object(geocode, "_fetch_json", return_value=bad):
        assert geocode.lookup_address("1004 S La Cienega Blvd") is None


def test_lookup_address_returns_none_when_address_cant_be_formatted():
    # No road/city in the address breakdown -- nothing usable to build a
    # display address from, even though the coordinates are present.
    bad = _mock_response(address={"house_number": "1004"})
    with patch.object(geocode, "_fetch_json", return_value=bad):
        assert geocode.lookup_address("1004 S La Cienega Blvd") is None


def test_lookup_address_returns_none_for_empty_query():
    assert geocode.lookup_address("") is None
    assert geocode.lookup_address("   ") is None


def test_lookup_address_never_calls_network_for_empty_query():
    # Sanity check that the empty-query short-circuit actually happens
    # before any network call would be attempted.
    with patch.object(geocode, "_fetch_json") as mock_fetch:
        geocode.lookup_address("")
        mock_fetch.assert_not_called()
