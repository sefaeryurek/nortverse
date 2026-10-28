"""Kupondaş (Sprint 93): anlık oranla kupon oluşturma ve ortak kupon akışı.

Kuponlar değişmez: oran kaydedildiği anda kaynaktan alınıp dondurulur, silinemez/düzenlenemez.
Herkes herkesin kuponunu görür (ortak sayfa); kupon sahibinin kullanıcı adı yazılır.

Sprint 94 (kullanıcı kararı K2): kupon **sadece maç öncesi** yazılır. Maç içi oranla kayıt, golü TV'de görüp
gol öncesi oranı kilitlemeye (past-posting) ve kapanmış İY'nin son oranını "bedava" kazanca açıktı.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Path, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.ratelimit import check_rate
from app.analysis.coupons import MARKETS, MAX_LEGS, coupon_status
from app.analysis.match_ref import MatchRef, load_match_refs, ref_from_fixture
from app.db.connection import get_session
from app.db.models import Coupon, CouponLeg, CouponLegResult, Match, User
from app.scraper.odds import current_odds

log = logging.getLogger(__name__)
router = APIRouter()

_ODDS_TTL = 30.0  # aynı maç için 30 sn içinde tekrar kaynağa gidilmez
_SAVE_MAX_AGE = 15.0  # kaydederken: kullanıcının son 15 sn'de gördüğü oran yeniden kullanılır, daha eskiyse yeniden çekilir
_odds_cache: dict[str, tuple[float, dict]] = {}
PREMATCH_ONLY = True  # K2: maç başladıysa hiçbir periyoda kupon yazılmaz
HT_CLOSE_AFTER = timedelta(minutes=47)   # pano/dakika bilinmese de başlamadan 47 dk sonra İY kapalı
FT_CLOSE_AFTER = timedelta(minutes=115)  # ... 115 dk sonra maç kapalı
_MINUTE_RE = re.compile(r"\s*(\d+)\s*(?:\+\s*(\d+))?")


def _odds_fresh(match_id: str, max_age: float = _ODDS_TTL) -> bool:
    cached = _odds_cache.get(match_id)
    return bool(cached) and time.monotonic() - cached[0] < max_age


async def _odds(match_id: str, *, max_age: float = _ODDS_TTL) -> dict:
    cached = _odds_cache.get(match_id)
    if cached and time.monotonic() - cached[0] < max_age:
        return cached[1]
    try:
        odds = await asyncio.wait_for(current_odds(match_id), timeout=28)  # tarayıcı isteği 30 sn
    except Exception:
        log.warning("Kupon oranı alınamadı [%s]", match_id, exc_info=True)
        raise HTTPException(503, "Oranlar şu an alınamadı, biraz sonra tekrar deneyin")
    if len(_odds_cache) > 300:
        _odds_cache.clear()
    _odds_cache[match_id] = (time.monotonic(), odds)
    return odds


def minute_value(minute: str | None) -> tuple[int, int] | None:
    """Kaynağın dakika metni → (dakika, uzatma). "45+2" → (45, 2); "HT" ve tanınmayan → None."""
    m = _MINUTE_RE.match(minute or "")
    if not m:
        return None
    return int(m.group(1)), int(m.group(2) or 0)


def closed_reason(*, period: str, now: datetime, kickoff: datetime | None, actual_ft: bool, actual_ht: bool,
                  odds: dict | None = None, board_status: str | None = None, board_phase: str | None = None,
                  board_minute: str | None = None, started_reason: str | None = None) -> str | None:
    """Bu periyoda artık kupon yazılamaz mı? Neden metni ya da None.

    Kaynakların hiçbiri tek başına güvenilir değil (oran ucunun durum alanı hep 0, DB skoru saatler sonra gelir,
    DB başlama saati yer tutucu olabilir) → hepsine bakılır, biri "kapalı" derse kapalı.
    - `board_*`: kaynak pano / canlı skor (status finished|live|postponed|abandoned, evre 1h|ht|2h, dakika)
    - `started_reason`: `prematch_v4.match_already_started` (sonuç, İY gözlemi, bültenin güncel saati/durumu)
    - `odds`: `scraper.odds.build_current` (maç içi oran satırı görüldüyse `started`, son dakika `live.minute`)
    """
    odds = odds or {}
    elapsed = (now - kickoff) if kickoff is not None else None
    if actual_ft or board_status == "finished" or started_reason == "result_known":
        return "Maç bitti"
    if board_status in ("postponed", "abandoned"):
        return "Maç ertelendi / iptal"
    if period == "ft" and elapsed is not None and elapsed >= FT_CLOSE_AFTER:
        return "Maç bitti"
    if period == "ht":
        minutes = [m for m in (board_minute, (odds.get("live") or {}).get("minute")) if m]
        ht_over = (actual_ht or started_reason == "ht_observed" or board_phase in ("ht", "2h")
                   or any(m.strip().upper() == "HT" for m in minutes)
                   or any((v := minute_value(m)) is not None and v[0] >= 45 for m in minutes)
                   or (elapsed is not None and elapsed >= HT_CLOSE_AFTER))
        if ht_over:
            return "İlk yarı bitti"
    if PREMATCH_ONLY and (started_reason is not None or odds.get("started") or board_status == "live"
                          or (elapsed is not None and elapsed >= timedelta(0))):
        return "Maç başladı — kupon sadece maç öncesi"
    return None


async def _match_state(session, match: MatchRef, now: datetime) -> dict:
    """Kapanış kararı için maçın durum kanıtları (pano + defter + bülten)."""
    from app.analysis.prematch_v4 import match_already_started
    from app.api.live_snapshot import get_live_snapshot

    started_reason = await match_already_started(session, match.match_id, now)
    board = None
    try:
        snapshot = await get_live_snapshot()
        board = snapshot.scores.get(match.match_id) if snapshot is not None else None
    except Exception:  # pano yoksa diğer kanıtlar yeter
        log.debug("Kupon kapanışı: pano okunamadı [%s]", match.match_id, exc_info=True)
    # Pano görmüyorsa bültenin son durumu (ertelendi / iptal) da kapatır
    board_status = board.status if board else (match.status if match.status in ("postponed", "abandoned") else None)
    return {"kickoff": match.kickoff_time, "actual_ft": match.ft is not None,
            "actual_ht": match.ht is not None, "started_reason": started_reason,
            "board_status": board_status, "board_phase": board.phase if board else None,
            "board_minute": board.minute if board else None}


async def _open_refs(session, match_ids: list[str], now: datetime) -> dict[str, MatchRef]:
    """Kupon için kullanılabilir maçlar (silinmiş DB kaydı kullanılmaz)."""
    return {mid: ref for mid, ref in (await load_match_refs(session, match_ids, now)).items() if not ref.deleted}


_UNAVAILABLE = ("finished", "finished_extra", "postponed", "abandoned")


@router.get("/api/coupon-matches")
async def coupon_matches(target_date: str = Query(..., alias="date", pattern=r"^\d{4}-\d{2}-\d{2}$")) -> list[dict]:
    """Kupona eklenebilecek maçlar: o günün bülteni (kupa dahil, Sprint 94 J6/K4) + veritabanındaki bitmemiş maçlar.

    Kaynağa hiç gitmez. Bitmiş / ertelenmiş / iptal maç listelenmez; başlamış maç `started` ile işaretlenir
    (kupon sadece maç öncesi — seçilemez). `analyzed`: maçın analizi var (ana + gölge lig).
    """
    from datetime import date as _date, timedelta

    from app.config import ISTANBUL_TZ
    from app.db.models import FixtureCache

    try:
        day = _date.fromisoformat(target_date)
    except ValueError:
        raise HTTPException(400, "Geçersiz tarih")
    start = datetime.combine(day, datetime.min.time(), ISTANBUL_TZ)
    async with get_session() as session:
        rows = (await session.execute(
            select(Match.match_id, Match.home_team, Match.away_team, Match.league_name, Match.kickoff_time)
            .where(Match.deleted_at.is_(None), Match.actual_ft_home.is_(None),
                   Match.kickoff_time >= start, Match.kickoff_time < start + timedelta(days=1))
        )).all()
        deleted = set((await session.execute(
            select(Match.match_id).where(Match.deleted_at.is_not(None), Match.kickoff_time >= start - timedelta(days=1),
                                         Match.kickoff_time < start + timedelta(days=2))
        )).scalars().all())
        fixture = await session.get(FixtureCache, day.isoformat())
    now = datetime.now(timezone.utc)
    out: dict[str, dict] = {}
    items = fixture.matches_json if fixture is not None and isinstance(fixture.matches_json, list) else []
    for item in items:
        if not isinstance(item, dict) or item.get("carried") or item.get("score_status") in _UNAVAILABLE:
            continue
        ref = ref_from_fixture(item)
        if ref is None or ref.match_id in deleted:
            continue
        out[ref.match_id] = {"match_id": ref.match_id, "home_team": ref.home_team, "away_team": ref.away_team,
                             "league_name": ref.league_name, "kickoff_time": ref.kickoff_time,
                             "started": item.get("score_status") == "live", "analyzed": False}
    for r in rows:  # analizli maç: takım/lig adı DB'den (kanonik)
        prev = out.get(r.match_id) or {}
        out[r.match_id] = {"match_id": r.match_id, "home_team": r.home_team, "away_team": r.away_team,
                           "league_name": r.league_name, "kickoff_time": r.kickoff_time or prev.get("kickoff_time"),
                           "started": bool(prev.get("started")), "analyzed": True}
    result = []
    for m in out.values():
        kickoff = m["kickoff_time"]
        m["started"] = m["started"] or bool(kickoff and kickoff <= now)
        m["kickoff_time"] = kickoff.isoformat() if kickoff else None
        result.append(m)
    far = "9999"
    result.sort(key=lambda m: (m["kickoff_time"] or far, m["league_name"] or "", m["home_team"]))
    return result


ODDS_RATE_PER_MIN = 20     # Sprint 94 E9: kullanıcı başına, KAYNAĞA GİDEN istek (önbellekten dönen sayılmaz) — her biri 3 HTTP
COUPON_RATE_PER_MIN = 6


@router.get("/api/odds/{match_id}")
async def get_odds(request: Request, match_id: str = Path(pattern=r"^[0-9]{1,12}$")) -> dict:
    """Kupon için güncel oranlar (maç sonu 1X2/ÇŞ/Ü-A, İY 1X2/Ü-A) — kapanmış periyot boş döner."""
    if not _odds_fresh(match_id):
        check_rate(request, "odds", ODDS_RATE_PER_MIN)
    now = datetime.now(timezone.utc)
    async with get_session() as session:
        match = (await _open_refs(session, [match_id], now)).get(match_id)
        if match is None:
            raise HTTPException(404, "Maç bulunamadı")
        state = await _match_state(session, match, now)
    pre = {p: closed_reason(period=p, now=now, **state) for p in ("ft", "ht")}
    odds = {} if all(pre.values()) else await _odds(match_id)  # başlamış maçta kaynağa hiç gidilmez
    out = {"match_id": match_id, "home_team": match.home_team, "away_team": match.away_team,
           "league_name": match.league_name, "live": None, "markets": {}}
    for period in ("ft", "ht"):
        closed = pre[period] or closed_reason(period=period, now=now, odds=odds, **state)
        out["markets"][period] = {"closed": closed, **({} if closed else odds.get(period, {}))}
    return out


class LegIn(BaseModel):
    match_id: str = Field(pattern=r"^[0-9]{1,12}$")
    period: str = Field(pattern=r"^(ft|ht)$")
    market: str = Field(pattern=r"^(result|dc|ou)$")
    selection: str = Field(max_length=10)
    # Kullanıcının ekranda gördüğü çizgi ve oran (J2): kayıt anındaki oran bundan kötüyse onay istenir
    line: float | None = None
    seen_odds: float | None = Field(default=None, gt=1.0, lt=1000.0)


class CouponIn(BaseModel):
    legs: list[LegIn] = Field(min_length=1, max_length=MAX_LEGS)
    note: str | None = Field(default=None, max_length=200)


ODDS_TOLERANCE = 0.03          # oran %3'ten fazla kötüleştiyse kullanıcı onayı (409 odds_changed)
_FETCH_LIMIT = asyncio.Semaphore(3)  # kayıt anında kaynağa en fazla 3 eşzamanlı istek
_IDEMPOTENCY_TTL = 600.0
_idempotency: dict[tuple[int, str], tuple[float, dict]] = {}


def odds_change(leg: LegIn, market: dict, price: float) -> dict | None:
    """Kullanıcının gördüğü çizgi/oranla kayıt anındaki arasında kabul edilemez fark var mı?"""
    line = market.get("line") if leg.market == "ou" else None
    line_moved = leg.market == "ou" and leg.line is not None and line is not None and abs(line - leg.line) > 1e-9
    worse = leg.seen_odds is not None and price < leg.seen_odds * (1 - ODDS_TOLERANCE)
    if not (line_moved or worse):
        return None
    return {"match_id": leg.match_id, "period": leg.period, "market": leg.market, "selection": leg.selection,
            "old_odds": leg.seen_odds, "new_odds": price, "old_line": leg.line, "new_line": line}


def _remember(user_id: int, key: str | None, response: dict) -> dict:
    if key:
        now = time.monotonic()
        for k in [k for k, (t, _) in _idempotency.items() if now - t > _IDEMPOTENCY_TTL]:
            _idempotency.pop(k, None)
        _idempotency[(user_id, key)] = (now, response)
    return response


async def _odds_for_save(match: MatchRef) -> dict:
    async with _FETCH_LIMIT:
        try:
            return await _odds(match.match_id, max_age=_SAVE_MAX_AGE)
        except HTTPException:
            # Hangi maçta olduğu söylensin (eskiden tüm kupon genel 503 dönüyordu)
            raise HTTPException(503, f"{match.home_team} - {match.away_team}: oranlar şu an alınamadı, "
                                     "bu maçı çıkarıp tekrar deneyin")


@router.post("/api/coupons")
async def create_coupon(body: CouponIn, request: Request) -> dict:
    """Kuponu o anki oranlarla kaydeder (oran kaynaktan yeniden alınır; istemcinin gördüğü oran sadece kıyas için).

    - Maç başına tek seçim (K3): aynı maçtan iki bacak korelasyonlu (MS1 + ÇŞ 1X getiriyi şişirir).
    - `Idempotency-Key` başlığı: çift tıklama / ağ tekrarı aynı kuponu ikinci kez yazmaz (10 dk).
    - Çizgi değiştiyse ya da oran %3'ten fazla kötüleştiyse 409 `odds_changed` + yeni değerler (kullanıcı onaylar).
    """
    user = getattr(request.state, "user", None)
    if user is None or user.id <= 0:
        raise HTTPException(401, "Kupon için giriş gerekli")
    idem_key = (request.headers.get("idempotency-key") or "").strip()[:80] or None
    if idem_key and (user.id, idem_key) in _idempotency:
        return _idempotency[(user.id, idem_key)][1]
    check_rate(request, "coupon", COUPON_RATE_PER_MIN)  # tekrar gönderilen aynı istek sayılmaz
    seen = set()
    for leg in body.legs:
        if leg.selection not in MARKETS.get((leg.period, leg.market), ()):
            raise HTTPException(400, f"Geçersiz seçim: {leg.period}/{leg.market}/{leg.selection}")
        if leg.match_id in seen:
            raise HTTPException(400, "Bir maçtan kupona tek seçim eklenebilir")
        seen.add(leg.match_id)
    match_ids = sorted(seen)
    now = datetime.now(timezone.utc)
    async with get_session() as session:
        matches = await _open_refs(session, match_ids, now)
        if len(matches) != len(match_ids):
            raise HTTPException(404, "Kupondaki bir maç bulunamadı")
        states = {m: await _match_state(session, matches[m], now) for m in match_ids}
    # Önce kaynağa gitmeden kapanış (başlama saati, pano, bülten) — başlamış maç için oran hiç çekilmez
    for leg in body.legs:
        closed = closed_reason(period=leg.period, now=now, **states[leg.match_id])
        if closed:
            match = matches[leg.match_id]
            raise HTTPException(409, f"{match.home_team} - {match.away_team}: {closed}")
    odds_by_match = dict(zip(match_ids, await asyncio.gather(*(_odds_for_save(matches[m]) for m in match_ids))))
    now = datetime.now(timezone.utc)
    legs = []
    changes = []
    for leg in body.legs:
        match, odds = matches[leg.match_id], odds_by_match[leg.match_id]
        closed = closed_reason(period=leg.period, now=now, odds=odds, **states[leg.match_id])
        if closed:
            raise HTTPException(409, f"{match.home_team} - {match.away_team}: {closed}")
        market = (odds.get(leg.period) or {}).get(leg.market) or {}
        price = market.get(leg.selection)
        if not price or price <= 1.0:
            raise HTTPException(409, f"{match.home_team} - {match.away_team}: bu seçim için oran yok")
        change = odds_change(leg, market, float(price))
        if change:
            changes.append({**change, "home_team": match.home_team, "away_team": match.away_team})
        live = odds.get("live") or {}
        legs.append(CouponLeg(
            match_id=match.match_id, home_team=match.home_team, away_team=match.away_team,
            league_name=match.league_name, kickoff_time=match.kickoff_time, period=leg.period, market=leg.market,
            selection=leg.selection, line=market.get("line") if leg.market == "ou" else None, odds=float(price),
            odds_at=now, live_minute=live.get("minute"), live_score=live.get("score"), source=match.source,
        ))
    if changes:
        raise HTTPException(409, {"code": "odds_changed", "message": "Oranlar değişti, yeni oranları onaylayın",
                                  "changes": changes})
    async with get_session() as session:
        coupon = Coupon(user_id=user.id, note=(body.note or "").strip() or None)
        session.add(coupon)
        await session.flush()
        for leg in legs:
            leg.coupon_id = coupon.id
            session.add(leg)
        coupon_id = coupon.id
    saved = [{"match_id": leg.match_id, "period": leg.period, "market": leg.market, "selection": leg.selection,
              "line": leg.line, "odds": leg.odds} for leg in legs]
    return _remember(user.id, idem_key, {"id": coupon_id, "legs": saved})


@router.get("/api/coupons")
async def list_coupons(
    request: Request,
    scope: str = Query("all", pattern=r"^(all|mine)$"),
    limit: int = Query(50, ge=1, le=200),
    before: int | None = Query(None, description="Bu kupon numarasından eskiler (sayfalama)"),
) -> dict:
    user = getattr(request.state, "user", None)
    async with get_session() as session:
        stmt = (select(Coupon.id, Coupon.created_at, Coupon.note, Coupon.user_id, User.username)
                .join(User, User.id == Coupon.user_id).order_by(Coupon.id.desc()).limit(limit))
        if scope == "mine":
            stmt = stmt.where(Coupon.user_id == (user.id if user else -1))
        if before:
            stmt = stmt.where(Coupon.id < before)
        coupons = (await session.execute(stmt)).all()
        ids = [c.id for c in coupons]
        legs = (await session.execute(
            select(CouponLeg, CouponLegResult.outcome, CouponLegResult.return_factor, CouponLegResult.score)
            .outerjoin(CouponLegResult, CouponLegResult.leg_id == CouponLeg.id)
            .where(CouponLeg.coupon_id.in_(ids)).order_by(CouponLeg.id)
        )).all() if ids else []
    by_coupon: dict[int, list[dict]] = {}
    for leg, outcome, factor, score in legs:
        by_coupon.setdefault(leg.coupon_id, []).append({
            "match_id": leg.match_id, "home_team": leg.home_team, "away_team": leg.away_team,
            "league_name": leg.league_name, "kickoff_time": leg.kickoff_time.isoformat() if leg.kickoff_time else None,
            "period": leg.period, "market": leg.market, "selection": leg.selection, "line": leg.line,
            "odds": leg.odds, "live_minute": leg.live_minute, "live_score": leg.live_score,
            "outcome": outcome, "return_factor": factor, "score": score,
        })
    out = []
    for c in coupons:
        c_legs = by_coupon.get(c.id, [])
        out.append({"id": c.id, "created_at": c.created_at.isoformat(), "note": c.note, "username": c.username,
                    "mine": bool(user and c.user_id == user.id), "legs": c_legs, **coupon_status(c_legs)})
    return {"coupons": out}
