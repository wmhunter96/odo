from datetime import datetime

import pytest

from app.csv_import import _parse_date


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("09/05/2025 6:11:59 PM", datetime(2025, 9, 5, 18, 11, 59)),
        ("09/27/2025 7:39 PM", datetime(2025, 9, 27, 19, 39)),
        ("12/6/2025 12:39:31 PM", datetime(2025, 12, 6, 12, 39, 31)),
        ("1/10/2026 12:42:00 PM", datetime(2026, 1, 10, 12, 42, 0)),
    ],
)
def test_parses_all_legacy_date_formats(raw, expected):
    parsed = _parse_date(raw)
    assert parsed.replace(tzinfo=None) == expected


def test_empty_date_returns_none():
    assert _parse_date("") is None
    assert _parse_date(None) is None
