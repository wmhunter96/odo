import pytest

from app import csv_import


def test_historical_csv_detects_eleven_records(historical_csv_text):
    rows = csv_import.parse_csv(historical_csv_text)
    summary = csv_import.summarize(csv_import.recalculate(rows))
    assert summary.total == 11
    assert summary.valid == 11
    assert summary.errors == 0


def test_historical_csv_mpg_alignment_matches_acceptance_data(historical_csv_text):
    """The legacy 'Avg MPG' column is shifted one row earlier than the
    fill-up it belongs to. The importer must ignore it entirely and
    recompute MPG from odometer + gallons instead."""
    rows = csv_import.recalculate(csv_import.parse_csv(historical_csv_text))
    valid = sorted([r for r in rows if r.is_valid], key=lambda r: r.timestamp)

    expected = [
        (401, None),
        (821, 49.934609),
        (1203, 56.938441),
        (1571, 52.109884),
        (1779, 52.419355),
        (2150, 54.295331),
        (2511, 55.995036),
        (2956, 51.285006),
        (3173, 48.513302),
        (3469, 48.901371),
        (3859, 51.376630),
    ]

    assert [r.odometer for r in valid] == [odo for odo, _ in expected]

    # First historical fill-up cannot have an MPG -- there is no earlier
    # odometer reading to compute a distance from.
    assert valid[0].mpg is None

    for row, (odometer, expected_mpg) in zip(valid, expected):
        assert row.odometer == odometer
        if expected_mpg is None:
            assert row.mpg is None
        else:
            assert row.mpg == pytest.approx(expected_mpg, abs=0.01)


def test_missing_required_column_raises():
    bad_csv = "Odometer,Gallons\n401,7.449\n"
    with pytest.raises(ValueError):
        csv_import.parse_csv(bad_csv)


def test_row_with_unparseable_odometer_is_flagged_invalid():
    bad_csv = (
        "Odometer,Date,Gallons,Price/Gal,Fuel Total $,Gas Station Address,Brand,Avg MPG\n"
        "not-a-number,09/05/2025 6:11:59 PM,7.449,4.199,31.28,123 Main St,Shell,\n"
    )
    rows = csv_import.parse_csv(bad_csv)
    assert len(rows) == 1
    assert not rows[0].is_valid
    assert rows[0].errors


def test_recalculate_derives_missing_fuel_total_from_gallons_and_price():
    csv_text = (
        "Odometer,Date,Gallons,Price/Gal,Fuel Total $,Gas Station Address,Brand,Avg MPG\n"
        "100,01/01/2026 9:00 AM,10,4.00,,,,\n"
    )
    rows = csv_import.recalculate(csv_import.parse_csv(csv_text))
    assert rows[0].fuel_total == pytest.approx(40.00)
