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


# ─── Sprint 94 E8: paylaşım öncesi sertleştirme ─────────────────────────────────────────────────

def test_origin_allowed_for_own_site_only():
    from app.api.main import origin_allowed

    assert origin_allowed(None) and origin_allowed("http://127.0.0.1:3000") and origin_allowed("http://localhost:3000")
    assert origin_allowed("https://sefa-pc.tail1234.ts.net")
    assert not origin_allowed("https://evil.example.com") and not origin_allowed("null")


def test_cross_site_post_is_403(client):
    response = client.post("/api/auth/login", json={"username": "a", "password": "b"},
                           headers={"Origin": "https://evil.example.com"})
    assert response.status_code == 403


def test_secure_cookie_behind_https(client, monkeypatch):
    async def ok(_session, username, _password, _ua):
        return "anahtar-9", auth.AuthUser(7, username, False)

    monkeypatch.setattr("app.api.routes_auth.login", ok)
    plain = client.post("/api/auth/login", json={"username": "a", "password": "b"})
    assert "Secure" not in plain.headers["set-cookie"]
    client.cookies.clear()  # ikinci istekte çerez gerçek DB'den çözülmesin
    https = client.post("/api/auth/login", json={"username": "a", "password": "b"},
                        headers={"X-Forwarded-Proto": "https"})
    assert "Secure" in https.headers["set-cookie"]


def test_health_without_session_shows_only_status(client, monkeypatch):
    @asynccontextmanager
    async def broken():
        raise RuntimeError("db yok")
        yield  # pragma: no cover

    monkeypatch.setattr("app.api.routes_admin.get_session", broken)
    body = client.get("/api/health").json()
    assert set(body) == {"status", "db_ok"} and body["status"] == "degraded"


def test_docs_and_openapi_are_off(client):
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404


def test_admin_endpoint_needs_admin_user_or_key(monkeypatch):
    import asyncio
    from types import SimpleNamespace

    from fastapi import HTTPException

    from app.api import routes_admin

    monkeypatch.setenv("AUTH_REQUIRED", "1")
    normal = SimpleNamespace(state=SimpleNamespace(user=auth.AuthUser(2, "arkadas", False)), headers={})
    admin = SimpleNamespace(state=SimpleNamespace(user=auth.AuthUser(1, "sefa", True)), headers={})
    monkeypatch.setattr(routes_admin, "_ADMIN_KEY", "")
    with pytest.raises(HTTPException):
        asyncio.run(routes_admin._require_admin(normal))
    asyncio.run(routes_admin._require_admin(admin))
    monkeypatch.setattr(routes_admin, "_ADMIN_KEY", "gizli")
    keyed = SimpleNamespace(state=SimpleNamespace(user=None), headers={"X-Admin-Key": "gizli"})
    asyncio.run(routes_admin._require_admin(keyed))
    wrong = SimpleNamespace(state=SimpleNamespace(user=None), headers={"X-Admin-Key": "yanlis"})
    with pytest.raises(HTTPException):
        asyncio.run(routes_admin._require_admin(wrong))


def test_login_runs_scrypt_even_for_unknown_user(monkeypatch):
    """Var olmayan kullanıcıda da aynı scrypt işi yapılır (yanıt süresinden ad anlaşılmaz)."""
    import asyncio

    calls = []
    monkeypatch.setattr(auth, "verify_password", lambda pw, stored: calls.append(stored) or False)

    class _Result:
        def scalar_one_or_none(self):
            return None

    class _Session:
        async def execute(self, *_a):
            return _Result()

    assert asyncio.run(auth.login(_Session(), "yok", "x", None)) is None
    assert calls == [auth._DUMMY_HASH]
