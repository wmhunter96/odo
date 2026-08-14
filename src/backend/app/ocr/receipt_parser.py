"""Turn a receipt-photo VLM extraction into a validated ReceiptResult.

Previously this module ran a battery of regex patterns over raw OCR text
to recover each field independently (see git history for that approach --
gallons/price/total/date/address, each with its own OCR-misread-recovery
tricks). PaddleOCR-VL-1.6 (receipt_vlm.py) now does that recovery itself:
it's asked directly for these fields, in JSON, with instructions to use
null rather than guess an unreadable value. That moves the character-level
judgment calls (is this a "5" or an "S"? does "GAL" here mean gallons or
price-per-gallon?) into the model, where a vision-language model that can
see the whole receipt at once is much better positioned to make them than
regex ever was.

What's left here is deliberately boring: pull each field out of the
model's JSON by name, coerce it to the right Python type defensively
(never raise on a malformed value -- treat it as missing instead), combine
date+time into one timestamp, canonicalize a known chain's name, and
report what's still missing. This keeps the parsing layer's job the same
as before -- normalize+validate raw extracted data into ReceiptResult --
just fed by a different kind of "raw extracted data" than an OCR text blob.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from dateutil import parser as dateparser

from .receipt_vlm import ReceiptExtraction

# Canonicalizes noisy real-world spellings of common chains (e.g. "COSTCO
# WHOLESALE #123") down to one clean name. The model is asked for
# "station_name" directly and usually returns something reasonable
# already, but a hardcoded list is still worth applying on top of that for
# the handful of chains a fill-up log likely repeats often, same as
# before this module talked to a VLM instead of raw OCR text.
KNOWN_BRANDS = [
    "Costco", "Sam's Club", "Kwik Trip", "Kwik Star",
    "Phillips 66", "Circle K", "Flying J", "Murphy USA", "Murphy Express",
    "Love's", "Pilot", "QuikTrip", "RaceTrac", "Racetrack", "Speedway",
    "Sheetz", "Wawa", "Casey's", "ExxonMobil", "Exxon", "Mobil", "Chevron",
    "Shell", "ARCO", "Sinclair", "Conoco", "Valero", "Marathon", "Sunoco",
    "BP", "76", "Kroger Fuel", "Safeway Fuel", "Fred Meyer Fuel",
    "Maverik", "Stripes", "Cumberland Farms", "Thorntons", "Holiday",
]


@dataclass
class ReceiptResult:
    gallons: float | None = None
    price_per_gallon: float | None = None
    fuel_total: float | None = None
    pump_number: int | None = None
    fuel_type: str | None = None
    timestamp: datetime | None = None
    station_brand: str | None = None
    station_address: str | None = None
    raw_text: str = ""
    warnings: list[str] = field(default_factory=list)


def _coerce_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _coerce_float(value: Any) -> float | None:
    # bool is an int subclass in Python -- reject it explicitly so a
    # stray JSON `true`/`false` never silently becomes 1.0/0.0.
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace("$", "").replace(",", "")
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else None
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        try:
            return int(cleaned)
        except ValueError:
            return None
    return None


def _canonicalize_brand(name: str | None) -> str | None:
    if not name:
        return None
    # \b word boundaries matter for short names like "76" or "BP" -- a
    # plain substring check would match those inside unrelated text too.
    upper = name.upper()
    for brand in KNOWN_BRANDS:
        if re.search(rf"\b{re.escape(brand.upper())}\b", upper):
            return brand
    return name


def _normalize_fuel_type(value: str | None) -> str | None:
    if not value:
        return None
    return value.strip().title()


def _parse_extracted_datetime(date_value: Any, time_value: Any) -> datetime | None:
    date_str = _coerce_str(date_value)
    if not date_str:
        return None
    time_str = _coerce_str(time_value) or "00:00:00"
    try:
        return dateparser.parse(f"{date_str} {time_str}")
    except (ValueError, OverflowError):
        pass
    # The model was asked for "YYYY-MM-DD" / 24-hour "HH:MM:SS" specifically
    # so this combined parse should normally succeed -- but if it followed
    # the date format and not the time (or vice versa), a date-only parse
    # is still better than reporting the whole timestamp as unreadable.
    try:
        return dateparser.parse(date_str)
    except (ValueError, OverflowError):
        return None


def parse_receipt(extraction: ReceiptExtraction) -> ReceiptResult:
    if extraction.fields is None:
        return ReceiptResult(
            raw_text=extraction.raw_response,
            warnings=[
                "Could not read the receipt -- the AI extraction step didn't return usable data. "
                "Please enter the fields manually."
            ],
        )

    fields = extraction.fields
    r = ReceiptResult(
        gallons=_coerce_float(fields.get("gallons")),
        price_per_gallon=_coerce_float(fields.get("price_per_gallon")),
        fuel_total=_coerce_float(fields.get("total")),
        pump_number=_coerce_int(fields.get("pump_number")),
        fuel_type=_normalize_fuel_type(_coerce_str(fields.get("fuel_type"))),
        timestamp=_parse_extracted_datetime(fields.get("date"), fields.get("time")),
        station_brand=_canonicalize_brand(_coerce_str(fields.get("station_name"))),
        station_address=_coerce_str(fields.get("address")),
        raw_text=extraction.raw_response,
    )

    # Deliberately NOT warning about missing gallons/price/total here --
    # whether one of those three is genuinely missing or just derivable
    # from the other two depends on derive_missing_fuel_value(), which
    # this module doesn't call (see the module docstring). That decision,
    # and the resulting message, belongs to the caller (routes/ocr.py).
    if r.timestamp is None:
        r.warnings.append("Could not find a transaction date/time on the receipt.")

    return r
