"""Günlük değerlendirme endpoint'i — tahmin vs sonuç karşılaştırması."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.api.schemas import (
    DailyEvaluation,
    EvaluationSummary,
    MatchEvaluation,
    PatternEvaluation,
)
from app.config import ANALYSIS
from app.db.connection import get_session
from app.db.models import Match

router = APIRouter()

# Beraberlik (X) sistemde neredeyse hiç tahmin edilmiyor — %8.1 tahmin oranına
# karşılık gerçek beraberlik oranı %24.6 (7,949 maçlık backtest). Pattern
# matching çoğunluk sınıfını (ev sahibi galibiyeti %44.4) doğal olarak
# kayırıyor. Bayesian shrinkage ile küçük örneklemli tahminler popülasyon
# taban oranlarına doğru çekilir — örneklem büyüdükçe shrinkage azalır.
BASE_RESULT = {"1": 44.4, "X": 24.6, "2": 30.9}
SHRINKAGE = 0.3  # taban orana doğru maksimum %30 çekiş


def _evaluate_pattern(
    pattern_data: dict | None,
    actual_result: str,
    actual_over_25: bool,
    actual_btts: bool,
    min_matches: int = 1,
) -> PatternEvaluation | None:
    if not pattern_data or not isinstance(pattern_data, dict):
        return None
    mc = pattern_data.get("match_count", 0)
    if mc < min_matches:
        return None

    pcts = {
        "1": pattern_data.get("result_1_pct", 0) or 0,
        "X": pattern_data.get("result_x_pct", 0) or 0,
        "2": pattern_data.get("result_2_pct", 0) or 0,
    }

    # Shrinkage: pattern yüzdelerini taban oranlara doğru karıştır.
    # Az veri (küçük mc) → daha fazla shrinkage; çok veri → ham argmax korunur.
    shrink = SHRINKAGE / (1 + mc / 20)
    adjusted_pcts = {
        k: pcts[k] * (1 - shrink) + BASE_RESULT[k] * shrink
        for k in ("1", "X", "2")
    }
    result_pick = max(adjusted_pcts, key=lambda k: adjusted_pcts[k])
    result_hit = result_pick == actual_result

    over_pct = pattern_data.get("ust_25_pct", 0) or 0
    over_pick = over_pct > ANALYSIS.over_25_threshold
    over_hit = over_pick == actual_over_25

    btts_pct = pattern_data.get("kg_var_pct", 0) or 0
    btts_pick = btts_pct > ANALYSIS.btts_threshold
    btts_hit = btts_pick == actual_btts

    return PatternEvaluation(
        match_count=mc,
        result_pick=result_pick,
        result_pct=round(pcts[result_pick], 1),
        result_hit=result_hit,
        over_25_pick="Üst" if over_pick else "Alt",
        over_25_pct=round(over_pct if over_pick else (100 - over_pct), 1),
        over_25_hit=over_hit,
        btts_pick="KG Var" if btts_pick else "KG Yok",
        btts_pct=round(btts_pct if btts_pick else (100 - btts_pct), 1),
        btts_hit=btts_hit,
    )


def _pct(hit: int, total: int) -> float:
    return round(hit / total * 100, 1) if total > 0 else 0.0


@router.get("/api/evaluation", response_model=DailyEvaluation)
async def daily_evaluation(
    target_date: Optional[str] = Query(None, alias="date"),
) -> DailyEvaluation:
    """Belirli bir günün maçları için tahmin vs sonuç karşılaştırması."""
    istanbul = timezone(timedelta(hours=3))

    if target_date:
        try:
            req_date = date.fromisoformat(target_date)
        except ValueError:
            raise HTTPException(400, "Geçersiz tarih formatı. Kullanım: YYYY-MM-DD")
    else:
        req_date = datetime.now(istanbul).date()

    day_start = datetime(req_date.year, req_date.month, req_date.day, tzinfo=istanbul)
    day_end = day_start + timedelta(days=1)

    async with get_session() as session:
        stmt = (
            select(
                Match.match_id, Match.home_team, Match.away_team,
                Match.league_code, Match.league_name, Match.kickoff_time,
                Match.actual_ft_home, Match.actual_ft_away,
                Match.actual_ht_home, Match.actual_ht_away,
                Match.pattern_ft_b, Match.pattern_ft_c,
                Match.ft_scores_1, Match.ft_scores_x, Match.ft_scores_2,
            )
            .where(
                Match.deleted_at.is_(None),
                Match.kickoff_time >= day_start,
                Match.kickoff_time < day_end,
                Match.actual_ft_home.isnot(None),
                Match.actual_ft_away.isnot(None),
            )
            .order_by(Match.kickoff_time)
        )
        rows = (await session.execute(stmt)).all()

    matches: list[MatchEvaluation] = []
    summary_result_hit = 0
    summary_over_hit = 0
    summary_btts_hit = 0
    summary_score_hit = 0
    evaluated = 0
    evaluated_c = 0
    summary_c_result_hit = 0
    summary_c_over_hit = 0
    summary_c_btts_hit = 0

    for row in rows:
        ft_h, ft_a = row.actual_ft_home, row.actual_ft_away
        ht_h, ht_a = row.actual_ht_home, row.actual_ht_away

        if ft_h > ft_a:
            actual_result = "1"
        elif ft_h == ft_a:
            actual_result = "X"
        else:
            actual_result = "2"

        actual_over_25 = (ft_h + ft_a) > 2
        actual_btts = ft_h > 0 and ft_a > 0

        actual_ft_str = f"{ft_h}-{ft_a}"
        actual_ht_str = f"{ht_h}-{ht_a}" if ht_h is not None and ht_a is not None else None

        all_scores = list(row.ft_scores_1 or []) + list(row.ft_scores_x or []) + list(row.ft_scores_2 or [])
        score_hit = actual_ft_str in all_scores

        pat_b = _evaluate_pattern(
            row.pattern_ft_b, actual_result, actual_over_25, actual_btts,
            min_matches=ANALYSIS.eval_min_matches,
        )
        pat_c = _evaluate_pattern(
            row.pattern_ft_c, actual_result, actual_over_25, actual_btts,
            min_matches=ANALYSIS.eval_min_matches,
        )

        if pat_b is not None:
            evaluated += 1
            if pat_b.result_hit:
                summary_result_hit += 1
            if pat_b.over_25_hit:
                summary_over_hit += 1
            if pat_b.btts_hit:
                summary_btts_hit += 1

        if pat_c is not None:
            evaluated_c += 1
            if pat_c.result_hit:
                summary_c_result_hit += 1
            if pat_c.over_25_hit:
                summary_c_over_hit += 1
            if pat_c.btts_hit:
                summary_c_btts_hit += 1

        if score_hit:
            summary_score_hit += 1

        kickoff_str = None
        if row.kickoff_time:
            kickoff_str = row.kickoff_time.isoformat() if hasattr(row.kickoff_time, "isoformat") else str(row.kickoff_time)

        matches.append(MatchEvaluation(
            match_id=row.match_id,
            home_team=row.home_team or "",
            away_team=row.away_team or "",
            league_code=row.league_code,
            league_name=row.league_name,
            kickoff_time=kickoff_str,
            actual_ft=actual_ft_str,
            actual_ht=actual_ht_str,
            result=actual_result,
            over_25=actual_over_25,
            btts=actual_btts,
            pattern_b=pat_b,
            pattern_c=pat_c,
            score_list=all_scores,
            score_list_hit=score_hit,
        ))

    total = len(matches)
    summary = EvaluationSummary(
        total_matches=total,
        evaluated=evaluated,
        result_hit=summary_result_hit,
        result_hit_pct=_pct(summary_result_hit, evaluated),
        over_25_hit=summary_over_hit,
        over_25_hit_pct=_pct(summary_over_hit, evaluated),
        btts_hit=summary_btts_hit,
        btts_hit_pct=_pct(summary_btts_hit, evaluated),
        score_list_hit=summary_score_hit,
        score_list_hit_pct=_pct(summary_score_hit, total),
        evaluated_c=evaluated_c,
        c_result_hit=summary_c_result_hit,
        c_result_hit_pct=_pct(summary_c_result_hit, evaluated_c),
        c_over_25_hit=summary_c_over_hit,
        c_over_25_hit_pct=_pct(summary_c_over_hit, evaluated_c),
        c_btts_hit=summary_c_btts_hit,
        c_btts_hit_pct=_pct(summary_c_btts_hit, evaluated_c),
    )

    return DailyEvaluation(
        date=req_date.isoformat(),
        summary=summary,
        matches=matches,
    )
