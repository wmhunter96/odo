"""/api/healthz must reliably report which build is actually running --
this is the one source of truth immune to any URL/CDN/browser caching
(e.g. an Unraid template icon fetched from raw.githubusercontent.com),
unlike everything else that might *look* updated without actually being so.
"""
from app.config import Settings


def test_settings_reads_git_sha_and_build_date_from_env(monkeypatch):
    monkeypatch.setenv("GIT_SHA", "abc1234567890")
    monkeypatch.setenv("BUILD_DATE", "2026-08-11T12:00:00Z")
    settings = Settings()
    assert settings.git_sha == "abc1234567890"
    assert settings.build_date == "2026-08-11T12:00:00Z"


def test_settings_defaults_to_unknown_without_build_args(monkeypatch):
    monkeypatch.delenv("GIT_SHA", raising=False)
    monkeypatch.delenv("BUILD_DATE", raising=False)
    settings = Settings()
    assert settings.git_sha == "unknown"
    assert settings.build_date == "unknown"
