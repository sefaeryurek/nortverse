"""Kaynak koruması (Sprint 94 E9): tarayıcı sırası, oran isteği kapısı, tek kazıma, kullanıcı başına hız sınırı."""

import asyncio
import io
import time
from datetime import date
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest
from fastapi import HTTPException

from app.scraper import browser, odds


@pytest.fixture
def one_browser(monkeypatch):
    monkeypatch.setattr(browser, "SCRAPER", SimpleNamespace(playwright_max_concurrency=1))
    monkeypatch.setattr(browser, "_slot", None)


@pytest.mark.asyncio
async def test_browser_slot_limits_concurrency(one_browser):
    order = []

    async def job(name):
        async with browser._browser_slot():
            order.append(f"{name}+")
            await asyncio.sleep(0.02)
            order.append(f"{name}-")

    await asyncio.gather(job("a"), job("b"))
    assert order in (["a+", "a-", "b+", "b-"], ["b+", "b-", "a+", "a-"])  # ikisi aynı anda açık değil


@pytest.mark.asyncio
async def test_nested_browser_slot_does_not_deadlock(one_browser):
    async def outer():
        async with browser._browser_slot():
            async with browser._browser_slot():  # aynı görevde iç çağrı (ctx verilmemiş yardımcı)
                return "ok"

    assert await asyncio.wait_for(outer(), 1) == "ok"
    assert browser.playwright_stats()["active"] == 0


@pytest.fixture
def odds_gate(monkeypatch):
    monkeypatch.setattr(odds, "SCRAPER", SimpleNamespace(odds_max_concurrency=4, odds_requests_per_second=50.0))
    monkeypatch.setattr(odds, "_gate", None)
    monkeypatch.setattr(odds, "_next_slot", 0.0)
    monkeypatch.setattr(odds, "_backoff", 0.0)
    monkeypatch.setattr(odds, "_blocked_until", 0.0)
    monkeypatch.setattr(odds, "_stats", {"requests": 0, "errors": 0, "throttled": 0, "blocked_skips": 0})


@pytest.mark.asyncio
async def test_odds_backoff_after_403(odds_gate, monkeypatch):
    calls = []

    def forbidden(path, referer):
        calls.append(path)
        raise HTTPError(path, 403, "Forbidden", {}, io.BytesIO(b""))

    monkeypatch.setattr(odds, "_get", forbidden)
    with pytest.raises(HTTPError):
        await odds._fetch("/x", "1")
    assert odds._backoff == odds._BACKOFF_START
    # Bekleme süresince kaynağa hiç istek gitmez
    with pytest.raises(odds.SourceThrottled):
        await odds._fetch("/y", "1")
    assert calls == ["/x"] and odds.odds_stats()["blocked_skips"] == 1
    # Süre dolunca yeniden denenir; yine 403 → bekleme ikiye katlanır
    monkeypatch.setattr(odds, "_blocked_until", 0.0)
    with pytest.raises(HTTPError):
        await odds._fetch("/z", "1")
    assert odds._backoff == 2 * odds._BACKOFF_START
    # Başarılı istek kademeyi sıfırlar
    monkeypatch.setattr(odds, "_blocked_until", 0.0)
    monkeypatch.setattr(odds, "_get", lambda path, referer: b"{}")
    assert await odds._fetch("/ok", "1") == b"{}"
    assert odds._backoff == 0.0


@pytest.mark.asyncio
async def test_odds_requests_are_paced(odds_gate, monkeypatch):
    monkeypatch.setattr(odds, "SCRAPER", SimpleNamespace(odds_max_concurrency=4, odds_requests_per_second=20.0))
    stamps = []

    def record(path, referer):
        stamps.append(time.monotonic())  # _get ayrı thread'de çalışır
        return b"{}"

    monkeypatch.setattr(odds, "_get", record)
    await asyncio.gather(*(odds._fetch(f"/{i}", "1") for i in range(4)))
    ordered = sorted(stamps)
    gaps = [b - a for a, b in zip(ordered, ordered[1:])]
    # 20/sn → başlangıçlar 0,05 sn arayla planlanır; iş parçacığı başlama gecikmesi ve Windows saat çözünürlüğü
    # (~15 ms) tek tek aralıkları oynatır → toplam süre ve en küçük aralık için toleranslı alt sınır
    assert ordered[-1] - ordered[0] >= 0.12, gaps
    assert min(gaps) >= 0.02, gaps


@pytest.mark.asyncio
async def test_fixture_scraped_once_for_concurrent_requests(monkeypatch):
    from app.api import routes_fixture

    calls = []

    async def slow_fetch(day, only_hot=False):
        calls.append(day)
        await asyncio.sleep(0.05)
        return ["maç"]

    monkeypatch.setattr(routes_fixture, "fetch_istanbul_fixture", slow_fetch)
    day = date(2026, 11, 3)
    results = await asyncio.gather(*(routes_fixture._scrape_fixture_once(day) for _ in range(5)))
    assert results == [["maç"]] * 5 and calls == [day]
    assert routes_fixture._scrapes_in_flight == {}


@pytest.mark.asyncio
async def test_odds_endpoint_rate_limited_per_user(monkeypatch):
    from app.api import routes_coupons
    from app.auth import AuthUser

    class Stop(Exception):
        pass

    def no_db():
        raise Stop

    monkeypatch.setattr(routes_coupons, "get_session", no_db)

    def req(uid):
        return SimpleNamespace(state=SimpleNamespace(user=AuthUser(uid, "u", False)), client=None, headers={})

    for _ in range(routes_coupons.ODDS_RATE_PER_MIN):
        with pytest.raises(Stop):
            await routes_coupons.get_odds(req(1), "123")
    with pytest.raises(HTTPException) as error:
        await routes_coupons.get_odds(req(1), "123")
    assert error.value.status_code == 429
    with pytest.raises(Stop):  # başka kullanıcının sınırı ayrı
        await routes_coupons.get_odds(req(2), "123")
    # Önbellekte taze oranı olan maç sayılmaz (kaynağa gidilmeyecek)
    monkeypatch.setitem(routes_coupons._odds_cache, "456", (time.monotonic(), {}))
    with pytest.raises(Stop):
        await routes_coupons.get_odds(req(1), "456")
