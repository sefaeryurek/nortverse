"""Gölge lig → ekran terfi raporu (Sprint 94 P3, 11-scraper notu "gölge → ekran süreci").

Terfi dört aşamalı; bu komut ilk üçünü ölçer, dördüncüsü (karar) sahibindir:
1. Veri: ≥5 sezon, son 3 sezonda takım gücü (λ) ve A3 ≥%95, H2H geçişi ≥%60, skor gecikmesi p90 <6 saat,
   lig adı kanonik, oran kapsaması ≥%80.
2. Sızıntısız backtest: lig başına ≥300 maç öncesi (v5) + ≥300 canlı karar, gösterilen − gerçek ≤2 puan.
3. Gerçek gölge karnesi: gölge havuzu ≥100 tekil kararda "yolunda/üstünde"; lig tek başına ≥30 karar ve
   "altında" değil.
4. Sahip kararı → `league_filter.PROMOTED_LEAGUES`'e lig + tarih, audit_log (`--kaydet`), CLAUDE.md.
Terfi SADECE ekranı değiştirir; ortak havuza (POOL_LEAGUES) eklemek ayrı karar ve yeni kural sürümleri ister.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import typer
from rich.table import Table

from app.cli._helpers import console

MIN_SEASONS = 5
SEASON_MIN_MATCHES = 30        # bu kadar bitmiş maçı olan sezon "kurulu" sayılır (devam eden sezon dahil)
MIN_COVERAGE_PCT = 95.0        # son 3 sezonda λ ve A3
MIN_H2H_PASS_PCT = 60.0
MAX_SCORE_DELAY_P90_H = 6.0
MIN_ODDS_COVERAGE_PCT = 80.0
MIN_BACKTEST_N = 300
MAX_CALIBRATION_GAP = 2.0      # puan
MIN_SHADOW_POOL_N = 100
MIN_LEAGUE_N = 30
RECENT_DAYS = 120              # H2H geçişi, skor gecikmesi ve oran kapsaması için pencere


def _check(name: str, ok: bool | None, detail: str) -> dict:
    return {"name": name, "ok": ok, "detail": detail}


def _gap_ok(stats: dict | None, min_n: int) -> tuple[bool, str]:
    if not stats or not stats.get("n"):
        return False, "koşu yok"
    gap = stats["shown_pct"] - stats["hit_pct"]
    ok = stats["n"] >= min_n and abs(gap) <= MAX_CALIBRATION_GAP
    return ok, f"{stats['n']} karar · gerçek %{stats['hit_pct']:.1f} · gösterilen %{stats['shown_pct']:.1f} (fark {gap:+.1f})"


def evaluate_promotion(m: dict) -> list[dict]:
    """Ölçümlerden terfi kontrolleri. `ok=None`: ölçülemedi (veri yok) — geçmiş sayılmaz."""
    checks = []
    seasons = m.get("seasons", [])
    checks.append(_check("sezon", len(seasons) >= MIN_SEASONS,
                         f"{len(seasons)} kurulu sezon (en az {MIN_SEASONS}): {', '.join(seasons) or '—'}"))
    cov = m.get("recent_coverage")
    checks.append(_check("λ_ve_A3", None if cov is None else min(cov) >= MIN_COVERAGE_PCT,
                         "veri yok" if cov is None else f"son 3 sezon λ %{cov[0]:.1f} · A3 %{cov[1]:.1f}"))
    h2h = m.get("h2h_pass_pct")
    checks.append(_check("h2h_gecisi", None if h2h is None else h2h >= MIN_H2H_PASS_PCT,
                         "son dönemde bülten analizi yok" if h2h is None else f"%{h2h:.0f} (en az %{MIN_H2H_PASS_PCT:.0f})"))
    p90 = m.get("score_delay_p90_h")
    checks.append(_check("skor_gecikmesi", None if p90 is None else p90 < MAX_SCORE_DELAY_P90_H,
                         "veri yok" if p90 is None else f"p90 {p90:.1f} saat (en fazla {MAX_SCORE_DELAY_P90_H:.0f})"))
    checks.append(_check("lig_adi", bool(m.get("canonical")), "kanonik ad ve alias var" if m.get("canonical")
                         else "lig adı LEAGUE_ALIASES'ta yok (F7)"))
    odds = m.get("odds_coverage_pct")
    checks.append(_check("oran_kapsamasi", None if odds is None else odds >= MIN_ODDS_COVERAGE_PCT,
                         "veri yok" if odds is None else f"%{odds:.0f} (en az %{MIN_ODDS_COVERAGE_PCT:.0f})"))
    for key, label in (("backtest_prematch", "backtest_mac_oncesi"), ("backtest_live", "backtest_canli")):
        ok, detail = _gap_ok(m.get(key), MIN_BACKTEST_N)
        checks.append(_check(label, ok, detail))
    for key, label in (("shadow_prematch", "golge_mac_oncesi"), ("shadow_live", "golge_canli")):
        s = m.get(key) or {}
        pool, league = s.get("pool") or {}, s.get("league") or {}
        pool_ok = pool.get("resolved", 0) >= MIN_SHADOW_POOL_N and pool.get("verdict") in ("on_track", "above")
        league_ok = league.get("resolved", 0) >= MIN_LEAGUE_N and not league.get("below", False)
        checks.append(_check(label, pool_ok and league_ok,
                             f"gölge havuzu {pool.get('resolved', 0)} karar ({pool.get('verdict', '—')}) · "
                             f"lig {league.get('resolved', 0)} karar"
                             + (f" %{league['hit_pct']:.1f} / gösterilen %{league['avg_prob_pct']:.1f}"
                                if league.get('hit_pct') is not None else "")))
    return checks


async def _collect(league: str) -> dict:
    from sqlalchemy import text

    from app.analysis.league_filter import LEAGUE_ALIASES, canonical_league_name
    from app.analysis.live_poisson import LIVE_POISSON_RULE_VERSION
    from app.analysis.performance import dedupe_decisions, summarize
    from app.analysis.prematch_v5 import V5_RULE_VERSION
    from app.analysis.stats_utils import wilson_ci
    from app.api.routes_performance import _load
    from app.db.connection import get_session

    now = datetime.now(timezone.utc)
    since = now - timedelta(days=RECENT_DAYS)
    m: dict = {"canonical": league in set(LEAGUE_ALIASES.values())}
    async with get_session() as s:
        per_season = (await s.execute(text("""
            SELECT season, count(*) n, count(team_lambda_home) lam, count(pattern_ft_d) d
            FROM matches WHERE deleted_at IS NULL AND NOT model_only AND league_name = :l
              AND actual_ft_home IS NOT NULL AND season IS NOT NULL
            GROUP BY season ORDER BY season DESC"""), {"l": league})).all()
        installed = [r for r in per_season if r.n >= SEASON_MIN_MATCHES]
        m["seasons"] = [r.season for r in installed]
        recent = installed[:3]
        if recent:
            total = sum(r.n for r in recent)
            m["recent_coverage"] = (100 * sum(r.lam for r in recent) / total, 100 * sum(r.d for r in recent) / total)
        analyzed = (await s.execute(text("""
            SELECT count(*) FROM matches WHERE deleted_at IS NULL AND NOT model_only AND league_name = :l
              AND kickoff_time >= :since AND analyzed_at < kickoff_time"""), {"l": league, "since": since})).scalar()
        skips = (await s.execute(text("""
            SELECT league_code, count(*) FROM skipped_analysis
            WHERE reason = 'h2h_insufficient' AND checked_at >= :since GROUP BY league_code"""),
            {"since": since})).all()
        h2h_skips = sum(n for code, n in skips if canonical_league_name(code) == league)
        if analyzed + h2h_skips:
            m["h2h_pass_pct"] = 100 * analyzed / (analyzed + h2h_skips)
        m["score_delay_p90_h"] = (await s.execute(text("""
            SELECT percentile_cont(0.9) WITHIN GROUP (ORDER BY extract(epoch FROM result_first_fetched_at - kickoff_time) / 3600)
            FROM matches WHERE deleted_at IS NULL AND league_name = :l AND kickoff_time >= :since
              AND result_first_fetched_at IS NOT NULL AND analyzed_at < kickoff_time"""),
            {"l": league, "since": since})).scalar()
        odds = (await s.execute(text("""
            SELECT count(*), count(*) FILTER (WHERE EXISTS (SELECT 1 FROM match_odds o WHERE o.match_id = m.match_id))
            FROM matches m WHERE m.deleted_at IS NULL AND NOT m.model_only AND m.league_name = :l
              AND m.kickoff_time >= :since AND m.actual_ft_home IS NOT NULL"""), {"l": league, "since": since})).one()
        if odds[0]:
            m["odds_coverage_pct"] = 100 * odds[1] / odds[0]
        for key, rule in (("backtest_prematch", V5_RULE_VERSION), ("backtest_live", LIVE_POISSON_RULE_VERSION)):
            row = (await s.execute(text("""
                SELECT count(*), count(*) FILTER (WHERE outcome = 'hit'), avg(prob_shown_bp)
                FROM prediction_backtest
                WHERE run_id = (SELECT max(id) FROM backtest_runs WHERE rule_version = :rv)
                  AND league_name = :l AND outcome IN ('hit', 'miss') AND NOT informational"""),
                {"rv": rule, "l": league})).one()
            if row[0]:
                m[key] = {"n": row[0], "hit_pct": 100 * row[1] / row[0], "shown_pct": float(row[2]) / 100}
    for key, source in (("shadow_prematch", "top_pick"), ("shadow_live", "live_ht")):
        rows = dedupe_decisions(await _load(source, None, None, None, "main", scope="shadow"))
        pool = summarize(rows)
        mine = summarize([r for r in rows if r.get("league_name") == league])
        below = False
        if mine["resolved"] and mine["avg_prob_pct"] is not None:
            below = wilson_ci(mine["hits"], mine["resolved"])[1] * 100 < mine["avg_prob_pct"]
        m[key] = {"pool": pool, "league": {**mine, "below": below}}
    return m


def league_promotion_report_cmd(
    league: str = typer.Argument(..., help="Lig (kanonik ad, kısa kod ya da bülten adı)"),
    save: bool = typer.Option(False, "--kaydet", help="Raporu audit_log'a yaz (terfi kararından önce)"),
) -> None:
    """Gölge lig ekrana alınabilir mi? Ölçütleri ölçer; terfi kararı sahibindir (yazmaz, --kaydet hariç)."""
    from app.analysis.league_filter import (
        PROMOTED_LEAGUES, canonical_league_name, is_display_league, is_shadow_league,
    )

    name = canonical_league_name(league)

    async def _run() -> list[dict]:
        checks = evaluate_promotion(await _collect(name))
        if save:
            from app.db.connection import get_session
            from app.db.models import AuditLog

            async with get_session() as session:
                session.add(AuditLog(operation="league_promotion_report", actor="cli",
                                     details={"league": name, "checks": checks}))
        return checks

    checks = asyncio.run(_run())
    state = ("ekranda" + (f" (terfi {PROMOTED_LEAGUES[name]})" if name in PROMOTED_LEAGUES else "")
             if is_display_league(name) else "gölgede" if is_shadow_league(name) else "takip edilmiyor")
    t = Table(title=f"Terfi raporu — {name} ({state})")
    t.add_column("Ölçüt")
    t.add_column("Durum")
    t.add_column("Ayrıntı")
    for c in checks:
        mark = "[green]✓[/green]" if c["ok"] else "[yellow]?[/yellow]" if c["ok"] is None else "[red]✗[/red]"
        t.add_row(c["name"], mark, c["detail"])
    console.print(t)
    passed = all(c["ok"] for c in checks)
    console.print("[green]Tüm ölçütler sağlandı — terfi sahibin kararı (PROMOTED_LEAGUES + CLAUDE.md).[/green]"
                  if passed else "[yellow]Terfi için eksik ölçüt var.[/yellow]")
    if save:
        console.print("[dim]Rapor audit_log'a yazıldı.[/dim]")
