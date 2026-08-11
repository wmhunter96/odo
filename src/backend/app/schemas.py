from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class VehicleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    year: int | None = None
    make: str | None = None
    model: str | None = None
    trim: str | None = None
    is_active: bool


class VehicleUpdate(BaseModel):
    name: str | None = None
    year: int | None = None
    make: str | None = None
    model: str | None = None
    trim: str | None = None


class FillUpOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    vehicle_id: int
    timestamp: datetime
    odometer: float
    gallons: float
    price_per_gallon: float | None
    fuel_total: float | None
    station_brand: str | None
    station_address: str | None
    latitude: float | None
    longitude: float | None
    odometer_photo_path: str | None
    receipt_photo_path: str | None
    raw_odometer_ocr: str | None
    raw_receipt_ocr: str | None
    ocr_confidence: float | None
    notes: str | None
    source: str

    # Derived, computed fresh from source values -- never stored.
    previous_odometer: float | None = None
    miles_driven: float | None = None
    mpg: float | None = None
    cost_per_mile: float | None = None


class FillUpUpdate(BaseModel):
    timestamp: datetime | None = None
    odometer: float | None = None
    gallons: float | None = None
    price_per_gallon: float | None = None
    fuel_total: float | None = None
    station_brand: str | None = None
    station_address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    notes: str | None = None


class WarningsOut(BaseModel):
    odometer: str | None = None
    mpg: str | None = None
    fuel_math: str | None = None
    # Field-level "couldn't find this on the receipt at all" notices from
    # the parser itself (as opposed to the sanity checks above, which
    # assume a value but think it looks wrong).
    receipt_fields: list[str] = []


class DuplicateCandidateOut(BaseModel):
    id: int
    timestamp: datetime
    odometer: float
    gallons: float
    fuel_total: float | None
    station_brand: str | None


class OCRProcessResponse(BaseModel):
    odometer_value: float | None
    odometer_confidence: float
    odometer_raw_text: str
    odometer_candidates: list[float]

    gallons: float | None
    price_per_gallon: float | None
    fuel_total: float | None
    station_brand: str | None
    station_address: str | None
    timestamp: datetime | None
    receipt_raw_text: str

    previous_odometer: float | None
    miles_driven: float | None
    mpg: float | None
    cost_per_mile: float | None

    warnings: WarningsOut
    duplicates: list[DuplicateCandidateOut]


class DashboardStats(BaseModel):
    last_fillup: FillUpOut | None
    month_spend: float
    month_miles: float
    month_mpg: float | None
    lifetime_average_mpg: float | None
    lifetime_mpg: float | None
    lifetime_total_miles: float
    lifetime_total_fuel_cost: float
    lifetime_average_price: float | None


class LifetimeStats(BaseModel):
    most_recent_mpg: float | None
    average_mpg: float | None
    lifetime_mpg: float | None
    average_fuel_price: float | None
    total_gallons: float
    total_fuel_cost: float
    total_miles: float
    current_month_spend: float
    current_month_miles: float
    average_monthly_spend: float | None
    average_monthly_miles: float | None
    cost_per_mile: float | None


class ChartSeriesPoint(BaseModel):
    label: str
    value: float


class ChartsResponse(BaseModel):
    mpg_over_time: list[ChartSeriesPoint]
    price_over_time: list[ChartSeriesPoint]
    monthly_spend: list[ChartSeriesPoint]
    monthly_miles: list[ChartSeriesPoint]


class ImportRowOut(BaseModel):
    row_number: int
    odometer: float | None
    timestamp: datetime | None
    gallons: float | None
    price_per_gallon: float | None
    fuel_total: float | None
    station_address: str | None
    station_brand: str | None
    miles_driven: float | None
    mpg: float | None
    cost_per_mile: float | None
    is_duplicate_in_file: bool
    is_valid: bool
    errors: list[str]


class ImportPreviewResponse(BaseModel):
    total: int
    valid: int
    errors: int
    rows: list[ImportRowOut]


class ImportCommitResponse(BaseModel):
    imported: int
    skipped: int


class SettingsOut(BaseModel):
    theme: str = "system"
    timezone: str = "UTC"
    ocr_engine: str = "tesseract"


class SettingsUpdate(BaseModel):
    theme: str | None = None
    timezone: str | None = None
    ocr_engine: str | None = None
