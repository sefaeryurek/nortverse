"""Backtest — "bugünkü algoritma o gün ne derdi" (sızıntısız, yeniden üretilebilir).

Maç öncesi (top_pick / market_summary): as_of = kickoff, prior aynı kayan pencereden;
satırın ht_*/ft_* kolonları gerçek İY/MS skorudur.

Canlı (live_ht): maçlar zaman sırasıyla işlenir; her hedef maç için COND tablosu sadece
hedefin İY anından (kickoff + 47 dk) 3 saat öncesine kadar sonucu bilinen maçlarla kurulur,
lig prior'u kayan 3 yıllık penceredir. Maç öncesi arşiv görüşü saklı pattern_ft_* değerleridir
(as_of = kickoff ile hesaplanmış). Sonuçlar `prediction_backtest`e yazılır, gerçek defterle karışmaz.
"""

from __future__ import annotations

import logging
import subprocess
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, insert, select

from app.analysis.live_model import (
    ALPHA, LIVE_RULE_VERSION, OUTCOMES, PRIOR_SEASON_DAYS, CondTable, Counts, predict_live,
)
from app.analysis.league_filter import canonical_league_name
from app.analysis.ledger import PREDICTION_DEFAULTS, uniform_rows
from app.analysis.market_resolver import resolve
from app.analysis.pattern_b import RESULT_KNOWN_DELAY
from app.analysis.prematch_v4 import (
    MARKET_SUMMARY_RULE_VERSION, RULE_PARAMS, V4_RULE_VERSION, ledger_rows_v4, rule_params_fingerprint,
)
from app.db.connection import get_session
from app.db.models import BacktestRun, Match, PredictionBacktest

log = logging.getLogger(__name__)

HT_CAPTURE_OFFSET = timedelta(minutes=47)
_BATCH = 1000


@dataclass
class IncrementalCondTable(CondTable):
    """CondTable + kayan pencereli lig prior'u (backtest için O(N))."""

    _prior_queue: deque = field(default_factory=deque)

    def add(self, league: str, ht_h: int, ht_a: int, ft_h: int, ft_a: int, kickoff: datetime) -> None:
        key = (ht_h, ht_a)
        diff = max(-3, min(3, ht_h - ht_a))
        self.by_score.setdefault(league, {}).setdefault(key, Counts()).add(ft_h, ft_a)
        self.by_diff.setdefault(league, {}).setdefault(diff, Counts()).add(ft_h, ft_a)
        self.global_by_score.setdefault(key, Counts()).add(ft_h, ft_a)
        self.global_by_diff.setdefault(diff, Counts()).add(ft_h, ft_a)
        self.prior.setdefault(league, Counts()).add(ft_h, ft_a)
        self._prior_queue.append((kickoff, league, ft_h, ft_a))

    def advance_prior(self, prior_from: datetime) -> None:
        self.prior_from = prior_from
        while self._prior_queue and self._prior_queue[0][0] < prior_from:
            _, league, ft_h, ft_a = self._prior_queue.popleft()
            self.prior[league].add(ft_h, ft_a, sign=-1)


def _git_sha() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                              timeout=5, check=True).stdout.strip() or None
    except Exception:
        return None


def multiclass_brier(probs: dict[str, float], ft: tuple[int, int]) -> float:
    actual = "1" if ft[0] > ft[1] else "X" if ft[0] == ft[1] else "2"
    return sum((probs[o] - (o == actual)) ** 2 for o in OUTCOMES)


