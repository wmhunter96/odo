from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .models import Vehicle


def get_active_vehicle(db: Session) -> Vehicle:
    vehicle = (
        db.query(Vehicle).filter(Vehicle.is_active.is_(True)).order_by(Vehicle.id).first()
    )
    if vehicle is None:
        vehicle = db.query(Vehicle).order_by(Vehicle.id).first()
    if vehicle is None:
        raise HTTPException(status_code=500, detail="No vehicle configured")
    return vehicle
