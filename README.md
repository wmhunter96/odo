## Deploying on Unraid

Every push to `main` builds and publishes the image to `ghcr.io/wmhunter96/odo:latest` via GitHub Actions. An Unraid template is included so the container installs and updates through the normal Docker UI instead of hand-editing `docker-compose.yml`.

**One-time setup:**

1. On GitHub, go to the repo's **Packages** tab → `odo` package → **Package settings** → change visibility to **Public**. (Only needed once — GHCR packages default to private, and a private image needs a login secret on the Unraid side to pull.)
2. On Unraid: **Docker** tab → **Template Repositories** → add `https://github.com/wmhunter96/Odo` → **Save**.
3. Go to **Apps** (or Docker → **Add Container** → template dropdown) and select **Odo**. Adjust the container paths and settings to match your setup, then **Apply**.

**After that:** any new push to `main` refreshes the `latest` tag on GHCR, and Unraid's normal container update check (Docker tab, or the Community Applications "Check for Updates") will offer the update — no manual pulling or compose edits needed.
