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


COMPACT_PUMP_RECEIPT = """SHELL
1200 S Baldwin Ave, Arcadia, CA 91007

7.591G
4.199/G

AMOUNT DUE
31.87

08/10/2026 6:42 PM
"""


def test_parses_compact_pump_unit_and_amount_due():
    result = parse_receipt(OCRResult(text=COMPACT_PUMP_RECEIPT))
    assert result.gallons == 7.591
    assert result.price_per_gallon == 4.199
    assert result.fuel_total == 31.87
    assert result.station_brand == "Shell"


NO_DOLLAR_SIGN_RECEIPT = """QUIKTRIP
400 E Colorado Blvd, Pasadena, CA 91101

PER GAL 4.190
8.327 GALS

SUBTOTAL 34.89
TOTAL 34.89

08/10/2026 6:42 PM
"""


def test_total_without_dollar_sign_and_ignores_subtotal():
    result = parse_receipt(OCRResult(text=NO_DOLLAR_SIGN_RECEIPT))
    assert result.gallons == 8.327
    assert result.price_per_gallon == 4.19
    # Both SUBTOTAL and TOTAL happen to be equal here on purpose -- the
    # real assertion is that the SUBTOTAL line doesn't get matched as if
    # it were a plain "TOTAL" label (see the negative lookbehind).
    assert result.fuel_total == 34.89


# Real garbled OCR output from a photographed receipt (see git history) --
# "INVOICE 883062" used to get mistaken for a "city, ST zip" address
# because two consecutive uppercase letters anywhere before a 5-digit run
# matched (here: "CE" out of "INVOICE" + "88306" out of "883062"), with no
# comma or word-boundary requirement to rule out the middle of an unrelated
# word. It should extract nothing rather than something wrong.
GARBLED_RECEIPT_WITH_INVOICE_LINE = """PRO MART
Los ANGELES, CA
INVOICE 883062
AUTH 979648
REGULAR 5.4226
PRICE/GAL $3.899
FUEL TOTAL $ 21.14
"""


def test_address_does_not_false_positive_on_invoice_line():
    result = parse_receipt(OCRResult(text=GARBLED_RECEIPT_WITH_INVOICE_LINE))
    assert result.station_address is None
    # The rest of the receipt should still parse fine.
    assert result.price_per_gallon == 3.899
    assert result.fuel_total == 21.14


def test_address_extracts_real_city_state_zip_on_one_line():
    receipt = "Some Station\n123 Main St, Springfield, IL 62704\nFUEL TOTAL $10.00\n"
    result = parse_receipt(OCRResult(text=receipt))
    assert result.station_address is not None
    assert "62704" in result.station_address
    assert "INVOICE" not in result.station_address
