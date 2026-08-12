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

# Fast path for common chains ONLY -- normalizes noisy OCR text like
# "COSTCO WHOLESALE #123" down to a clean canonical "Costco". This is
# deliberately not the only way a brand gets found: independent/regional
# stations (of which there are far too many to ever hardcode) fall back to
# a structural heuristic in _extract_brand() instead of going unrecognized.
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
    # Last resort: a fuel-grade label followed by a number with a
    # spurious 4th decimal digit exactly where the "G" unit letter would
    # be -- a common misread in some receipt fonts (e.g. "5.422G" read as
    # "5.4226", the digit "6" standing in for "G"). US pump receipts
    # always print gallons to exactly 3 decimal places, so a 4th digit
    # here is a unit-letter misread, not real precision, far more often
    # than it's a coincidence -- captures only the 3 real decimals.
    re.compile(
        r"\b(?:REGULAR|PLUS|PREMIUM|MIDGRADE|DIESEL|UNLEADED)\b[ \t]*(\d{1,2}\.\d{3})\d\b",
        re.IGNORECASE,
    ),
]

# [.,] (not just \.) tolerates the decimal point misreading as a comma --
# confirmed against a real receipt ("PRICE/GAL $3,899" instead of
# "$3.899"). Safe to allow broadly here since a price-per-gallon is never
# in the thousands, so there's no real "thousands separator" comma this
# could be confused with. _first_match() normalizes the captured comma
# back to a period before parsing.
_PRICE_PER_GAL_PATTERNS = [
    re.compile(r"\$?\s*(\d{1,2}[.,]\d{2,4})\s*/\s*(?:GAL(?:LON)?|G)\b", re.IGNORECASE),
    re.compile(r"PRICE\s*/?\s*GAL(?:LON)?S?\.?\s*[:\-]?\s*\$?\s*(\d{1,2}[.,]\d{2,4})", re.IGNORECASE),
    re.compile(r"PER\s*GAL(?:LON)?S?\.?\s*[:\-]?\s*\$?\s*(\d{1,2}[.,]\d{2,4})", re.IGNORECASE),
    re.compile(r"PPG\s*[:\-]?\s*\$?\s*(\d{1,2}[.,]\d{2,4})", re.IGNORECASE),
    re.compile(r"@\s*\$?\s*(\d{1,2}[.,]\d{2,4})\s*/?\s*(?:GAL)?", re.IGNORECASE),
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
# City/state and the zip often land on two separate OCR lines rather than
# one -- these two match each half so they can be bridged back together.
_CITY_STATE_ONLY_RE = re.compile(r"[A-Za-z.\- ]{2,30},\s*\b[A-Z]{2}\b\s*$")
_BARE_ZIP_LINE_RE = re.compile(r"^\s*\d{5}(?:-\d{4})?\s*$")
_STREET_LINE_RE = re.compile(r"^\s*\d{1,6}\s+[A-Za-z0-9.'\- ]{3,40}$")
# Catches a garbled street line even when OCR mangles the leading digit
# badly enough that _STREET_LINE_RE's "starts with digits" check misses it
# entirely (e.g. "1004" -> "4aad") -- the street-type abbreviation at the
# end tends to survive better than the leading house number does.
_STREET_SUFFIX_RE = re.compile(
    r"\b(BLVD|BL|ST|AVE|AVENUE|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|PL|PLACE|HWY|PKWY|BOULEVARD|STREET)\.?\b",
    re.IGNORECASE,
)
# A line that's just masked account digits/asterisks ("XXXXXXXXX3003"),
# not a name.
_MASKED_OR_CODE_LINE_RE = re.compile(r"^[\sXx0-9#*\-]+$")
# Any run of 3+ consecutive digits reads as a reference/invoice/auth
# number, not a business name.
_DIGIT_RUN_RE = re.compile(r"\d{3,}")
# First-word denylist for the receipt's transaction/payment furniture --
# labels a hardcoded brand list can never keep up with, but these
# generic terms are common to virtually every receipt format.
_NON_BRAND_FIRST_WORDS = {
    "debit", "credit", "cash", "invoice", "auth", "pump", "regular", "plus",
    "premium", "diesel", "unleaded", "fuel", "total", "subtotal", "tax",
    "change", "balance", "approved", "verified", "sequence", "contactless",
    "mode", "aid", "tvr", "iad", "tsi", "arc", "arqc", "customer-activated",
    "customer", "us", "price", "amount",
}


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
                # Only ever relevant for patterns that deliberately allow a
                # comma as a misread decimal point (see _PRICE_PER_GAL_PATTERNS)
                # -- a no-op for every other pattern, which never capture one.
                return float(m.group(1).replace(",", "."))
            except (ValueError, IndexError):
                continue
    return None


# How many lines from the top of the receipt to consider for the brand
# fallback -- the name is always near the very top, and staying this
# narrow is itself a strong guard against picking up footer/payment
# garbage further down that the keyword denylist doesn't happen to catch.
_BRAND_SCAN_LINES = 8


def _looks_like_brand_line(line: str) -> bool:
    stripped = line.strip()
    if not (2 <= len(stripped) <= 40):
        return False
    if _STREET_LINE_RE.match(stripped) or _STREET_SUFFIX_RE.search(stripped):
        return False
    if _CITY_STATE_ZIP_RE.search(stripped):
        return False
    if _MASKED_OR_CODE_LINE_RE.match(stripped):
        return False
    if _DATE_TOKEN_RE.search(stripped) or _TIME_TOKEN_RE.search(stripped):
        return False
    if _DIGIT_RUN_RE.search(stripped):
        return False
    first_word = re.sub(r"[^a-z\-]", "", stripped.split()[0].lower()) if stripped.split() else ""
    if first_word in _NON_BRAND_FIRST_WORDS:
        return False
    if sum(c.isalpha() for c in stripped) < 2:
        return False
    return True


def _extract_brand(text: str, lines: list[str]) -> str | None:
    # Known chains first -- lets us normalize noisy OCR of a common brand
    # to its canonical name (e.g. "COSTCO WHOLESALE #123" -> "Costco").
    upper = text.upper()
    for brand in KNOWN_BRANDS:
        if brand.upper() in upper:
            return brand

    # Independent/regional stations will never all fit in a hardcoded
    # list -- fall back to whatever plausible-looking business-name line
    # appears first near the top of the receipt instead.
    for line in lines[:_BRAND_SCAN_LINES]:
        if _looks_like_brand_line(line):
            # Strip stray OCR-noise punctuation from the edges (a
            # misread border/torn-edge artifact, e.g. a trailing "]" or
            # "|") without touching real internal punctuation like
            # "Love's" or "7-Eleven".
            return re.sub(r"^[^A-Za-z0-9]+|[^A-Za-z0-9]+$", "", line.strip())

    return None


def _find_preceding_street_line(lines: list[str], index: int, lookback: int = 5) -> str | None:
    """Search backward from `index` for a street-address-looking line,
    tolerating other receipt content (a store name, a masked account
    number) sitting between it and the city/state/zip -- real layouts
    routinely have that gap, it's not just adjacent lines."""
    for j in range(index - 1, max(-1, index - 1 - lookback), -1):
        candidate = lines[j].strip()
        if candidate and (_STREET_LINE_RE.match(candidate) or _STREET_SUFFIX_RE.search(candidate)):
            return candidate
    return None


def _next_nonblank_line(lines: list[str], index: int, lookahead: int = 3) -> str | None:
    for j in range(index + 1, min(len(lines), index + 1 + lookahead)):
        candidate = lines[j].strip()
        if candidate:
            return candidate
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
            street = _find_preceding_street_line(lines, i)
            if street:
                combined = f"{street}, {city_state_zip}"
                return re.sub(r"\s+", " ", combined).strip(" ,")
            return city_state_zip

    # City/state and the zip commonly end up on two separate OCR lines --
    # bridge a "City, ST" line to a bare zip code on the next non-blank
    # line, rather than requiring them on one line together.
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not _CITY_STATE_ONLY_RE.search(stripped):
            continue
        zip_line = _next_nonblank_line(lines, i)
        if not zip_line or not _BARE_ZIP_LINE_RE.match(zip_line):
            continue
        city_state_zip = f"{stripped} {zip_line}"
        street = _find_preceding_street_line(lines, i)
        if street:
            combined = f"{street}, {city_state_zip}"
            return re.sub(r"\s+", " ", combined).strip(" ,")
        return re.sub(r"\s+", " ", city_state_zip).strip(" ,")

    return None


def _extract_datetime(text: str) -> datetime | None:
    date_match = _DATE_TOKEN_RE.search(text)
    if not date_match:
        return None
    # Strip whitespace the token regexes deliberately tolerated around
    # separators (see their comments) before handing off to dateutil.
    date_str = re.sub(r"\s+", "", date_match.group(0))

    time_match = _TIME_TOKEN_RE.search(text)
    time_candidates: list[str] = []
    if time_match:
        time_str = re.sub(r"\s+", "", time_match.group(0))
        time_candidates.append(time_str)
        # A 2-digit hour that's outside 1-12 (this pattern only matches
        # with an AM/PM suffix, so it's always a 12-hour clock) is almost
        # always a misread leading digit glued onto a real 1-digit hour --
        # the same "extra spurious digit" issue as the gallons G-unit
        # misread, e.g. a smudged "0" reading as "9" turns "4:19" into
        # "94:19". Retry with just the last hour digit.
        hour_match = re.match(r"^(\d{2}):", time_str)
        if hour_match and int(hour_match.group(1)) > 12:
            time_candidates.append(hour_match.group(1)[-1] + time_str[2:])

    for time_str in time_candidates or [None]:  # type: ignore[list-item]
        candidate = f"{date_str} {time_str}" if time_str else date_str
        try:
            return dateparser.parse(candidate)
        except (ValueError, OverflowError):
            continue

    try:
        return dateparser.parse(date_str)
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
        station_brand=_extract_brand(text, lines),
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
