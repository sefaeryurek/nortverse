"""Canlı İY→MS Poisson modeli (live-poisson-v1) — GÖLGEDE: ekranda yok, sadece deftere yazılır.

Sprint 91 ajan ölçümü: zaman ağırlıklı Poisson takım gücü + 2. yarı skor durumu ile %85+ işaretler
~%93 tutuyordu ve arşivlerin yakalayamadığı maçlarda da karar üretebiliyordu. Bir hafta gölgede
ölçülüp live-arch-v2 ile karşılaştırılacak; ekrana alınması kullanıcı kararıdır.

Model:
1. Takım gücü (lig başına): log λ_ev = μ + ev_avantajı + hücum_ev − savunma_dep,
   log λ_dep = μ + hücum_dep − savunma_ev. Son 3 yıl, yarı ömür 1 yıl, küçük ridge cezası
   (yeni çıkan takım ≈ lig ortalaması). scipy L-BFGS ile ağırlıklı Poisson olabilirlik.
2. 2. yarı: λ_2Y = λ_maç × pay[İY gol farkı]. Pay, aynı ligin geçmiş maçlarında "2Y'de atılan gol /
   modelin maç beklentisi" oranıdır (önde olan takım daha az, geride olan daha çok atar);
   az veride tüm liglerin payına çekilir.
3. Son skor = İY skoru + bağımsız Poisson(λ_2Y_ev) × Poisson(λ_2Y_dep); her pazarın olasılığı
   bu ızgaradan `market_resolver` ile çözülür.

Sızıntısız: model `as_of − 3 saat` öncesinde sonucu bilinen maçlarla kurulur.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import time
from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from app.analysis.freshness import ResultsWatch, results_marker
from app.analysis.live_archive import DECISION_MARKETS, _pair_hit, cond_probability, market_decided
from app.analysis.market_catalog import get_market
from app.analysis.pattern_b import RESULT_KNOWN_DELAY

log = logging.getLogger(__name__)

LIVE_POISSON_RULE_VERSION = "live-poisson-v1"
RULE_PARAMS = {
    "half_life_days": 365,
    "train_days": 1095,
    "ridge": 5.0,  # 1.0'da tek maçlık takım ligin en iyi hücumu çıkıyordu
    "min_league_matches": 200,
    "share_prior_goals": 50.0,
    "max_extra_goals": 10,
    "threshold_pct": 85.0,
    "valuable_cond_below": 80.0,
    "refit_days": 7,
    # live-arch-v2 ile aynı 6 pazar: backtest #10'da KG pazarları %85 gösterip %62-64 tuttu
    "markets": [list(m) for m in DECISION_MARKETS],
}
THRESHOLD_PCT = RULE_PARAMS["threshold_pct"]
VALUABLE_COND_BELOW = RULE_PARAMS["valuable_cond_below"]
MAX_EXTRA = RULE_PARAMS["max_extra_goals"]
STATES = (-2, -1, 0, 1, 2)


def rule_params_fingerprint() -> str:
    return hashlib.sha1(json.dumps(RULE_PARAMS, sort_keys=True).encode()).hexdigest()[:12]


@dataclass(frozen=True)
class TrainMatch:
    kickoff: datetime
    league: str
    home: str
    away: str
    ht_h: int
    ht_a: int
    ft_h: int
    ft_a: int


@dataclass
class LeagueModel:
    mu: float
    home_adv: float
    attack: dict[str, float]
    defense: dict[str, float]
    n: int
    # Dixon-Coles düşük skor düzeltmesi (maç öncesi v5 kullanır; canlı 2Y tahminini etkilemez)
    rho: float = 0.0
    # İY gol farkı durumu → (2Y ev payı, 2Y dep payı) — λ_2Y = λ_maç × pay
    share: dict[int, tuple[float, float]] = field(default_factory=dict)
    # pay hesabı için ham toplamlar (tüm ligler ortalamasına çekmek için)
    _share_sums: dict[int, list[float]] = field(default_factory=dict, repr=False)
    # İlk yarı (Sprint 93, maç öncesi İY ht-display-v1): golün İY'de atılan payı (ev, dep) ve
    # İY lig ortalamaları — aynı zaman ağırlığıyla, sadece eğitim penceresinden (sızıntısız)
    ht_share: tuple[float, float] = (0.445, 0.445)
    ht_base: dict[str, float] = field(default_factory=dict)

    def expected_goals(self, home: str, away: str) -> tuple[float, float]:
        att, dfn = self.attack, self.defense
        lam_h = math.exp(self.mu + self.home_adv + att.get(home, 0.0) - dfn.get(away, 0.0))
        lam_a = math.exp(self.mu + att.get(away, 0.0) - dfn.get(home, 0.0))
        return lam_h, lam_a


@dataclass
class PoissonModel:
    as_of: datetime
    leagues: dict[str, LeagueModel]


def _state(ht_h: int, ht_a: int) -> int:
    return max(-2, min(2, ht_h - ht_a))


def fit_league(rows: list[TrainMatch], as_of: datetime) -> LeagueModel | None:
    """Tek lig için ağırlıklı Poisson takım gücü (numpy + scipy; çağıran thread'de çalıştırır)."""
    import numpy as np
    from scipy.optimize import minimize

    if len(rows) < RULE_PARAMS["min_league_matches"]:
        return None
    teams = sorted({r.home for r in rows} | {r.away for r in rows})
    index = {t: i for i, t in enumerate(teams)}
    n_teams = len(teams)
    hi = np.array([index[r.home] for r in rows])
    ai = np.array([index[r.away] for r in rows])
    y_h = np.array([r.ft_h for r in rows], dtype=float)
    y_a = np.array([r.ft_a for r in rows], dtype=float)
    age = np.array([(as_of - r.kickoff).total_seconds() / 86400 for r in rows])
    w = 0.5 ** (age / RULE_PARAMS["half_life_days"])
    ridge = float(RULE_PARAMS["ridge"])

    def nll(theta):
        mu, hadv = theta[0], theta[1]
        att, dfn = theta[2:2 + n_teams], theta[2 + n_teams:]
        eta_h = mu + hadv + att[hi] - dfn[ai]
        eta_a = mu + att[ai] - dfn[hi]
        lam_h, lam_a = np.exp(eta_h), np.exp(eta_a)
        value = np.sum(w * (lam_h - y_h * eta_h)) + np.sum(w * (lam_a - y_a * eta_a))
        value += ridge * (np.sum(att ** 2) + np.sum(dfn ** 2))
        g_h, g_a = w * (lam_h - y_h), w * (lam_a - y_a)
        grad = np.zeros_like(theta)
        grad[0] = g_h.sum() + g_a.sum()
        grad[1] = g_h.sum()
        grad[2:2 + n_teams] = (np.bincount(hi, g_h, n_teams) + np.bincount(ai, g_a, n_teams) + 2 * ridge * att)
        grad[2 + n_teams:] = (-np.bincount(ai, g_h, n_teams) - np.bincount(hi, g_a, n_teams) + 2 * ridge * dfn)
        return value, grad

    start = np.zeros(2 + 2 * n_teams)
    start[0] = math.log(max(0.1, float(np.average((y_h + y_a) / 2, weights=w))))
    result = minimize(nll, start, jac=True, method="L-BFGS-B")
    theta = result.x
    model = LeagueModel(
        mu=float(theta[0]), home_adv=float(theta[1]),
        attack={t: float(theta[2 + i]) for t, i in index.items()},
        defense={t: float(theta[2 + n_teams + i]) for t, i in index.items()},
        n=len(rows),
    )
    model.rho = _fit_rho(model, rows, w.tolist())
    sums = {s: [0.0, 0.0, 0.0, 0.0] for s in STATES}  # 2Y ev gol, ev beklenti, 2Y dep gol, dep beklenti
    for r, weight in zip(rows, w.tolist()):
        lam_h, lam_a = model.expected_goals(r.home, r.away)
        acc = sums[_state(r.ht_h, r.ht_a)]
        acc[0] += weight * (r.ft_h - r.ht_h)
        acc[1] += weight * lam_h
        acc[2] += weight * (r.ft_a - r.ht_a)
        acc[3] += weight * lam_a
    model._share_sums = sums
    _fit_first_half(model, rows, w.tolist())
    return model


def _fit_first_half(model: LeagueModel, rows: list[TrainMatch], weights: list[float]) -> None:
    """İY gol payı (ev/dep ayrı) ve İY lig ortalamaları (Laplace 0.5) — ağırlıklı eğitim penceresinden."""
    ht_h = ft_h = ht_a = ft_a = total = 0.0
    counts = {"1": 0.0, "X": 0.0, "2": 0.0, "goal": 0.0, "under15": 0.0, "home_scores": 0.0,
              "away_scores": 0.0, "btts": 0.0}
    for r, w in zip(rows, weights):
        ht_h += w * r.ht_h
        ft_h += w * r.ft_h
        ht_a += w * r.ht_a
        ft_a += w * r.ft_a
        total += w
        counts["1" if r.ht_h > r.ht_a else "2" if r.ht_h < r.ht_a else "X"] += w
        counts["goal"] += w * (r.ht_h + r.ht_a > 0)
        counts["under15"] += w * (r.ht_h + r.ht_a < 2)
        counts["home_scores"] += w * (r.ht_h > 0)
        counts["away_scores"] += w * (r.ht_a > 0)
        counts["btts"] += w * (r.ht_h > 0 and r.ht_a > 0)
    model.ht_share = (ht_h / ft_h if ft_h else 0.445, ht_a / ft_a if ft_a else 0.445)
    model.ht_base = {k: (v + 0.5) / (total + 1.0) for k, v in counts.items()}


def dc_tau(x: int, y: int, lam_h: float, lam_a: float, rho: float) -> float:
    """Dixon-Coles (1997) düzeltmesi: 0-0, 1-0, 0-1, 1-1 skorlarının bağımsız Poisson'dan sapması."""
    if x == 0 and y == 0:
        return 1 - lam_h * lam_a * rho
    if x == 0 and y == 1:
        return 1 + lam_h * rho
    if x == 1 and y == 0:
        return 1 + lam_a * rho
    if x == 1 and y == 1:
        return 1 - rho
    return 1.0


def _fit_rho(model: LeagueModel, rows: list[TrainMatch], weights: list[float]) -> float:
    """Takım güçleri sabitken ağırlıklı log-olabilirliği en büyükleyen rho ([-0.2, 0.2])."""
    from scipy.optimize import minimize_scalar

    low = []
    for r, weight in zip(rows, weights):
        if r.ft_h <= 1 and r.ft_a <= 1:
            low.append((r.ft_h, r.ft_a, *model.expected_goals(r.home, r.away), weight))
    if not low:
        return 0.0

    def neg(rho: float) -> float:
        total = 0.0
        for x, y, lam_h, lam_a, weight in low:
            tau = dc_tau(x, y, lam_h, lam_a, rho)
            if tau <= 0:
                return 1e12
            total -= weight * math.log(tau)
        return total

    return float(minimize_scalar(neg, bounds=(-0.2, 0.2), method="bounded").x)


def _finish_shares(leagues: dict[str, LeagueModel]) -> None:
    """Lig payları ana liglerin ortak payına `share_prior_goals` beklenen gol kadar çekilir.

    Ortak pay sadece 7 ana ligden (Sprint 92): gölgedeki yeni ligler ana liglerin payını kaydırmasın.
    """
    from app.analysis.league_filter import is_main_league

    total = {s: [0.0, 0.0, 0.0, 0.0] for s in STATES}
    reference = [lm for name, lm in leagues.items() if is_main_league(name)] or list(leagues.values())
    for lm in reference:
        for s, acc in lm._share_sums.items():
            for i in range(4):
                total[s][i] += acc[i]
    k = RULE_PARAMS["share_prior_goals"]
    glob = {s: (t[0] / t[1] if t[1] else 0.55, t[2] / t[3] if t[3] else 0.55) for s, t in total.items()}
    for lm in leagues.values():
        for s in STATES:
            acc = lm._share_sums.get(s, [0.0, 0.0, 0.0, 0.0])
            gh, ga = glob[s]
            lm.share[s] = (float((acc[0] + k * gh) / (acc[1] + k)), float((acc[2] + k * ga) / (acc[3] + k)))


def fit_model(rows: list[TrainMatch], as_of: datetime) -> PoissonModel:
    """Tüm ligler. `rows` sadece `as_of − 3 saat` öncesi ve son `train_days` içindeki maçlar olmalı."""
    by_league: dict[str, list[TrainMatch]] = {}
    for r in rows:
        by_league.setdefault(r.league, []).append(r)
    leagues = {}
    for league, items in by_league.items():
        lm = fit_league(items, as_of)
        if lm is not None:
            leagues[league] = lm
    _finish_shares(leagues)
    return PoissonModel(as_of=as_of, leagues=leagues)


def _pmf(lam: float) -> list[float]:
    probs = [math.exp(-lam) * lam ** k / math.factorial(k) for k in range(MAX_EXTRA)]
    probs.append(max(0.0, 1.0 - sum(probs)))  # kuyruk son hücrede
    return probs


def final_grid(model: PoissonModel, league: str, home: str, away: str, ht: tuple[int, int]) -> dict | None:
    """İY skorundan son skor dağılımı: [((iy_ev, iy_dep, ms_ev, ms_dep), olasılık)] + λ'lar. Model yoksa None."""
    lm = model.leagues.get(league)
    if lm is None:
        return None
    lam_h, lam_a = lm.expected_goals(home, away)
    share_h, share_a = lm.share[_state(*ht)]
    r_h, r_a = lam_h * share_h, lam_a * share_a
    ph, pa = _pmf(r_h), _pmf(r_a)
    grid = [((ht[0], ht[1], ht[0] + i, ht[1] + j), ph[i] * pa[j]) for i in range(len(ph)) for j in range(len(pa))]
    return {"grid": grid, "lam_h": lam_h, "lam_a": lam_a, "r_h": r_h, "r_a": r_a}


def predict(model: PoissonModel, league: str, home: str, away: str, ht: tuple[int, int]) -> dict | None:
    """Pazar başına en olası seçim ve olasılığı (yüzde). Lig modeli yoksa None."""
    dist = final_grid(model, league, home, away, ht)
    if dist is None:
        return None
    grid, lam_h, lam_a, r_h, r_a = dist["grid"], dist["lam_h"], dist["lam_a"], dist["r_h"], dist["r_a"]
    cells = []
    for period, market in DECISION_MARKETS:
        if market_decided(period, market, tuple(ht)):
            continue
        options = {}
        for _field, code in get_market(market).fields:
            options[code] = round(100 * sum(p for pair, p in grid if _pair_hit(period, market, code, pair)), 1)
        best = max(options, key=options.get)
        cells.append({"period": period, "market": market, "selection": best, "pct": options[best],
                      "options": options})
    return {"lambda_2h": {"home": round(r_h, 3), "away": round(r_a, 3)},
            "lambda_ft": {"home": round(lam_h, 3), "away": round(lam_a, 3)}, "cells": cells}


def decisions(prediction: dict | None, cond_of) -> list[dict]:
    """%85+ seçimler; COND (lig + İY geçmişi) <%80 ise "değerli"; en yüksek olasılıklı = en iyi tek işaret."""
    if prediction is None:
        return []
    out = []
    for cell in prediction["cells"]:
        if cell["pct"] < THRESHOLD_PCT:
            continue
        cond = cond_of(cell["period"], cell["market"], cell["selection"])
        out.append({**cell, "cond_pct": cond["pct"] if cond else None, "cond_n": cond["n"] if cond else None,
                    "valuable": cond is None or cond["pct"] < VALUABLE_COND_BELOW, "best": False})
    if out:
        max(out, key=lambda d: d["pct"])["best"] = True
    return out


def ledger_rows(prediction: dict, picks: list[dict], common: dict, *, late: bool = False) -> list[dict]:
    """Gölge kayıtlar: ekranda gösterilmez, sadece ölçülür."""
    return [{
        **common, "source": "live_ht", "rule_version": LIVE_POISSON_RULE_VERSION,
        "period": p["period"], "market": p["market"], "selection": p["selection"], "archive": None,
        "prob_shown_bp": round(p["pct"] * 100), "sample_n": None, "confidence_tier": "high",
        "details": {"shadow": True, "valuable": p["valuable"], "best": p["best"],
                    "cond_pct": p["cond_pct"], "cond_n": p["cond_n"], "options": p["options"],
                    "lambda_2h": prediction["lambda_2h"], "lambda_ft": prediction["lambda_ft"],
                    "params": rule_params_fingerprint(), "late": late},
    } for p in picks]


def cond_lookup(table, league: str, ht: tuple[int, int]):
    return lambda period, market, sel: cond_probability(table, league, ht, period, market, sel)


# ─── Eğitim verisi + canlı önbellek ─────────────────────────────────────────

def train_window(history: list[TrainMatch], kickoffs: list[datetime], as_of: datetime) -> list[TrainMatch]:
    """Sıralı geçmişten [as_of − train_days, as_of − 3 saat] aralığı (backtest için O(log n))."""
    lo = bisect_left(kickoffs, as_of - timedelta(days=RULE_PARAMS["train_days"]))
    hi = bisect_right(kickoffs, as_of - RESULT_KNOWN_DELAY)
    return history[lo:hi]


async def load_training(as_of: datetime | None = None) -> list[TrainMatch]:
    """Ana liglerin sonucu maçtan sonra kaydedilmiş biten maçları (zaman sıralı)."""
    from sqlalchemy import func, select

    from app.analysis.league_filter import is_tracked_league
    from app.db.connection import get_session
    from app.db.models import Match

    known_at = func.coalesce(Match.result_first_fetched_at, Match.result_fetched_at)
    stmt = select(
        Match.kickoff_time, Match.league_name, Match.home_team, Match.away_team,
        Match.actual_ht_home, Match.actual_ht_away, Match.actual_ft_home, Match.actual_ft_away,
    ).where(
        Match.deleted_at.is_(None), Match.actual_ft_home.isnot(None), Match.actual_ht_home.isnot(None),
        Match.kickoff_time.isnot(None), known_at > Match.kickoff_time, Match.league_name.isnot(None),
    ).order_by(Match.kickoff_time)
    if as_of is not None:
        stmt = stmt.where(Match.kickoff_time <= as_of - RESULT_KNOWN_DELAY,
                          Match.kickoff_time >= as_of - timedelta(days=RULE_PARAMS["train_days"]))
    async with get_session() as session:
        rows = (await session.execute(stmt)).all()
    out = []
    for ko, league, home, away, hh, ha, fh, fa in rows:
        if hh > fh or ha > fa or not is_tracked_league(league):
            continue
        out.append(TrainMatch(ko if ko.tzinfo else ko.replace(tzinfo=timezone.utc), league, home, away, hh, ha, fh, fa))
    return out


MODEL_TTL_SECONDS = 24 * 3600
_model: PoissonModel | None = None
_model_built_at = 0.0
_model_lock = asyncio.Lock()
_model_watch = ResultsWatch()


async def get_poisson_model() -> PoissonModel:
    """Günde bir ya da yeni sonuç gelince yeniden kurulur (kesim = kuruluş − 3 saat)."""
    global _model, _model_built_at
    fresh = _model is not None and time.monotonic() - _model_built_at < MODEL_TTL_SECONDS
    if fresh and not await _model_watch.stale():
        return _model
    async with _model_lock:
        if _model is None or time.monotonic() - _model_built_at >= MODEL_TTL_SECONDS or await _model_watch.stale():
            marker = await results_marker()
            as_of = datetime.now(timezone.utc)
            rows = await load_training(as_of)
            _model = await asyncio.to_thread(fit_model, rows, as_of)
            _model_built_at = time.monotonic()
            _model_watch.mark(marker)
            log.info("Poisson canlı modeli kuruldu: %d lig, %d maç", len(_model.leagues), len(rows))
    return _model


# ─── Maç öncesi takım gücü beklentisi (A3 en yakın maç uzayı, Sprint 91 Faz 4) ─────────

def week_start(moment: datetime) -> datetime:
    """Haftalık model önbelleği anahtarı (Pazartesi 00:00 UTC) — as_of ≤ kickoff olduğundan sızıntısız."""
    day = moment.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return day - timedelta(days=day.weekday())


def expected_pair(model: PoissonModel, league: str, home: str, away: str) -> tuple[float, float] | None:
    lm = model.leagues.get(league)
    if lm is None:
        return None
    lam_h, lam_a = lm.expected_goals(home, away)
    return round(lam_h, 4), round(lam_a, 4)


async def backfill_team_lambdas(*, only_missing: bool = True, batch: int = 2000) -> dict:
    """Tüm (ana lig) maçlara maç öncesi λ ev/dep yazar. Her maç, başlama haftasının başında kurulmuş
    modelle hesaplanır (eğitim: o andan 3 saat öncesine kadar) → arşiv maçlarında gelecek bilgisi yok."""
    from sqlalchemy import select, update

    from app.analysis.league_filter import is_tracked_league
    from app.db.connection import get_session
    from app.db.models import Match

    training = await load_training()
    kickoffs = [t.kickoff for t in training]
    stmt = select(Match.match_id, Match.league_name, Match.home_team, Match.away_team, Match.kickoff_time).where(
        Match.deleted_at.is_(None), Match.kickoff_time.isnot(None), Match.league_name.isnot(None),
    ).order_by(Match.kickoff_time)
    if only_missing:
        stmt = stmt.where(Match.team_lambda_home.is_(None))
    async with get_session() as session:
        targets = [r for r in (await session.execute(stmt)).all() if is_tracked_league(r.league_name)]
    now = datetime.now(timezone.utc)
    models: dict[datetime, PoissonModel] = {}
    stats = {"targets": len(targets), "written": 0, "no_model": 0}
    pending: list[dict] = []

    async def flush() -> None:
        if not pending:
            return
        async with get_session() as session:
            for item in pending:
                await session.execute(update(Match).where(Match.match_id == item["id"]).values(
                    team_lambda_home=item["h"], team_lambda_away=item["a"], team_lambda_as_of=item["as_of"]))
        stats["written"] += len(pending)
        pending.clear()

    for mid, league, home, away, kickoff in targets:
        kickoff = kickoff if kickoff.tzinfo else kickoff.replace(tzinfo=timezone.utc)
        as_of = week_start(min(kickoff, now))
        model = models.get(as_of)
        if model is None:
            model = models[as_of] = await asyncio.to_thread(fit_model, train_window(training, kickoffs, as_of), as_of)
            if len(models) > 8:
                models.pop(next(iter(models)))
        pair = expected_pair(model, league, home, away)
        if pair is None:
            stats["no_model"] += 1
            continue
        pending.append({"id": mid, "h": pair[0], "a": pair[1], "as_of": as_of})
        if len(pending) >= batch:
            await flush()
            log.info("Takım gücü λ: %d/%d", stats["written"], len(targets))
    await flush()
    return stats


# Saklı λ en fazla bu kadar eski bir modelle hesaplanmışsa kullanılır; yaklaşan maçlar Ekim'de
# Mayıs maçı için yazılan λ ile maç günü A3 eşleşmesi yapmasın (Sprint 92.2).
LAMBDA_MAX_AGE = timedelta(days=7)
_week_models: dict[datetime, PoissonModel] = {}
_week_lock = asyncio.Lock()


def stored_lambda_usable(stored_as_of: datetime | None, *, as_of: datetime, kickoff: datetime | None,
                         now: datetime) -> bool:
    """Saklı λ bu hesap için geçerli mi? Maçın kendi sonucunu görmemiş ve yeterince taze olmalı."""
    if stored_as_of is None:
        return False
    if kickoff is not None and stored_as_of - RESULT_KNOWN_DELAY >= kickoff:
        return False  # model maçın kendi sonucunu görmüş olabilir (sızıntı)
    return stored_as_of >= min(as_of, now) - LAMBDA_MAX_AGE


async def _model_for(kickoff: datetime, now: datetime) -> PoissonModel:
    """Maçın kendi sonucunu görmeyen model: güncel model uygunsa o, değilse başlama haftasının modeli."""
    current = await get_poisson_model()
    if current.as_of - RESULT_KNOWN_DELAY < kickoff:
        return current
    as_of = week_start(min(kickoff, now))
    async with _week_lock:
        model = _week_models.get(as_of)
        if model is None:
            model = await asyncio.to_thread(fit_model, await load_training(as_of), as_of)
            _week_models[as_of] = model
            while len(_week_models) > 8:
                _week_models.pop(next(iter(_week_models)))
    return model


async def team_lambdas_for_match(match_id: str, as_of: datetime, *, league: str | None = None,
                                 home: str | None = None, away: str | None = None,
                                 kickoff: datetime | None = None) -> tuple[float, float] | None:
    """Maçın maç öncesi λ'sı. Saklı değer geçerliyse o; yoksa sızıntısız modelle hesaplanıp yazılır.

    Satır henüz yoksa (pipeline'da ilk analiz, kayıt pattern'lerden sonra yapılır) `league/home/away`
    ile hesaplanır, yazılamaz; `_upsert` kayıttan sonra tekrar çağırıp yazar. Model yoksa None.
    """
    from sqlalchemy import select, update

    from app.db.connection import get_session
    from app.db.models import Match

    async with get_session() as session:
        row = (await session.execute(select(
            Match.team_lambda_home, Match.team_lambda_away, Match.team_lambda_as_of,
            Match.league_name, Match.home_team, Match.away_team, Match.kickoff_time,
        ).where(Match.match_id == match_id))).first()
    now = datetime.now(timezone.utc)
    if row is not None:
        league, home, away = row.league_name or league, row.home_team or home, row.away_team or away
        kickoff = row.kickoff_time or kickoff
    if not (league and home and away):
        return None
    kickoff = kickoff or as_of
    kickoff = kickoff if kickoff.tzinfo else kickoff.replace(tzinfo=timezone.utc)
    if (row is not None and row.team_lambda_home is not None and row.team_lambda_away is not None
            and stored_lambda_usable(row.team_lambda_as_of, as_of=as_of, kickoff=kickoff, now=now)):
        return row.team_lambda_home, row.team_lambda_away
    if row is not None and row.team_lambda_home is None and now - kickoff > timedelta(days=8):
        return None  # hiç λ'sı olmayan eski maç: doldurma komutu (backfill-team-lambdas) haftalık modelle yazar
    model = await _model_for(kickoff, now)
    pair = expected_pair(model, league, home, away)
    if pair is None:
        return None
    if row is not None:
        async with get_session() as session:
            await session.execute(update(Match).where(Match.match_id == match_id).values(
                team_lambda_home=pair[0], team_lambda_away=pair[1], team_lambda_as_of=model.as_of))
    return pair
