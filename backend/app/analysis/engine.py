"""Analiz motoru — Katman A (klasik skor hesaplama).

Formül:
    oran(hg, ag, period) = (
        (h2h_ev_period[hg] + form_ev_period[hg])
        + (h2h_dep_period[ag] + form_dep_period[ag])
    ) / 2

Her maç için 3 periyot × 35 skor = 105 hesaplama yapılır.
Sonuç, 0.5 katlarında bir sayıdır (0.0, 0.5, 1.0, ...).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from app.analysis.scores import ALL_SCORES, categorize, score_key
from app.config import ANALYSIS
from app.models import (
    HistoricalMatch,
    MatchAnalysisResult,
    MatchRawData,
    Period,
    PeriodAnalysis,
)

log = logging.getLogger(__name__)


def _get_goals_in_period(
    match: HistoricalMatch, for_team: str, period: Period
) -> Optional[int]:
    """Bir tarihi maçta 'for_team' takımının belirtilen periyotta attığı gol sayısı.

    Periyotlar:
    - HT: İlk yarı (0-45)
    - 2H: Sadece ikinci yarı (46-90), yani FT - HT
    - FT: Tam maç
    """
    if match.home_team == for_team:
        # Bizim takım ev sahibi
        if period == Period.FT:
            return match.home_score_ft
        if match.home_score_ht is None:
            return None
        if period == Period.HT:
            return match.home_score_ht
        # 2H = FT - HT
        return match.home_score_ft - match.home_score_ht

    elif match.away_team == for_team:
        # Bizim takım deplasman
        if period == Period.FT:
            return match.away_score_ft
        if match.away_score_ht is None:
            return None
        if period == Period.HT:
            return match.away_score_ht
        return match.away_score_ft - match.away_score_ht

    return None


def _goal_count_distribution(
    matches: list[HistoricalMatch], for_team: str, period: Period, last_n: int
) -> dict[int, int]:
    """Son N maçta bu takımın kaç kez 0, 1, 2, ... gol attığını say.

    Returns:
        {0: 2, 1: 3, 2: 1, ...}  gibi bir sözlük. Eksik gol sayıları için 0 kabul edilir.
    """
    distribution: dict[int, int] = {i: 0 for i in range(8)}  # 0-7 gol

    count = 0
    for match in matches:
        if count >= last_n:
            break
        goals = _get_goals_in_period(match, for_team, period)
        if goals is None:
            # HT verisi olmayan eski maçları atla
            continue
        goals = max(0, goals)  # negatif olmasın
        if goals > 7:
            goals = 7  # cap
        distribution[goals] = distribution.get(goals, 0) + 1
        count += 1

    return distribution


def _filter_h2h_for_team(
    h2h_matches: list[HistoricalMatch], home_team: str, away_team: str
) -> tuple[list[HistoricalMatch], list[HistoricalMatch]]:
    """H2H maçlarını ev sahibi perspektifi ve deplasman perspektifi olarak ayırır.

    Aslında aynı maçlar — ama ev sahibinin attığı vs deplasmanın attığı
    gol dağılımlarını ayrı ayrı hesaplamak için böyle düşünüyoruz.
    """
    # Tüm h2h maçları ev sahibi için "biz home"
    for_home = h2h_matches
    for_away = h2h_matches
    return for_home, for_away


def _analyze_period(data: MatchRawData, period: Period, cfg_n: int, cfg_threshold: float) -> PeriodAnalysis:
    """Tek bir periyot için 35 skoru hesapla."""
    # Gol dağılımları (son N lig maçı) — formül sadece lig maçlarını kullanır
    form_home_league = [m for m in data.home_recent_matches if m.is_league_match]
    form_away_league = [m for m in data.away_recent_matches if m.is_league_match]
    form_home_dist = _goal_count_distribution(form_home_league, data.home_team, period, cfg_n)
    form_away_dist = _goal_count_distribution(form_away_league, data.away_team, period, cfg_n)

    # H2H gol dağılımları (son N h2h)
    h2h_league = [m for m in data.h2h_matches if m.is_league_match]
    h2h_home_dist = _goal_count_distribution(h2h_league, data.home_team, period, cfg_n)
    h2h_away_dist = _goal_count_distribution(h2h_league, data.away_team, period, cfg_n)

    # Her skor için oran hesapla
    all_ratios: dict[str, float] = {}
    scores_1: list[str] = []
    scores_x: list[str] = []
    scores_2: list[str] = []

    for hg, ag in ALL_SCORES:
        ratio = (
            (h2h_home_dist.get(hg, 0) + form_home_dist.get(hg, 0))
            + (h2h_away_dist.get(ag, 0) + form_away_dist.get(ag, 0))
        ) / 2

        key = score_key(hg, ag)
        all_ratios[key] = ratio

        if ratio >= cfg_threshold:
            cat = categorize(hg, ag)
            if cat == "1":
                scores_1.append(key)
            elif cat == "X":
                scores_x.append(key)
            else:
                scores_2.append(key)

    return PeriodAnalysis(
        period=period,
        scores_1=scores_1,
        scores_x=scores_x,
        scores_2=scores_2,
        all_ratios=all_ratios,
    )


def _current_season() -> str:
    """Bugünün tarihine göre sezon kodu döndür."""
    now = datetime.now()
    year = now.year
    return f"{year - 1}/{year}" if now.month < 8 else f"{year}/{year + 1}"


def analyze_match(
    data: MatchRawData,
    n_matches: int = ANALYSIS.n_matches,
    threshold: float = ANALYSIS.threshold,
) -> MatchAnalysisResult:
    """Bir maçın 3 periyot için tam analizini yap.

    Not: Bu fonksiyon filtreleme yapmaz. Filtreleme için
    `analysis.filtering.check_match_filters` kullanın.

    Args:
        data: nowgoal'den çekilmiş ham veri
        n_matches: Kaç son maç kullanılacak (default 5)
        threshold: 3.5+ eşiği (default 3.5)

    Returns:
        MatchAnalysisResult, 3 periyotlu sonuç.
    """
    log.info(
        "Analiz başlıyor: %s vs %s (n=%d, threshold=%.1f)",
        data.home_team,
        data.away_team,
        n_matches,
        threshold,
    )

    ht = _analyze_period(data, Period.HT, n_matches, threshold)
    h2 = _analyze_period(data, Period.H2, n_matches, threshold)
    ft = _analyze_period(data, Period.FT, n_matches, threshold)

    result = MatchAnalysisResult(
        match_id=data.match_id,
        home_team=data.home_team,
        away_team=data.away_team,
        league_code=data.league_code,
        season=_current_season(),
        n_matches=n_matches,
        threshold=threshold,
        ht=ht,
        half2=h2,
        ft=ft,
    )

    log.info(
        "Analiz bitti: FT 1=%d X=%d 2=%d | archive1=%s",
        len(ft.scores_1),
        len(ft.scores_x),
        len(ft.scores_2),
        result.has_any_archive1_row,
    )
    return result


def is_match_analyzable(data: MatchRawData) -> bool:
    """Bir maç için analiz çağrılabilir mi? (hızlı erken kontrol)

    Gerçek filtreleme `check_match_filters` ile yapılır — bu sadece
    veri yeterliliği kontrolü.
    """
    if not data.home_team or not data.away_team:
        return False
    if data.home_team == "?" or data.away_team == "?":
        return False
    if not data.home_recent_matches and not data.away_recent_matches:
        return False
    return True
