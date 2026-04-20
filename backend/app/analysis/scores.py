"""Analiz edilen 35 skor ve yardımcı fonksiyonlar.

Excel'deki sıralama aynen korunuyor. Bu sıra değişmemeli —
veritabanı sütunları ve pattern matching bu sıraya güvenecek.
"""

from __future__ import annotations

# Excel'deki skor sırası (sizin ARSIV sheet'inden)
# MS1 (ev kazanır)
MS1_SCORES: list[tuple[int, int]] = [
    (1, 0), (2, 0), (2, 1), (3, 0), (3, 1), (3, 2),
    (4, 0), (4, 1), (4, 2), (4, 3),
    (5, 0), (5, 1), (5, 2),
    (6, 0), (6, 1),
]

# MSX (beraberlik)
MSX_SCORES: list[tuple[int, int]] = [
    (0, 0), (1, 1), (2, 2), (3, 3), (4, 4),
]

# MS2 (deplasman kazanır)
MS2_SCORES: list[tuple[int, int]] = [
    (0, 1), (0, 2), (1, 2), (0, 3), (1, 3), (2, 3),
    (0, 4), (1, 4), (2, 4), (3, 4),
    (0, 5), (1, 5), (2, 5),
    (0, 6), (1, 6),
]

# Toplam 35 skor — ARŞIV-2'nin sütun sırası bu olacak
ALL_SCORES: list[tuple[int, int]] = MS1_SCORES + MSX_SCORES + MS2_SCORES

assert len(ALL_SCORES) == 35, "Skor sayısı 35 olmalı"


def score_key(home: int, away: int) -> str:
    """(1, 0) -> '1-0'."""
    return f"{home}-{away}"


def column_name(home: int, away: int) -> str:
    """DB sütun adı: (1, 0) -> 'score_1_0'."""
    return f"score_{home}_{away}"


def categorize(home: int, away: int) -> str:
    """Bir skorun MS1 / MSX / MS2'den hangisi olduğunu söyler."""
    if home > away:
        return "1"
    if home < away:
        return "2"
    return "X"
