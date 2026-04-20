"""Günlük bülten sayfasından maç ID'lerini çekme.

URL: https://live5.nowgoal26.com/football/fixture

KRİTİK: Sayfa varsayılan olarak "Show All" modunda açılıyor (li_ShowAll class="on").
Hot filtresini aktive etmek için #li_FilterHot butonuna tıklamak gerekiyor.
JS tıklama sonrası "hot olmayan" satırlara display:none uygular.
Biz sadece görünür kalan satırları (hot maçları) alıyoruz.

Sayfa yapısı:
- Maç satırı: <tr id="tr1_XXXXXX" class="b2" sclassid="XX" style="...">
  - style="display: none;" → gizli (site Hot modunda göstermiyor) → atla
  - style="" → görünür → al
  - td.onclick="soccerInPage.analysis(ID,"Home","Away","League Name")"
  - td.time[data-t] içinde kick-off datetime
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from typing import Optional

from bs4 import BeautifulSoup
from bs4.element import Tag

from app.config import SCRAPER
from app.models import FixtureMatch
from app.scraper.browser import browser_context, close_ad_overlay, goto_with_retry

log = logging.getLogger(__name__)

# tr1_XXXXXX → match row
_MATCH_ROW_RE = re.compile(r"^tr1_(\d+)$")
# tr_XX → league header row
_LEAGUE_ROW_RE = re.compile(r"^tr_(\d+)$")
# onclick="soccerInPage.analysis(2784810,"Sassuolo","Como","Italy Serie A")"
_ONCLICK_RE = re.compile(
    r'soccerInPage\.analysis\(\s*(\d+)\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\)'
)


def _build_fixture_url(target_date: Optional[date] = None) -> str:
    """Hedef tarih için fixture URL'i oluştur."""
    base = SCRAPER.base_url + SCRAPER.fixture_path
    if target_date is None:
        return base

    today = date.today()
    diff = (target_date - today).days

    if diff == 0:
        return base
    if diff > 0:
        return f"{base}?f=sc{diff}"
    return f"{base}?f=ft{abs(diff)}"


def _is_row_hidden(tr: Tag) -> bool:
    """Maç satırı CSS ile gizlenmiş mi?

    Site 'Hot' filtresini display:none ile uyguluyor.
    """
    style = (tr.get("style") or "").replace(" ", "").lower()
    return "display:none" in style


def _build_league_map(soup: BeautifulSoup) -> dict[str, str]:
    """Sayfadaki ligleri map'le: sclassid -> league_name."""
    leagues: dict[str, str] = {}
    for tr in soup.find_all("tr", id=_LEAGUE_ROW_RE, class_="Leaguestitle"):
        sclassid = tr.get("sclassid")
        if not sclassid:
            continue
        name_el = tr.select_one(".LGname")
        name = name_el.get_text(strip=True) if name_el else "?"
        leagues[sclassid] = name
    return leagues


def _extract_match_info(tr: Tag) -> Optional[dict]:
    """Bir <tr> maç satırından bilgileri çıkar."""
    for td in tr.find_all("td"):
        onclick = td.get("onclick", "") or ""
        m = _ONCLICK_RE.search(onclick)
        if m:
            match_id = m.group(1)
            home = m.group(2)
            away = m.group(3)
            league_name = m.group(4)

            time_el = tr.select_one("td.time")
            kickoff = None
            kickoff_text = None
            if time_el:
                data_t = time_el.get("data-t", "")
                kickoff_text = time_el.get_text(strip=True)
                if data_t:
                    # Format: "2026-4-17 16:30:00" — tek haneli ay/gün olabilir
                    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%#m-%#d %H:%M:%S"):
                        try:
                            kickoff = datetime.strptime(data_t, fmt)
                            break
                        except (ValueError, Exception):
                            continue

            return {
                "match_id": match_id,
                "home": home,
                "away": away,
                "league_name": league_name,
                "kickoff": kickoff,
                "kickoff_text": kickoff_text,
            }
    return None


