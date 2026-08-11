"""Extract gas-receipt fields from raw OCR text.

Deliberately NOT built around any single station's receipt layout. Every
field is found independently via a handful of regex patterns tried in
priority order, so a receipt missing/garbling one field doesn't prevent the
others from being extracted. Missing-value derivation (gallons * price =
total) lives in validation.py, not here -- this module only reports what it
actually found.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from dateutil import parser as dateparser

from .provider import OCRResult

# Common gas station brands, used to normalize noisy OCR text like
# "COSTCO WHOLESALE #123" -> "Costco". Longest names first so e.g. "Phillips
# 66" matches before a bare "66" would.
KNOWN_BRANDS = [
    "Costco", "Sam's Club", "Kwik Trip", "Kwik Star",
    "Phillips 66", "Circle K", "Flying J", "Murphy USA", "Murphy Express",
    "Love's", "Pilot", "QuikTrip", "RaceTrac", "Racetrack", "Speedway",
    "Sheetz", "Wawa", "Casey's", "ExxonMobil", "Exxon", "Mobil", "Chevron",
    "Shell", "ARCO", "Sinclair", "Conoco", "Valero", "Marathon", "Sunoco",
    "BP", "76", "Kroger Fuel", "Safeway Fuel", "Fred Meyer Fuel",
    "Maverik", "Stripes", "Cumberland Farms", "Thorntons", "Holiday",
]

# [ \t]* (not \s*) deliberately keeps these on a single line -- receipts
# routinely have a price-per-gallon line immediately above/below a gallons
# line, and \s* would happily "match" across that line break onto the
# wrong number.
_GALLON_PATTERNS = [
    re.compile(r"(\d{1,2}\.\d{2,4})[ \t]*(?:GAL(?:LONS?|S)?)\b", re.IGNORECASE),
    # Negative lookbehind for "/" excludes "PRICE/GAL" style labels, which
    # contain the substring "GAL" but describe price-per-gallon, not gallons.
    re.compile(r"(?<!/)\bGAL(?:LONS?|S)?\b[ \t]*[:\-]?[ \t]*\$?[ \t]*(\d{1,2}\.\d{2,4})", re.IGNORECASE),
    # Compact single-letter unit some pumps print, e.g. "7.591G".
    re.compile(r"(\d{1,2}\.\d{2,4})[ \t]*G\b", re.IGNORECASE),
]

_PRICE_PER_GAL_PATTERNS = [
    re.compile(r"\$?\s*(\d{1,2}\.\d{2,4})\s*/\s*(?:GAL(?:LON)?|G)\b", re.IGNORECASE),
    re.compile(r"PRICE\s*/?\s*GAL(?:LON)?S?\.?\s*[:\-]?\s*\$?\s*(\d{1,2}\.\d{2,4})", re.IGNORECASE),
    re.compile(r"PER\s*GAL(?:LON)?S?\.?\s*[:\-]?\s*\$?\s*(\d{1,2}\.\d{2,4})", re.IGNORECASE),
    re.compile(r"PPG\s*[:\-]?\s*\$?\s*(\d{1,2}\.\d{2,4})", re.IGNORECASE),
    re.compile(r"@\s*\$?\s*(\d{1,2}\.\d{2,4})\s*/?\s*(?:GAL)?", re.IGNORECASE),
]

_TOTAL_PATTERNS = [
    re.compile(r"FUEL\s*TOTAL\s*[:\-]?\s*\$?\s*(\d{1,4}\.\d{2})", re.IGNORECASE),
    re.compile(r"PUMP\s*TOTAL\s*[:\-]?\s*\$?\s*(\d{1,4}\.\d{2})", re.IGNORECASE),
    re.compile(r"AMOUNT\s*DUE\s*[:\-]?\s*\$?\s*(\d{1,4}\.\d{2})", re.IGNORECASE),
    re.compile(r"BALANCE\s*(?:DUE)?\s*[:\-]?\s*\$?\s*(\d{1,4}\.\d{2})", re.IGNORECASE),
    # "SUB TOTAL"/"SUBTOTAL" is excluded by requiring TOTAL not be preceded
    # by "SUB " (either as one word, which \b already blocks, or as two).
    re.compile(r"(?<!SUB )\bTOTAL\s*(?:SALE|DUE|AMOUNT)?\s*[:\-]?\s*\$?\s*(\d{1,4}\.\d{2})", re.IGNORECASE),
    re.compile(r"\bAMOUNT\s*[:\-]?\s*\$?\s*(\d{1,4}\.\d{2})", re.IGNORECASE),
]

# No leading \b: OCR frequently glues a stray misread character straight
# onto a leading digit with no real word boundary between them (e.g. "01"
# misread as "a1", butted against nothing but the digits that follow), and
# the trailing "\b" plus the literal "/"/":" separators are already
# distinctive enough on their own to not need it. Optional whitespace
# around the separators for the same reason -- OCR sometimes inserts a
# stray space next to a misread character (e.g. "a1 /24/2026").
_DATE_TOKEN_RE = re.compile(r"\d{1,2}\s*[/\-]\s*\d{1,2}\s*[/\-]\s*\d{2,4}\b")
_TIME_TOKEN_RE = re.compile(r"\d{1,2}\s*:\s*\d{2}(?:\s*:\s*\d{2})?\s*[AaPp]\.?[Mm]\.?\b")

# \b around the state code in both of these is load-bearing: without it,
# any two consecutive uppercase letters immediately before a 5-digit run
# match -- which happily fires on completely unrelated all-caps receipt
# lines like "INVOICE 883062" (matching "CE" + "88306" out of the middle
# of "INVOICE"). The comma is required for the same reason: it's the one
# structural signal that reliably distinguishes "city, ST zip" from
# arbitrary nearby text.
_ADDRESS_FULL_RE = re.compile(
    r"\d{1,6}\s+[A-Za-z0-9.'\- ]{3,40}?,\s*[A-Za-z.\- ]{2,30},?\s*\b[A-Z]{2}\b\s*\d{5}(?:-\d{4})?"
)
_CITY_STATE_ZIP_RE = re.compile(r"[A-Za-z.\- ]{2,30},\s*\b[A-Z]{2}\b\s*\d{5}(?:-\d{4})?")
_STREET_LINE_RE = re.compile(r"^\s*\d{1,6}\s+[A-Za-z0-9.'\- ]{3,40}$")


@dataclass
class ReceiptResult:
    gallons: float | None = None
    price_per_gallon: float | None = None
    fuel_total: float | None = None
    timestamp: datetime | None = None
    station_brand: str | None = None
    station_address: str | None = None
    raw_text: str = ""
    warnings: list[str] = field(default_factory=list)


def _first_match(patterns: list[re.Pattern], text: str) -> float | None:
    for pattern in patterns:
        m = pattern.search(text)
        if m:
            try:
                return float(m.group(1))
            except (ValueError, IndexError):
                continue
    return None


def _extract_brand(text: str) -> str | None:
    upper = text.upper()
    for brand in KNOWN_BRANDS:
        if brand.upper() in upper:
            return brand
    return None


def _extract_address(lines: list[str]) -> str | None:
    joined = " ".join(line.strip() for line in lines if line.strip())
    m = _ADDRESS_FULL_RE.search(joined)
    if m:
        return re.sub(r"\s+", " ", m.group(0)).strip(" ,")

    for i, line in enumerate(lines):
        csz_match = _CITY_STATE_ZIP_RE.search(line)
        if csz_match and not _STREET_LINE_RE.match(line):
            # Use the actual matched "city, ST zip" text, not the whole
            # line -- the line can (and does, in practice) contain other
            # content the match happened to be found inside of.
            city_state_zip = csz_match.group(0).strip()
            # Try to combine with a street-number line directly above it.
            if i > 0 and _STREET_LINE_RE.match(lines[i - 1].strip()):
                combined = f"{lines[i - 1].strip()}, {city_state_zip}"
                return re.sub(r"\s+", " ", combined).strip(" ,")
            return city_state_zip
    return None


def _extract_datetime(text: str) -> datetime | None:
    date_match = _DATE_TOKEN_RE.search(text)
    if not date_match:
        return None
    time_match = _TIME_TOKEN_RE.search(text)
    # Strip whitespace the token regexes deliberately tolerated around
    # separators (see their comments) before handing off to dateutil.
    combined = re.sub(r"\s+", "", date_match.group(0))
    if time_match:
        combined = f"{combined} {re.sub(r'\\s+', '', time_match.group(0))}"
    try:
        return dateparser.parse(combined)
    except (ValueError, OverflowError):
        try:
            return dateparser.parse(re.sub(r"\s+", "", date_match.group(0)))
        except (ValueError, OverflowError):
            return None


def parse_receipt(result: OCRResult) -> ReceiptResult:
    text = result.text or ""
    lines = [ln for ln in text.splitlines()]

    gallons = _first_match(_GALLON_PATTERNS, text)
    price_per_gallon = _first_match(_PRICE_PER_GAL_PATTERNS, text)
    fuel_total = _first_match(_TOTAL_PATTERNS, text)

    r = ReceiptResult(
        gallons=gallons,
        price_per_gallon=price_per_gallon,
        fuel_total=fuel_total,
        timestamp=_extract_datetime(text),
        station_brand=_extract_brand(text),
        station_address=_extract_address(lines),
        raw_text=text,
    )

    # Deliberately NOT warning about missing gallons/price/total here --
    # whether one of those three is genuinely missing or just derivable
    # from the other two depends on derive_missing_fuel_value(), which
    # this module doesn't call (see the module docstring). That decision,
    # and the resulting message, belongs to the caller (routes/ocr.py).
    if r.timestamp is None:
        r.warnings.append("Could not find a transaction date/time on the receipt.")

    return r
