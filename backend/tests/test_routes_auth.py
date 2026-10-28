"""Giriş uçları ve oturum kapısı (Sprint 94 M3): çerez ayarları, çıkış, açık yollar, OPTIONS, WebSocket, giriş kapalı."""

from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app import auth


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED", "1")
    auth._failures.clear()
    from app.api.main import app

    @asynccontextmanager
    async def no_db():
        yield None

    monkeypatch.setattr("app.api.routes_auth.get_session", no_db)
    return TestClient(app)


def test_login_sets_httponly_lax_cookie(client, monkeypatch):
    async def ok(_session, username, _password, _ua):
        return "anahtar-123", auth.AuthUser(7, username, False)

    monkeypatch.setattr("app.api.routes_auth.login", ok)
    response = client.post("/api/auth/login", json={"username": "  Arkadas ", "password": "x"})
    assert response.status_code == 200
    assert response.json() == {"username": "arkadas", "is_admin": False}  # ad küçültülüp kırpılır
    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{auth.COOKIE_NAME}=anahtar-123")
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie and "Path=/" in cookie
    assert f"Max-Age={auth.SESSION_DAYS * 86400}" in cookie


def test_wrong_password_is_401_without_cookie(client, monkeypatch):
    async def wrong(*_a):
        return None

    monkeypatch.setattr("app.api.routes_auth.login", wrong)
    response = client.post("/api/auth/login", json={"username": "sefa", "password": "yanlis"})
    assert response.status_code == 401 and "set-cookie" not in response.headers
    auth._failures.clear()


def test_logout_deletes_session_and_cookie(client, monkeypatch):
    removed = []

    async def fake_logout(token):
        removed.append(token)

    async def resolve(_token):
        return auth.AuthUser(7, "arkadas", False)

    monkeypatch.setattr("app.api.routes_auth.logout", fake_logout)
    monkeypatch.setattr("app.auth.resolve", resolve)  # kapı açık yollarda da kullanıcıyı çözer
    client.cookies.set(auth.COOKIE_NAME, "anahtar-123")
    response = client.post("/api/auth/logout")
    assert response.status_code == 200 and removed == ["anahtar-123"]
    assert f'{auth.COOKIE_NAME}=""' in response.headers["set-cookie"] or "Max-Age=0" in response.headers["set-cookie"]


def test_public_paths_and_preflight_pass_without_session(client):
    assert client.get("/api/auth/me").status_code == 401           # açık yol: kendi 401'ini verir
    assert client.post("/api/auth/logout").status_code == 200
    preflight = client.options("/api/fixture", headers={"Origin": "http://localhost:3000",
                                                        "Access-Control-Request-Method": "GET"})
    assert preflight.status_code != 401                             # CORS ön isteği kapıya takılmaz
    assert client.get("/api/fixture").status_code == 401            # korumalı uç


def test_websocket_rejected_without_session(client, monkeypatch):
    async def none(_token):
        return None

    monkeypatch.setattr("app.auth.resolve", none)
    with pytest.raises(WebSocketDisconnect) as closed:
        with client.websocket_connect("/ws/live-ht"):
            pass
    assert closed.value.code == 4401


def test_auth_disabled_never_touches_session_store(monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED", "0")
    from app.api.main import app

    calls = []

    async def resolve(token):
        calls.append(token)
        return None

    monkeypatch.setattr("app.auth.resolve", resolve)
    response = TestClient(app).get("/api/auth/me")
    assert response.json() == {"username": "yerel", "is_admin": True}
    assert calls == [None]  # çerezsiz çözüm DB'ye gitmez (resolve None'da hemen döner)
