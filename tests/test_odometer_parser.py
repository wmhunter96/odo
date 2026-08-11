from app.ocr.odometer_parser import parse_odometer
from app.ocr.provider import OCRResult

DASHBOARD_TEXT = """18442
RANGE 320 mi
OUTSIDE TEMP 72F
12:42 PM
AVG 44.6 MPG
TRIP A 128.4
"""


def test_picks_odometer_over_other_dashboard_numbers_using_previous_reading():
    result = parse_odometer(OCRResult(text=DASHBOARD_TEXT), previous_odometer=18071)
    assert result.value == 18442


def test_prefers_plausible_length_whole_number_without_previous_reading():
    result = parse_odometer(OCRResult(text=DASHBOARD_TEXT), previous_odometer=None)
    assert result.value == 18442


def test_returns_none_when_no_numbers_found():
    result = parse_odometer(OCRResult(text="no digits here at all"), previous_odometer=None)
    assert result.value is None
    assert result.candidates == []


def test_lower_than_previous_is_deprioritized_but_still_returned_if_only_option():
    result = parse_odometer(OCRResult(text="13902"), previous_odometer=18442)
    assert result.value == 13902  # still surfaced -- validation.check_odometer() is what warns the user
