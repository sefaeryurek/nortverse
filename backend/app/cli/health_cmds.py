"""Sağlık raporu (Sprint 94 D4) — `scripts/health-check.ps1` veritabanına bakan kontrolleri buradan alır.

Dosya/sistem kontrolleri (Docker, kalp atışları, disk, yedek dosyaları) PowerShell tarafında; burada sadece
DB'den okunabilenler. Çıktı JSON: {"checks": [{"name", "ok", "detail"}], "info": {...}}.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

import typer

from app.cli._helpers import console

LIVE_KICKOFF_FROM = timedelta(minutes=70)  # başlaması 50–70 dk önce olan maç devre arasını geçmiş olmalı
LIVE_KICKOFF_TO = timedelta(minutes=50)
LIVE_RECENT = timedelta(minutes=25)
ODDS_STALE = timedelta(hours=48)  # oranlar sadece İY sayfası / backfill ile yazılıyor → kullanım olmayan gün normal
NOT_PLAYED = {"postponed", "abandoned", "unplayed"}


def evaluate_live(candidates: list[str], observed: set[str], statuses: dict[str, str]) -> dict:
    """Devre arasını geçmiş izlenen maçlar varsa en az birinde son 25 dk'da İY gözlemi olmalı."""
    playing = [mid for mid in candidates if statuses.get(mid) not in NOT_PLAYED]
    if not playing:
        return {"name": "canli_dondurma", "ok": True, "detail": "kontrol edilecek maç yok"}
    seen = [mid for mid in playing if mid in observed]
    ok = bool(seen)
    detail = (f"{len(seen)}/{len(playing)} maçta İY kaydı var" if ok
              else f"{len(playing)} maç devre arasını geçti ama son 25 dk'da hiç İY kaydı yok: {', '.join(playing[:5])}")
    return {"name": "canli_dondurma", "ok": ok, "detail": detail}


async def _collect(now: datetime) -> dict:
    from sqlalchemy import func, select

    from app.analysis.league_filter import is_main_league
    from app.analysis.match_status import fixture_statuses
    from app.db.connection import get_session
    from app.db.models import Match, MatchHtObservation, MatchOdds

    async with get_session() as session:
        rows = (await session.execute(
            select(Match.match_id, Match.league_name, Match.league_code).where(
                Match.deleted_at.is_(None),
                Match.kickoff_time.between(now - LIVE_KICKOFF_FROM, now - LIVE_KICKOFF_TO))
        )).all()
        candidates = [r.match_id for r in rows if is_main_league(r.league_name, r.league_code)]
        observed: set[str] = set()
        if candidates:
            observed = set((await session.execute(
                select(MatchHtObservation.match_id).where(
                    MatchHtObservation.match_id.in_(candidates),
                    MatchHtObservation.ingested_at >= now - LIVE_RECENT)
            )).scalars())
        statuses = await fixture_statuses(session, candidates, now)
        odds_at = (await session.execute(select(func.max(MatchOdds.fetched_at)))).scalar_one_or_none()

    checks = [evaluate_live(candidates, observed, statuses)]
    odds_age = (now - odds_at) if odds_at else None
    checks.append({
        "name": "oran_kaydi",
        "ok": odds_age is not None and odds_age < ODDS_STALE,
        "detail": f"son oran kaydı {odds_age.total_seconds() / 3600:.1f} saat önce" if odds_age else "hiç oran kaydı yok",
    })
    return {"checks": checks, "info": {"live_candidates": len(candidates), "odds_age_h":
                                       round(odds_age.total_seconds() / 3600, 1) if odds_age else None}}


def health_report_cmd(
    as_json: bool = typer.Option(False, "--json", help="Makine okunur çıktı (health-check.ps1 kullanır)"),
) -> None:
    """Veritabanına bakan sağlık kontrolleri: canlı İY dondurma, oran kaydı yaşı (Sprint 94 D4)."""
    try:
        report = asyncio.run(_collect(datetime.now(timezone.utc)))
    except Exception as exc:  # DB'ye ulaşılamıyorsa bu da bir bulgu
        report = {"checks": [{"name": "veritabani", "ok": False, "detail": f"{type(exc).__name__}: {exc}"[:300]}],
                  "info": {}}
    if as_json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        for c in report["checks"]:
            console.print(f"{'[green]✓' if c['ok'] else '[red]✗'}[/] {c['name']}: {c['detail']}")
    raise typer.Exit(0 if all(c["ok"] for c in report["checks"]) else 1)
