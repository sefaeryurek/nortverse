"""Günlük değerlendirme endpoint'i — tahmin vs sonuç karşılaştırması."""

from __future__ import annotations

import math
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

BASE_RESULT = {"1": 45.1, "X": 24.8, "2": 30.0, "ou25": 53.0, "btts": 53.3}

# Lig bazlı taban oranları — 20,770 skorlu maçtan hesaplandı (2026-10-10).
LEAGUE_BASE_RATES: dict[str, dict[str, float]] = {
    "German Bundesliga": {"1": 44.9, "X": 24.8, "2": 30.3, "ou25": 63.3, "btts": 60.8},
    "Turkish Super Lig": {"1": 46.0, "X": 24.5, "2": 29.5, "ou25": 57.3, "btts": 56.2},
    "English Premier League": {"1": 45.2, "X": 24.6, "2": 30.3, "ou25": 52.9, "btts": 52.0},
    "Dutch Eredivisie": {"1": 43.9, "X": 24.8, "2": 31.2, "ou25": 61.3, "btts": 57.7},
    "Spanish La Liga": {"1": 46.9, "X": 24.9, "2": 28.2, "ou25": 49.9, "btts": 51.9},
    "Italy Serie A": {"1": 43.4, "X": 25.6, "2": 31.0, "ou25": 51.2, "btts": 53.2},
    "French Ligue 1": {"1": 44.4, "X": 23.3, "2": 32.3, "ou25": 55.4, "btts": 55.6},
}


def _get_base_rates(league_name: str | None) -> dict[str, float]:
    if league_name:
        for key, rates in LEAGUE_BASE_RATES.items():
            if key.lower() in league_name.lower():
                return rates
    return BASE_RESULT


