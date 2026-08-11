"""Application configuration.

Everything is environment-driven so the container needs zero configuration
files to start. All persistent state lives under DATA_DIR (default /data).
"""
from __future__ import annotations

import os
from pathlib import Path


class Settings:
    def __init__(self) -> None:
        self.data_dir = Path(os.environ.get("DATA_DIR", "/data"))
        self.photos_dir = self.data_dir / "photos"
        self.thumbnails_dir = self.data_dir / "thumbnails"
        self.db_path = self.data_dir / "odo.db"
        self.database_url = os.environ.get(
            "DATABASE_URL", f"sqlite:///{self.db_path.as_posix()}"
        )
        self.timezone = os.environ.get("TZ", "UTC")
        self.static_dir = Path(
            os.environ.get("STATIC_DIR", Path(__file__).resolve().parent.parent / "static")
        )
        self.ocr_engine = os.environ.get("OCR_ENGINE", "tesseract")
        self.max_upload_mb = int(os.environ.get("MAX_UPLOAD_MB", "20"))
        self.thumbnail_max_px = int(os.environ.get("THUMBNAIL_MAX_PX", "480"))

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.photos_dir.mkdir(parents=True, exist_ok=True)
        self.thumbnails_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
