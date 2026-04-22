"""Pattern matching istatistik hesaplama — ortak modül.

Hem Katman B (JSONB equality) hem Katman C (fuzzy ratio) tarafından kullanılır.
"""

from __future__ import annotations

from collections import Counter
from typing import Optional

from pydantic import BaseModel


class PatternResult(BaseModel):
    """Kapsamlı iddaa istatistik sonucu."""

    match_count: int

    # Maç Sonucu (bu periyot için 1/X/2)
    result_1_pct: float
    result_x_pct: float
    result_2_pct: float

    # Çifte Şans
    dc_1x_pct: float   # 1 veya X
    dc_x2_pct: float   # X veya 2
    dc_12_pct: float   # 1 veya 2

    # Alt / Üst
    alt_15_pct: float
    ust_15_pct: float
    alt_25_pct: float
    ust_25_pct: float
    alt_35_pct: float
    ust_35_pct: float

    # Karşılıklı Gol
    kg_var_pct: float
    kg_yok_pct: float

    # Handikaplı Maç Sonu — hnd_(ev_avantaj)_(dep_avantaj)
    # Örn: hnd_h20 = ev takımı 2 gol avantaj veriyor, yani ev-2 vs dep karşılaştırması
    hnd_h20_1_pct: float
    hnd_h20_x_pct: float
    hnd_h20_2_pct: float
    hnd_h10_1_pct: float
    hnd_h10_x_pct: float
    hnd_h10_2_pct: float
    hnd_a10_1_pct: float
    hnd_a10_x_pct: float
    hnd_a10_2_pct: float
    hnd_a20_1_pct: float
    hnd_a20_x_pct: float
    hnd_a20_2_pct: float

    # MS + 1.5 Alt/Üst kombine
    ms1_alt15_pct: float
    ms1_ust15_pct: float
    msx_alt15_pct: float
    msx_ust15_pct: float
    ms2_alt15_pct: float
    ms2_ust15_pct: float

    # MS + Karşılıklı Gol kombine
    ms1_kg_var_pct: float
    ms1_kg_yok_pct: float
    msx_kg_var_pct: float
    msx_kg_yok_pct: float
    ms2_kg_var_pct: float
    ms2_kg_yok_pct: float

    # Skor sıklığı: {"1-0": 7, "0-0": 3, ...} (ilk 12 skor)
    score_freq: dict

    # --- HT alt istatistikleri (sadece FT pattern için doldurulur) ---
    ht_result_1_pct: float = 0.0
    ht_result_x_pct: float = 0.0
    ht_result_2_pct: float = 0.0
    ht_dc_1x_pct: float = 0.0
    ht_dc_x2_pct: float = 0.0
    ht_dc_12_pct: float = 0.0
    ht_alt_15_pct: float = 0.0
    ht_ust_15_pct: float = 0.0
    ht_kg_var_pct: float = 0.0
    ht_kg_yok_pct: float = 0.0

    # --- H2 alt istatistikleri (sadece FT pattern için doldurulur) ---
    h2_result_1_pct: float = 0.0
    h2_result_x_pct: float = 0.0
    h2_result_2_pct: float = 0.0


def _hnd_result(h: int, a: int, home_minus: int, away_minus: int) -> str:
    """Handikap sonucunu hesapla.

    home_minus: ev takımından çıkarılacak gol (ev avantaj veriyor)
    away_minus: dep takımından çıkarılacak gol (dep avantaj veriyor)
    """
    eff_h = h - home_minus
    eff_a = a - away_minus
    if eff_h > eff_a:
        return "1"
    elif eff_h == eff_a:
        return "x"
    return "2"


def _period_scores(row, period: str) -> tuple[Optional[int], Optional[int]]:
    if period == "ht":
        return row.actual_ht_home, row.actual_ht_away
    elif period == "h2":
        return row.actual_h2_home, row.actual_h2_away
    return row.actual_ft_home, row.actual_ft_away


