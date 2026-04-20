"""Nortverse CLI.

Kullanım:
    python -m app.cli.main analyze 2813084
    python -m app.cli.main analyze 2813084 --ratios        # 35 skorun hepsi
    python -m app.cli.main analyze-debug 2813084           # Excel karşılaştırma için tam detay
    python -m app.cli.main analyze-debug 2813084 --save    # debug/ klasörüne kaydet
    python -m app.cli.main fetch-fixture
    python -m app.cli.main fetch-fixture --date 2026-04-18
    python -m app.cli.main fetch-fixture --all             # gizli dahil tüm maçlar
    python -m app.cli.main fetch-and-analyze --save        # sonuçları dosyaya kaydet
"""

import asyncio
import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table

from app.analysis import analyze_match, check_match_filters
from app.analysis.pattern_b import PatternBResult, find_pattern_b_matches
from app.analysis.scores import ALL_SCORES, MS1_SCORES, MSX_SCORES, MS2_SCORES
from app.models import MatchAnalysisResult, MatchRawData, Period, PeriodAnalysis
from app.scraper import fetch_fixture, fetch_match_detail

app = typer.Typer(help="Nortverse - futbol tahmin sistemi CLI", no_args_is_help=True)
console = Console()

DEBUG_DIR = Path("debug")


def _flag(v: object) -> bool:
    """Typer 0.12 + Python 3.11 bool flag uyum katmanı.

    Typer bu kombinasyonda bool option'ları string veya None döndürüyor:
      - Flag geçilmeden → 'False' (str, truthy — yanlış!)
      - Flag geçilerek  → None
    Bu helper her iki durumu düzgün çözüyor.
    """
    # None = flag geçildi, 'False'/False = geçilmedi
    if v is None:
        return True
    if isinstance(v, bool):
        return v
    return str(v).lower() in ("true", "1", "yes")


def _setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=False)],
    )


def _make_recording_console() -> Console:
    """Hem terminale hem hafızaya yazan console döndür."""
    return Console(record=True)


def _save_text(content: str, filename: str) -> Path:
    """Debug çıktısını dosyaya kaydet."""
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    path = DEBUG_DIR / filename
    path.write_text(content, encoding="utf-8")
    return path


def _render_period(label: str, pa: PeriodAnalysis, con: Console) -> Table:
    """Bir periyodun 3.5+ sonucunu tablo olarak göster."""
    t = Table(
        title=f"{label} ({pa.period.value})",
        show_header=True,
        header_style="bold magenta",
    )
    t.add_column("Kategori", style="cyan", width=8)
    t.add_column("Adet", style="yellow", justify="right", width=6)
    t.add_column("Skorlar", style="green")

    t.add_row(f"{label}1", str(len(pa.scores_1)), " / ".join(pa.scores_1) or "—")
    t.add_row(f"{label}X", str(len(pa.scores_x)), " / ".join(pa.scores_x) or "—")
    t.add_row(f"{label}2", str(len(pa.scores_2)), " / ".join(pa.scores_2) or "—")
    return t


def _render_all_ratios(result: MatchAnalysisResult) -> Table:
    """35 skor × 3 periyot = 105 hücre tek tabloda.

    Excel ile karşılaştırmak için ideal format.
    """
    t = Table(
        title="Tüm Skor Oranları (35 skor × 3 periyot)",
        show_header=True,
        header_style="bold magenta",
    )
    t.add_column("Kategori", style="dim", width=10)
    t.add_column("Skor", style="cyan", width=6)
    t.add_column("İY", style="yellow", justify="right", width=6)
    t.add_column("2Y", style="yellow", justify="right", width=6)
    t.add_column("MS", style="yellow", justify="right", width=6)

    def _row(category: str, h: int, a: int) -> None:
        key = f"{h}-{a}"
        ht_v = result.ht.all_ratios.get(key, 0.0)
        h2_v = result.half2.all_ratios.get(key, 0.0)
        ft_v = result.ft.all_ratios.get(key, 0.0)

        def fmt(v: float) -> str:
            s = f"{v:.1f}"
            if v >= result.threshold:
                return f"[bold green]{s}*[/bold green]"
            return s

        t.add_row(category, key, fmt(ht_v), fmt(h2_v), fmt(ft_v))

    for h, a in MS1_SCORES:
        _row("MS1", h, a)
    t.add_section()
    for h, a in MSX_SCORES:
        _row("MSX", h, a)
    t.add_section()
    for h, a in MS2_SCORES:
        _row("MS2", h, a)

    return t


