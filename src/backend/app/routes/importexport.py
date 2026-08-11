from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .. import csv_export, csv_import, schemas
from ..db import get_db
from ..deps import get_active_vehicle
from ..models import FillUp, Vehicle
from .fillups import ordered_fillups

router = APIRouter(tags=["import-export"])


async def _read_csv_text(file: UploadFile) -> str:
    raw = await file.read()
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise HTTPException(status_code=400, detail="Could not decode CSV file as text")


def _row_to_schema(row: csv_import.ImportRow) -> schemas.ImportRowOut:
    return schemas.ImportRowOut(
        row_number=row.row_number,
        odometer=row.odometer,
        timestamp=row.timestamp,
        gallons=row.gallons,
        price_per_gallon=row.price_per_gallon,
        fuel_total=row.fuel_total,
        station_address=row.station_address,
        station_brand=row.station_brand,
        miles_driven=row.miles_driven,
        mpg=row.mpg,
        cost_per_mile=row.cost_per_mile,
        is_duplicate_in_file=row.is_duplicate_in_file,
        is_valid=row.is_valid,
        errors=row.errors,
    )


@router.post("/api/import/csv/preview", response_model=schemas.ImportPreviewResponse)
async def preview_import(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await _read_csv_text(file)
    try:
        summary = csv_import.import_preview(content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return schemas.ImportPreviewResponse(
        total=summary.total,
        valid=summary.valid,
        errors=summary.errors,
        rows=[_row_to_schema(r) for r in summary.rows],
    )


@router.post("/api/import/csv/commit", response_model=schemas.ImportCommitResponse)
async def commit_import(
    file: UploadFile = File(...),
    vehicle_id: int | None = None,
    db: Session = Depends(get_db),
):
    content = await _read_csv_text(file)
    try:
        rows = csv_import.parse_csv(content)
        rows = csv_import.recalculate(rows)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    vehicle = db.get(Vehicle, vehicle_id) if vehicle_id else get_active_vehicle(db)

    imported = 0
    skipped = 0
    for row in rows:
        if not row.is_valid:
            skipped += 1
            continue
        db.add(
            FillUp(
                vehicle_id=vehicle.id,
                timestamp=row.timestamp,
                odometer=row.odometer,
                gallons=row.gallons,
                price_per_gallon=row.price_per_gallon,
                fuel_total=row.fuel_total,
                station_brand=row.station_brand,
                station_address=row.station_address,
                odometer_photo_path=None,
                receipt_photo_path=None,
                source="import",
            )
        )
        imported += 1
    db.commit()

    return schemas.ImportCommitResponse(imported=imported, skipped=skipped)


@router.get("/api/export/csv")
def export_csv(vehicle_id: int | None = None, db: Session = Depends(get_db)):
    vid = vehicle_id or get_active_vehicle(db).id
    records = ordered_fillups(db, vid)
    content = csv_export.export_csv(records)
    return StreamingResponse(
        iter([content]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=odo-export.csv"},
    )
