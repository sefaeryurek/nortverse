"""Nowgoal26 scraping modülü."""

from app.scraper.fixture import fetch_fixture, fetch_leagues
from app.scraper.match_detail import fetch_match_detail

__all__ = ["fetch_fixture", "fetch_leagues", "fetch_match_detail"]
