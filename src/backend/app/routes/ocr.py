from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .. import calculations, validation
from ..config import settings as app_settings
from ..db import get_db
from ..deps import get_active_vehicle
from ..ocr import get_provider
from ..ocr.odometer_parser import parse_odometer
from ..ocr.preprocess import (
    MIN_RECEIPT_WIDTH,
    WIDE_RECEIPT_WIDTH,
    crop_receipt_from_bytes,
    prepare_for_ocr,
    prepare_receipt_variant,
)
from ..ocr.receipt_parser import parse_receipt
from ..schemas import DuplicateCandidateOut, OCRProcessResponse, WarningsOut
from .fillups import ordered_fillups

router = APIRouter(prefix="/api/ocr", tags=["ocr"])

MAX_UPLOAD_BYTES = app_settings.max_upload_mb * 1024 * 1024


async def _read_upload(upload: UploadFile) -> bytes:
    data = await upload.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"Image exceeds {app_settings.max_upload_mb}MB limit")
    if not data:
        raise HTTPException(status_code=400, detail="Empty file upload")
    return data


@router.post("/process", response_model=OCRProcessResponse)
async def process_ocr(
    odometer_image: UploadFile = File(...),
    receipt_image: UploadFile = File(...),
    vehicle_id: int | None = None,
    db: Session = Depends(get_db),
):
    from ..models import Vehicle

    vehicle_obj: Vehicle = db.get(Vehicle, vehicle_id) if vehicle_id else get_active_vehicle(db)
    if vehicle_obj is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    provider = get_provider(app_settings.ocr_engine)

    odometer_bytes = await _read_upload(odometer_image)
    receipt_bytes = await _read_upload(receipt_image)

    recent = ordered_fillups(db, vehicle_obj.id)
    previous_odometer = recent[-1].odometer if recent else None
    historical_mpgs = [a.mpg for a in calculations.annotate_sequence(recent) if a.mpg is not None]

    odo_img = prepare_for_ocr(odometer_bytes, mode="odometer")
    odo_ocr = provider.read(odo_img)
    odo_result = parse_odometer(odo_ocr, previous_odometer=previous_odometer)

    # Primary pass: tuned via a grid search against a real receipt (scored
    # against its known-correct manual transcription) for gallons/price/
    # total/date -- see preprocess.MIN_RECEIPT_WIDTH. --psm 4 ("a single
    # column of variable-size text") beat the default full-page mode (3)
    # and the uniform-block mode (6) there.
    cropped_receipt = crop_receipt_from_bytes(receipt_bytes)
    receipt_img = prepare_receipt_variant(cropped_receipt, MIN_RECEIPT_WIDTH)
    receipt_ocr = provider.read(receipt_img, config="--psm 4")
    receipt_result = parse_receipt(receipt_ocr)

    # A wider crop recovers small punctuation (a zip code's digits, in
    # particular) more reliably in the same grid search, but usually at
    # the cost of losing the exact time-of-day -- worth the extra OCR pass
    # only when the primary pass didn't find an address at all.
    if receipt_result.station_address is None:
        wide_img = prepare_receipt_variant(cropped_receipt, WIDE_RECEIPT_WIDTH)
        wide_ocr = provider.read(wide_img, config="--psm 4")
        wide_result = parse_receipt(wide_ocr)
        receipt_result.station_address = wide_result.station_address
        if wide_result.raw_text:
            receipt_result.raw_text = (
                f"{receipt_result.raw_text}\n\n--- wider pass, address recovery ---\n\n{wide_result.raw_text}"
            )

    gallons, price_per_gallon, fuel_total = validation.derive_missing_fuel_value(
        receipt_result.gallons, receipt_result.price_per_gallon, receipt_result.fuel_total
    )

    derived = calculations.derive(previous_odometer, odo_result.value or 0.0, gallons, fuel_total)
    miles = derived.miles_driven if odo_result.value is not None else None
    mpg = derived.mpg if odo_result.value is not None else None
    cpm = derived.cost_per_mile if odo_result.value is not None else None

    fuel_warnings = validation.fuel_field_warnings(
        original={
            "gallons": receipt_result.gallons,
            "price_per_gallon": receipt_result.price_per_gallon,
            "fuel_total": receipt_result.fuel_total,
        },
        final={"gallons": gallons, "price_per_gallon": price_per_gallon, "fuel_total": fuel_total},
    )

    warnings = WarningsOut(
        odometer=validation.check_odometer(previous_odometer, odo_result.value) if odo_result.value is not None else None,
        mpg=validation.check_mpg(mpg, historical_mpgs),
        fuel_math=validation.check_fuel_math(gallons, price_per_gallon, fuel_total),
        # fuel_warnings covers gallons/price/total, distinguishing "found
        # directly" / "derived from the other two" / "still missing".
        # receipt_result.warnings covers date/time, which has no such
        # derivation fallback. Surfacing these is what makes a
        # silently-defaulted field (like today's date when none was found)
        # visibly different from an actually-read one.
        receipt_fields=fuel_warnings + receipt_result.warnings,
    )

    candidate = {
        "odometer": odo_result.value,
        "gallons": gallons,
        "fuel_total": fuel_total,
        "timestamp": receipt_result.timestamp,
    }
    dupes = validation.find_duplicates(candidate, recent[-25:])

    return OCRProcessResponse(
        odometer_value=odo_result.value,
        odometer_confidence=odo_result.confidence,
        odometer_raw_text=odo_result.raw_text,
        odometer_candidates=[c.value for c in odo_result.candidates],
        gallons=gallons,
        price_per_gallon=price_per_gallon,
        fuel_total=fuel_total,
        station_brand=receipt_result.station_brand,
        station_address=receipt_result.station_address,
        timestamp=receipt_result.timestamp,
        receipt_raw_text=receipt_result.raw_text,
        previous_odometer=previous_odometer,
        miles_driven=miles,
        mpg=mpg,
        cost_per_mile=cpm,
        warnings=warnings,
        duplicates=[
            DuplicateCandidateOut(
                id=d.id,
                timestamp=d.timestamp,
                odometer=d.odometer,
                gallons=d.gallons,
                fuel_total=d.fuel_total,
                station_brand=d.station_brand,
            )
            for d in dupes
        ],
    )
