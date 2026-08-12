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

# Baked in at build time (see .github/workflows/docker-publish.yml) so a
# running container can report exactly which commit it was built from via
# /api/healthz -- otherwise there's no reliable way to tell whether an
# Unraid container actually picked up a given push versus still running an
# older image, short of guessing from behavior.
ARG GIT_SHA=unknown
ARG BUILD_DATE=unknown

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/data \
    STATIC_DIR=/app/static \
    PORT=8080 \
    GIT_SHA=${GIT_SHA} \
    BUILD_DATE=${BUILD_DATE} \
    TESSDATA_PREFIX=/usr/share/tessdata-best

# tesseract-ocr: local, free, CPU-only OCR engine (no GPU, no network calls
# at runtime -- the traineddata download below happens at build time, same
# as pip/npm installs).
# libgl1/libglib2.0-0/libgomp1: runtime libs required by opencv-python-headless
# curl: used by the container HEALTHCHECK, and to fetch the traineddata below
#
# apt's tesseract-ocr-eng ships Google's "fast" (integer-quantized) English
# model, optimized for throughput over accuracy. This app runs OCR at most a
# few times a minute (one fill-up at a time, by a human standing at a gas
# pump), so accuracy matters far more than shaving milliseconds -- replaced
# with Google's "best" (float, higher-accuracy) model instead. Confirmed
# directly against a real receipt: "best" correctly read a house number
# ("1004") that "fast" consistently misread as "4004" across every
# preprocessing variant tried (crop, upscale, contrast, sharpen, whitelist).
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
        curl \
    && mkdir -p "$TESSDATA_PREFIX" \
    && curl -fsSL -o "$TESSDATA_PREFIX/eng.traineddata" \
        https://github.com/tesseract-ocr/tessdata_best/raw/main/eng.traineddata \
    && chmod 644 "$TESSDATA_PREFIX/eng.traineddata" \
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
