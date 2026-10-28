"""Kural sürümü → parmak izi fonksiyonu (Sprint 94 C2): tek liste.

Her `*_RULE_VERSION` / `*_SHADOW_VERSION` sabiti burada olmalı; `tests/test_rule_registry.py` tüm modülleri tarar,
eksik ya da sabitlenmiş değerinden farklı parmak izi varsa kırılır → kural parametresi değişip sürüm artmazsa
fark edilir. Backtest seçicisindeki "güncel ayarlarla mı üretildi?" kontrolü de buradan okur.
"""

from __future__ import annotations

from typing import Callable


def fingerprints() -> dict[str, Callable[[], str]]:
    from app.analysis import (
        ht_value, live_2h, live_archive, live_model, live_poisson, market_summary_v3, prematch_ht, prematch_v4,
        prematch_v5, score_snapshots,
    )

    return {
        live_model.LIVE_RULE_VERSION: live_model.rule_params_fingerprint,
        live_archive.LIVE_ARCHIVE_RULE_VERSION: live_archive.rule_params_fingerprint,
        live_archive.LIVE_ARCHIVE_SHADOW_VERSION: live_archive.shadow_params_fingerprint,
        live_poisson.LIVE_POISSON_RULE_VERSION: live_poisson.rule_params_fingerprint,
        live_poisson.LIVE_POISSON_SHADOW_VERSION: live_poisson.shadow_params_fingerprint,
        live_2h.LIVE_2H_RULE_VERSION: live_2h.rule_params_fingerprint,
        prematch_v5.V5_RULE_VERSION: prematch_v5.rule_params_fingerprint,
        prematch_v4.V4_RULE_VERSION: prematch_v4.rule_params_fingerprint,
        prematch_v4.MARKET_SUMMARY_RULE_VERSION: prematch_v4.market_summary_fingerprint,
        market_summary_v3.MARKET_SUMMARY_SHADOW_VERSION: market_summary_v3.fingerprint,
        prematch_ht.HT_RULE_VERSION: prematch_ht.rule_params_fingerprint,
        ht_value.HT_VALUE_RULE_VERSION: ht_value.rule_params_fingerprint,
        score_snapshots.SCORE_RULE_VERSION: score_snapshots.rule_params_fingerprint,
    }


def fingerprint_of(rule_version: str) -> str | None:
    fn = fingerprints().get(rule_version)
    return fn() if fn is not None else None
