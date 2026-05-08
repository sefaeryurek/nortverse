"""Sprint 8.9 — `compute_trends` testleri (Sprint 8.8 modülünün kalıcı testi)."""

from app.analysis.trends import MIN_SAMPLE, compute_trends
from app.models import HistoricalMatch, MatchRawData


def _make_raw(home: str = "TestHome", away: str = "TestAway",
              home_recent: list[HistoricalMatch] = None,
              away_recent: list[HistoricalMatch] = None,
              h2h: list[HistoricalMatch] = None) -> MatchRawData:
    return MatchRawData(
        match_id="test",
        home_team=home,
        away_team=away,
        league_code="Turkish Super Lig",
        home_recent_matches=home_recent or [],
        away_recent_matches=away_recent or [],
        h2h_matches=h2h or [],
    )


def _h(home: str, away: str, hf: int, af: int, league: bool = True) -> HistoricalMatch:
    return HistoricalMatch(
        opponent=away if home == "TestHome" else home,
        home_team=home,
        away_team=away,
        home_score_ft=hf,
        away_score_ft=af,
        is_league_match=league,
    )


class TestComputeTrends:
    def test_home_form_5_match(self) -> None:
        # Ev: 5 ev maçı, 2G/2B/1M
        matches = [
            _h("TestHome", "X", 3, 1),  # G
            _h("TestHome", "Y", 2, 0),  # G
            _h("TestHome", "Z", 1, 1),  # B
            _h("TestHome", "W", 2, 2),  # B
            _h("TestHome", "V", 0, 1),  # M
        ]
        raw = _make_raw(home_recent=matches)
        trends = compute_trends(raw)
        assert trends.home_form is not None
        assert trends.home_form.sample_size == 5
        assert trends.home_form.win_pct == 40.0  # 2/5
        assert trends.home_form.draw_pct == 40.0  # 2/5
        assert trends.home_form.loss_pct == 20.0  # 1/5
        # KG: 3-1 var, 1-1 var, 2-2 var = 3 maç
        assert trends.home_form.kg_var_pct == 60.0
        # Üst 2.5: 3-1 (4>=3), 2-2 (4>=3), 0-1 (1<3 hayır), 1-1 (2<3 hayır), 2-0 (2<3 hayır) = 2 maç
        assert trends.home_form.over_25_pct == 40.0
        # Last 5: G G B B M
        assert trends.home_form.last_n_results == ["G", "G", "B", "B", "M"]

    def test_away_form_only_dış_maçlar(self) -> None:
        # Dep takımının "dış" maçları (away_team olduğu)
        matches = [
            _h("X", "TestAway", 0, 2),  # G (Dep dep'te kazandı)
            _h("Y", "TestAway", 1, 1),  # B
            _h("Z", "TestAway", 2, 1),  # M
        ]
        raw = _make_raw(away_recent=matches)
        trends = compute_trends(raw)
        assert trends.away_form is not None
        assert trends.away_form.sample_size == 3
        assert abs(trends.away_form.win_pct - 33.3) < 0.1

    def test_h2h_ev_perspektifi(self) -> None:
        # H2H ev sahibi (TestHome) açısından
        matches = [
            _h("TestHome", "TestAway", 2, 1),     # G (TestHome ev kazandı)
            _h("TestAway", "TestHome", 1, 1),     # B (TestHome dep beraberlik)
            _h("TestHome", "TestAway", 3, 2),     # G (TestHome ev kazandı)
        ]
        raw = _make_raw(h2h=matches)
        trends = compute_trends(raw)
        assert trends.h2h is not None
        assert trends.h2h.sample_size == 3
        # 2G/1B/0M = 66.7% galibiyet
        assert abs(trends.h2h.win_pct - 66.7) < 0.1
        # Tüm maçlarda 2-1, 1-1, 3-2 → KG hepsi var
        assert trends.h2h.kg_var_pct == 100.0

    def test_minimum_sample_size_returns_none(self) -> None:
        # Sample <3 → None
        matches = [_h("TestHome", "X", 1, 0), _h("TestHome", "Y", 2, 1)]
        raw = _make_raw(home_recent=matches)
        trends = compute_trends(raw)
        assert trends.home_form is None  # 2 < MIN_SAMPLE (3)

    def test_only_league_matches_counted(self) -> None:
        # Kupa maçları sayılmaz
        matches = [
            _h("TestHome", "X", 5, 0, league=False),  # Kupa - sayılmaz
            _h("TestHome", "Y", 1, 0, league=True),
            _h("TestHome", "Z", 0, 0, league=True),
            _h("TestHome", "W", 2, 1, league=True),
        ]
        raw = _make_raw(home_recent=matches)
        trends = compute_trends(raw)
        assert trends.home_form is not None
        assert trends.home_form.sample_size == 3  # Kupa hariç 3

    def test_empty_matches_returns_none_blocks(self) -> None:
        raw = _make_raw()
        trends = compute_trends(raw)
        assert trends.home_form is None
        assert trends.away_form is None
        assert trends.h2h is None
