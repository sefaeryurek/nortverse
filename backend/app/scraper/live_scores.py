"""Current match states from the public livescore board."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from app.scraper.browser import browser_context, goto_with_retry
from app.scraper.fixture import _MATCH_ROW_RE
from app.scraper.fixture_scores import FixtureScore, _MINUTE_RE, _score

_FINISHED = {"FT"}
_POSTPONED = {"Postp.", "Pend.", "Abd.", "Canc."}
_LIVE = {"1st Half", "2nd Half", "HT"}
_SCORE_CELL = "td.f-b.blue"


def parse_live_scores(html: str) -> dict[str, FixtureScore]:
    """Use the site's rendered clock; an absent clock is never invented."""
    soup = BeautifulSoup(html, "lxml")
    scores: dict[str, FixtureScore] = {}
    for row in soup.find_all("tr", id=_MATCH_ROW_RE):
        match_id = row["id"][4:]
        status_cell = row.select_one("td.status")
        label = status_cell.get_text(" ", strip=True) if status_cell else ""
        if label in _POSTPONED:
            scores[match_id] = FixtureScore(match_id, "postponed")
            continue
        if label not in _FINISHED and label not in _LIVE and not _MINUTE_RE.fullmatch(label):
            scores[match_id] = FixtureScore(match_id, "scheduled")
            continue
        score_cell = row.select_one(_SCORE_CELL)
        pair = _score(score_cell.get_text(" ", strip=True)) if score_cell else None
        if pair is None:
            continue
        scores[match_id] = FixtureScore(
            match_id=match_id,
            status="finished" if label in _FINISHED else "live",
            home=pair[0], away=pair[1],
            minute=label if _MINUTE_RE.fullmatch(label) else ("HT" if label == "HT" else None),
        )
    return scores


async def fetch_live_scores() -> dict[str, FixtureScore]:
    async with browser_context() as ctx:
        page = await ctx.new_page()
        try:
            await goto_with_retry(page, "https://live5.nowgoal26.com/")
            await page.wait_for_selector('tr[id^="tr1_"]', timeout=12000)
            # The score feed and minute clock are applied after the initial HTML.
            await page.wait_for_timeout(1500)
            html = await page.content()
        finally:
            await page.close()
    return parse_live_scores(html)
