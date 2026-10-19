"""Arşiv-3 (algoritma d4): takım gücü (λ ev, λ dep) uzayında aynı ligden en yakın K maç."""

import math
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.analysis.pattern_d import _build_pool, find_pattern_d_all_periods, nearest

AS_OF = datetime(2026, 10, 1, tzinfo=timezone.utc)
LEAGUE = "English Premier League"


def _row(match_id, lam_h, lam_a, league=LEAGUE, kickoff=None, ft=(2, 1), ht=(1, 0)):
    kickoff = kickoff or AS_OF - timedelta(days=30)
    return (match_id, lam_h, lam_a, ft[0], ft[1], ht[0], ht[1], ft[0] - ht[0], ft[1] - ht[1], league, kickoff)


async def _run(target, rows, **kwargs):
    pool = _build_pool(rows)
    with patch("app.analysis.pattern_d._load_pool", new_callable=AsyncMock, return_value=pool):
        kwargs.setdefault("as_of", AS_OF)
        kwargs.setdefault("league_name", LEAGUE)
        return await find_pattern_d_all_periods(target, **kwargs)


def test_pool_skips_missing_lambdas_and_groups_by_league():
    pool = _build_pool([_row("1", 1.5, 1.0), _row("2", None, 1.0), _row("3", 1.2, 0.9, league="Spanish La Liga")])
    assert [c.match_id for c in pool.by_league[LEAGUE]] == ["1"]
    assert [c.match_id for c in pool.by_league["Spanish La Liga"]] == ["3"]


def test_nearest_orders_by_log_distance_and_respects_cutoff_and_self():
    pool = _build_pool([
        _row("near", 1.6, 1.0), _row("far", 0.6, 2.2), _row("mid", 1.9, 0.8),
        _row("self", 1.5, 1.0), _row("future", 1.5, 1.0, kickoff=AS_OF + timedelta(days=1)),
    ])
    hits = nearest(pool.by_league[LEAGUE], (1.5, 1.0), cutoff=AS_OF, exclude_match_id="self", top_k=2)
    assert [c.match_id for _, c in hits] == ["near", "mid"]
    assert hits[0][0] == pytest.approx(math.log(1.6 / 1.5))


@pytest.mark.asyncio
async def test_top_k_limits_and_similarity_is_exp_minus_distance():
    rows = [_row(str(i), 1.0 + i * 0.05, 1.0) for i in range(30)]
    _, _, ft = await _run((1.0, 1.0), rows, top_k=10)
    assert ft.match_count == 10
    assert ft._matched_ids[0] == "0" and ft._matched_sims[0] == 1.0
    assert ft._matched_sims == sorted(ft._matched_sims, reverse=True)


@pytest.mark.asyncio
async def test_only_same_league_and_min_matches():
    rows = [_row(str(i), 1.5, 1.0) for i in range(5)] + [_row(f"x{i}", 1.5, 1.0, league="Spanish La Liga") for i in range(20)]
    assert await _run((1.5, 1.0), rows, min_matches=6) == (None, None, None)
    _, _, ft = await _run((1.5, 1.0), rows, min_matches=5)
    assert ft.match_count == 5 and all(not m.startswith("x") for m in ft._matched_ids)


@pytest.mark.asyncio
async def test_no_target_or_league_returns_none():
    assert await find_pattern_d_all_periods(None, league_name=LEAGUE) == (None, None, None)
    assert await find_pattern_d_all_periods((1.2, 1.0), league_name=None) == (None, None, None)


@pytest.mark.asyncio
async def test_result_known_delay_excludes_just_finished_matches():
    rows = [_row("old", 1.5, 1.0), _row("recent", 1.5, 1.0, kickoff=AS_OF - timedelta(hours=1))]
    _, _, ft = await _run((1.5, 1.0), rows)
    assert ft._matched_ids == ["old"]


@pytest.mark.asyncio
async def test_naive_as_of_rejected():
    with pytest.raises(ValueError):
        await _run((1.5, 1.0), [_row("1", 1.5, 1.0)], as_of=datetime(2026, 10, 1))
