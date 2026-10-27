"""Bahis oranları (Bet365, nowgoal üzerinden) — İY değer kuralı ve kupondaş için (Sprint 93).

Kaynak: `{base}/ajax/SoccerAjax?type=14&t=20&id={id}&cid=8&h={0|1}` (düz HTTP, Playwright yok; kaynak
`live.nowgoal.life`'a yönlendirir, urllib takip eder). `h=1` ilk yarı, `h=0` maç sonu. Yanıt her pazar için
oran geçmişi döner (en yeni başta):
- `op` 1X2, ondalık oran: `u` ev, `g` beraberlik, `d` deplasman
- `ou` Asya Ü/A: `g` çizgi (0.75, 1.25 ...), `u` üst, `d` alt — Hong Kong oranı (ondalık = 1 + oran)
- `ah` Asya handikap: `g` handikap, `u` ev, `d` deplasman — Hong Kong oranı
Satırdaki `ht` boş değilse oran maç sırasında verilmiştir (dakika) → maç öncesi kararlarda kullanılmaz.
Geçmiş yaklaşık son 9 ay için var (Şubat 2026 öncesi boş döner).
"""

from __future__ import annotations

import asyncio
import gzip
import json
from datetime import datetime, timezone
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from app.config import SCRAPER

MARKETS = ("op", "ou", "ah")


def _num(value) -> float | None:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if x > 0 else None


def parse_odds(payload: str | bytes) -> dict[str, list[dict]] | None:
    """Ham yanıt → {"op"|"ou"|"ah": [{"mt": epoch, "pre": bool, "u", "g", "d"}...]} (en yeni başta)."""
    try:
        data = json.loads(payload)["Data"]
    except (ValueError, KeyError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    out: dict[str, list[dict]] = {}
    for market in MARKETS:
        rows = []
        for entry in data.get(market) or []:
            odds = entry.get("odds") or {}
            u, d = _num(odds.get("u")), _num(odds.get("d"))
            try:
                g = float(odds.get("g"))
            except (TypeError, ValueError):
                g = None
            if u is None or d is None or g is None or not entry.get("mt"):
                continue
            if market == "op" and g <= 0:
                continue
            rows.append({"mt": int(entry["mt"]), "pre": not entry.get("ht"), "u": u, "g": g, "d": d})
        rows.sort(key=lambda r: -r["mt"])
        out[market] = rows
    return out


def latest_prematch(history: dict | None, before: datetime | None = None) -> dict[str, dict]:
    """Her pazarın maç öncesi son oranı (kickoff verilirse ondan önceki son = kapanış), ondalık oranlarla.

    {"op": {"1": 2.3, "X": 2.5, "2": 4.33, "mt": ...},
     "ou": {"line": 1.25, "over": 1.9, "under": 1.9, "mt": ...},
     "ah": {"line": 0.25, "home": 1.88, "away": 1.93, "mt": ...}}
    """
    if not history:
        return {}
    limit = before.timestamp() if before is not None else None
    out: dict[str, dict] = {}
    for market in MARKETS:
        row = next((r for r in history.get(market) or []
                    if r["pre"] and (limit is None or r["mt"] < limit)), None)
        if row is None:
            continue
        if market == "op":
            out["op"] = {"1": row["u"], "X": row["g"], "2": row["d"], "mt": row["mt"]}
        elif market == "ou":
            out["ou"] = {"line": row["g"], "over": round(1 + row["u"], 3), "under": round(1 + row["d"], 3),
                         "mt": row["mt"]}
        else:
            out["ah"] = {"line": row["g"], "home": round(1 + row["u"], 3), "away": round(1 + row["d"], 3),
                         "mt": row["mt"]}
    return out


# Kaynak her isteği başka alan adına yönlendiriyor (yavaş DNS + ikinci bağlantı) → ilk yönlendirilen adres hatırlanır
_resolved_base: str | None = None


async def fetch_odds(match_id: str, *, half: bool) -> dict[str, list[dict]] | None:
    """Tek maçın oran geçmişi (İY için half=True)."""
    def fetch() -> bytes:
        global _resolved_base
        base = _resolved_base or SCRAPER.base_url
        request = Request(
            f"{base}/ajax/SoccerAjax?type=14&t=20&id={match_id}&cid=8&h={1 if half else 0}&r1=0&r2=0&r3=0",
            headers={"User-Agent": SCRAPER.user_agent, "Referer": f"{base}/oddscomp/{match_id}"},
        )
        with urlopen(request, timeout=20) as response:
            final = urlsplit(response.geturl())
            _resolved_base = f"{final.scheme}://{final.netloc}"
            body = response.read()
        # Kaynak istemese de gzip gönderiyor
        return gzip.decompress(body) if body[:2] == bytes((0x1F, 0x8B)) else body

    return parse_odds(await asyncio.to_thread(fetch))


async def load_or_fetch(session, match_id: str, *, half: bool, max_age_s: int) -> dict | None:
    """DB'deki oran geçmişi yeterince tazeyse onu, değilse kaynaktan çekip DB'ye yazar."""
    from sqlalchemy.dialects.postgresql import insert

    from app.db.models import MatchOdds

    scope = "ht" if half else "ft"
    row = await session.get(MatchOdds, (match_id, scope))
    now = datetime.now(timezone.utc)
    if row is not None and (now - row.fetched_at).total_seconds() < max_age_s:
        return row.history
    history = await fetch_odds(match_id, half=half)
    if history is None:
        return row.history if row is not None else None
    await session.execute(
        insert(MatchOdds).values(match_id=match_id, scope=scope, fetched_at=now, history=history)
        .on_conflict_do_update(index_elements=["match_id", "scope"],
                               set_={"fetched_at": now, "history": history})
    )
    return history