def _rows_for(match, prediction: dict, run_id: int, as_of: datetime) -> list[dict]:
    ht, ft = (match.actual_ht_home, match.actual_ht_away), (match.actual_ft_home, match.actual_ft_away)
    common = {
        "run_id": run_id, "source": "live_ht", "rule_version": LIVE_RULE_VERSION,
        "match_id": match.match_id, "league_name": match.league_name, "kickoff_time": match.kickoff_time,
        "as_of": as_of, "period": "ft", "ht_home": ht[0], "ht_away": ht[1],
        "ft_home": ft[0], "ft_away": ft[1],
    }
    ms = prediction["ms"]
    rows = [{
        **common, "market": "result", "selection": ms["pick"],
        "prob_shown_bp": round(ms["prob"] * 10000),
        "prob_raw_bp": round(ms["ht_baseline"]["probs"][ms["pick"]] * 10000),
        "baseline_selection": ms["ht_baseline"]["pick"],
        "baseline_prob_bp": round(ms["ht_baseline"]["prob"] * 10000),
        "confidence_tier": ms["tier"], "sample_n": ms["n"] or None,
        "outcome": resolve("ft", "result", ms["pick"], ht, ft),
        "details": {"ms": ms, "brier": round(multiclass_brier(ms["probs"], ft), 5),
                    "baseline_brier": round(multiclass_brier(ms["ht_baseline"]["probs"], ft), 5)},
    }]
    for market, key in (("ou_25", "over25"), ("kg", "btts")):
        block = prediction[key]
        if block.get("applicable"):
            rows.append({
                **common, "market": market, "selection": block["pick"],
                "prob_shown_bp": round(block["prob"] * 10000),
                "confidence_tier": block["tier"], "sample_n": block["n"] or None,
                "outcome": resolve("ft", market, block["pick"], ht, ft), "details": {key: block},
            })
    return rows


def _history_stmt():
    known_at = func.coalesce(Match.result_first_fetched_at, Match.result_fetched_at)
    return select(
        Match.league_name, Match.actual_ht_home, Match.actual_ht_away,
        Match.actual_ft_home, Match.actual_ft_away, Match.kickoff_time,
    ).where(
        Match.deleted_at.is_(None),
        Match.actual_ft_home.isnot(None), Match.actual_ht_home.isnot(None),
        Match.kickoff_time.isnot(None), known_at > Match.kickoff_time,
        Match.league_name.isnot(None),
    ).order_by(Match.kickoff_time)


async def _start_run(strategy: str, rule_version: str, params: dict, date_from: datetime,
                     date_to: datetime, notes: str | None, replace_run: int | None):
    """Geçmiş maçları + hedef maç id'lerini yükler, backtest_runs satırını açar."""
    target_ids_stmt = select(Match.match_id).where(
        Match.deleted_at.is_(None),
        Match.actual_ft_home.isnot(None), Match.actual_ht_home.isnot(None),
        Match.kickoff_time >= date_from, Match.kickoff_time < date_to,
        Match.league_name.isnot(None),
    ).order_by(Match.kickoff_time, Match.match_id)
    async with get_session() as session:
        history = [r for r in (await session.execute(_history_stmt())).all()
                   if r[1] <= r[3] and r[2] <= r[4]]
        target_ids = list((await session.execute(target_ids_stmt)).scalars().all())
        if replace_run is not None:
            await session.execute(delete(BacktestRun).where(BacktestRun.id == replace_run))
        run_id = (await session.execute(
            insert(BacktestRun).values(
                strategy=strategy, rule_version=rule_version, params=params,
                date_from=date_from, date_to=date_to, git_sha=_git_sha(), notes=notes,
            ).returning(BacktestRun.id)
        )).scalar_one()
    return run_id, history, target_ids


