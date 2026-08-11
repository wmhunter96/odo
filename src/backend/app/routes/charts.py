from __future__ import annotations

from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import calculations, schemas
from ..db import get_db
from ..deps import get_active_vehicle
from ..models import Setting
from .fillups import ordered_fillups
from .stats import _get_timezone, _month_key

router = APIRouter(prefix="/api/charts", tags=["charts"])


@router.get("", response_model=schemas.ChartsResponse)
def charts(vehicle_id: int | None = None, db: Session = Depends(get_db)):
    vid = vehicle_id or get_active_vehicle(db).id
    records = ordered_fillups(db, vid)
    annotated = calculations.annotate_sequence(records)
    tz = _get_timezone(db)

    mpg_points = [
        schemas.ChartSeriesPoint(label=a.record.timestamp.date().isoformat(), value=a.mpg)
        for a in annotated
        if a.mpg is not None
    ]
    price_points = [
        schemas.ChartSeriesPoint(label=a.record.timestamp.date().isoformat(), value=a.record.price_per_gallon)
        for a in annotated
        if a.record.price_per_gallon is not None
    ]

    monthly_spend: dict[str, float] = {}
    monthly_miles: dict[str, float] = {}
    for a in annotated:
        key = _month_key(a.record.timestamp, tz)
        monthly_spend[key] = monthly_spend.get(key, 0.0) + (a.record.fuel_total or 0)
        if a.miles_driven is not None:
            monthly_miles[key] = monthly_miles.get(key, 0.0) + a.miles_driven

    spend_series = [schemas.ChartSeriesPoint(label=k, value=v) for k, v in sorted(monthly_spend.items())]
    miles_series = [schemas.ChartSeriesPoint(label=k, value=v) for k, v in sorted(monthly_miles.items())]

    return schemas.ChartsResponse(
        mpg_over_time=mpg_points,
        price_over_time=price_points,
        monthly_spend=spend_series,
        monthly_miles=miles_series,
    )
