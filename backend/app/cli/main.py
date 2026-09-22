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

import typer

from app.cli._helpers import console
from app.cli.archive_cmds import (
    build_archive_cmd,
    build_multi_archive_cmd,
    list_leagues_cmd,
    normalize_leagues_cmd,
    repair_archive_cmd,
)
from app.cli.audit_cmds import (
    audit_db_cmd,
    audit_patterns_cmd,
    prune_non_league_cmd,
    recompute_patterns_cmd,
    restore_deleted_cmd,
    self_test_cmd,
)
from app.cli.pipeline_cmds import (
    analyze,
    analyze_debug,
    capture_recommendations_cmd,
    capture_score_snapshots_cmd,
    fetch_and_analyze_cmd,
    fetch_fixture_cmd,
    refresh_fixture_cache_cmd,
    run_pipeline_cmd,
    serve,
    update_scores_cmd,
)

app = typer.Typer(help="Nortverse - futbol tahmin sistemi CLI", no_args_is_help=True)

# --- Pipeline / Analiz ---
app.command()(analyze)
app.command("analyze-debug")(analyze_debug)
app.command("fetch-fixture")(fetch_fixture_cmd)
app.command("fetch-and-analyze")(fetch_and_analyze_cmd)
app.command("run-pipeline")(run_pipeline_cmd)
app.command("capture-score-snapshots")(capture_score_snapshots_cmd)
app.command("capture-recommendations")(capture_recommendations_cmd)
app.command("refresh-fixture-cache")(refresh_fixture_cache_cmd)
app.command("update-scores")(update_scores_cmd)
app.command()(serve)

# --- Arşiv / Onarım ---
app.command("build-archive")(build_archive_cmd)
app.command("build-multi-archive")(build_multi_archive_cmd)
app.command("list-leagues")(list_leagues_cmd)
app.command("repair-archive")(repair_archive_cmd)
app.command("normalize-leagues")(normalize_leagues_cmd)

# --- Audit / Bakım ---
app.command("prune-non-league")(prune_non_league_cmd)
app.command("restore-deleted")(restore_deleted_cmd)
app.command("audit-db")(audit_db_cmd)
app.command("audit-patterns")(audit_patterns_cmd)
app.command("recompute-patterns")(recompute_patterns_cmd)
app.command("self-test")(self_test_cmd)


@app.command()
def version() -> None:
    """Versiyon bilgisi."""
    from app import __version__

    console.print(f"nortverse [cyan]v{__version__}[/cyan]")


if __name__ == "__main__":
    app()
