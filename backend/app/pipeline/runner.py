"""Pipeline: Fetch → Analyze → Persist.

Tek browser context ile tüm maçları işler, sonuçları Supabase'e yazar.
Idempotent: aynı match_id için tekrar çalıştırılırsa günceller (upsert).
"""

import logging
from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.analysis import analyze_match, check_match_filters
from app.db.connection import get_session
from app.db.models import Match
from app.models import MatchAnalysisResult, MatchRawData
from app.scraper.browser import browser_context
from app.scraper.fixture import fetch_fixture
from app.scraper.match_detail import fetch_match_detail

log = logging.getLogger(__name__)


def _result_to_row(r: MatchAnalysisResult, raw: MatchRawData | None = None) -> dict:
    """MatchAnalysisResult → matches tablosu satırı."""
    return {
        "match_id": r.match_id,
        "home_team": r.home_team,
        "away_team": r.away_team,
        "league_code": r.league_code,
        "season": r.season,
        "analyzed_at": r.analyzed_at,
        "ht_scores_1": r.ht.scores_1,
        "ht_scores_x": r.ht.scores_x,
        "ht_scores_2": r.ht.scores_2,
        "ht_all_ratios": r.ht.all_ratios,
        "h2_scores_1": r.half2.scores_1,
        "h2_scores_x": r.half2.scores_x,
        "h2_scores_2": r.half2.scores_2,
        "h2_all_ratios": r.half2.all_ratios,
        "ft_scores_1": r.ft.scores_1,
        "ft_scores_x": r.ft.scores_x,
        "ft_scores_2": r.ft.scores_2,
        "ft_all_ratios": r.ft.all_ratios,
        "actual_ft_home": raw.actual_ft_home if raw else None,
        "actual_ft_away": raw.actual_ft_away if raw else None,
        "actual_ht_home": raw.actual_ht_home if raw else None,
        "actual_ht_away": raw.actual_ht_away if raw else None,
    }


async def _upsert(result: MatchAnalysisResult, raw: MatchRawData | None = None) -> None:
    """Analiz sonucunu DB'ye yaz; zaten varsa güncelle."""
    row = _result_to_row(result, raw)
    stmt = (
        insert(Match)
        .values(**row)
        .on_conflict_do_update(index_elements=["match_id"], set_=row)
    )
    async with get_session() as session:
        await session.execute(stmt)


async def run_pipeline(
    target_date: Optional[date] = None,
    only_hot: bool = True,
) -> dict:
    """Hot maçları çek, analiz et, Supabase'e yaz.

    Dönüş: {"analyzed": N, "skipped": N, "errors": N}
    """
    stats = {"analyzed": 0, "skipped": 0, "errors": 0}

    async with browser_context() as ctx:
        fixtures = await fetch_fixture(target_date=target_date, only_hot=only_hot, ctx=ctx)
        log.info("Pipeline başladı: %d maç işlenecek", len(fixtures))

        for fixture in fixtures:
            mid = fixture.match_id
            try:
                raw = await fetch_match_detail(mid, ctx=ctx)
                check = check_match_filters(raw)

                if not check.passed:
                    log.info("Atlandı [%s]: %s", mid, check.reason.value)
                    stats["skipped"] += 1
                    continue

                result = analyze_match(raw)
                await _upsert(result, raw)
                stats["analyzed"] += 1
                log.info(
                    "Kaydedildi [%s]: %s vs %s | FT 3.5+: %s",
                    mid,
                    result.home_team,
                    result.away_team,
                    result.ft.scores_1 + result.ft.scores_x + result.ft.scores_2,
                )

            except Exception as e:
                log.error("Hata [%s]: %s", mid, e, exc_info=True)
                stats["errors"] += 1

    log.info(
        "Pipeline tamamlandı: %d analiz, %d atlandı, %d hata",
        stats["analyzed"],
        stats["skipped"],
        stats["errors"],
    )
    return stats
