"""Read final and in-progress scores from one fixture page request."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from bs4 import BeautifulSoup

from app.scraper.browser import browser_context
from app.scraper.fixture import _build_fixture_url, _fetch_fixture_with_ctx, _MATCH_ROW_RE

_SCORE_RE = re.compile(r"^\s*(\d{1,2})\s*[-:]\s*(\d{1,2})\s*$")
_LIVE_STATUSES = {"1st Half", "2nd Half", "HT"}
_MINUTE_RE = re.compile(r"^(?:[1-9]|[1-9]\d|1[01]\d)(?:\+[1-9]\d?)?$", re.ASCII)


@dataclass(frozen=True)
class FixtureScore:
    match_id: str
    status: str
    home: int | None = None
    away: int | None = None
    ht_home: int | None = None
    ht_away: int | None = None
    minute: str | None = None


def _score(value: str) -> tuple[int, int] | None:
    match = _SCORE_RE.fullmatch(value)
    if match is None:
        return None
    pair = int(match.group(1)), int(match.group(2))
    return pair if all(0 <= number <= 30 for number in pair) else None


def parse_fixture_scores(html: str) -> dict[str, FixtureScore]:
    """Only an explicit FT status is accepted as a final result."""
    soup = BeautifulSoup(html, "lxml")
    scores: dict[str, FixtureScore] = {}
    for row in soup.find_all("tr", id=_MATCH_ROW_RE):
        match_id = row["id"][4:]
        status_cell = row.select_one("td.status")
        source_status = status_cell.get_text(" ", strip=True) if status_cell else ""
        if source_status == "Postp.":
            scores[match_id] = FixtureScore(match_id, "postponed")
            continue
        if source_status != "FT" and source_status not in _LIVE_STATUSES and not _MINUTE_RE.fullmatch(source_status):
            continue
        score_cell = row.select_one("td.handpoint")
        pair = _score(score_cell.get_text(" ", strip=True)) if score_cell else None
        if pair is None:
            continue
        half_pair = None
        if source_status == "FT":
            tool = row.select_one("td.toolimg")
            half_cell = tool.find_previous_sibling("td") if tool else None
            half_pair = _score(half_cell.get_text(" ", strip=True)) if half_cell else None
            if half_pair and any(half > final for half, final in zip(half_pair, pair)):
                half_pair = None
        scores[match_id] = FixtureScore(
            match_id=match_id,
            status="finished" if source_status == "FT" else "live",
            home=pair[0], away=pair[1],
            ht_home=half_pair[0] if half_pair else None,
            ht_away=half_pair[1] if half_pair else None,
            minute=source_status if _MINUTE_RE.fullmatch(source_status) else None,
        )
    return scores


async def fetch_fixture_scores(target_date: date) -> dict[str, FixtureScore]:
    url = _build_fixture_url(target_date)
    async with browser_context() as ctx:
        html = await _fetch_fixture_with_ctx(ctx, url, only_hot=False)
    return parse_fixture_scores(html)
