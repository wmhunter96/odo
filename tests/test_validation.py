from datetime import datetime, timedelta, timezone

import pytest

from app import validation


def test_fuel_math_accepts_normal_rounding():
    # 8.411 * 4.459 = 37.510949 -- receipt rounds to 37.50
    assert validation.check_fuel_math(8.411, 4.459, 37.50) is None


def test_fuel_math_flags_large_mismatch():
    warning = validation.check_fuel_math(8.411, 4.459, 20.00)
    assert warning is not None
    assert "doesn't match" in warning


def test_derive_missing_fuel_value_needs_two_known():
    # Only gallons known -- must not invent price or total.
    gallons, price, total = validation.derive_missing_fuel_value(8.411, None, None)
    assert gallons == 8.411
    assert price is None
    assert total is None


def test_derive_missing_price_per_gallon():
    gallons, price, total = validation.derive_missing_fuel_value(8.411, None, 37.50)
    assert price == pytest.approx(37.50 / 8.411, abs=1e-3)


def test_derive_missing_total():
    gallons, price, total = validation.derive_missing_fuel_value(8.411, 4.459, None)
    assert total == pytest.approx(8.411 * 4.459, abs=0.01)


def test_odometer_warns_when_not_higher_than_previous():
    assert validation.check_odometer(18442, 13902) is not None
    assert validation.check_odometer(18071, 18442) is None


def test_mpg_needs_enough_history_before_flagging():
    # Fewer than min_samples records -- no flag even for an outlier.
    assert validation.check_mpg(8.2, [50, 51, 52]) is None


def test_mpg_flags_dramatic_outlier_once_history_exists():
    history = [50, 51, 49, 52, 50, 51]
    assert validation.check_mpg(8.2, history) is not None
    assert validation.check_mpg(50.5, history) is None


class _FillUp:
    def __init__(self, id, timestamp, odometer, gallons, fuel_total, station_brand=None):
        self.id = id
        self.timestamp = timestamp
        self.odometer = odometer
        self.gallons = gallons
        self.fuel_total = fuel_total
        self.station_brand = station_brand


def test_duplicate_detection_flags_near_identical_fillup():
    existing = _FillUp(1, datetime(2025, 9, 27, 19, 39, tzinfo=timezone.utc), 821, 8.411, 37.50)
    candidate = {
        "odometer": 822,
        "gallons": 8.40,
        "fuel_total": 37.55,
        "timestamp": datetime(2025, 9, 27, 20, 0, tzinfo=timezone.utc),
    }
    dupes = validation.find_duplicates(candidate, [existing])
    assert existing in dupes


def test_duplicate_detection_ignores_unrelated_fillup():
    existing = _FillUp(1, datetime(2025, 9, 27, 19, 39, tzinfo=timezone.utc), 821, 8.411, 37.50)
    candidate = {
        "odometer": 1600,
        "gallons": 6.0,
        "fuel_total": 25.00,
        "timestamp": datetime(2025, 11, 1, 12, 0, tzinfo=timezone.utc),
    }
    dupes = validation.find_duplicates(candidate, [existing])
    assert dupes == []


def test_duplicate_detection_requires_multiple_signals():
    # Only gallons happens to match -- everything else is unrelated.
    existing = _FillUp(1, datetime(2025, 9, 27, 19, 39, tzinfo=timezone.utc), 821, 8.411, 37.50)
    candidate = {
        "odometer": 5000,
        "gallons": 8.411,
        "fuel_total": 55.00,
        "timestamp": datetime(2025, 12, 25, 12, 0, tzinfo=timezone.utc),
    }
    dupes = validation.find_duplicates(candidate, [existing])
    assert dupes == []