async def _replay(run_id: int, history: list, target_ids: list[str], date_from: datetime,
                  as_of_of, rows_of) -> int:
    """Hedef maçları zaman sırasıyla işler; tablo her maçta sadece as_of − 3 saate kadar bilinenleri görür."""
    table = IncrementalCondTable(cutoff=date_from, prior_from=date_from)
    cursor = 0
    written = 0
    for start in range(0, len(target_ids), _BATCH):
        chunk_ids = target_ids[start:start + _BATCH]
        async with get_session() as session:
            targets = (await session.execute(
                select(Match).where(Match.match_id.in_(chunk_ids)).order_by(Match.kickoff_time, Match.match_id)
            )).scalars().all()
        rows: list[dict] = []
        for match in targets:
            kickoff = match.kickoff_time if match.kickoff_time.tzinfo else match.kickoff_time.replace(tzinfo=timezone.utc)
            as_of = as_of_of(kickoff)
            cutoff = as_of - RESULT_KNOWN_DELAY
            while cursor < len(history) and history[cursor][5] <= cutoff:
                league, ht_h, ht_a, ft_h, ft_a, ko = history[cursor]
                table.add(league, ht_h, ht_a, ft_h, ft_a, ko)
                cursor += 1
            table.cutoff = cutoff
            table.advance_prior(as_of - timedelta(days=PRIOR_SEASON_DAYS))
            rows.extend(rows_of(table, match, as_of))
        async with get_session() as session:
            for i in range(0, len(rows), 500):
                await session.execute(insert(PredictionBacktest).values(
                    uniform_rows(rows[i:i + 500], PREDICTION_DEFAULTS)))
        written += len(rows)
        log.info("Backtest #%d: %d/%d maç", run_id, min(start + _BATCH, len(target_ids)), len(target_ids))
    log.info("Backtest #%d tamamlandı: %d satır", run_id, written)
    return written


async def run_live_backtest(date_from: datetime, date_to: datetime, *, notes: str | None = None,
                            alpha: float = ALPHA, replace_run: int | None = None) -> int:
    """Canlı modelin backtest'ini çalıştırır; backtest_runs.id döner."""
    run_id, history, target_ids = await _start_run(
        "live_ht", LIVE_RULE_VERSION, {"alpha": alpha, "ht_capture_offset_min": 47},
        date_from, date_to, notes, replace_run,
    )
    log.info("Canlı backtest #%d: %d hedef maç, %d geçmiş maç", run_id, len(target_ids), len(history))

    def rows_of(table, match, as_of):
        prediction = predict_live(
            table, match.league_name, (match.actual_ht_home, match.actual_ht_away),
            [match.pattern_ft_b, match.pattern_ft_c, match.pattern_ft_d], alpha=alpha,
        )
        return _rows_for(match, prediction, run_id, as_of)

    await _replay(run_id, history, target_ids, date_from, lambda ko: ko + HT_CAPTURE_OFFSET, rows_of)
    return run_id


def prematch_rows(table, match, as_of: datetime, run_id: int, strategy: str) -> list[dict]:
    """Maç öncesi v4 kararı (saklı pattern'ler = 'bugünkü algoritma kickoff'ta ne derdi') + sonucu."""
    league = canonical_league_name(match.league_name)
    patterns = {f"pattern_{p}_{f}": getattr(match, f"pattern_{p}_{f}") for p in ("ht", "h2", "ft") for f in "bcd"}
    common = {"match_id": match.match_id, "league_name": league, "kickoff_time": match.kickoff_time,
              "as_of": as_of}
    ht = (match.actual_ht_home, match.actual_ht_away)
    ft = (match.actual_ft_home, match.actual_ft_away)
    out = []
    for row in ledger_rows_v4(patterns, table.league_prior(league), table.league_goal_prior(league), common):
        if row["source"] != strategy:
            continue
        out.append({**row, "run_id": run_id, "ht_home": ht[0], "ht_away": ht[1],
                    "ft_home": ft[0], "ft_away": ft[1],
                    "outcome": resolve(row["period"], row["market"], row["selection"], ht, ft)})
    return out


async def run_prematch_backtest(strategy: str, date_from: datetime, date_to: datetime, *,
                                notes: str | None = None, replace_run: int | None = None) -> int:
    """Top Picks (v4) veya Ana Pazar Özeti kazananlarının backtest'i; backtest_runs.id döner."""
    rule_version = V4_RULE_VERSION if strategy == "top_pick" else MARKET_SUMMARY_RULE_VERSION
    run_id, history, target_ids = await _start_run(
        strategy, rule_version,
        {"rule_params": RULE_PARAMS, "params_fingerprint": rule_params_fingerprint()},
        date_from, date_to, notes, replace_run,
    )
    log.info("Maç öncesi backtest #%d (%s): %d hedef maç", run_id, strategy, len(target_ids))
    await _replay(run_id, history, target_ids, date_from, lambda ko: ko,
                  lambda table, match, as_of: prematch_rows(table, match, as_of, run_id, strategy))
    return run_id


