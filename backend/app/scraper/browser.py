"""Playwright için ortak browser yardımcıları.

Her scraper modülü bu sınıf üzerinden sayfa açar — böylece
reklam kapatma, user agent ayarı gibi ortak işler tek yerde.
"""

from __future__ import annotations

import asyncio
import logging
import random
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import AsyncIterator

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from app.config import SCRAPER

log = logging.getLogger(__name__)

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
]


# Sprint 94 E9: süreç başına en fazla N tarayıcı. Aynı görev zaten bir yer tutuyorsa (iç içe çağrı) tekrar
# beklemez — iki dış işin birbirinin iç çağrısını beklemesiyle kilitlenme olmaz.
_slot: tuple[asyncio.AbstractEventLoop, asyncio.Semaphore] | None = None
_holding: ContextVar[bool] = ContextVar("nv_playwright_slot", default=False)
_stats = {"active": 0, "waiting": 0, "launched": 0}


def _semaphore() -> asyncio.Semaphore:
    """Olay döngüsü başına bir semafor (CLI her komutta yeni döngü açar)."""
    global _slot
    loop = asyncio.get_running_loop()
    if _slot is None or _slot[0] is not loop:
        _slot = (loop, asyncio.Semaphore(max(1, SCRAPER.playwright_max_concurrency)))
    return _slot[1]


def playwright_stats() -> dict:
    return {"max": SCRAPER.playwright_max_concurrency, **_stats}


@asynccontextmanager
async def _browser_slot() -> AsyncIterator[None]:
    if _holding.get():
        yield
        return
    sem = _semaphore()
    if sem.locked():
        log.info("Playwright sırası bekleniyor (aynı anda en fazla %d tarayıcı)", SCRAPER.playwright_max_concurrency)
    _stats["waiting"] += 1
    try:
        await sem.acquire()
    finally:
        _stats["waiting"] -= 1
    token = _holding.set(True)
    _stats["active"] += 1
    _stats["launched"] += 1
    try:
        yield
    finally:
        _stats["active"] -= 1
        _holding.reset(token)
        sem.release()


@asynccontextmanager
async def browser_context() -> AsyncIterator[BrowserContext]:
    """Playwright browser context'i açar ve kapanışı garanti eder (aynı anda en fazla N tarayıcı).

    Kullanım:
        async with browser_context() as ctx:
            page = await ctx.new_page()
            await page.goto(url)
    """
    async with _browser_slot(), async_playwright() as pw:
        browser: Browser = await pw.chromium.launch(headless=SCRAPER.headless)
        try:
            context: BrowserContext = await browser.new_context(
                user_agent=random.choice(_USER_AGENTS),
                viewport={"width": 1280, "height": 800},
                locale="en-US",
            )
            try:
                yield context
            finally:
                await context.close()
        finally:
            await browser.close()


async def close_ad_overlay(page: Page) -> bool:
    """Nowgoal'in reklam overlay'ini kapatmaya çalışır.

    Ad gözükmüyorsa sessizce False döner. Görüntüyü engelleyen
    overlay maç tablosunu da gizlediği için bunu mutlaka kapatmak gerekir.
    """
    try:
        if await page.locator(".closebtn").count() == 0:
            return False
        await page.click(".closebtn", timeout=3000)
        await page.wait_for_timeout(500)
        log.debug("Reklam kapatıldı (.closebtn)")
        return True
    except Exception:
        # Reklam zaten yok ya da selector değişmiş — sorun değil
        return False


async def goto_with_retry(page: Page, url: str, retries: int = 2) -> None:
    """Sayfayı aç. Timeout hatasında birkaç kez dener."""
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            await page.goto(
                url,
                timeout=int(SCRAPER.page_timeout * 1000),
                wait_until="domcontentloaded",
            )
            return
        except Exception as e:
            last_err = e
            log.warning("goto başarısız (attempt %d/%d): %s", attempt + 1, retries + 1, e)
            await page.wait_for_timeout(2000)
    if last_err:
        raise last_err
