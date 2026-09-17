"""Sprint 20 — Tarihsel veri onarımı testleri."""

from app.analysis.repair import detect_issues, needs_normalization


def _row(**overrides):
    """Test için minimal maç kaydı."""
    base = {
        "match_id": "123456",
        "home_team": "TeamA",
        "away_team": "TeamB",
        "league_code": "English Premier League",
        "league_name": "English Premier League",
        "actual_ft_home": 2,
        "actual_ft_away": 1,
        "actual_ht_home": 1,
        "actual_ht_away": 0,
        "actual_h2_home": 1,
        "actual_h2_away": 1,
    }
    base.update(overrides)
    return base


class TestDetectIssues:
    def test_clean_row_no_issue(self):
        assert detect_issues(_row()) is None

    def test_empty_home_team(self):
        result = detect_issues(_row(home_team=""))
        assert result is not None
        assert result[0] == "empty_team"

    def test_question_mark_away_team(self):
        result = detect_issues(_row(away_team="?"))
        assert result is not None
        assert result[0] == "empty_team"

    def test_none_home_team(self):
        result = detect_issues(_row(home_team=None))
        assert result is not None
        assert result[0] == "empty_team"

    def test_non_league_cup_match(self):
        result = detect_issues(_row(
            league_code="UEFA Champions League",
            league_name="UEFA Champions League",
        ))
        assert result is not None
        assert result[0] == "non_league"

    def test_negative_score(self):
        result = detect_issues(_row(actual_ft_home=-1))
        assert result is not None
        assert result[0] == "bad_score"
        assert "-1" in result[1]

    def test_excessive_score(self):
        result = detect_issues(_row(actual_ft_away=20))
        assert result is not None
        assert result[0] == "bad_score"
        assert "20" in result[1]

    def test_score_15_is_ok(self):
        assert detect_issues(_row(actual_ft_home=15)) is None

    def test_score_16_is_bad(self):
        result = detect_issues(_row(actual_ft_home=16))
        assert result is not None
        assert result[0] == "bad_score"

    def test_negative_ht_score(self):
        result = detect_issues(_row(actual_ht_home=-2))
        assert result is not None
        assert result[0] == "bad_score"

    def test_inconsistent_half_home(self):
        result = detect_issues(_row(actual_ht_home=3, actual_ft_home=2))
        assert result is not None
        assert result[0] == "inconsistent_half"

    def test_inconsistent_half_away(self):
        result = detect_issues(_row(actual_ht_away=2, actual_ft_away=1))
        assert result is not None
        assert result[0] == "inconsistent_half"

    def test_consistent_half_ok(self):
        assert detect_issues(_row(actual_ht_home=1, actual_ft_home=3)) is None

    def test_equal_half_ok(self):
        assert detect_issues(_row(actual_ht_home=2, actual_ft_home=2)) is None

    def test_null_scores_ok(self):
        assert detect_issues(_row(
            actual_ft_home=None, actual_ft_away=None,
            actual_ht_home=None, actual_ht_away=None,
        )) is None

    def test_null_ht_with_ft_ok(self):
        assert detect_issues(_row(actual_ht_home=None, actual_ft_home=3)) is None

    def test_priority_empty_team_over_score(self):
        result = detect_issues(_row(home_team="", actual_ft_home=-5))
        assert result[0] == "empty_team"

    def test_priority_non_league_over_score(self):
        result = detect_issues(_row(
            league_code="FA Cup",
            league_name="FA Cup",
            actual_ft_home=-1,
        ))
        assert result[0] == "non_league"


class TestNeedsNormalization:
    def test_already_canonical(self):
        assert not needs_normalization("English Premier League", "English Premier League")

    def test_code_needs_normalize(self):
        assert needs_normalization("ENG PR", "English Premier League")

    def test_name_needs_normalize(self):
        assert needs_normalization("English Premier League", "eng pr")

    def test_both_need_normalize(self):
        assert needs_normalization("ENG PR", "Premier League")

    def test_unknown_league_no_change(self):
        assert not needs_normalization("Some Unknown League", "Some Unknown League")

    def test_none_values(self):
        assert not needs_normalization(None, None)

    def test_empty_values(self):
        assert not needs_normalization("", "")

    def test_turkish_league(self):
        assert needs_normalization("TUR D1", "Turkish Super Lig")
