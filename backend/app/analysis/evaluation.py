"""Değerlendirme çekirdek mantığı — API ve CLI ortak kullanır."""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.analysis.league_priors import DEFAULT_RATES, PriorBook
from app.config import ANALYSIS


def get_base_rates(league_name: str | None, priors: PriorBook | None = None) -> dict[str, float]:
    """Lig ortalaması (yüzde) — tek kaynak `league_priors`. priors verilmezse genel varsayılan."""
    if priors is not None:
        return priors.rates(league_name)
    return dict(DEFAULT_RATES)


@dataclass
class PatternEval:
    match_count: int
    result_pick: str
    result_pct: float
    result_hit: bool
    result_margin: float
    is_confident: bool
    over_25_pick: str
    over_25_pct: float
    over_25_hit: bool
    btts_pick: str
    btts_pct: float
    btts_hit: bool
    brier_score: float


def evaluate_pattern(
    pattern_data: dict | None,
    actual_result: str,
    actual_over_25: bool,
    actual_btts: bool,
    min_matches: int = 1,
    league_name: str | None = None,
    priors: PriorBook | None = None,
) -> PatternEval | None:
    if not pattern_data or not isinstance(pattern_data, dict):
        return None
    mc = pattern_data.get("match_count", 0)
    if mc < min_matches:
        return None

    pcts = {
        "1": pattern_data.get("result_1_pct", 0) or 0,
        "X": pattern_data.get("result_x_pct", 0) or 0,
        "2": pattern_data.get("result_2_pct", 0) or 0,
    }

    base_rates = get_base_rates(league_name, priors)
    shrink = ANALYSIS.result_shrinkage / (1 + mc / ANALYSIS.shrinkage_half_life)

    adjusted_pcts: dict[str, float] = {}
    for k in ("1", "X", "2"):
        raw_p = max(1.0, min(99.0, pcts[k])) / 100.0
        base_p = base_rates[k] / 100.0
        raw_logit = math.log(raw_p / (1 - raw_p))
        base_logit = math.log(base_p / (1 - base_p))
        adj_logit = raw_logit * (1 - shrink) + base_logit * shrink
        adjusted_pcts[k] = 1 / (1 + math.exp(-adj_logit)) * 100

    sorted_vals = sorted(adjusted_pcts.values(), reverse=True)
    result_margin = sorted_vals[0] - sorted_vals[1]
    is_confident = result_margin >= ANALYSIS.result_min_margin

    result_pick = max(adjusted_pcts, key=lambda k: adjusted_pcts[k])
    result_hit = result_pick == actual_result

    ou_base = base_rates["ou25"]
    btts_base = base_rates["btts"]

    over_pct = pattern_data.get("ust_25_pct", 0) or 0
    over_raw_p = max(1.0, min(99.0, over_pct)) / 100.0
    over_base_p = ou_base / 100.0
    over_adj_logit = (
        math.log(over_raw_p / (1 - over_raw_p)) * (1 - shrink)
        + math.log(over_base_p / (1 - over_base_p)) * shrink
    )
    over_adjusted = 1 / (1 + math.exp(-over_adj_logit)) * 100
    # Seçim olasılığı %50'nin üstünde olan taraf ("Alt %40" gibi %50 altı seçim gösterilmez).
    over_pick = over_adjusted > 50.0
    over_hit = over_pick == actual_over_25

    btts_pct = pattern_data.get("kg_var_pct", 0) or 0
    btts_raw_p = max(1.0, min(99.0, btts_pct)) / 100.0
    btts_base_p = btts_base / 100.0
    btts_adj_logit = (
        math.log(btts_raw_p / (1 - btts_raw_p)) * (1 - shrink)
        + math.log(btts_base_p / (1 - btts_base_p)) * shrink
    )
    btts_adjusted = 1 / (1 + math.exp(-btts_adj_logit)) * 100
    btts_pick_val = btts_adjusted > 50.0
    btts_hit = btts_pick_val == actual_btts

    brier = sum(
        (adjusted_pcts[k] / 100.0 - (1.0 if k == actual_result else 0.0)) ** 2
        for k in ("1", "X", "2")
    )

    return PatternEval(
        match_count=mc,
        result_pick=result_pick,
        result_pct=round(pcts[result_pick], 1),
        result_hit=result_hit,
        result_margin=round(result_margin, 1),
        is_confident=is_confident,
        over_25_pick="Üst" if over_pick else "Alt",
        over_25_pct=round(over_pct if over_pick else (100 - over_pct), 1),
        over_25_hit=over_hit,
        btts_pick="KG Var" if btts_pick_val else "KG Yok",
        btts_pct=round(btts_pct if btts_pick_val else (100 - btts_pct), 1),
        btts_hit=btts_hit,
        brier_score=round(brier, 4),
    )


def pct(hit: int, total: int) -> float:
    return round(hit / total * 100, 1) if total > 0 else 0.0


def brier_avg(brier_sum: float, count: int) -> float | None:
    return round(brier_sum / count, 4) if count > 0 else None


@dataclass
class EvalAccumulator:
    evaluated: int = 0
    result_hit: int = 0
    over_hit: int = 0
    btts_hit: int = 0
    confident_evaluated: int = 0
    confident_result_hit: int = 0
    brier_sum: float = 0.0

    def accumulate(self, pat: PatternEval | None) -> None:
        if pat is None:
            return
        self.evaluated += 1
        self.brier_sum += pat.brier_score
        if pat.result_hit:
            self.result_hit += 1
        if pat.over_25_hit:
            self.over_hit += 1
        if pat.btts_hit:
            self.btts_hit += 1
        if pat.is_confident:
            self.confident_evaluated += 1
            if pat.result_hit:
                self.confident_result_hit += 1

    def merge(self, other: EvalAccumulator) -> None:
        self.evaluated += other.evaluated
        self.result_hit += other.result_hit
        self.over_hit += other.over_hit
        self.btts_hit += other.btts_hit
        self.confident_evaluated += other.confident_evaluated
        self.confident_result_hit += other.confident_result_hit
        self.brier_sum += other.brier_sum
