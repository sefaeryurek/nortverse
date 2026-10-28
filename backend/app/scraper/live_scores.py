"""Current match states from the public livescore board."""

from __future__ import annotations

from bs4 import BeautifulSoup

from app.config import SCRAPER
from app.scraper import status as st
from app.scraper.browser import browser_context, goto_with_retry
from app.scraper.fixture import _MATCH_ROW_RE
from app.scraper.fixture_scores import FixtureScore, _MINUTE_RE, _score, phase_from_minute

_LABEL_PHASES = {"1st Half": "1h", "HT": "ht", "2nd Half": "2h"}
_SCORE_CELL = "td.f-b.blue"


def parse_live_scores(html: str) -> dict[str, FixtureScore]:
    """Use the site's rendered clock; an absent clock is never invented."""
    soup = BeautifulSoup(html, "lxml")
    scores: dict[str, FixtureScore] = {}
    unknown = st.UnknownTally("Canlı sayfa")
    for row in soup.find_all("tr", id=_MATCH_ROW_RE):
        match_id = row["id"][4:]
        status_cell = row.select_one("td.status")
        label = status_cell.get_text(" ", strip=True) if status_cell else ""
        state = st.LIVE if _MINUTE_RE.fullmatch(label) else st.fixture_status(label)
        if state is None:
            unknown.add(label)
            state = st.SCHEDULED  # bilinmeyen etiket: canlıymış gibi gösterilmez
        if state in st.UNPLAYED:
            # İptal artık "ertelendi" sayılmaz (Sprint 94 B2)
            scores[match_id] = FixtureScore(match_id, state)
            continue
        if state in (st.SCHEDULED, st.FINISHED_EXTRA):
            scores[match_id] = FixtureScore(match_id, "scheduled" if state == st.SCHEDULED else state)
            continue
        score_cell = row.select_one(_SCORE_CELL)
        pair = _score(score_cell.get_text(" ", strip=True)) if score_cell else None
        if pair is None:
            continue
        minute = label if _MINUTE_RE.fullmatch(label) else ("HT" if label == "HT" else None)
        finished = state == st.FINISHED
        scores[match_id] = FixtureScore(
            match_id=match_id,
            status="finished" if finished else "live",
            home=pair[0], away=pair[1],
            minute=minute,
            phase=None if finished else (_LABEL_PHASES.get(label) or phase_from_minute(minute)),
        )
    unknown.report()
    return scores


async def fetch_live_scores() -> dict[str, FixtureScore]:
    async with browser_context() as ctx:
        page = await ctx.new_page()
        try:
            # Adres ayardan (SCRAPER_BASE_URL): kaynak alan adı değişirse tek yerden güncellenir.
            await goto_with_retry(page, SCRAPER.base_url + "/")
            await page.wait_for_selector('tr[id^="tr1_"]', timeout=12000)
            # The score feed and minute clock are applied after the initial HTML.
            await page.wait_for_timeout(1500)
            html = await page.content()
        finally:
            await page.close()
    return parse_live_scores(html)
