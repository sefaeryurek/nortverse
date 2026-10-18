"""Günlük değerlendirme endpoint'i — saklı pattern'lerin sonuçla karşılaştırması.

Saklı pattern'ler kickoff anındaki arşivle hesaplanır (`persist.pattern_as_of`), yani sızıntısızdır;
ama recompute sonrası "bugünkü algoritma o gün ne derdi" değeridir — o gün gösterilen değil.
Gerçek performans tahmin defterinden (`/api/performance/*`) ölçülür.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.analysis.evaluation import (
    EvalAccumulator,
    evaluate_pattern,
    pct,
    brier_avg,
)
from app.analysis.league_priors import load_prior_book
from app.api.schemas import (
    DailyEvaluation,
    EvaluationSummary,
    MatchEvaluation,
    PatternEvaluation,
)
from app.config import ANALYSIS, ISTANBUL_TZ
from app.db.connection import get_session
from app.db.models import Match

router = APIRouter()


def _core_to_schema(pat) -> PatternEvaluation | None:
    if pat is None:
        return None
    return PatternEvaluation(
        match_count=pat.match_count,
        result_pick=pat.result_pick,
        result_pct=pat.result_pct,
        result_hit=pat.result_hit,
        result_margin=pat.result_margin,
        is_confident=pat.is_confident,
        over_25_pick=pat.over_25_pick,
        over_25_pct=pat.over_25_pct,
        over_25_hit=pat.over_25_hit,
        btts_pick=pat.btts_pick,
        btts_pct=pat.btts_pct,
        btts_hit=pat.btts_hit,
        brier_score=pat.brier_score,
    )


@router.get("/api/evaluation", response_model=DailyEvaluation)
async def daily_evaluation(
    target_date: Optional[str] = Query(None, alias="date"),
) -> DailyEvaluation:
    """Belirli bir günün maçları için tahmin vs sonuç karşılaştırması."""
    if target_date:
        try:
            req_date = date.fromisoformat(target_date)
        except ValueError:
            raise HTTPException(400, "Geçersiz tarih formatı. Kullanım: YYYY-MM-DD")
    else:
        req_date = datetime.now(ISTANBUL_TZ).date()

    day_start = datetime(req_date.year, req_date.month, req_date.day, tzinfo=ISTANBUL_TZ)
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

    priors = await load_prior_book(day_start)
    matches: list[MatchEvaluation] = []
    summary_score_hit = 0
    score_list_evaluated = 0

    acc_b, acc_c, acc_d = EvalAccumulator(), EvalAccumulator(), EvalAccumulator()

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

        eval_kwargs = dict(
            actual_result=actual_result, actual_over_25=actual_over_25,
            actual_btts=actual_btts, min_matches=ANALYSIS.eval_min_matches,
            league_name=row.league_name, priors=priors,
        )
        pat_b = evaluate_pattern(row.pattern_ft_b, **eval_kwargs)
        pat_c = evaluate_pattern(row.pattern_ft_c, **eval_kwargs)
        pat_d = evaluate_pattern(row.pattern_ft_d, **eval_kwargs)

        acc_b.accumulate(pat_b)
        acc_c.accumulate(pat_c)
        acc_d.accumulate(pat_d)

        if all_scores:
            score_list_evaluated += 1
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
            pattern_b=_core_to_schema(pat_b),
            pattern_c=_core_to_schema(pat_c),
            pattern_d=_core_to_schema(pat_d),
            score_list=all_scores,
            score_list_hit=score_hit,
        ))

    total = len(matches)

    summary = EvaluationSummary(
        total_matches=total,
        evaluated=acc_b.evaluated,
        result_hit=acc_b.result_hit,
        result_hit_pct=pct(acc_b.result_hit, acc_b.evaluated),
        over_25_hit=acc_b.over_hit,
        over_25_hit_pct=pct(acc_b.over_hit, acc_b.evaluated),
        btts_hit=acc_b.btts_hit,
        btts_hit_pct=pct(acc_b.btts_hit, acc_b.evaluated),
        score_list_hit=summary_score_hit,
        score_list_hit_pct=pct(summary_score_hit, score_list_evaluated),
        score_list_evaluated=score_list_evaluated,
        evaluated_c=acc_c.evaluated,
        c_result_hit=acc_c.result_hit,
        c_result_hit_pct=pct(acc_c.result_hit, acc_c.evaluated),
        c_over_25_hit=acc_c.over_hit,
        c_over_25_hit_pct=pct(acc_c.over_hit, acc_c.evaluated),
        c_btts_hit=acc_c.btts_hit,
        c_btts_hit_pct=pct(acc_c.btts_hit, acc_c.evaluated),
        evaluated_d=acc_d.evaluated,
        d_result_hit=acc_d.result_hit,
        d_result_hit_pct=pct(acc_d.result_hit, acc_d.evaluated),
        d_over_25_hit=acc_d.over_hit,
        d_over_25_hit_pct=pct(acc_d.over_hit, acc_d.evaluated),
        d_btts_hit=acc_d.btts_hit,
        d_btts_hit_pct=pct(acc_d.btts_hit, acc_d.evaluated),
        confident_evaluated=acc_b.confident_evaluated,
        confident_result_hit=acc_b.confident_result_hit,
        confident_result_hit_pct=pct(acc_b.confident_result_hit, acc_b.confident_evaluated),
        confident_c_evaluated=acc_c.confident_evaluated,
        confident_c_result_hit=acc_c.confident_result_hit,
        confident_c_result_hit_pct=pct(acc_c.confident_result_hit, acc_c.confident_evaluated),
        confident_d_evaluated=acc_d.confident_evaluated,
        confident_d_result_hit=acc_d.confident_result_hit,
        confident_d_result_hit_pct=pct(acc_d.confident_result_hit, acc_d.confident_evaluated),
        brier_result_b=brier_avg(acc_b.brier_sum, acc_b.evaluated),
        brier_result_c=brier_avg(acc_c.brier_sum, acc_c.evaluated),
        brier_result_d=brier_avg(acc_d.brier_sum, acc_d.evaluated),
    )

    return DailyEvaluation(
        date=req_date.isoformat(),
        summary=summary,
        matches=matches,
    )
