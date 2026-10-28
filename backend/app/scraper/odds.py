"""Bahis oranları (Bet365, nowgoal üzerinden) — İY değer kuralı ve kupondaş için (Sprint 93).

Kaynak: `{base}/ajax/SoccerAjax?type=14&t=20&id={id}&cid=8&h={0|1}` (düz HTTP, Playwright yok; kaynak
`live.nowgoal.life`'a yönlendirir, urllib takip eder). `h=1` ilk yarı, `h=0` maç sonu. Yanıt her pazar için
oran geçmişi döner (en yeni başta):
- `op` 1X2, ondalık oran: `u` ev, `g` beraberlik, `d` deplasman
- `ou` Asya Ü/A: `g` çizgi (0.75, 1.25 ...), `u` üst, `d` alt — Hong Kong oranı (ondalık = 1 + oran)
- `ah` Asya handikap: `g` handikap, `u` ev, `d` deplasman — Hong Kong oranı
Satırdaki `ht` boş değilse oran maç sırasında verilmiştir (dakika) → maç öncesi kararlarda kullanılmaz.
`close:true` satırı pazarın o anda kapandığını söyler (oranlar 0); en yeni satır kapalıysa pazar yoktur —
bir önceki açık satır kullanılmaz (Sprint 94: biten İY'nin son oranı "bedava" kazanç veriyordu).
Geçmiş yaklaşık son 9 ay için var (Şubat 2026 öncesi boş döner).
Özet uçtaki (t=10) `MatchState` canlıyken de bittikten sonra da 0 döner → maç durumu ondan okunmaz.
"""

from __future__ import annotations

import asyncio
import gzip
import json
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from app.config import SCRAPER

MARKETS = ("op", "ou", "ah")
LIVE_ROW_MAX_AGE = 90  # sn — maç içi satır bundan eskiyse güncel oran sayılmaz (kaynak golden sonra pazarı askıya alır)


def _num(value) -> float | None:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if x > 0 else None


