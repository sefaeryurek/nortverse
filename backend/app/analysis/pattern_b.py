"""Katman B — Pattern Matching (ARŞIV-1).

Bülten maçının skor setini (MS1/MSX/MS2) DB'deki geçmiş maçlarla karşılaştırır.
Tam aynı skor setine sahip maçların gerçek sonuçlarından istatistik çıkarır.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta

from sqlalchemy import and_, cast, func, select
from sqlalchemy.dialects.postgresql import JSONB

from app.analysis.pattern_stats import PatternResult, compute_stats
from app.db.connection import get_session
from app.db.models import Match

log = logging.getLogger(__name__)

# Bir maçın sonucu dünyada kickoff'tan ~3 saat sonra kesin bilinir.
RESULT_KNOWN_DELAY = timedelta(hours=3)


def candidate_filters(as_of: datetime) -> list:
    """Arşiv adayı olabilecek maçlar: as_of anında sonucu bilinen, silinmemiş maçlar.

    analyzed_at kısıtı yok: oranlar history.select_history(before=kickoff) ile
    sadece maç öncesi veriden üretildiği için toplu çekilen arşiv maçları da adaydır.
    Sonucun bizim sisteme geç yazılması (arşiv importu) adaylığı engellemez.
    """
    known_at = func.coalesce(Match.result_first_fetched_at, Match.result_fetched_at)
    return [
        Match.deleted_at.is_(None),
        Match.model_only.is_(False),
        Match.kickoff_time <= as_of - RESULT_KNOWN_DELAY,
        known_at > Match.kickoff_time,
    ]


def _temporal_weights(rows: list, as_of: datetime, half_life_years: float) -> list[float]:
    """Her maç için temporal decay ağırlığı hesapla.

    weight = 0.5 ^ (yaş_yıl / half_life)
    Son sezon 1.0, 3 yıl önce 0.5, 6 yıl önce 0.25.
    """
    weights = []
    for row in rows:
        kt = getattr(row, "kickoff_time", None)
        if kt is None or half_life_years <= 0:
            weights.append(1.0)
            continue
        if kt.tzinfo is None:
            from datetime import timezone
            kt = kt.replace(tzinfo=timezone.utc)
        age_years = (as_of - kt).total_seconds() / (365.25 * 86400)
        weights.append(math.pow(0.5, max(0.0, age_years) / half_life_years))
    return weights


async def find_pattern_b_matches(
    period: str,
    scores_1: list[str],
    scores_x: list[str],
    scores_2: list[str],
    min_matches: int = 5,
    exclude_match_id: str | None = None,
    as_of: datetime | None = None,
    league_name: str | None = None,
    match_cap: int | None = None,
    temporal_half_life: float = 0.0,
) -> PatternResult | None:
    """Aynı periyot skor setine sahip geçmiş maçları bul ve istatistik üret.

    Args:
        period: "ht", "h2" veya "ft"
        scores_1, scores_x, scores_2: Eşleştirilecek skor listeleri
        min_matches: Minimum eşleşme sayısı
        exclude_match_id: Bu match_id'yi sonuçlardan çıkar (analiz edilen maçın kendisi)
        league_name: Lig filtresi — sadece aynı lig (başka lige düşülmez)
        match_cap: Maksimum eşleşme sayısı (en yakın N maç, sinyal seyrelmesini önler)
        temporal_half_life: Temporal decay yarı ömrü (yıl). 0 ise eşit ağırlık.

    Returns:
        PatternResult veya None (eşleşme < min_matches ise)
    """
    if type(min_matches) is not int or min_matches < 1:
        raise ValueError("min_matches must be a positive integer")
    if as_of is None or as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")
    if period == "ht":
        col_1, col_x, col_2 = Match.ht_scores_1, Match.ht_scores_x, Match.ht_scores_2
        actual_check = and_(Match.actual_ht_home.isnot(None), Match.actual_ht_away.isnot(None))
    elif period == "h2":
        col_1, col_x, col_2 = Match.h2_scores_1, Match.h2_scores_x, Match.h2_scores_2
        actual_check = and_(Match.actual_h2_home.isnot(None), Match.actual_h2_away.isnot(None))
    elif period == "ft":
        col_1, col_x, col_2 = Match.ft_scores_1, Match.ft_scores_x, Match.ft_scores_2
        actual_check = and_(Match.actual_ft_home.isnot(None), Match.actual_ft_away.isnot(None))
    else:
        raise ValueError(f"Geçersiz periyot: {period}")

    filters = [
        col_1.cast(JSONB) == cast(scores_1, JSONB),
        col_x.cast(JSONB) == cast(scores_x, JSONB),
        col_2.cast(JSONB) == cast(scores_2, JSONB),
        actual_check,
        *candidate_filters(as_of),
    ]
    if league_name:
        filters.append(Match.league_name == league_name)
    if exclude_match_id:
        filters.append(Match.match_id != exclude_match_id)
    stmt = select(
        Match.match_id,
        Match.actual_ft_home, Match.actual_ft_away,
        Match.actual_ht_home, Match.actual_ht_away,
        Match.actual_h2_home, Match.actual_h2_away,
        Match.kickoff_time,
    ).where(*filters).order_by(Match.kickoff_time.desc())
    if match_cap and match_cap > 0:
        stmt = stmt.limit(match_cap)
    async with get_session() as session:
        rows = list((await session.execute(stmt)).all())

    if len(rows) < min_matches:
        log.debug("Katman B [%s]: %d eşleşme (minimum %d) — atlandı", period, len(rows), min_matches)
        return None

    log.debug("Katman B [%s]: %d eşleşme bulundu", period, len(rows))
    weights = _temporal_weights(rows, as_of, temporal_half_life) if temporal_half_life > 0 else None
    result = compute_stats(rows, period, weights=weights)
    if result is None or result.match_count < min_matches:
        return None
    return result
