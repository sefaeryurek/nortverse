"""Kural dışı maç tespiti.

Kurallar:
1. Analiz edilen maç lig maçı olmalı (kupa/friendly değil)
2. Her iki takım ligde en az N maç oynamış olmalı
3. H2H'ta en az M lig maçı olmalı
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.config import ANALYSIS
from app.models import MatchRawData, SkipReason


@dataclass
class FilterCheck:
    """Filtreleme kontrol sonucu."""

    passed: bool
    reason: Optional[SkipReason] = None
    detail: Optional[str] = None


def check_match_filters(
    data: MatchRawData,
    min_league_matches: int = ANALYSIS.min_league_matches,
    min_h2h: int = ANALYSIS.min_h2h,
) -> FilterCheck:
    """Bir maçın analize uygun olup olmadığını kontrol eder.

    Args:
        data: Nowgoal'den çekilmiş ham veri
        min_league_matches: Her takımın ligde oynaması gereken minimum maç sayısı
        min_h2h: H2H'ta olması gereken minimum lig maçı sayısı

    Returns:
        FilterCheck. passed=True ise analiz edilebilir.
    """
    # 1. Ev sahibi yeterince lig maçı oynamış mı?
    home_league_count = sum(
        1 for m in data.home_recent_matches if m.is_league_match
    )
    if home_league_count < min_league_matches:
        return FilterCheck(
            passed=False,
            reason=SkipReason.HOME_TEAM_INSUFFICIENT,
            detail=f"Ev sahibi ligde {home_league_count} maç, en az {min_league_matches} gerekli",
        )

    # 2. Deplasman yeterince lig maçı oynamış mı?
    away_league_count = sum(
        1 for m in data.away_recent_matches if m.is_league_match
    )
    if away_league_count < min_league_matches:
        return FilterCheck(
            passed=False,
            reason=SkipReason.AWAY_TEAM_INSUFFICIENT,
            detail=f"Deplasman ligde {away_league_count} maç, en az {min_league_matches} gerekli",
        )

    # 3. H2H yeterli lig maçı var mı?
    h2h_league_count = sum(1 for m in data.h2h_matches if m.is_league_match)
    if h2h_league_count < min_h2h:
        return FilterCheck(
            passed=False,
            reason=SkipReason.H2H_INSUFFICIENT,
            detail=f"H2H'ta {h2h_league_count} lig maçı, en az {min_h2h} gerekli",
        )

    return FilterCheck(passed=True)


def select_last_n_league_matches(
    matches: list, n: int, is_home_perspective: bool, team_name: str
) -> list:
    """Son N lig maçını seç.

    Args:
        matches: Tüm form/h2h maçları
        n: Kaç maç alınacak
        is_home_perspective: 'bizim takım' ev sahibi mi perspektifinden bakılsın?
        team_name: Takım adı (form maçlarında hangi taraf 'biz' onu bulmak için)

    Returns:
        Son N lig maçı, tarih sırasına göre (en yeniler başta bekleniyor).
    """
    league_only = [m for m in matches if m.is_league_match]
    return league_only[:n]
