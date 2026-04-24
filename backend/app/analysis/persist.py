"""Pattern sonuçlarını DB'ye kaydetmek için ortak yardımcı.

Pipeline ve API tarafı bu modülü kullanır — pattern hesaplamasının tek bir
doğru yeri olur, _result_to_row ve _do_analyze tek satırla pattern dolduran
dict alır.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from sqlalchemy import update as sa_update

from app.analysis.pattern_b import find_pattern_b_matches
from app.analysis.pattern_c import find_pattern_c_all_periods
from app.db.connection import get_session
from app.db.models import Match

log = logging.getLogger(__name__)


async def compute_all_patterns(
    match_id: str,
    ht_scores: tuple[list, list, list],
    h2_scores: tuple[list, list, list],
    ft_scores: tuple[list, list, list],
    ft_ratios: dict | None,
) -> dict[str, dict | None]:
    """6 pattern alanını tek seferde hesapla.

    exclude_match_id=match_id ile hesaplanır → analiz edilen maç kendi
    arşivine dahil edilmez. Saklanan değer doğrudan kullanıma hazır.

    Args:
        match_id: Analiz edilen maç kimliği (self-exclusion için)
        ht_scores: (scores_1, scores_x, scores_2) İlk yarı 3.5+ skorları
        h2_scores: aynı, 2. yarı için
        ft_scores: aynı, maç sonu için
        ft_ratios: FT tüm 35 skorun oranları (Pattern C için)

    Returns:
        {"pattern_ht_b": dict|None, "pattern_ht_c": ..., ...} 6 anahtarlı dict.
        compute başarısız olursa ilgili anahtar None değeri taşır.
    """

    async def _b(period: str, s1, sx, s2) -> Optional[dict]:
        try:
            res = await find_pattern_b_matches(
                period, s1, sx, s2, exclude_match_id=match_id
            )
            return res.model_dump() if res else None
        except Exception as exc:
            log.warning("Pattern B [%s] hesaplanamadı [%s]: %s", period, match_id, exc)
            return None

    async def _c_all() -> tuple[Optional[dict], Optional[dict], Optional[dict]]:
        if not ft_ratios:
            return None, None, None
        try:
            ht_c, h2_c, ft_c = await find_pattern_c_all_periods(
                ft_ratios, exclude_match_id=match_id
            )
            return (
                ht_c.model_dump() if ht_c else None,
                h2_c.model_dump() if h2_c else None,
                ft_c.model_dump() if ft_c else None,
            )
        except Exception as exc:
            log.warning("Pattern C hesaplanamadı [%s]: %s", match_id, exc)
            return None, None, None

    (ht_b, h2_b, ft_b), (ht_c, h2_c, ft_c) = await asyncio.gather(
        asyncio.gather(
            _b("ht", *ht_scores),
            _b("h2", *h2_scores),
            _b("ft", *ft_scores),
        ),
        _c_all(),
    )

    return {
        "pattern_ht_b": ht_b,
        "pattern_ht_c": ht_c,
        "pattern_h2_b": h2_b,
        "pattern_h2_c": h2_c,
        "pattern_ft_b": ft_b,
        "pattern_ft_c": ft_c,
    }


async def update_match_patterns(match_id: str, patterns: dict[str, dict | None]) -> None:
    """matches satırının sadece 6 pattern kolonunu günceller.

    Lazy backfill için kullanılır: _build_from_db DB'de pattern bulamazsa
    hesaplar, sonra bu fonksiyonu çağırıp DB'ye yazar (write-through cache).
    """
    try:
        async with get_session() as session:
            await session.execute(
                sa_update(Match).where(Match.match_id == match_id).values(**patterns)
            )
        log.info("Pattern'ler DB'ye kaydedildi (lazy backfill): %s", match_id)
    except Exception as exc:
        log.warning("Pattern'leri DB'ye yazamadık [%s]: %s", match_id, exc)
