# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1: build the frontend (Vite/React PWA) as static assets
# ---------------------------------------------------------------------------
FROM node:20-alpine AS frontend-build
WORKDIR /frontend
COPY src/frontend/package.json src/frontend/package-lock.json ./
RUN npm ci
COPY src/frontend ./
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 2: production runtime -- Python + FastAPI + local Tesseract OCR
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/data \
    STATIC_DIR=/app/static \
    PORT=8080

# tesseract-ocr: local, free, CPU-only OCR engine (no GPU, no network calls)
# libgl1/libglib2.0-0: runtime libs required by opencv-python-headless
# curl: used by the container HEALTHCHECK
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY src/backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY src/backend/app ./app
COPY --from=frontend-build /frontend/dist ./static

COPY docker/entrypoint.sh /entrypoint.sh
# Build-time placeholder user/group -- entrypoint.sh remaps this to
# PUID/PGID (default 99/100, matching Unraid's nobody:users) at container
# start, so the exact IDs picked here don't matter as long as they're free.
RUN chmod +x /entrypoint.sh \
    && groupadd -g 1000 odo \
    && useradd -u 1000 -g 1000 -d /app -s /sbin/nologin odo \
    && mkdir -p /data/photos /data/thumbnails \
    && chown -R odo:odo /app /data

VOLUME ["/data"]
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8080/api/healthz || exit 1

ENTRYPOINT ["/entrypoint.sh"]
# uvicorn's default signal handling already shuts down gracefully on SIGTERM.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
