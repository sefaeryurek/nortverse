"""Lightweight current and final scores from the fixture AJAX response."""

from __future__ import annotations

import ast
import asyncio
import gzip
import json
import re
from datetime import date
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.config import SCRAPER
from app.scraper.fixture_scores import FixtureScore

_ROW_RE = re.compile(r"A\[\d+\]=(\[[^\r\n]*\]);")
_URL = SCRAPER.base_url + "/ajax/SoccerAjax"


def parse_source_board(payload: bytes) -> dict[str, FixtureScore]:
    if payload[:2] == b"\x1f\x8b":
        payload = gzip.decompress(payload)
    data = json.loads(payload)
    if data.get("ErrCode") != 0 or not isinstance(data.get("Data"), str):
        raise ValueError("Invalid fixture score response")
    scores: dict[str, FixtureScore] = {}
    for raw in _ROW_RE.findall(data["Data"]):
        normalized = raw
        while ",," in normalized:
            normalized = normalized.replace(",,", ",None,")
        try:
            fields = ast.literal_eval(normalized)
        except (ValueError, SyntaxError):
            continue
        if len(fields) < 10 or not isinstance(fields[0], int) or not isinstance(fields[7], int):
            continue
        match_id, code = str(fields[0]), fields[7]
        if code == -1:
            status = "finished"
        elif code in (1, 2, 3):
            status = "live"
        elif code == 0:
            status = "scheduled"
        elif code in (-11, -14):
            status = "postponed"
        else:
            continue
        home, away = fields[8:10]
        if status in ("finished", "live"):
            if not all(isinstance(value, int) and 0 <= value <= 30 for value in (home, away)):
                continue
        else:
            home = away = None
        scores[match_id] = FixtureScore(match_id, status, home, away)
    if not scores:
        raise ValueError("Empty fixture score response")
    return scores


async def fetch_source_board(target_date: date) -> dict[str, FixtureScore]:
    # urllib follows the source site's redirect to its current live host.
    # The HTTP client used elsewhere in the app can lose that response behind
    # some outbound proxies, so keep this one small read in a worker thread.
    def fetch() -> bytes:
        query = urlencode({"type": 6, "date": target_date.isoformat(),
                           "order": "league", "timezone": 3})
        request = Request(
            f"{_URL}?{query}",
            headers={"User-Agent": SCRAPER.user_agent, "X-Requested-With": "XMLHttpRequest",
                     "Referer": SCRAPER.base_url + "/football/fixture"},
        )
        with urlopen(request, timeout=18) as response:
            return response.read()

    return parse_source_board(await asyncio.to_thread(fetch))
