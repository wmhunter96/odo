"""Photo storage.

Originals are always written byte-for-byte as uploaded and never discarded
or re-encoded. A separate, smaller thumbnail is generated for list/dashboard
use. Layout under DATA_DIR:

    photos/<yyyy>/<mm>/<fillup-id>/odometer.jpg
    photos/<yyyy>/<mm>/<fillup-id>/receipt.jpg
    thumbnails/<yyyy>/<mm>/<fillup-id>/odometer.jpg
    thumbnails/<yyyy>/<mm>/<fillup-id>/receipt.jpg
"""
from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageOps

from .config import settings


def _relative_dir(timestamp: datetime, fillup_id: int) -> Path:
    return Path(f"{timestamp.year:04d}") / f"{timestamp.month:02d}" / str(fillup_id)


def photo_paths(timestamp: datetime, fillup_id: int) -> tuple[Path, Path]:
    """Returns (original_dir, thumbnail_dir) absolute paths, creating them."""
    rel = _relative_dir(timestamp, fillup_id)
    original_dir = settings.photos_dir / rel
    thumb_dir = settings.thumbnails_dir / rel
    original_dir.mkdir(parents=True, exist_ok=True)
    thumb_dir.mkdir(parents=True, exist_ok=True)
    return original_dir, thumb_dir


def save_photo(data: bytes, timestamp: datetime, fillup_id: int, kind: str) -> str:
    """kind: 'odometer' | 'receipt'. Returns the path stored on the FillUp
    record, relative to DATA_DIR, so it survives DATA_DIR being remounted
    at a different host path."""
    original_dir, thumb_dir = photo_paths(timestamp, fillup_id)
    filename = f"{kind}.jpg"

    original_path = original_dir / filename
    original_path.write_bytes(data)

    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img).convert("RGB")
        img.thumbnail((settings.thumbnail_max_px, settings.thumbnail_max_px))
        img.save(thumb_dir / filename, "JPEG", quality=80)
    except Exception:
        # Thumbnail generation is best-effort; the original is what matters.
        pass

    rel_path = original_path.relative_to(settings.data_dir).as_posix()
    return rel_path


def resolve_photo(relative_path: str) -> Path:
    return settings.data_dir / relative_path


def resolve_thumbnail(relative_path: str) -> Path:
    """Given the original's relative path (under photos/...), return the
    matching thumbnail path (under thumbnails/...), falling back to the
    original if no thumbnail was generated."""
    rel = Path(relative_path)
    if rel.parts and rel.parts[0] == "photos":
        thumb_rel = Path("thumbnails", *rel.parts[1:])
        thumb_path = settings.data_dir / thumb_rel
        if thumb_path.exists():
            return thumb_path
    return settings.data_dir / relative_path


def delete_fillup_photos(timestamp: datetime, fillup_id: int) -> None:
    import shutil

    rel = _relative_dir(timestamp, fillup_id)
    for base in (settings.photos_dir, settings.thumbnails_dir):
        d = base / rel
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
