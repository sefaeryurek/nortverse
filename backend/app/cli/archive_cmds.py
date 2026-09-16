"""Arşiv oluşturma, onarım ve normalize komutları."""

import asyncio
from datetime import datetime
from typing import Optional

import typer
from rich.panel import Panel
from rich.table import Table

from app.analysis import analyze_match, check_match_filters
from app.cli._helpers import _setup_logging, console
from app.scraper import fetch_leagues, fetch_match_detail


def build_archive_cmd(
    league: str = typer.Argument(..., help="Nowgoal lig ID'si (örn: 36 = ENG PR)"),
    season: Optional[str] = typer.Argument(None, help="Sezon (örn: 2024-2025). Boşsa güncel sezon."),
    concurrency: int = typer.Option(5, "--concurrency", "-c", help="Aynı anda kaç maç çekilsin (default 5)."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Geçmiş sezon maçlarını çekip DB'ye arşivle (paralel)."""
    _setup_logging("DEBUG" if verbose else "INFO")

    from app.pipeline.runner import _upsert
    from app.scraper.browser import browser_context
    from app.scraper.league import fetch_league_match_ids

    league_id = int(league)
    seasons = [season] if season else [None]

    async def _run() -> None:
        stats = {"analyzed": 0, "skipped": 0, "errors": 0, "done": 0}
        total_ids: list[tuple[str, str | None]] = []

        async with browser_context() as ctx:
            for s in seasons:
                label = s or "güncel sezon"
                console.print(f"[cyan]Lig {league_id} / {label} maç ID'leri çekiliyor...[/cyan]")
                ids = await fetch_league_match_ids(league_id=league_id, season=s, ctx=ctx)
                console.print(f"  {len(ids)} mac bulundu")
                for mid in ids:
                    total_ids.append((mid, s))

            if not total_ids:
                console.print("[yellow]Hiç maç ID'si bulunamadı. Debug HTML'ini inceleyin.[/yellow]")
                return

            total = len(total_ids)
            console.print(f"\n[bold]{total} maç arşivlenecek (concurrency={concurrency})...[/bold]\n")

            sem = asyncio.Semaphore(concurrency)

            async def _process(mid: str, s: str | None) -> None:
                async with sem:
                    try:
                        raw = await fetch_match_detail(mid, ctx=ctx)
                        check = check_match_filters(raw)
                        if not check.passed:
                            stats["skipped"] += 1
                            return

                        result = analyze_match(raw, season=s)
                        await _upsert(result, raw)
                        stats["analyzed"] += 1
                    except Exception as e:
                        stats["errors"] += 1
                    finally:
                        stats["done"] += 1
                        done = stats["done"]
                        if done % 10 == 0 or done == total:
                            console.print(
                                f"  [{done}/{total}] "
                                f"[green]{stats['analyzed']} kayıt[/green] · "
                                f"[yellow]{stats['skipped']} atlandı[/yellow] · "
                                f"[red]{stats['errors']} hata[/red]"
                            )

            tasks = [_process(mid, s) for mid, s in total_ids]
            await asyncio.gather(*tasks)

        console.print(
            f"\n[bold green]Arşiv tamamlandı:[/bold green] "
            f"[green]{stats['analyzed']} kaydedildi[/green] · "
            f"[yellow]{stats['skipped']} atlandı[/yellow] · "
            f"[red]{stats['errors']} hata[/red]"
        )

    asyncio.run(_run())


def build_multi_archive_cmd(
    league_ids: list[str] = typer.Argument(..., help="Lig ID listesi (boşlukla ayırın: 36 60 65)"),
    seasons: Optional[str] = typer.Option(None, "--seasons", "-s", help="Her lig için kaç sezon geriye git (varsayılan: 5)"),
    concurrency: int = typer.Option(5, "--concurrency", "-c", help="Aynı anda kaç maç çekilsin (default 5)."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Birden fazla lig için arşiv oluşturur — her ligi son N sezonda çeker (paralel)."""
    _setup_logging("DEBUG" if verbose else "INFO")
    n_seasons = int(seasons) if seasons and str(seasons).isdigit() else 5
    from app.pipeline.runner import _upsert
    from app.scraper.browser import browser_context
    from app.scraper.league import fetch_league_match_ids
    from app.scraper.match_detail import fetch_match_detail as _fetch_detail

    def _recent_seasons(n: int) -> list[str]:
        now = datetime.now()
        start_year = now.year if now.month >= 8 else now.year - 1
        return [f"{start_year - i}-{start_year - i + 1}" for i in range(n)]

    async def _run() -> None:
        total_stats = {"analyzed": 0, "skipped": 0, "errors": 0, "leagues": 0}

        async with browser_context() as ctx:
            sem = asyncio.Semaphore(concurrency)

            for lid_str in league_ids:
                if lid_str.startswith("-"):
                    continue
                try:
                    lid = int(lid_str)
                except ValueError:
                    console.print(f"[red]Geçersiz lig ID: {lid_str}[/red]")
                    continue

                from app.scraper.league import fetch_league_seasons
                season_list = await fetch_league_seasons(lid, ctx=ctx)
                if not season_list:
                    season_list = _recent_seasons(n_seasons)
                    console.print(
                        f"[dim]Lig {lid}: sezon API basarisiz, son {n_seasons} sezon: "
                        f"{', '.join(season_list)}[/dim]"
                    )

                to_process = season_list[:n_seasons]
                console.print(
                    f"\n[bold cyan]Lig {lid}[/bold cyan]: "
                    f"{len(to_process)} sezon — {', '.join(to_process)}"
                )
                total_stats["leagues"] += 1

                for season in to_process:
                    match_ids = await fetch_league_match_ids(lid, season, ctx=ctx)
                    if not match_ids:
                        console.print(f"  [yellow]{season}: maç ID bulunamadı — atlandı[/yellow]")
                        continue

                    total = len(match_ids)
                    console.print(
                        f"  [cyan]{season}[/cyan]: {total} maç işlenecek (concurrency={concurrency})"
                    )
                    stats = {"analyzed": 0, "skipped": 0, "errors": 0, "done": 0}

                    async def _process(mid: str, _season: str = season) -> None:
                        async with sem:
                            try:
                                raw = await _fetch_detail(mid, ctx=ctx)
                                check = check_match_filters(raw)
                                if not check.passed:
                                    stats["skipped"] += 1
                                    return
                                result = analyze_match(raw, season=_season)
                                await _upsert(result, raw)
                                stats["analyzed"] += 1
                            except Exception as e:
                                stats["errors"] += 1
                                if verbose:
                                    console.print(f"  [red]Hata [{mid}]: {e}[/red]")
                            finally:
                                stats["done"] += 1
                                done = stats["done"]
                                if done % 10 == 0 or done == total:
                                    console.print(
                                        f"  ({done}/{total}) "
                                        f"[green]{stats['analyzed']} kayıt[/green] · "
                                        f"[yellow]{stats['skipped']} atlandı[/yellow]"
                                    )

                    tasks = [_process(mid) for mid in match_ids]
                    await asyncio.gather(*tasks)

                    console.print(
                        f"  [bold]{season} bitti:[/bold] "
                        f"[green]{stats['analyzed']} kayıt[/green] · "
                        f"[yellow]{stats['skipped']} atlandı[/yellow] · "
                        f"[red]{stats['errors']} hata[/red]"
                    )
                    for k in ("analyzed", "skipped", "errors"):
                        total_stats[k] += stats[k]

        console.print(
            f"\n[bold green]Tüm arşivler tamamlandı:[/bold green] "
            f"{total_stats['leagues']} lig · "
            f"[green]{total_stats['analyzed']} kayıt[/green] · "
            f"[yellow]{total_stats['skipped']} atlandı[/yellow] · "
            f"[red]{total_stats['errors']} hata[/red]"
        )

    asyncio.run(_run())


def list_leagues_cmd(
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Bugünkü fixture sayfasındaki tüm ligleri listeler (ID + ad)."""
    _setup_logging("DEBUG" if verbose else "WARNING")

    async def _run() -> None:
        console.print("[cyan]Fixture sayfasından lig listesi çekiliyor...[/cyan]")
        leagues = await fetch_leagues()
        if not leagues:
            console.print("[red]Lig bulunamadı.[/red]")
            return

        t = Table(title=f"Ligler ({len(leagues)} adet)", show_header=True)
        t.add_column("ID", style="cyan", width=8)
        t.add_column("Lig Adı", style="white")
        for lid, name in sorted(leagues.items(), key=lambda x: x[1]):
            t.add_row(lid, name)
        console.print(t)
        console.print("[dim]İpucu: build-archive <ID> <sezon> veya build-multi-archive <ID1> <ID2> ...[/dim]")

    asyncio.run(_run())


def repair_archive_cmd(
    apply: bool = typer.Option(False, "--apply", help="Gerçekten soft-delete yap (default dry-run)."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Sprint 20 — Sorunlu arşiv kayıtlarını tespit edip onar (soft delete)."""
    _setup_logging("DEBUG" if verbose else "INFO")

    from datetime import timezone
    from sqlalchemy import select, update as sa_update
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from app.analysis.league_filter import is_supported_league
    from app.db.connection import get_session
    from app.db.models import AuditLog, Match

    async def _run() -> None:
        async with get_session() as session:
            rows = (await session.execute(
                select(
                    Match.match_id, Match.home_team, Match.away_team,
                    Match.league_code, Match.league_name,
                    Match.actual_ft_home, Match.actual_ft_away,
                    Match.actual_ht_home, Match.actual_ht_away,
                    Match.actual_h2_home, Match.actual_h2_away,
                ).where(Match.deleted_at.is_(None))
            )).all()

        issues: list[tuple[str, str, str]] = []

        for r in rows:
            mid = r.match_id
            label = f"{r.home_team} vs {r.away_team}"

            if not r.home_team or r.home_team.strip() in ("", "?"):
                issues.append((mid, "empty_team", f"home_team='{r.home_team}'"))
                continue
            if not r.away_team or r.away_team.strip() in ("", "?"):
                issues.append((mid, "empty_team", f"away_team='{r.away_team}'"))
                continue

            if not is_supported_league(r.league_name, r.league_code):
                issues.append((mid, "non_league", f"league={r.league_code or r.league_name}"))
                continue

            score_fields = [
                ("actual_ft_home", r.actual_ft_home),
                ("actual_ft_away", r.actual_ft_away),
                ("actual_ht_home", r.actual_ht_home),
                ("actual_ht_away", r.actual_ht_away),
                ("actual_h2_home", r.actual_h2_home),
                ("actual_h2_away", r.actual_h2_away),
            ]
            bad_score = False
            for fname, val in score_fields:
                if val is not None and (val < 0 or val > 15):
                    issues.append((mid, "bad_score", f"{fname}={val} ({label})"))
                    bad_score = True
                    break
            if bad_score:
                continue

            if (r.actual_ht_home is not None and r.actual_ft_home is not None
                    and r.actual_ht_home > r.actual_ft_home):
                issues.append((mid, "inconsistent_half",
                               f"ht_home={r.actual_ht_home} > ft_home={r.actual_ft_home} ({label})"))
                continue
            if (r.actual_ht_away is not None and r.actual_ft_away is not None
                    and r.actual_ht_away > r.actual_ft_away):
                issues.append((mid, "inconsistent_half",
                               f"ht_away={r.actual_ht_away} > ft_away={r.actual_ft_away} ({label})"))
                continue

        if not issues:
            console.print(f"[green]✓ Temiz! {len(rows)} aktif kayıtta sorun bulunamadı.[/green]")
            return

        from collections import Counter
        cats = Counter(reason for _, reason, _ in issues)

        console.print(Panel.fit(
            f"[bold yellow]{len(issues)} sorunlu kayıt tespit edildi[/bold yellow]\n\n"
            + "\n".join(f"  {reason}: {count}" for reason, count in cats.most_common()),
            title="[cyan]Repair Archive Raporu[/cyan]", border_style="yellow",
        ))

        t = Table(title="Sorunlu Kayıtlar (ilk 20)")
        t.add_column("Match ID", style="cyan", width=10)
        t.add_column("Sebep", style="magenta", width=20)
        t.add_column("Detay", style="yellow")
        for mid, reason, detail in issues[:20]:
            t.add_row(mid, reason, detail)
        console.print(t)
        if len(issues) > 20:
            console.print(f"[dim]... ve {len(issues) - 20} kayıt daha[/dim]")

        if not apply:
            console.print("\n[yellow]Dry-run modu: hiçbir şey değişmedi.[/yellow]")
            console.print("[dim]Gerçekten silmek için: repair-archive --apply[/dim]")
            return

        ts = datetime.now(timezone.utc)
        match_ids = [mid for mid, _, _ in issues]

        async with get_session() as session:
            await session.execute(
                sa_update(Match)
                .where(Match.match_id.in_(match_ids))
                .values(deleted_at=ts, deleted_reason="repair_archive")
            )
            await session.execute(
                pg_insert(AuditLog).values(
                    operation="repair_archive",
                    actor="cli:repair-archive",
                    details={
                        "total_repaired": len(match_ids),
                        "categories": dict(cats),
                        "match_ids_sample": match_ids[:50],
                        "issues_sample": [
                            {"match_id": mid, "reason": reason, "detail": detail}
                            for mid, reason, detail in issues[:50]
                        ],
                    },
                )
            )

        console.print(
            f"\n[green]✓ {len(issues)} kayıt soft-delete edildi.[/green] "
            f"[dim](audit_log'a kayıt düştü; geri almak için: restore-deleted <match_id>)[/dim]"
        )

    asyncio.run(_run())


def normalize_leagues_cmd(
    apply: bool = typer.Option(False, "--apply", help="Gerçekten güncelle (default dry-run)."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Sprint 20 — Lig adlarını kanonik forma normalize et."""
    _setup_logging("DEBUG" if verbose else "INFO")

    from collections import Counter
    from sqlalchemy import select, update as sa_update
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from app.analysis.league_filter import canonical_league_name
    from app.db.connection import get_session
    from app.db.models import AuditLog, Match

    async def _run() -> None:
        async with get_session() as session:
            rows = (await session.execute(
                select(Match.match_id, Match.league_code, Match.league_name)
                .where(Match.deleted_at.is_(None))
            )).all()

        changes: list[tuple[str, str, str, str, str]] = []

        for r in rows:
            mid = r.match_id
            old_code = r.league_code or ""
            old_name = r.league_name or ""

            new_code = canonical_league_name(old_code)
            new_name = canonical_league_name(old_name)

            if new_code != old_code or new_name != old_name:
                changes.append((mid, old_code, new_code, old_name, new_name))

        if not changes:
            console.print(f"[green]✓ {len(rows)} kayıt zaten kanonik formda.[/green]")
            return

        code_changes = Counter(
            f"{old_c} → {new_c}" for _, old_c, new_c, _, _ in changes if old_c != new_c
        )
        name_changes = Counter(
            f"{old_n} → {new_n}" for _, _, _, old_n, new_n in changes if old_n != new_n
        )

        console.print(Panel.fit(
            f"[bold]{len(changes)} kayıtta normalize gerekiyor[/bold]",
            title="[cyan]Lig Normalizasyonu[/cyan]", border_style="cyan",
        ))

        if code_changes:
            t = Table(title="League Code Dönüşümleri")
            t.add_column("Eski → Yeni", style="yellow")
            t.add_column("Sayı", justify="right", style="cyan")
            for transform, count in code_changes.most_common(20):
                t.add_row(transform, str(count))
            console.print(t)

        if name_changes:
            t = Table(title="League Name Dönüşümleri")
            t.add_column("Eski → Yeni", style="yellow")
            t.add_column("Sayı", justify="right", style="cyan")
            for transform, count in name_changes.most_common(20):
                t.add_row(transform, str(count))
            console.print(t)

        if not apply:
            console.print("\n[yellow]Dry-run modu: hiçbir şey değişmedi.[/yellow]")
            console.print("[dim]Uygulamak için: normalize-leagues --apply[/dim]")
            return

        updated = 0
        async with get_session() as session:
            for mid, _, new_code, _, new_name in changes:
                await session.execute(
                    sa_update(Match)
                    .where(Match.match_id == mid)
                    .values(league_code=new_code, league_name=new_name)
                )
                updated += 1

            await session.execute(
                pg_insert(AuditLog).values(
                    operation="normalize_leagues",
                    actor="cli:normalize-leagues",
                    details={
                        "total_normalized": updated,
                        "code_transforms": dict(code_changes),
                        "name_transforms": dict(name_changes),
                    },
                )
            )

        console.print(
            f"\n[green]✓ {updated} kayıt normalize edildi.[/green] "
            f"[dim](audit_log'a kayıt düştü)[/dim]"
        )

    asyncio.run(_run())
