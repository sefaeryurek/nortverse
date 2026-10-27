"""Performans paneli: tahmin defterinden tuttu/tutmadı ve kazanma yüzdeleri.

Gerçek kayıtlar (`prediction_ledger_resolved`) ile backtest (`prediction_backtest`) asla karışmaz.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text

from app.analysis.league_filter import is_main_league, is_shadow_league
from app.analysis.market_resolver import resolve
from app.analysis.performance import (
    GROUP_FIELDS,
    calibration_buckets,
    dedupe_decisions,
    expand_by_archive,
    group_summaries,
    summarize,
)
from app.config import ISTANBUL_TZ
from app.db.connection import get_session

router = APIRouter()

Source = Literal["live_ht", "top_pick", "market_summary"]
Informational = Literal["all", "main", "info"]
# Ekrandaki 7 ana lig ya da gölgedeki yeni ligler (Sprint 92) — karneleri birbirine karışmaz.
Scope = Literal["main", "shadow"]


def _in_scope(league_name: str | None, scope: str) -> bool:
    return is_shadow_league(league_name) if scope == "shadow" else is_main_league(league_name)

_LEDGER_SQL = """
    SELECT l.id, l.source, l.rule_version, l.match_id, l.league_name, m.kickoff_time, l.recorded_at,
           l.period, l.market, l.selection, l.archive, l.prob_shown_bp, l.confidence_tier,
           l.informational, l.sample_n, l.agreement, l.baseline_selection, l.ht_home, l.ht_away, l.details,
           l.outcome, l.res_ft_home, l.res_ft_away, l.res_ht_home, l.res_ht_away,
           m.home_team, m.away_team
    FROM prediction_ledger_resolved l
    JOIN matches m ON m.match_id = l.match_id
    WHERE l.source = :source AND l.resolver_version IS DISTINCT FROM 'invalidated' {filters}
    ORDER BY m.kickoff_time DESC, l.match_id, l.market
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


def on_screen_rule_version(source: str) -> str:
    """Kaynağın ekranda gösterilen kural sürümü. Sürüm verilmeyen özetler gölge/eski kayıtları karıştırmaz."""
    from app.analysis.live_poisson import LIVE_POISSON_RULE_VERSION
    from app.analysis.prematch_v4 import MARKET_SUMMARY_RULE_VERSION
    from app.analysis.prematch_v5 import V5_RULE_VERSION

    # Sprint 93: canlıda ekrandaki karar takım gücü modeli (live-poisson-v1.1); live-arch-v2 onay rozeti + gölge
    return {"live_ht": LIVE_POISSON_RULE_VERSION, "top_pick": V5_RULE_VERSION,
            "market_summary": MARKET_SUMMARY_RULE_VERSION}[source]


async def _load(source: str, rule_version: str | None, date_from: date | None, date_to: date | None,
                informational: str, limit: int = 50000, scope: str = "main") -> list[dict]:
    filters, params = [], {"source": source, "limit": limit}
    # Sürüm verilmezse ekrandaki sürüm; "all" açıkça tüm sürümler (gölge dahil).
    rule_version = on_screen_rule_version(source) if rule_version is None else rule_version
    if rule_version and rule_version != "all":
        filters.append("AND l.rule_version = :rule_version")
        params["rule_version"] = rule_version
    if date_from:
        filters.append("AND m.kickoff_time >= :date_from")
        params["date_from"] = datetime.combine(date_from, datetime.min.time(), ISTANBUL_TZ)
    if date_to:
        filters.append("AND m.kickoff_time < :date_to")
        params["date_to"] = datetime.combine(date_to + timedelta(days=1), datetime.min.time(), ISTANBUL_TZ)
    if informational == "main":
        filters.append("AND NOT l.informational")
    elif informational == "info":
        filters.append("AND l.informational")
    async with get_session() as session:
        rows = (await session.execute(text(_LEDGER_SQL.format(filters=" ".join(filters))), params)).all()
    # Ekranda olmayan küçük lig / silinmiş lig kayıtları (eski v3 kopyaları dahil) panelde sayılmaz;
    # gölgedeki ligler sadece scope=shadow ile.
    return [_with_baseline(r) for r in rows if _in_scope(r.league_name, scope)]


