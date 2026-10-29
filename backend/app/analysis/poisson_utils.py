"""Poisson olasılık yardımcıları — canlı model, maç öncesi v5 ve İY tahmini ortak (Sprint 94 M5: 3 kopya vardı)."""

from __future__ import annotations

import math


def pmf(lam: float, n: int, *, tail: bool) -> list[float]:
    """P(k) k=0..n-1; `tail=True` ise son hücreye kalan olasılık (≥n) eklenir (toplam 1). `tail=False`: k=0..n."""
    if tail:
        probs = [math.exp(-lam) * lam ** k / math.factorial(k) for k in range(n)]
        probs.append(max(0.0, 1.0 - sum(probs)))
        return probs
    return [math.exp(-lam) * lam ** k / math.factorial(k) for k in range(n + 1)]
