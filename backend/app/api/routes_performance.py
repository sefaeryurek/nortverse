"""Performans paneli: tahmin defterinden tuttu/tutmadı ve kazanma yüzdeleri.

Gerçek kayıtlar (`prediction_ledger_resolved`) ile backtest (`prediction_backtest`) asla karışmaz.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text

from app.analysis.market_resolver import resolve
from app.analysis.performance import GROUP_FIELDS, calibration_buckets, group_summaries, summarize
from app.config import ISTANBUL_TZ
from app.db.connection import get_session

router = APIRouter()

Source = Literal["live_ht", "top_pick", "market_summary"]
Informational = Literal["all", "main", "info"]

_LEDGER_SQL = """
    SELECT l.id, l.source, l.rule_version, l.match_id, l.league_name, l.kickoff_time, l.recorded_at,
           l.period, l.market, l.selection, l.archive, l.prob_shown_bp, l.confidence_tier,
           l.informational, l.sample_n, l.agreement, l.baseline_selection, l.ht_home, l.ht_away, l.details,
           l.outcome, l.res_ft_home, l.res_ft_away, l.res_ht_home, l.res_ht_away,
           m.home_team, m.away_team
    FROM prediction_ledger_resolved l
    JOIN matches m ON m.match_id = l.match_id
    WHERE l.source = :source {filters}
    ORDER BY l.kickoff_time DESC, l.match_id, l.market
    LIMIT :limit
