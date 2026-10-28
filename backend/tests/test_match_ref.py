"""Kupondaş bülten tabanlı bacak (Sprint 94 J6, K4): maç bilgisi önce `matches`, yoksa bülten önbelleği."""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.analysis import coupons, match_ref
from app.analysis.match_ref import MatchRef, latest_fixture_items, load_match_refs, ref_from_fixture
from app.api import routes_coupons as rc

NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows

    def scalars(self):
        return self


def test_ref_from_fixture_fields_and_unknown_league():
    ref = ref_from_fixture({"match_id": "5", "home_team": "Celta", "away_team": "Getafe", "league_name": "?",
                            "kickoff_time": "2026-10-29T18:00:00+00:00", "score_status": "finished",
                            "score_home": 2, "score_away": 1, "actual_ht_home": 1, "actual_ht_away": 0})
    assert ref.source == "fixture" and ref.league_name is None
    assert ref.ft == (2, 1) and ref.ht == (1, 0) and ref.kickoff_time.tzinfo is not None
    assert ref_from_fixture({"match_id": "6", "home_team": "", "away_team": "B"}) is None


def test_extra_time_score_is_not_final():
    ref = ref_from_fixture({"match_id": "5", "home_team": "A", "away_team": "B", "score_status": "finished_extra",
                            "score_home": 3, "score_away": 2})
    assert ref.ft is None and ref.status == "finished_extra"


def test_latest_non_carried_entry_wins():
    old = datetime(2026, 10, 27, tzinfo=timezone.utc)
    new = datetime(2026, 10, 28, tzinfo=timezone.utc)

    class _Session:
        async def execute(self, _sql, params):
            assert params["ids"] == ["5"]
            return _Rows([(new, {"match_id": "5", "kickoff_time": "B"}), (old, {"match_id": "5", "kickoff_time": "A"})])

    out = asyncio.run(latest_fixture_items(_Session(), ["5"], NOW))
    assert out["5"]["kickoff_time"] == "B"


def test_db_row_preferred_over_fixture(monkeypatch):
    db_row = SimpleNamespace(match_id="1", home_team="Arsenal", away_team="Chelsea", league_name="English Premier League",
                             kickoff_time=NOW, actual_ft_home=None, actual_ft_away=None, actual_ht_home=1,
                             actual_ht_away=0, deleted_at=None)

    class _Session:
        async def execute(self, *_a, **_k):
            return _Rows([db_row])

    async def items(_s, _ids, _now):
        return {"1": {"match_id": "1", "home_team": "Arsenal FC", "away_team": "Chelsea FC", "score_status": "live"},
                "2": {"match_id": "2", "home_team": "Betis", "away_team": "Sevilla", "league_name": "Copa del Rey"}}

    monkeypatch.setattr(match_ref, "latest_fixture_items", items)
    refs = asyncio.run(load_match_refs(_Session(), ["1", "2"], NOW))
    assert refs["1"].source == "db" and refs["1"].home_team == "Arsenal" and refs["1"].status == "live"
    assert refs["1"].ht == (1, 0) and refs["1"].ft is None
    assert refs["2"].source == "fixture" and refs["2"].league_name == "Copa del Rey"


def test_coupon_matches_includes_bulletin_and_cup_matches(monkeypatch):
    kick = datetime.now(timezone.utc) + timedelta(hours=5)
    db_rows = [SimpleNamespace(match_id="1", home_team="Arsenal", away_team="Chelsea",
                               league_name="English Premier League", kickoff_time=kick)]
    fixture = SimpleNamespace(matches_json=[
        {"match_id": "1", "home_team": "Arsenal FC", "away_team": "Chelsea FC", "league_name": "ENG PR",
         "kickoff_time": kick.isoformat()},
        {"match_id": "2", "home_team": "Betis", "away_team": "Sevilla", "league_name": "Copa del Rey",
         "kickoff_time": (kick - timedelta(hours=1)).isoformat()},
        {"match_id": "3", "home_team": "Bitti", "away_team": "X", "score_status": "finished"},
        {"match_id": "4", "home_team": "Ertelendi", "away_team": "X", "score_status": "postponed"},
        {"match_id": "5", "home_team": "Taşındı", "away_team": "X", "carried": True},
        {"match_id": "6", "home_team": "Silindi", "away_team": "X"},
        {"match_id": "7", "home_team": "Oynuyor", "away_team": "X", "score_status": "live",
         "kickoff_time": (kick - timedelta(hours=6)).isoformat()},
    ])
    calls = []

    class _Session:
        async def execute(self, *_a, **_k):
            calls.append(1)
            return _Rows(db_rows if len(calls) == 1 else ["6"])

        async def get(self, _model, key):
            assert key == "2026-10-29"
            return fixture

    @asynccontextmanager
    async def fake_session():
        yield _Session()

    monkeypatch.setattr(rc, "get_session", fake_session)
    out = asyncio.run(rc.coupon_matches(target_date="2026-10-29"))
    by_id = {m["match_id"]: m for m in out}
    assert set(by_id) == {"1", "2", "7"}
    assert by_id["1"]["analyzed"] and by_id["1"]["home_team"] == "Arsenal"
    assert not by_id["2"]["analyzed"] and by_id["2"]["league_name"] == "Copa del Rey"
    assert by_id["7"]["started"] and not by_id["2"]["started"]
    assert [m["match_id"] for m in out] == ["7", "2", "1"]  # başlama saatine göre


def test_settle_pending_uses_fixture_scores(monkeypatch):
    now = datetime.now(timezone.utc)  # 48 saat kuralı gerçek saate göre
    legs = [
        SimpleNamespace(id=1, match_id="2", period="ft", market="result", selection="1", line=None, odds=2.0,
                        kickoff_time=now - timedelta(hours=3)),
        SimpleNamespace(id=2, match_id="2", period="ht", market="ou", selection="over", line=0.5, odds=1.5,
                        kickoff_time=now - timedelta(hours=3)),
        SimpleNamespace(id=3, match_id="9", period="ft", market="result", selection="X", line=None, odds=3.0,
                        kickoff_time=now - timedelta(hours=60)),
    ]
    written = []

    class _Session:
        async def execute(self, stmt, *_a, **_k):
            sql = str(stmt)
            if sql.startswith("INSERT"):
                written.append(stmt.compile().params)
                return SimpleNamespace(rowcount=1)
            return _Rows(legs)

    async def refs(_s, _ids, _now):
        return {"2": MatchRef(match_id="2", home_team="Betis", away_team="Sevilla", league_name="Copa del Rey",
                              kickoff_time=now - timedelta(hours=3), source="fixture", ft=(2, 1), ht=(0, 0),
                              status="finished")}

    async def no_obs(_s, _ids):
        return {}

    monkeypatch.setattr(match_ref, "load_match_refs", refs)
    monkeypatch.setattr(coupons, "_ht_observations", no_obs)
    assert asyncio.run(coupons.settle_pending(_Session())) == 3
    by_leg = {p["leg_id"]: p for p in written}
    assert by_leg[1]["outcome"] == "hit" and by_leg[1]["score"] == "2-1"
    assert by_leg[2]["outcome"] == "miss" and by_leg[2]["score"] == "0-0"
    assert by_leg[3]["outcome"] == "void"  # bilinmeyen maç, 48 saat skor yok