def compute_stats(rows: list, period: str) -> Optional[PatternResult]:
    """Eşleşen DB maçlarından kapsamlı iddaa istatistiği üret.

    Args:
        rows: DB Match satırları (SQLAlchemy ORM nesneleri)
        period: "ht", "h2" veya "ft"

    Returns:
        PatternResult veya None (geçerli skor bulunamadıysa)
    """
    valid: list[tuple] = []
    for row in rows:
        h, a = _period_scores(row, period)
        if h is not None and a is not None:
            valid.append((row, h, a))

    total = len(valid)
    if total == 0:
        return None

    r1 = rx = r2 = 0
    alt15 = ust15 = alt25 = ust25 = alt35 = ust35 = 0
    kg_var = kg_yok = 0
    hnd_h20 = {"1": 0, "x": 0, "2": 0}
    hnd_h10 = {"1": 0, "x": 0, "2": 0}
    hnd_a10 = {"1": 0, "x": 0, "2": 0}
    hnd_a20 = {"1": 0, "x": 0, "2": 0}
    ms_15: dict[str, int] = {}
    ms_kg: dict[str, int] = {}
    score_ctr: Counter = Counter()

    ht_pairs: list[tuple[int, int]] = []
    h2_pairs: list[tuple[int, int]] = []

    for row, h, a in valid:
        total_goals = h + a

        if h > a:
            r1 += 1; res = "1"
        elif h == a:
            rx += 1; res = "x"
        else:
            r2 += 1; res = "2"

        alt15 += 1 if total_goals < 2 else 0
        ust15 += 1 if total_goals >= 2 else 0
        alt25 += 1 if total_goals < 3 else 0
        ust25 += 1 if total_goals >= 3 else 0
        alt35 += 1 if total_goals < 4 else 0
        ust35 += 1 if total_goals >= 4 else 0

        if h > 0 and a > 0:
            kg_var += 1
        else:
            kg_yok += 1

        hnd_h20[_hnd_result(h, a, 2, 0)] += 1
        hnd_h10[_hnd_result(h, a, 1, 0)] += 1
        hnd_a10[_hnd_result(h, a, 0, 1)] += 1
        hnd_a20[_hnd_result(h, a, 0, 2)] += 1

        is_ust15 = total_goals >= 2
        is_kg = h > 0 and a > 0
        k15 = f"{res}_{'ust' if is_ust15 else 'alt'}"
        kkg = f"{res}_{'var' if is_kg else 'yok'}"
        ms_15[k15] = ms_15.get(k15, 0) + 1
        ms_kg[kkg] = ms_kg.get(kkg, 0) + 1

        score_ctr[f"{h}-{a}"] += 1

        if period == "ft":
            if row.actual_ht_home is not None and row.actual_ht_away is not None:
                ht_pairs.append((row.actual_ht_home, row.actual_ht_away))
            if row.actual_h2_home is not None and row.actual_h2_away is not None:
                h2_pairs.append((row.actual_h2_home, row.actual_h2_away))

    def pct(n: int) -> float:
        return round(n / total * 100, 1)

    result = PatternResult(
        match_count=total,
        result_1_pct=pct(r1),
        result_x_pct=pct(rx),
        result_2_pct=pct(r2),
        dc_1x_pct=pct(r1 + rx),
        dc_x2_pct=pct(rx + r2),
        dc_12_pct=pct(r1 + r2),
        alt_15_pct=pct(alt15),
        ust_15_pct=pct(ust15),
        alt_25_pct=pct(alt25),
        ust_25_pct=pct(ust25),
        alt_35_pct=pct(alt35),
        ust_35_pct=pct(ust35),
        kg_var_pct=pct(kg_var),
        kg_yok_pct=pct(kg_yok),
        hnd_h20_1_pct=pct(hnd_h20["1"]),
        hnd_h20_x_pct=pct(hnd_h20["x"]),
        hnd_h20_2_pct=pct(hnd_h20["2"]),
        hnd_h10_1_pct=pct(hnd_h10["1"]),
        hnd_h10_x_pct=pct(hnd_h10["x"]),
        hnd_h10_2_pct=pct(hnd_h10["2"]),
        hnd_a10_1_pct=pct(hnd_a10["1"]),
        hnd_a10_x_pct=pct(hnd_a10["x"]),
        hnd_a10_2_pct=pct(hnd_a10["2"]),
        hnd_a20_1_pct=pct(hnd_a20["1"]),
        hnd_a20_x_pct=pct(hnd_a20["x"]),
        hnd_a20_2_pct=pct(hnd_a20["2"]),
        ms1_alt15_pct=pct(ms_15.get("1_alt", 0)),
        ms1_ust15_pct=pct(ms_15.get("1_ust", 0)),
        msx_alt15_pct=pct(ms_15.get("x_alt", 0)),
        msx_ust15_pct=pct(ms_15.get("x_ust", 0)),
        ms2_alt15_pct=pct(ms_15.get("2_alt", 0)),
        ms2_ust15_pct=pct(ms_15.get("2_ust", 0)),
        ms1_kg_var_pct=pct(ms_kg.get("1_var", 0)),
        ms1_kg_yok_pct=pct(ms_kg.get("1_yok", 0)),
        msx_kg_var_pct=pct(ms_kg.get("x_var", 0)),
        msx_kg_yok_pct=pct(ms_kg.get("x_yok", 0)),
        ms2_kg_var_pct=pct(ms_kg.get("2_var", 0)),
        ms2_kg_yok_pct=pct(ms_kg.get("2_yok", 0)),
        score_freq=dict(score_ctr.most_common(12)),
    )

    # HT alt istatistikleri (FT pattern'e ek bilgi)
    if ht_pairs:
        n = len(ht_pairs)
        ht_r1 = sum(1 for h, a in ht_pairs if h > a)
        ht_rx = sum(1 for h, a in ht_pairs if h == a)
        ht_r2 = sum(1 for h, a in ht_pairs if h < a)
        ht_alt = sum(1 for h, a in ht_pairs if h + a < 2)
        ht_kgv = sum(1 for h, a in ht_pairs if h > 0 and a > 0)

        def hp(v: int) -> float:
            return round(v / n * 100, 1)

        result.ht_result_1_pct = hp(ht_r1)
        result.ht_result_x_pct = hp(ht_rx)
        result.ht_result_2_pct = hp(ht_r2)
        result.ht_dc_1x_pct = hp(ht_r1 + ht_rx)
        result.ht_dc_x2_pct = hp(ht_rx + ht_r2)
        result.ht_dc_12_pct = hp(ht_r1 + ht_r2)
        result.ht_alt_15_pct = hp(ht_alt)
        result.ht_ust_15_pct = hp(n - ht_alt)
        result.ht_kg_var_pct = hp(ht_kgv)
        result.ht_kg_yok_pct = hp(n - ht_kgv)

    # H2 alt istatistikleri
    if h2_pairs:
        n = len(h2_pairs)
        h2_r1 = sum(1 for h, a in h2_pairs if h > a)
        h2_rx = sum(1 for h, a in h2_pairs if h == a)
        h2_r2 = sum(1 for h, a in h2_pairs if h < a)

        def h2p(v: int) -> float:
            return round(v / n * 100, 1)

        result.h2_result_1_pct = h2p(h2_r1)
        result.h2_result_x_pct = h2p(h2_rx)
        result.h2_result_2_pct = h2p(h2_r2)

    return result