"""


def _with_baseline(row) -> dict:
    data = dict(row._mapping)
    baseline = None
    if data["baseline_selection"] and data["outcome"] in ("hit", "miss"):
        ft = (data["res_ft_home"], data["res_ft_away"]) if data["res_ft_home"] is not None else None
        ht = (data["res_ht_home"], data["res_ht_away"]) if data["res_ht_home"] is not None else None
        try:
            baseline = resolve(data["period"], data["market"], data["baseline_selection"], ht, ft)
        except ValueError:
            baseline = None
    data["baseline_outcome"] = baseline
    return data


async def _load(source: str, rule_version: str | None, date_from: date | None, date_to: date | None,
                informational: str, limit: int = 50000) -> list[dict]:
    filters, params = [], {"source": source, "limit": limit}
    if rule_version:
        filters.append("AND l.rule_version = :rule_version")
        params["rule_version"] = rule_version
    if date_from:
        filters.append("AND l.kickoff_time >= :date_from")
        params["date_from"] = datetime.combine(date_from, datetime.min.time(), ISTANBUL_TZ)
    if date_to:
        filters.append("AND l.kickoff_time < :date_to")
        params["date_to"] = datetime.combine(date_to + timedelta(days=1), datetime.min.time(), ISTANBUL_TZ)
    if informational == "main":
        filters.append("AND NOT l.informational")
    elif informational == "info":
        filters.append("AND l.informational")
    async with get_session() as session:
        rows = (await session.execute(text(_LEDGER_SQL.format(filters=" ".join(filters))), params)).all()
    return [_with_baseline(r) for r in rows]


@router.get("/api/performance/summary")
async def performance_summary(
    source: Source = Query("live_ht"),
    rule_version: str | None = Query(None, max_length=32),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    group_by: str = Query("market,tier", description="Virgülle: " + ",".join(GROUP_FIELDS)),
    informational: Informational = Query("all"),
) -> dict:
    groups = [g.strip() for g in group_by.split(",") if g.strip()]
    unknown = [g for g in groups if g not in GROUP_FIELDS]
    if unknown:
        raise HTTPException(400, f"Bilinmeyen gruplama: {', '.join(unknown)}")
    rows = await _load(source, rule_version, date_from, date_to, informational)
    return {
        "source": source,
        "rule_versions": sorted({r["rule_version"] for r in rows}),
        "overall": summarize(rows),
        "groups": {g: group_summaries(rows, g) for g in groups},
        "calibration": calibration_buckets(rows),
    }


@router.get("/api/performance/predictions")
async def performance_predictions(
    source: Source = Query("live_ht"),
    day: date | None = Query(None, description="İstanbul günü (maç başlama)"),
    rule_version: str | None = Query(None, max_length=32),
    limit: int = Query(300, ge=1, le=1000),
) -> list[dict]:
    rows = await _load(source, rule_version, day, day, "all", limit=limit)
    return [{
        "id": r["id"], "match_id": r["match_id"], "home_team": r["home_team"], "away_team": r["away_team"],
        "league_name": r["league_name"], "kickoff_time": r["kickoff_time"].isoformat(),
        "recorded_at": r["recorded_at"].isoformat(), "rule_version": r["rule_version"],
        "period": r["period"], "market": r["market"], "selection": r["selection"], "archive": r["archive"],
        "prob_pct": round(r["prob_shown_bp"] / 100, 1), "tier": r["confidence_tier"],
        "informational": r["informational"], "sample_n": r["sample_n"],
        "baseline_selection": r["baseline_selection"], "baseline_outcome": r["baseline_outcome"],
        "ht": None if r["ht_home"] is None else f'{r["ht_home"]}-{r["ht_away"]}',
        "final_ht": None if r["res_ht_home"] is None else f'{r["res_ht_home"]}-{r["res_ht_away"]}',
        "final_ft": None if r["res_ft_home"] is None else f'{r["res_ft_home"]}-{r["res_ft_away"]}',
        "outcome": r["outcome"] or "pending",
        "late": bool((r["details"] or {}).get("late")),
    } for r in rows]


# ── Backtest ("bugünkü algoritma o gün ne derdi") — gerçek defterden ayrı ──

_BACKTEST_GROUPS = {
    "live_ht": ("tier", "market", "league"),
    "top_pick": ("tier", "market", "league"),
    "market_summary": ("archive", "period_market"),
}
_backtest_cache: dict[int, dict] = {}


@router.get("/api/performance/backtest/runs")
async def backtest_runs() -> list[dict]:
    async with get_session() as session:
        rows = (await session.execute(text("""
            SELECT r.id, r.strategy, r.rule_version, r.params, r.date_from, r.date_to, r.notes, r.created_at,
                   (SELECT count(*) FROM prediction_backtest b WHERE b.run_id = r.id) AS n
            FROM backtest_runs r ORDER BY r.id DESC
        """))).all()
    return [{
        "id": r.id, "strategy": r.strategy, "rule_version": r.rule_version, "params": r.params,
        "date_from": r.date_from.isoformat(), "date_to": r.date_to.isoformat(), "notes": r.notes,
        "created_at": r.created_at.isoformat(), "n": r.n, "current": _is_current(r.strategy, r.params or {}),
    } for r in rows]


def _is_current(strategy: str, params: dict) -> bool:
    """Koşu bugünkü ayarlarla mı üretildi? (deneme koşuları seçicide ikincil gösterilir)"""
    if strategy == "live_ht":
        from app.analysis.live_model import ALPHA
        return params.get("alpha") == ALPHA
    from app.analysis.prematch_v4 import rule_params_fingerprint
    return params.get("params_fingerprint") == rule_params_fingerprint()


@router.get("/api/performance/backtest/{run_id}/summary")
async def backtest_summary(run_id: int) -> dict:
    """Koşu değişmez (yeniden üretim yeni id açar) → özet süreç içinde önbelleklenir."""
    cached = _backtest_cache.get(run_id)
    if cached is not None:
        return cached
    from app.analysis.backtest import load_backtest_rows

    async with get_session() as session:
        run = (await session.execute(
            text("SELECT id, strategy, rule_version FROM backtest_runs WHERE id = :id"), {"id": run_id},
        )).first()
    if run is None:
        raise HTTPException(404, "Backtest koşusu bulunamadı")
    rows = await load_backtest_rows(run_id)
    main = [r for r in rows if not r["informational"]]
    result = {
        "run_id": run.id, "source": run.strategy, "rule_versions": [run.rule_version],
        "overall": summarize(main),
        "informational": summarize([r for r in rows if r["informational"]]),
        "groups": {g: group_summaries(rows, g) for g in _BACKTEST_GROUPS.get(run.strategy, ("market",))},
        "calibration": calibration_buckets(main),
    }
    if len(_backtest_cache) >= 8:
        _backtest_cache.pop(next(iter(_backtest_cache)))
    _backtest_cache[run_id] = result
    return result
