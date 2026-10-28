"""Giriş ve oturumlar (Sprint 93 — siteyi Tailscale üzerinden arkadaşla paylaşmak için).

- Şifre: Python'un kendi scrypt'i (hashlib, yeni bağımlılık yok), kullanıcı başına rastgele tuz.
- Oturum: çerezde rastgele 32 baytlık anahtar (`nv_session`, httpOnly); DB'de sadece SHA-256 özeti.
  30 gün geçerli. Çıkışta ya da şifre değişince silinir.
- Yetki tek merkezde: backend her `/api` ve `/ws` isteğinde oturumu çözer (`main.require_session`).
  Next sunucu tarafı istekleri kullanıcının kendi çerezini iletir; ayrı bir gizli anahtar yok.
- Playwright tetikleyen uçlar (yeni maç çekimi) sadece admin hesabında çalışır.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

COOKIE_NAME = "nv_session"
SESSION_DAYS = 30
_SCRYPT = {"n": 2**14, "r": 8, "p": 1}
_CACHE_TTL = 60.0  # çözülmüş oturum bellekte (her istekte DB'ye gitmesin)
_cache: dict[str, tuple[float, "AuthUser | None"]] = {}

# Kaba kuvvet koruması: kullanıcı adı veya IP başına 15 dk'da 8 hatalı deneme
_FAIL_WINDOW = 15 * 60
_FAIL_LIMIT = 8
_failures: dict[str, list[float]] = {}


@dataclass(frozen=True)
class AuthUser:
    id: int
    username: str
    is_admin: bool


def auth_required() -> bool:
    """`AUTH_REQUIRED=0` sadece testler/yerel deneme içindir; varsayılan açık."""
    return os.environ.get("AUTH_REQUIRED", "1").strip().lower() not in ("0", "false", "no")


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT, dklen=32)
    return f"scrypt${_SCRYPT['n']}${_SCRYPT['r']}${_SCRYPT['p']}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        actual = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p),
                                dklen=32)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, base64.b64decode(digest))


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def too_many_failures(*keys: str) -> bool:
    now = time.monotonic()
    for key in keys:
        recent = [t for t in _failures.get(key, []) if now - t < _FAIL_WINDOW]
        _failures[key] = recent
        if len(recent) >= _FAIL_LIMIT:
            return True
    return False


def record_failure(*keys: str) -> None:
    now = time.monotonic()
    for key in keys:
        _failures.setdefault(key, []).append(now)


async def login(session, username: str, password: str, user_agent: str | None) -> tuple[str, AuthUser] | None:
    """Doğruysa yeni oturum anahtarı (çereze yazılacak) ve kullanıcı."""
    from sqlalchemy import select

    from app.db.models import User, UserSession

    user = (await session.execute(select(User).where(User.username == username.strip().lower()))).scalar_one_or_none()
    if user is None or user.disabled or not verify_password(password, user.password_hash):
        return None
    token = secrets.token_urlsafe(32)
    session.add(UserSession(token_hash=token_hash(token), user_id=user.id, user_agent=(user_agent or "")[:200],
                            expires_at=datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)))
    return token, AuthUser(user.id, user.username, user.is_admin)


async def resolve(token: str | None) -> AuthUser | None:
    """Çerezdeki anahtar → kullanıcı (süresi dolmuş, silinmiş ya da devre dışı hesapta None)."""
    if not token or len(token) > 100:
        return None
    key = token_hash(token)
    cached = _cache.get(key)
    if cached is not None and time.monotonic() - cached[0] < _CACHE_TTL:
        return cached[1]
    from sqlalchemy import select

    from app.db.connection import get_session
    from app.db.models import User, UserSession

    async with get_session() as session:
        row = (await session.execute(
            select(User.id, User.username, User.is_admin)
            .join(UserSession, UserSession.user_id == User.id)
            .where(UserSession.token_hash == key, UserSession.expires_at > datetime.now(timezone.utc),
                   User.disabled.is_(False))
        )).first()
    user = AuthUser(row.id, row.username, row.is_admin) if row else None
    if len(_cache) > 500:
        _cache.clear()
    _cache[key] = (time.monotonic(), user)
    return user


async def logout(token: str | None) -> None:
    if not token:
        return
    from sqlalchemy import delete

    from app.db.connection import get_session
    from app.db.models import UserSession

    key = token_hash(token)
    _cache.pop(key, None)
    async with get_session() as session:
        await session.execute(delete(UserSession).where(UserSession.token_hash == key))


INTERNAL_HEADER = "x-internal-key"
# Çerezsiz sunucu çizimi (ör. istek dışı ön çizim): yönetici DEĞİL — Playwright gibi ağır işleri tetikleyemez
# (Sprint 94 E1; eskiden her sayfa çizimi yönetici sayılıyordu, normal kullanıcı kazıma başlatabiliyordu).
_SERVER_USER = AuthUser(0, "sunucu", False)


def internal_user(header_value: str | None) -> AuthUser | None:
    """Next sunucu tarafı istekleri (sayfa çizimi): `INTERNAL_API_KEY` eşleşirse. Sayfaların kendisini Next
    `proxy.ts` oturum kontrolüyle korur; anahtar tarayıcıya hiç gitmez. Next kullanıcının çerezini de iletir;
    çerez geçerliyse `request_user` gerçek kullanıcıyı (ve yetkisini) kullanır, bu sadece çerezsiz yedektir."""
    expected = os.environ.get("INTERNAL_API_KEY", "")
    if not expected or not header_value:
        return None
    return _SERVER_USER if hmac.compare_digest(header_value.encode(), expected.encode()) else None


async def request_user(cookie_token: str | None, internal_header: str | None) -> AuthUser | None:
    """İsteğin kullanıcısı: önce çerezdeki gerçek oturum, yoksa iç anahtarlı sunucu çizimi (yönetici değil)."""
    return await resolve(cookie_token) or internal_user(internal_header)


def forget_user_sessions_cache() -> None:
    """Şifre değişince / hesap kapatılınca bellekteki çözümler de unutulsun."""
    _cache.clear()


def is_admin_request(request) -> bool:
    """Yeni maç çekimi (Playwright) gibi ağır işler: sadece admin. Giriş kapalıysa (yerel/test) serbest."""
    if not auth_required():
        return True
    user = getattr(request.state, "user", None)
    return bool(user and user.is_admin)
