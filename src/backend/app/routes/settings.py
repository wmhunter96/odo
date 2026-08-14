from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import schemas
from ..config import settings as app_settings
from ..db import get_db
from ..models import Setting

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _get(db: Session, key: str, default: str) -> str:
    row = db.get(Setting, key)
    return row.value if row else default


def _set(db: Session, key: str, value: str) -> None:
    row = db.get(Setting, key)
    if row is None:
        db.add(Setting(key=key, value=value))
    else:
        row.value = value


@router.get("", response_model=schemas.SettingsOut)
def get_settings(db: Session = Depends(get_db)):
    return schemas.SettingsOut(
        theme=_get(db, "theme", "system"),
        timezone=_get(db, "timezone", "UTC"),
        # Reported straight from the actual running config (env-driven,
        # see config.py), not the DB-stored copy below -- the OCR engine
        # is a deployment choice, not a per-user preference (the dropdown
        # this feeds is disabled/read-only in the UI), so there's no
        # reason for it to ever drift from what's actually running. A
        # value already stored in an existing installation's DB from
        # before this engine swap (a leftover "tesseract") would otherwise
        # keep displaying as such indefinitely despite PaddleOCR actually
        # being the one processing every photo.
        ocr_engine=app_settings.ocr_engine,
    )


@router.patch("", response_model=schemas.SettingsOut)
def update_settings(payload: schemas.SettingsUpdate, db: Session = Depends(get_db)):
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        if value is not None:
            _set(db, key, str(value))
    db.commit()
    return get_settings(db)


@router.get("/backup-info")
def backup_info():
    data_dir = app_settings.data_dir
    db_size = app_settings.db_path.stat().st_size if app_settings.db_path.exists() else 0
    photo_count = sum(1 for _ in app_settings.photos_dir.rglob("*.jpg")) if app_settings.photos_dir.exists() else 0
    photos_size = (
        sum(f.stat().st_size for f in app_settings.photos_dir.rglob("*.jpg"))
        if app_settings.photos_dir.exists()
        else 0
    )
    return {
        "data_dir": str(data_dir),
        "database_size_bytes": db_size,
        "photo_count": photo_count,
        "photos_size_bytes": photos_size,
        "note": "Backing up the entire /data directory is sufficient to restore Odo completely.",
    }
