"""Lig sayfasından tüm maç ID'lerini çeker.

Yaklaşım: HTML scraping değil, doğrudan JSON API.
Nowgoal lig sayfası verileri şu formattan yükler:
  https://football.nowgoal26.com/jsData/matchResult/json/{SEASON}/s{LEAGUE_ID}_en.json

Yapı:
  data['ScheduleList'] = {'R_1': [maç, maç, ...], 'R_2': [...], ...}
  maç[0] = match_id (int)

Sezon listesi için:
  https://football.nowgoal26.com/jsData/leagueSeason/sea{LEAGUE_ID}.json
"""

from __future__ import annotations

import json
import logging

from bs4 import BeautifulSoup

from app.config import SCRAPER
from app.scraper.browser import browser_context, goto_with_retry

log = logging.getLogger(__name__)

_JSON_BASE = "https://football.nowgoal26.com/jsData/matchResult/json"
_SEASON_BASE = "https://football.nowgoal26.com/jsData/leagueSeason"


async def _fetch_json(url: str, ctx=None) -> dict | list:
    """Verilen URL'deki JSON'u Playwright ile çek ve döndür."""

    async def _get(ctx_) -> str:
        page = await ctx_.new_page()
        await goto_with_retry(page, url)
        await page.wait_for_timeout(2000)
        content = await page.content()
        await page.close()
        return content

    if ctx is not None:
        html = await _get(ctx)
    else:
        async with browser_context() as new_ctx:
            html = await _get(new_ctx)

    soup = BeautifulSoup(html, "lxml")
    pre = soup.find("pre")
    raw = pre.get_text() if pre else html
    return json.loads(raw)


async def fetch_league_seasons(league_id: int, ctx=None) -> list[str]:
    """Bir lig için mevcut sezon listesini döndür.

    Örnek dönüş: ["2024-2025", "2023-2024", "2022-2023", ...]
    """
    url = f"{_SEASON_BASE}/sea{league_id}.json"
    log.info("Sezon listesi çekiliyor: %s", url)
    try:
        data = await _fetch_json(url, ctx=ctx)
        if isinstance(data, list):
            # [{season: "2024-2025", ...}, ...] veya ["2024-2025", ...] olabilir
            seasons = []
            for item in data:
                if isinstance(item, dict):
                    s = item.get("season") or item.get("Season") or item.get("s")
                    if s:
                        seasons.append(str(s))
                elif isinstance(item, (str, int)):
                    seasons.append(str(item))
            return seasons
        elif isinstance(data, dict):
            return [str(v) for v in data.values() if isinstance(v, str)]
    except Exception as e:
        log.warning("Sezon listesi alınamadı: %s", e)
    return []


async def fetch_league_match_ids(
    league_id: int,
    season: str | None = None,
    ctx=None,
) -> list[str]:
    """Bir lig sezonunun tüm maç ID'lerini döndür.

    Args:
        league_id: Nowgoal lig ID'si (örn: 36 = ENG PR)
        season: "2024-2025" formatında sezon, None ise güncel sezon alınır
        ctx: Varolan BrowserContext. None ise yeni browser açılır.

    Returns:
        Maç ID string listesi
    """
    if season is None:
        # Güncel sezonu sezon listesinden al
        seasons = await fetch_league_seasons(league_id, ctx=ctx)
        if seasons:
            season = seasons[0]
            log.info("Güncel sezon: %s", season)
        else:
            log.error("Sezon bilgisi alınamadı, league_id=%d", league_id)
            return []

    url = f"{_JSON_BASE}/{season}/s{league_id}_en.json"
    log.info("Lig maç verisi çekiliyor: %s", url)

    try:
        data = await _fetch_json(url, ctx=ctx)
    except Exception as e:
        log.error("JSON çekilemedi (%s): %s", url, e)
        return []

    if not isinstance(data, dict):
        log.error("Beklenmedik JSON formatı: %s", type(data))
        return []

    schedule = data.get("ScheduleList", {})
    if not schedule:
        log.warning("ScheduleList boş, veri yok")
        return []

    match_ids: list[str] = []
    for round_key, matches in schedule.items():
        if not isinstance(matches, list):
            continue
        for match in matches:
            if isinstance(match, list) and match:
                match_ids.append(str(match[0]))
            elif isinstance(match, dict):
                mid = match.get("id") or match.get("matchId") or match.get("mid")
                if mid:
                    match_ids.append(str(mid))

    log.info(
        "Lig %d / %s: %d round, %d maç ID çekildi",
        league_id,
        season,
        len(schedule),
        len(match_ids),
    )
    return match_ids
