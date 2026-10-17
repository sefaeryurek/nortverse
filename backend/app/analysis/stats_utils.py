"""Ortak istatistik yardımcıları — performans paneli ve v3 doğrulama birlikte kullanır."""

from __future__ import annotations

import math


def wilson_ci(successes: int, trials: int, z: float = 1.96) -> tuple[float, float] | None:
    """İsabet oranı için %95 Wilson güven aralığı (0..1)."""
    if trials <= 0:
        return None
    p = successes / trials
    z2 = z * z
    denom = 1 + z2 / trials
    center = p + z2 / (2 * trials)
    spread = z * math.sqrt(p * (1 - p) / trials + z2 / (4 * trials * trials))
    return max(0.0, (center - spread) / denom), min(1.0, (center + spread) / denom)


def paired_coverage_interval(model_only: int, baseline_only: int, paired: int) -> tuple[float, float, float] | None:
    """Distribution-free 95% interval for paired coverage difference."""
    if paired <= 0:
        return None
    difference = 100.0 * (model_only - baseline_only) / paired
    # Paired difference is bounded in [-1, 1] (range width 2).
    half_width = 100.0 * math.sqrt(2.0 * math.log(40.0) / paired)
    return difference, max(-100.0, difference - half_width), min(100.0, difference + half_width)


def sample_stage(resolved: int) -> str:
    """Örneklem olgunluğu: <30 çok erken, <100 ön bulgu, aksi halde tam."""
    if resolved < 30:
        return "cok_erken"
    if resolved < 100:
        return "on_bulgu"
    return "tam"
