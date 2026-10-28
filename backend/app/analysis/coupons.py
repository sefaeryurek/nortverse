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


_LIVE_STATE = {"hit": "winning", "half_win": "winning", "push": "level", "miss": "losing", "half_loss": "losing"}


def live_leg_state(period: str, market: str, selection: str, line: float | None, odds: float,
                   board) -> dict | None:
    """Sonuçlanmamış bacağın anlık durumu (Sprint 94 J8): maç şimdi bitse ne olurdu.

    `board`: canlı skor panosunun maç kaydı (`FixtureScore`). İY bacağında devre arası / 2. yarıda panonun İY skoru
    esas alınır (`period_over` — sonuç kesinleşti, sadece kayıt bekliyor). Başlamamış / ertelenmiş maç → None.
    """
    if board is None or board.status not in ("live", "finished", "finished_extra"):
        return None
    if board.home is None or board.away is None:
        return None
    ht_done = board.phase in ("ht", "2h") or board.status != "live"
    if period == "ht":
        score = (board.ht_home, board.ht_away) if ht_done else (board.home, board.away)
        if score[0] is None or score[1] is None:
            return None
        period_over = ht_done
    else:
        if board.status == "finished_extra":
            return None  # uzatmalı maçta panodaki skor 90. dakika mı belli değil
        score = (board.home, board.away)
        period_over = board.status == "finished"
    result = leg_return(period, market, selection, line, odds, score if period == "ht" else None,
                        score if period == "ft" else None)
    if result is None:
        return None
    return {"status": board.status, "minute": board.minute, "phase": board.phase,
            "score": f"{board.home}-{board.away}", "period_score": f"{score[0]}-{score[1]}",
            "state": _LIVE_STATE[result[0]], "period_over": period_over}


def live_summary(legs: list[dict]) -> str | None:
    """Bekleyen kuponun anlık özeti: "losing" (bir bacak şu an tutmuyor), "winning" (sonuçlanmamış her bacak canlı
    ve tutuyor/berabere), yoksa None (henüz başlamamış bacak var)."""
    pending = [leg for leg in legs if leg.get("return_factor") is None]
    states = [(leg.get("live") or {}).get("state") for leg in pending]
    if "losing" in states:
        return "losing"
    if pending and all(s in ("winning", "level") for s in states):
        return "winning"
    return None


def user_stats(coupons: list[dict]) -> list[dict]:
    """Kullanıcı karnesi / puan tablosu (Sprint 94 J9). `coupons`: her biri `username`, `legs` (outcome dahil) ve
    `coupon_status` alanları olan kuponlar.

    - Kâr: her kupona 1 birim; sonuçlanan kuponların geri dönüşleri toplamı − sonuçlanan kupon sayısı.
    - Bacak isabeti: tutan (hit + yarım kazanç) / sonuçlanan bacak (iade ve geçersiz hariç).
    Sıralama: kâr, sonra sonuçlanan kupon sayısı.
    """
    by_user: dict[str, dict] = {}
    for c in coupons:
        u = by_user.setdefault(c["username"], {
            "username": c["username"], "coupons": 0, "settled": 0, "won": 0, "lost": 0, "partial_loss": 0,
            "refund": 0, "pending": 0, "returned": 0.0, "legs_won": 0, "legs_decided": 0, "odds_sum": 0.0,
            "best_won_odds": None,
        })
        u["coupons"] += 1
        u["odds_sum"] += c["total_odds"]
        u[c["status"]] += 1
        if c["status"] != "pending":
            u["settled"] += 1
            u["returned"] += c["return"] or 0.0
        if c["status"] == "won" and (u["best_won_odds"] is None or c["total_odds"] > u["best_won_odds"]):
            u["best_won_odds"] = c["total_odds"]
        for leg in c["legs"]:
            if leg.get("outcome") in ("hit", "half_win", "miss", "half_loss"):
                u["legs_decided"] += 1
                u["legs_won"] += leg["outcome"] in ("hit", "half_win")
    out = []
    for u in by_user.values():
        profit = round(u["returned"] - u["settled"], 2)
        out.append({
            "username": u["username"], "coupons": u["coupons"], "settled": u["settled"], "pending": u["pending"],
            "won": u["won"], "lost": u["lost"], "partial_loss": u["partial_loss"], "refund": u["refund"],
            "profit": profit, "roi_pct": round(profit / u["settled"] * 100, 1) if u["settled"] else None,
            "leg_hit_pct": round(u["legs_won"] / u["legs_decided"] * 100, 1) if u["legs_decided"] else None,
            "legs_decided": u["legs_decided"],
            "avg_odds": round(u["odds_sum"] / u["coupons"], 2), "best_won_odds": u["best_won_odds"],
        })
    out.sort(key=lambda r: (-r["profit"], -r["settled"], r["username"]))
    return out


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

    Maç bilgisi `match_ref.load_match_refs`'ten: analizli maç `matches`'tan, bülten tabanlı bacak (Sprint 94 J6)
    bülten önbelleğinden. Yazılan sonuç sayısı.
    """
    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert

    from app.analysis.match_ref import load_match_refs
    from app.db.models import CouponLeg, CouponLegResult

    rows = (await session.execute(
        select(CouponLeg.id, CouponLeg.match_id, CouponLeg.period, CouponLeg.market, CouponLeg.selection,
               CouponLeg.line, CouponLeg.odds, CouponLeg.kickoff_time)
        .outerjoin(CouponLegResult, CouponLegResult.leg_id == CouponLeg.id)
        .where(CouponLegResult.leg_id.is_(None))
    )).all()
    if not rows:
        return 0
    now = datetime.now(timezone.utc)
    ids = sorted({r.match_id for r in rows})
    refs = await load_match_refs(session, ids, now)
    ht_obs = await _ht_observations(session, ids)
    written = 0
    for r in rows:
        ref = refs.get(r.match_id)
        # İY bacağı devre arasında gözlenen İY skoruyla sonuçlanır (DB'ye sonuç saatler sonra geliyordu)
        ht = (ref.ht if ref is not None else None) or ht_obs.get(r.match_id)
        ft = ref.ft if ref is not None else None
        score = ht if r.period == "ht" else ft
        void = leg_void_reason(deleted=bool(ref and ref.deleted), status=ref.status if ref else None,
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
