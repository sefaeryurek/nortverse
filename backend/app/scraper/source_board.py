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
from app.scraper import status as st
from app.scraper.fixture_scores import FixtureScore

_ROW_RE = re.compile(r"A\[\d+\]=(\[[^\r\n]*\]);")
_PHASES = {1: "1h", 2: "ht", 3: "2h", 4: "et", 5: "et"}
_URL = SCRAPER.base_url + "/ajax/SoccerAjax"


def parse_source_board(payload: bytes) -> dict[str, FixtureScore]:
    if payload[:2] == b"\x1f\x8b":
        payload = gzip.decompress(payload)
    data = json.loads(payload)
    if data.get("ErrCode") != 0 or not isinstance(data.get("Data"), str):
        raise ValueError("Invalid fixture score response")
    scores: dict[str, FixtureScore] = {}
    unknown = st.UnknownTally("Kaynak pano")
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
        status = st.board_status(code)
        if status is None:
            unknown.add(code)
            continue
        home, away = fields[8:10]
        if status in ("finished", "live"):
            if not all(isinstance(value, int) and 0 <= value <= 30 for value in (home, away)):
                continue
        else:
            home = away = None
        ht_home = ht_away = None
        if len(fields) > 11 and status in ("finished", "live"):
            ht_h, ht_a = fields[10], fields[11]
            if isinstance(ht_h, int) and isinstance(ht_a, int) and 0 <= ht_h <= 30 and 0 <= ht_a <= 30:
                ht_home, ht_away = ht_h, ht_a
        # Durum kodu: 1 = 1. yarı, 2 = devre arası, 3 = 2. yarı, 4/5 = uzatma/penaltı.
        phase = _PHASES.get(code)
        minute = None
        if phase == "ht":
            minute = "HT"
            if ht_home is None:
                ht_home, ht_away = home, away
        scores[match_id] = FixtureScore(match_id, status, home, away, ht_home, ht_away, minute, phase)
    unknown.report()
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
