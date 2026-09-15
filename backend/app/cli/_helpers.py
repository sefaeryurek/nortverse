"""CLI ortak yardımcılar — tüm komut modüllerinin kullandığı araçlar."""

import logging
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table

from app.analysis.pattern_stats import PatternResult
from app.analysis.scores import MS1_SCORES, MSX_SCORES, MS2_SCORES
from app.models import MatchAnalysisResult, MatchRawData, Period, PeriodAnalysis

console = Console()
DEBUG_DIR = Path("debug")


def _setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=False)],
    )


def _make_recording_console() -> Console:
    return Console(record=True)


def _save_text(content: str, filename: str) -> Path:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    path = DEBUG_DIR / filename
    path.write_text(content, encoding="utf-8")
    return path


def _render_period(label: str, pa: PeriodAnalysis, con: Console) -> Table:
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
