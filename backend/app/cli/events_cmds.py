"""Maç olayları (gol dakikaları + kırmızı kartlar) — anlık maç modeli kalibrasyonu için (Sprint 93)."""

import asyncio
import time
from datetime import date, datetime, timezone
from typing import Optional

import typer

from app.cli._helpers import _setup_logging, console
from app.cli._long_jobs import backoff_delay, paced_delay, parse_until, past_deadline
from app.analysis.pattern_b import RESULT_KNOWN_DELAY


def backfill_goal_events_cmd(
    since: str = typer.Option("2024-07-01", "--since", help="Bu tarihten sonraki biten maçlar (YYYY-MM-DD)"),
    limit: Optional[int] = typer.Option(None, "--limit", help="En fazla bu kadar maç (deneme için)"),
    delay: float = typer.Option(5.0, "--delay", help="İstekler arası bekleme (sn) — maç saatlerinde en az 12"),
    until: Optional[str] = typer.Option(None, "--until", help="Bu saatte (HH:MM, İstanbul) kendiliğinden biter"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Biten ana + gölge lig maçlarının gol dakikalarını çeker (en yeniden geriye).

    Kesilirse tekrar çalıştırın: sadece henüz çekilmemiş maçlar işlenir. Kaynak hatasında durmaz, artan aralıklarla
    bekler; maç saatlerinde yavaşlar (Sprint 94 D5).
    """
    _setup_logging("DEBUG" if verbose else "WARNING")
    start = datetime.combine(date.fromisoformat(since), datetime.min.time(), timezone.utc)
    asyncio.run(_backfill(start, limit, delay, parse_until(until)))


async def _backfill(start: datetime, limit: int | None, delay: float, deadline: datetime | None = None) -> None:
    from sqlalchemy import select, update

    from app.analysis.league_filter import is_tracked_league
    from app.db.connection import get_session
    from app.db.models import Match
    from app.scraper.goal_events import events_match_score, fetch_goal_events

    cutoff = datetime.now(timezone.utc) - RESULT_KNOWN_DELAY
    async with get_session() as session:
        rows = (await session.execute(
            select(Match.match_id, Match.league_name, Match.actual_ft_home, Match.actual_ft_away)
            .where(Match.deleted_at.is_(None), Match.actual_ft_home.isnot(None),
                   Match.kickoff_time >= start, Match.kickoff_time <= cutoff,
                   Match.goal_events_fetched_at.is_(None))
            .order_by(Match.kickoff_time.desc())
        )).all()
    targets = [r for r in rows if is_tracked_league(r.league_name)]
    if limit:
        targets = targets[:limit]
    total = len(targets)
    est_h = total * (delay + 4) / 3600
    console.print(f"[cyan]{total} maçın gol dakikaları çekilecek (tahmini ~{est_h:.1f} saat). "
                  f"Kesilirse tekrar çalıştırın, kaldığı yerden devam eder.[/cyan]")
    stats = {"ok": 0, "mismatch": 0, "no_table": 0, "error": 0}
    failures_in_row = 0
    started = time.monotonic()
    for i, r in enumerate(targets, 1):
        if past_deadline(deadline):
            console.print(f"[cyan]Süre doldu ({deadline:%H:%M}) — kaldığı yerden sonra devam edecek.[/cyan]")
            break
        try:
            events = await fetch_goal_events(r.match_id)
        except Exception as exc:  # ağ / kaynak hatası: durmaz, artan aralıklarla bekler
            stats["error"] += 1
            failures_in_row += 1
            wait = backoff_delay(failures_in_row)
            console.print(f"[yellow]Hata [{r.match_id}]: {exc} — {wait / 60:.0f} dk beklenip devam edilecek[/yellow]")
            await asyncio.sleep(wait)
            continue
        failures_in_row = 0
        ok = events_match_score(events, (r.actual_ft_home, r.actual_ft_away))
        stats["ok" if ok else ("no_table" if events is None else "mismatch")] += 1
        async with get_session() as session:
            await session.execute(update(Match).where(Match.match_id == r.match_id).values(
                goal_events=events, goal_events_ok=ok,
                goal_events_fetched_at=datetime.now(timezone.utc)))
        if i % 25 == 0 or i == total:
            rate = i / max(1.0, time.monotonic() - started) * 3600
            console.print(f"  ({i}/{total}) uyuşan {stats['ok']} · uyuşmayan {stats['mismatch']} · "
                          f"tablosuz {stats['no_table']} · hata {stats['error']} · ~{rate:.0f} maç/saat")
        await asyncio.sleep(paced_delay(delay))
    console.print(f"[green]Bitti:[/green] uyuşan {stats['ok']} · uyuşmayan {stats['mismatch']} · "
                  f"tablosuz {stats['no_table']} · hata {stats['error']}")