@router.get("/api/performance/summary")
async def performance_summary(
    source: Source = Query("live_ht"),
    rule_version: str | None = Query(None, max_length=32),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    group_by: str = Query("market,tier", description="Virgülle: " + ",".join(GROUP_FIELDS)),
    informational: Informational = Query("all"),
    scope: Scope = Query("main"),
) -> dict:
    groups = [g.strip() for g in group_by.split(",") if g.strip()]
    unknown = [g for g in groups if g not in GROUP_FIELDS]
    if unknown:
        raise HTTPException(400, f"Bilinmeyen gruplama: {', '.join(unknown)}")
    rows = await _load(source, rule_version, date_from, date_to, informational, scope=scope)
    return {
        "source": source,
        "rule_versions": sorted({r["rule_version"] for r in rows}),
        **_unique_summary(rows, groups),
    }


def _unique_summary(rows: list[dict], groups) -> dict:
    """Tekil karar sayımı; sadece "arşiv" kırılımı her arşivi kendi satırıyla sayar."""
    unique = dedupe_decisions(rows)
    return {
        "overall": summarize(unique),
        "raw_resolved": sum(r.get("outcome") in ("hit", "miss") for r in rows),
        "groups": {g: group_summaries(expand_by_archive(rows) if g == "archive" else unique, g) for g in groups},
        "calibration": calibration_buckets(unique),
    }


@router.get("/api/performance/predictions")
async def performance_predictions(
    source: Source = Query("live_ht"),
    day: date | None = Query(None, description="İstanbul günü (maç başlama)"),
    rule_version: str | None = Query(None, max_length=32),
    limit: int = Query(300, ge=1, le=1000),
    scope: Scope = Query("main"),
) -> list[dict]:
    rows = await _load(source, rule_version, day, day, "all", limit=limit, scope=scope)
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


def _backtest_groups(strategy: str, rule_version: str) -> tuple[str, ...]:
    from app.analysis.live_archive import LIVE_ARCHIVE_RULE_VERSIONS
    if rule_version in LIVE_ARCHIVE_RULE_VERSIONS:
        return ("risk", "archive", "period_market", "league")
    return _BACKTEST_GROUPS.get(strategy, ("market",))


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
        "created_at": r.created_at.isoformat(), "n": r.n, "current": _is_current(r.rule_version, r.params or {}),
    } for r in rows]


def _is_current(rule_version: str, params: dict) -> bool:
    """Koşu bugünkü sürüm ve ayarlarla mı üretildi? (deneme koşuları seçicide ikincil gösterilir)

    Parmak izi koşunun kendi kural sürümüne göre seçilir (eskiden v5 v4'le, Poisson canlı arşivle
    karşılaştırılıyordu → ekrandaki strateji "güncel değil" görünüyordu). Sürüm artmışsa eski koşu güncel değildir.
    """
    from app.analysis import live_2h, live_archive, live_model, live_poisson, prematch_v4, prematch_v5

    if rule_version == live_model.LIVE_RULE_VERSION:
        return params.get("alpha") == live_model.ALPHA
    fingerprints = {
        live_archive.LIVE_ARCHIVE_RULE_VERSION: live_archive.rule_params_fingerprint,
        live_poisson.LIVE_POISSON_RULE_VERSION: live_poisson.rule_params_fingerprint,
        live_2h.LIVE_2H_RULE_VERSION: live_2h.rule_params_fingerprint,
        prematch_v5.V5_RULE_VERSION: prematch_v5.rule_params_fingerprint,
        prematch_v4.V4_RULE_VERSION: prematch_v4.rule_params_fingerprint,
        prematch_v4.MARKET_SUMMARY_RULE_VERSION: prematch_v4.rule_params_fingerprint,
    }
    fingerprint = fingerprints.get(rule_version)
    return fingerprint is not None and params.get("params_fingerprint") == fingerprint()


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
    unique = dedupe_decisions(rows)
    result = {
        "run_id": run.id, "source": run.strategy, "rule_versions": [run.rule_version],
        "overall": summarize(dedupe_decisions(main)),
        "raw_resolved": sum(r.get("outcome") in ("hit", "miss") for r in main),
        "informational": summarize(dedupe_decisions([r for r in rows if r["informational"]])),
        "groups": {g: group_summaries(expand_by_archive(rows) if g == "archive" else unique, g)
                   for g in _backtest_groups(run.strategy, run.rule_version)},
        "calibration": calibration_buckets(dedupe_decisions(main)),
    }
    if len(_backtest_cache) >= 8:
        _backtest_cache.pop(next(iter(_backtest_cache)))
    _backtest_cache[run_id] = result
    return result


