"""Sprint 8.9 — `_validate_row` (pre-write integrity guard) testleri."""

from app.pipeline.runner import _validate_row


def _base_row(**overrides) -> dict:
    """Geçerli bir satır şablonu."""
    row = {
        "match_id": "12345",
        "home_team": "Galatasaray",
        "away_team": "Fenerbahce",
        "league_code": "Turkish Super Lig",
        "season": "2025/2026",
        "actual_ft_home": 2,
        "actual_ft_away": 1,
    }
    row.update(overrides)
    return row


class TestValidateRow:
    def test_valid_row_passes(self) -> None:
        ok, reason = _validate_row(_base_row())
        assert ok is True
        assert reason is None

    def test_empty_home_team_rejected(self) -> None:
        ok, reason = _validate_row(_base_row(home_team=""))
        assert ok is False
        assert "home_team" in reason

    def test_question_mark_home_team_rejected(self) -> None:
        ok, reason = _validate_row(_base_row(home_team="?"))
        assert ok is False
        assert "home_team" in reason

    def test_empty_away_team_rejected(self) -> None:
        ok, reason = _validate_row(_base_row(away_team=""))
        assert ok is False
        assert "away_team" in reason

    def test_empty_league_rejected(self) -> None:
        ok, reason = _validate_row(_base_row(league_code=""))
        assert ok is False
        assert "league_code" in reason

    def test_cup_match_rejected(self) -> None:
        ok, reason = _validate_row(_base_row(league_code="UEFA Champions League"))
        assert ok is False
        assert "kupa" in reason.lower() or "lig maçı değil" in reason

    def test_negative_score_rejected(self) -> None:
        ok, reason = _validate_row(_base_row(actual_ft_home=-1))
        assert ok is False
        assert "actual_ft_home" in reason

    def test_extreme_score_rejected(self) -> None:
        ok, reason = _validate_row(_base_row(actual_ft_away=99))
        assert ok is False
        assert "actual_ft_away" in reason

    def test_none_score_passes(self) -> None:
        # actual_*_home None olabilir (henüz oynanmamış)
        row = _base_row()
        row["actual_ft_home"] = None
        row["actual_ft_away"] = None
        ok, reason = _validate_row(row)
        assert ok is True

    def test_zero_score_passes(self) -> None:
        ok, _ = _validate_row(_base_row(actual_ft_home=0, actual_ft_away=0))
        assert ok is True