def _parse_fixture_html(html: str, only_hot: bool = True) -> list[FixtureMatch]:
    """Fixture sayfasının HTML'inden maç listesi çıkar.

    only_hot=True: Sitede görünür olan (display:none olmayan) maçlar.
                   Site 'Hot' filtresini varsayılan olarak uyguluyor.
    only_hot=False: Sitedeki TÜM maçlar (gizliler dahil).
    """
    soup = BeautifulSoup(html, "lxml")
    leagues = _build_league_map(soup)

    matches: list[FixtureMatch] = []
    seen_ids: set[str] = set()
    skipped_hidden = 0

    for tr in soup.find_all("tr", id=_MATCH_ROW_RE):
        if only_hot and _is_row_hidden(tr):
            skipped_hidden += 1
            continue

        info = _extract_match_info(tr)
        if not info:
            continue

        if info["match_id"] in seen_ids:
            continue
        seen_ids.add(info["match_id"])

        sclassid = tr.get("sclassid") or ""
        league_name = leagues.get(sclassid) or info.get("league_name") or "?"

        matches.append(
            FixtureMatch(
                match_id=info["match_id"],
                home_team=info["home"],
                away_team=info["away"],
                league_code=league_name,
                league_name=league_name,
                kickoff_time=info["kickoff"],
            )
        )

    log.info(
        "Fixture parse: %d görünür maç, %d gizli atlanan",
        len(matches),
        skipped_hidden,
    )
    return matches


async def _fetch_fixture_with_ctx(
    ctx,
    url: str,
    only_hot: bool,
) -> str:
    """Verilen browser context ile fixture sayfasının HTML'ini çeker."""
    page = await ctx.new_page()
    await goto_with_retry(page, url)

    try:
        await page.wait_for_selector('tr[id^="tr1_"]', timeout=10000)
    except Exception:
        log.warning("Maç satırları beklenen sürede yüklenmedi, devam ediliyor")
    await page.wait_for_timeout(int(SCRAPER.default_wait * 1000))

    await close_ad_overlay(page)

    if only_hot:
        try:
            await page.click("#li_FilterHot")
            await page.wait_for_timeout(2000)
            log.debug("Hot filtresi aktive edildi")
        except Exception as e:
            log.warning("Hot filtresi tıklanamadı: %s", e)

    html = await page.content()
    await page.close()

    if SCRAPER.save_html_on_error:
        SCRAPER.debug_dir.mkdir(parents=True, exist_ok=True)
        debug_path = (
            SCRAPER.debug_dir / f"fixture_{datetime.now():%Y%m%d_%H%M%S}.html"
        )
        debug_path.write_text(html, encoding="utf-8")
        log.debug("HTML kaydedildi: %s", debug_path)

    return html


async def fetch_fixture(
    target_date: Optional[date] = None,
    only_hot: bool = True,
    ctx=None,
) -> list[FixtureMatch]:
    """Nowgoal26 fixture sayfasından maç listesini çeker.

    ctx: Varolan BrowserContext (pipeline'dan gelir). None ise yeni browser açılır.
    """
    url = _build_fixture_url(target_date)
    log.info("Fixture çekiliyor: %s (only_hot=%s)", url, only_hot)

    if ctx is not None:
        html = await _fetch_fixture_with_ctx(ctx, url, only_hot)
    else:
        async with browser_context() as new_ctx:
            html = await _fetch_fixture_with_ctx(new_ctx, url, only_hot)

    matches = _parse_fixture_html(html, only_hot=only_hot)
    log.info("Fixture: %d maç bulundu (only_hot=%s)", len(matches), only_hot)
    return matches


async def fetch_fixture_for_tomorrow(only_hot: bool = True) -> list[FixtureMatch]:
    """Yarının fixture'ını çek (günlük cron için kısayol)."""
    return await fetch_fixture(
        target_date=date.today() + timedelta(days=1), only_hot=only_hot
    )
