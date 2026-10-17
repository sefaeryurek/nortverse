"""Tahmin defteri: şema sözleşmesi ve çözüm yardımcıları."""

from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy import CheckConstraint, UniqueConstraint

from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import insert

from app.analysis.ledger import PREDICTION_DEFAULTS, _outcome_row, uniform_rows
from app.db.models import MatchHtObservation, PredictionBacktest, PredictionLedger, PredictionResolution


def _checks(table) -> set[str]:
    return {c.name for c in table.constraints if isinstance(c, CheckConstraint)}


def _uniques(table) -> dict[str, tuple[str, ...]]:
    return {c.name: tuple(c.columns.keys()) for c in table.constraints if isinstance(c, UniqueConstraint)}


def test_ledger_first_write_wins_key_and_chronology():
    table = PredictionLedger.__table__
    assert _uniques(table)["uq_prediction_ledger_decision"] == (
        "source", "rule_version", "match_id", "period", "market", "archive",
    )
    assert {"ck_prediction_ledger_chronology", "ck_prediction_ledger_recorded_after_as_of",
            "ck_prediction_ledger_source", "ck_prediction_ledger_prob_range"} <= _checks(table)


def test_backtest_is_separate_table_with_run_key():
    assert _uniques(PredictionBacktest.__table__)["uq_prediction_backtest_decision"][0] == "run_id"
    assert "origin" not in PredictionBacktest.__table__.c


def test_resolution_and_ht_observation_constraints():
    assert "uq_prediction_resolutions_state" in _uniques(PredictionResolution.__table__)
    assert {"ck_match_ht_observations_chronology", "ck_match_ht_observations_phase"} <= _checks(
        MatchHtObservation.__table__
    )


def test_uniform_fills_missing_keys():
    rows = uniform_rows([{"a": 1}, {"a": 2, "b": 3}])
    assert rows == [{"a": 1, "b": None}, {"a": 2, "b": 3}]


def _row(**kw):
    base = dict(id=1, period="ft", market="result", selection="1", deleted_at=None,
                actual_ht_home=0, actual_ht_away=0, actual_ft_home=2, actual_ft_away=1)
    base.update(kw)
    return SimpleNamespace(**base)


def test_outcome_row_hit_keeps_scores():
    out = _outcome_row(_row())
    assert out["outcome"] == "hit" and (out["ft_home"], out["ft_away"]) == (2, 1)


def test_outcome_row_deleted_match_is_void_with_all_keys():
    out = _outcome_row(_row(deleted_at=datetime.now(timezone.utc)))
    assert out["outcome"] == "void"
    assert set(out) == {"ledger_id", "outcome", "resolver_version", "ft_home", "ft_away", "ht_home", "ht_away"}


def test_outcome_row_unresolvable_without_ht_for_ht_market():
    assert _outcome_row(_row(period="ht", actual_ht_home=None, actual_ht_away=None)) is None


def test_uniform_rows_uses_column_defaults_not_null():
    rows = uniform_rows([{"a": 1, "informational": True}, {"a": 2}], PREDICTION_DEFAULTS)
    assert rows[1]["informational"] is False


def test_mixed_ledger_rows_compile_without_null_required_columns():
    base = {"source": "top_pick", "rule_version": "v", "match_id": "1", "league_name": "L",
            "kickoff_time": datetime(2026, 10, 20, tzinfo=timezone.utc),
            "as_of": datetime(2026, 10, 19, tzinfo=timezone.utc), "period": "ft",
            "market": "result", "selection": "1", "prob_shown_bp": 5000}
    rows = uniform_rows([{**base, "details": {"x": 1}}, {**base, "market": "kg", "informational": True}],
                        PREDICTION_DEFAULTS)
    params = insert(PredictionLedger).values(rows).compile(dialect=postgresql.dialect()).params
    assert params["informational_m0"] is False and params["informational_m1"] is True
    assert params["details_m1"] == {}
