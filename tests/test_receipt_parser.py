"""parse_receipt() now consumes a ReceiptExtraction (PaddleOCR-VL-1.6's
parsed JSON output -- see receipt_vlm.py), not raw OCR text. These tests
build ReceiptExtraction objects directly rather than going through the
model, mirroring how test_receipt_vlm.py mocks the model call itself --
each module is tested at its own seam.
"""
from app.ocr.receipt_parser import parse_receipt
from app.ocr.receipt_vlm import ReceiptExtraction


def _extraction(**fields) -> ReceiptExtraction:
    return ReceiptExtraction(raw_response="{...}", fields=fields)


def test_parses_a_complete_extraction():
    result = parse_receipt(
        _extraction(
            station_name="PRO MART",
            address="1004 S LA CIENEGA BL, LOS ANGELES, CA 90035",
            date="2026-01-24",
            time="16:19:59",
            pump_number=6,
            fuel_type="REGULAR",
            gallons=5.422,
            price_per_gallon=3.899,
            total=21.14,
        )
    )
    assert result.station_brand == "PRO MART"
    assert result.station_address == "1004 S LA CIENEGA BL, LOS ANGELES, CA 90035"
    assert result.pump_number == 6
    assert result.fuel_type == "Regular"
    assert result.gallons == 5.422
    assert result.price_per_gallon == 3.899
    assert result.fuel_total == 21.14
    assert result.timestamp is not None
    assert (result.timestamp.year, result.timestamp.month, result.timestamp.day) == (2026, 1, 24)
    assert (result.timestamp.hour, result.timestamp.minute, result.timestamp.second) == (16, 19, 59)
    assert result.warnings == []


def test_known_brand_is_canonicalized():
    result = parse_receipt(_extraction(station_name="COSTCO WHOLESALE #123", gallons=7.591))
    assert result.station_brand == "Costco"


def test_unknown_brand_is_passed_through_as_is():
    result = parse_receipt(_extraction(station_name="Joe's Fuel Stop"))
    assert result.station_brand == "Joe's Fuel Stop"


def test_null_fields_become_none_not_zero_or_empty_string():
    # The extraction prompt explicitly asks the model for null rather
    # than a guessed value -- that must survive as None, not get coerced
    # into a misleading 0 or "".
    result = parse_receipt(
        _extraction(
            station_name=None,
            address=None,
            date=None,
            time=None,
            pump_number=None,
            fuel_type=None,
            gallons=None,
            price_per_gallon=None,
            total=None,
        )
    )
    assert result.station_brand is None
    assert result.station_address is None
    assert result.pump_number is None
    assert result.fuel_type is None
    assert result.gallons is None
    assert result.price_per_gallon is None
    assert result.fuel_total is None
    assert result.timestamp is None
    assert "date/time" in result.warnings[0]


def test_missing_keys_are_treated_the_same_as_explicit_nulls():
    # A model response that simply omits a key (rather than including it
    # as `null`) shouldn't behave any differently -- both mean "not read".
    result = parse_receipt(_extraction(gallons=5.0))
    assert result.station_brand is None
    assert result.fuel_total is None


def test_invalid_json_response_degrades_to_all_fields_missing():
    extraction = ReceiptExtraction(raw_response="I cannot read this receipt clearly.", fields=None)
    result = parse_receipt(extraction)
    assert result.gallons is None
    assert result.station_brand is None
    assert result.raw_text == "I cannot read this receipt clearly."
    assert result.warnings
    assert "AI extraction" in result.warnings[0]


def test_numeric_strings_are_coerced_defensively():
    # Not the happy path (the prompt asks for plain numbers), but the
    # model is free-text generation, not a strict API -- a stringified
    # number or a stray "$"/comma shouldn't be silently dropped as missing.
    result = parse_receipt(_extraction(gallons="5.422", price_per_gallon="$3.899", total="1,234.56"))
    assert result.gallons == 5.422
    assert result.price_per_gallon == 3.899
    assert result.fuel_total == 1234.56


def test_non_numeric_garbage_becomes_none_rather_than_raising():
    result = parse_receipt(_extraction(gallons="a lot", pump_number="six"))
    assert result.gallons is None
    assert result.pump_number is None


def test_boolean_json_values_are_rejected_not_coerced_to_0_or_1():
    # bool is technically an int subclass in Python/JSON -- a stray
    # `true`/`false` must not silently become 1.0/0.0.
    result = parse_receipt(_extraction(gallons=True, pump_number=False))
    assert result.gallons is None
    assert result.pump_number is None


def test_whitespace_only_strings_are_treated_as_missing():
    result = parse_receipt(_extraction(station_name="   ", address=""))
    assert result.station_brand is None
    assert result.station_address is None


def test_fuel_type_is_title_cased():
    assert parse_receipt(_extraction(fuel_type="DIESEL")).fuel_type == "Diesel"
    assert parse_receipt(_extraction(fuel_type="premium")).fuel_type == "Premium"


def test_pump_number_accepts_a_whole_number_float():
    # The model is asked for a JSON integer, but a VLM can just as
    # easily emit `6.0` for a whole-number field -- still unambiguous.
    result = parse_receipt(_extraction(pump_number=6.0))
    assert result.pump_number == 6


def test_pump_number_rejects_a_fractional_float():
    result = parse_receipt(_extraction(pump_number=6.5))
    assert result.pump_number is None


def test_date_without_time_still_parses_the_date():
    result = parse_receipt(_extraction(date="2026-01-24", time=None))
    assert result.timestamp is not None
    assert (result.timestamp.year, result.timestamp.month, result.timestamp.day) == (2026, 1, 24)


def test_unparseable_date_is_treated_as_missing_not_raising():
    result = parse_receipt(_extraction(date="not a date", time="16:19:59"))
    assert result.timestamp is None
    assert "date/time" in result.warnings[0]
