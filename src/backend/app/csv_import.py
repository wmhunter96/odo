"""Historical CSV import.

Supports the exact legacy spreadsheet schema:

    Odometer, Date, Gallons, Price/Gal, Fuel Total $,
    Gas Station Address, Brand, Avg MPG

Important: the legacy "Avg MPG" column is row-shifted by one relative to the
fill-up it actually describes (see recalculate()), so it is NEVER imported
directly. Odometer + Gallons are treated as ground truth and MPG is always
recomputed from them.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import datetime

from dateutil import parser as dateparser

from . import calculations, validation

REQUIRED_COLUMNS = {"Odometer", "Date", "Gallons"}
EXPECTED_COLUMNS = [
    "Odometer",
    "Date",
    "Gallons",
    "Price/Gal",
    "Fuel Total $",
    "Gas Station Address",
    "Brand",
    "Avg MPG",
]


@dataclass
class ImportRow:
    row_number: int
    odometer: float | None = None
    timestamp: datetime | None = None
    gallons: float | None = None
    price_per_gallon: float | None = None
    fuel_total: float | None = None
    station_address: str | None = None
    station_brand: str | None = None
    miles_driven: float | None = None
    mpg: float | None = None
    cost_per_mile: float | None = None
    is_duplicate_in_file: bool = False
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors


@dataclass
class ImportSummary:
    total: int
    valid: int
    errors: int
    rows: list[ImportRow]


def _parse_float(raw: str | None) -> float | None:
    if raw is None:
        return None
    cleaned = raw.strip().replace("$", "").replace(",", "")
    if cleaned == "":
        return None
    return float(cleaned)


def _parse_date(raw: str | None) -> datetime | None:
    cleaned = (raw or "").strip()
    if not cleaned:
        return None
    # dateutil handles single/double digit month & day and optional seconds
    # out of the box, e.g. "9/5/2025 6:11:59 PM", "1/10/2026 12:42 PM".
    return dateparser.parse(cleaned)


def parse_csv(content: str) -> list[ImportRow]:
    reader = csv.DictReader(io.StringIO(content))
    header = {c.strip() for c in (reader.fieldnames or [])}
    missing = REQUIRED_COLUMNS - header
    if missing:
        raise ValueError(f"CSV is missing required column(s): {', '.join(sorted(missing))}")

    rows: list[ImportRow] = []
    for i, raw in enumerate(reader, start=2):  # row 1 is the header
        row = ImportRow(row_number=i)

        odo_raw = raw.get("Odometer")
        try:
            row.odometer = _parse_float(odo_raw)
            if row.odometer is None:
                row.errors.append("Missing odometer value")
        except ValueError:
            row.errors.append(f"Could not parse odometer '{odo_raw}'")

        date_raw = raw.get("Date")
        try:
            row.timestamp = _parse_date(date_raw)
            if row.timestamp is None:
                row.errors.append("Missing date")
        except (ValueError, OverflowError):
            row.errors.append(f"Could not parse date '{date_raw}'")

        gallons_raw = raw.get("Gallons")
        try:
            row.gallons = _parse_float(gallons_raw)
            if row.gallons is None:
                row.errors.append("Missing gallons value")
        except ValueError:
            row.errors.append(f"Could not parse gallons '{gallons_raw}'")

        try:
            row.price_per_gallon = _parse_float(raw.get("Price/Gal"))
        except ValueError:
            row.errors.append("Could not parse Price/Gal")

        try:
            row.fuel_total = _parse_float(raw.get("Fuel Total $"))
        except ValueError:
            row.errors.append("Could not parse Fuel Total $")

        row.station_address = (raw.get("Gas Station Address") or "").strip() or None
        row.station_brand = (raw.get("Brand") or "").strip() or None
        # raw.get("Avg MPG") is intentionally never used -- see module docstring.

        rows.append(row)
    return rows


def recalculate(rows: list[ImportRow]) -> list[ImportRow]:
    """Sort valid rows chronologically, flag in-file duplicates, derive any
    missing fuel value, and recompute miles/mpg/cost-per-mile from the
    previous row's odometer -- ignoring the legacy Avg MPG column."""
    valid = [r for r in rows if r.is_valid]
    valid.sort(key=lambda r: (r.timestamp, r.odometer))

    seen: set[tuple] = set()
    prev_odometer: float | None = None
    for row in valid:
        key = (round(row.odometer, 1), row.timestamp.date() if row.timestamp else None, round(row.gallons, 2))
        if key in seen:
            row.is_duplicate_in_file = True
        seen.add(key)

        row.gallons, row.price_per_gallon, row.fuel_total = validation.derive_missing_fuel_value(
            row.gallons, row.price_per_gallon, row.fuel_total
        )

        derived = calculations.derive(prev_odometer, row.odometer, row.gallons, row.fuel_total)
        row.miles_driven = derived.miles_driven
        row.mpg = derived.mpg
        row.cost_per_mile = derived.cost_per_mile
        prev_odometer = row.odometer

    return rows


def summarize(rows: list[ImportRow]) -> ImportSummary:
    valid = [r for r in rows if r.is_valid]
    errors = [r for r in rows if not r.is_valid]
    return ImportSummary(total=len(rows), valid=len(valid), errors=len(errors), rows=rows)


def import_preview(content: str) -> ImportSummary:
    rows = parse_csv(content)
    rows = recalculate(rows)
    # Preserve original row order for display purposes after recalculation
    # touched only the valid subset in place.
    rows.sort(key=lambda r: r.row_number)
    return summarize(rows)
