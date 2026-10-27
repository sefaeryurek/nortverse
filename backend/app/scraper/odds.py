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
            row = {"mt": int(entry["mt"]), "pre": not entry.get("ht"), "u": u, "g": g, "d": d}
            if entry.get("ht"):  # maç içi: dakika ve o anki skor
                row["min"] = str(entry["ht"])
                row["score"] = f"{entry.get('hs', 0)}-{entry.get('gs', 0)}"
            rows.append(row)
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


def market_options(odds: dict) -> list[dict]:
    """Oranlardan seçenekler: oran + bahis payı çıkarılmış olasılık (yüzde). Pazar içinde olasılıklar toplamı 100."""
    out: list[dict] = []
    op = odds.get("op")
    if op:
        inv = {k: 1 / op[k] for k in ("1", "X", "2")}
        total = sum(inv.values())
        out += [{"market": "result", "selection": k, "line": None, "odds": op[k],
                 "pct": round(100 * inv[k] / total, 1), "margin_pct": round(100 * (total - 1), 1)} for k in inv]
    ou = odds.get("ou")
    if ou:
        inv = {"over": 1 / ou["over"], "under": 1 / ou["under"]}
        total = sum(inv.values())
        out += [{"market": "ou", "selection": k, "line": ou["line"], "odds": ou[k],
                 "pct": round(100 * inv[k] / total, 1), "margin_pct": round(100 * (total - 1), 1)} for k in inv]
    return out


def _get(path: str, referer_id: str) -> bytes:
    """Kaynaktan ham yanıt (yönlendirilen adres hatırlanır; gzip açılır)."""
    global _resolved_base
    base = _resolved_base or SCRAPER.base_url
    request = Request(f"{base}{path}", headers={"User-Agent": SCRAPER.user_agent,
                                                 "Referer": f"{base}/oddscomp/{referer_id}"})
    with urlopen(request, timeout=20) as response:
        final = urlsplit(response.geturl())
        _resolved_base = f"{final.scheme}://{final.netloc}"
        body = response.read()
    # Kaynak istemese de gzip gönderiyor
    return gzip.decompress(body) if body[:2] == bytes((0x1F, 0x8B)) else body


async def fetch_odds(match_id: str, *, half: bool) -> dict[str, list[dict]] | None:
    """Tek maçın oran geçmişi (İY için half=True)."""
    path = f"/ajax/SoccerAjax?type=14&t=20&id={match_id}&cid=8&h={1 if half else 0}&r1=0&r2=0&r3=0"
    return parse_odds(await asyncio.to_thread(_get, path, match_id))


def parse_summary(payload: str | bytes) -> dict | None:
    """Güncel maç sonu oranları (t=10): 1X2 (ondalık), çifte şans ve Ü/A (Hong Kong → ondalık) + maç durumu."""
    try:
        body = json.loads(payload)
        data = body["Data"]
    except (ValueError, KeyError, TypeError):
        return None
    out: dict = {"state": body.get("MatchState")}
    op = data.get("op") or {}
    u, g, d = _num(op.get("u")), _num(op.get("g")), _num(op.get("d"))
    if u and g and d:
        out["result"] = {"1": u, "X": g, "2": d}
    dc = data.get("double") or {}
    u, g, d = _num(dc.get("u")), _num(dc.get("g")), _num(dc.get("d"))
    if u and g and d:
        out["dc"] = {"1X": round(1 + u, 3), "12": round(1 + g, 3), "X2": round(1 + d, 3)}
    ou = data.get("ou") or {}
    u, d = _num(ou.get("u")), _num(ou.get("d"))
    try:
        line = float(ou.get("g"))
    except (TypeError, ValueError):
        line = None
    if u and d and line is not None:
        out["ou"] = {"line": line, "over": round(1 + u, 3), "under": round(1 + d, 3)}
    return out


async def current_odds(match_id: str) -> dict:
    """Kupon için şu anki oranlar: {"ft": {...}, "ht": {...}, "live": {"minute", "score"} | None, "state"}.

    Maç sonu: özet uç (canlıyken canlı oran). İlk yarı: İY geçmişinin en son satırı (canlıysa canlı).
    """
    summary_raw, ht_hist = await asyncio.gather(
        asyncio.to_thread(_get, f"/ajax/SoccerAjax?type=14&t=10&id={match_id}&cid=8&h=0&r1=0&r2=0&r3=0", match_id),
        fetch_odds(match_id, half=True),
    )
    summary = parse_summary(summary_raw) or {}
    out: dict = {"state": summary.get("state"), "ft": {k: summary[k] for k in ("result", "dc", "ou") if k in summary},
                 "ht": {}, "live": None}
    latest = {m: (ht_hist or {}).get(m, [None])[0] if (ht_hist or {}).get(m) else None for m in ("op", "ou")}
    if latest["op"]:
        r = latest["op"]
        out["ht"]["result"] = {"1": r["u"], "X": r["g"], "2": r["d"]}
    if latest["ou"]:
        r = latest["ou"]
        out["ht"]["ou"] = {"line": r["g"], "over": round(1 + r["u"], 3), "under": round(1 + r["d"], 3)}
    live_row = next((r for r in (latest["op"], latest["ou"]) if r and not r["pre"]), None)
    if live_row:
        out["live"] = {"minute": live_row.get("min"), "score": live_row.get("score")}
    return out


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
