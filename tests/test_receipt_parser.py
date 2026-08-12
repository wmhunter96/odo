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


# Independent/regional stations will never all fit in a hardcoded brand
# list (this exact station -- "PRO MART" -- is a real example that
# prompted moving off one entirely). The fallback instead looks for the
# first plausible business-name line near the top of the receipt.
INDEPENDENT_STATION_RECEIPT = """1004 S LA CIENEGA BL
PRO MART
XXXXXXXXX3003
LOS ANGELES, CA
90035

REGULAR 5.422G
PRICE/GAL $3.899
FUEL TOTAL $ 21.14

01/24/2026 4:19:59 PM
"""


def test_brand_falls_back_to_first_plausible_line_for_unknown_station():
    result = parse_receipt(OCRResult(text=INDEPENDENT_STATION_RECEIPT))
    assert result.station_brand == "PRO MART"


def test_brand_fallback_strips_stray_ocr_edge_punctuation():
    # A misread border/torn-edge artifact commonly shows up as a stray
    # leading/trailing character on an otherwise-correct line.
    receipt = "PRO MART ]\nFUEL TOTAL $ 21.14\n"
    result = parse_receipt(OCRResult(text=receipt))
    assert result.station_brand == "PRO MART"


def test_gallons_recovers_from_g_unit_misread_as_trailing_digit():
    # Real garbled OCR output: "5.422G" read as "5.4226" -- the "G" unit
    # letter misread as a digit, right after a fuel-grade label. US pump
    # receipts always print gallons to exactly 3 decimal places, so the
    # 4th digit is recovered as the unit letter, not treated as more
    # precision or left unparsed (which would previously fall through to
    # derive_missing_fuel_value() and report a misleading "wasn't directly
    # readable" even though it plainly is, to a human, on the receipt).
    receipt = "REGULAR 5.4226\nPRICE/GAL $3.899\nFUEL TOTAL $ 21.14\n"
    result = parse_receipt(OCRResult(text=receipt))
    assert result.gallons == 5.422


def test_brand_fallback_skips_address_date_and_code_lines():
    receipt = (
        "4aad Ss LA CIEWEGA BL\n"  # garbled street line (survives via the suffix check)
        "XXXXXXXXX3003\n"  # masked account/reference code
        "ai/24/2ne6 A53270231\n"  # garbled date + reference number
        "PRO MART\n"  # the actual brand -- first line that isn't excluded
        "INVOICE 883062\n"
        "FUEL TOTAL $ 21.14\n"
    )
    result = parse_receipt(OCRResult(text=receipt))
    assert result.station_brand == "PRO MART"


def test_known_brand_takes_priority_over_fallback_heuristic():
    # If a recognized chain name appears anywhere, prefer its canonical
    # form over whatever line happens to be first.
    receipt = "Fuel Stop Express\nCOSTCO WHOLESALE #123\nFUEL TOTAL $10.00\n"
    result = parse_receipt(OCRResult(text=receipt))
    assert result.station_brand == "Costco"


def test_brand_fallback_returns_none_when_nothing_plausible_found():
    receipt = "XXXXXXXXX3003\nINVOICE 883062\nAUTH 979648\nFUEL TOTAL $10.00\n"
    result = parse_receipt(OCRResult(text=receipt))
    assert result.station_brand is None


# Real receipt layout: street address, then store name, then a masked
# account code, THEN city/state on one line and the zip on the very next
# line -- not all on one line together, which the original address regex
# required.
SEPARATE_LINE_ADDRESS_RECEIPT = """1004 S LA CIENEGA BL
PRO MART
XXXXXXXXX3003
LOS ANGELES, CA
90035

FUEL TOTAL $ 21.14
"""


def test_address_bridges_city_state_and_zip_on_separate_lines():
    result = parse_receipt(OCRResult(text=SEPARATE_LINE_ADDRESS_RECEIPT))
    assert result.station_address is not None
    assert "LOS ANGELES" in result.station_address
    assert "90035" in result.station_address
    # The street line should get picked up too, even with the store name
    # and masked account code sitting between it and the city/state line.
    assert "1004" in result.station_address
    assert "CIENEGA" in result.station_address.upper()


def test_address_bridging_skips_blank_lines_between_city_state_and_zip():
    receipt = "Some Station\n123 Main St\nSpringfield, IL\n\n62704\nFUEL TOTAL $10.00\n"
    result = parse_receipt(OCRResult(text=receipt))
    assert result.station_address is not None
    assert "62704" in result.station_address


def test_address_bridging_does_not_fire_without_a_real_zip_following():
    # "Springfield, IL" alone, followed by unrelated content -- must not
    # grab some other number and call it a zip.
    receipt = "Some Station\nSpringfield, IL\nINVOICE 883062\nFUEL TOTAL $10.00\n"
    result = parse_receipt(OCRResult(text=receipt))
    assert result.station_address is None
