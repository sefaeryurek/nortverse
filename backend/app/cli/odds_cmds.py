"""Oran geçmişi çekimi — İY değer kuralının geçmiş testi için (Sprint 93)."""

import asyncio
import time
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import typer

from app.cli._helpers import _setup_logging, console


def backfill_odds_cmd(
    since: str = typer.Option("2026-02-01", "--since", help="Bu tarihten sonraki biten maçlar (kaynakta daha eskisi yok)"),
    scope: str = typer.Option("ht", "--scope", help="ht = ilk yarı oranları, ft = maç sonu"),
    limit: Optional[int] = typer.Option(None, "--limit", help="En fazla bu kadar maç (deneme için)"),
    delay: float = typer.Option(3.0, "--delay", help="İstekler arası bekleme (sn) — kaynağı yormamak için"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Biten ana + gölge lig maçlarının oran geçmişini `match_odds`'a yazar (en yeniden geriye).

    Kesilirse tekrar çalıştırın: sadece henüz çekilmemiş maçlar işlenir.
    """
    if scope not in ("ht", "ft"):
        raise typer.BadParameter("--scope ht veya ft olmalı")
    _setup_logging("DEBUG" if verbose else "WARNING")
    start = datetime.combine(date.fromisoformat(since), datetime.min.time(), timezone.utc)
    asyncio.run(_backfill(start, scope, limit, delay))


async def _backfill(start: datetime, scope: str, limit: int | None, delay: float) -> None:
    from sqlalchemy import and_, select

    from app.analysis.league_filter import is_tracked_league
    from app.db.connection import get_session
    from app.db.models import Match, MatchOdds
    from app.scraper.odds import load_or_fetch

    cutoff = datetime.now(timezone.utc) - timedelta(hours=3)
    async with get_session() as session:
        rows = (await session.execute(
            select(Match.match_id, Match.league_name)
            .outerjoin(MatchOdds, and_(MatchOdds.match_id == Match.match_id, MatchOdds.scope == scope))
            .where(Match.deleted_at.is_(None), Match.actual_ft_home.isnot(None),
                   Match.kickoff_time >= start, Match.kickoff_time <= cutoff, MatchOdds.match_id.is_(None))
            .order_by(Match.kickoff_time.desc())
        )).all()
    targets = [r for r in rows if is_tracked_league(r.league_name)]
    if limit:
        targets = targets[:limit]
    total = len(targets)
    console.print(f"[cyan]{total} maçın {scope.upper()} oranları çekilecek (tahmini ~{total * (delay + 1.5) / 3600:.1f} "
                  f"saat). Kesilirse tekrar çalıştırın, kaldığı yerden devam eder.[/cyan]")
    stats = {"ok": 0, "empty": 0, "error": 0}
    failures_in_row = 0
    started = time.monotonic()
    for i, r in enumerate(targets, 1):
        try:
            async with get_session() as session:
                history = await load_or_fetch(session, r.match_id, half=scope == "ht", max_age_s=0)
        except Exception as exc:  # ağ / kaynak hatası
            stats["error"] += 1
            failures_in_row += 1
            console.print(f"[yellow]Hata [{r.match_id}]: {exc}[/yellow]")
            if failures_in_row >= 5:
                console.print("[red]Üst üste 5 hata — kaynak erişilemiyor olabilir, durduruldu.[/red]")
                break
            await asyncio.sleep(delay * 3)
            continue
        failures_in_row = 0
        stats["ok" if history and history.get("op") else "empty"] += 1
        if i % 50 == 0 or i == total:
            rate = i / max(1.0, time.monotonic() - started) * 3600
            console.print(f"  ({i}/{total}) oranlı {stats['ok']} · boş {stats['empty']} · hata {stats['error']} "
                          f"· ~{rate:.0f} maç/saat")
        await asyncio.sleep(delay)
    console.print(f"[green]Bitti:[/green] oranlı {stats['ok']} · boş {stats['empty']} · hata {stats['error']}")


def backtest_ht_value_cmd(
    since: str = typer.Option("2026-02-01", "--since", help="Başlangıç (YYYY-MM-DD)"),
    split: str = typer.Option("2026-07-01", "--split", help="Ayar / test dönemi ayrımı (eşikler ilk dönemde seçilir)"),
) -> None:
    """İY değer kuralının geçmiş kapanış oranlarıyla testi (sızıntısız haftalık takım modeli). DB'ye yazmaz."""
    _setup_logging("WARNING")
    start = datetime.combine(date.fromisoformat(since), datetime.min.time(), timezone.utc)
    cut = datetime.combine(date.fromisoformat(split), datetime.min.time(), timezone.utc)
    asyncio.run(_backtest_ht_value(start, cut))


async def _backtest_ht_value(start: datetime, cut: datetime) -> None:
    from sqlalchemy import select

    from app.analysis import ht_value as hv
    from app.analysis import live_poisson as lp
    from app.analysis.league_filter import is_main_league
    from app.db.connection import get_session
    from app.db.models import Match, MatchOdds
    from app.scraper.odds import latest_prematch

    async with get_session() as session:
        rows = (await session.execute(
            select(Match.match_id, Match.kickoff_time, Match.league_name, Match.league_code, Match.home_team,
                   Match.away_team, Match.actual_ht_home, Match.actual_ht_away, MatchOdds.history)
            .join(MatchOdds, (MatchOdds.match_id == Match.match_id) & (MatchOdds.scope == "ht"))
            .where(Match.deleted_at.is_(None), Match.actual_ht_home.isnot(None), Match.kickoff_time >= start)
            .order_by(Match.kickoff_time)
        )).all()
    rows = [r for r in rows if is_main_league(r.league_name, r.league_code)]
    training = await lp.load_training()
    kickoffs = [t.kickoff for t in training]
    refit = timedelta(days=lp.RULE_PARAMS["refit_days"])
    model = None
    records: list[dict] = []
    for r in rows:
        if model is None or r.kickoff_time - model.as_of >= refit:
            model = lp.fit_model(lp.train_window(training, kickoffs, r.kickoff_time), r.kickoff_time)
        lm = model.leagues.get(r.league_name or "")
        odds = latest_prematch(r.history, before=r.kickoff_time)
        if lm is None or not odds:
            continue
        lam_h, lam_a = lm.expected_goals(r.home_team, r.away_team)
        lam_h, lam_a = lam_h * lm.ht_share[0], lam_a * lm.ht_share[1]
        ht = (r.actual_ht_home, r.actual_ht_away)
        for c in hv.candidates(lam_h, lam_a, odds):
            records.append({**c, "match_id": r.match_id, "late": r.kickoff_time >= cut,
                            "profit": hv.settle(c, ht)})
    n_matches = len({x["match_id"] for x in records})
    console.print(f"[cyan]{len(rows)} oranlı ana lig maçı, {n_matches} maçta model + kapanış oranı[/cyan]")

    def line(label: str, xs: list[dict]) -> str:
        if not xs:
            return f"  {label:34s} n=0"
        n = len(xs)
        roi = 100 * sum(x["profit"] for x in xs) / n
        hit = 100 * sum(x["profit"] > 0 for x in xs) / n
        prob = 100 * sum(x["prob"] for x in xs) / n
        odds = sum(x["odds"] for x in xs) / n
        return f"  {label:34s} n={n:5d}  kazanma=%{hit:5.1f}  model=%{prob:5.1f}  ort.oran={odds:5.2f}  getiri=%{roi:+6.1f}"

    console.print("\n[bold]Her seçime körlemesine 1 birim (piyasa payı tabanı)[/bold]")
    for key in sorted({(x["market"], x["selection"]) for x in records}):
        console.print(line(f"{key[0]} {key[1]}", [x for x in records if (x["market"], x["selection"]) == key]))

    console.print("\n[bold]Değer eşikleri (pazar başına en yüksek EV) — ayar dönemi | test dönemi[/bold]")
    for min_ev in (0.0, 0.03, 0.05, 0.10, 0.15, 0.20):
        for min_prob in (0.0, 0.30, 0.45):
            for max_odds in (6.0, 3.5):
                params = {**hv.RULE_PARAMS, "min_ev": min_ev, "min_prob": min_prob, "max_odds": max_odds}
                picked = {"early": [], "late": []}
                by_match: dict[str, list[dict]] = {}
                for x in records:
                    by_match.setdefault(x["match_id"], []).append(x)
                for xs in by_match.values():
                    for p in hv.decide(xs, params):
                        picked["late" if p["late"] else "early"].append(p)
                label = f"EV≥{min_ev:.2f} p≥{min_prob:.2f} oran≤{max_odds}"
                console.print(line(label + " ayar", picked["early"]))
                console.print(line(label + " test", picked["late"]))
