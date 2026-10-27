"""Maç olayları: gol dakikaları ve kırmızı kartlar (Sprint 93 — anlık maç modeli).

Kaynak: `{base}/match/live-{id}` sayfasındaki `#teamEventDiv_detail table#eventsTable` (sunucu HTML'i,
Playwright gerekmez). Her olay satırı: ev ikonu | dakika (b.score, "27'" / "90+4'") | dep ikonu;
gol satırında o anki skor (`span.ky_score`) da yazar → hangi takımın attığı skordan doğrulanır
(kendi kalesine gol de doğru tarafa yazılır).
"""

from __future__ import annotations

import asyncio
import re
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from app.config import SCRAPER

_MINUTE_RE = re.compile(r"(\d+)\s*(?:\+\s*(\d+))?")
_SCORE_RE = re.compile(r"(\d+)\s*-\s*(\d+)")


def _kind(text: str) -> str | None:
    t = text.lower()
    if "miss" in t:
        return None                      # kaçan penaltı gol değil
    if "own" in t:
        return "own_goal"
    if "penalty" in t:
        return "penalty"
    if "goal" in t:
        return "goal"
    if "red" in t or "two yellow" in t or "second yellow" in t:
        return "red"
    return None


def _minute(text: str) -> tuple[int, int] | None:
    m = _MINUTE_RE.search(text or "")
    return (int(m.group(1)), int(m.group(2) or 0)) if m else None


def parse_goal_events(html: str) -> list[dict] | None:
    """Gol ve kırmızı kart olayları, zaman sırasıyla. Olay tablosu yoksa None (sayfa yapısı değişmiş)."""
    soup = BeautifulSoup(html, "lxml")
    table = soup.select_one("#teamEventDiv_detail table#eventsTable")
    if table is None:
        return None
    events: list[dict] = []
    for row in table.find_all("tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) != 5:
            continue
        minute = _minute(cells[2].get_text(" ", strip=True))
        if minute is None:
            continue
        for side, icon_cell, text_cell in (("home", cells[1], cells[0]), ("away", cells[3], cells[4])):
            tip = icon_cell.select_one("span.icontips")
            kind = _kind(tip.get("txt", "")) if tip else None
            if kind is None:
                continue
            event = {"minute": minute[0], "extra": minute[1], "side": side, "kind": kind}
            score = text_cell.select_one("span.ky_score")
            m = _SCORE_RE.search(score.get_text(" ", strip=True)) if score else None
            if m:
                event["score"] = [int(m.group(1)), int(m.group(2))]
            events.append(event)
    # Sayfa en son olaydan geriye listeler → zaman sırasına çevir ("45+2" 46'dan önce gelir)
    events.sort(key=lambda e: (e["minute"], e["extra"]))
    return _fix_sides(events)


def _fix_sides(events: list[dict]) -> list[dict]:
    """Gol tarafını skor ilerlemesinden düzeltir (kendi kalesine gol ikonu diğer takım tarafında olabilir)."""
    prev = (0, 0)
    for e in events:
        if e["kind"] == "red" or "score" not in e:
            continue
        h, a = e["score"]
        if (h, a) == (prev[0] + 1, prev[1]):
            e["side"] = "home"
        elif (h, a) == (prev[0], prev[1] + 1):
            e["side"] = "away"
        prev = (h, a)
    return events


def goals_total(events: list[dict]) -> tuple[int, int]:
    goals = [e for e in events if e["kind"] != "red"]
    return sum(e["side"] == "home" for e in goals), sum(e["side"] == "away" for e in goals)


def events_match_score(events: list[dict] | None, ft: tuple[int | None, int | None]) -> bool:
    """Olaylardan çıkan skor kayıtlı maç sonucuyla aynı mı (değilse kalibrasyonda kullanılmaz)."""
    if events is None or ft[0] is None or ft[1] is None:
        return False
    return goals_total(events) == (ft[0], ft[1])


async def fetch_goal_events(match_id: str) -> list[dict] | None:
    """Tek maçın olaylarını çeker (urllib; kaynak yönlendirmesini kendisi takip eder)."""
    def fetch() -> bytes:
        request = Request(
            f"{SCRAPER.base_url}/match/live-{match_id}",
            headers={"User-Agent": SCRAPER.user_agent, "Referer": SCRAPER.base_url + "/"},
        )
        with urlopen(request, timeout=30) as response:
            return response.read()

    html = (await asyncio.to_thread(fetch)).decode("utf-8", errors="replace")
    return parse_goal_events(html)
