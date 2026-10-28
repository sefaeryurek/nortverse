"""Uygulama yapılandırması.

Tüm değerler env var ile override edilebilir. Env var yoksa mevcut default kullanılır.
"""

import os
from dataclasses import dataclass, field
from datetime import timedelta, timezone
from pathlib import Path

ISTANBUL_TZ = timezone(timedelta(hours=3))


def _env_float(key: str, default: float) -> float:
    val = os.environ.get(key)
    return float(val) if val else default


def _env_int(key: str, default: int) -> int:
    val = os.environ.get(key)
    return int(val) if val else default


def _env_bool(key: str, default: bool) -> bool:
    val = os.environ.get(key)
    if val is None:
        return default
    return val.lower() in ("1", "true", "yes")


@dataclass(frozen=True)
class ScraperConfig:
    """Scraping ayarları."""

    base_url: str = field(default_factory=lambda: os.environ.get("SCRAPER_BASE_URL", "https://live5.nowgoal26.com"))
    fixture_path: str = "/football/fixture"
    match_detail_path: str = "/match/h2h-{match_id}"

    headless: bool = field(default_factory=lambda: _env_bool("SCRAPER_HEADLESS", True))
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )

    page_timeout: float = field(default_factory=lambda: _env_float("SCRAPER_TIMEOUT", 30.0))
    # Sprint 94 E9: aynı anda en fazla bu kadar Chromium (her biri ~300 MB) — tek kullanıcı / hata belleği bitirmesin
    playwright_max_concurrency: int = field(default_factory=lambda: _env_int("PLAYWRIGHT_MAX_CONCURRENCY", 2))
    # Oran uçları (düz HTTP): eşzamanlı istek ve saniyedeki istek sınırı — evin IP'si kaynakta engellenmesin
    odds_max_concurrency: int = field(default_factory=lambda: _env_int("ODDS_MAX_CONCURRENCY", 4))
    odds_requests_per_second: float = field(default_factory=lambda: _env_float("ODDS_REQUESTS_PER_SECOND", 1.0))
    default_wait: float = field(default_factory=lambda: _env_float("SCRAPER_WAIT", 4.0))
    save_html_on_error: bool = True
    debug_dir: Path = field(default_factory=lambda: Path("debug_html"))


@dataclass(frozen=True)
class AnalysisConfig:
    """Analiz motoru ayarları."""

    n_matches: int = field(default_factory=lambda: _env_int("ANALYSIS_N_MATCHES", 5))
    threshold: float = field(default_factory=lambda: _env_float("ANALYSIS_THRESHOLD", 3.5))
    min_h2h: int = field(default_factory=lambda: _env_int("ANALYSIS_MIN_H2H", 5))
    min_league_matches: int = field(default_factory=lambda: _env_int("ANALYSIS_MIN_LEAGUE_MATCHES", 5))
    # Sprint 91 Faz 4: A2 sabit ±1.0 (eski 0.5→1.0 uyarlamalı; karar vermediği için sade ve geniş liste)
    pattern_c_tolerance: float = field(default_factory=lambda: _env_float("PATTERN_C_TOLERANCE", 1.0))
    pattern_c_max_tolerance: float = field(default_factory=lambda: _env_float("PATTERN_C_MAX_TOLERANCE", 1.0))
    pattern_c_tolerance_step: float = field(default_factory=lambda: _env_float("PATTERN_C_TOLERANCE_STEP", 0.25))
    pattern_c_adaptive_min: int = field(default_factory=lambda: _env_int("PATTERN_C_ADAPTIVE_MIN", 3))
    eval_min_matches: int = field(default_factory=lambda: _env_int("EVAL_MIN_MATCHES", 5))
    result_shrinkage: float = field(default_factory=lambda: _env_float("RESULT_SHRINKAGE", 0.45))
    shrinkage_half_life: float = field(default_factory=lambda: _env_float("SHRINKAGE_HALF_LIFE", 15.0))
    result_min_margin: float = field(default_factory=lambda: _env_float("RESULT_MIN_MARGIN", 10.0))
    pattern_b_match_cap: int = field(default_factory=lambda: _env_int("PATTERN_B_MATCH_CAP", 150))
    pattern_c_match_cap: int = field(default_factory=lambda: _env_int("PATTERN_C_MATCH_CAP", 150))
    # Sprint 91 Faz 4: A3 = takım gücü (λ) uzayında aynı ligden en yakın K maç
    pattern_d_top_k: int = field(default_factory=lambda: _env_int("PATTERN_D_TOP_K", 200))
    pattern_d_min_matches: int = field(default_factory=lambda: _env_int("PATTERN_D_MIN_MATCHES", 10))
    temporal_decay_half_life_years: float = field(default_factory=lambda: _env_float("TEMPORAL_DECAY_HALF_LIFE", 3.0))
    min_archive_matches: int = field(default_factory=lambda: _env_int("MIN_ARCHIVE_MATCHES", 10))


SCRAPER = ScraperConfig()
ANALYSIS = AnalysisConfig()
