"""Avrupa kupaları seçenek B (Sprint 94 P4): kupa arşivi + canlı "aynı kupa + aynı İY" gölge kuralı."""

import inspect
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.analysis import live_cup
from app.analysis.league_filter import is_supported_league, is_tracked_cup, is_tracked_league, tracked_cup_name
from app.api import live_ledger
from app.models import FixtureMatch
from app.pipeline.model_only import cup_match_row
from app.scraper.cup import parse_cup_season
from app.scraper.fixture_scores import FixtureScore

UEL = "UEFA Europa League"
NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)


def _season_json() -> dict:
    """Kaynak dosyanın gerçek biçimi (29 Ekim örneğinden kısaltılmış)."""
    return {
        "CupKindList": [[26763, 0, "Qualifi 1", "0", 0, 1], [27250, 1, "League Round", "1", 0, 0],
                        [28302, 0, "1/8 Final", "0", 0, 1]],
        "TeamList": [[724, "PAOK", "", ""], [714, "Maccabi Tel Aviv", "", ""], [238, "Midtjylland", "", ""],
                     [14, "Sturm Graz", "", ""]],
        "ScheduleList": {
            "G27250A": [
                [1, 113, -1, "2025-09-25 00:45", 724, 714, "0-0", "0-0"],
                [2, 113, -1, "2025-09-25 03:00", 238, 14, "2-0", "1-0"],
                [3, 113, 0, "2025-12-11 03:00", 724, 238, "", ""],           # oynanmamış
                [4, 113, -1, "2025-10-02 03:00", 14, 724, "1-0", "2-0"],     # İY > MS: bozuk
                [5, 113, -1, "2025-10-02 03:00", 999, 724, "1-1", "0-0"],    # bilinmeyen takım
            ],
            "G28302": [[6, 113, -1, "2026-03-13 04:00", 724, 238, "2-2", "1-1"]],  # eleme turu: uzatma olabilir
            "G26763": [[7, 113, -1, "2025-07-11 02:00", 14, 238, "3-1", "1-1"]],   # ön eleme
        },
    }


def test_parse_takes_only_finished_league_stage_matches():
    rows = parse_cup_season(_season_json(), UEL, "2025-2026")
    assert [r["match_id"] for r in rows] == ["1", "2"]
    first = rows[1]
    assert first["home_team"] == "Midtjylland" and (first["ht_home"], first["ft_home"]) == (1, 2)
    assert first["round"] == "League Round" and first["season"] == "2025/2026"
    # kaynak saati UTC+8: 03:00 → 19:00 UTC (21:00 CEST)
    assert first["kickoff_time"] == datetime(2025, 9, 24, 19, 0, tzinfo=timezone.utc)


def test_parse_tolerates_garbage():
    assert parse_cup_season({}, UEL, "2025-2026") == []
    assert parse_cup_season({"ScheduleList": {"G1A": "x"}, "CupKindList": [[1, 1, "L"]]}, UEL, "2025-2026") == []


def test_cups_are_tracked_but_never_leagues():
    for name in ("UEFA Europa League", "UEFA Champions League", "UEFA Conference League"):
        assert is_tracked_cup(name) and not is_supported_league(name) and not is_tracked_league(name)
    assert tracked_cup_name("UEFA Europa Conference League") == "UEFA Conference League"
    assert not is_tracked_cup("CAF Champions League") and not is_tracked_cup("English Premier League")


def _rows(cup: str, ht, ft, n, *, days_ago: int = 30):
    kickoff = NOW - timedelta(days=days_ago)
    return [(cup, *ht, *ft, kickoff)] * n


def test_decide_uses_same_cup_then_pooled_history():
    rows = _rows(UEL, (1, 0), (2, 0), 40) + _rows("UEFA Champions League", (0, 2), (0, 3), 20) \
        + _rows("UEFA Conference League", (0, 2), (1, 3), 20)
    table = live_cup.build_table(rows, NOW)
    picks = {(p["period"], p["market"]): p for p in live_cup.decide(table, UEL, (1, 0))}
    assert picks[("ft", "result")]["selection"] == "1" and picks[("ft", "result")]["level"] == "cup"
    assert picks[("ft", "result")]["n"] == 40 and picks[("ft", "result")]["pct"] >= 85
    # UCL'de 0-2 İY'li 20 maç (<30) → üç kupanın ortak geçmişi (40 maç), hepsi deplasman kazandı
    ucl = {(p["period"], p["market"]): p for p in live_cup.decide(table, "UEFA Champions League", (0, 2))}
    assert ucl[("ft", "result")]["selection"] == "2" and ucl[("ft", "result")]["level"] == "pooled"