def _render_pattern_b(b: PatternBResult, con: Optional[Console] = None) -> None:
    """Katman B istatistiklerini konsola yazdır."""
    c = con or console
    c.print(
        Panel(
            f"Eşleşen geçmiş maç: [bold]{b.match_count}[/bold]\n"
            f"KG Var: [cyan]{b.kg_var_pct:.0f}%[/cyan]  |  "
            f"2.5 Üst: [cyan]{b.over_25_pct:.0f}%[/cyan]\n"
            f"[green]1: {b.result_1_pct:.0f}%[/green]  |  "
            f"[yellow]X: {b.result_x_pct:.0f}%[/yellow]  |  "
            f"[red]2: {b.result_2_pct:.0f}%[/red]",
            title="[magenta]Katman B — Pattern Matching[/magenta]",
            border_style="magenta",
        )
    )


def _render_result(result: MatchAnalysisResult, show_all_ratios: bool = False, con: Optional[Console] = None) -> None:
    """Analiz sonucunu konsola yazdır."""
    c = con or console
    header = Panel(
        f"[bold]{result.home_team}[/bold] vs [bold]{result.away_team}[/bold]\n"
        f"Lig: [cyan]{result.league_code}[/cyan]  |  Sezon: {result.season}\n"
        f"ID: {result.match_id}  |  N={result.n_matches}  |  Eşik={result.threshold}",
        title="[green]Analiz Sonucu[/green]",
        border_style="green",
    )
    c.print(header)

    c.print(_render_period("İY", result.ht, c))
    c.print(_render_period("2Y", result.half2, c))
    c.print(_render_period("MS", result.ft, c))

    if show_all_ratios:
        c.print(_render_all_ratios(result))

    if result.has_any_archive1_row:
        c.print("[green]ARSIV-1: YAZILIR[/green] (en az bir periyotta 3.5+ skor var)")
    else:
        c.print("[yellow]ARSIV-1: YAZILMAZ[/yellow] (hicbir periyotta 3.5+ skor yok)")


def _render_raw_matches(raw: MatchRawData, con: Optional[Console] = None) -> None:
    """Form + H2H maçlarını detaylıca göster — Excel karşılaştırması için."""
    c = con or console
    ev_league = [m for m in raw.home_recent_matches if m.is_league_match]
    dep_league = [m for m in raw.away_recent_matches if m.is_league_match]
    h2h_league = [m for m in raw.h2h_matches if m.is_league_match]

    def _matches_table(title: str, matches: list, team: str, limit: int = 5) -> Table:
        t = Table(title=title, show_header=True, header_style="bold cyan")
        t.add_column("#", width=3)
        t.add_column("Lig", style="magenta", width=10)
        t.add_column("Tarih", style="dim", width=10)
        t.add_column("Ev", style="green")
        t.add_column("Skor", style="yellow", width=10)
        t.add_column("Dep", style="green")
        t.add_column("Rol", style="cyan", width=4)
        t.add_column("İY", style="yellow", justify="right", width=4)
        t.add_column("2Y", style="yellow", justify="right", width=4)
        t.add_column("MS", style="yellow", justify="right", width=4)

        for i, m in enumerate(matches[:limit], 1):
            ht = f"({m.home_score_ht}-{m.away_score_ht})" if m.home_score_ht is not None else "?"
            score_str = f"{m.home_score_ft}-{m.away_score_ft} {ht}"
            date_str = m.match_date.strftime("%Y-%m-%d") if m.match_date else "?"

            if m.home_team == team:
                rol = "EV"
                g_ft = m.home_score_ft
                g_ht = m.home_score_ht if m.home_score_ht is not None else 0
            elif m.away_team == team:
                rol = "DEP"
                g_ft = m.away_score_ft
                g_ht = m.away_score_ht if m.away_score_ht is not None else 0
            else:
                continue
            g_2y = g_ft - g_ht

            t.add_row(
                str(i), m.league_code or "?", date_str,
                m.home_team, score_str, m.away_team,
                rol, str(g_ht), str(g_2y), str(g_ft),
            )
        return t

    c.print(_matches_table(
        f"Ev Sahibi ({raw.home_team}) — Son 5 Lig Maçı",
        ev_league, raw.home_team,
    ))
    c.print(_matches_table(
        f"Deplasman ({raw.away_team}) — Son 5 Lig Maçı",
        dep_league, raw.away_team,
    ))
    c.print(_matches_table(
        f"H2H (Ev Sahibi perspektifi: {raw.home_team})",
        h2h_league, raw.home_team,
    ))


