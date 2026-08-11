"""Pure, dependency-free math for fill-up derived values.

Nothing here touches the database or ORM models -- functions accept plain
values (or any object exposing .odometer / .gallons / .fuel_total) so they
stay trivially unit-testable and reusable from both the API layer and the
CSV importer.

Derived values (miles_driven, mpg, cost_per_mile) are NEVER persisted. They
are always computed from source values against the previous fill-up in
chronological order, which is what lets editing a historical odometer value
correctly ripple forward without a migration or backfill step.
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Protocol


class FillUpLike(Protocol):
    odometer: float
    gallons: float | None
    fuel_total: float | None


@dataclass
class Derived:
    miles_driven: float | None
    mpg: float | None
    cost_per_mile: float | None


def miles_driven(previous_odometer: float | None, odometer: float) -> float | None:
    """Miles driven since the previous fill-up. None if there is no previous
    fill-up, or the odometer did not actually advance (bad data)."""
    if previous_odometer is None:
        return None
    delta = odometer - previous_odometer
    return delta if delta > 0 else None


def mpg(miles: float | None, gallons: float | None) -> float | None:
    """Standard full-tank MPG: miles driven since last fill-up divided by the
    CURRENT fill-up's gallons. This belongs to the current fill-up, not the
    previous one."""
    if miles is None or not gallons:
        return None
    return miles / gallons


def cost_per_mile(fuel_total: float | None, miles: float | None) -> float | None:
    if not miles or fuel_total is None:
        return None
    return fuel_total / miles


def derive(
    previous_odometer: float | None,
    odometer: float,
    gallons: float | None,
    fuel_total: float | None,
) -> Derived:
    m = miles_driven(previous_odometer, odometer)
    mg = mpg(m, gallons)
    cpm = cost_per_mile(fuel_total, m)
    return Derived(miles_driven=m, mpg=mg, cost_per_mile=cpm)


@dataclass
class AnnotatedFillUp:
    record: object
    previous_odometer: float | None
    miles_driven: float | None
    mpg: float | None
    cost_per_mile: float | None


def annotate_sequence(records: list) -> list[AnnotatedFillUp]:
    """Given fill-ups already sorted chronologically (ascending), compute
    derived values for each using the immediately preceding record."""
    out: list[AnnotatedFillUp] = []
    prev = None
    for record in records:
        prev_odo = prev.odometer if prev is not None else None
        d = derive(prev_odo, record.odometer, record.gallons, record.fuel_total)
        out.append(
            AnnotatedFillUp(
                record=record,
                previous_odometer=prev_odo,
                miles_driven=d.miles_driven,
                mpg=d.mpg,
                cost_per_mile=d.cost_per_mile,
            )
        )
        prev = record
    return out


def lifetime_mpg(annotated: list[AnnotatedFillUp]) -> float | None:
    """Total tracked distance / total gallons used for those tracked
    intervals -- NOT a simple average of per-fill-up MPGs."""
    tracked = [a for a in annotated if a.miles_driven is not None]
    total_miles = sum(a.miles_driven for a in tracked)
    total_gallons = sum(a.record.gallons for a in tracked if a.record.gallons)
    if not total_gallons:
        return None
    return total_miles / total_gallons


def average_mpg(annotated: list[AnnotatedFillUp]) -> float | None:
    """Simple arithmetic mean of individual fill-up MPGs."""
    values = [a.mpg for a in annotated if a.mpg is not None]
    if not values:
        return None
    return mean(values)


def total_miles(annotated: list[AnnotatedFillUp]) -> float:
    return sum(a.miles_driven for a in annotated if a.miles_driven is not None)


def total_gallons(annotated: list[AnnotatedFillUp]) -> float:
    return sum(a.record.gallons for a in annotated if a.record.gallons)


def total_fuel_cost(annotated: list[AnnotatedFillUp]) -> float:
    return sum(a.record.fuel_total for a in annotated if a.record.fuel_total)


def average_price_per_gallon(records: list) -> float | None:
    prices = [r.price_per_gallon for r in records if r.price_per_gallon]
    if not prices:
        return None
    return mean(prices)