def test_decide_needs_30_matches_and_85_percent():
    table = live_cup.build_table(_rows(UEL, (1, 0), (2, 0), 20), NOW)
    assert live_cup.decide(table, UEL, (1, 0)) == []                 # 20 maç: kapı yok
    split = _rows(UEL, (0, 0), (1, 0), 20) + _rows(UEL, (0, 0), (0, 0), 20)
    picks = live_cup.decide(live_cup.build_table(split, NOW), UEL, (0, 0))
    assert all(p["market"] != "result" for p in picks)              # %50 – %50: MS kararı yok


def test_table_ignores_results_not_known_three_hours_before():
    rows = _rows(UEL, (1, 0), (2, 0), 40, days_ago=0)                # NOW'da başlamış → kesimin sonrası
    assert live_cup.decide(live_cup.build_table(rows, NOW), UEL, (1, 0)) == []


def test_ledger_rows_are_shadow_with_cup_details():
    table = live_cup.build_table(_rows(UEL, (1, 0), (2, 0), 40), NOW)
    picks = live_cup.decide(table, UEL, (1, 0))
    rows = live_cup.ledger_rows(picks, {"match_id": "9"}, cup=UEL)
    assert rows and {r["rule_version"] for r in rows} == {live_cup.LIVE_CUP_SHADOW_VERSION}
    assert all(r["details"]["shadow"] and r["details"]["cup"] == UEL for r in rows)


def test_cup_match_row_is_model_only_and_screens_bad_fixtures():
    kickoff = NOW + timedelta(hours=5)
    row = cup_match_row(FixtureMatch(match_id="9", home_team="PAOK", away_team="Lyon", league_code=UEL,
                                     league_name=UEL, kickoff_time=kickoff), NOW)
    assert row["model_only"] is True and row["league_name"] == UEL and "ft_scores_1" not in row
    assert cup_match_row(FixtureMatch(match_id="9", home_team="?", away_team="Lyon", league_code=UEL,
                                      league_name=UEL, kickoff_time=kickoff), NOW) is None
    assert cup_match_row(FixtureMatch(match_id="9", home_team="A", away_team="B", league_code="ENG PR",
                                      league_name="English Premier League", kickoff_time=kickoff), NOW) is None


@pytest.mark.asyncio
async def test_live_freeze_cup_writes_only_cup_rule(monkeypatch):
    table = live_cup.build_table(_rows(UEL, (1, 0), (2, 0), 40), datetime.now(timezone.utc))
    monkeypatch.setattr(live_cup, "get_cup_table", AsyncMock(return_value=table))
    for name in ("_poisson_shadow", "_live_2h_shadow", "_windowed_shadows"):
        monkeypatch.setattr(live_ledger, name, AsyncMock(side_effect=AssertionError(f"{name} kupada çalışmaz")))
    monkeypatch.setattr(live_ledger, "market_snapshot", AsyncMock(return_value=None))
    monkeypatch.setattr(live_ledger, "_ht_observation_id", AsyncMock(return_value=3))
    written: list = []

    async def record(_session, rows):
        written.extend(rows)
        return len(rows)

    @asynccontextmanager
    async def fake_session():
        yield object()

    monkeypatch.setattr(live_ledger, "record_predictions", record)
    monkeypatch.setattr(live_ledger, "get_session", fake_session)
    match = SimpleNamespace(match_id="9", league_name=UEL, league_code=UEL, home_team="PAOK", away_team="Lyon",
                            kickoff_time=datetime.now(timezone.utc) - timedelta(minutes=50), model_only=True,
                            pattern_ft_b=None, pattern_ft_c=None, pattern_ft_d=None,
                            pattern_b_hash=None, pattern_c_hash=None, pattern_d_hash=None)
    assert await live_ledger.freeze_live_prediction(match, FixtureScore("9", "live", 1, 0, minute="HT")) == "frozen"
    assert written and {r["rule_version"] for r in written} == {live_cup.LIVE_CUP_SHADOW_VERSION}
    assert all(r["details"]["model_only"] and r["details"]["cup"] == UEL for r in written)


def test_cup_scope_scorecard_is_separate():
    from app.api.routes_performance import _in_scope

    assert _in_scope(UEL, "cup") and not _in_scope(UEL, "main") and not _in_scope(UEL, "shadow")
    assert not _in_scope("English Premier League", "cup")


def test_cleanup_commands_skip_model_only_rows():
    """prune-non-league / repair-archive kupa ve yalnız model satırlarını "lig dışı" diye silmemeli."""
    from app.cli.archive_cmds import repair_archive_cmd
    from app.cli.audit_cmds import prune_non_league_cmd

    for fn in (prune_non_league_cmd, repair_archive_cmd):
        assert "Match.model_only.is_(False)" in inspect.getsource(fn)
