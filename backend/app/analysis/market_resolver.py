"""Tahmin sonucu çözücü — bir seçim gerçek skorla tuttu mu?

Ayrı kurallar yazmak yerine gerçek skorla tek satırlık `compute_stats` çalıştırılır:
seçimin alanı %100 ise tuttu. Böylece istatistik nasıl hesaplanıyorsa sonuç da
aynı mantıkla çözülür (handikap, fark, kombine... hepsi tek kaynaktan).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.analysis.market_catalog import get_market
from app.analysis.pattern_stats import compute_stats

RESOLVER_VERSION = "stats-v1"


@dataclass(frozen=True)
class _ScoreRow:
    actual_ht_home: int | None
    actual_ht_away: int | None
    actual_h2_home: int | None
    actual_h2_away: int | None
    actual_ft_home: int | None
    actual_ft_away: int | None


def resolve(
    period: str, market: str, selection: str,
    ht: tuple[int, int] | None, ft: tuple[int, int] | None,
) -> str | None:
    """'hit' / 'miss' döner; skor eksik veya tutarsızsa None (henüz çözülemez)."""
    spec = get_market(market)
    field = spec.field_for(selection)
    if field is None:
        raise ValueError(f"{market} pazarında bilinmeyen seçim: {selection}")
    if not spec.active_in(period) or ft is None:
        return None
    needs_ht = period != "ft" or spec.ft_only
    if needs_ht and ht is None:
        return None
    h2 = (ft[0] - ht[0], ft[1] - ht[1]) if ht is not None else (None, None)
    row = _ScoreRow(
        actual_ht_home=ht[0] if ht else None, actual_ht_away=ht[1] if ht else None,
        actual_h2_home=h2[0], actual_h2_away=h2[1],
        actual_ft_home=ft[0], actual_ft_away=ft[1],
    )
    stats = compute_stats([row], period)
    if stats is None:
        return None
    return "hit" if getattr(stats, field) >= 99.95 else "miss"
