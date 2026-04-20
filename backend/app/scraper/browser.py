"""Playwright için ortak browser yardımcıları.

Her scraper modülü bu sınıf üzerinden sayfa açar — böylece
reklam kapatma, user agent ayarı gibi ortak işler tek yerde.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from app.config import SCRAPER

log = logging.getLogger(__name__)


@asynccontextmanager
async def browser_context() -> AsyncIterator[BrowserContext]:
    """Playwright browser context'i açar ve kapanışı garanti eder.

    Kullanım:
        async with browser_context() as ctx:
            page = await ctx.new_page()
            await page.goto(url)
    """
    async with async_playwright() as pw:
        browser: Browser = await pw.chromium.launch(headless=SCRAPER.headless)
        try:
            context: BrowserContext = await browser.new_context(
                user_agent=SCRAPER.user_agent,
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