def _render_goal_distributions(raw: MatchRawData, n: int = 5, con: Optional[Console] = None) -> Table:
    """Son 5 maçtaki gol dağılımlarını göster — formülün girdileri."""
    from app.analysis.engine import _goal_count_distribution

    t = Table(
        title=f"Gol Dağılımları (son {n} lig maçı)",
        show_header=True,
        header_style="bold magenta",
    )
    t.add_column("Kaynak", style="cyan", width=20)
    t.add_column("Periyot", style="yellow", width=8)
    for g in range(8):
        t.add_column(f"{g}", justify="right", width=4)

    ev_league = [m for m in raw.home_recent_matches if m.is_league_match][:n]
    dep_league = [m for m in raw.away_recent_matches if m.is_league_match][:n]
    h2h_league = [m for m in raw.h2h_matches if m.is_league_match][:n]

    def _add_row(label: str, matches: list, team: str, period: Period):
        dist = _goal_count_distribution(matches, team, period, n)
        vals = [str(dist.get(g, 0)) for g in range(8)]
        t.add_row(label, period.value, *vals)

    for period in [Period.HT, Period.H2, Period.FT]:
        _add_row(f"Form Ev ({raw.home_team})", ev_league, raw.home_team, period)
    t.add_section()
    for period in [Period.HT, Period.H2, Period.FT]:
        _add_row(f"Form Dep ({raw.away_team})", dep_league, raw.away_team, period)
    t.add_section()
    for period in [Period.HT, Period.H2, Period.FT]:
        _add_row(f"H2H Ev ({raw.home_team})", h2h_league, raw.home_team, period)
    t.add_section()
    for period in [Period.HT, Period.H2, Period.FT]:
        _add_row(f"H2H Dep ({raw.away_team})", h2h_league, raw.away_team, period)

    return t


def _result_to_json(result: MatchAnalysisResult) -> dict:
    """Analiz sonucunu JSON-serializable dict'e dönüştür."""
    def period_dict(pa: PeriodAnalysis) -> dict:
        return {
            "period": pa.period.value,
            "scores_1": pa.scores_1,
            "scores_x": pa.scores_x,
            "scores_2": pa.scores_2,
            "all_ratios": pa.all_ratios,
        }
    return {
        "match_id": result.match_id,
        "home_team": result.home_team,
        "away_team": result.away_team,
        "league_code": result.league_code,
        "season": result.season,
        "n_matches": result.n_matches,
        "threshold": result.threshold,
        "has_archive1_row": result.has_any_archive1_row,
        "ht": period_dict(result.ht),
        "half2": period_dict(result.half2),
        "ft": period_dict(result.ft),
    }


