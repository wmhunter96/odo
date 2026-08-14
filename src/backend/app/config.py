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
        self.ocr_engine = os.environ.get("OCR_ENGINE", "paddleocr")
        self.max_upload_mb = int(os.environ.get("MAX_UPLOAD_MB", "20"))
        self.thumbnail_max_px = int(os.environ.get("THUMBNAIL_MAX_PX", "480"))
        # Baked into the image at build time (see Dockerfile /
        # docker-publish.yml) so a running container can report exactly
        # which commit it's built from -- the one unambiguous way to tell
        # whether an update actually landed, independent of any URL/CDN/
        # browser caching elsewhere (e.g. the Unraid template icon).
        self.git_sha = os.environ.get("GIT_SHA", "unknown")
        self.build_date = os.environ.get("BUILD_DATE", "unknown")

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.photos_dir.mkdir(parents=True, exist_ok=True)
        self.thumbnails_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