# ── Canlı İY: canlıya giren her maç ve devre arası %85+ işaretlerinin sonucu ──

_LIVE_MATCHES_SQL = """
    SELECT l.match_id, l.rule_version, l.market, l.period, l.selection, l.archive, l.prob_shown_bp,
           l.sample_n, l.confidence_tier, l.details, l.recorded_at, m.kickoff_time, l.ht_home, l.ht_away,
           l.outcome, l.res_ft_home, l.res_ft_away, l.res_ht_home, l.res_ht_away,
           m.home_team, m.away_team, m.league_name
    FROM prediction_ledger_resolved l
    JOIN matches m ON m.match_id = l.match_id
    WHERE l.source = 'live_ht' AND m.kickoff_time >= :start AND m.kickoff_time < :end
      AND l.resolver_version IS DISTINCT FROM 'invalidated'
    ORDER BY m.kickoff_time, l.match_id, l.id
"""


def _merge_pick(picks: list[dict], pick: dict, sources: list[str] | None = None) -> None:
    """Aynı periyot/pazar/seçim farklı arşivlerden geldiyse tek işaret: kaynaklar `labels`'a eklenir,
    gösterilen yüzde/örneklem en büyük örneklemli kaynaktan (tekil sayım)."""
    for existing in picks:
        key = ("period", "market", "selection", "rule_version")
        if all(existing.get(k) == pick.get(k) for k in key):
            existing["labels"].append(pick["label"])
            if (pick["n"], pick["pct"]) > (existing["n"], existing["pct"]):
                existing.update({k: pick[k] for k in ("archive", "label", "pct", "n", "risky")})
            return
    picks.append({**pick, "labels": list(sources) if sources else [pick["label"]]})


@router.get("/api/performance/live-matches")
async def live_matches(day: date = Query(..., description="İstanbul günü (maç başlama)"),
                       scope: Scope = Query("main")) -> list[dict]:
    """Canlıya giren (devre arasında kaydedilen) her maç: %85+ arşiv işaretleri ve tuttu/tutmadı."""
    from app.analysis.live_archive import LIVE_ARCHIVE_RULE_VERSIONS

    start = datetime.combine(day, datetime.min.time(), ISTANBUL_TZ)
    async with get_session() as session:
        rows = (await session.execute(text(_LIVE_MATCHES_SQL),
                                      {"start": start, "end": start + timedelta(days=1)})).all()
    matches: dict[str, dict] = {}
    for r in rows:
        if not _in_scope(r.league_name, scope):
            continue  # canlı sayfada olmayan küçük lig kayıtları değerlendirmede de gösterilmez
        entry = matches.setdefault(r.match_id, {
            "match_id": r.match_id, "home_team": r.home_team, "away_team": r.away_team,
            "league_name": r.league_name, "kickoff_time": r.kickoff_time.isoformat(),
            "recorded_at": r.recorded_at.isoformat(), "ht": f"{r.ht_home}-{r.ht_away}",
            "final_ht": None, "final_ft": None, "picks": [],
        })
        if r.res_ft_home is not None:
            entry["final_ft"] = f"{r.res_ft_home}-{r.res_ft_away}"
            entry["final_ht"] = None if r.res_ht_home is None else f"{r.res_ht_home}-{r.res_ht_away}"
        if r.rule_version not in LIVE_ARCHIVE_RULE_VERSIONS:
            continue  # eski COND modeli ekranda yok; sadece arka planda ölçülür
        details = r.details or {}
        label = details.get("label") or (r.archive or "genel").upper()
        _merge_pick(entry["picks"], {
            "period": r.period, "market": r.market, "selection": r.selection,
            "archive": r.archive or "genel", "label": label,
            "pct": round(r.prob_shown_bp / 100, 1), "n": r.sample_n or 0,
            "risky": r.confidence_tier == "insufficient", "outcome": r.outcome or "pending",
            "rule_version": r.rule_version, "archive_pct": details.get("archive_pct"),
        }, sources=details.get("sources"))
    for entry in matches.values():
        resolved = [p for p in entry["picks"] if p["outcome"] in ("hit", "miss")]
        entry["hits"] = sum(p["outcome"] == "hit" for p in resolved)
        entry["resolved"] = len(resolved)
        entry["picks"].sort(key=lambda p: (p["risky"], -p["pct"]))
    return list(matches.values())
