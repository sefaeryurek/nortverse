"""Uygulama yapılandırması.

Tüm değerler env var ile override edilebilir. Env var yoksa mevcut default kullanılır.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path


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


SCRAPER = ScraperConfig()
ANALYSIS = AnalysisConfig()
