from datetime import datetime, timedelta, timezone

import pytest

from app.analysis.engine import _get_goals_in_period, analyze_match
from app.analysis.filtering import check_match_filters
from app.analysis.history import prepare_history, select_history
from app.models import HistoricalMatch, MatchRawData, Period, SkipReason


def history(**changes):
    values = dict(home_team="A", away_team="B", opponent="B", home_score_ft=2, away_score_ft=1,
                  home_score_ht=1, away_score_ht=0, match_date=datetime(2024, 2, 1, tzinfo=timezone.utc))
    return HistoricalMatch(**(values | changes))


def test_history_excludes_future_self_duplicates_and_wrong_teams():
    cutoff = datetime(2024, 3, 1, tzinfo=timezone.utc)
    older = history(match_id="1")
    newer = history(match_id="2", match_date=datetime(2024, 2, 10))
    selected = select_history([
        older, newer, older, history(match_id="target"),
        history(match_date=cutoff), history(match_date=cutoff + timedelta(days=1)),
        history(home_team="C", away_team="D"), history(is_league_match=False),
    ], "A", before=cutoff, exclude_id="target")
    assert [m.match_id for m in selected] == ["2", "1"]


def test_h2h_requires_both_teams_and_does_not_mutate_raw():
    raw = MatchRawData(match_id="target", home_team="A", away_team="B", league_code="ENG PR",
                       h2h_matches=[history(), history(away_team="C")])
    prepared = prepare_history(raw)
    assert len(prepared.h2h_matches) == 1
    assert len(raw.h2h_matches) == 2


def test_foreign_team_rows_cannot_pass_eligibility():
    raw = MatchRawData(match_id="target", home_team="A", away_team="B", league_code="ENG PR",
                       home_recent_matches=[history(home_team="C", away_team="D") for _ in range(5)])
    assert check_match_filters(raw).reason == SkipReason.HOME_TEAM_INSUFFICIENT


def test_invalid_second_half_is_not_counted_as_zero_goals():
    invalid = history(home_score_ht=3)
    assert _get_goals_in_period(invalid, "A", Period.H2) is None
    assert _get_goals_in_period(invalid, "A", Period.FT) == 2


def test_explicit_archive_season_is_preserved():
    raw = MatchRawData(match_id="1", home_team="A", away_team="B", league_code="ENG PR")
    assert analyze_match(raw, season="2022-2023").season == "2022/2023"


@pytest.mark.parametrize("kwargs", [{"n_matches": 0}, {"n_matches": -1}, {"threshold": float("nan")}, {"threshold": 0}])
def test_invalid_analysis_configuration_is_rejected(kwargs):
    raw = MatchRawData(match_id="1", home_team="A", away_team="B", league_code="ENG PR")
    with pytest.raises(ValueError):
        analyze_match(raw, **kwargs)
