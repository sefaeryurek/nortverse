"""Analiz motorunun testleri.

Excel'deki örnek bir maçı simüle edip formülün doğru çalıştığını doğrularız.
"""

from __future__ import annotations

from app.analysis.engine import analyze_match
from app.analysis.filtering import check_match_filters
from app.analysis.pattern_c import _ratios_match
from app.analysis.scores import ALL_SCORES
from app.models import HistoricalMatch, MatchRawData, Period, SkipReason


def _make_match(
    home: str,
    away: str,
    hg_ft: int,
    ag_ft: int,
    hg_ht: int | None = None,
    ag_ht: int | None = None,
    is_league: bool = True,
) -> HistoricalMatch:
    return HistoricalMatch(
        opponent=away,
        home_team=home,
        away_team=away,
        home_score_ft=hg_ft,
        away_score_ft=ag_ft,
        home_score_ht=hg_ht,
        away_score_ht=ag_ht,
        is_league_match=is_league,
    )


def test_skor_sayisi_35():
    """Toplam 35 skor olmalı."""
    assert len(ALL_SCORES) == 35


def test_kural_disi_h2h_yetersiz():
    """H2H'da 5'ten az lig maçı varsa kural dışı."""
    data = MatchRawData(
        match_id="1",
        home_team="A",
        away_team="B",
        league_code="X",
        home_recent_matches=[_make_match("A", f"T{i}", 1, 0) for i in range(5)],
        away_recent_matches=[_make_match("B", f"T{i}", 1, 0) for i in range(5)],
        h2h_matches=[_make_match("A", "B", 1, 0) for _ in range(3)],  # sadece 3 tane
    )
    check = check_match_filters(data)
    assert not check.passed
    assert check.reason == SkipReason.H2H_INSUFFICIENT


def test_kural_disi_ev_yetersiz():
    """Ev sahibi 5'ten az lig maçı oynamışsa kural dışı."""
    data = MatchRawData(
        match_id="1",
        home_team="A",
        away_team="B",
        league_code="X",
        home_recent_matches=[_make_match("A", "T", 1, 0) for _ in range(3)],  # 3 tane
        away_recent_matches=[_make_match("B", "T", 1, 0) for _ in range(5)],
        h2h_matches=[_make_match("A", "B", 1, 0) for _ in range(5)],
    )
    check = check_match_filters(data)
    assert not check.passed
    assert check.reason == SkipReason.HOME_TEAM_INSUFFICIENT


def test_filtre_gecer():
    """Her şey yeterliyse kontrol geçmeli."""
    data = MatchRawData(
        match_id="1",
        home_team="A",
        away_team="B",
        league_code="X",
        home_recent_matches=[_make_match("A", "T", 1, 0) for _ in range(5)],
        away_recent_matches=[_make_match("B", "T", 1, 0) for _ in range(5)],
        h2h_matches=[_make_match("A", "B", 1, 0) for _ in range(5)],
    )
    check = check_match_filters(data)
    assert check.passed


def test_analiz_0_0_formulu():
    """
    Basit bir senaryoda formül doğrulaması.

    Tüm maçlar 0-0 bittiyse:
    - form_ev gol dağılımı: {0: 5}
    - form_dep gol dağılımı: {0: 5}
    - h2h_ev gol dağılımı: {0: 5}
    - h2h_dep gol dağılımı: {0: 5}

    0-0 skoru için formül:
    ((h2h_ev[0] + form_ev[0]) + (h2h_dep[0] + form_dep[0])) / 2
    = ((5 + 5) + (5 + 5)) / 2
    = 10

    1-0 skoru için:
    ((h2h_ev[1] + form_ev[1]) + (h2h_dep[0] + form_dep[0])) / 2
    = ((0 + 0) + (5 + 5)) / 2
    = 5
    """
    form_home = [_make_match("A", f"T{i}", 0, 0, 0, 0) for i in range(5)]
    form_away = [_make_match("B", f"T{i}", 0, 0, 0, 0) for i in range(5)]
    h2h = [_make_match("A", "B", 0, 0, 0, 0) for _ in range(5)]

    data = MatchRawData(
        match_id="test1",
        home_team="A",
        away_team="B",
        league_code="X",
        home_recent_matches=form_home,
        away_recent_matches=form_away,
        h2h_matches=h2h,
    )

    result = analyze_match(data)

    # MS (FT) periyodunda 0-0'ın oranı 10 olmalı
    assert result.ft.all_ratios["0-0"] == 10.0
    # 1-0'ın oranı 5 olmalı
    assert result.ft.all_ratios["1-0"] == 5.0
    # 3.5 üstü MSX'te 0-0 olmalı
    assert "0-0" in result.ft.scores_x


