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


# --- Sprint 94 B3 (K20): lig-sezon grubu kuralları ---------------------------------------------------------
from datetime import datetime as _dt, timedelta as _td, timezone as _tz  # noqa: E402

from app.analysis.repair import detect_group_issues  # noqa: E402

_NOW = _dt(2026, 10, 28, tzinfo=_tz.utc)


def _g(mid, league, season, home, away, day, ft=1):
    return {"match_id": mid, "league_name": league, "season": season, "home_team": home, "away_team": away,
            "kickoff_time": day, "actual_ft_home": ft, "actual_ft_away": 0 if ft is not None else None}


def _season(league, season, start, n=30):
    return [_g(f"{league[:3]}{season}{i}", league, season, f"T{i}", f"U{i}", start + _td(days=7 * i)) for i in range(n)]


def test_cancelled_only_when_season_closed():
    old = _season("French Ligue 1", "2019/2020", _dt(2019, 8, 10, tzinfo=_tz.utc))
    old.append(_g("covid", "French Ligue 1", "2019/2020", "A", "B", _dt(2020, 3, 20, tzinfo=_tz.utc), ft=None))
    current = _season("Turkish Super Lig", "2026/2027", _NOW - _td(days=7 * 29))
    current.append(_g("postponed", "Turkish Super Lig", "2026/2027", "A", "B", _NOW - _td(days=40), ft=None))
    found = {mid: reason for mid, reason, _ in detect_group_issues(old + current, now=_NOW)}
    assert found == {"covid": "cancelled"}  # süren sezondaki ertelenmiş maç silinmez


def test_playoff_repeat_at_season_end():
    rows = _season("Dutch Eredivisie", "2023/2024", _dt(2023, 8, 12, tzinfo=_tz.utc))
    end = rows[-1]["kickoff_time"]
    rows.append(_g("po1", "Dutch Eredivisie", "2023/2024", "T3", "U3", end + _td(days=3)))
    rows.append(_g("early", "Dutch Eredivisie", "2023/2024", "T4", "U4", rows[10]["kickoff_time"]))
    found = {mid: reason for mid, reason, _ in detect_group_issues(rows, now=_NOW)}
    assert found == {"po1": "playoff"}  # sezon ortasındaki tekrar play-off sayılmaz


def test_split_format_league_repeats_are_normal():
    rows = _season("Scottish Premiership", "2023/2024", _dt(2023, 8, 5, tzinfo=_tz.utc))
    rows.append(_g("split", "Scottish Premiership", "2023/2024", "T3", "U3", rows[-1]["kickoff_time"] + _td(days=3)))
    assert detect_group_issues(rows, now=_NOW) == []


def test_stray_old_league_season():
    rows = _season("German Bundesliga", "2006/2007", _dt(2006, 8, 11, tzinfo=_tz.utc))
    rows.append(_g("88734", "German 2. Bundesliga", "2006/2007", "Alemannia Aachen", "Energie Cottbus",
                   _dt(2006, 10, 21, tzinfo=_tz.utc)))
    recent = [_g("new", "Chile Primera B", "2026/2027", "A", "B", _NOW - _td(days=3))]
    found = {mid: reason for mid, reason, _ in detect_group_issues(rows + recent, now=_NOW)}
    assert found == {"88734": "stray_season"}  # yeni sezondaki tek maçlık küçük lig dokunulmaz
