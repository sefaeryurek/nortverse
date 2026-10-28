"""Kupondaş (Sprint 93): kupon oluşturma kuralları ve sonuçlandırma.

Kupon maçının oranı kaydedildiği anda kaynaktan (Bet365 via nowgoal) alınır ve dondurulur; sonradan değişmez.
Pazarlar: maç sonu 1X2, çifte şans, Asya Ü/A (sitenin ana çizgisi); ilk yarı 1X2 ve Asya Ü/A.
Asya Ü/A'da tam çizgi iade, çeyrek çizgi yarım kazanç/kayıp olabilir — `ht_value.total_return` ile aynı hesap.
Kupon getirisi = maçların geri dönüş katsayılarının çarpımı (kayıp 0, iade 1, kazanç oran).
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from app.analysis.ht_value import total_return

MARKETS = {
    ("ft", "result"): ("1", "X", "2"),
    ("ft", "dc"): ("1X", "12", "X2"),
    ("ft", "ou"): ("over", "under"),
    ("ht", "result"): ("1", "X", "2"),
    ("ht", "ou"): ("over", "under"),
}
MAX_LEGS = 10  # Sprint 94 J3 (20 fazlaydı)


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
        # Yarım kayıp toplamı 1'in altına düşürür: "iade" değil "kısmi kayıp" (J1; eskiden 0,5 getiri "iade" yazıyordu)
        if math.isclose(realized, 1.0, abs_tol=1e-6):
            status = "refund"
        else:
            status = "won" if realized > 1 else "partial_loss"
    else:
        status, realized = "pending", None
    return {"total_odds": round(total, 2), "status": status,
            "return": None if realized is None else round(realized, 3)}


VOID_AFTER = timedelta(hours=48)  # dondurulmuş başlama saatinden 48 saat sonra skor yoksa bacak iade
HT_VOID_AFTER = timedelta(hours=24)  # maç bitti ama İY skoru 24 saat gelmediyse İY bacağı iade


def leg_void_reason(*, deleted: bool, status: str | None, has_score: bool, kickoff: datetime | None,
                    now: datetime, ft_known: bool = False, period: str = "ft") -> str | None:
    """Oynanmayan maçın bacağı iade (katsayı 1,0) sayılır: silinmiş / iptal / 48 saat skor yok (Sprint 94 B2);
    İY bacağında maç sonucu var ama İY skoru 24 saattir yoksa (J5)."""
    if deleted:
        return "deleted"
    if has_score:
        return None
    if status == "abandoned":
        return "abandoned"
    if period == "ht" and ft_known and kickoff is not None and now - kickoff > HT_VOID_AFTER:
        return "no_ht_24h"
    if kickoff is not None and now - kickoff > VOID_AFTER:
        return "no_result_48h"
    return None


async def _ht_observations(session, match_ids: list[str]) -> dict[str, tuple[int, int]]:
    """Değişmez İY gözlemleri (devre arası / 2. yarı / maç sonu); her maç için en son gözlem."""
    from sqlalchemy import select

    from app.db.models import MatchHtObservation

    rows = (await session.execute(
        select(MatchHtObservation.match_id, MatchHtObservation.ht_home, MatchHtObservation.ht_away)
        .where(MatchHtObservation.match_id.in_(match_ids)).order_by(MatchHtObservation.id)
    )).all()
    return {r[0]: (r[1], r[2]) for r in rows}


async def settle_pending(session) -> int:
    """Skoru belli olan sonuçsuz kupon maçlarını sonuçlandırır (her maç bir kez); oynanmayan maç iade.

    Yazılan sonuç sayısı.
    """
    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert

    from app.analysis.match_status import fixture_statuses
    from app.db.models import CouponLeg, CouponLegResult, Match

    rows = (await session.execute(
        select(CouponLeg.id, CouponLeg.match_id, CouponLeg.period, CouponLeg.market, CouponLeg.selection,
               CouponLeg.line, CouponLeg.odds, CouponLeg.kickoff_time,
               Match.actual_ht_home, Match.actual_ht_away, Match.actual_ft_home, Match.actual_ft_away,
               Match.deleted_at)
        .join(Match, Match.match_id == CouponLeg.match_id)
        .outerjoin(CouponLegResult, CouponLegResult.leg_id == CouponLeg.id)
        .where(CouponLegResult.leg_id.is_(None))
    )).all()
    now = datetime.now(timezone.utc)
    ids = sorted({r.match_id for r in rows})
    statuses = await fixture_statuses(session, ids, now) if rows else {}
    ht_obs = await _ht_observations(session, ids) if rows else {}
    written = 0
    for r in rows:
        # İY bacağı devre arasında gözlenen İY skoruyla sonuçlanır (DB'ye sonuç saatler sonra geliyordu)
        ht = ((r.actual_ht_home, r.actual_ht_away) if r.actual_ht_home is not None else ht_obs.get(r.match_id))
        ft = (r.actual_ft_home, r.actual_ft_away) if r.actual_ft_home is not None else None
        score = ht if r.period == "ht" else ft
        void = leg_void_reason(deleted=r.deleted_at is not None, status=statuses.get(r.match_id),
                               has_score=score is not None, kickoff=r.kickoff_time, now=now,
                               ft_known=ft is not None, period=r.period)
        if void is not None:
            values = {"outcome": "void", "return_factor": 1.0, "score": None}
        else:
            result = leg_return(r.period, r.market, r.selection, r.line, r.odds, ht, ft)
            if result is None:
                continue
            values = {"outcome": result[0], "return_factor": result[1], "score": f"{score[0]}-{score[1]}"}
        res = await session.execute(insert(CouponLegResult).values(
            leg_id=r.id, resolved_at=now, **values,
        ).on_conflict_do_nothing(index_elements=["leg_id"]))
        written += res.rowcount or 0
    return written
