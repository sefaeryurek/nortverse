"""Skor → sonuç ilkelleri (tek kaynak).

Arşiv istatistikleri (`pattern_stats.compute_stats`) ve tuttu/tutmadı çözücüsü
(`market_resolver`, compute_stats üzerinden) aynı fonksiyonları kullanır; bir pazarın
anlamı tek yerde tanımlıdır.
"""

from __future__ import annotations

from typing import Optional


def result_code(h: int, a: int) -> str:
    """'1' ev, 'x' beraberlik, '2' deplasman."""
    if h > a:
        return "1"
    if h == a:
        return "x"
    return "2"


def handicap_result(h: int, a: int, home_start: int, away_start: int) -> str:
    """Arayüzdeki başlangıç skoru eklenir: Hnd (2:0) = ev +2 → handicap_result(h, a, 2, 0)."""
    return result_code(h + home_start, a + away_start)


def margin_bucket(h: int, a: int) -> str:
    """Fark kovası: ev1/ev2/ev3p, ber, dep1/dep2/dep3p."""
    diff = h - a
    if diff == 0:
        return "ber"
    side = "ev" if diff > 0 else "dep"
    size = abs(diff)
    return f"{side}{size}" if size <= 2 else f"{side}3p"


def goal_range(total_goals: int) -> str:
    """Toplam gol aralığı: 01, 23, 45, 6p."""
    if total_goals <= 1:
        return "01"
    if total_goals <= 3:
        return "23"
    if total_goals <= 5:
        return "45"
    return "6p"


def both_scored(h: int, a: int) -> bool:
    return h > 0 and a > 0


def period_scores(row, period: str) -> tuple[Optional[int], Optional[int]]:
    """Satırın periyot skoru; geçersiz/tutarsızsa (None, None).

    İY/2Y skoru MS'yi aşamaz; 2Y = MS − İY tutmalı.
    """
    pair = (getattr(row, f"actual_{period}_home"), getattr(row, f"actual_{period}_away"))
    if not all(type(v) is int and 0 <= v <= 30 for v in pair):
        return None, None
    if period != "ft":
        ft = (row.actual_ft_home, row.actual_ft_away)
        if any(total is not None and score > total for score, total in zip(pair, ft)):
            return None, None
        if period == "h2":
            ht = (row.actual_ht_home, row.actual_ht_away)
            if any(first is not None and total is not None and first + second != total
                   for first, second, total in zip(ht, pair, ft)):
                return None, None
    return pair
