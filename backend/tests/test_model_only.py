"""Yalnız model maçları (Sprint 94 P1, K15): H2H <5 takip maçı → takım gücü + gölge kayıtlar, havuzlara girmez."""

import inspect
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.analysis import performance
from app.analysis import prematch_v5 as v5
from app.analysis.live_poisson import LeagueModel, PoissonModel
from app.api import live_ledger
from app.models import MatchRawData
from app.pipeline import runner
from app.scraper.fixture_scores import FixtureScore

LEAGUE = "English Premier League"


def _raw(**kw):
    base = dict(match_id="777", home_team="Coventry", away_team="Fulham", league_code="ENG PR",
                league_name=LEAGUE, kickoff_time=datetime.now(timezone.utc) + timedelta(hours=20))
    base.update(kw)
    return MatchRawData(**base)


def test_model_only_row_has_no_layer_a_or_archives():
    row = runner._model_only_row(_raw(), datetime.now(timezone.utc))
    assert row["model_only"] is True
    assert row["league_name"] == row["league_code"] == LEAGUE
    for key in ("ft_scores_1", "ft_all_ratios", "pattern_ft_b", "pattern_ft_d", "trends", "pattern_computed_at"):
        assert key not in row
    assert runner._validate_row(row) == (True, None)


def test_full_analysis_clears_model_only_flag():
    """Tam analiz (H2H sonradan yeterli olursa) yalnız model satırının yerini alır."""
    from tests.test_runner import _result

    assert runner._result_to_row(_result())["model_only"] is False


def _model() -> PoissonModel:
    lm = LeagueModel(mu=0.25, home_adv=0.2, rho=-0.05, attack={"Coventry": 0.5, "Fulham": -0.4},
                     defense={"Coventry": 0.3, "Fulham": -0.3}, n=900)
    return PoissonModel(as_of=datetime.now(timezone.utc), leagues={LEAGUE: lm})


def _patch_capture(monkeypatch, *, started=None):
    import app.analysis.ledger as ledger
    import app.analysis.live_model as live_model
    import app.analysis.live_poisson as live_poisson
    import app.analysis.prematch_v4 as prematch_v4

    prior = {"1": 0.45, "X": 0.25, "2": 0.30}
    monkeypatch.setattr(live_model, "get_cond_table",
                        AsyncMock(return_value=SimpleNamespace(league_prior=lambda _l: prior)))
    monkeypatch.setattr(live_poisson, "get_poisson_model", AsyncMock(return_value=_model()))
    monkeypatch.setattr(prematch_v4, "match_already_started", AsyncMock(return_value=started))
    written: list = []

    async def record(_session, rows):
        written.extend(rows)
        return len(rows)

    monkeypatch.setattr(ledger, "record_predictions", record)
    return written


