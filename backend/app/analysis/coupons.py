"""Kupondaş (Sprint 93): kupon oluşturma kuralları ve sonuçlandırma.

Kupon maçının oranı kaydedildiği anda kaynaktan (Bet365 via nowgoal) alınır ve dondurulur; sonradan değişmez.
Pazarlar: maç sonu 1X2, çifte şans, Asya Ü/A (sitenin ana çizgisi); ilk yarı 1X2 ve Asya Ü/A.
Asya Ü/A'da tam çizgi iade, çeyrek çizgi yarım kazanç/kayıp olabilir — `ht_value.total_return` ile aynı hesap.
Kupon getirisi = maçların geri dönüş katsayılarının çarpımı (kayıp 0, iade 1, kazanç oran).
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.analysis.ht_value import total_return

MARKETS = {
    ("ft", "result"): ("1", "X", "2"),
    ("ft", "dc"): ("1X", "12", "X2"),
    ("ft", "ou"): ("over", "under"),
    ("ht", "result"): ("1", "X", "2"),
    ("ht", "ou"): ("over", "under"),
}
MAX_LEGS = 20


def leg_return(period: str, market: str, selection: str, line: float | None, odds: float,
               ht: tuple[int, int] | None, ft: tuple[int, int] | None) -> tuple[str, float] | None:
    """(sonuç, 1 birim başına geri dönen). Skor henüz yoksa None."""
    score = ht if period == "ht" else ft
    if score is None or score[0] is None or score[1] is None:
        return None
    h, a = score
    if market in ("result", "dc"):
        actual = "1" if h > a else "2" if h < a else "X"
        won = actual == selection if market == "result" else actual in selection
        return ("hit", odds) if won else ("miss", 0.0)
    profit = total_return(h + a, line or 0.0, selection, odds)
    if profit >= odds - 1 - 1e-9:
        return "hit", odds
    if profit <= -1 + 1e-9:
        return "miss", 0.0
    if abs(profit) < 1e-9:
        return "push", 1.0
    return ("half_win" if profit > 0 else "half_loss"), round(1 + profit, 4)


def coupon_status(legs: list[dict]) -> dict:
    """Kupon özeti: toplam oran, durum (bekliyor / kazandı / kaybetti) ve gerçekleşen geri dönüş."""
    total = 1.0
    for leg in legs:
        total *= leg["odds"]
    factors = [leg.get("return_factor") for leg in legs]
    if any(f == 0 for f in factors if f is not None):
        status, realized = "lost", 0.0
    elif all(f is not None for f in factors):
        realized = 1.0
        for f in factors:
            realized *= f
        status = "won" if realized > 1 else "refund"
    else:
        status, realized = "pending", None
    return {"total_odds": round(total, 2), "status": status,
            "return": None if realized is None else round(realized, 3)}


async def settle_pending(session) -> int:
    """Skoru belli olan sonuçsuz kupon maçlarını sonuçlandırır (her maç bir kez). Yazılan sonuç sayısı."""
    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert

    from app.db.models import CouponLeg, CouponLegResult, Match

    rows = (await session.execute(
        select(CouponLeg.id, CouponLeg.period, CouponLeg.market, CouponLeg.selection, CouponLeg.line, CouponLeg.odds,
               Match.actual_ht_home, Match.actual_ht_away, Match.actual_ft_home, Match.actual_ft_away)
        .join(Match, Match.match_id == CouponLeg.match_id)
        .outerjoin(CouponLegResult, CouponLegResult.leg_id == CouponLeg.id)
        .where(CouponLegResult.leg_id.is_(None))
    )).all()
    written = 0
    for r in rows:
        ht = (r.actual_ht_home, r.actual_ht_away) if r.actual_ht_home is not None else None
        ft = (r.actual_ft_home, r.actual_ft_away) if r.actual_ft_home is not None else None
        result = leg_return(r.period, r.market, r.selection, r.line, r.odds, ht, ft)
        if result is None:
            continue
        score = ht if r.period == "ht" else ft
        res = await session.execute(insert(CouponLegResult).values(
            leg_id=r.id, outcome=result[0], return_factor=result[1], score=f"{score[0]}-{score[1]}",
            resolved_at=datetime.now(timezone.utc),
        ).on_conflict_do_nothing(index_elements=["leg_id"]))
        written += res.rowcount or 0
    return written
