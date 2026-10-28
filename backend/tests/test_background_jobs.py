"""BACKGROUND_JOBS=0: uçtan uca testlerde canlı izleyici / WebSocket yayıncısı kaynağa istek atmasın (Sprint 94 M1)."""

from app.api.main import background_jobs_enabled


def test_background_jobs_default_on(monkeypatch):
    monkeypatch.delenv("BACKGROUND_JOBS", raising=False)
    assert background_jobs_enabled()


def test_background_jobs_can_be_disabled(monkeypatch):
    for value in ("0", "false", "No"):
        monkeypatch.setenv("BACKGROUND_JOBS", value)
        assert not background_jobs_enabled()