def parse_odds(payload: str | bytes) -> dict[str, list[dict]] | None:
    """Ham yanıt → {"op"|"ou"|"ah": [{"mt": epoch, "pre": bool, "u", "g", "d"}...]} (en yeni başta).

    Kapalı satır `{"mt", "pre", "closed": True}` olarak tutulur (oran alanları yok).
    """
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
            if not isinstance(entry, dict) or not entry.get("mt"):
                continue
            row: dict = {"mt": int(entry["mt"]), "pre": not entry.get("ht")}
            if entry.get("ht"):  # maç içi: dakika ve o anki skor
                row["min"] = str(entry["ht"])
                row["score"] = f"{entry.get('hs', 0)}-{entry.get('gs', 0)}"
            if entry.get("close"):
                rows.append({**row, "closed": True})
                continue
            odds = entry.get("odds") or {}
            u, d = _num(odds.get("u")), _num(odds.get("d"))
            try:
                g = float(odds.get("g"))
            except (TypeError, ValueError):
                g = None
            if u is None or d is None or g is None:
                continue
            if market == "op" and g <= 0:
                continue
            rows.append({**row, "u": u, "g": g, "d": d})
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
                    if r["pre"] and not r.get("closed") and (limit is None or r["mt"] < limit)), None)
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
    """Güncel maç sonu özeti (t=10): 1X2 (ondalık), çifte şans ve Ü/A (Hong Kong → ondalık).

    Zaman damgası yoktur ve çifte şans maç içinde güncellenmez → sadece maç öncesi ve yedek olarak kullanılır.
    """
    try:
        body = json.loads(payload)
        data = body["Data"]
    except (ValueError, KeyError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    out: dict = {}
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


def _current_row(rows: list[dict] | None, now: float) -> dict | None:
    """Pazarın şu anki satırı: en yeni satır; kapalıysa ya da bayat maç içi satırsa pazar yok (None)."""
    if not rows:
        return None
    row = rows[0]
    if row.get("closed"):
        return None
    if not row["pre"] and now - row["mt"] > LIVE_ROW_MAX_AGE:
        return None
    return row


def build_current(summary: dict | None, ft_hist: dict | None, ht_hist: dict | None,
                  now: float | None = None) -> dict:
    """Kupon oranları: {"ft": {...}, "ht": {...}, "started": bool, "live": {"minute", "score", "mt"} | None}.

    - Maç sonu 1X2 ve Ü/A: MS geçmişinin (t=20 h=0) en yeni satırı; geçmiş alınamadıysa özet uç (t=10).
    - İlk yarı 1X2 ve Ü/A: İY geçmişinin (h=1) en yeni satırı.
    - Çifte şans: sadece özet uçta var ve maç içinde güncellenmiyor → maç başladıysa hiç verilmez.
    - Canlı dakika/skor: iki geçmişteki tüm pazarlar arasında en yeni (`mt` en büyük) maç içi satırdan.
    """
    now = time.time() if now is None else now
    summary = summary or {}
    out: dict = {"ft": {}, "ht": {}, "live": None, "started": False}
    histories = [h for h in (ft_hist, ht_hist) if h]
    in_play = [r for h in histories for rows in h.values() for r in rows if not r["pre"]]
    out["started"] = bool(in_play)
    if in_play:
        newest = max(in_play, key=lambda r: r["mt"])
        out["live"] = {"minute": newest.get("min"), "score": newest.get("score"), "mt": newest["mt"]}
    for period, hist in (("ft", ft_hist), ("ht", ht_hist)):
        if hist is None:
            continue
        op = _current_row(hist.get("op"), now)
        if op:
            out[period]["result"] = {"1": op["u"], "X": op["g"], "2": op["d"]}
        ou = _current_row(hist.get("ou"), now)
        if ou:
            out[period]["ou"] = {"line": ou["g"], "over": round(1 + ou["u"], 3), "under": round(1 + ou["d"], 3)}
    if ft_hist is None:
        out["ft"].update({k: summary[k] for k in ("result", "ou") if k in summary})
    if not out["started"] and "dc" in summary:
        out["ft"]["dc"] = summary["dc"]
    return out


async def current_odds(match_id: str) -> dict:
    """Kupon için şu anki oranlar (`build_current`). Üç istek paralel; biri düşse de diğerleriyle devam eder."""
    summary_raw, ft_hist, ht_hist = await asyncio.gather(
        asyncio.to_thread(_get, f"/ajax/SoccerAjax?type=14&t=10&id={match_id}&cid=8&h=0&r1=0&r2=0&r3=0", match_id),
        fetch_odds(match_id, half=False),
        fetch_odds(match_id, half=True),
        return_exceptions=True,
    )
    results = (summary_raw, ft_hist, ht_hist)
    if all(isinstance(r, BaseException) for r in results):
        raise results[0]
    summary = None if isinstance(summary_raw, BaseException) else parse_summary(summary_raw)
    return build_current(summary,
                         None if isinstance(ft_hist, BaseException) else ft_hist,
                         None if isinstance(ht_hist, BaseException) else ht_hist)


def _newest_mt(history: dict | None) -> dict[str, int]:
    return {m: rows[0]["mt"] for m, rows in (history or {}).items() if rows}


def should_replace_history(old: dict | None, new: dict | None) -> bool:
    """Yeni geçmiş eskisinin yerine yazılsın mı? Boş yanıt ya da bir pazarda daha eski veri iyi geçmişi ezmez."""
    if not new or not any(new.get(m) for m in MARKETS):
        return False
    if not old:
        return True
    old_mt, new_mt = _newest_mt(old), _newest_mt(new)
    return all(new_mt.get(m, 0) >= mt for m, mt in old_mt.items())


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
    if row is not None and not should_replace_history(row.history, history):
        # Boş / daha eski yanıt saklı geçmişi ezmez (Sprint 94 B7); ilk kayıt boş da olsa yazılır (tekrar denenmez)
        return row.history
    await session.execute(
        insert(MatchOdds).values(match_id=match_id, scope=scope, fetched_at=now, history=history)
        .on_conflict_do_update(index_elements=["match_id", "scope"],
                               set_={"fetched_at": now, "history": history})
    )
    return history
