from __future__ import annotations

from sqlalchemy.orm import Session

from .models import Setting, Vehicle

DEFAULT_SETTINGS = {
    "theme": "system",
    "timezone": "UTC",
    "ocr_engine": "paddleocr",
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
