"""Pipeline, analiz ve sunucu komutları."""

import asyncio
import json
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import typer
from rich.panel import Panel
from rich.table import Table

from app.analysis import analyze_match, check_match_filters
from app.analysis.pattern_b import find_pattern_b_matches
from app.analysis.pattern_c import find_pattern_c_all_periods
from app.cli._helpers import (
    DEBUG_DIR,
    _make_recording_console,
    _render_goal_distributions,
    _render_pattern,
    _render_raw_matches,
    _render_result,
    _result_to_json,
    _save_text,
    _setup_logging,
    console,
)
from app.scraper import fetch_fixture, fetch_match_detail


def analyze(
    match_id: str = typer.Argument(..., help="Nowgoal match ID (örn: 2813084)"),
    ratios: bool = typer.Option(
        False, "--ratios", help="35 skorun 3 periyotta da oranlarını göster"
    ),
    n: int = typer.Option(5, "--n", help="Son kaç maç analiz edilsin"),
    threshold: float = typer.Option(3.5, "--threshold", help="Oran eşiği"),
    save: bool = typer.Option(False, "--save", help="Sonucu debug/ klasörüne kaydet"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Tek bir maçı analiz eder."""
    _setup_logging("DEBUG" if verbose else "INFO")

    async def _run() -> None:
        con = _make_recording_console() if save else console
        con.print(f"[cyan]Match detail çekiliyor: {match_id}[/cyan]")
        raw = await fetch_match_detail(match_id)

        con.print(
            f"[dim]Çekildi: {raw.home_team} vs {raw.away_team} [{raw.league_code}]  |  "
            f"ev_ligte={raw.home_league_match_count}, "
            f"dep_ligte={raw.away_league_match_count}, "
            f"h2h={len(raw.h2h_matches)} (lig: "
            f"{sum(1 for m in raw.h2h_matches if m.is_league_match)})[/dim]"
        )

        check = check_match_filters(raw)
        if not check.passed:
            con.print(Panel(
                f"[yellow]Kural dışı:[/yellow] {check.reason.value}\n{check.detail}\n\n"
                f"[dim]İpucu: Tüm oranları görmek için 'analyze-debug {match_id}' komutunu kullanın.[/dim]",
                title="[yellow]Atlandı[/yellow]", border_style="yellow",
            ))
            if save:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                txt_path = _save_text(con.export_text(), f"analyze_{match_id}_{ts}.txt")
                console.print(f"[dim]Kaydedildi: {txt_path}[/dim]")
            return

        con.print("[green]Filtreleme: GECTI[/green]")
        result = analyze_match(raw, n_matches=n, threshold=threshold)
        _render_result(result, show_all_ratios=ratios, con=con)

        try:
            b_result = await find_pattern_b_matches(
                period="ft",
                scores_1=result.ft.scores_1,
                scores_x=result.ft.scores_x,
                scores_2=result.ft.scores_2,
            )
            if b_result:
                _render_pattern(b_result, "[magenta]Katman B — Pattern Matching[/magenta]", "magenta", con=con)
            else:
                con.print("[dim]Katman B: Yeterli eşleşme yok (arşiv boş veya < 5 maç)[/dim]")
        except Exception as e:
            con.print(f"[dim]Katman B sorgusu yapılamadı: {e}[/dim]")

        try:
            _ht_c, _h2_c, ft_c = await find_pattern_c_all_periods(result.ft.all_ratios)
            if ft_c:
                _render_pattern(ft_c, "[blue]Katman C — Oran Eşleşmesi (±0.5)[/blue]", "blue", con=con)
            else:
                con.print("[dim]Katman C: Yeterli eşleşme yok (arşiv boş veya < 5 maç)[/dim]")
        except Exception as e:
            con.print(f"[dim]Katman C sorgusu yapılamadı: {e}[/dim]")

        if save:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            txt_path = _save_text(con.export_text(), f"analyze_{match_id}_{ts}.txt")
            json_path = DEBUG_DIR / f"analyze_{match_id}_{ts}.json"
            json_path.write_text(
                json.dumps(_result_to_json(result), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            console.print(f"[dim]Kaydedildi: {txt_path}  |  {json_path}[/dim]")

    asyncio.run(_run())


def analyze_debug(
    match_id: str = typer.Argument(..., help="Nowgoal match ID (örn: 2813084)"),
    n: int = typer.Option(5, "--n", help="Son kaç maç"),
    threshold: float = typer.Option(3.5, "--threshold", help="Oran eşiği"),
    save: bool = typer.Option(False, "--save", help="Sonucu debug/ klasörüne kaydet"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Bir maçı analiz eder + tüm ham veriyi gösterir.

    Excel ile karşılaştırma için ideal. Gösterir:
    - Alınan 5 ev maçı (İY/2Y/MS gol sayıları dahil)
    - Alınan 5 dep maçı
    - Alınan 5 h2h maçı
    - Her takım × her periyot için gol dağılımı (formül girdisi)
    - 35 skor × 3 periyot için tüm oranlar
    """
    _setup_logging("DEBUG" if verbose else "INFO")

    async def _run() -> None:
        con = _make_recording_console() if save else console
        con.print(f"[cyan]Match detail çekiliyor: {match_id}[/cyan]")
        raw = await fetch_match_detail(match_id)

        con.print(
            f"\n[bold]{raw.home_team}[/bold] vs [bold]{raw.away_team}[/bold] "
            f"[cyan]{raw.league_code}[/cyan]\n"
        )

        _render_raw_matches(raw, con=con)
        con.print(_render_goal_distributions(raw, n=n, con=con))

        check = check_match_filters(raw)
        if not check.passed:
            con.print(Panel(
                f"[yellow]Kural dışı:[/yellow] {check.reason.value}\n{check.detail}\n\n"
                f"[dim]Debug modu: Analiz yine de çalıştırılıyor.[/dim]",
                title="[yellow]Filtre Uyarısı[/yellow]", border_style="yellow",
            ))
        else:
            con.print("[green]Filtreleme: GECTI[/green]")

        result = analyze_match(raw, n_matches=n, threshold=threshold)
        _render_result(result, show_all_ratios=True, con=con)

        try:
            b_result = await find_pattern_b_matches(
                period="ft",
                scores_1=result.ft.scores_1,
                scores_x=result.ft.scores_x,
                scores_2=result.ft.scores_2,
            )
            if b_result:
                _render_pattern(b_result, "[magenta]Katman B — Pattern Matching[/magenta]", "magenta", con=con)
            else:
                con.print("[dim]Katman B: Yeterli eşleşme yok (arşiv boş veya < 5 maç)[/dim]")
        except Exception as e:
            con.print(f"[dim]Katman B sorgusu yapılamadı: {e}[/dim]")

        try:
            _ht_c, _h2_c, ft_c = await find_pattern_c_all_periods(result.ft.all_ratios)
            if ft_c:
                _render_pattern(ft_c, "[blue]Katman C — Oran Eşleşmesi (±0.5)[/blue]", "blue", con=con)
            else:
                con.print("[dim]Katman C: Yeterli eşleşme yok (arşiv boş veya < 5 maç)[/dim]")
        except Exception as e:
            con.print(f"[dim]Katman C sorgusu yapılamadı: {e}[/dim]")

        if save:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            txt_path = _save_text(con.export_text(), f"debug_{match_id}_{ts}.txt")
            json_path = DEBUG_DIR / f"debug_{match_id}_{ts}.json"
            json_path.write_text(
                json.dumps(_result_to_json(result), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            console.print(f"[dim]Kaydedildi: {txt_path}  |  {json_path}[/dim]")

    asyncio.run(_run())


def fetch_fixture_cmd(
    target_date: Optional[str] = typer.Option(
        None, "--date", help="YYYY-MM-DD. Boşsa bugün."
    ),
    all_matches: bool = typer.Option(False, "--all", help="Gizli maçlar dahil tümü (site Hot ile filtreliyor)"),
    save: bool = typer.Option(False, "--save", help="Sonucu debug/ klasörüne kaydet"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Bülteni çek ve maç listesini yazdır. Varsayılan: sitenin Hot moduyla gösterdikleri."""
    _setup_logging("DEBUG" if verbose else "INFO")

    dt: Optional[date] = None
    if target_date:
        dt = datetime.strptime(target_date, "%Y-%m-%d").date()

    async def _run() -> None:
        matches = await fetch_fixture(target_date=dt, only_hot=not all_matches)

        if not matches:
            console.print("[yellow]Hiç maç bulunamadı[/yellow]")
            return

        from collections import defaultdict

        by_league: dict[str, list] = defaultdict(list)
        for m in matches:
            by_league[m.league_code].append(m)

        mode_label = "Hot (site görünümü)" if not all_matches else "Tümü (gizli dahil)"
        t = Table(title=f"{mode_label} — {len(matches)} maç, {len(by_league)} lig")
        t.add_column("ID", style="cyan")
        t.add_column("Lig", style="magenta")
        t.add_column("Saat", style="yellow")
        t.add_column("Ev", style="green")
        t.add_column("Deplasman", style="green")

        for league in sorted(by_league.keys()):
            for m in by_league[league]:
                time_str = m.kickoff_time.strftime("%H:%M") if m.kickoff_time else "?"
                t.add_row(m.match_id, league, time_str, m.home_team, m.away_team)

        if save:
            rec = _make_recording_console()
            rec.print(t)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            date_label = (dt or date.today()).strftime("%Y%m%d")
            txt_path = _save_text(rec.export_text(), f"fixture_{date_label}_{ts}.txt")
            json_path = DEBUG_DIR / f"fixture_{date_label}_{ts}.json"
            json_path.write_text(
                json.dumps(
                    [
                        {
                            "match_id": m.match_id,
                            "league": m.league_code,
                            "home": m.home_team,
                            "away": m.away_team,
                            "kickoff": m.kickoff_time.isoformat() if m.kickoff_time else None,
                        }
                        for m in matches
                    ],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            console.print(f"[dim]Kaydedildi: {txt_path}  |  {json_path}[/dim]")

        console.print(t)

    asyncio.run(_run())


def fetch_and_analyze_cmd(
    target_date: Optional[str] = typer.Option(None, "--date"),
    limit: int = typer.Option(0, "--limit", help="Kaç maç (0=hepsi)"),
    save: bool = typer.Option(False, "--save", help="Sonuçları debug/ klasörüne kaydet"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Bültendeki Hot maçların hepsini çek ve analiz et."""
    _setup_logging("DEBUG" if verbose else "INFO")

    dt: Optional[date] = None
    if target_date:
        dt = datetime.strptime(target_date, "%Y-%m-%d").date()

    async def _run() -> None:
        matches = await fetch_fixture(target_date=dt, only_hot=True)

        if not matches:
            console.print("[yellow]Hiç maç bulunamadı[/yellow]")
            return

        if limit > 0:
            matches = matches[:limit]

        console.print(f"[cyan]{len(matches)} maç analiz edilecek[/cyan]\n")

        summary_table = Table(title=f"Analiz Özeti ({len(matches)} maç)")
        summary_table.add_column("ID", style="cyan")
        summary_table.add_column("Maç", style="green")
        summary_table.add_column("Durum", style="yellow")
        summary_table.add_column("MS1", style="magenta")
        summary_table.add_column("MSX", style="magenta")
        summary_table.add_column("MS2", style="magenta")

        all_results: list[dict] = []

        for i, fm in enumerate(matches, 1):
            console.print(f"[dim]({i}/{len(matches)}) {fm.home_team} vs {fm.away_team}...[/dim]")
            try:
                raw = await fetch_match_detail(fm.match_id)
                check = check_match_filters(raw)
                if not check.passed:
                    summary_table.add_row(
                        fm.match_id, f"{fm.home_team}-{fm.away_team}",
                        f"[yellow]{check.reason.value}[/yellow]", "-", "-", "-",
                    )
                    if save:
                        all_results.append({
                            "match_id": fm.match_id,
                            "home": fm.home_team,
                            "away": fm.away_team,
                            "status": "skipped",
                            "reason": check.reason.value,
                        })
                    continue

                result = analyze_match(raw)
                summary_table.add_row(
                    fm.match_id, f"{fm.home_team}-{fm.away_team}",
                    "[green]OYNA[/green]" if result.has_any_archive1_row else "[dim]boş[/dim]",
                    " / ".join(result.ft.scores_1) or "-",
                    " / ".join(result.ft.scores_x) or "-",
                    " / ".join(result.ft.scores_2) or "-",
                )
                if save:
                    all_results.append(_result_to_json(result))
            except Exception as e:
                console.print(f"[red]Hata ({fm.match_id}): {e}[/red]")
                summary_table.add_row(
                    fm.match_id, f"{fm.home_team}-{fm.away_team}",
                    "[red]HATA[/red]", "-", "-", "-",
                )
                if save:
                    all_results.append({
                        "match_id": fm.match_id,
                        "home": fm.home_team,
                        "away": fm.away_team,
                        "status": "error",
                        "error": str(e),
                    })

        console.print(summary_table)

        if save:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            date_label = (dt or date.today()).strftime("%Y%m%d")
            rec = _make_recording_console()
            rec.print(summary_table)
            txt_path = _save_text(rec.export_text(), f"batch_{date_label}_{ts}.txt")
            json_path = DEBUG_DIR / f"batch_{date_label}_{ts}.json"
            json_path.write_text(
                json.dumps(all_results, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            console.print(f"[dim]Kaydedildi: {txt_path}  |  {json_path}[/dim]")

    asyncio.run(_run())


def run_pipeline_cmd(
    target_date: Optional[str] = typer.Option(None, "--date", help="YYYY-MM-DD. Boşsa bugün."),
    all_matches: bool = typer.Option(False, "--all", help="Hot değil, tüm maçlar"),
    incremental: bool = typer.Option(False, "--incremental", help="Hazır maçları tekrar analiz etme"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Hot maçları çek → analiz et → DB'ye kaydet."""
    _setup_logging("DEBUG" if verbose else "INFO")

    dt: Optional[date] = None
    if target_date:
        dt = datetime.strptime(target_date, "%Y-%m-%d").date()

    from app.pipeline import run_pipeline

    async def _run() -> None:
        stats = await run_pipeline(target_date=dt, only_hot=not all_matches, incremental=incremental)
        console.print(
            f"\n[bold green]Pipeline tamamlandı:[/bold green] "
            f"[green]{stats['analyzed']} kaydedildi[/green] · "
            f"[yellow]{stats['skipped']} atlandı[/yellow] · "
            f"[red]{stats['errors']} hata[/red]"
        )

    asyncio.run(_run())


def capture_score_snapshots_cmd(
    target_date: str = typer.Option(..., "--date", help="YYYY-MM-DD (İstanbul günü)"),
) -> None:
    """Maç başlamadan hazırlanmış skor listelerini ileri dönem takibine sabitle."""
    from app.analysis.score_snapshots import capture_prepared_score_snapshots

    day = datetime.strptime(target_date, "%Y-%m-%d").date()
    count = asyncio.run(capture_prepared_score_snapshots(day))
    console.print(f"[green]{day}: {count} yeni skor karşılaştırması sabitlendi[/green]")


def capture_recommendations_cmd(
    target_date: str = typer.Option(..., "--date", help="YYYY-MM-DD (İstanbul günü)"),
) -> None:
    """Hazır analizlerin ölçülecek FT seçimlerini maç başlamadan sabitle."""
    from app.analysis.snapshots import capture_prepared_recommendations

    day = datetime.strptime(target_date, "%Y-%m-%d").date()
    count = asyncio.run(capture_prepared_recommendations(day))
    console.print(f"[green]{day}: {count} yeni FT seçim kaydı sabitlendi[/green]")


def refresh_fixture_cache_cmd(
    target_date: Optional[str] = typer.Option(None, "--date", help="YYYY-MM-DD. Boşsa yarın (İstanbul)."),
) -> None:
    """Ertesi günün maç listesini analiz yapmadan önbelleğe alır."""
    _setup_logging("INFO")
    day = (datetime.strptime(target_date, "%Y-%m-%d").date() if target_date
           else datetime.now(timezone(timedelta(hours=3))).date() + timedelta(days=1))

    from app.pipeline.runner import refresh_fixture_cache

    count = asyncio.run(refresh_fixture_cache(day))
    console.print(f"[green]{day}: {count} lig maçı bülten önbelleğine kaydedildi[/green]")


def update_scores_cmd(
    target_date: Optional[str] = typer.Option(None, "--date", help="YYYY-MM-DD. Boşsa bugün (gece 00-04 arası ise dün)."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """DB'deki maçların gerçek sonuçlarını günceller."""
    _setup_logging("DEBUG" if verbose else "INFO")

    dt: Optional[date] = None
    if target_date:
        dt = datetime.strptime(target_date, "%Y-%m-%d").date()

    from app.pipeline import update_results

    async def _run() -> None:
        stats = await update_results(target_date=dt)
        console.print(
            f"\n[bold green]Sonuç güncellemesi tamamlandı:[/bold green] "
            f"[green]{stats['updated']} güncellendi[/green] · "
            f"[yellow]{stats['not_finished']} bitmemiş[/yellow] · "
            f"{stats['skipped']} atlandı · "
            f"[red]{stats['errors']} hata[/red]"
        )

    asyncio.run(_run())


def serve(
    host: str = typer.Option("0.0.0.0", "--host", help="Dinlenecek adres"),
    port: int = typer.Option(8000, "--port", help="Port"),
    reload: bool = typer.Option(False, "--reload", help="Geliştirme modu (dosya değişikliğinde yeniden yükle)"),
) -> None:
    """FastAPI sunucusunu başlatır."""
    import sys
    import uvicorn
    if sys.platform == "win32":
        import asyncio as _asyncio
        _asyncio.set_event_loop_policy(_asyncio.WindowsProactorEventLoopPolicy())
    uvicorn.run(
        "app.api.main:app",
        host=host,
        port=port,
        reload=reload,
        loop="none",
    )
