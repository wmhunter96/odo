# Odo

A containerized self-hosted fuel tracker for simplifying gas fill-up logging.

Odo uses odometer and receipt photos to make recording fill-ups quick and easy, reducing manual data entry while keeping fuel records organized in one place.

---

## Features

### Core Features (MVP)

- Web UI for logging gas fill-ups
- Upload **one odometer photo and one receipt photo**
- Extract fill-up data from uploaded photos
- Review and correct extracted data before saving
- Store completed fill-up records
- Keep the original photos attached to each record
- View previous fill-ups in a simple history

---

## Configuration

- **Application data directory**
- **Uploaded photo storage**
- **Vehicle information**
- Configurable defaults for fill-up logging

---

## Planned Features

- Improved automatic data extraction from **odometer photos**
- Improved automatic data extraction from **gas receipts**
- Fill-up statistics and trends
- Fuel cost and mileage history
- CSV export
- Multiple vehicle support
- Optional Google Sheets export or sync
- Automatic checks for unusual or incorrect readings

---

## Goals

- Make logging a fill-up as simple as taking **two photos**
- Eliminate the need to manually update a fuel spreadsheet
- Keep fuel records and source photos together
- Provide a simple, self-hosted alternative to cloud-based fuel tracking apps

---

## Deploying on Unraid

Every push to `main` builds and publishes the image to `ghcr.io/wmhunter96/odo:latest` via [GitHub Actions](.github/workflows/docker-publish.yml). An [Unraid template](unraid/odo.xml) is included so the container installs and updates through the normal Docker UI instead of hand-editing `docker-compose.yml`.

**One-time setup:**

1. On GitHub, go to the repo's **Packages** tab → `odo` package → **Package settings** → change visibility to **Public**. (Only needed once — GHCR packages default to private, and a private image needs a login secret on the Unraid side to pull.)
2. On Unraid: **Docker** tab → **Template Repositories** → add `https://github.com/wmhunter96/Odo` → **Save**.
3. Go to **Apps** (or Docker → **Add Container** → template dropdown) and select **Odo**. Adjust the config/data paths to match your shares, then **Apply**.

**After that:** any new push to `main` refreshes the `latest` tag on GHCR, and Unraid's normal container update check (Docker tab, or the Community Applications "Check for Updates") will offer the update — no manual pulling or compose edits needed.
