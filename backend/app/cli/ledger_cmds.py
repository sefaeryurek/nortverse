"""Tahmin defteri komutları: canlı dondurma denemesi ve sızıntısız backtest."""

import asyncio
from typing import Optional

import typer
from rich.table import Table

from app.cli._helpers import _setup_logging, console

_STATUS_TEXT = {
    "frozen": "[green]kaydedildi[/green]",
    "dry_run": "[cyan]kaydedilirdi (deneme)[/cyan]",
    "already_frozen": "zaten kayıtlı",
    "late_score_changed": "[yellow]2. yarıda skor değişmiş — kaydedilmez[/yellow]",
    "no_ht": "henüz devre arası değil",
    "not_started": "başlamadı",
    "not_live": "canlı listede yok",
    "no_snapshot": "[red]canlı skor kaynağına ulaşılamadı[/red]",
    "error": "[red]hata (log'a bakın)[/red]",
}


def _prediction_text(prediction: dict | None) -> str:
    if not prediction:
        return "—"
    ms = prediction["ms"]
    extra = [f"{key} {block['pick']} %{block['prob'] * 100:.0f}"
             for key, block in (("Ü2.5", prediction["over25"]), ("KG", prediction["btts"]))
             if block.get("applicable")]
    base = ms["ht_baseline"]
    return (f"MS {ms['pick']} %{ms['prob'] * 100:.1f} · {ms['tier']} · n={ms['n']} ({ms['cond_level']})"
            f" · İY tabanı {base['pick']} %{base['prob'] * 100:.1f}"
            + (f" · {' · '.join(extra)}" if extra else ""))


