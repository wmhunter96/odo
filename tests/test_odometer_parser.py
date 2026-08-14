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


# Real dashboard layout: the odometer sits in a cluster with several other
# numbers (outside temp, clock, speed, distance-to-empty, seatbelt icons)
# that would otherwise be plausible-length competitors for "biggest/first
# number wins" heuristics. "ODO" and "mi" flank the real reading and
# should be used as anchors ahead of the generic scoring.
DASHBOARD_CLUSTER_TEXT = """75°F 12:52
0
MPH
Distance to Empty
280 miles
REAR
P ODO 4090mi
"""


def test_odo_and_mi_anchors_win_over_other_dashboard_numbers():
    result = parse_odometer(OCRResult(text=DASHBOARD_CLUSTER_TEXT), previous_odometer=3800)
    assert result.value == 4090
    assert result.confidence == 100.0


def test_odo_anchor_wins_even_without_a_previous_reading():
    result = parse_odometer(OCRResult(text=DASHBOARD_CLUSTER_TEXT), previous_odometer=None)
    assert result.value == 4090


def test_odo_anchor_strips_non_digit_characters_between_anchors():
    # A stray misread character landing between the digits and "mi" (e.g.
    # a smudge) shouldn't get treated as part of the number.
    result = parse_odometer(OCRResult(text="ODO 4090.mi"), previous_odometer=None)
    assert result.value == 4090