async def run_live_archive_backtest(date_from: datetime, date_to: datetime, *, notes: str | None = None,
                                    replace_run: int | None = None) -> int:
    """Canlı arşiv görünümü (live-arch-v1): her maçın %85+ işaretleri, gerçek İY/MS ile çözülür.

    Arşiv üyelikleri maç öncesi `matched_ids`'ten (sonucu kickoff − 3 saatten önce bilinen maçlar) → sızıntısız.
    """
    from app.analysis import live_archive

    run_id, history, target_ids = await _start_run(
        "live_ht", live_archive.LIVE_ARCHIVE_RULE_VERSION,
        {"rule_params": live_archive.RULE_PARAMS, "params_fingerprint": live_archive.rule_params_fingerprint(),
         "ht_capture_offset_min": 47},
        date_from, date_to, notes, replace_run,
    )
    async with get_session() as session:
        results = {r[0]: tuple(r[1:]) for r in (await session.execute(select(
            Match.match_id, Match.actual_ht_home, Match.actual_ht_away, Match.actual_ft_home, Match.actual_ft_away,
        ).where(Match.deleted_at.is_(None), Match.actual_ft_home.isnot(None), Match.actual_ht_home.isnot(None)))).all()}
    log.info("Canlı arşiv backtest #%d: %d hedef maç", run_id, len(target_ids))

    def rows_of(_table, match, as_of):
        ht = (match.actual_ht_home, match.actual_ht_away)
        ft = (match.actual_ft_home, match.actual_ft_away)
        blobs = {"b": match.pattern_ft_b, "c": match.pattern_ft_c, "d": match.pattern_ft_d}
        view = live_archive.build_view(live_archive.ht_filtered_rows(blobs, results, ht), ht)
        common = {"match_id": match.match_id, "league_name": match.league_name,
                  "kickoff_time": match.kickoff_time, "as_of": as_of}
        return [{**row, "run_id": run_id, "ht_home": ht[0], "ht_away": ht[1], "ft_home": ft[0], "ft_away": ft[1],
                 "outcome": resolve(row["period"], row["market"], row["selection"], ht, ft)}
                for row in live_archive.ledger_rows(view, common)]

    await _replay(run_id, history, target_ids, date_from, lambda ko: ko + HT_CAPTURE_OFFSET, rows_of)
    return run_id


async def load_backtest_rows(run_id: int) -> list[dict]:
    async with get_session() as session:
        rows = (await session.execute(
            select(PredictionBacktest).where(PredictionBacktest.run_id == run_id)
        )).scalars().all()
    out = []
    for r in rows:
        data = {c: getattr(r, c) for c in (
            "market", "selection", "period", "prob_shown_bp", "confidence_tier", "league_name",
            "kickoff_time", "archive", "informational", "outcome", "baseline_selection",
            "ft_home", "ft_away", "ht_home", "ht_away", "details",
        )}
        data["baseline_outcome"] = (
            resolve(r.period, r.market, r.baseline_selection, (r.ht_home, r.ht_away), (r.ft_home, r.ft_away))
            if r.baseline_selection and r.outcome in ("hit", "miss") else None
        )
        out.append(data)
    return out


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def ms_brier_report(rows: list[dict]) -> dict:
    """MS satırları için çok sınıflı Brier: model vs İY tabanı."""
    ms = [r for r in rows if r["market"] == "result" and (r["details"] or {}).get("brier") is not None]
    return {
        "brier": _mean([r["details"]["brier"] for r in ms]),
        "baseline_brier": _mean([r["details"]["baseline_brier"] for r in ms]),
    }