@pytest.mark.asyncio
async def test_capture_model_only_writes_only_v51_shadow(monkeypatch):
    written = _patch_capture(monkeypatch)
    now = datetime.now(timezone.utc)
    n = await v5.capture_model_only(object(), match_id="777", captured_at=now, kickoff_time=now + timedelta(hours=5),
                                    league=LEAGUE, home="Coventry", away="Fulham")
    assert n == 1
    (row,) = written
    assert row["rule_version"] == v5.V51_SHADOW_VERSION and row["selection"] == "1"
    assert row["details"]["model_only"] is True and row["details"]["shadow"] is True
    assert row["pattern_hash"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("hours,league,started", [
    (60, LEAGUE, None),                     # 48 saat ufkundan erken
    (-1, LEAGUE, None),                     # başlamış (saat geçmiş)
    (5, "Kenya Premier League", None),      # takip edilmeyen lig
    (5, LEAGUE, "source_started"),          # kaynakta başlamış görünüyor
])
async def test_capture_model_only_guards(monkeypatch, hours, league, started):
    written = _patch_capture(monkeypatch, started=started)
    now = datetime.now(timezone.utc)
    n = await v5.capture_model_only(object(), match_id="777", captured_at=now,
                                    kickoff_time=now + timedelta(hours=hours), league=league,
                                    home="Coventry", away="Fulham")
    assert n == 0 and written == []


# ─── Canlı izleyici: yalnız model maçında ekrandaki sürümler yazılmaz ────────────────────────────────────────

def _live_capture(monkeypatch):
    from app.analysis.live_model import CondTable

    table = CondTable(cutoff=datetime.now(timezone.utc), prior_from=datetime.now(timezone.utc) - timedelta(days=900))
    monkeypatch.setattr(live_ledger, "get_cond_table", AsyncMock(return_value=table))
    picks = [{"period": "ft", "market": "dc", "selection": "1X", "pct": 91.0, "cond_pct": 90.0, "cond_n": 40,
              "best": True, "valuable": False}]
    monkeypatch.setattr(live_ledger, "_poisson_shadow", AsyncMock(return_value=({"lambda": 1}, picks)))
    monkeypatch.setattr(live_ledger, "_live_2h_shadow", AsyncMock(return_value=([], None, [])))
    monkeypatch.setattr(live_ledger.live_archive, "load_view",
                        AsyncMock(side_effect=AssertionError("yalnız model maçında arşiv görünümü açılmaz")))
    monkeypatch.setattr(live_ledger.live_poisson, "cond_lookup", lambda *_a: {})
    monkeypatch.setattr(live_ledger.live_poisson, "decisions", lambda *_a: picks)
    monkeypatch.setattr(live_ledger.live_cond_filter, "warnings", lambda *_a: [])
    monkeypatch.setattr(
        live_ledger.live_poisson, "ledger_rows",
        lambda pred, p, common, late=False, shadow=False: [
            {**common, "rule_version": "live-poisson-v1.2" if shadow else "live-poisson-v1.1", "period": "ft",
             "details": {"shadow": shadow}}])
    monkeypatch.setattr(live_ledger, "market_snapshot", AsyncMock(return_value=None))
    monkeypatch.setattr(live_ledger, "_ht_observation_id", AsyncMock(return_value=11))
    written: list = []

    async def record(_session, rows):
        written.extend(rows)
        return len(rows)

    monkeypatch.setattr(live_ledger, "record_predictions", record)

    @asynccontextmanager
    async def fake_session():
        yield object()

    monkeypatch.setattr(live_ledger, "get_session", fake_session)
    return written


def _live_match(**kw):
    base = dict(match_id="777", league_name=LEAGUE, league_code=LEAGUE, home_team="Coventry", away_team="Fulham",
                kickoff_time=datetime.now(timezone.utc) - timedelta(minutes=50), pattern_ft_b=None,
                pattern_ft_c=None, pattern_ft_d=None, pattern_b_hash=None, pattern_c_hash=None,
                pattern_d_hash=None, model_only=True)
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.mark.asyncio
async def test_live_freeze_model_only_writes_only_shadow_versions(monkeypatch):
    written = _live_capture(monkeypatch)
    fs = FixtureScore("777", "live", 1, 0, minute="HT")
    assert await live_ledger.freeze_live_prediction(_live_match(), fs) == "frozen"
    assert [r["rule_version"] for r in written] == ["live-poisson-v1.2"]
    assert written[0]["details"] == {"shadow": True, "model_only": True}


@pytest.mark.asyncio
async def test_live_freeze_full_match_still_writes_on_screen_version(monkeypatch):
    written = _live_capture(monkeypatch)
    monkeypatch.setattr(live_ledger.live_archive, "load_view", AsyncMock(return_value=None))
    fs = FixtureScore("777", "live", 1, 0, minute="HT")
    await live_ledger.freeze_live_prediction(_live_match(model_only=False), fs)
    versions = [r["rule_version"] for r in written]
    assert "live-poisson-v1.1" in versions
    assert all("model_only" not in r["details"] for r in written)


def test_performance_groups_model_only_separately():
    rows = [{"details": {"model_only": True}}, {"details": {}}, {"details": None}]
    assert [performance.GROUP_FIELDS["model_only"](r) for r in rows] == ["model_only", "full", "full"]


# ─── Hariç tutmalar: ana liglerin oranları ve ekran listeleri değişmez ──────────────────────────────────────

def test_candidate_filters_exclude_model_only():
    from app.analysis.pattern_b import candidate_filters

    assert any("model_only" in str(f) for f in candidate_filters(datetime.now(timezone.utc)))


def test_backtest_history_excludes_model_only():
    from app.analysis.backtest import _history_stmt

    assert "model_only" in str(_history_stmt())


# Her satır: (modül, fonksiyon, neden). Fonksiyonun sorgusu `model_only` süzgecini içermeli.
EXCLUDED = [
    ("app.analysis.live_model", "build_cond_table", "COND tablosu"),
    ("app.analysis.league_priors", "_query_book", "lig ortalamaları"),
    ("app.analysis.live_poisson", "load_training", "takım gücü eğitimi"),
    ("app.analysis.pattern_d", "_load_pool", "A3 aday havuzu"),
    ("app.analysis.freshness", "results_marker", "havuz yenileme sinyali"),
    ("app.analysis.score_snapshots", "capture_score_snapshot", "skor sıklığı havuzu"),
    ("app.analysis.backtest", "_start_run", "backtest hedefleri"),
    ("app.analysis.backtest", "run_live_archive_backtest", "canlı arşiv backtest"),
    ("app.api.routes_fixture", "get_pattern_status", "bülten rozetleri"),
    ("app.api.routes_fixture", "_enrich_prediction_status", "bülten listesi"),
    ("app.api.routes_results", "get_results", "sonuçlar"),
    ("app.api.routes_results", "list_matches", "maç listesi"),
    ("app.api.routes_analysis", "get_match", "analiz sayfası"),
    ("app.api.services", "analyze_and_cache", "analiz sayfası"),
    ("app.api.services", "_analyze_db_only_locked", "arka plan analiz"),
    ("app.api.routes_evaluation", "daily_evaluation", "pattern geçmişi"),
    ("app.api.routes_live_ht", "get_live_ht_matches", "canlı sayfa"),
    ("app.api.routes_live_ht", "get_live_prediction", "canlı sayfa"),
    ("app.api.routes_ht", "ht_strategy", "İY panosu"),
    ("app.api.routes_admin", "admin_quality", "kalite metrikleri"),
    ("app.cli.audit_cmds", "audit_db_cmd", "audit-db"),
    ("app.cli.audit_cmds", "recompute_patterns_cmd", "recompute-patterns"),
]


@pytest.mark.parametrize("module,func,why", EXCLUDED)
def test_pool_and_screen_queries_exclude_model_only(module, func, why):
    source = inspect.getsource(getattr(import_module(module), func))
    assert "model_only.is_(False)" in source, f"{why}: {module}.{func} yalnız model satırlarını süzmüyor"


def test_coverage_sql_excludes_model_only():
    from app.api.routes_performance import _COVERAGE_SQL

    assert "NOT m.model_only" in _COVERAGE_SQL


def test_prepared_ids_ignore_model_only_rows():
    """Hazır sayılmak için Katman A şart — yalnız model satırı ertesi gün yeniden denenir (λ tazelenir)."""
    assert "ft_scores_1.is_not(None)" in inspect.getsource(runner._prepared_match_ids)


def test_included_paths_keep_model_only_rows():
    """Skor güncelleme, sonuç bekleyen günler ve canlı izleyici yalnız model maçlarını da görür."""
    assert "Match.model_only" not in inspect.getsource(runner.update_results)
    assert "Match.model_only.is_(True)" in inspect.getsource(runner.pending_result_days)
    assert "Match.model_only.is_(True)" in inspect.getsource(live_ledger.run_tick)


@pytest.mark.asyncio
async def test_pipeline_writes_model_only_for_tracked_h2h_skip(monkeypatch):
    from app.analysis.filtering import FilterCheck
    from app.models import FixtureMatch, SkipReason

    kickoff = datetime.now(timezone.utc) + timedelta(hours=10)
    fixtures = [FixtureMatch(match_id="777", home_team="Coventry", away_team="Fulham", league_code="ENG PR",
                             league_name=LEAGUE, kickoff_time=kickoff),
                FixtureMatch(match_id="778", home_team="A", away_team="B", league_code="ENG PR",
                             league_name=LEAGUE, kickoff_time=kickoff)]

    @asynccontextmanager
    async def fake_browser():
        yield object()

    monkeypatch.setattr(runner, "browser_context", fake_browser)
    monkeypatch.setattr(runner, "_fetch_fixture_with_retry", AsyncMock(return_value=fixtures))
    monkeypatch.setattr(runner, "save_fixture_cache", AsyncMock(return_value=2))
    monkeypatch.setattr(runner, "save_skip", AsyncMock())
    monkeypatch.setattr(runner, "fetch_match_detail",
                        AsyncMock(side_effect=lambda mid, **_k: _raw(match_id=mid, kickoff_time=kickoff)))
    reasons = {"777": SkipReason.H2H_INSUFFICIENT, "778": SkipReason.HOME_TEAM_INSUFFICIENT}
    monkeypatch.setattr(runner, "check_match_filters", lambda raw: FilterCheck(False, reasons[raw.match_id]))
    model_only = AsyncMock(return_value=1)
    monkeypatch.setattr(runner, "upsert_model_only", model_only)
    import app.analysis.skip_cache as skip_cache
    monkeypatch.setattr(skip_cache, "prune_old_skips", AsyncMock(return_value=0))

    stats = await runner.run_pipeline()
    assert stats["model_only"] == 1 and stats["skipped"] == 2
    model_only.assert_awaited_once()
    assert model_only.await_args.args[0].match_id == "777"
