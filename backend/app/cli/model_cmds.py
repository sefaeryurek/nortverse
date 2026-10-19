"""Model/değerlendirme komutları: pattern backtest'i ve ensemble eğitimi."""

import asyncio

import typer
from rich.panel import Panel
from rich.table import Table

from app.analysis.league_priors import istanbul_day_start, load_prior_book
from app.cli._helpers import _setup_logging, console


def backtest_cmd(
    from_date: str = typer.Option(..., "--from", help="Başlangıç tarihi (YYYY-MM-DD)"),
    to_date: str = typer.Option(..., "--to", help="Bitiş tarihi (YYYY-MM-DD)"),
    min_matches: int = typer.Option(5, "--min-matches", help="Pattern en az N eşleşme"),
    ensemble_model: str = typer.Option("models/ensemble.joblib", "--ensemble", help="Ensemble model dosyası"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Tarih aralığında değerlendirme — strateji değişikliklerinin etkisini ölç."""
    _setup_logging("DEBUG" if verbose else "WARNING")

    from datetime import date, datetime, timedelta
    from pathlib import Path
    from sqlalchemy import select
    from app.analysis.evaluation import (
        EvalAccumulator,
        evaluate_pattern,
        pct,
        brier_avg,
    )
    from app.analysis.ensemble import load_models, predict
    from app.config import ISTANBUL_TZ
    from app.db.connection import get_session
    from app.db.models import Match

    try:
        d_from = date.fromisoformat(from_date)
        d_to = date.fromisoformat(to_date)
    except ValueError:
        console.print("[red]Geçersiz tarih formatı. Kullanım: YYYY-MM-DD[/red]")
        raise typer.Exit(1)

    if d_from > d_to:
        console.print("[red]--from tarihi --to'dan sonra olamaz.[/red]")
        raise typer.Exit(1)

    async def _run() -> None:
        start = datetime(d_from.year, d_from.month, d_from.day, tzinfo=ISTANBUL_TZ)
        end = datetime(d_to.year, d_to.month, d_to.day, tzinfo=ISTANBUL_TZ) + timedelta(days=1)

        async with get_session() as session:
            stmt = (
                select(
                    Match.match_id, Match.league_name, Match.kickoff_time,
                    Match.actual_ft_home, Match.actual_ft_away,
                    Match.pattern_ft_b, Match.pattern_ft_c, Match.pattern_ft_d,
                    Match.ft_scores_1, Match.ft_scores_x, Match.ft_scores_2,
                )
                .where(
                    Match.deleted_at.is_(None),
                    Match.kickoff_time >= start,
                    Match.kickoff_time < end,
                    Match.actual_ft_home.isnot(None),
                    Match.actual_ft_away.isnot(None),
                )
                .order_by(Match.kickoff_time)
            )
            rows = (await session.execute(stmt)).all()

        if not rows:
            console.print(f"[yellow]{d_from} — {d_to} aralığında bitmiş maç yok.[/yellow]")
            return

        ens_models = load_models(Path(ensemble_model))
        if ens_models:
            console.print(f"[green]Ensemble model yüklendi: {ensemble_model} ({ens_models.training_size} maç ile eğitilmiş)[/green]")
        else:
            console.print(f"[dim]Ensemble model bulunamadı: {ensemble_model} (sadece B/C/D ayrı gösterilecek)[/dim]")

        acc_b, acc_c, acc_d = EvalAccumulator(), EvalAccumulator(), EvalAccumulator()
        acc_ens = EvalAccumulator()
        total_matches = 0
        score_list_hit = 0

        for row in rows:
            ft_h, ft_a = row.actual_ft_home, row.actual_ft_away
            if ft_h > ft_a:
                actual_result = "1"
            elif ft_h == ft_a:
                actual_result = "X"
            else:
                actual_result = "2"

            actual_over_25 = (ft_h + ft_a) > 2
            actual_btts = ft_h > 0 and ft_a > 0

            priors = await load_prior_book(istanbul_day_start(row.kickoff_time))
            eval_kwargs = dict(
                actual_result=actual_result, actual_over_25=actual_over_25,
                actual_btts=actual_btts, min_matches=min_matches,
                league_name=row.league_name, priors=priors,
            )
            pat_b = evaluate_pattern(row.pattern_ft_b, **eval_kwargs)
            pat_c = evaluate_pattern(row.pattern_ft_c, **eval_kwargs)
            pat_d = evaluate_pattern(row.pattern_ft_d, **eval_kwargs)

            acc_b.accumulate(pat_b)
            acc_c.accumulate(pat_c)
            acc_d.accumulate(pat_d)

            if ens_models:
                from app.analysis.evaluation import PatternEval
                ens_pred = predict(ens_models, row.pattern_ft_b, row.pattern_ft_c, row.pattern_ft_d,
                                   row.league_name, base_rates=priors.rates(row.league_name))
                ens_result_hit = ens_pred.result_pick == actual_result
                ens_over_hit = (ens_pred.over_25_pick == "over") == actual_over_25
                ens_btts_hit = (ens_pred.btts_pick == "yes") == actual_btts
                ens_brier = sum(
                    (ens_pred.result_probs.get(k, 33.3) / 100.0 - (1.0 if k == actual_result else 0.0)) ** 2
                    for k in ("1", "X", "2")
                )
                ens_eval = PatternEval(
                    match_count=0, result_pick=ens_pred.result_pick,
                    result_pct=ens_pred.result_probs.get(ens_pred.result_pick, 0),
                    result_hit=ens_result_hit, result_margin=ens_pred.result_margin,
                    is_confident=ens_pred.is_confident,
                    over_25_pick=ens_pred.over_25_pick, over_25_pct=ens_pred.over_25_prob,
                    over_25_hit=ens_over_hit,
                    btts_pick=ens_pred.btts_pick, btts_pct=ens_pred.btts_prob,
                    btts_hit=ens_btts_hit, brier_score=round(ens_brier, 4),
                )
                acc_ens.accumulate(ens_eval)

            all_scores = (
                list(row.ft_scores_1 or [])
                + list(row.ft_scores_x or [])
                + list(row.ft_scores_2 or [])
            )
            if f"{ft_h}-{ft_a}" in all_scores:
                score_list_hit += 1
            total_matches += 1

        console.print(Panel.fit(
            f"[bold]Backtest Sonuçları[/bold]\n"
            f"Tarih aralığı: {d_from} → {d_to}\n"
            f"Toplam maç: {total_matches:,} · min_matches={min_matches}",
            border_style="cyan",
        ))

        t = Table(title="Pattern Performansı")
        t.add_column("Metrik", style="white")
        t.add_column("A1 (Pattern B)", style="cyan", justify="right")
        t.add_column("A2 (Pattern C)", style="green", justify="right")
        t.add_column("A3 (Pattern D)", style="yellow", justify="right")
        if ens_models:
            t.add_column("Ensemble", style="magenta", justify="right")

        def _ens_col(field: str) -> str:
            if not ens_models:
                return ""
            v = getattr(acc_ens, field)
            return str(v)

        t.add_row("Değerlendirilen", str(acc_b.evaluated), str(acc_c.evaluated), str(acc_d.evaluated),
                   *([str(acc_ens.evaluated)] if ens_models else []))
        t.add_row(
            "MS İsabet",
            f"{acc_b.result_hit} ({pct(acc_b.result_hit, acc_b.evaluated):.1f}%)",
            f"{acc_c.result_hit} ({pct(acc_c.result_hit, acc_c.evaluated):.1f}%)",
            f"{acc_d.result_hit} ({pct(acc_d.result_hit, acc_d.evaluated):.1f}%)",
            *([f"{acc_ens.result_hit} ({pct(acc_ens.result_hit, acc_ens.evaluated):.1f}%)"] if ens_models else []),
        )
        t.add_row(
            "Üst/Alt İsabet",
            f"{acc_b.over_hit} ({pct(acc_b.over_hit, acc_b.evaluated):.1f}%)",
            f"{acc_c.over_hit} ({pct(acc_c.over_hit, acc_c.evaluated):.1f}%)",
            f"{acc_d.over_hit} ({pct(acc_d.over_hit, acc_d.evaluated):.1f}%)",
            *([f"{acc_ens.over_hit} ({pct(acc_ens.over_hit, acc_ens.evaluated):.1f}%)"] if ens_models else []),
        )
        t.add_row(
            "KG İsabet",
            f"{acc_b.btts_hit} ({pct(acc_b.btts_hit, acc_b.evaluated):.1f}%)",
            f"{acc_c.btts_hit} ({pct(acc_c.btts_hit, acc_c.evaluated):.1f}%)",
            f"{acc_d.btts_hit} ({pct(acc_d.btts_hit, acc_d.evaluated):.1f}%)",
            *([f"{acc_ens.btts_hit} ({pct(acc_ens.btts_hit, acc_ens.evaluated):.1f}%)"] if ens_models else []),
        )
        t.add_row(
            "Güvenli MS",
            f"{acc_b.confident_result_hit}/{acc_b.confident_evaluated} ({pct(acc_b.confident_result_hit, acc_b.confident_evaluated):.1f}%)",
            f"{acc_c.confident_result_hit}/{acc_c.confident_evaluated} ({pct(acc_c.confident_result_hit, acc_c.confident_evaluated):.1f}%)",
            f"{acc_d.confident_result_hit}/{acc_d.confident_evaluated} ({pct(acc_d.confident_result_hit, acc_d.confident_evaluated):.1f}%)",
            *([f"{acc_ens.confident_result_hit}/{acc_ens.confident_evaluated} ({pct(acc_ens.confident_result_hit, acc_ens.confident_evaluated):.1f}%)"] if ens_models else []),
        )
        b_brier = brier_avg(acc_b.brier_sum, acc_b.evaluated)
        c_brier = brier_avg(acc_c.brier_sum, acc_c.evaluated)
        d_brier = brier_avg(acc_d.brier_sum, acc_d.evaluated)
        ens_brier = brier_avg(acc_ens.brier_sum, acc_ens.evaluated) if ens_models else None
        t.add_row(
            "Brier Skoru",
            f"{b_brier:.4f}" if b_brier is not None else "—",
            f"{c_brier:.4f}" if c_brier is not None else "—",
            f"{d_brier:.4f}" if d_brier is not None else "—",
            *([f"{ens_brier:.4f}" if ens_brier is not None else "—"] if ens_models else []),
        )
        t.add_row(
            "Skor Listesi İsabet",
            f"{score_list_hit}/{total_matches} ({pct(score_list_hit, total_matches):.1f}%)",
            "", "",
            *([""] if ens_models else []),
        )
        console.print(t)

    asyncio.run(_run())


def train_ensemble_cmd(
    from_date: str = typer.Option(..., "--from", help="Eğitim başlangıç tarihi (YYYY-MM-DD)"),
    to_date: str = typer.Option(..., "--to", help="Eğitim bitiş tarihi (YYYY-MM-DD)"),
    min_matches: int = typer.Option(5, "--min-matches", help="Pattern en az N eşleşme"),
    output: str = typer.Option("models/ensemble.joblib", "--output", "-o", help="Model dosya yolu"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """B+C+D pattern yüzdelerinden ensemble meta-model eğit."""
    _setup_logging("DEBUG" if verbose else "INFO")

    from datetime import date, datetime, timedelta
    from pathlib import Path
    from sqlalchemy import select
    from app.analysis.ensemble import train_ensemble, save_models
    from app.config import ISTANBUL_TZ
    from app.db.connection import get_session
    from app.db.models import Match

    try:
        d_from = date.fromisoformat(from_date)
        d_to = date.fromisoformat(to_date)
    except ValueError:
        console.print("[red]Geçersiz tarih formatı. Kullanım: YYYY-MM-DD[/red]")
        raise typer.Exit(1)

    if d_from > d_to:
        console.print("[red]--from tarihi --to'dan sonra olamaz.[/red]")
        raise typer.Exit(1)

    async def _run() -> None:
        start = datetime(d_from.year, d_from.month, d_from.day, tzinfo=ISTANBUL_TZ)
        end = datetime(d_to.year, d_to.month, d_to.day, tzinfo=ISTANBUL_TZ) + timedelta(days=1)

        async with get_session() as session:
            stmt = (
                select(
                    Match.match_id, Match.league_name, Match.kickoff_time,
                    Match.actual_ft_home, Match.actual_ft_away,
                    Match.pattern_ft_b, Match.pattern_ft_c, Match.pattern_ft_d,
                )
                .where(
                    Match.deleted_at.is_(None),
                    Match.kickoff_time >= start,
                    Match.kickoff_time < end,
                    Match.actual_ft_home.isnot(None),
                    Match.actual_ft_away.isnot(None),
                )
                .order_by(Match.kickoff_time)
            )
            rows = (await session.execute(stmt)).all()

        if not rows:
            console.print(f"[yellow]{d_from} — {d_to} aralığında bitmiş maç yok.[/yellow]")
            return

        training_data = []
        for row in rows:
            ft_h, ft_a = row.actual_ft_home, row.actual_ft_away
            if ft_h > ft_a:
                actual_result = "1"
            elif ft_h == ft_a:
                actual_result = "X"
            else:
                actual_result = "2"

            training_data.append({
                "pattern_ft_b": row.pattern_ft_b,
                "pattern_ft_c": row.pattern_ft_c,
                "pattern_ft_d": row.pattern_ft_d,
                "actual_result": actual_result,
                "actual_over_25": (ft_h + ft_a) > 2,
                "actual_btts": ft_h > 0 and ft_a > 0,
                "league_name": row.league_name,
                "base_rates": (await load_prior_book(istanbul_day_start(row.kickoff_time))).rates(row.league_name),
            })

        console.print(f"[cyan]Eğitim verisi: {len(training_data)} maç ({d_from} → {d_to})[/cyan]")

        try:
            models = train_ensemble(training_data, min_patterns=2)
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1)

        model_path = Path(output)
        save_models(models, model_path)
        console.print(f"[green]Model kaydedildi: {model_path} ({models.training_size} maç ile eğitildi)[/green]")

    asyncio.run(_run())


def backfill_team_lambdas_cmd(
    all_matches: bool = typer.Option(False, "--all", help="Saklı λ'ları da yeniden hesapla (varsayılan: sadece eksikler)"),
) -> None:
    """Maç öncesi takım gücü beklentilerini (λ ev/dep) doldurur — A3 bu uzayda en yakın maçları bulur.

    Her maç kendi başlama haftasının başında kurulmuş modelle hesaplanır (sızıntısız).
    """
    _setup_logging("INFO")
    from app.analysis.live_poisson import backfill_team_lambdas

    stats = asyncio.run(backfill_team_lambdas(only_missing=not all_matches))
    console.print(f"[green]Takım gücü λ:[/green] {stats['written']} maç yazıldı · "
                  f"{stats['no_model']} maçta lig modeli yok (yetersiz geçmiş) · hedef {stats['targets']}")