def live_freeze_cmd(
    match_id: Optional[str] = typer.Option(None, "--match", help="Tek maç için tahmini göster (yazmaz)"),
    ht: Optional[str] = typer.Option(None, "--ht", help="--match ile varsayılan İY skoru, örn. 1-0"),
    apply: bool = typer.Option(False, "--apply", help="İzleyicinin bir turunu gerçekten çalıştır (deftere yazar)"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Canlı İY→MS dondurma denemesi — varsayılan sadece gösterir, hiçbir şey yazmaz.

    Argümansız: şu an devre arasındaki maçlar için izleyicinin ne yapacağını listeler.
    --apply: aynı turu gerçekten çalıştırır (backend kapalıyken kaçırılan devre aralarını yakalar).
    --match ID --ht 1-0: o maç o İY skoruyla bitseydi tahmin ne olurdu (asla yazmaz).
    """
    _setup_logging("DEBUG" if verbose else "WARNING")

    if match_id is not None:
        if apply:
            console.print("[red]--match ile --apply kullanılamaz: elle verilen İY skoru gerçek kayıt olamaz.[/red]")
            raise typer.Exit(1)
        try:
            ht_home, ht_away = (int(x) for x in (ht or "").split("-"))
            if not (0 <= ht_home <= 30 and 0 <= ht_away <= 30):
                raise ValueError
        except ValueError:
            console.print("[red]--ht biçimi: EV-DEP, örn. 1-0[/red]")
            raise typer.Exit(1)

    async def _single() -> None:
        from sqlalchemy import select
        from app.analysis.live_model import get_cond_table, predict_live
        from app.db.connection import get_session
        from app.db.models import Match

        async with get_session() as session:
            match = (await session.execute(
                select(Match).where(Match.match_id == match_id, Match.deleted_at.is_(None))
            )).scalar_one_or_none()
        if match is None:
            console.print(f"[red]Maç bulunamadı: {match_id}[/red]")
            raise typer.Exit(1)
        prediction = predict_live(
            await get_cond_table(), match.league_name or "", (ht_home, ht_away),
            [match.pattern_ft_b, match.pattern_ft_c, match.pattern_ft_d],
        )
        console.print(f"[bold]{match.home_team} - {match.away_team}[/bold] · {match.league_name} · İY {ht}")
        console.print(f"  {_prediction_text(prediction)}")
        ms = prediction["ms"]
        console.print("  Olasılıklar: " + " · ".join(f"{o} %{p * 100:.1f}" for o, p in ms["probs"].items()))
        if ms["prematch"]:
            console.print(f"  Maç öncesi arşiv havuzu: n={ms['prematch']['pooled_n']} · "
                          + " · ".join(f"{o} %{p * 100:.1f}" for o, p in ms["prematch"]["probs"].items()))
        else:
            console.print("  Maç öncesi arşiv görüşü yok — sadece İY koşullu dağılım kullanıldı.")
        from app.analysis import live_archive, live_poisson

        ht_pair = (ht_home, ht_away)
        table = await get_cond_table()
        view = await live_archive.load_view(
            match.match_id, {"b": match.pattern_ft_b, "c": match.pattern_ft_c, "d": match.pattern_ft_d},
            ht_pair, league=match.league_name or "", table=table)
        console.print(f"  Kararlar ({live_archive.LIVE_ARCHIVE_RULE_VERSION}): " + (", ".join(
            f"{h['period']}·{h['market']} {h['selection']} %{h['pct']} (lig {h['cond_n']} maç, arşiv "
            f"{'+'.join(h['sources'])} %{h['archive_pct']})" for h in view["highlights"]) or "yok"))
        poisson = live_poisson.predict(await live_poisson.get_poisson_model(), match.league_name or "",
                                       match.home_team, match.away_team, ht_pair)
        picks = live_poisson.decisions(poisson, live_poisson.cond_lookup(table, match.league_name or "", ht_pair))
        console.print(f"  Gölge {live_poisson.LIVE_POISSON_RULE_VERSION}: " + (", ".join(
            f"{p['period']}·{p['market']} {p['selection']} %{p['pct']}{' ★' if p['best'] else ''}"
            f"{' (değerli)' if p['valuable'] else ''}" for p in picks) or "yok"))
        from app.analysis import live_2h

        dist = live_poisson.final_grid(await live_poisson.get_poisson_model(), match.league_name or "",
                                       match.home_team, match.away_team, ht_pair)
        h2 = live_2h.decide(dist["grid"] if dist else None, ht_pair,
                            live_2h.cond_lookup(table, match.league_name or "", ht_pair))
        console.print(f"  Gölge {live_2h.LIVE_2H_RULE_VERSION}: " + (", ".join(
            f"{p['period']}·{p['market']} {p['selection']} %{p['pct']} ({p['kind']}"
            f"{', zaten neredeyse kesin' if p['trivial'] else ''})" for p in h2) or "yok"))
        console.print("[dim]Deneme: deftere hiçbir şey yazılmadı.[/dim]")

    async def _tick() -> None:
        from app.api.live_ledger import WINDOW_END, WINDOW_START, run_tick
        from app.api.live_snapshot import refresh_live_snapshot

        snapshot = await refresh_live_snapshot()
        report = await run_tick(dry_run=not apply, snapshot=snapshot)
        if not report:
            console.print(
                f"Şu an izleme penceresinde maç yok (başlama saati {int(WINDOW_START.total_seconds() // 60)}–"
                f"{int(WINDOW_END.total_seconds() // 60)} dk önce olan analizli maçlar)."
            )
            return
        table = Table(title="Canlı İY→MS dondurma " + ("(GERÇEK)" if apply else "(deneme — yazılmaz)"))
        for col in ("Maç", "Durum", "Skor", "Karar", "Tahmin"):
            table.add_column(col)
        for entry in report:
            match, fs = entry["match"], entry["score"]
            score = "—" if fs is None else (
                f"{fs.home}-{fs.away} ({fs.phase or fs.minute or '?'})"
                + (f" · İY {fs.ht_home}-{fs.ht_away}" if fs.ht_home is not None else "")
            )
            table.add_row(
                f"{match.home_team} - {match.away_team}\n[dim]{match.match_id} · {match.league_name}[/dim]",
                fs.status if fs else "—", score,
                _STATUS_TEXT.get(entry["status"], entry["status"]), _prediction_text(entry["prediction"]),
            )
        console.print(table)
        if not apply:
            console.print("[dim]Deneme: deftere hiçbir şey yazılmadı. Gerçekten kaydetmek için --apply.[/dim]")

    asyncio.run(_single() if match_id is not None else _tick())


def backtest_ledger_cmd(
    strategy: str = typer.Option("live_ht", "--strategy", help="live_ht | live_archive | live_poisson | live_2h | top_pick | top_pick_v5 | market_summary"),
    from_date: str = typer.Option(..., "--from", help="Başlangıç (YYYY-MM-DD)"),
    to_date: str = typer.Option(..., "--to", help="Bitiş, hariç (YYYY-MM-DD)"),
    alpha: float = typer.Option(0.5, "--alpha", help="Maç öncesi LR üssü (live_model.ALPHA)"),
    notes: Optional[str] = typer.Option(None, "--notes"),
    replace_run: Optional[int] = typer.Option(None, "--replace-run", help="Bu koşuyu silip yeniden üret"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Sızıntısız backtest — sonuçlar prediction_backtest'e yazılır (gerçek defterle karışmaz)."""
    _setup_logging("DEBUG" if verbose else "INFO")
    from datetime import datetime
    from app.analysis.backtest import (
        load_backtest_rows, ms_brier_report, run_live_archive_backtest, run_live_backtest,
        run_live_2h_backtest, run_live_poisson_backtest, run_prematch_backtest, run_prematch_v5_backtest,
    )
    from app.analysis.performance import group_summaries, summarize
    from app.config import ISTANBUL_TZ

    if strategy not in ("live_ht", "live_archive", "live_poisson", "live_2h", "top_pick", "top_pick_v5",
                        "market_summary"):
        console.print("[red]--strategy: live_ht | live_archive | live_poisson | live_2h | top_pick | top_pick_v5 | "
                      "market_summary[/red]")
        raise typer.Exit(1)
    start = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=ISTANBUL_TZ)
    end = datetime.strptime(to_date, "%Y-%m-%d").replace(tzinfo=ISTANBUL_TZ)

    def _line(label: str, s: dict) -> None:
        lift = "—" if s["lift_pct"] is None else f"{s['lift_pct']:+.1f}"
        console.print(
            f"  {label:<22} n={s['resolved']:>5}  isabet=%{s['hit_pct'] or 0:5.1f}  "
            f"[%{s['ci_low'] or 0:.1f}–{s['ci_high'] or 0:.1f}]  ort.olasılık=%{s['avg_prob_pct'] or 0:5.1f}  "
            f"taban=%{s['baseline_hit_pct'] or 0:5.1f}  fark={lift}"
        )

    async def _run() -> None:
        if strategy == "live_archive":
            run_id = await run_live_archive_backtest(start, end, notes=notes, replace_run=replace_run)
            title = f"Canlı arşiv (%85+) backtest #{run_id} ({from_date} → {to_date})"
        elif strategy == "top_pick_v5":
            run_id = await run_prematch_v5_backtest(start, end, notes=notes, replace_run=replace_run)
            title = f"Maç öncesi v5 (Dixon-Coles) backtest #{run_id} ({from_date} → {to_date})"
        elif strategy == "live_poisson":
            run_id = await run_live_poisson_backtest(start, end, notes=notes, replace_run=replace_run)
            title = f"Canlı Poisson (gölge, %85+) backtest #{run_id} ({from_date} → {to_date})"
        elif strategy == "live_2h":
            run_id = await run_live_2h_backtest(start, end, notes=notes, replace_run=replace_run)
            title = f"Canlı 2. yarı (gölge: güvenli alt ≥%85, gol ≥%70) backtest #{run_id} ({from_date} → {to_date})"
        elif strategy == "live_ht":
            run_id = await run_live_backtest(start, end, notes=notes, alpha=alpha, replace_run=replace_run)
            title = f"Canlı İY→MS backtest #{run_id} ({from_date} → {to_date}, α={alpha})"
        else:
            run_id = await run_prematch_backtest(strategy, start, end, notes=notes, replace_run=replace_run)
            title = f"Maç öncesi backtest #{run_id} · {strategy} ({from_date} → {to_date})"
        rows = await load_backtest_rows(run_id)
        brier = ms_brier_report(rows)
        console.print(f"\n[bold cyan]{title}[/bold cyan]")
        breakdown = "archive" if strategy in ("market_summary", "live_archive") else "tier"
        for period in ("ht", "h2", "ft"):
            for market in sorted({r["market"] for r in rows if r["period"] == period}):
                market_rows = [r for r in rows if r["market"] == market and r["period"] == period]
                _line(f"{period}·{market}", summarize(market_rows))
                for group in group_summaries(market_rows, breakdown):
                    _line(f"  · {group['key']}", group)
        if brier["brier"] is not None:
            console.print(
                f"\n  MS çok sınıflı Brier: model {brier['brier']:.4f} · İY tabanı {brier['baseline_brier']:.4f} "
                "(düşük daha iyi)"
            )

    asyncio.run(_run())
