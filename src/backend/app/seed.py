from __future__ import annotations

from sqlalchemy.orm import Session

from .models import Setting, Vehicle

DEFAULT_SETTINGS = {
    "theme": "system",
    "timezone": "UTC",
    "ocr_engine": "tesseract",
    # Off by default: the one setting that, when enabled, sends data
    # (the OCR'd receipt address) to an external service (OpenStreetMap
    # Nominatim) -- see app/geocode.py. Everything else in Odo works
    # fully offline regardless of this setting.
    "geocode_enabled": "false",
}


def seed_defaults(db: Session) -> None:
    if db.query(Vehicle).count() == 0:
        db.add(
            Vehicle(
                name="2025 Toyota Corolla Hybrid LE",
                year=2025,
                make="Toyota",
                model="Corolla Hybrid",
                trim="LE",
                is_active=True,
            )
        )

    existing_keys = {k for (k,) in db.query(Setting.key).all()}
    for key, value in DEFAULT_SETTINGS.items():
        if key not in existing_keys:
            db.add(Setting(key=key, value=value))

    db.commit()
