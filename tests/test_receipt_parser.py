from app.ocr.provider import OCRResult
from app.ocr.receipt_parser import parse_receipt

COSTCO_RECEIPT = """COSTCO WHOLESALE
2201 S Santa Anita Ave, Arcadia, CA 91006

7.591 GAL
4.199 / GAL

FUEL TOTAL
$31.87

01/10/2026
12:42 PM
"""

CHEVRON_RECEIPT = """CHEVRON
500 W Main St, Alhambra, CA 91801

PRICE/GAL: $4.290
GALLONS: 6.709
TOTAL SALE $28.78

10/12/2025 5:15 PM
"""


def test_parses_costco_style_receipt():
    result = parse_receipt(OCRResult(text=COSTCO_RECEIPT))
    assert result.gallons == 7.591
    assert result.price_per_gallon == 4.199
    assert result.fuel_total == 31.87
    assert result.station_brand == "Costco"
    assert result.timestamp is not None
    assert result.timestamp.month == 1 and result.timestamp.day == 10 and result.timestamp.year == 2026


def test_parses_alternate_receipt_layout():
    result = parse_receipt(OCRResult(text=CHEVRON_RECEIPT))
    assert result.gallons == 6.709
    assert result.price_per_gallon == 4.29
    assert result.fuel_total == 28.78
    assert result.station_brand == "Chevron"


def test_missing_fields_produce_warnings_not_exceptions():
    result = parse_receipt(OCRResult(text="garbled unreadable text ###"))
    assert result.gallons is None
    assert result.warnings
