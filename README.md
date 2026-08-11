# ⛽ Odo — Gas Tracker

A self-hosted fuel fill-up tracker that turns two photos — your **odometer** and your **gas receipt** — into a complete fill-up record, using OCR that runs entirely on your own hardware.

No paid APIs. No SaaS. No Google Sheets. No cloud OCR. No subscription. No external database server. Everything runs in one Docker container on your own network, backed by SQLite.

> **The goal:** pull into a gas station, fill up, and do this —
> `Open Odo → New Fill-Up → photo of the dashboard → photo of the receipt → review → Looks Good`
> — and get a complete, correct record with both photos kept forever.

---

## Table of Contents

- [What Odo Is](#what-odo-is)
- [Features](#features)
- [Screenshots](#screenshots)
- [How It Works](#how-it-works)
- [Docker Installation](#docker-installation)
- [Unraid Installation](#unraid-installation)
- [Updating](#updating)
- [Backup & Restore](#backup--restore)
- [Historical CSV Import](#historical-csv-import)
- [Development](#development)
- [Architecture](#architecture)
- [License](#license)

---

## What Odo Is

Odo is a small, mobile-first PWA + API for logging vehicle fill-ups without typing. Take a photo of your dashboard and a photo of your receipt; local OCR (Tesseract, running on CPU inside the container) extracts the odometer reading, gallons, price per gallon, fuel total, station, and date. You get one confirmation screen to check the numbers — every field is editable — and one tap to save.

Everything persists under a single `/data` directory: the SQLite database, every original photo (never discarded), and your settings. Back that directory up and you've backed up the entire app.

## Features

### Core Features (MVP)

- 📸 **Two-photo fill-up workflow** — odometer photo → receipt photo → OCR runs automatically → confirm → saved
- 🧠 **Local OCR** — Tesseract running on CPU inside the container, no network calls, swappable behind a provider interface
- 🎯 **Smart odometer parsing** — scores candidate numbers by plausible length, OCR confidence, and closeness to your last reading, instead of grabbing the first/biggest number on the dashboard
- 🧾 **Flexible receipt parsing** — not tied to one station's layout; extracts gallons, price/gal, fuel total, date/time, brand, and address independently
- ➗ **Missing-value derivation** — if two of (gallons, price/gal, total) are known, the third is computed; nothing is invented from a single known value
- ✅ **Validation, never blocking** — flags a lower-than-previous odometer, an MPG far outside your history, or fuel math that doesn't add up, but always lets you save anyway
- 🔁 **Duplicate detection** — warns on likely repeat entries (same odometer/gallons/total/time window) before you save
- 🖼️ **Original photos always kept**, plus a generated thumbnail for fast list views
- 📊 **Dashboard, History, Charts** — last fill-up, monthly and lifetime stats, MPG/price/spend/miles trends
- ✏️ **Fully editable history** — editing a historical odometer reading automatically recalculates the affected interval's miles/MPG/cost-per-mile; nothing is permanently baked in
- 📥📤 **CSV import/export** — import a legacy spreadsheet (see [Historical CSV Import](#historical-csv-import)), export a clean CSV at any time
- 📱 **Installable PWA** — home-screen install on iOS/Android, offline-capable app shell, camera capture input
- 🌗 **Light / Dark / System theme**
- 🐳 **One Docker container**, SQLite, no external services, works with zero internet access

### Future Features (not in v1 — see the project spec for the full list)

- Multiple vehicles, maintenance/oil-change/tire-rotation tracking
- Registration & insurance document storage
- Gas station recognition, mapping, and price history
- Better/alternate local OCR models
- Automatic image compression & station geocoding
- Multiple users / optional authentication

## Screenshots

_Add screenshots here once you've got a few fill-ups logged — dashboard, new fill-up flow, and history all look better with real data than mockups._

| Dashboard | New Fill-Up | History |
| --- | --- | --- |
| _screenshot_ | _screenshot_ | _screenshot_ |

## How It Works

```
Odometer Photo ─┐
                 ├─▶ Preprocess (orient / deskew / grayscale / contrast)
Receipt Photo  ──┘         │
                            ▼
                     Tesseract OCR (local, CPU)
                            │
                            ▼
                  Field Parsers (odometer / receipt)
                            │
                            ▼
                  Validation (odometer, MPG range, fuel math)
                            │
                            ▼
                  Confirmation Screen (everything editable)
                            │
                            ▼
                        SQLite + Photos
```

The OCR engine sits behind a small provider interface (`src/backend/app/ocr/provider.py`) so Tesseract can be swapped for another local/free engine later without touching preprocessing, parsing, or the API.

MPG is never stored — it's always computed as `(current_odometer − previous_odometer) / current_fill-up_gallons` from the vehicle's chronological fill-up sequence, so editing a historical odometer value automatically ripples through to the affected interval.

## Docker Installation

```bash
docker run -d \
  --name odo \
  -p 8080:8080 \
  -v /path/to/appdata/odo:/data \
  -e TZ=America/Chicago \
  ghcr.io/wmhunter96/odo:latest
```

Or with Compose (see [docker-compose.yml](docker-compose.yml)):

```bash
docker compose up -d
```

Then open `http://<host>:8080`.

| Setting | Value |
| --- | --- |
| Image | `ghcr.io/wmhunter96/odo:latest` |
| Port | `8080` (HTTP) |
| Volume | `/data` — database, photos, settings |
| Env `TZ` | IANA timezone, e.g. `America/Chicago` |
| Env `PUID` / `PGID` | Optional; sets file ownership inside `/data` (default `99`/`100`) |

No other configuration is required — on first start, Odo creates the SQLite database, seeds the default vehicle (**2025 Toyota Corolla Hybrid LE**), and is ready to use.

## Unraid Installation

Odo is a first-class Unraid target — it's a normal single container with one bind-mounted data path.

**Option A — Template repository (recommended):**

1. **Docker** tab → **Template Repositories** → add `https://github.com/wmhunter96/Odo` → **Save**.
2. Go to **Apps** (or **Docker** → **Add Container** → template dropdown) and select **Odo**.
3. Confirm the fields below, then **Apply**.

**Option B — Add manually:**

**Docker** → **Add Container**, and set:

| Field | Value |
| --- | --- |
| Repository | `ghcr.io/wmhunter96/odo:latest` |
| Web UI Port | `8080` |
| Path: Container | `/data` |
| Path: Host | `/mnt/user/appdata/odo` |
| Variable: `TZ` | your timezone, e.g. `America/Chicago` |
| Variable: `PUID` | `99` (nobody — Unraid default) |
| Variable: `PGID` | `100` (users — Unraid default) |

One-time setup for a private GHCR image: on GitHub, go to the repo's **Packages** tab → `odo` package → **Package settings** → set visibility to **Public** (only needed once — GHCR packages default to private, and a private image needs a login secret on the Unraid side to pull).

The Unraid template XML is included at [`unraid/odo.xml`](unraid/odo.xml).

## Updating

**Unraid:** the Docker tab (or Community Applications' "Check for Updates") detects new `latest` images automatically — click **Update**. `/data` is untouched.

**Docker CLI:**

```bash
docker pull ghcr.io/wmhunter96/odo:latest
docker stop odo && docker rm odo
docker run -d --name odo -p 8080:8080 -v /path/to/appdata/odo:/data -e TZ=America/Chicago ghcr.io/wmhunter96/odo:latest
```

**Docker Compose:**

```bash
docker compose pull && docker compose up -d
```

In every case, the SQLite database, all photos, and settings live in `/data`, outside the container — recreating or updating the container never touches them.

## Backup & Restore

Everything Odo needs to fully restore is under `/data`:

```
/data/
├── odo.db              ← SQLite database
├── photos/              ← original odometer/receipt photos, full resolution
│   └── <yyyy>/<mm>/<fillup-id>/{odometer,receipt}.jpg
└── thumbnails/           ← generated thumbnails (safe to delete; regenerate on next photo save)
```

**Backup:** stop the container (or just copy live — SQLite handles concurrent reads safely for a simple file-copy backup on a low-write personal app) and copy `/data` (on Unraid: `/mnt/user/appdata/odo`) to your backup destination of choice.

**Restore:** stop the container, replace `/data` with the backed-up copy, start the container. No migration step is required — Odo just needs the directory back in place.

Settings → Data → **Backup Information** shows the current database size and photo count as a quick sanity check.

## Historical CSV Import

Settings → Data → **Import CSV** accepts the exact legacy spreadsheet schema:

```
Odometer, Date, Gallons, Price/Gal, Fuel Total $, Gas Station Address, Brand, Avg MPG
```

You'll see a preview before anything is imported:

```
11 records detected
11 valid
0 errors
```

**Important — the legacy `Avg MPG` column is never imported directly.** In the original spreadsheet that column is shifted one row earlier than the fill-up it actually describes (a spreadsheet-formula artifact). The importer instead:

1. Sorts records chronologically.
2. Keeps `Odometer` and `Gallons` as ground truth.
3. Recomputes MPG for each record from `(this odometer − previous odometer) / this record's gallons`.

The first historical record can never have an MPG (there's no earlier odometer to measure from) — that's expected, not an error.

The importer also:

- Parses mixed date formats (single/double-digit month & day, with or without seconds — e.g. `09/05/2025 6:11:59 PM`, `9/5/2025 6:11:59 PM`, `1/10/2026 12:42:00 PM`) without requiring you to clean the file first.
- Derives whichever of gallons/price-per-gallon/fuel-total is missing when the other two are present.
- Flags rows that can't be parsed instead of failing the whole import.
- Flags likely duplicate rows within the file itself.
- Imports fine with `odometer_photo`/`receipt_photo` left empty — historical rows don't need photos.

This exact behavior is covered by an automated acceptance test — see [`tests/test_csv_import.py`](tests/test_csv_import.py).

## Development

Odo is two projects in one repo: a Python/FastAPI backend and a Vite/React frontend, served together as one container in production.

### Backend

```bash
cd src/backend
python -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

# Tesseract must be installed locally for OCR routes to work outside Docker:
#   macOS:   brew install tesseract
#   Ubuntu:  sudo apt install tesseract-ocr
#   Windows: https://github.com/UB-Mannheim/tesseract/wiki

DATA_DIR=./dev-data uvicorn app.main:app --reload --port 8080
```

### Frontend

```bash
cd src/frontend
npm install
npm run dev   # proxies /api to http://localhost:8080 — run the backend alongside this
```

### Tests

```bash
pip install -r src/backend/requirements.txt pytest
pytest        # from the repo root — pytest.ini points at src/backend and tests/
```

Covers, among other things:

- MPG calculation (`miles_driven / current_fill-up_gallons`)
- Miles-driven arithmetic
- CSV date parsing across all the legacy timestamp formats
- The historical CSV's shifted-`Avg MPG` recalculation (exact acceptance data)
- Fuel-math validation with receipt-rounding tolerance
- Duplicate-fill-up detection
- Odometer/receipt OCR field parsing

### Full container build

```bash
docker build -t odo:dev .
docker run -d -p 8080:8080 -v odo-dev-data:/data odo:dev
```

## Architecture

```
src/
├── backend/                  FastAPI + SQLAlchemy + SQLite
│   └── app/
│       ├── models.py          Vehicle, FillUp, Setting (vehicle_id on every fill-up
│       │                      so multi-vehicle support is additive later, not a
│       │                      schema redesign)
│       ├── calculations.py    Pure math: miles driven, MPG, cost/mile, lifetime stats
│       ├── validation.py      Odometer/MPG/fuel-math sanity checks + duplicate detection
│       ├── csv_import.py      Legacy CSV import + recalculation
│       ├── csv_export.py      Clean CSV export
│       ├── ocr/                Preprocessing, provider interface, Tesseract provider,
│       │                      odometer parser, receipt parser
│       └── routes/            fillups, ocr, vehicles, stats, charts, settings, import/export
└── frontend/                 Vite + React + TypeScript PWA
    └── src/
        ├── pages/              Dashboard, NewFillUp, History, FillUpDetail, Charts, Settings
        └── components/         BottomNav, PhotoCapture, WarningBanner
```

Derived values (`miles_driven`, `mpg`, `cost_per_mile`) are **never stored** — they're computed from source values against the vehicle's chronological fill-up sequence every time they're read, so editing a historical record can't leave a stale calculation behind.

## License

[MIT](LICENSE)