@app.command()
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
    _setup_logging("DEBUG" if _flag(verbose) else "INFO")

    async def _run() -> None:
        con = _make_recording_console() if _flag(save) else console
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
            if _flag(save):
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                txt_path = _save_text(con.export_text(), f"analyze_{match_id}_{ts}.txt")
                console.print(f"[dim]Kaydedildi: {txt_path}[/dim]")
            return

        con.print("[green]Filtreleme: GECTI[/green]")
        result = analyze_match(raw, n_matches=n, threshold=threshold)
        _render_result(result, show_all_ratios=_flag(ratios), con=con)

        # Katman B — pattern matching
        try:
            b_result = await find_pattern_b_matches(
                ft_scores_1=result.ft.scores_1,
                ft_scores_x=result.ft.scores_x,
                ft_scores_2=result.ft.scores_2,
            )
            if b_result:
                _render_pattern_b(b_result, con=con)
            else:
                con.print("[dim]Katman B: Yeterli eşleşme yok (arşiv boş veya < 5 maç)[/dim]")
        except Exception as e:
            con.print(f"[dim]Katman B sorgusu yapılamadı: {e}[/dim]")

        if _flag(save):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            txt_path = _save_text(con.export_text(), f"analyze_{match_id}_{ts}.txt")
            json_path = DEBUG_DIR / f"analyze_{match_id}_{ts}.json"
            json_path.write_text(
                json.dumps(_result_to_json(result), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            console.print(f"[dim]Kaydedildi: {txt_path}  |  {json_path}[/dim]")

    asyncio.run(_run())


@app.command("analyze-debug")
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
    _setup_logging("DEBUG" if _flag(verbose) else "INFO")

    async def _run() -> None:
        con = _make_recording_console() if _flag(save) else console
        con.print(f"[cyan]Match detail çekiliyor: {match_id}[/cyan]")
        raw = await fetch_match_detail(match_id)

        con.print(
            f"\n[bold]{raw.home_team}[/bold] vs [bold]{raw.away_team}[/bold] "
            f"[cyan]{raw.league_code}[/cyan]\n"
        )

        # 1. Ham maç listeleri
        _render_raw_matches(raw, con=con)

        # 2. Gol dağılımları
        con.print(_render_goal_distributions(raw, n=n, con=con))

        # 3. Filtreleme (debug modda analizi durdurmaz, uyarı gösterir)
        check = check_match_filters(raw)
        if not check.passed:
            con.print(Panel(
                f"[yellow]Kural dışı:[/yellow] {check.reason.value}\n{check.detail}\n\n"
                f"[dim]Debug modu: Analiz yine de çalıştırılıyor.[/dim]",
                title="[yellow]Filtre Uyarısı[/yellow]", border_style="yellow",
            ))
        else:
            con.print("[green]Filtreleme: GECTI[/green]")

        # 4. Analiz + tüm oranlar (filtre fail olsa da çalışır)
        result = analyze_match(raw, n_matches=n, threshold=threshold)
        _render_result(result, show_all_ratios=True, con=con)

        # Katman B — pattern matching
        try:
            b_result = await find_pattern_b_matches(
                ft_scores_1=result.ft.scores_1,
                ft_scores_x=result.ft.scores_x,
                ft_scores_2=result.ft.scores_2,
            )
            if b_result:
                _render_pattern_b(b_result, con=con)
            else:
                con.print("[dim]Katman B: Yeterli eşleşme yok (arşiv boş veya < 5 maç)[/dim]")
        except Exception as e:
            con.print(f"[dim]Katman B sorgusu yapılamadı: {e}[/dim]")

        if _flag(save):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            txt_path = _save_text(con.export_text(), f"debug_{match_id}_{ts}.txt")
            json_path = DEBUG_DIR / f"debug_{match_id}_{ts}.json"
            json_path.write_text(
                json.dumps(_result_to_json(result), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            console.print(f"[dim]Kaydedildi: {txt_path}  |  {json_path}[/dim]")

    asyncio.run(_run())


@app.command("fetch-fixture")
def fetch_fixture_cmd(
    target_date: Optional[str] = typer.Option(
        None, "--date", help="YYYY-MM-DD. Boşsa bugün."
    ),
    all_matches: bool = typer.Option(False, "--all", help="Gizli maçlar dahil tümü (site Hot ile filtreliyor)"),
    save: bool = typer.Option(False, "--save", help="Sonucu debug/ klasörüne kaydet"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Bülteni çek ve maç listesini yazdır. Varsayılan: sitenin Hot moduyla gösterdikleri."""
    _setup_logging("DEBUG" if _flag(verbose) else "INFO")

    dt: Optional[date] = None
    if target_date:
        dt = datetime.strptime(target_date, "%Y-%m-%d").date()

    async def _run() -> None:
        matches = await fetch_fixture(target_date=dt, only_hot=not _flag(all_matches))

        if not matches:
            console.print("[yellow]Hiç maç bulunamadı[/yellow]")
            return

        from collections import defaultdict

        by_league: dict[str, list] = defaultdict(list)
        for m in matches:
            by_league[m.league_code].append(m)

        mode_label = "Hot (site görünümü)" if not _flag(all_matches) else "Tümü (gizli dahil)"
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

        if _flag(save):
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


@app.command("fetch-and-analyze")
def fetch_and_analyze_cmd(
    target_date: Optional[str] = typer.Option(None, "--date"),
    limit: int = typer.Option(0, "--limit", help="Kaç maç (0=hepsi)"),
    save: bool = typer.Option(False, "--save", help="Sonuçları debug/ klasörüne kaydet"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Bültendeki Hot maçların hepsini çek ve analiz et."""
    _setup_logging("DEBUG" if _flag(verbose) else "INFO")

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
                    if _flag(save):
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
                if _flag(save):
                    all_results.append(_result_to_json(result))
            except Exception as e:
                console.print(f"[red]Hata ({fm.match_id}): {e}[/red]")
                summary_table.add_row(
                    fm.match_id, f"{fm.home_team}-{fm.away_team}",
                    "[red]HATA[/red]", "-", "-", "-",
                )
                if _flag(save):
                    all_results.append({
                        "match_id": fm.match_id,
                        "home": fm.home_team,
                        "away": fm.away_team,
                        "status": "error",
                        "error": str(e),
                    })

        console.print(summary_table)

        if _flag(save):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            date_label = (dt or date.today()).strftime("%Y%m%d")

            # Özet tabloyu text olarak kaydet
            rec = _make_recording_console()
            rec.print(summary_table)
            txt_path = _save_text(rec.export_text(), f"batch_{date_label}_{ts}.txt")

            # Tüm JSON sonuçlar
            json_path = DEBUG_DIR / f"batch_{date_label}_{ts}.json"
            json_path.write_text(
                json.dumps(all_results, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            console.print(f"[dim]Kaydedildi: {txt_path}  |  {json_path}[/dim]")

    asyncio.run(_run())


@app.command("build-archive")
def build_archive_cmd(
    league: str = typer.Argument(..., help="Nowgoal lig ID'si (örn: 36 = ENG PR)"),
    season: Optional[str] = typer.Argument(None, help="Sezon (örn: 2024-2025). Boşsa güncel sezon."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Geçmiş sezon maçlarını çekip DB'ye arşivle.

    Örnekler:
        build-archive 36 2024-2025
        build-archive 36   (güncel sezon)
    """
    _setup_logging("DEBUG" if _flag(verbose) else "INFO")

    from app.pipeline.runner import _upsert
    from app.scraper.browser import browser_context
    from app.scraper.league import fetch_league_match_ids

    league_id = int(league)
    seasons = [season] if season else [None]

    async def _run() -> None:
        stats = {"analyzed": 0, "skipped": 0, "errors": 0}
        total_ids: list[tuple[str, str | None]] = []

        async with browser_context() as ctx:
            for s in seasons:
                label = s or "güncel sezon"
                console.print(f"[cyan]Lig {league_id} / {label} maç ID'leri çekiliyor...[/cyan]")
                ids = await fetch_league_match_ids(league_id=league_id, season=s, ctx=ctx)
                console.print(f"  → {len(ids)} maç bulundu")
                for mid in ids:
                    total_ids.append((mid, s))

            if not total_ids:
                console.print("[yellow]Hiç maç ID'si bulunamadı. Debug HTML'ini inceleyin.[/yellow]")
                return

            console.print(f"\n[bold]{len(total_ids)} maç arşivlenecek...[/bold]\n")

            for i, (mid, s) in enumerate(total_ids, 1):
                try:
                    console.print(f"[dim]({i}/{len(total_ids)}) {mid}...[/dim]", end="")
                    raw = await fetch_match_detail(mid, ctx=ctx)
                    check = check_match_filters(raw)
                    if not check.passed:
                        console.print(f" [yellow]atlandı ({check.reason.value})[/yellow]")
                        stats["skipped"] += 1
                        continue

                    result = analyze_match(raw)
                    await _upsert(result, raw)
                    stats["analyzed"] += 1
                    score_str = ""
                    if raw.actual_ft_home is not None:
                        score_str = f" | Skor: {raw.actual_ft_home}-{raw.actual_ft_away}"
                    console.print(
                        f" [green]kaydedildi[/green] — "
                        f"{raw.home_team} vs {raw.away_team}{score_str}"
                    )
                except Exception as e:
                    console.print(f" [red]hata: {e}[/red]")
                    stats["errors"] += 1

        console.print(
            f"\n[bold green]Arşiv tamamlandı:[/bold green] "
            f"[green]{stats['analyzed']} kaydedildi[/green] · "
            f"[yellow]{stats['skipped']} atlandı[/yellow] · "
            f"[red]{stats['errors']} hata[/red]"
        )

    asyncio.run(_run())


@app.command("run-pipeline")
def run_pipeline_cmd(
    target_date: Optional[str] = typer.Option(None, "--date", help="YYYY-MM-DD. Boşsa bugün."),
    all_matches: bool = typer.Option(False, "--all", help="Hot değil, tüm maçlar"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Hot maçları çek → analiz et → Supabase'e kaydet."""
    _setup_logging("DEBUG" if _flag(verbose) else "INFO")

    dt: Optional[date] = None
    if target_date:
        dt = datetime.strptime(target_date, "%Y-%m-%d").date()

    from app.pipeline import run_pipeline

    async def _run() -> None:
        stats = await run_pipeline(target_date=dt, only_hot=not _flag(all_matches))
        console.print(
            f"\n[bold green]Pipeline tamamlandı:[/bold green] "
            f"[green]{stats['analyzed']} kaydedildi[/green] · "
            f"[yellow]{stats['skipped']} atlandı[/yellow] · "
            f"[red]{stats['errors']} hata[/red]"
        )

    asyncio.run(_run())


@app.command()
def version() -> None:
    from app import __version__

    console.print(f"nortverse [cyan]v{__version__}[/cyan]")


if __name__ == "__main__":
    app()
