Odo
A containerized self-hosted fuel tracker for logging gas fill-up data.
Odo uses odometer and receipt photos to simplify data entry and keep fuel records organized in one place.
---
Features
Core Features (MVP)
Log gas fill-up data
Upload odometer photos
Upload receipt photos
Keep fill-up records organized in one place
---
Planned Features
Automatic data extraction from odometer photos
Automatic data extraction from gas receipts
Reduce manual data entry
Simple fill-up history and record management
---
Goals
Make logging gas fill-ups quick and easy
Reduce the need for manual spreadsheet updates
Keep fuel records in one self-hosted application
---
Deploying on Unraid
Every push to `main` builds and publishes the image to `ghcr.io/wmhunter96/odo:latest` via GitHub Actions. An Unraid template is included so the container installs and updates through the normal Docker UI instead of hand-editing `docker-compose.yml`.
One-time setup:
On GitHub, go to the repo's Packages tab → `odo` package → Package settings → change visibility to Public. (Only needed once — GHCR packages default to private, and a private image needs a login secret on the Unraid side to pull.)
On Unraid: Docker tab → Template Repositories → add `https://github.com/wmhunter96/Odo` → Save.
Go to Apps (or Docker → Add Container → template dropdown) and select Odo. Adjust the container paths and settings to match your setup, then Apply.
After that: any new push to `main` refreshes the `latest` tag on GHCR, and Unraid's normal container update check (Docker tab, or the Community Applications "Check for Updates") will offer the update — no manual pulling or compose edits needed.
