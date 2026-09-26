"""Pazar çiftleri arası korelasyon faktörleri.

İki yöntem:
1. Poisson modeli (λ_h=1.37, λ_a=1.12) ile teorik hesaplama — DB gerekmez
2. Arşiv verisinden gözlemlenen korelasyon — compute_from_matches()

Çıktı: {(outcome_a, outcome_b): float} sözlüğü.
corr > 1.0 → pozitif korelasyon (birlikte gerçekleşme beklentinin üstünde)
corr < 1.0 → negatif korelasyon
corr = 1.0 → bağımsız
"""

from __future__ import annotations


import math
from collections import defaultdict
from typing import Any


def _poisson_pmf(k: int, lam: float) -> float:
    return (lam ** k) * math.exp(-lam) / math.factorial(k)


OUTCOME_KEYS = [
    "result:1", "result:X", "result:2",
    "dc:1X", "dc:X2", "dc:12",
    "kg:KG Var", "kg:KG Yok",
    "ou_25:Üst 2.5", "ou_25:Alt 2.5",
    "ou_15:Üst 1.5", "ou_15:Alt 1.5",
    "ou_35:Üst 3.5", "ou_35:Alt 3.5",
    "fark:Ev 1 fark", "fark:Ev 2 fark", "fark:Ev 3+ fark",
    "fark:Berabere",
    "fark:Dep 1 fark", "fark:Dep 2 fark", "fark:Dep 3+ fark",
    "ev_05:Ev Üst 0.5", "ev_05:Ev Alt 0.5",
    "ev_15:Ev Üst 1.5", "ev_15:Ev Alt 1.5",
    "dep_05:Dep Üst 0.5", "dep_05:Dep Alt 0.5",
    "dep_15:Dep Üst 1.5", "dep_15:Dep Alt 1.5",
]


def _outcomes_for_score(h: int, a: int) -> set[str]:
    """Bir skor için hangi pazar sonuçları geçerli."""
    total = h + a
    diff = h - a
    out: set[str] = set()

    if h > a:
        out.add("result:1")
    elif h == a:
        out.add("result:X")
    else:
        out.add("result:2")

    if h >= a:
        out.add("dc:1X")
    if h <= a:
        out.add("dc:X2")
    if h != a:
        out.add("dc:12")

    if h > 0 and a > 0:
        out.add("kg:KG Var")
    else:
        out.add("kg:KG Yok")

    if total >= 3:
        out.add("ou_25:Üst 2.5")
    else:
        out.add("ou_25:Alt 2.5")

    if total >= 2:
        out.add("ou_15:Üst 1.5")
    else:
        out.add("ou_15:Alt 1.5")

    if total >= 4:
        out.add("ou_35:Üst 3.5")
    else:
        out.add("ou_35:Alt 3.5")

    if diff == 1:
        out.add("fark:Ev 1 fark")
    elif diff == 2:
        out.add("fark:Ev 2 fark")
    elif diff >= 3:
        out.add("fark:Ev 3+ fark")
    elif diff == 0:
        out.add("fark:Berabere")
    elif diff == -1:
        out.add("fark:Dep 1 fark")
    elif diff == -2:
        out.add("fark:Dep 2 fark")
    elif diff <= -3:
        out.add("fark:Dep 3+ fark")

    if h >= 1:
        out.add("ev_05:Ev Üst 0.5")
    else:
        out.add("ev_05:Ev Alt 0.5")
    if h >= 2:
        out.add("ev_15:Ev Üst 1.5")
    else:
        out.add("ev_15:Ev Alt 1.5")

    if a >= 1:
        out.add("dep_05:Dep Üst 0.5")
    else:
        out.add("dep_05:Dep Alt 0.5")
    if a >= 2:
        out.add("dep_15:Dep Üst 1.5")
    else:
        out.add("dep_15:Dep Alt 1.5")

    return out


def compute_poisson_correlations(
    lambda_h: float = 1.37,
    lambda_a: float = 1.12,
    max_goals: int = 8,
) -> dict[str, float]:
    """Poisson modeli ile teorik korelasyon faktörleri hesapla.

    Returns: {"result:1|kg:KG Var": 1.12, ...} — sadece 1.0'dan farklı olanlar.
    """
    marginal: dict[str, float] = defaultdict(float)
    joint: dict[str, float] = defaultdict(float)

    for h in range(max_goals + 1):
        ph = _poisson_pmf(h, lambda_h)
        for a in range(max_goals + 1):
            pa = _poisson_pmf(a, lambda_a)
            prob = ph * pa
            outcomes = _outcomes_for_score(h, a)

            for oc in outcomes:
                marginal[oc] += prob

            oc_list = sorted(outcomes)
            for i, oc_a in enumerate(oc_list):
                for oc_b in oc_list[i + 1:]:
                    key = f"{oc_a}|{oc_b}"
                    joint[key] += prob

    result: dict[str, float] = {}
    for key, jp in joint.items():
        oc_a, oc_b = key.split("|")
        pa = marginal.get(oc_a, 0)
        pb = marginal.get(oc_b, 0)
        if pa > 0 and pb > 0:
            corr = jp / (pa * pb)
            if abs(corr - 1.0) > 0.01:
                result[key] = round(corr, 3)

    return result


def compute_from_matches(
    matches: list[dict[str, Any]],
) -> dict[str, float]:
    """Gerçek arşiv verisinden korelasyon faktörleri hesapla.

    matches: [{"actual_ft_home": int, "actual_ft_away": int}, ...]
    """
    marginal: dict[str, int] = defaultdict(int)
    joint: dict[str, int] = defaultdict(int)
    total = 0

    for m in matches:
        h = m.get("actual_ft_home")
        a = m.get("actual_ft_away")
        if h is None or a is None:
            continue
        if not (0 <= h <= 30 and 0 <= a <= 30):
            continue

        total += 1
        outcomes = _outcomes_for_score(h, a)

        for oc in outcomes:
            marginal[oc] += 1

        oc_list = sorted(outcomes)
        for i, oc_a in enumerate(oc_list):
            for oc_b in oc_list[i + 1:]:
                key = f"{oc_a}|{oc_b}"
                joint[key] += 1

    if total < 100:
        return compute_poisson_correlations()

    result: dict[str, float] = {}
    for key, jc in joint.items():
        oc_a, oc_b = key.split("|")
        ca = marginal.get(oc_a, 0)
        cb = marginal.get(oc_b, 0)
        if ca > 0 and cb > 0:
            observed = jc / total
            expected = (ca / total) * (cb / total)
            corr = observed / expected
            if abs(corr - 1.0) > 0.01:
                result[key] = round(corr, 3)

    return result


def get_correction_factor(
    corr_table: dict[str, float],
    market_key_a: str,
    selection_a: str,
    market_key_b: str,
    selection_b: str,
) -> float:
    """İki pazar sonucu arasındaki düzeltme faktörünü bul."""
    oc_a = f"{market_key_a}:{selection_a}"
    oc_b = f"{market_key_b}:{selection_b}"

    if oc_a > oc_b:
        oc_a, oc_b = oc_b, oc_a

    key = f"{oc_a}|{oc_b}"
    return corr_table.get(key, 1.0)
