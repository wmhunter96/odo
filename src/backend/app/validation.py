"""Sanity-checking for OCR results and manual entry.

Every check here returns a warning string (or None) -- nothing in this
module ever blocks a save. The UI decides whether to nag the user before
they tap "Looks Good".
"""
from __future__ import annotations

from statistics import mean, pstdev


def check_odometer(previous_odometer: float | None, odometer: float) -> str | None:
    if previous_odometer is not None and odometer <= previous_odometer:
        return "Odometer is lower than (or equal to) the previous reading. Please verify this value."
    return None


def expected_mpg_range(
    historical_mpgs: list[float], min_samples: int = 5
) -> tuple[float, float] | None:
    """Once enough history exists, build a plausible MPG band from it rather
    than hard-coding a vehicle's expected range."""
    values = [m for m in historical_mpgs if m is not None]
    if len(values) < min_samples:
        return None
    m = mean(values)
    sd = pstdev(values) if len(values) > 1 else 0.0
    # Guarantee a minimum band width so a very tight history doesn't flag
    # ordinary variation.
    spread = max(sd * 2.5, m * 0.15)
    return (max(0.0, m - spread), m + spread)


def check_mpg(new_mpg: float | None, historical_mpgs: list[float]) -> str | None:
    if new_mpg is None:
        return None
    rng = expected_mpg_range(historical_mpgs)
    if rng is None:
        return None
    lo, hi = rng
    if not (lo <= new_mpg <= hi):
        return (
            f"{new_mpg:.1f} MPG is significantly different from your normal fuel economy. "
            "Please verify the odometer and gallons."
        )
    return None


def check_fuel_math(
    gallons: float | None,
    price_per_gallon: float | None,
    fuel_total: float | None,
    tolerance_pct: float = 0.03,
    tolerance_abs: float = 0.15,
) -> str | None:
    """gallons * price_per_gallon should ~= fuel_total, allowing for normal
    receipt rounding."""
    if gallons is None or price_per_gallon is None or fuel_total is None:
        return None
    expected = gallons * price_per_gallon
    diff = abs(expected - fuel_total)
    if diff > max(tolerance_abs, fuel_total * tolerance_pct):
        return (
            f"Gallons × Price/Gal (${expected:.2f}) doesn't match Fuel Total "
            f"(${fuel_total:.2f}). Please verify."
        )
    return None


def derive_missing_fuel_value(
    gallons: float | None, price_per_gallon: float | None, fuel_total: float | None
) -> tuple[float | None, float | None, float | None]:
    """Fill in whichever of (gallons, price_per_gallon, fuel_total) is
    missing, given the other two. Never invents a value when fewer than two
    are known."""
    known = sum(v is not None for v in (gallons, price_per_gallon, fuel_total))
    if known < 2:
        return gallons, price_per_gallon, fuel_total

    if fuel_total is None:
        fuel_total = round(gallons * price_per_gallon, 2)
    elif price_per_gallon is None and gallons:
        price_per_gallon = round(fuel_total / gallons, 3)
    elif gallons is None and price_per_gallon:
        gallons = round(fuel_total / price_per_gallon, 3)

    return gallons, price_per_gallon, fuel_total


_FUEL_FIELD_LABELS = (
    ("gallons", "Gallons"),
    ("price_per_gallon", "Price/Gal"),
    ("fuel_total", "Fuel Total"),
)


def fuel_field_warnings(
    original: dict[str, float | None], final: dict[str, float | None]
) -> list[str]:
    """Per-field messaging for gallons/price_per_gallon/fuel_total, given
    what the receipt parser originally read (`original`, pre-derivation)
    versus the values after derive_missing_fuel_value() ran (`final`).

    A field that was missing but got filled in by derivation is a
    different (better -- calculated, not guessed) situation than one
    that's still genuinely missing, so each gets its own message rather
    than a blanket "couldn't find X" sitting next to an actually-filled-in
    value.
    """
    warnings_out = []
    for field, label in _FUEL_FIELD_LABELS:
        if original.get(field) is not None:
            continue
        if final.get(field) is not None:
            warnings_out.append(
                f"{label} wasn't directly readable on the receipt -- calculated from the other two values instead."
            )
        else:
            warnings_out.append(f"Could not find {label} on the receipt.")
    return warnings_out


def find_duplicates(
    candidate: dict,
    recent_fillups: list,
    odometer_tolerance: float = 2,
    gallons_tolerance: float = 0.05,
    total_tolerance: float = 0.50,
    time_window_hours: float = 20,
    min_signals: int = 3,
) -> list:
    """Score each recent fill-up against the candidate on four independent
    signals (odometer, gallons, fuel total, time proximity). Flag anything
    that agrees on at least `min_signals` of them -- a single coincidental
    match (e.g. same gallons) shouldn't trigger a false positive."""
    matches = []
    for f in recent_fillups:
        score = 0
        if candidate.get("odometer") is not None and abs(candidate["odometer"] - f.odometer) <= odometer_tolerance:
            score += 1
        if candidate.get("gallons") is not None and f.gallons and abs(candidate["gallons"] - f.gallons) <= gallons_tolerance:
            score += 1
        if candidate.get("fuel_total") is not None and f.fuel_total and abs(candidate["fuel_total"] - f.fuel_total) <= total_tolerance:
            score += 1
        ts = candidate.get("timestamp")
        if ts is not None and f.timestamp is not None:
            delta_hours = abs((ts - f.timestamp).total_seconds()) / 3600
            if delta_hours <= time_window_hours:
                score += 1
        if score >= min_signals:
            matches.append(f)
    return matches
