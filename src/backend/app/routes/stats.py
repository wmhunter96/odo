from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import calculations, schemas
from ..db import get_db
from ..deps import get_active_vehicle
from ..models import Setting
from .fillups import ordered_fillups, _to_out

router = APIRouter(prefix="/api/stats", tags=["stats"])


def _get_timezone(db: Session) -> ZoneInfo:
    setting = db.get(Setting, "timezone")
    tz_name = setting.value if setting else "UTC"
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("UTC")


def _month_key(dt: datetime, tz: ZoneInfo) -> str:
    local = dt.astimezone(tz)
    return f"{local.year:04d}-{local.month:02d}"


def _month_stats(annotated: list[calculations.AnnotatedFillUp], tz: ZoneInfo, month_key: str):
    in_month = [a for a in annotated if _month_key(a.record.timestamp, tz) == month_key]
    spend = sum(a.record.fuel_total or 0 for a in in_month)
    miles = sum(a.miles_driven or 0 for a in in_month if a.miles_driven is not None)
    gallons = sum(a.record.gallons or 0 for a in in_month if a.miles_driven is not None)
    mpg = (miles / gallons) if gallons else None
    return spend, miles, mpg


@router.get("/dashboard", response_model=schemas.DashboardStats)
def dashboard_stats(vehicle_id: int | None = None, db: Session = Depends(get_db)):
    vid = vehicle_id or get_active_vehicle(db).id
    records = ordered_fillups(db, vid)
    annotated = calculations.annotate_sequence(records)
    tz = _get_timezone(db)

    last = None
    if annotated:
        last = _to_out(annotated[-1])

    now = datetime.now(tz)
    month_key = f"{now.year:04d}-{now.month:02d}"
    month_spend, month_miles, month_mpg = _month_stats(annotated, tz, month_key)

    return schemas.DashboardStats(
        last_fillup=last,
        month_spend=month_spend,
        month_miles=month_miles,
        month_mpg=month_mpg,
        lifetime_average_mpg=calculations.average_mpg(annotated),
        lifetime_mpg=calculations.lifetime_mpg(annotated),
        lifetime_total_miles=calculations.total_miles(annotated),
        lifetime_total_fuel_cost=calculations.total_fuel_cost(annotated),
        lifetime_average_price=calculations.average_price_per_gallon(records),
    )


@router.get("/lifetime", response_model=schemas.LifetimeStats)
def lifetime_stats(vehicle_id: int | None = None, db: Session = Depends(get_db)):
    vid = vehicle_id or get_active_vehicle(db).id
    records = ordered_fillups(db, vid)
    annotated = calculations.annotate_sequence(records)
    tz = _get_timezone(db)

    most_recent_mpg = annotated[-1].mpg if annotated else None

    now = datetime.now(tz)
    month_key = f"{now.year:04d}-{now.month:02d}"
    month_spend, month_miles, _ = _month_stats(annotated, tz, month_key)

    by_month: dict[str, dict] = {}
    for a in annotated:
        key = _month_key(a.record.timestamp, tz)
        bucket = by_month.setdefault(key, {"spend": 0.0, "miles": 0.0})
        bucket["spend"] += a.record.fuel_total or 0
        if a.miles_driven is not None:
            bucket["miles"] += a.miles_driven

    n_months = len(by_month) or 1
    avg_monthly_spend = sum(b["spend"] for b in by_month.values()) / n_months if by_month else None
    avg_monthly_miles = sum(b["miles"] for b in by_month.values()) / n_months if by_month else None

    total_miles = calculations.total_miles(annotated)
    total_cost = calculations.total_fuel_cost(annotated)

    return schemas.LifetimeStats(
        most_recent_mpg=most_recent_mpg,
        average_mpg=calculations.average_mpg(annotated),
        lifetime_mpg=calculations.lifetime_mpg(annotated),
        average_fuel_price=calculations.average_price_per_gallon(records),
        total_gallons=calculations.total_gallons(annotated),
        total_fuel_cost=total_cost,
        total_miles=total_miles,
        current_month_spend=month_spend,
        current_month_miles=month_miles,
        average_monthly_spend=avg_monthly_spend,
        average_monthly_miles=avg_monthly_miles,
        cost_per_mile=(total_cost / total_miles) if total_miles else None,
    )
