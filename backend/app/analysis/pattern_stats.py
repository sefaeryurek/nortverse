"""Pattern matching istatistik hesaplama — ortak modül."""

from __future__ import annotations

from collections import Counter
from typing import Optional

from pydantic import BaseModel


class PatternResult(BaseModel):
    match_count: int

    # Maç Sonucu
    result_1_pct: float
    result_x_pct: float
    result_2_pct: float

    # Çifte Şans
    dc_1x_pct: float
    dc_x2_pct: float
    dc_12_pct: float

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

    # Handikap
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

    # MS + 1.5 kombine
    ms1_alt15_pct: float
    ms1_ust15_pct: float
    msx_alt15_pct: float
    msx_ust15_pct: float
    ms2_alt15_pct: float
    ms2_ust15_pct: float

    # MS + 2.5 kombine
    ms1_alt25_pct: float = 0.0
    ms1_ust25_pct: float = 0.0
    msx_alt25_pct: float = 0.0
    msx_ust25_pct: float = 0.0
    ms2_alt25_pct: float = 0.0
    ms2_ust25_pct: float = 0.0

    # MS + KG kombine
    ms1_kg_var_pct: float
    ms1_kg_yok_pct: float
    msx_kg_var_pct: float
    msx_kg_yok_pct: float
    ms2_kg_var_pct: float
    ms2_kg_yok_pct: float

    # Hangi Takım Kaç Farkla Kazanır
    fark_ev1_pct: float = 0.0
    fark_ev2_pct: float = 0.0
    fark_ev3p_pct: float = 0.0
    fark_ber_pct: float = 0.0
    fark_dep1_pct: float = 0.0
    fark_dep2_pct: float = 0.0
    fark_dep3p_pct: float = 0.0

    # Taraf Alt/Üst
    ev_alt_05_pct: float = 0.0
    ev_ust_05_pct: float = 0.0
    ev_alt_15_pct: float = 0.0
    ev_ust_15_pct: float = 0.0
    ev_alt_25_pct: float = 0.0
    ev_ust_25_pct: float = 0.0
    dep_alt_05_pct: float = 0.0
    dep_ust_05_pct: float = 0.0
    dep_alt_15_pct: float = 0.0
    dep_ust_15_pct: float = 0.0
    dep_alt_25_pct: float = 0.0
    dep_ust_25_pct: float = 0.0

    # Ev/Dep 1. Yarı 0.5 Alt/Üst (FT pattern için)
    ev_ht_alt_05_pct: float = 0.0
    ev_ht_ust_05_pct: float = 0.0
    dep_ht_alt_05_pct: float = 0.0
    dep_ht_ust_05_pct: float = 0.0

    # Toplam Gol Aralığı
    gol_01_pct: float = 0.0
    gol_23_pct: float = 0.0
    gol_45_pct: float = 0.0
    gol_6p_pct: float = 0.0

    # En Çok Gol Olacak Yarı (FT için)
    encok_gol_1y_pct: float = 0.0
    encok_gol_esit_pct: float = 0.0
    encok_gol_2y_pct: float = 0.0

    # 1. Yarı Alt/Üst (FT için)
    iy_alt_05_pct: float = 0.0
    iy_ust_05_pct: float = 0.0
    iy_alt_15_pct: float = 0.0
    iy_ust_15_pct: float = 0.0
    iy_alt_25_pct: float = 0.0
    iy_ust_25_pct: float = 0.0
    iki_yari_alt15_pct: float = 0.0
    iki_yari_ust15_pct: float = 0.0

    # 2. Yarı KG (FT için)
    h2_kg_var_pct: float = 0.0
    h2_kg_yok_pct: float = 0.0

    # İY/2Y KG kombine (FT için)
    iy_h2_kg_vv_pct: float = 0.0
    iy_h2_kg_vy_pct: float = 0.0
    iy_h2_kg_yv_pct: float = 0.0
    iy_h2_kg_yy_pct: float = 0.0

    # Ev/Dep İki Yarıda da Gol (FT için)
    ev_iki_yari_gol_pct: float = 0.0
    dep_iki_yari_gol_pct: float = 0.0

    # Ev Hangi Yarıda Daha Çok Gol Atar (FT için)
    ev_encok_1y_pct: float = 0.0
    ev_encok_esit_pct: float = 0.0
    ev_encok_2y_pct: float = 0.0

    # Dep Hangi Yarıda Daha Çok Gol Atar (FT için)
    dep_encok_1y_pct: float = 0.0
    dep_encok_esit_pct: float = 0.0
    dep_encok_2y_pct: float = 0.0

    # İY/MS Kombine (FT için)
    iy_ms_11_pct: float = 0.0
    iy_ms_1x_pct: float = 0.0
    iy_ms_12_pct: float = 0.0
    iy_ms_x1_pct: float = 0.0
    iy_ms_xx_pct: float = 0.0
    iy_ms_x2_pct: float = 0.0
    iy_ms_21_pct: float = 0.0
    iy_ms_2x_pct: float = 0.0
    iy_ms_22_pct: float = 0.0

    # Skor sıklığı
    score_freq: dict

    # HT alt istatistikleri (FT pattern için)
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

    # H2 alt istatistikleri (FT pattern için)
    h2_result_1_pct: float = 0.0
    h2_result_x_pct: float = 0.0
    h2_result_2_pct: float = 0.0


