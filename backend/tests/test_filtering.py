"""Maç filtreleme (filtering.py) birim testleri.

check_match_filters kuralları ve select_last_n_league_matches.
"""

from __future__ import annotations

import pytest

from app.analysis.filtering import FilterCheck, check_match_filters, select_last_n_league_matches
from app.models import HistoricalMatch, MatchRawData, SkipReason


def _m(
    home: str = "A",
    away: str = "B",
    hg_ft: int = 1,
    ag_ft: int = 0,
    is_league: bool = True,
) -> HistoricalMatch:
    return HistoricalMatch(
        opponent=away,
        home_team=home,
        away_team=away,
        home_score_ft=hg_ft,
        away_score_ft=ag_ft,
        home_score_ht=0,
        away_score_ht=0,
        is_league_match=is_league,
    )


def _raw(
    home_team: str = "Fenerbahce",
    away_team: str = "Galatasaray",
    league_code: str = "TUR D1",
    league_name: str = "Turkish Super Lig",
    home_n: int = 5,
    away_n: int = 5,
    h2h_n: int = 5,
    home_league: bool = True,
    away_league: bool = True,
    h2h_league: bool = True,
) -> MatchRawData:
    return MatchRawData(
        match_id="test",
        home_team=home_team,
        away_team=away_team,
        league_code=league_code,
        league_name=league_name,
        home_recent_matches=[
            _m(home_team, f"T{i}", is_league=home_league) for i in range(home_n)
        ],
        away_recent_matches=[
            _m(f"T{i}", away_team, is_league=away_league) for i in range(away_n)
        ],
        h2h_matches=[
            _m(home_team, away_team, is_league=h2h_league) for _ in range(h2h_n)
        ],
    )


# ─── check_match_filters — geçen durumlar ───────────────────────────────────

class TestFilterPass:
    def test_normal_match_passes(self):
        result = check_match_filters(_raw())
        assert result.passed
        assert result.reason is None

    def test_exact_minimum_passes(self):
        result = check_match_filters(_raw(home_n=5, away_n=5, h2h_n=5))
        assert result.passed

    def test_custom_thresholds_pass(self):
        result = check_match_filters(
            _raw(home_n=3, away_n=3, h2h_n=2),
            min_league_matches=3,
            min_h2h=2,
        )
        assert result.passed


# ─── check_match_filters — reddedilen durumlar ──────────────────────────────

class TestFilterReject:
    def test_empty_home_team(self):
        result = check_match_filters(_raw(home_team=""))
        assert not result.passed
        assert result.reason == SkipReason.DATA_FETCH_FAILED

    def test_question_mark_away_team(self):
        result = check_match_filters(_raw(away_team="?"))
        assert not result.passed
        assert result.reason == SkipReason.DATA_FETCH_FAILED

    def test_whitespace_team(self):
        result = check_match_filters(_raw(home_team="   "))
        assert not result.passed
        assert result.reason == SkipReason.DATA_FETCH_FAILED

    def test_whitespace_question_mark(self):
        result = check_match_filters(_raw(away_team=" ? "))
        assert not result.passed
        assert result.reason == SkipReason.DATA_FETCH_FAILED

    def test_cup_match_rejected(self):
        result = check_match_filters(
            _raw(league_name="UEFA Champions League", league_code="Champions League")
        )
        assert not result.passed
        assert result.reason == SkipReason.NOT_LEAGUE_MATCH

    def test_friendly_rejected(self):
        result = check_match_filters(
            _raw(league_name="International Friendly", league_code="FRIENDLY")
        )
        assert not result.passed
        assert result.reason == SkipReason.NOT_LEAGUE_MATCH

    def test_home_insufficient(self):
        result = check_match_filters(_raw(home_n=4))
        assert not result.passed
        assert result.reason == SkipReason.HOME_TEAM_INSUFFICIENT
        assert "4" in result.detail

    def test_away_insufficient(self):
        result = check_match_filters(_raw(away_n=3))
        assert not result.passed
        assert result.reason == SkipReason.AWAY_TEAM_INSUFFICIENT

    def test_h2h_insufficient(self):
        result = check_match_filters(_raw(h2h_n=4))
        assert not result.passed
        assert result.reason == SkipReason.H2H_INSUFFICIENT

    def test_non_league_home_matches_not_counted(self):
        result = check_match_filters(_raw(home_n=10, home_league=False))
        assert not result.passed
        assert result.reason == SkipReason.HOME_TEAM_INSUFFICIENT

    def test_non_league_away_matches_not_counted(self):
        result = check_match_filters(_raw(away_n=10, away_league=False))
        assert not result.passed
        assert result.reason == SkipReason.AWAY_TEAM_INSUFFICIENT

    def test_non_league_h2h_not_counted(self):
        result = check_match_filters(_raw(h2h_n=10, h2h_league=False))
        assert not result.passed
        assert result.reason == SkipReason.H2H_INSUFFICIENT


# ─── Öncelik sırası ─────────────────────────────────────────────────────────

class TestFilterPriority:
    def test_team_check_before_league_check(self):
        result = check_match_filters(_raw(
            home_team="",
            league_name="UEFA Europa League",
            league_code="UEL",
        ))
        assert result.reason == SkipReason.DATA_FETCH_FAILED

    def test_league_check_before_match_count(self):
        result = check_match_filters(_raw(
            league_name="FIFA World Cup",
            league_code="World Cup Qualifier",
            home_n=0,
            away_n=0,
            h2h_n=0,
        ))
        assert result.reason == SkipReason.NOT_LEAGUE_MATCH

    def test_home_before_away(self):
        result = check_match_filters(_raw(home_n=2, away_n=2))
        assert result.reason == SkipReason.HOME_TEAM_INSUFFICIENT

    def test_away_before_h2h(self):
        result = check_match_filters(_raw(away_n=2, h2h_n=2))
        assert result.reason == SkipReason.AWAY_TEAM_INSUFFICIENT


# ─── FilterCheck dataclass ──────────────────────────────────────────────────

class TestFilterCheck:
    def test_defaults(self):
        fc = FilterCheck(passed=True)
        assert fc.passed
        assert fc.reason is None
        assert fc.detail is None

    def test_with_reason(self):
        fc = FilterCheck(False, SkipReason.H2H_INSUFFICIENT, "2 maç")
        assert not fc.passed
        assert fc.reason == SkipReason.H2H_INSUFFICIENT
        assert "2 maç" in fc.detail


# ─── select_last_n_league_matches ───────────────────────────────────────────

class TestSelectLastN:
    def test_filters_non_league(self):
        matches = [
            _m(is_league=True),
            _m(is_league=False),
            _m(is_league=True),
            _m(is_league=False),
            _m(is_league=True),
        ]
        result = select_last_n_league_matches(matches, 10, True, "A")
        assert len(result) == 3

    def test_limits_to_n(self):
        matches = [_m(is_league=True) for _ in range(10)]
        result = select_last_n_league_matches(matches, 3, True, "A")
        assert len(result) == 3

    def test_empty_input(self):
        result = select_last_n_league_matches([], 5, True, "A")
        assert result == []

    def test_all_cup_returns_empty(self):
        matches = [_m(is_league=False) for _ in range(5)]
        result = select_last_n_league_matches(matches, 5, True, "A")
        assert result == []
