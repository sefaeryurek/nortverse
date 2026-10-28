"""Unit tests must never use a developer's production database credentials."""
import os

os.environ["DATABASE_URL"] = "postgresql+asyncpg://test:test@127.0.0.1:5432/nortverse_test"
os.environ["DATABASE_URL_SYNC"] = ""
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
# Giriş zorunluluğu kendi testlerinde (test_auth.py) açılır; diğer testler uçları doğrudan çağırır
os.environ["AUTH_REQUIRED"] = "0"


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_rate_limits():
    """Hız sınırı sayaçları süreç içinde kalıcı; testler birbirinin sayacını tüketmesin (Sprint 94 E9)."""
    from app.api import ratelimit

    ratelimit.reset()
    yield
    ratelimit.reset()


def fake_db_session():
    """AsyncMock oturum + gerçekten girilen savepoint (`begin_nested`) — Sprint 94 M2.

    Düz AsyncMock'ta `session.begin_nested()` beklenmemiş bir eşyordam döndürür; `async with` hata verir, kod bunu
    `except Exception` ile yutar ve savepoint içi testte HİÇ çalışmaz (RuntimeWarning: never awaited).
    """
    from unittest.mock import AsyncMock, MagicMock

    session = AsyncMock()
    session.begin_nested = MagicMock(side_effect=lambda: _Savepoint())
    return session


class _Savepoint:
    """Gerçek savepoint gibi: içerideki hata dışarı çıkar (AsyncMock'un __aexit__'i hatayı yutuyordu)."""

    entered = 0

    async def __aenter__(self):
        _Savepoint.entered += 1
        return self

    async def __aexit__(self, *exc):
        return False


@pytest.fixture(autouse=True)
def _no_odds_network(monkeypatch):
    """Testler oran kaynağına asla gerçek istek atmasın (Sprint 94 I2: canlı dondurma artık fiyat da çeker).
    `_get`'i sınayan testler `_request_once`'ı kendileri taklit eder."""
    from app.scraper import odds

    def blocked(url, headers):
        raise ConnectionError(f"testte ağ kapalı: {url}")

    monkeypatch.setattr(odds, "_request_once", blocked)
