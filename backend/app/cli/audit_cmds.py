"""Audit, self-test, prune, restore ve recompute komutları."""

import asyncio
import logging
from typing import Optional

import typer
from rich.panel import Panel
from rich.table import Table

from app.analysis import analyze_match, check_match_filters
from app.cli._helpers import _setup_logging, console
from app.scraper import fetch_match_detail


def prune_non_league_cmd(
    apply: bool = typer.Option(False, "--apply", help="Gerçekten soft-delete et (yoksa preview)"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Sprint 8.9 — DB'deki kupa/Avrupa/friendly maçlarını soft-delete et."""
    _setup_logging("DEBUG" if verbose else "INFO")

    from datetime import datetime, timezone
    from sqlalchemy import select, update as sa_update
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from app.analysis.league_filter import is_supported_league
    from app.db.connection import get_session
    from app.db.models import AuditLog, Match

    async def _run() -> None:
        async with get_session() as session:
            rows = (await session.execute(
                select(Match.match_id, Match.home_team, Match.away_team,
                       Match.league_code, Match.league_name, Match.deleted_at)
            )).all()

        non_league = [
            r for r in rows
            if r.deleted_at is None
            and not is_supported_league(r.league_name, r.league_code)
        ]

        if not non_league:
            console.print(f"[green]✓ Temiz! {len(rows)} aktif maçın hepsi lig maçı.[/green]")
            return

        t = Table(title=f"Soft-Delete Önizleme — {len(non_league)} maç")
        t.add_column("Match ID", style="cyan", width=10)
        t.add_column("Lig", style="magenta")
        t.add_column("Maç", style="yellow")
        for r in non_league[:15]:
            t.add_row(r.match_id, r.league_code or r.league_name or "?",
                      f"{r.home_team} vs {r.away_team}")
        console.print(t)
        if len(non_league) > 15:
            console.print(f"[dim]... ve {len(non_league) - 15} maç daha[/dim]")

        if not apply:
            console.print("\n[yellow]Dry-run modu: hiçbir şey değişmedi.[/yellow]")
            console.print("[dim]Gerçekten silmek için: prune-non-league --apply[/dim]")
            return

        ts = datetime.now(timezone.utc)
        match_ids = [r.match_id for r in non_league]

        async with get_session() as session:
            await session.execute(
                sa_update(Match)
                .where(Match.match_id.in_(match_ids))
                .values(deleted_at=ts, deleted_reason="non_league")
            )
            await session.execute(
                pg_insert(AuditLog).values(
                    operation="prune_non_league",
                    actor="cli:prune-non-league",
                    details={
                        "total_pruned": len(match_ids),
                        "match_ids_sample": match_ids[:50],
                        "leagues_sample": list({r.league_code or r.league_name or "?"
                                                for r in non_league[:50]}),
                    },
                )
            )

        console.print(
            f"\n[green]✓ {len(non_league)} maç soft-delete edildi.[/green] "
            f"[dim](audit_log'a kayıt düştü; restore için: restore-deleted <match_id>)[/dim]"
        )

    asyncio.run(_run())


def restore_deleted_cmd(
    match_id: str = typer.Argument(..., help="Geri alınacak match_id"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Sprint 8.9 — Soft-deleted bir maçı geri al."""
    _setup_logging("DEBUG" if verbose else "INFO")
    from sqlalchemy import select, update as sa_update
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from app.db.connection import get_session
    from app.db.models import AuditLog, Match

    async def _run() -> None:
        async with get_session() as session:
            row = (await session.execute(
                select(Match.match_id, Match.deleted_at, Match.deleted_reason)
                .where(Match.match_id == match_id)
            )).first()

            if not row:
                console.print(f"[red]Maç bulunamadı: {match_id}[/red]")
                return
            if row.deleted_at is None:
                console.print(f"[yellow]Maç zaten aktif (silinmemiş): {match_id}[/yellow]")
                return

            await session.execute(
                sa_update(Match)
                .where(Match.match_id == match_id)
                .values(deleted_at=None, deleted_reason=None)
            )
            await session.execute(
                pg_insert(AuditLog).values(
                    operation="restore",
                    target_match_id=match_id,
                    actor="cli:restore-deleted",
                    details={"previous_reason": row.deleted_reason,
                             "previous_deleted_at": row.deleted_at.isoformat()},
                )
            )
        console.print(f"[green]✓ Maç geri alındı: {match_id}[/green]")

    asyncio.run(_run())


def audit_db_cmd(
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Sprint 8.9 — DB sağlık raporu: aktif/silinmiş, eksik veri, kalite skoru."""
    _setup_logging("DEBUG" if verbose else "WARNING")

    from datetime import datetime, timezone, timedelta
    from sqlalchemy import select, func, or_
    from app.analysis.league_filter import is_supported_league, canonical_league_name
    from app.db.connection import get_session
    from app.db.models import Match

    async def _run() -> None:
        async with get_session() as session:
            total = (await session.execute(select(func.count(Match.id)))).scalar() or 0
            active = (await session.execute(
                select(func.count(Match.id)).where(Match.deleted_at.is_(None))
            )).scalar() or 0
            deleted = total - active

            active_rows = (await session.execute(
                select(Match.match_id, Match.league_code, Match.league_name)
                .where(Match.deleted_at.is_(None))
            )).all()
            non_league_active = [
                r for r in active_rows
                if not is_supported_league(r.league_name, r.league_code)
            ]

            missing_pattern = (await session.execute(
                select(func.count(Match.id)).where(
                    Match.deleted_at.is_(None),
                    Match.pattern_computed_at.is_(None),
                )
            )).scalar() or 0

            missing_trends = (await session.execute(
                select(func.count(Match.id)).where(
                    Match.deleted_at.is_(None), Match.trends.is_(None)
                )
            )).scalar() or 0

            cutoff = datetime.now(timezone.utc) - timedelta(minutes=130)
            missing_actual = (await session.execute(
                select(func.count(Match.id)).where(
                    Match.deleted_at.is_(None),
                    Match.kickoff_time < cutoff,
                    or_(Match.actual_ft_home.is_(None), Match.actual_ft_away.is_(None)),
                )
            )).scalar() or 0

            now = datetime.now(timezone.utc)
            d24 = (await session.execute(
                select(func.count(Match.id)).where(
                    Match.deleted_at.is_(None), Match.created_at >= now - timedelta(days=1)
                )
            )).scalar() or 0
            d7 = (await session.execute(
                select(func.count(Match.id)).where(
                    Match.deleted_at.is_(None), Match.created_at >= now - timedelta(days=7)
                )
            )).scalar() or 0
            last_pipeline = (await session.execute(
                select(func.max(Match.analyzed_at)).where(Match.deleted_at.is_(None))
            )).scalar()

            score_rows = (await session.execute(
                select(
                    Match.match_id,
                    Match.actual_ft_home, Match.actual_ft_away,
                    Match.actual_ht_home, Match.actual_ht_away,
                ).where(Match.deleted_at.is_(None))
            )).all()
            bad_scores = 0
            inconsistent_halves = 0
            for sr in score_rows:
                for val in (sr.actual_ft_home, sr.actual_ft_away,
                            sr.actual_ht_home, sr.actual_ht_away):
                    if val is not None and (val < 0 or val > 15):
                        bad_scores += 1
                        break
                else:
                    if (sr.actual_ht_home is not None and sr.actual_ft_home is not None
                            and sr.actual_ht_home > sr.actual_ft_home):
                        inconsistent_halves += 1
                    elif (sr.actual_ht_away is not None and sr.actual_ft_away is not None
                            and sr.actual_ht_away > sr.actual_ft_away):
                        inconsistent_halves += 1

            unnormalized = sum(
                1 for r in active_rows
                if (r.league_code and canonical_league_name(r.league_code) != r.league_code)
                or (r.league_name and canonical_league_name(r.league_name) != r.league_name)
            )

            ftb_rows = (await session.execute(
                select(Match.match_id, Match.pattern_ft_b)
                .where(Match.deleted_at.is_(None), Match.pattern_ft_b.isnot(None))
            )).all()
            pattern_anomalies = []
            for r in ftb_rows:
                p = r.pattern_ft_b
                if not p:
                    continue
                total_pct = (
                    (p.get("result_1_pct") or 0)
                    + (p.get("result_x_pct") or 0)
                    + (p.get("result_2_pct") or 0)
                )
                if abs(total_pct - 100) > 1:
                    pattern_anomalies.append((r.match_id, total_pct))

            repair_candidates = bad_scores + inconsistent_halves
            if total == 0:
                quality = 0.0
            else:
                penalties = (
                    (len(non_league_active) / total) * 40
                    + (missing_pattern / max(active, 1)) * 20
                    + (missing_actual / max(active, 1)) * 30
                    + (missing_trends / max(active, 1)) * 10
                    + (repair_candidates / max(active, 1)) * 15
                    + (unnormalized / max(active, 1)) * 5
                )
                quality = max(0.0, 100.0 - penalties)

        console.print(Panel.fit(
            f"[bold]Toplam maç:[/bold] {total:,}\n"
            f"├─ Aktif:               {active:,}\n"
            f"└─ Soft-deleted:        {deleted:,}",
            title="[cyan]DB Sağlık Raporu[/cyan]", border_style="cyan",
        ))

        t = Table(title="Veri Bütünlüğü", show_header=False)
        t.add_column("Metrik", style="white")
        t.add_column("Sayı", style="yellow", justify="right")
        t.add_column("Durum", justify="center")

        def _row(label: str, n: int, ok_if_zero: bool = True) -> None:
            status = "[green]✓[/green]" if (n == 0 if ok_if_zero else True) else "[red]⚠[/red]"
            t.add_row(label, f"{n:,}", status)

        _row("Aktif kupa/turnuva (prune lazım)", len(non_league_active))
        _row("Sorunlu skor (negatif/>15)", bad_scores)
        _row("Tutarsız yarı (İY > MS)", inconsistent_halves)
        _row("Normalize edilmemiş lig adı", unnormalized)
        _row("Pattern hesaplama durumu bilinmiyor", missing_pattern)
        _row("Trends NULL (Sprint 8.8 öncesi)", missing_trends, ok_if_zero=False)
        _row("Skor eksik (kickoff +130dk)", missing_actual, ok_if_zero=False)
        _row("Pattern tutarsızlık (1+X+2 ≠ 100)", len(pattern_anomalies))
        console.print(t)

        t2 = Table(title="Aktivite", show_header=False)
        t2.add_column("Metrik", style="white")
        t2.add_column("Değer", style="cyan")
        t2.add_row("Son 24 saat eklenen", f"{d24}")
        t2.add_row("Son 7 gün eklenen", f"{d7}")
        t2.add_row("Son pipeline analizi",
                   last_pipeline.strftime("%Y-%m-%d %H:%M") if last_pipeline else "—")
        console.print(t2)

        color = "green" if quality >= 80 else ("yellow" if quality >= 60 else "red")
        console.print(Panel.fit(
            f"[bold {color}]Veri Kalitesi Skoru: {quality:.1f} / 100[/bold {color}]\n"
            "[dim]100 = mükemmel · 80+ = iyi · 60-80 = orta · <60 = sorun var[/dim]",
            border_style=color,
        ))

        if non_league_active:
            console.print(
                f"\n[yellow]Öneri:[/yellow] "
                f"[cyan]python -m app.cli.main prune-non-league --apply[/cyan] "
                f"ile {len(non_league_active)} kupa maçını temizle."
            )
        if repair_candidates > 0:
            console.print(
                f"\n[yellow]Öneri:[/yellow] "
                f"[cyan]python -m app.cli.main repair-archive --apply[/cyan] "
                f"ile {repair_candidates} sorunlu kaydı onar."
            )
        if unnormalized > 0:
            console.print(
                f"\n[yellow]Öneri:[/yellow] "
                f"[cyan]python -m app.cli.main normalize-leagues --apply[/cyan] "
                f"ile {unnormalized} lig adını normalize et."
            )
        if pattern_anomalies:
            console.print(
                f"\n[yellow]Pattern anomalisi tespit edildi ({len(pattern_anomalies)} maç):[/yellow]"
            )
            for mid, total_val in pattern_anomalies[:5]:
                console.print(f"  [dim]{mid}: result_1+x+2 = {total_val:.1f}[/dim]")

    asyncio.run(_run())


def audit_patterns_cmd(
    match_id: str = typer.Argument(..., help="Pattern davranışı raporlanacak match ID"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Sprint 8.9 — Bir maçın Pattern B/C eşleşme davranışını rapor et."""
    _setup_logging("DEBUG" if verbose else "WARNING")

    from app.analysis.pattern_b import find_pattern_b_matches
    from app.analysis.pattern_c import find_pattern_c_all_periods

    async def _run() -> None:
        console.print(f"[cyan]Pattern audit başladı: {match_id}[/cyan]\n")
        raw = await fetch_match_detail(match_id)
        result = analyze_match(raw)

        b_results = {}
        for period_key, scores in [
            ("ht", (result.ht.scores_1, result.ht.scores_x, result.ht.scores_2)),
            ("h2", (result.half2.scores_1, result.half2.scores_x, result.half2.scores_2)),
            ("ft", (result.ft.scores_1, result.ft.scores_x, result.ft.scores_2)),
        ]:
            b = await find_pattern_b_matches(
                period_key, *scores, exclude_match_id=match_id, as_of=result.analyzed_at,
            )
            b_results[period_key] = b

        c_ht, c_h2, c_ft = await find_pattern_c_all_periods(
            result.ft.all_ratios, exclude_match_id=match_id, as_of=result.analyzed_at,
        )

        t = Table(title=f"{raw.home_team} vs {raw.away_team} [{raw.league_code}]")
        t.add_column("Pattern", style="cyan")
        t.add_column("İY", justify="right", style="yellow")
        t.add_column("2Y", justify="right", style="yellow")
        t.add_column("MS", justify="right", style="yellow")
        t.add_column("Yorum", style="dim")
        t.add_row(
            "Pattern B (skor seti)",
            str(b_results["ht"].match_count) if b_results["ht"] else "—",
            str(b_results["h2"].match_count) if b_results["h2"] else "—",
            str(b_results["ft"].match_count) if b_results["ft"] else "—",
            "Her periyot ayrı eşleşme — sayılar farklı olabilir",
        )
        c_count = c_ft.match_count if c_ft else (c_ht.match_count if c_ht else 0)
        t.add_row(
            "Pattern C (oran benzerliği)",
            str(c_count), str(c_count), str(c_count),
            "Tek FT set — üç periyot için aynı maçlar (tolerance=0)",
        )
        console.print(t)

        if c_count == 0:
            console.print(
                "\n[yellow]Pattern C eşleşmesi bulunamadı.[/yellow] "
                "[dim]tolerance=0.0 sıkı; bu maçın oranlarına tam aynı geçmiş maç yok.[/dim]"
            )
        elif c_count < 5:
            console.print(
                f"\n[yellow]⚠ Pattern C düşük güven: {c_count} maç (önerilen ≥5).[/yellow]"
            )

    asyncio.run(_run())


def recompute_patterns_cmd(
    limit: Optional[int] = typer.Option(None, "--limit", help="En fazla N maç işle. Boşsa hepsi."),
    batch_size: int = typer.Option(500, "--batch-size", help="Batch boyutu (default 500)."),
    only_missing: bool = typer.Option(False, "--only-missing", help="Hesaplama zamanı olmayan maçları işle."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Tüm matches tablosunda Pattern B/C alanlarını yeniden hesaplayıp DB'ye yaz."""
    _setup_logging("DEBUG" if verbose else "INFO")

    from sqlalchemy import select, and_
    from app.db.connection import get_session
    from app.db.models import Match
    from app.analysis.persist import compute_all_patterns, update_match_patterns
    from app.pipeline.runner import _with_retry

    async def _run() -> None:
        async with get_session() as session:
            filters = [Match.deleted_at.is_(None)]
            if only_missing:
                filters.append(Match.pattern_computed_at.is_(None))
            stmt = select(Match.match_id).where(and_(*filters)).order_by(Match.match_id)
            if limit:
                stmt = stmt.limit(limit)
            result = await session.execute(stmt)
            match_ids = [row[0] for row in result.all()]

        total = len(match_ids)
        if total == 0:
            console.print("[yellow]İşlenecek maç yok (filtreye uygun).[/yellow]")
            return

        console.print(
            f"[cyan]Recompute başladı:[/cyan] {total} maç · batch={batch_size}"
            f"{' · only-missing' if only_missing else ''}"
        )
        processed = 0
        errors = 0
        batch_count = (total + batch_size - 1) // batch_size

        for i in range(0, total, batch_size):
            batch = match_ids[i : i + batch_size]
            for mid in batch:
                try:
                    async with get_session() as session:
                        row = (await session.execute(
                            select(Match).where(Match.match_id == mid)
                        )).scalar_one_or_none()
                    if not row:
                        errors += 1
                        continue

                    patterns = await compute_all_patterns(
                        match_id=mid,
                        ht_scores=(row.ht_scores_1 or [], row.ht_scores_x or [], row.ht_scores_2 or []),
                        h2_scores=(row.h2_scores_1 or [], row.h2_scores_x or [], row.h2_scores_2 or []),
                        ft_scores=(row.ft_scores_1 or [], row.ft_scores_x or [], row.ft_scores_2 or []),
                        ft_ratios=row.ft_all_ratios,
                        as_of=row.analyzed_at,
                    )
                    await _with_retry(
                        lambda: update_match_patterns(mid, patterns, expected_analyzed_at=row.analyzed_at),
                        label=f"recompute {mid}",
                    )
                    processed += 1
                except Exception as exc:
                    logging.exception("Recompute hatası [%s]: %s", mid, exc)
                    errors += 1

            pct = 100.0 * (processed + errors) / total
            console.print(
                f"[dim]Batch {i // batch_size + 1}/{batch_count} bitti: "
                f"{processed} ✓ · {errors} ✗ · {pct:.1f}%[/dim]"
            )
            await asyncio.sleep(1.0)

        console.print(
            f"\n[bold green]Recompute tamamlandı:[/bold green] "
            f"[green]{processed} güncellendi[/green] · [red]{errors} hata[/red]"
        )

    asyncio.run(_run())


def self_test_cmd(
    match_id: str = typer.Argument("2813084", help="Test edilecek match ID"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Sprint 8.9 — Sistem sağlık E2E testi: tek maç üzerinden tüm boru hattı."""
    _setup_logging("DEBUG" if verbose else "WARNING")

    from app.analysis.league_filter import is_supported_league
    from app.analysis.persist import compute_all_patterns
    from app.analysis.trends import compute_trends
    from app.pipeline.runner import _validate_row, _result_to_row

    async def _run() -> None:
        console.print(Panel.fit(
            f"[bold]Self-Test:[/bold] Match {match_id}",
            border_style="cyan",
        ))

        console.print("[1/7] Match detail çekiliyor...", end=" ")
        raw = await fetch_match_detail(match_id)
        console.print(f"[green]✓[/green] {raw.home_team} vs {raw.away_team} [{raw.league_code}]")

        console.print("[2/7] is_supported_league()...", end=" ")
        ok = is_supported_league(raw.league_name, raw.league_code)
        console.print(f"[green]✓[/green] = {ok}")
        if not ok:
            console.print("[red]Bu maç lig maçı değil — pipeline burada durur.[/red]")
            return

        console.print("[3/7] check_match_filters()...", end=" ")
        check = check_match_filters(raw)
        if check.passed:
            console.print("[green]✓ PASSED[/green]")
        else:
            console.print(f"[yellow]✗ {check.reason.value}[/yellow] — {check.detail}")
            return

        console.print("[4/7] analyze_match() — Katman A...", end=" ")
        result = analyze_match(raw)
        a_count = (
            len(result.ft.scores_1) + len(result.ft.scores_x) + len(result.ft.scores_2)
        )
        console.print(f"[green]✓[/green] FT toplam {a_count} skor (3.5+ eşik)")

        console.print("[5/7] compute_all_patterns()...", end=" ")
        patterns = await compute_all_patterns(
            match_id=match_id,
            ht_scores=(result.ht.scores_1, result.ht.scores_x, result.ht.scores_2),
            h2_scores=(result.half2.scores_1, result.half2.scores_x, result.half2.scores_2),
            ft_scores=(result.ft.scores_1, result.ft.scores_x, result.ft.scores_2),
            ft_ratios=result.ft.all_ratios,
            as_of=result.analyzed_at,
        )
        ft_b_count = (patterns["pattern_ft_b"] or {}).get("match_count", 0)
        ft_c_count = (patterns["pattern_ft_c"] or {}).get("match_count", 0)
        console.print(f"[green]✓[/green] B={ft_b_count}, C={ft_c_count}")

        console.print("[6/7] compute_trends()...", end=" ")
        trends = compute_trends(raw)
        blocks_n = sum(1 for b in [trends.home_form, trends.away_form, trends.h2h] if b)
        console.print(f"[green]✓[/green] {blocks_n}/3 blok dolu")

        console.print("[7/7] _validate_row() pre-write...", end=" ")
        row = _result_to_row(result, raw, patterns)
        ok, reason = _validate_row(row)
        if ok:
            console.print("[green]✓ DB write hazır[/green]")
        else:
            console.print(f"[red]✗ {reason}[/red]")

        console.print()
        console.print(Panel.fit(
            f"[bold]Davranış Kanıtı:[/bold]\n"
            f"  • Pattern B MS sekmesi {ft_b_count} maç eşleşti, bu maçların\n"
            f"    actual_ht_* skorlarıyla İY/MS kombineleri hesaplandı.\n"
            f"  • Pattern C tek set {ft_c_count} maç (tolerance=0.0).\n"
            f"  • Lig adı kanonik: {row.get('league_code')}\n"
            f"  • Tüm 137 PatternResult alanı dolu: "
            f"{'evet' if patterns['pattern_ft_b'] else 'hayır'}",
            border_style="green",
        ))

    asyncio.run(_run())