def test_analiz_ev_hep_kazaniyor():
    """Ev sahibinin son 5 maçı 2-0, deplasmanın son 5 maçı 0-2, h2h 2-0.

    Beklenen: 2-0 skoru yüksek oranda MS1 olarak çıkmalı.

    2-0 skoru için:
    - h2h_ev[2] = 5 (h2h'ta ev hep 2 attı)
    - form_ev[2] = 5 (formda ev hep 2 attı)
    - h2h_dep[0] = 5 (h2h'ta dep hep 0 attı)
    - form_dep[0] = 5 (formda dep hep 0 attı)
    Oran = ((5+5) + (5+5)) / 2 = 10
    """
    form_home = [_make_match("A", f"T{i}", 2, 0, 1, 0) for i in range(5)]
    form_away = [_make_match(f"T{i}", "B", 2, 0, 1, 0) for i in range(5)]  # Dep hep kaybediyor
    h2h = [_make_match("A", "B", 2, 0, 1, 0) for _ in range(5)]

    data = MatchRawData(
        match_id="test2",
        home_team="A",
        away_team="B",
        league_code="X",
        home_recent_matches=form_home,
        away_recent_matches=form_away,
        h2h_matches=h2h,
    )

    result = analyze_match(data)
    # 2-0 oranı 10 olmalı
    assert result.ft.all_ratios["2-0"] == 10.0
    # MS1'de 2-0 olmalı
    assert "2-0" in result.ft.scores_1


def test_oran_hep_0_5_kati():
    """Formül sonucu her zaman 0.5 katı olmalı (tam sayılar / 2)."""
    form_home = [_make_match("A", f"T{i}", i % 4, 0, 0, 0) for i in range(5)]
    form_away = [_make_match(f"T{i}", "B", 0, i % 3, 0, 0) for i in range(5)]
    h2h = [_make_match("A", "B", (i % 2) + 1, i % 3, 0, 0) for i in range(5)]

    data = MatchRawData(
        match_id="t3",
        home_team="A",
        away_team="B",
        league_code="X",
        home_recent_matches=form_home,
        away_recent_matches=form_away,
        h2h_matches=h2h,
    )

    result = analyze_match(data)

    for period_result in (result.ht, result.half2, result.ft):
        for key, ratio in period_result.all_ratios.items():
            # Her değer 0.5'in katı olmalı
            doubled = ratio * 2
            assert abs(doubled - round(doubled)) < 1e-9, f"{key} = {ratio}"


def test_pattern_c_ratios_match_tolerans():
    """_ratios_match tolerans mantığını doğrular."""
    target = {"1-0": 5.0, "0-1": 3.0, "0-0": 2.5}
    # Tam eşleşme
    assert _ratios_match(target, {"1-0": 5.0, "0-1": 3.0, "0-0": 2.5}, 0.5)
    # Tolerans sınırında (±0.5)
    assert _ratios_match(target, {"1-0": 5.5, "0-1": 2.5, "0-0": 2.0}, 0.5)
    # Tolerans aşıldı
    assert not _ratios_match(target, {"1-0": 5.6, "0-1": 3.0, "0-0": 2.5}, 0.5)
    # Eksik anahtar → eşleşme yok
    assert not _ratios_match(target, {"1-0": 5.0, "0-1": 3.0}, 0.5)


def test_iy_ve_ms_farkli_sonuclar():
    """İY ve MS gol dağılımları ayrı hesaplanmalı."""
    # Tüm maçlar İY 0-0, MS 2-0 bitmiş
    form_home = [_make_match("A", f"T{i}", 2, 0, 0, 0) for i in range(5)]
    form_away = [_make_match(f"T{i}", "B", 2, 0, 0, 0) for i in range(5)]
    h2h = [_make_match("A", "B", 2, 0, 0, 0) for _ in range(5)]

    data = MatchRawData(
        match_id="t4",
        home_team="A",
        away_team="B",
        league_code="X",
        home_recent_matches=form_home,
        away_recent_matches=form_away,
        h2h_matches=h2h,
    )

    result = analyze_match(data)

    # HT'de ev hep 0 atmış → 0-0 oranı 10
    assert result.ht.all_ratios["0-0"] == 10.0
    # FT'de ev hep 2 atmış → 2-0 oranı 10
    assert result.ft.all_ratios["2-0"] == 10.0
    # 2Y'da ev hep 2 atmış (FT 2 - HT 0 = 2) → 2-0 oranı 10
    assert result.half2.all_ratios["2-0"] == 10.0