def _evaluate_pattern(
    pattern_data: dict | None,
    actual_result: str,
    actual_over_25: bool,
    actual_btts: bool,
    min_matches: int = 1,
    league_name: str | None = None,
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

    base_rates = _get_base_rates(league_name)
    shrink = ANALYSIS.result_shrinkage / (1 + mc / ANALYSIS.shrinkage_half_life)

    adjusted_pcts: dict[str, float] = {}
    for k in ("1", "X", "2"):
        raw_p = max(1.0, min(99.0, pcts[k])) / 100.0
        base_p = base_rates[k] / 100.0
        raw_logit = math.log(raw_p / (1 - raw_p))
        base_logit = math.log(base_p / (1 - base_p))
        adj_logit = raw_logit * (1 - shrink) + base_logit * shrink
        adjusted_pcts[k] = 1 / (1 + math.exp(-adj_logit)) * 100

    sorted_vals = sorted(adjusted_pcts.values(), reverse=True)
    result_margin = sorted_vals[0] - sorted_vals[1]
    is_confident = result_margin >= ANALYSIS.result_min_margin

    result_pick = max(adjusted_pcts, key=lambda k: adjusted_pcts[k])
    result_hit = result_pick == actual_result

    ou_base = base_rates.get("ou25", ANALYSIS.over_25_base_rate)
    btts_base = base_rates.get("btts", ANALYSIS.btts_base_rate)

    over_pct = pattern_data.get("ust_25_pct", 0) or 0
    over_raw_p = max(1.0, min(99.0, over_pct)) / 100.0
    over_base_p = ou_base / 100.0
    over_adj_logit = (
        math.log(over_raw_p / (1 - over_raw_p)) * (1 - shrink)
        + math.log(over_base_p / (1 - over_base_p)) * shrink
    )
    over_adjusted = 1 / (1 + math.exp(-over_adj_logit)) * 100
    over_pick = over_adjusted > ou_base
    over_hit = over_pick == actual_over_25

    btts_pct = pattern_data.get("kg_var_pct", 0) or 0
    btts_raw_p = max(1.0, min(99.0, btts_pct)) / 100.0
    btts_base_p = btts_base / 100.0
    btts_adj_logit = (
        math.log(btts_raw_p / (1 - btts_raw_p)) * (1 - shrink)
        + math.log(btts_base_p / (1 - btts_base_p)) * shrink
    )
    btts_adjusted = 1 / (1 + math.exp(-btts_adj_logit)) * 100
    btts_pick = btts_adjusted > btts_base
    btts_hit = btts_pick == actual_btts

    brier = sum(
        (adjusted_pcts[k] / 100.0 - (1.0 if k == actual_result else 0.0)) ** 2
        for k in ("1", "X", "2")
    )

    return PatternEvaluation(
        match_count=mc,
        result_pick=result_pick,
        result_pct=round(pcts[result_pick], 1),
        result_hit=result_hit,
        result_margin=round(result_margin, 1),
        is_confident=is_confident,
        over_25_pick="Üst" if over_pick else "Alt",
        over_25_pct=round(over_pct if over_pick else (100 - over_pct), 1),
        over_25_hit=over_hit,
        btts_pick="KG Var" if btts_pick else "KG Yok",
        btts_pct=round(btts_pct if btts_pick else (100 - btts_pct), 1),
        btts_hit=btts_hit,
        brier_score=round(brier, 4),
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
                Match.pattern_ft_b, Match.pattern_ft_c, Match.pattern_ft_d,
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
    evaluated_d = 0
    summary_d_result_hit = 0
    summary_d_over_hit = 0
    summary_d_btts_hit = 0
    confident_evaluated = 0
    confident_result_hit = 0
    confident_c_evaluated = 0
    confident_c_result_hit = 0
    confident_d_evaluated = 0
    confident_d_result_hit = 0
    brier_sum_b = 0.0
    brier_sum_c = 0.0
    brier_sum_d = 0.0

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
            league_name=row.league_name,
        )
        pat_c = _evaluate_pattern(
            row.pattern_ft_c, actual_result, actual_over_25, actual_btts,
            min_matches=ANALYSIS.eval_min_matches,
            league_name=row.league_name,
        )
        pat_d = _evaluate_pattern(
            row.pattern_ft_d, actual_result, actual_over_25, actual_btts,
            min_matches=ANALYSIS.eval_min_matches,
            league_name=row.league_name,
        )

        if pat_b is not None:
            evaluated += 1
            brier_sum_b += pat_b.brier_score
            if pat_b.result_hit:
                summary_result_hit += 1
            if pat_b.over_25_hit:
                summary_over_hit += 1
            if pat_b.btts_hit:
                summary_btts_hit += 1
            if pat_b.is_confident:
                confident_evaluated += 1
                if pat_b.result_hit:
                    confident_result_hit += 1

        if pat_c is not None:
            evaluated_c += 1
            brier_sum_c += pat_c.brier_score
            if pat_c.result_hit:
                summary_c_result_hit += 1
            if pat_c.over_25_hit:
                summary_c_over_hit += 1
            if pat_c.btts_hit:
                summary_c_btts_hit += 1
            if pat_c.is_confident:
                confident_c_evaluated += 1
                if pat_c.result_hit:
                    confident_c_result_hit += 1

        if pat_d is not None:
            evaluated_d += 1
            brier_sum_d += pat_d.brier_score
            if pat_d.result_hit:
                summary_d_result_hit += 1
            if pat_d.over_25_hit:
                summary_d_over_hit += 1
            if pat_d.btts_hit:
                summary_d_btts_hit += 1
            if pat_d.is_confident:
                confident_d_evaluated += 1
                if pat_d.result_hit:
                    confident_d_result_hit += 1

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
            pattern_d=pat_d,
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
        evaluated_d=evaluated_d,
        d_result_hit=summary_d_result_hit,
        d_result_hit_pct=_pct(summary_d_result_hit, evaluated_d),
        d_over_25_hit=summary_d_over_hit,
        d_over_25_hit_pct=_pct(summary_d_over_hit, evaluated_d),
        d_btts_hit=summary_d_btts_hit,
        d_btts_hit_pct=_pct(summary_d_btts_hit, evaluated_d),
        confident_evaluated=confident_evaluated,
        confident_result_hit=confident_result_hit,
        confident_result_hit_pct=_pct(confident_result_hit, confident_evaluated),
        confident_c_evaluated=confident_c_evaluated,
        confident_c_result_hit=confident_c_result_hit,
        confident_c_result_hit_pct=_pct(confident_c_result_hit, confident_c_evaluated),
        confident_d_evaluated=confident_d_evaluated,
        confident_d_result_hit=confident_d_result_hit,
        confident_d_result_hit_pct=_pct(confident_d_result_hit, confident_d_evaluated),
        brier_result_b=round(brier_sum_b / evaluated, 4) if evaluated > 0 else None,
        brier_result_c=round(brier_sum_c / evaluated_c, 4) if evaluated_c > 0 else None,
        brier_result_d=round(brier_sum_d / evaluated_d, 4) if evaluated_d > 0 else None,
    )

    return DailyEvaluation(
        date=req_date.isoformat(),
        summary=summary,
        matches=matches,
    )
