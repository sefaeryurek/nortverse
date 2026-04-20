"""Lig sayfasından tüm maç ID'lerini çeker.

URL formatı:
- Güncel sezon: https://football.nowgoal26.com/league/{LEAGUE_ID}
- Geçmiş sezon: https://football.nowgoal26.com/league/{SEASON}/{LEAGUE_ID}

Sayfa JS-render gerektiriyor. Playwright ile açılıp maç ID'leri çıkarılır.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

from app.config import SCRAPER
from app.scraper.browser import browser_context, close_ad_overlay, goto_with_retry

log = logging.getLogger(__name__)

_LEAGUE_BASE = "https://football.nowgoal26.com/league"

# tr id="tr_MATCHID" veya onclick="...MATCHID..." gibi pattern'lar
_TR_ID_RE = re.compile(r"^tr_(\d+)$")
_ONCLICK_ID_RE = re.compile(r'analysis\((\d+)\s*,')
_H2H_HREF_RE = re.compile(r"/match/h2h-(\d+)")


def _extract_match_ids(html: str) -> list[str]:
    """HTML'den maç ID'lerini çıkar. Birden fazla strateji dener."""
    soup = BeautifulSoup(html, "lxml")
    ids: list[str] = []
    seen: set[str] = set()

    def _add(mid: str) -> None:
        if mid and mid not in seen:
            seen.add(mid)
            ids.append(mid)

    # Strateji 1: <tr id="tr_XXXXXX"> pattern'ı (fixture sayfasına benzer)
    for tr in soup.find_all("tr", id=_TR_ID_RE):
        m = _TR_ID_RE.match(tr.get("id", ""))
        if m:
            _add(m.group(1))

    # Strateji 2: onclick="...analysis(MATCHID, ..." gibi attribute
    for el in soup.find_all(onclick=True):
        m = _ONCLICK_ID_RE.search(el.get("onclick", ""))
        if m:
            _add(m.group(1))

    # Strateji 3: /match/h2h-MATCHID linkleri
    for a in soup.find_all("a", href=_H2H_HREF_RE):
        m = _H2H_HREF_RE.search(a.get("href", ""))
        if m:
            _add(m.group(1))

    # Strateji 4: data-mid veya data-id attribute'ları
    for el in soup.find_all(attrs={"data-mid": True}):
        _add(el.get("data-mid", ""))
    for el in soup.find_all(attrs={"data-id": True}):
        _add(el.get("data-id", ""))

    log.info("Sayfadan %d maç ID'si çıkarıldı", len(ids))
    return ids


def _save_debug_html(label: str, html: str) -> Path:
    debug_dir = SCRAPER.debug_dir
    debug_dir.mkdir(parents=True, exist_ok=True)
    path = debug_dir / f"league_{label}_{datetime.now():%Y%m%d_%H%M%S}.html"
    path.write_text(html, encoding="utf-8")
    log.info("Lig sayfası HTML debug'e kaydedildi: %s", path)
    return path


async def fetch_league_match_ids(
    league_id: int,
    season: str | None = None,
    ctx=None,
    save_debug: bool = False,
) -> list[str]:
    """Bir lig sezonunun tüm maç ID'lerini döner.

    Args:
        league_id: Nowgoal lig ID'si (örn: 36 = ENG PR)
        season: "2024-2025" formatında sezon, None ise güncel sezon
        ctx: Varolan BrowserContext. None ise yeni browser açılır.
        save_debug: True ise ham HTML debug klasörüne kaydedilir.

    Returns:
        Maç ID string listesi (sıra: sayfada göründüğü sıra)
    """
    if season:
        url = f"{_LEAGUE_BASE}/{season}/{league_id}"
    else:
        url = f"{_LEAGUE_BASE}/{league_id}"

    log.info("Lig sayfası çekiliyor: %s", url)

    async def _fetch(ctx_) -> str:
        page = await ctx_.new_page()
        await goto_with_retry(page, url)
        # Sayfa JS ile render oluyor — maç satırları için bekle
        await page.wait_for_timeout(int(SCRAPER.default_wait * 1000))
        await close_ad_overlay(page)
        await page.wait_for_timeout(1000)

        # Maç satırları yüklenene kadar ek bekleme (table veya tr yoksa daha fazla bekle)
        try:
            await page.wait_for_selector("tr[id], td[onclick], a[href*='/match/h2h-']", timeout=10000)
        except Exception:
            log.warning("Maç satırları bulunamadı, devam ediliyor...")

        html = await page.content()
        await page.close()
        return html

    if ctx is not None:
        html = await _fetch(ctx)
    else:
        async with browser_context() as new_ctx:
            html = await _fetch(new_ctx)

    if save_debug or not _extract_match_ids(html):
        label = f"{league_id}_{season or 'current'}"
        _save_debug_html(label, html)

    return _extract_match_ids(html)
