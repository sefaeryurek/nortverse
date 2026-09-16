"""Analiz motoru (engine.py) birim testleri.

_get_goals_in_period, _goal_count_distribution, _current_season,
analyze_match validasyonu ve edge case'ler.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from app.analysis.engine import (
    _current_season,
    _get_goals_in_period,
    _goal_count_distribution,
    analyze_match,
    is_match_analyzable,
)
from app.models import HistoricalMatch, MatchRawData, Period


def _m(
    home: str = "A",
    away: str = "B",
    hg_ft: int = 1,
    ag_ft: int = 0,
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


def _raw(
    home_matches: list | None = None,
    away_matches: list | None = None,
    h2h: list | None = None,
) -> MatchRawData:
    return MatchRawData(
        match_id="test",
        home_team="A",
        away_team="B",
        league_code="X",
        home_recent_matches=home_matches or [_m("A", f"T{i}", 1, 0, 0, 0) for i in range(5)],
        away_recent_matches=away_matches or [_m(f"T{i}", "B", 0, 1, 0, 0) for i in range(5)],
        h2h_matches=h2h or [_m("A", "B", 1, 0, 0, 0) for _ in range(5)],
    )


# ─── _get_goals_in_period ────────────────────────────────────────────────────

class TestGetGoalsInPeriod:
    def test_ft_home(self):
        m = _m(hg_ft=3, ag_ft=1)
        assert _get_goals_in_period(m, "A", Period.FT) == 3

    def test_ft_away(self):
        m = _m(hg_ft=2, ag_ft=4)
        assert _get_goals_in_period(m, "B", Period.FT) == 4

    def test_ht_home(self):
        m = _m(hg_ft=3, ag_ft=1, hg_ht=1, ag_ht=0)
        assert _get_goals_in_period(m, "A", Period.HT) == 1

    def test_ht_away(self):
        m = _m(hg_ft=2, ag_ft=3, hg_ht=1, ag_ht=2)
        assert _get_goals_in_period(m, "B", Period.HT) == 2

    def test_h2_home(self):
        m = _m(hg_ft=4, ag_ft=1, hg_ht=1, ag_ht=0)
        assert _get_goals_in_period(m, "A", Period.H2) == 3  # 4 - 1

    def test_h2_away(self):
        m = _m(hg_ft=2, ag_ft=5, hg_ht=1, ag_ht=2)
        assert _get_goals_in_period(m, "B", Period.H2) == 3  # 5 - 2

    def test_ht_none_returns_none(self):
        m = _m(hg_ft=2, ag_ft=0, hg_ht=None, ag_ht=None)
        assert _get_goals_in_period(m, "A", Period.HT) is None

    def test_h2_none_when_ht_missing(self):
        m = _m(hg_ft=2, ag_ft=0, hg_ht=None, ag_ht=None)
        assert _get_goals_in_period(m, "A", Period.H2) is None

    def test_unknown_team_returns_none(self):
        m = _m()
        assert _get_goals_in_period(m, "C", Period.FT) is None

    def test_inconsistent_ht_gt_ft_home_returns_ft_for_ft(self):
        m = _m(hg_ft=1, ag_ft=0, hg_ht=3, ag_ht=0)
        assert _get_goals_in_period(m, "A", Period.FT) == 1

    def test_inconsistent_ht_gt_ft_home_returns_none_for_ht(self):
        m = _m(hg_ft=1, ag_ft=0, hg_ht=3, ag_ht=0)
        assert _get_goals_in_period(m, "A", Period.HT) is None

    def test_inconsistent_ht_gt_ft_away(self):
        m = _m(hg_ft=0, ag_ft=1, hg_ht=0, ag_ht=5)
        assert _get_goals_in_period(m, "B", Period.FT) == 1
        assert _get_goals_in_period(m, "B", Period.HT) is None

    def test_zero_zero_match(self):
        m = _m(hg_ft=0, ag_ft=0, hg_ht=0, ag_ht=0)
        assert _get_goals_in_period(m, "A", Period.FT) == 0
        assert _get_goals_in_period(m, "A", Period.HT) == 0
        assert _get_goals_in_period(m, "A", Period.H2) == 0


# ─── _goal_count_distribution ────────────────────────────────────────────────

class TestGoalCountDistribution:
    def test_uniform_1_goal(self):
        matches = [_m("A", f"T{i}", 1, 0, 0, 0) for i in range(5)]
        dist = _goal_count_distribution(matches, "A", Period.FT, 5)
        assert dist[1] == 5
        assert dist[0] == 0

    def test_last_n_limits(self):
        matches = [_m("A", f"T{i}", 1, 0, 0, 0) for i in range(10)]
        dist = _goal_count_distribution(matches, "A", Period.FT, 3)
        assert sum(dist.values()) == 3

    def test_skips_none_ht(self):
        matches = [
            _m("A", "T1", 2, 0, None, None),
            _m("A", "T2", 1, 0, 1, 0),
            _m("A", "T3", 3, 0, 2, 0),
        ]
        dist = _goal_count_distribution(matches, "A", Period.HT, 5)
        assert sum(dist.values()) == 2  # ilk maçın HT'si None
        assert dist[1] == 1
        assert dist[2] == 1

    def test_caps_at_7(self):
        matches = [_m("A", "T1", 9, 0, 4, 0)]
        dist = _goal_count_distribution(matches, "A", Period.FT, 1)
        assert dist[7] == 1
        assert 9 not in dist

    def test_empty_matches(self):
        dist = _goal_count_distribution([], "A", Period.FT, 5)
        assert sum(dist.values()) == 0

    def test_away_team_perspective(self):
        matches = [_m("T1", "B", 0, 3, 0, 1) for _ in range(3)]
        dist = _goal_count_distribution(matches, "B", Period.FT, 3)
        assert dist[3] == 3


# ─── _current_season ─────────────────────────────────────────────────────────

class TestCurrentSeason:
    def test_august_starts_new_season(self):
        assert _current_season(datetime(2026, 8, 15)) == "2026/2027"

    def test_july_is_previous_season(self):
        assert _current_season(datetime(2026, 7, 30)) == "2025/2026"

    def test_january_is_previous_year_season(self):
        assert _current_season(datetime(2027, 1, 10)) == "2026/2027"

    def test_december_is_current_season(self):
        assert _current_season(datetime(2026, 12, 25)) == "2026/2027"


# ─── is_match_analyzable ─────────────────────────────────────────────────────

class TestIsMatchAnalyzable:
    def test_valid_data(self):
        data = _raw()
        assert is_match_analyzable(data)

    def test_empty_home_team(self):
        data = MatchRawData(match_id="1", home_team="", away_team="B", league_code="X")
        assert not is_match_analyzable(data)

    def test_question_mark_team(self):
        data = MatchRawData(match_id="1", home_team="?", away_team="B", league_code="X")
        assert not is_match_analyzable(data)

    def test_no_recent_matches(self):
        data = MatchRawData(match_id="1", home_team="A", away_team="B", league_code="X")
        assert not is_match_analyzable(data)

    def test_one_side_has_matches(self):
        data = MatchRawData(
            match_id="1", home_team="A", away_team="B", league_code="X",
            home_recent_matches=[_m()],
        )
        assert is_match_analyzable(data)


# ─── analyze_match validasyon ─────────────────────────────────────────────────

class TestAnalyzeMatchValidation:
    def test_negative_n_matches_raises(self):
        with pytest.raises(ValueError, match="pozitif"):
            analyze_match(_raw(), n_matches=-1)

    def test_zero_n_matches_raises(self):
        with pytest.raises(ValueError, match="pozitif"):
            analyze_match(_raw(), n_matches=0)

    def test_bool_n_matches_raises(self):
        with pytest.raises(ValueError, match="pozitif"):
            analyze_match(_raw(), n_matches=True)

    def test_negative_threshold_raises(self):
        with pytest.raises(ValueError, match="pozitif"):
            analyze_match(_raw(), threshold=-1.0)

    def test_inf_threshold_raises(self):
        with pytest.raises(ValueError, match="sonlu"):
            analyze_match(_raw(), threshold=float("inf"))

    def test_custom_season_format(self):
        result = analyze_match(_raw(), season="2025-2026")
        assert result.season == "2025/2026"

    def test_default_season(self):
        result = analyze_match(_raw())
        assert "/" in result.season

    def test_result_has_105_ratios(self):
        result = analyze_match(_raw())
        assert len(result.ft.all_ratios) == 35
        assert len(result.ht.all_ratios) == 35
        assert len(result.half2.all_ratios) == 35


# ─── Kenar durumları ─────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_non_league_matches_excluded_from_distribution(self):
        league = [_m("A", "T1", 3, 0, 1, 0)]
        cup = [_m("A", "T2", 5, 0, 2, 0, is_league=False)]
        data = _raw(
            home_matches=league + cup + [_m("A", f"T{i}", 1, 0, 0, 0) for i in range(4)],
            away_matches=[_m(f"T{i}", "B", 0, 1, 0, 0) for i in range(5)],
        )
        result = analyze_match(data)
        assert result.ft.all_ratios.get("5-0", 0) < result.ft.all_ratios.get("1-0", 0)

    def test_high_threshold_no_scores(self):
        result = analyze_match(_raw(), threshold=100.0)
        assert result.ft.scores_1 == []
        assert result.ft.scores_x == []
        assert result.ft.scores_2 == []
        assert not result.ft.has_any_3_5_plus

    def test_low_threshold_many_scores(self):
        result = analyze_match(_raw(), threshold=0.5)
        total = len(result.ft.scores_1) + len(result.ft.scores_x) + len(result.ft.scores_2)
        assert total > 0
