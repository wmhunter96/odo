from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import calculations, photos, schemas, validation
from ..config import settings as app_settings
from ..db import get_db
from ..deps import get_active_vehicle
from ..models import FillUp, Vehicle

router = APIRouter(prefix="/api/fillups", tags=["fillups"])


def ordered_fillups(db: Session, vehicle_id: int) -> list[FillUp]:
    return (
        db.query(FillUp)
        .filter(FillUp.vehicle_id == vehicle_id)
        .order_by(FillUp.timestamp.asc(), FillUp.id.asc())
        .all()
    )


def _to_out(annotated: calculations.AnnotatedFillUp) -> schemas.FillUpOut:
    f = annotated.record
    out = schemas.FillUpOut.model_validate(f)
    out.previous_odometer = annotated.previous_odometer
    out.miles_driven = annotated.miles_driven
    out.mpg = annotated.mpg
    out.cost_per_mile = annotated.cost_per_mile
    return out


@router.get("", response_model=list[schemas.FillUpOut])
def list_fillups(
    vehicle_id: int | None = None,
    limit: int = 500,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    vid = vehicle_id or get_active_vehicle(db).id
    records = ordered_fillups(db, vid)
    annotated = calculations.annotate_sequence(records)
    # Most recent first for the UI, but computed against chronological order.
    annotated.reverse()
    page = annotated[offset : offset + limit]
    return [_to_out(a) for a in page]


@router.get("/{fillup_id}", response_model=schemas.FillUpOut)
def get_fillup(fillup_id: int, db: Session = Depends(get_db)):
    f = db.get(FillUp, fillup_id)
    if f is None:
        raise HTTPException(status_code=404, detail="Fill-up not found")
    records = ordered_fillups(db, f.vehicle_id)
    annotated = calculations.annotate_sequence(records)
    match = next(a for a in annotated if a.record.id == fillup_id)
    return _to_out(match)


@router.post("/check-duplicate", response_model=list[schemas.DuplicateCandidateOut])
def check_duplicate(
    odometer: float | None = None,
    gallons: float | None = None,
    fuel_total: float | None = None,
    timestamp: datetime | None = None,
    vehicle_id: int | None = None,
    exclude_id: int | None = None,
    db: Session = Depends(get_db),
):
    vid = vehicle_id or get_active_vehicle(db).id
    recent = ordered_fillups(db, vid)[-25:]
    if exclude_id is not None:
        recent = [r for r in recent if r.id != exclude_id]
    candidate = {"odometer": odometer, "gallons": gallons, "fuel_total": fuel_total, "timestamp": timestamp}
    return validation.find_duplicates(candidate, recent)


@router.post("", response_model=schemas.FillUpOut, status_code=201)
def create_fillup(
    timestamp: datetime = Form(...),
    odometer: float = Form(...),
    gallons: float = Form(...),
    price_per_gallon: float | None = Form(None),
    fuel_total: float | None = Form(None),
    station_brand: str | None = Form(None),
    station_address: str | None = Form(None),
    latitude: float | None = Form(None),
    longitude: float | None = Form(None),
    notes: str | None = Form(None),
    raw_odometer_ocr: str | None = Form(None),
    raw_receipt_ocr: str | None = Form(None),
    ocr_confidence: float | None = Form(None),
    source: str = Form("manual"),
    vehicle_id: int | None = Form(None),
    odometer_photo: UploadFile | None = File(None),
    receipt_photo: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    vehicle: Vehicle = db.get(Vehicle, vehicle_id) if vehicle_id else get_active_vehicle(db)
    if vehicle is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    gallons, price_per_gallon, fuel_total = validation.derive_missing_fuel_value(
        gallons, price_per_gallon, fuel_total
    )

    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    fillup = FillUp(
        vehicle_id=vehicle.id,
        timestamp=timestamp,
        odometer=odometer,
        gallons=gallons,
        price_per_gallon=price_per_gallon,
        fuel_total=fuel_total,
        station_brand=station_brand,
        station_address=station_address,
        latitude=latitude,
        longitude=longitude,
        notes=notes,
        raw_odometer_ocr=raw_odometer_ocr,
        raw_receipt_ocr=raw_receipt_ocr,
        ocr_confidence=ocr_confidence,
        source=source,
    )
    db.add(fillup)
    db.commit()
    db.refresh(fillup)

    if odometer_photo is not None and odometer_photo.filename:
        data = odometer_photo.file.read()
        fillup.odometer_photo_path = photos.save_photo(data, fillup.timestamp, fillup.id, "odometer")
    if receipt_photo is not None and receipt_photo.filename:
        data = receipt_photo.file.read()
        fillup.receipt_photo_path = photos.save_photo(data, fillup.timestamp, fillup.id, "receipt")
    db.commit()
    db.refresh(fillup)

    records = ordered_fillups(db, fillup.vehicle_id)
    annotated = calculations.annotate_sequence(records)
    match = next(a for a in annotated if a.record.id == fillup.id)
    return _to_out(match)


@router.patch("/{fillup_id}", response_model=schemas.FillUpOut)
def update_fillup(fillup_id: int, payload: schemas.FillUpUpdate, db: Session = Depends(get_db)):
    f = db.get(FillUp, fillup_id)
    if f is None:
        raise HTTPException(status_code=404, detail="Fill-up not found")
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(f, field, value)
    db.commit()
    db.refresh(f)

    records = ordered_fillups(db, f.vehicle_id)
    annotated = calculations.annotate_sequence(records)
    match = next(a for a in annotated if a.record.id == fillup_id)
    return _to_out(match)


@router.delete("/{fillup_id}", status_code=204)
def delete_fillup(fillup_id: int, db: Session = Depends(get_db)):
    f = db.get(FillUp, fillup_id)
    if f is None:
        raise HTTPException(status_code=404, detail="Fill-up not found")
    photos.delete_fillup_photos(f.timestamp, f.id)
    db.delete(f)
    db.commit()
    return None


@router.get("/{fillup_id}/photo/{kind}")
def get_photo(fillup_id: int, kind: str, thumbnail: bool = False, db: Session = Depends(get_db)):
    if kind not in ("odometer", "receipt"):
        raise HTTPException(status_code=400, detail="kind must be 'odometer' or 'receipt'")
    f = db.get(FillUp, fillup_id)
    if f is None:
        raise HTTPException(status_code=404, detail="Fill-up not found")
    rel_path = f.odometer_photo_path if kind == "odometer" else f.receipt_photo_path
    if not rel_path:
        raise HTTPException(status_code=404, detail="No photo stored for this fill-up")
    path = photos.resolve_thumbnail(rel_path) if thumbnail else photos.resolve_photo(rel_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Photo file missing on disk")
    return FileResponse(path)
