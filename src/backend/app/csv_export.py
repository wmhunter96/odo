"""CSV export -- a clean, self-contained schema that can fully reconstruct
fill-up history without depending on Odo itself."""
from __future__ import annotations

import csv
import io

from . import calculations

EXPORT_COLUMNS = [
    "Date",
    "Odometer",
    "Miles Driven",
    "Gallons",
    "Price/Gal",
    "Fuel Total $",
    "Gas Station Address",
    "Brand",
    "MPG",
    "Cost Per Mile",
]


def export_csv(fillups_chronological: list) -> str:
    """fillups_chronological: FillUp records already sorted ascending by
    timestamp (see routes.fillups.ordered_fillups)."""
    annotated = calculations.annotate_sequence(fillups_chronological)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(EXPORT_COLUMNS)

    for a in annotated:
        f = a.record
        writer.writerow(
            [
                f.timestamp.strftime("%Y-%m-%d %H:%M:%S") if f.timestamp else "",
                f"{f.odometer:g}" if f.odometer is not None else "",
                f"{a.miles_driven:g}" if a.miles_driven is not None else "",
                f"{f.gallons:g}" if f.gallons is not None else "",
                f"{f.price_per_gallon:g}" if f.price_per_gallon is not None else "",
                f"{f.fuel_total:.2f}" if f.fuel_total is not None else "",
                f.station_address or "",
                f.station_brand or "",
                f"{a.mpg:.4f}" if a.mpg is not None else "",
                f"{a.cost_per_mile:.4f}" if a.cost_per_mile is not None else "",
            ]
        )

    return buf.getvalue()
