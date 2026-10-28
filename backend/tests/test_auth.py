"""Giriş zorunluluğu ve şifre saklama (Sprint 93)."""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import auth


def test_password_hash_roundtrip_and_salt():
    stored = auth.hash_password("gizli-şifre")
    assert stored.startswith("scrypt$") and "gizli" not in stored
    assert auth.verify_password("gizli-şifre", stored)
    assert not auth.verify_password("yanlis", stored)
    assert auth.hash_password("gizli-şifre") != stored  # her seferinde farklı tuz
    assert not auth.verify_password("x", "bozuk-kayit")


def test_failure_limit():
    auth._failures.clear()
    for _ in range(auth._FAIL_LIMIT):
        auth.record_failure("u:deneme")
    assert auth.too_many_failures("u:deneme", "ip:1.2.3.4")
    assert not auth.too_many_failures("u:baska")
    auth._failures.clear()


def test_admin_check(monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED", "1")
    request = SimpleNamespace(state=SimpleNamespace(user=auth.AuthUser(1, "arkadas", False)))
    assert not auth.is_admin_request(request)
    request.state.user = auth.AuthUser(2, "sefa", True)
    assert auth.is_admin_request(request)
    monkeypatch.setenv("AUTH_REQUIRED", "0")
    assert auth.is_admin_request(None)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED", "1")
    from app.api.main import app

    return TestClient(app)


def test_api_requires_session(client):
    response = client.get("/api/fixture")
    assert response.status_code == 401 and response.headers["cache-control"] == "no-store"
    assert client.get("/api/performance/summary").status_code == 401
    assert client.get("/api/auth/me").status_code == 401


def test_forged_cookie_rejected(client, monkeypatch):
    async def none(_token):
        return None

    monkeypatch.setattr("app.auth.resolve", none)
    client.cookies.set(auth.COOKIE_NAME, "uydurma")
    assert client.get("/api/results").status_code == 401


def test_internal_key(monkeypatch):
    monkeypatch.setenv("INTERNAL_API_KEY", "dogru-anahtar")
    assert auth.internal_user("dogru-anahtar") is not None
    assert not auth.internal_user("dogru-anahtar").is_admin  # Sprint 94 E1: iç anahtar yönetici değil
    assert auth.internal_user("yanlis") is None and auth.internal_user(None) is None
    monkeypatch.setenv("INTERNAL_API_KEY", "")
    assert auth.internal_user("") is None


def test_server_render_uses_real_user(client, monkeypatch):
    """Sprint 94 E1: sayfa çizimi iç anahtarla gelir ama yetki çerezdeki gerçek kullanıcınınkidir."""
    users = {"normal": auth.AuthUser(5, "arkadas", False), "yonetici": auth.AuthUser(1, "sefa", True)}

    async def fake_resolve(token):
        return users.get(token)

    monkeypatch.setenv("INTERNAL_API_KEY", "dogru-anahtar")
    monkeypatch.setattr("app.auth.resolve", fake_resolve)
    headers = {auth.INTERNAL_HEADER: "dogru-anahtar"}

    client.cookies.set(auth.COOKIE_NAME, "normal")
    assert client.get("/api/auth/me", headers=headers).json() == {"username": "arkadas", "is_admin": False}
    client.cookies.set(auth.COOKIE_NAME, "yonetici")
    assert client.get("/api/auth/me", headers=headers).json() == {"username": "sefa", "is_admin": True}
    client.cookies.clear()
    assert client.get("/api/auth/me", headers=headers).json() == {"username": "sunucu", "is_admin": False}
    # Normal kullanıcı önbellekte olmayan bir günü açınca kazıma başlamaz (503, Playwright yok)
    client.cookies.set(auth.COOKIE_NAME, "normal")

    scrapes = []

    async def fake_scrape(*_a, **_k):
        scrapes.append(1)
        return []

    monkeypatch.setattr("app.api.routes_fixture.fetch_istanbul_fixture", fake_scrape)
    monkeypatch.setattr("app.api.routes_fixture.get_session", _no_db)
    from datetime import date, timedelta
    day = (date.today() + timedelta(days=9)).isoformat()
    assert client.get(f"/api/fixture?date={day}", headers=headers).status_code == 503
    assert scrapes == []
    # Aynı istek yönetici çereziyle kazımaya gider (kapı gerçekten çerezdeki kullanıcıya bakıyor)
    client.cookies.set(auth.COOKIE_NAME, "yonetici")
    client.get(f"/api/fixture?date={day}", headers=headers)
    assert scrapes == [1]


class _NoDb:
    async def __aenter__(self):
        raise RuntimeError("DB yok")

    async def __aexit__(self, *exc):
        return False


def _no_db():
    return _NoDb()
