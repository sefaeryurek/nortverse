"""Contract tests for the normalized v3 validation schema."""

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.dialects import postgresql

from app.db.models import AnalysisSnapshotMarket, MatchFinalResultObservation


def _check_names(table) -> set[str]:
    return {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }


def test_analysis_snapshot_market_constraints_and_composite_fk() -> None:
    table = AnalysisSnapshotMarket.__table__

    assert tuple(column.name for column in table.primary_key.columns) == (
        "match_id", "rule_version", "market",
    )
    foreign_key = next(
        constraint
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    )
    assert tuple(foreign_key.column_keys) == ("match_id", "rule_version")
    assert foreign_key.ondelete == "RESTRICT"
    assert {element.target_fullname for element in foreign_key.elements} == {
        "analysis_snapshots.match_id",
        "analysis_snapshots.rule_version",
    }
    assert {
        "ck_analysis_snapshot_markets_market",
        "ck_analysis_snapshot_markets_model_selection",
        "ck_analysis_snapshot_markets_baseline_selection",
        "ck_analysis_snapshot_markets_model_score_range",
        "ck_analysis_snapshot_markets_baseline_score_range",
        "ck_analysis_snapshot_markets_model_sample_size",
        "ck_analysis_snapshot_markets_baseline_sample_size",
        "ck_analysis_snapshot_markets_model_bundle",
        "ck_analysis_snapshot_markets_baseline_bundle",
    } <= _check_names(table)


def test_result_observation_identity_uniqueness_and_checks() -> None:
    table = MatchFinalResultObservation.__table__
    ddl = str(table.c.id.type.compile(dialect=postgresql.dialect()))

    assert ddl == "BIGINT"
    assert table.c.id.autoincrement is True
    assert any(
        isinstance(constraint, UniqueConstraint)
        and tuple(constraint.columns.keys()) == ("match_id", "source", "source_revision")
        for constraint in table.constraints
    )
    foreign_key = next(
        constraint for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    )
    assert {element.target_fullname for element in foreign_key.elements} == {"matches.match_id"}
    assert foreign_key.ondelete == "RESTRICT"
    assert table.c.ingested_at.server_default is not None
    assert {
        "ck_match_final_result_observations_chronology",
        "ck_match_final_result_observations_score_range",
        "ck_match_final_result_observations_source",
    } <= _check_names(table)
    assert {index.name for index in table.indexes} == {
        "ix_match_final_result_observations_match_ingested",
    }


def test_v3_snapshot_requires_baseline_version() -> None:
    assert "ck_analysis_snapshots_v3_baseline_version" in _check_names(
        AnalysisSnapshotMarket.metadata.tables["analysis_snapshots"]
    )
