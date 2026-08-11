from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Vehicle(Base):
    """A tracked vehicle. V1 uses a single active vehicle, but every fill-up
    is scoped to a vehicle_id so multi-vehicle support is a additive change
    later, not a schema redesign."""

    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    make: Mapped[str | None] = mapped_column(String(80), nullable=True)
    model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    trim: Mapped[str | None] = mapped_column(String(80), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    fillups: Mapped[list["FillUp"]] = relationship(
        back_populates="vehicle", cascade="all, delete-orphan"
    )


class FillUp(Base):
    """A single fuel fill-up. Derived values (miles_driven, mpg,
    cost_per_mile) are intentionally NOT stored here -- they're computed from
    source values against the vehicle's ordered fill-up sequence so editing a
    historical record can never leave stale calculations behind."""

    __tablename__ = "fillups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), index=True)

    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    odometer: Mapped[float] = mapped_column(Float)
    gallons: Mapped[float] = mapped_column(Float)
    price_per_gallon: Mapped[float | None] = mapped_column(Float, nullable=True)
    fuel_total: Mapped[float | None] = mapped_column(Float, nullable=True)

    station_brand: Mapped[str | None] = mapped_column(String(120), nullable=True)
    station_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    odometer_photo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    receipt_photo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    raw_odometer_ocr: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_receipt_ocr: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # "ocr" | "manual" | "import"
    source: Mapped[str] = mapped_column(String(20), default="manual")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    vehicle: Mapped["Vehicle"] = relationship(back_populates="fillups")


class Setting(Base):
    """Simple key/value application settings store (theme, timezone, ocr
    engine, etc). Deliberately not a config file so it survives container
    recreation via the same /data volume as everything else."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
