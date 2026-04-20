"""Nowgoal26 scraping modülü."""

from app.scraper.fixture import fetch_fixture
from app.scraper.match_detail import fetch_match_detail

__all__ = ["fetch_fixture", "fetch_match_detail"]
