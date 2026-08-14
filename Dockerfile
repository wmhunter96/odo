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
# Stage 2: production runtime -- Python + FastAPI + local PaddleOCR
#
# Two separate local models, not one: PP-OCRv6 (odometer photo -- read one
# number off a dashboard display) and PaddleOCR-VL-1.6 (receipt photo -- a
# 0.9B vision-language document model asked directly for the receipt's
# fields as JSON, see receipt_vlm.py). Both run entirely on CPU with no
# network access at runtime; this makes for a noticeably larger image and
# a noticeably slower build than a single conventional OCR engine would,
# which is the deliberate tradeoff for the VL model's much better real-
# world-photo robustness on the receipt side specifically.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

# Baked in at build time (see .github/workflows/docker-publish.yml) so a
# running container can report exactly which commit it was built from via
# /api/healthz -- otherwise there's no reliable way to tell whether an
# Unraid container actually picked up a given push versus still running an
# older image, short of guessing from behavior.
ARG GIT_SHA=unknown
ARG BUILD_DATE=unknown

# PADDLE_PDX_CACHE_HOME (below) is where PaddleX caches downloaded model
# weights -- set explicitly rather than relying on its own default of
# "~/.paddlex", so the build-time model download further down and the
# runtime read of it both land in the same place regardless of $HOME, and
# so it falls under the `chown -R odo:odo /app` near the bottom without a
# separate rule.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/data \
    STATIC_DIR=/app/static \
    PORT=8080 \
    GIT_SHA=${GIT_SHA} \
    BUILD_DATE=${BUILD_DATE} \
    PADDLE_PDX_CACHE_HOME=/app/.paddlex

# libgl1/libsm6/libxext6/libxrender1: runtime libs opencv-contrib-python
# (pulled in by paddleocr -- see requirements.txt) links against even
# though nothing here ever opens a GUI window; it's built as a full,
# non-headless OpenCV, unlike the opencv-python-headless this replaced.
# libgomp1: OpenMP, used by paddlepaddle's CPU inference kernels.
# curl: used by the container HEALTHCHECK.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libsm6 \
        libxext6 \
        libxrender1 \
        libgomp1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY src/backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download every PP-OCRv6 pipeline sub-model (document orientation
# classification, document unwarping, text detection, text-line
# orientation, text recognition) at build time, into
# PADDLE_PDX_CACHE_HOME above -- so the running container never needs
# network access to do OCR, the same guarantee Tesseract's baked-in
# traineddata gave (see git history) before this engine swap. Building
# the pipeline AND running one prediction (not just importing the
# package) is what actually forces every sub-model to be fetched --
# some only load their weights lazily on first real inference call
# rather than at construction, and skipping the predict() call here
# would silently leave those to download on the container's first real
# request instead, defeating the point.
RUN python -c "import numpy as np; from paddleocr import PaddleOCR; ocr = PaddleOCR(lang='en', ocr_version='PP-OCRv6', use_doc_orientation_classify=True, use_doc_unwarping=True, use_textline_orientation=True); ocr.predict(np.full((64, 64, 3), 255, dtype=np.uint8))"

# Same idea, second model: pre-download PaddleOCR-VL-1.6's weights (see
# receipt_vlm.py -- MODEL_NAME must match this string exactly). A tiny
# blank image and a short max_new_tokens are enough to force the download
# and a real forward pass without spending meaningful build time actually
# generating text -- this step exists purely to warm the weight cache, not
# to validate output quality.
RUN python -c "import numpy as np; from PIL import Image; from paddleocr import DocUnderstanding; Image.fromarray(np.full((64, 64, 3), 255, dtype=np.uint8)).save('/tmp/warm.jpg'); doc = DocUnderstanding(doc_understanding_model_name='PaddleOCR-VL-1.6-0.9B'); doc.predict({'image': '/tmp/warm.jpg', 'query': 'Say OK.'}, max_new_tokens=8); import os; os.remove('/tmp/warm.jpg')"

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
