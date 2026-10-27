"""Kupondaş (Sprint 93): anlık oranla kupon oluşturma ve ortak kupon akışı.

Kuponlar değişmez: oran kaydedildiği anda kaynaktan alınıp dondurulur, silinemez/düzenlenemez.
Herkes herkesin kuponunu görür (ortak sayfa); kupon sahibinin kullanıcı adı yazılır.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Path, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.analysis.coupons import MARKETS, MAX_LEGS, coupon_status, settle_pending
from app.db.connection import get_session
from app.db.models import Coupon, CouponLeg, CouponLegResult, Match, User
from app.scraper.odds import current_odds

log = logging.getLogger(__name__)
router = APIRouter()

_ODDS_TTL = 30.0  # aynı maç için 30 sn içinde tekrar kaynağa gidilmez
_odds_cache: dict[str, tuple[float, dict]] = {}
_FINISHED_STATES = {-1, -10, -11, -12, -13, -14}  # nowgoal: bitti / iptal / ertelendi vb.


async def _odds(match_id: str, *, fresh: bool = False) -> dict:
    cached = _odds_cache.get(match_id)
    if cached and not fresh and time.monotonic() - cached[0] < _ODDS_TTL:
        return cached[1]
    try:
        odds = await asyncio.wait_for(current_odds(match_id), timeout=20)
    except Exception:
        log.warning("Kupon oranı alınamadı [%s]", match_id, exc_info=True)
        raise HTTPException(503, "Oranlar şu an alınamadı, biraz sonra tekrar deneyin")
    if len(_odds_cache) > 300:
        _odds_cache.clear()
    _odds_cache[match_id] = (time.monotonic(), odds)
    return odds


def _closed_reason(odds: dict, match: Match, period: str) -> str | None:
    """Bu periyoda artık kupon yazılamaz mı (maç / ilk yarı bitti)."""
    state = odds.get("state")
    if match.actual_ft_home is not None or (isinstance(state, int) and state in _FINISHED_STATES):
        return "Maç bitti"
    if period == "ht":
        minute = ((odds.get("live") or {}).get("minute") or "").strip().upper()
        if (match.actual_ht_home is not None or state in (2, 3) or minute == "HT"
                or (minute.isdigit() and int(minute) > 45)):
            return "İlk yarı bitti"
    return None


@router.get("/api/odds/{match_id}")
async def get_odds(match_id: str = Path(pattern=r"^[0-9]{1,12}$")) -> dict:
    """Kupon için güncel oranlar (maç sonu 1X2/ÇŞ/Ü-A, İY 1X2/Ü-A) — kapanmış periyot boş döner."""
    async with get_session() as session:
        match = (await session.execute(
            select(Match).where(Match.match_id == match_id, Match.deleted_at.is_(None))
        )).scalar_one_or_none()
    if match is None:
        raise HTTPException(404, "Maç bulunamadı")
    odds = await _odds(match_id)
    out = {"match_id": match_id, "home_team": match.home_team, "away_team": match.away_team,
           "league_name": match.league_name, "live": odds.get("live"), "markets": {}}
    for period in ("ft", "ht"):
        closed = _closed_reason(odds, match, period)
        out["markets"][period] = {"closed": closed, **({} if closed else odds.get(period, {}))}
    return out


class LegIn(BaseModel):
    match_id: str = Field(pattern=r"^[0-9]{1,12}$")
    period: str = Field(pattern=r"^(ft|ht)$")
    market: str = Field(pattern=r"^(result|dc|ou)$")
    selection: str = Field(max_length=10)


class CouponIn(BaseModel):
    legs: list[LegIn] = Field(min_length=1, max_length=MAX_LEGS)
    note: str | None = Field(default=None, max_length=200)


@router.post("/api/coupons")
async def create_coupon(body: CouponIn, request: Request) -> dict:
    """Kuponu o anki oranlarla kaydeder (oran kaynaktan yeniden alınır; istemcinin gördüğü oran kullanılmaz)."""
    user = getattr(request.state, "user", None)
    if user is None or user.id <= 0:
        raise HTTPException(401, "Kupon için giriş gerekli")
    seen = set()
    for leg in body.legs:
        if leg.selection not in MARKETS.get((leg.period, leg.market), ()):
            raise HTTPException(400, f"Geçersiz seçim: {leg.period}/{leg.market}/{leg.selection}")
        key = (leg.match_id, leg.period, leg.market)
        if key in seen:
            raise HTTPException(400, "Aynı maçta aynı pazar iki kez seçilemez")
        seen.add(key)
    match_ids = sorted({leg.match_id for leg in body.legs})
    async with get_session() as session:
        matches = {m.match_id: m for m in (await session.execute(
            select(Match).where(Match.match_id.in_(match_ids), Match.deleted_at.is_(None))
        )).scalars().all()}
    if len(matches) != len(match_ids):
        raise HTTPException(404, "Kupondaki bir maç bulunamadı")
    odds_by_match = dict(zip(match_ids, await asyncio.gather(*(_odds(m, fresh=True) for m in match_ids))))
    now = datetime.now(timezone.utc)
    legs = []
    for leg in body.legs:
        match, odds = matches[leg.match_id], odds_by_match[leg.match_id]
        closed = _closed_reason(odds, match, leg.period)
        if closed:
            raise HTTPException(409, f"{match.home_team} - {match.away_team}: {closed}")
        market = (odds.get(leg.period) or {}).get(leg.market) or {}
        price = market.get(leg.selection)
        if not price or price <= 1.0:
            raise HTTPException(409, f"{match.home_team} - {match.away_team}: bu seçim için oran yok")
        live = odds.get("live") or {}
        legs.append(CouponLeg(
            match_id=match.match_id, home_team=match.home_team, away_team=match.away_team,
            league_name=match.league_name, kickoff_time=match.kickoff_time, period=leg.period, market=leg.market,
            selection=leg.selection, line=market.get("line") if leg.market == "ou" else None, odds=float(price),
            odds_at=now, live_minute=live.get("minute"), live_score=live.get("score"),
        ))
    async with get_session() as session:
        coupon = Coupon(user_id=user.id, note=(body.note or "").strip() or None)
        session.add(coupon)
        await session.flush()
        for leg in legs:
            leg.coupon_id = coupon.id
            session.add(leg)
        coupon_id = coupon.id
    return {"id": coupon_id}


@router.get("/api/coupons")
async def list_coupons(
    request: Request,
    scope: str = Query("all", pattern=r"^(all|mine)$"),
    limit: int = Query(50, ge=1, le=200),
    before: int | None = Query(None, description="Bu kupon numarasından eskiler (sayfalama)"),
) -> dict:
    user = getattr(request.state, "user", None)
    async with get_session() as session:
        await settle_pending(session)
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
