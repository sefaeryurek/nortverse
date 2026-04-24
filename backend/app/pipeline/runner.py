"""Pipeline: Fetch → Analyze → Persist.

Tek browser context ile tüm maçları işler, sonuçları Supabase'e yazar.
Idempotent: aynı match_id için tekrar çalıştırılırsa günceller (upsert).
"""

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, update as sa_update
from sqlalchemy.dialects.postgresql import insert

from app.analysis import analyze_match, check_match_filters
from app.analysis.persist import compute_all_patterns
from app.db.connection import get_session
from app.db.models import Match
from app.models import MatchAnalysisResult, MatchRawData
from app.scraper.browser import browser_context
from app.scraper.fixture import fetch_fixture
from app.scraper.match_detail import fetch_match_detail

log = logging.getLogger(__name__)


def _result_to_row(
    r: MatchAnalysisResult,
    raw: MatchRawData | None = None,
    patterns: dict[str, dict | None] | None = None,
) -> dict:
    """MatchAnalysisResult → matches tablosu satırı.

    patterns parametresi compute_all_patterns()'in çıktısıdır; verilirse
    pattern_*_b/c kolonları da satıra eklenir.
    """
    row = {
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
        "kickoff_time": raw.kickoff_time if raw else None,
        "actual_ft_home": raw.actual_ft_home if raw else None,
        "actual_ft_away": raw.actual_ft_away if raw else None,
        "actual_ht_home": raw.actual_ht_home if raw else None,
        "actual_ht_away": raw.actual_ht_away if raw else None,
        "actual_h2_home": raw.actual_h2_home if raw else None,
        "actual_h2_away": raw.actual_h2_away if raw else None,
    }
    if patterns:
        row.update(patterns)
    return row


async def _upsert(
    result: MatchAnalysisResult,
    raw: MatchRawData | None = None,
    patterns: dict[str, dict | None] | None = None,
) -> None:
    """Analiz sonucunu (varsa pattern'lerle) DB'ye yaz; zaten varsa güncelle."""
    row = _result_to_row(result, raw, patterns)
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
                # Pattern B/C'leri hesapla (exclude_match_id=mid ile self-exclusion)
                patterns = await compute_all_patterns(
                    match_id=mid,
                    ht_scores=(result.ht.scores_1, result.ht.scores_x, result.ht.scores_2),
                    h2_scores=(result.half2.scores_1, result.half2.scores_x, result.half2.scores_2),
                    ft_scores=(result.ft.scores_1, result.ft.scores_x, result.ft.scores_2),
                    ft_ratios=result.ft.all_ratios,
                )
                await _upsert(result, raw, patterns)
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


async def update_results(target_date: Optional[date] = None) -> dict:
    """DB'deki maçların gerçek sonuçlarını günceller — Katman A/B/C verisi dokunulmaz.

    Gece çalıştırılır: sabah pipeline'ının kaydettiği maçları tekrar scrape eder,
    actual_ft/ht skorlarını doldurur → /sonuclar sayfasında görünür hale gelir.
    """
    istanbul_tz = timezone(timedelta(hours=3))

    if target_date:
        d = target_date
    else:
        now_ist = datetime.now(istanbul_tz)
        # Gece 00:00–04:00 İstanbul'da çalışırsa önceki günün maçlarını güncelle
        d = (now_ist - timedelta(days=1)).date() if now_ist.hour < 4 else now_ist.date()

    day_start = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=istanbul_tz)
    day_end = datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=istanbul_tz)

    async with get_session() as session:
        match_ids = list(
            (await session.execute(
                select(Match.match_id)
                .where(Match.kickoff_time >= day_start, Match.kickoff_time <= day_end)
            )).scalars().all()
        )

    log.info("Sonuç güncellemesi: %s için %d maç bulundu", d, len(match_ids))
    stats = {"updated": 0, "not_finished": 0, "errors": 0}

    async with browser_context() as ctx:
        for match_id in match_ids:
            try:
                raw = await fetch_match_detail(match_id, ctx=ctx)
                if raw.actual_ft_home is None:
                    stats["not_finished"] += 1
                    continue

                async with get_session() as session:
                    await session.execute(
                        sa_update(Match)
                        .where(Match.match_id == match_id)
                        .values(
                            actual_ft_home=raw.actual_ft_home,
                            actual_ft_away=raw.actual_ft_away,
                            actual_ht_home=raw.actual_ht_home,
                            actual_ht_away=raw.actual_ht_away,
                            actual_h2_home=raw.actual_h2_home,
                            actual_h2_away=raw.actual_h2_away,
                            result_fetched_at=datetime.now(timezone.utc),
                        )
                    )
                stats["updated"] += 1
                log.info(
                    "Güncellendi [%s]: %s vs %s | %d-%d",
                    match_id, raw.home_team, raw.away_team,
                    raw.actual_ft_home, raw.actual_ft_away,
                )
            except Exception as e:
                log.error("Güncelleme hatası [%s]: %s", match_id, e, exc_info=True)
                stats["errors"] += 1

    log.info(
        "Sonuç güncellemesi tamamlandı: %d güncellendi, %d bitmemiş, %d hata",
        stats["updated"], stats["not_finished"], stats["errors"],
    )
    return stats
