import gzip
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from app.api import routes_fixture as rf
from app.api.live_snapshot import LiveSnapshot
from app.api.score_state import resolve_match_state
from app.scraper.fixture_scores import FixtureScore
from app.scraper.live_scores import parse_live_scores
from app.scraper.source_board import parse_source_board


def test_source_board_reads_all_match_states_from_gzip_json():
    data = "\r\n".join([
        "A[1]=[101,1,2,3,'A','B','2026,8,19,12,00,00',-1,2,1,,,0];",
        "A[2]=[102,1,2,3,'C','D','2026,8,19,13,00,00',3,1,1,,,0];",
        "A[3]=[103,1,2,3,'E','F','2026,8,19,14,00,00',0,0,0,,,0];",
    ])
    payload = gzip.compress(json.dumps({"ErrCode": 0, "Data": data}).encode())
    scores = parse_source_board(payload)
    assert (scores["101"].status, scores["101"].home, scores["101"].away) == ("finished", 2, 1)
    assert scores["102"].status == "live"
    assert scores["103"].status == "scheduled"


def test_live_board_uses_source_minute_and_ignores_unreadable_score():
    html = """
      <tr id="tr1_101"><td class="status">45+4</td><td class="f-b blue">1 - 0</td></tr>
      <tr id="tr1_102"><td class="status">FT</td><td class="f-b blue">2 - 1</td></tr>
      <tr id="tr1_103"><td class="status">FT</td><td class="f-b blue">?</td></tr>
      <tr id="tr1_104"><td class="status">HT</td><td class="f-b blue">0 - 0</td></tr>
    """
    scores = parse_live_scores(html)
    assert (scores["101"].status, scores["101"].minute) == ("live", "45+4")
    assert scores["102"].status == "finished"
    assert "103" not in scores
    assert (scores["104"].status, scores["104"].minute) == ("live", "HT")


def test_finished_state_wins_and_stale_live_is_not_presented_as_current():
    now = datetime.now(timezone.utc)
    item = {"match_id": "101", "score_status": "live", "score_home": 1, "score_away": 0,
            "score_checked_at": "2026-09-19T17:00:00+00:00"}
    finished = resolve_match_state(item, None, None, None,
                                   FixtureScore("101", "finished", 2, 1), now, now)
    assert (finished.status, finished.final_home, finished.final_away) == ("finished", 2, 1)
    stale = resolve_match_state(item, now, None, None, None, None, now)
    assert stale.status == "pending"


@pytest.mark.asyncio
async def test_bulletin_keeps_live_and_scheduled_but_removes_finished(monkeypatch):
    now = datetime.now(timezone.utc)
    snapshot = LiveSnapshot({
        "101": FixtureScore("101", "finished", 2, 1),
        "102": FixtureScore("102", "live", 1, 0, minute="67"),
        "103": FixtureScore("103", "scheduled"),
    }, now)
    monkeypatch.setattr(rf, "get_live_snapshot", AsyncMock(return_value=snapshot))
    today = now.astimezone(timezone(timedelta(hours=3))).date()
    items = [{"match_id": mid, "home_team": "A", "away_team": "B", "league_code": "ENG PR",
              "league_name": "English Premier League", "kickoff_time": None}
             for mid in ("101", "102", "103")]
    visible = await rf._bulletin_items(items, today)
    assert [(row.match_id, row.status) for row in visible] == [("102", "live"), ("103", "scheduled")]
    assert (visible[0].live_home, visible[0].live_away, visible[0].live_minute) == (1, 0, "67")
