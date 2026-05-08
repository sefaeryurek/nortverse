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
from app.analysis.pattern_b import find_pattern_b_matches
from app.analysis.pattern_c import find_pattern_c_all_periods
from app.analysis.pattern_stats import PatternResult
from app.analysis.scores import ALL_SCORES, MS1_SCORES, MSX_SCORES, MS2_SCORES
from app.models import MatchAnalysisResult, MatchRawData, Period, PeriodAnalysis
from app.scraper import fetch_fixture, fetch_leagues, fetch_match_detail
from app.scraper.league import fetch_league_seasons

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


def _render_pattern(p: PatternResult, title: str, style: str, con: Optional[Console] = None) -> None:
    """Pattern istatistiklerini konsola yazdır."""
    c = con or console
    c.print(
        Panel(
            f"Eşleşen geçmiş maç: [bold]{p.match_count}[/bold]\n"
            f"KG Var: [cyan]{p.kg_var_pct:.0f}%[/cyan]  |  "
            f"2.5 Üst: [cyan]{p.ust_25_pct:.0f}%[/cyan]\n"
            f"[green]1: {p.result_1_pct:.0f}%[/green]  |  "
            f"[yellow]X: {p.result_x_pct:.0f}%[/yellow]  |  "
            f"[red]2: {p.result_2_pct:.0f}%[/red]",
            title=title,
            border_style=style,
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

        # Katman B — pattern matching (FT)
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

        # Katman C — oran eşleşmesi (FT)
        try:
            _ht_c, _h2_c, ft_c = await find_pattern_c_all_periods(result.ft.all_ratios)
            if ft_c:
                _render_pattern(ft_c, "[blue]Katman C — Oran Eşleşmesi (±0.5)[/blue]", "blue", con=con)
            else:
                con.print("[dim]Katman C: Yeterli eşleşme yok (arşiv boş veya < 5 maç)[/dim]")
        except Exception as e:
            con.print(f"[dim]Katman C sorgusu yapılamadı: {e}[/dim]")

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

        # Katman B — pattern matching (FT, debug)
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

        # Katman C — oran eşleşmesi (FT, debug)
        try:
            _ht_c, _h2_c, ft_c = await find_pattern_c_all_periods(result.ft.all_ratios)
            if ft_c:
                _render_pattern(ft_c, "[blue]Katman C — Oran Eşleşmesi (±0.5)[/blue]", "blue", con=con)
            else:
                con.print("[dim]Katman C: Yeterli eşleşme yok (arşiv boş veya < 5 maç)[/dim]")
        except Exception as e:
            con.print(f"[dim]Katman C sorgusu yapılamadı: {e}[/dim]")

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
                console.print(f"  {len(ids)} mac bulundu")
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
def serve(
    host: str = typer.Option("0.0.0.0", "--host", help="Dinlenecek adres"),
    port: int = typer.Option(8000, "--port", help="Port"),
    reload: bool = typer.Option(False, "--reload", help="Geliştirme modu (dosya değişikliğinde yeniden yükle)"),
) -> None:
    """FastAPI sunucusunu başlatır.

    Örnek: python -m app.cli.main serve
           python -m app.cli.main serve --reload  # geliştirme modu
    """
    import sys
    import uvicorn
    # Windows'ta Playwright subprocess için ProactorEventLoop gerekiyor
    if sys.platform == "win32":
        import asyncio
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    uvicorn.run(
        "app.api.main:app",
        host=host,
        port=port,
        reload=_flag(reload),
        loop="none",
    )


@app.command("list-leagues")
def list_leagues_cmd(
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Bugünkü fixture sayfasındaki tüm ligleri listeler (ID + ad).

    Çıkan ID'leri build-archive veya build-multi-archive komutlarında kullanın.
    """
    _setup_logging("DEBUG" if _flag(verbose) else "WARNING")

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


@app.command("build-multi-archive")
def build_multi_archive_cmd(
    league_ids: list[str] = typer.Argument(..., help="Lig ID listesi (boşlukla ayırın: 36 60 65)"),
    seasons: Optional[str] = typer.Option(None, "--seasons", "-s", help="Her lig için kaç sezon geriye git (varsayılan: 5)"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Birden fazla lig için arşiv oluşturur — her ligi son N sezonda çeker.

    Örnek: build-multi-archive 36 60 65 --seasons 4
           → ENG PR, TUR D1, ... için son 4 sezon
    """
    _setup_logging("DEBUG" if _flag(verbose) else "INFO")
    # Typer 0.12.5: int option'lar None dönebiliyor, str olarak alıp çeviriyoruz
    n_seasons = int(seasons) if seasons and str(seasons).isdigit() else 5
    from app.pipeline.runner import _upsert
    from app.scraper.browser import browser_context
    from app.scraper.league import fetch_league_match_ids, fetch_league_seasons
    from app.scraper.match_detail import fetch_match_detail as _fetch_detail

    def _recent_seasons(n: int) -> list[str]:
        """Güncel tarihten geriye n sezon üret (ör. 2024-2025, 2023-2024 ...)."""
        now = datetime.now()
        start_year = now.year if now.month >= 8 else now.year - 1
        return [f"{start_year - i}-{start_year - i + 1}" for i in range(n)]

    async def _run() -> None:
        total_stats = {"analyzed": 0, "skipped": 0, "errors": 0, "leagues": 0}

        async with browser_context() as ctx:
            for lid_str in league_ids:
                if lid_str.startswith("-"):
                    continue  # option artefact'ı atla
                try:
                    lid = int(lid_str)
                except ValueError:
                    console.print(f"[red]Geçersiz lig ID: {lid_str}[/red]")
                    continue

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

                    console.print(
                        f"  [cyan]{season}[/cyan]: {len(match_ids)} maç işlenecek"
                    )
                    stats = {"analyzed": 0, "skipped": 0, "errors": 0}

                    for i, mid in enumerate(match_ids, 1):
                        try:
                            raw = await _fetch_detail(mid, ctx=ctx)
                            check = check_match_filters(raw)
                            if not check.passed:
                                stats["skipped"] += 1
                                continue
                            result = analyze_match(raw)
                            await _upsert(result, raw)
                            stats["analyzed"] += 1
                            if i % 20 == 0:
                                console.print(
                                    f"  ({i}/{len(match_ids)}) "
                                    f"[green]{stats['analyzed']} kayıt[/green] · "
                                    f"[yellow]{stats['skipped']} atlandı[/yellow]"
                                )
                        except Exception as e:
                            stats["errors"] += 1
                            if _flag(verbose):
                                console.print(f"  [red]Hata [{mid}]: {e}[/red]")

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


@app.command("update-scores")
def update_scores_cmd(
    target_date: Optional[str] = typer.Option(None, "--date", help="YYYY-MM-DD. Boşsa bugün (gece 00-04 arası ise dün)."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """DB'deki maçların gerçek sonuçlarını günceller.

    Gece çalıştırılır: sabah pipeline ile kaydedilen maçları scrape edip
    actual_ft/ht skorlarını doldurur. Sonuçlar sayfasında görünür hale gelir.
    """
    _setup_logging("DEBUG" if _flag(verbose) else "INFO")

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
            f"[red]{stats['errors']} hata[/red]"
        )

    asyncio.run(_run())


@app.command("prune-non-league")
def prune_non_league_cmd(
    apply: bool = typer.Option(False, "--apply", help="Gerçekten soft-delete et (yoksa preview)"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Sprint 8.9 — DB'deki kupa/Avrupa/friendly maçlarını soft-delete et.

    Default dry-run: kaç maç temizleneceğinin preview'i. --apply ile gerçek silme.
    Soft delete (deleted_at SET) — geri alınabilir. Audit log'a kayıt düşer.
    """
    _setup_logging("DEBUG" if _flag(verbose) else "INFO")

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

        # Preview
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

        if not _flag(apply):
            console.print(f"\n[yellow]Dry-run modu: hiçbir şey değişmedi.[/yellow]")
            console.print(f"[dim]Gerçekten silmek için: prune-non-league --apply[/dim]")
            return

        # Apply: soft delete + audit log
        ts = datetime.now(timezone.utc)
        match_ids = [r.match_id for r in non_league]

        async with get_session() as session:
            await session.execute(
                sa_update(Match)
                .where(Match.match_id.in_(match_ids))
                .values(deleted_at=ts, deleted_reason="non_league")
            )
            # Audit log: tek toplu kayıt + her maç için ayrı satır
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


@app.command("restore-deleted")
def restore_deleted_cmd(
    match_id: str = typer.Argument(..., help="Geri alınacak match_id"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Sprint 8.9 — Soft-deleted bir maçı geri al."""
    _setup_logging("DEBUG" if _flag(verbose) else "INFO")
    from datetime import datetime, timezone
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


@app.command("audit-db")
def audit_db_cmd(
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Sprint 8.9 — DB sağlık raporu: aktif/silinmiş, eksik veri, kalite skoru."""
    _setup_logging("DEBUG" if _flag(verbose) else "WARNING")

    from datetime import datetime, timezone, timedelta
    from sqlalchemy import select, func, and_, or_
    from app.analysis.league_filter import is_supported_league
    from app.db.connection import get_session
    from app.db.models import Match

    async def _run() -> None:
        async with get_session() as session:
            total = (await session.execute(select(func.count(Match.id)))).scalar() or 0
            active = (await session.execute(
                select(func.count(Match.id)).where(Match.deleted_at.is_(None))
            )).scalar() or 0
            deleted = total - active

            # Aktif ama lig olmayan (yeni filtre sonrası 0 olmalı; öncesi varsa prune lazım)
            active_rows = (await session.execute(
                select(Match.match_id, Match.league_code, Match.league_name)
                .where(Match.deleted_at.is_(None))
            )).all()
            non_league_active = [
                r for r in active_rows
                if not is_supported_league(r.league_name, r.league_code)
            ]

            # Eksik pattern
            missing_pattern = (await session.execute(
                select(func.count(Match.id)).where(
                    Match.deleted_at.is_(None),
                    or_(Match.pattern_ft_b.is_(None), Match.pattern_ft_c.is_(None),
                        Match.pattern_ht_b.is_(None), Match.pattern_h2_b.is_(None)),
                )
            )).scalar() or 0

            # Eksik trends
            missing_trends = (await session.execute(
                select(func.count(Match.id)).where(
                    Match.deleted_at.is_(None), Match.trends.is_(None)
                )
            )).scalar() or 0

            # Eksik actual skor (kickoff +130dk geçmiş ama actual_ft NULL)
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=130)
            missing_actual = (await session.execute(
                select(func.count(Match.id)).where(
                    Match.deleted_at.is_(None),
                    Match.kickoff_time < cutoff,
                    Match.actual_ft_home.is_(None),
                )
            )).scalar() or 0

            # Aktivite
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

            # Pattern self-check (Madde 18) — aktif maçların pattern_ft_b'sinde
            # result_1+x+2 toplamı 100 değilse anomali
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
                if abs(total_pct - 100) > 1:  # 0.1 yuvarlama toleransı
                    pattern_anomalies.append((r.match_id, total_pct))

            # Quality score
            if total == 0:
                quality = 0.0
            else:
                penalties = (
                    (len(non_league_active) / total) * 40
                    + (missing_pattern / max(active, 1)) * 20
                    + (missing_actual / max(active, 1)) * 30
                    + (missing_trends / max(active, 1)) * 10
                )
                quality = max(0.0, 100.0 - penalties)

        # Render
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
        _row("Pattern eksik (en az bir kolon)", missing_pattern, ok_if_zero=False)
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

        # Quality skoru
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
        if pattern_anomalies:
            console.print(
                f"\n[yellow]Pattern anomalisi tespit edildi ({len(pattern_anomalies)} maç):[/yellow]"
            )
            for mid, total in pattern_anomalies[:5]:
                console.print(f"  [dim]{mid}: result_1+x+2 = {total:.1f}[/dim]")

    asyncio.run(_run())


@app.command("audit-patterns")
def audit_patterns_cmd(
    match_id: str = typer.Argument(..., help="Pattern davranışı raporlanacak match ID"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Sprint 8.9 — Bir maçın Pattern B/C eşleşme davranışını rapor et.

    Pattern B IY/2Y/MS sekmelerinde farklı eşleşme sayıları gösterir.
    Pattern C tek FT setiyle 3 periyot — tutarlılık varsayımını doğrular.
    """
    _setup_logging("DEBUG" if _flag(verbose) else "WARNING")

    from app.analysis.pattern_b import find_pattern_b_matches
    from app.analysis.pattern_c import find_pattern_c_all_periods

    async def _run() -> None:
        console.print(f"[cyan]Pattern audit başladı: {match_id}[/cyan]\n")
        raw = await fetch_match_detail(match_id)
        result = analyze_match(raw)

        # Pattern B her periyot ayrı
        b_results = {}
        for period_key, scores in [
            ("ht", (result.ht.scores_1, result.ht.scores_x, result.ht.scores_2)),
            ("h2", (result.half2.scores_1, result.half2.scores_x, result.half2.scores_2)),
            ("ft", (result.ft.scores_1, result.ft.scores_x, result.ft.scores_2)),
        ]:
            b = await find_pattern_b_matches(
                period_key, *scores, exclude_match_id=match_id
            )
            b_results[period_key] = b

        # Pattern C tek set
        c_ht, c_h2, c_ft = await find_pattern_c_all_periods(
            result.ft.all_ratios, exclude_match_id=match_id
        )

        # Tablo
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


@app.command("self-test")
def self_test_cmd(
    match_id: str = typer.Argument("2813084", help="Test edilecek match ID"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Sprint 8.9 — Sistem sağlık E2E testi: tek maç üzerinden tüm boru hattı.

    Adım adım kontrol: scrape → filtre → analiz → pattern → trends → DB write → roundtrip.
    """
    _setup_logging("DEBUG" if _flag(verbose) else "WARNING")

    from app.analysis.league_filter import is_supported_league
    from app.analysis.persist import compute_all_patterns
    from app.analysis.trends import compute_trends
    from app.pipeline.runner import _validate_row, _result_to_row

    async def _run() -> None:
        console.print(Panel.fit(
            f"[bold]Self-Test:[/bold] Match {match_id}",
            border_style="cyan",
        ))

        steps = []

        # 1. Scrape
        console.print("[1/7] Match detail çekiliyor...", end=" ")
        raw = await fetch_match_detail(match_id)
        console.print(f"[green]✓[/green] {raw.home_team} vs {raw.away_team} [{raw.league_code}]")

        # 2. Lig kontrolü
        console.print("[2/7] is_supported_league()...", end=" ")
        ok = is_supported_league(raw.league_name, raw.league_code)
        console.print(f"[green]✓[/green] = {ok}")
        if not ok:
            console.print("[red]Bu maç lig maçı değil — pipeline burada durur.[/red]")
            return

        # 3. Filter
        console.print("[3/7] check_match_filters()...", end=" ")
        check = check_match_filters(raw)
        if check.passed:
            console.print(f"[green]✓ PASSED[/green]")
        else:
            console.print(f"[yellow]✗ {check.reason.value}[/yellow] — {check.detail}")
            return

        # 4. Analyze
        console.print("[4/7] analyze_match() — Katman A...", end=" ")
        result = analyze_match(raw)
        a_count = (
            len(result.ft.scores_1) + len(result.ft.scores_x) + len(result.ft.scores_2)
        )
        console.print(f"[green]✓[/green] FT toplam {a_count} skor (3.5+ eşik)")

        # 5. Patterns
        console.print("[5/7] compute_all_patterns()...", end=" ")
        patterns = await compute_all_patterns(
            match_id=match_id,
            ht_scores=(result.ht.scores_1, result.ht.scores_x, result.ht.scores_2),
            h2_scores=(result.half2.scores_1, result.half2.scores_x, result.half2.scores_2),
            ft_scores=(result.ft.scores_1, result.ft.scores_x, result.ft.scores_2),
            ft_ratios=result.ft.all_ratios,
        )
        ft_b_count = (patterns["pattern_ft_b"] or {}).get("match_count", 0)
        ft_c_count = (patterns["pattern_ft_c"] or {}).get("match_count", 0)
        console.print(f"[green]✓[/green] B={ft_b_count}, C={ft_c_count}")

        # 6. Trends
        console.print("[6/7] compute_trends()...", end=" ")
        trends = compute_trends(raw)
        blocks_n = sum(1 for b in [trends.home_form, trends.away_form, trends.h2h] if b)
        console.print(f"[green]✓[/green] {blocks_n}/3 blok dolu")

        # 7. Row validation (DB write öncesi)
        console.print("[7/7] _validate_row() pre-write...", end=" ")
        row = _result_to_row(result, raw, patterns)
        ok, reason = _validate_row(row)
        if ok:
            console.print(f"[green]✓ DB write hazır[/green]")
        else:
            console.print(f"[red]✗ {reason}[/red]")

        # Davranış kanıtı
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


@app.command()
def version() -> None:
    from app import __version__

    console.print(f"nortverse [cyan]v{__version__}[/cyan]")


if __name__ == "__main__":
    app()
