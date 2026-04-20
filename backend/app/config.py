"""Uygulama yapılandırması.

Sprint 1'de minimal tutuyoruz. Sonraki sprint'lerde .env desteği eklenecek.
"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ScraperConfig:
    """Scraping ayarları."""

    # Nowgoal base URL
    base_url: str = "https://live5.nowgoal26.com"
    fixture_path: str = "/football/fixture"
    match_detail_path: str = "/match/h2h-{match_id}"

    # Browser ayarları
    headless: bool = True
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )

    # Timing (saniye)
    page_timeout: float = 30.0
    default_wait: float = 4.0
    between_requests: float = 2.5

    # Debug
    save_html_on_error: bool = True
    debug_dir: Path = field(default_factory=lambda: Path("debug_html"))


@dataclass(frozen=True)
class AnalysisConfig:
    """Analiz motoru ayarları."""

    # Kaç son maç analiz edilecek (sizin 'ANALİZ MAÇ SAYISI' sütunu)
    n_matches: int = 5

    # 3.5+ oran eşiği (sizin 'FILTER RATIO' sütunu)
    threshold: float = 3.5

    # Minimum H2H maç sayısı
    min_h2h: int = 5

    # Minimum lig maçı sayısı (takım başına)
    min_league_matches: int = 5


# Modül seviyesinde varsayılan örnekler
SCRAPER = ScraperConfig()
ANALYSIS = AnalysisConfig()