def _hnd_result(h: int, a: int, home_minus: int, away_minus: int) -> str:
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
    ms_25: dict[str, int] = {}
    ms_kg: dict[str, int] = {}
    score_ctr: Counter = Counter()
    fark_ctr: Counter = Counter()
    ev_ust_05 = ev_ust_15 = ev_ust_25 = 0
    dep_ust_05 = dep_ust_15 = dep_ust_25 = 0
    gol_01 = gol_23 = gol_45 = gol_6p = 0

    ht_pairs: list[tuple[int, int]] = []
    h2_pairs: list[tuple[int, int]] = []
    # (ft_h, ft_a, ht_h, ht_a, h2_h, h2_a) — hem HT hem H2 verisi olan FT maçları
    ft_full: list[tuple[int, int, int, int, int, int]] = []

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
        is_ust25 = total_goals >= 3
        is_kg = h > 0 and a > 0
        k15 = f"{res}_{'ust' if is_ust15 else 'alt'}"
        k25 = f"{res}_{'ust' if is_ust25 else 'alt'}"
        kkg = f"{res}_{'var' if is_kg else 'yok'}"
        ms_15[k15] = ms_15.get(k15, 0) + 1
        ms_25[k25] = ms_25.get(k25, 0) + 1
        ms_kg[kkg] = ms_kg.get(kkg, 0) + 1

        score_ctr[f"{h}-{a}"] += 1

        diff = h - a
        if diff > 0:
            if diff == 1:   fark_ctr["ev1"] += 1
            elif diff == 2: fark_ctr["ev2"] += 1
            else:           fark_ctr["ev3p"] += 1
        elif diff == 0:
            fark_ctr["ber"] += 1
        else:
            adiff = -diff
            if adiff == 1:   fark_ctr["dep1"] += 1
            elif adiff == 2: fark_ctr["dep2"] += 1
            else:            fark_ctr["dep3p"] += 1

        ev_ust_05 += 1 if h >= 1 else 0
        ev_ust_15 += 1 if h >= 2 else 0
        ev_ust_25 += 1 if h >= 3 else 0
        dep_ust_05 += 1 if a >= 1 else 0
        dep_ust_15 += 1 if a >= 2 else 0
        dep_ust_25 += 1 if a >= 3 else 0

        if total_goals <= 1:   gol_01 += 1
        elif total_goals <= 3: gol_23 += 1
        elif total_goals <= 5: gol_45 += 1
        else:                  gol_6p += 1

        if period == "ft":
            ht_h = row.actual_ht_home
            ht_a = row.actual_ht_away
            h2_h = row.actual_h2_home
            h2_a = row.actual_h2_away
            if ht_h is not None and ht_a is not None:
                ht_pairs.append((ht_h, ht_a))
            if h2_h is not None and h2_a is not None:
                h2_pairs.append((h2_h, h2_a))
            if all(v is not None for v in [ht_h, ht_a, h2_h, h2_a]):
                ft_full.append((h, a, ht_h, ht_a, h2_h, h2_a))

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
        ms1_alt25_pct=pct(ms_25.get("1_alt", 0)),
        ms1_ust25_pct=pct(ms_25.get("1_ust", 0)),
        msx_alt25_pct=pct(ms_25.get("x_alt", 0)),
        msx_ust25_pct=pct(ms_25.get("x_ust", 0)),
        ms2_alt25_pct=pct(ms_25.get("2_alt", 0)),
        ms2_ust25_pct=pct(ms_25.get("2_ust", 0)),
        ms1_kg_var_pct=pct(ms_kg.get("1_var", 0)),
        ms1_kg_yok_pct=pct(ms_kg.get("1_yok", 0)),
        msx_kg_var_pct=pct(ms_kg.get("x_var", 0)),
        msx_kg_yok_pct=pct(ms_kg.get("x_yok", 0)),
        ms2_kg_var_pct=pct(ms_kg.get("2_var", 0)),
        ms2_kg_yok_pct=pct(ms_kg.get("2_yok", 0)),
        fark_ev1_pct=pct(fark_ctr["ev1"]),
        fark_ev2_pct=pct(fark_ctr["ev2"]),
        fark_ev3p_pct=pct(fark_ctr["ev3p"]),
        fark_ber_pct=pct(fark_ctr["ber"]),
        fark_dep1_pct=pct(fark_ctr["dep1"]),
        fark_dep2_pct=pct(fark_ctr["dep2"]),
        fark_dep3p_pct=pct(fark_ctr["dep3p"]),
        ev_alt_05_pct=pct(total - ev_ust_05),
        ev_ust_05_pct=pct(ev_ust_05),
        ev_alt_15_pct=pct(total - ev_ust_15),
        ev_ust_15_pct=pct(ev_ust_15),
        ev_alt_25_pct=pct(total - ev_ust_25),
        ev_ust_25_pct=pct(ev_ust_25),
        dep_alt_05_pct=pct(total - dep_ust_05),
        dep_ust_05_pct=pct(dep_ust_05),
        dep_alt_15_pct=pct(total - dep_ust_15),
        dep_ust_15_pct=pct(dep_ust_15),
        dep_alt_25_pct=pct(total - dep_ust_25),
        dep_ust_25_pct=pct(dep_ust_25),
        gol_01_pct=pct(gol_01),
        gol_23_pct=pct(gol_23),
        gol_45_pct=pct(gol_45),
        gol_6p_pct=pct(gol_6p),
        score_freq=dict(score_ctr.most_common(12)),
    )

    # HT alt istatistikleri
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

        iy_ust_05 = sum(1 for h, a in ht_pairs if h + a >= 1)
        iy_ust_15 = sum(1 for h, a in ht_pairs if h + a >= 2)
        iy_ust_25 = sum(1 for h, a in ht_pairs if h + a >= 3)
        result.iy_alt_05_pct = hp(n - iy_ust_05)
        result.iy_ust_05_pct = hp(iy_ust_05)
        result.iy_alt_15_pct = hp(n - iy_ust_15)
        result.iy_ust_15_pct = hp(iy_ust_15)
        result.iy_alt_25_pct = hp(n - iy_ust_25)
        result.iy_ust_25_pct = hp(iy_ust_25)

        ev_ht_ust = sum(1 for h, a in ht_pairs if h >= 1)
        dep_ht_ust = sum(1 for h, a in ht_pairs if a >= 1)
        result.ev_ht_alt_05_pct = hp(n - ev_ht_ust)
        result.ev_ht_ust_05_pct = hp(ev_ht_ust)
        result.dep_ht_alt_05_pct = hp(n - dep_ht_ust)
        result.dep_ht_ust_05_pct = hp(dep_ht_ust)

    # H2 alt istatistikleri
    if h2_pairs:
        n = len(h2_pairs)
        h2_r1 = sum(1 for h, a in h2_pairs if h > a)
        h2_rx = sum(1 for h, a in h2_pairs if h == a)
        h2_r2 = sum(1 for h, a in h2_pairs if h < a)
        h2_kgv = sum(1 for h, a in h2_pairs if h > 0 and a > 0)

        def h2p(v: int) -> float:
            return round(v / n * 100, 1)

        result.h2_result_1_pct = h2p(h2_r1)
        result.h2_result_x_pct = h2p(h2_rx)
        result.h2_result_2_pct = h2p(h2_r2)
        result.h2_kg_var_pct = h2p(h2_kgv)
        result.h2_kg_yok_pct = h2p(n - h2_kgv)

    # FT tam veri istatistikleri (hem HT hem H2 skoru olan maçlar)
    if ft_full:
        n = len(ft_full)

        def fp(v: int) -> float:
            return round(v / n * 100, 1)

        iki_yari_alt15 = sum(
            1 for ft_h, ft_a, ht_h, ht_a, h2_h, h2_a in ft_full
            if (ht_h + ht_a) < 2 and (h2_h + h2_a) < 2
        )
        iki_yari_ust15 = sum(
            1 for ft_h, ft_a, ht_h, ht_a, h2_h, h2_a in ft_full
            if (ht_h + ht_a) >= 2 and (h2_h + h2_a) >= 2
        )
        result.iki_yari_alt15_pct = fp(iki_yari_alt15)
        result.iki_yari_ust15_pct = fp(iki_yari_ust15)

        encok_1y   = sum(1 for _, _, ht_h, ht_a, h2_h, h2_a in ft_full if (ht_h + ht_a) > (h2_h + h2_a))
        encok_esit = sum(1 for _, _, ht_h, ht_a, h2_h, h2_a in ft_full if (ht_h + ht_a) == (h2_h + h2_a))
        encok_2y   = sum(1 for _, _, ht_h, ht_a, h2_h, h2_a in ft_full if (ht_h + ht_a) < (h2_h + h2_a))
        result.encok_gol_1y_pct    = fp(encok_1y)
        result.encok_gol_esit_pct  = fp(encok_esit)
        result.encok_gol_2y_pct    = fp(encok_2y)

        iy_h2_kg: Counter = Counter()
        for _, _, ht_h, ht_a, h2_h, h2_a in ft_full:
            iy_kg = "v" if (ht_h > 0 and ht_a > 0) else "y"
            h2_kg = "v" if (h2_h > 0 and h2_a > 0) else "y"
            iy_h2_kg[f"{iy_kg}{h2_kg}"] += 1
        result.iy_h2_kg_vv_pct = fp(iy_h2_kg["vv"])
        result.iy_h2_kg_vy_pct = fp(iy_h2_kg["vy"])
        result.iy_h2_kg_yv_pct = fp(iy_h2_kg["yv"])
        result.iy_h2_kg_yy_pct = fp(iy_h2_kg["yy"])

        ev_iki  = sum(1 for _, _, ht_h, ht_a, h2_h, h2_a in ft_full if ht_h > 0 and h2_h > 0)
        dep_iki = sum(1 for _, _, ht_h, ht_a, h2_h, h2_a in ft_full if ht_a > 0 and h2_a > 0)
        result.ev_iki_yari_gol_pct  = fp(ev_iki)
        result.dep_iki_yari_gol_pct = fp(dep_iki)

        ev_e1  = sum(1 for _, _, ht_h, ht_a, h2_h, h2_a in ft_full if ht_h > h2_h)
        ev_ee  = sum(1 for _, _, ht_h, ht_a, h2_h, h2_a in ft_full if ht_h == h2_h)
        ev_e2  = sum(1 for _, _, ht_h, ht_a, h2_h, h2_a in ft_full if ht_h < h2_h)
        dep_e1 = sum(1 for _, _, ht_h, ht_a, h2_h, h2_a in ft_full if ht_a > h2_a)
        dep_ee = sum(1 for _, _, ht_h, ht_a, h2_h, h2_a in ft_full if ht_a == h2_a)
        dep_e2 = sum(1 for _, _, ht_h, ht_a, h2_h, h2_a in ft_full if ht_a < h2_a)
        result.ev_encok_1y_pct    = fp(ev_e1)
        result.ev_encok_esit_pct  = fp(ev_ee)
        result.ev_encok_2y_pct    = fp(ev_e2)
        result.dep_encok_1y_pct   = fp(dep_e1)
        result.dep_encok_esit_pct = fp(dep_ee)
        result.dep_encok_2y_pct   = fp(dep_e2)

        iy_ms_ctr: Counter = Counter()
        for ft_h, ft_a, ht_h, ht_a, h2_h, h2_a in ft_full:
            ht_res = "1" if ht_h > ht_a else ("x" if ht_h == ht_a else "2")
            ft_res = "1" if ft_h > ft_a else ("x" if ft_h == ft_a else "2")
            iy_ms_ctr[f"{ht_res}{ft_res}"] += 1
        result.iy_ms_11_pct = fp(iy_ms_ctr["11"])
        result.iy_ms_1x_pct = fp(iy_ms_ctr["1x"])
        result.iy_ms_12_pct = fp(iy_ms_ctr["12"])
        result.iy_ms_x1_pct = fp(iy_ms_ctr["x1"])
        result.iy_ms_xx_pct = fp(iy_ms_ctr["xx"])
        result.iy_ms_x2_pct = fp(iy_ms_ctr["x2"])
        result.iy_ms_21_pct = fp(iy_ms_ctr["21"])
        result.iy_ms_2x_pct = fp(iy_ms_ctr["2x"])
        result.iy_ms_22_pct = fp(iy_ms_ctr["22"])

    return result
