"""Config (config.py) birim testleri.

Env override, default değerler, tip dönüşümleri.
"""

from __future__ import annotations

import pytest

from app.config import _env_bool, _env_float, _env_int


# ─── _env_float ─────────────────────────────────────────────────────────────

class TestEnvFloat:
    def test_default_when_missing(self, monkeypatch):
        monkeypatch.delenv("TEST_FLOAT", raising=False)
        assert _env_float("TEST_FLOAT", 3.5) == 3.5

    def test_override(self, monkeypatch):
        monkeypatch.setenv("TEST_FLOAT", "7.2")
        assert _env_float("TEST_FLOAT", 3.5) == 7.2

    def test_integer_string(self, monkeypatch):
        monkeypatch.setenv("TEST_FLOAT", "10")
        assert _env_float("TEST_FLOAT", 1.0) == 10.0

    def test_empty_string_uses_default(self, monkeypatch):
        monkeypatch.setenv("TEST_FLOAT", "")
        assert _env_float("TEST_FLOAT", 5.0) == 5.0


# ─── _env_int ───────────────────────────────────────────────────────────────

class TestEnvInt:
    def test_default_when_missing(self, monkeypatch):
        monkeypatch.delenv("TEST_INT", raising=False)
        assert _env_int("TEST_INT", 5) == 5

    def test_override(self, monkeypatch):
        monkeypatch.setenv("TEST_INT", "12")
        assert _env_int("TEST_INT", 5) == 12

    def test_empty_string_uses_default(self, monkeypatch):
        monkeypatch.setenv("TEST_INT", "")
        assert _env_int("TEST_INT", 3) == 3


# ─── _env_bool ──────────────────────────────────────────────────────────────

class TestEnvBool:
    def test_default_true(self, monkeypatch):
        monkeypatch.delenv("TEST_BOOL", raising=False)
        assert _env_bool("TEST_BOOL", True) is True

    def test_default_false(self, monkeypatch):
        monkeypatch.delenv("TEST_BOOL", raising=False)
        assert _env_bool("TEST_BOOL", False) is False

    def test_true_values(self, monkeypatch):
        for val in ("1", "true", "True", "TRUE", "yes", "Yes", "YES"):
            monkeypatch.setenv("TEST_BOOL", val)
            assert _env_bool("TEST_BOOL", False) is True, f"Failed for {val}"

    def test_false_values(self, monkeypatch):
        for val in ("0", "false", "False", "no", "No", "anything"):
            monkeypatch.setenv("TEST_BOOL", val)
            assert _env_bool("TEST_BOOL", True) is False, f"Failed for {val}"

    def test_none_returns_default(self, monkeypatch):
        monkeypatch.delenv("TEST_BOOL", raising=False)
        assert _env_bool("TEST_BOOL", True) is True
        assert _env_bool("TEST_BOOL", False) is False


# ─── ScraperConfig defaults ────────────────────────────────────────────────

class TestScraperConfigDefaults:
    def test_default_headless(self, monkeypatch):
        monkeypatch.delenv("SCRAPER_HEADLESS", raising=False)
        from app.config import ScraperConfig
        cfg = ScraperConfig()
        assert cfg.headless is True

    def test_override_headless(self, monkeypatch):
        monkeypatch.setenv("SCRAPER_HEADLESS", "false")
        from app.config import ScraperConfig
        cfg = ScraperConfig()
        assert cfg.headless is False

    def test_default_timeout(self, monkeypatch):
        monkeypatch.delenv("SCRAPER_TIMEOUT", raising=False)
        from app.config import ScraperConfig
        cfg = ScraperConfig()
        assert cfg.page_timeout == 30.0

    def test_override_timeout(self, monkeypatch):
        monkeypatch.setenv("SCRAPER_TIMEOUT", "15")
        from app.config import ScraperConfig
        cfg = ScraperConfig()
        assert cfg.page_timeout == 15.0

    def test_default_base_url(self, monkeypatch):
        monkeypatch.delenv("SCRAPER_BASE_URL", raising=False)
        from app.config import ScraperConfig
        cfg = ScraperConfig()
        assert "nowgoal" in cfg.base_url

    def test_override_base_url(self, monkeypatch):
        monkeypatch.setenv("SCRAPER_BASE_URL", "https://test.example.com")
        from app.config import ScraperConfig
        cfg = ScraperConfig()
        assert cfg.base_url == "https://test.example.com"

    def test_frozen_dataclass(self):
        from app.config import ScraperConfig
        cfg = ScraperConfig()
        with pytest.raises(AttributeError):
            cfg.headless = False


# ─── AnalysisConfig defaults ───────────────────────────────────────────────

class TestAnalysisConfigDefaults:
    def test_default_n_matches(self, monkeypatch):
        monkeypatch.delenv("ANALYSIS_N_MATCHES", raising=False)
        from app.config import AnalysisConfig
        cfg = AnalysisConfig()
        assert cfg.n_matches == 5

    def test_override_n_matches(self, monkeypatch):
        monkeypatch.setenv("ANALYSIS_N_MATCHES", "10")
        from app.config import AnalysisConfig
        cfg = AnalysisConfig()
        assert cfg.n_matches == 10

    def test_default_threshold(self, monkeypatch):
        monkeypatch.delenv("ANALYSIS_THRESHOLD", raising=False)
        from app.config import AnalysisConfig
        cfg = AnalysisConfig()
        assert cfg.threshold == 3.5

    def test_override_threshold(self, monkeypatch):
        monkeypatch.setenv("ANALYSIS_THRESHOLD", "4.0")
        from app.config import AnalysisConfig
        cfg = AnalysisConfig()
        assert cfg.threshold == 4.0

    def test_default_min_h2h(self, monkeypatch):
        monkeypatch.delenv("ANALYSIS_MIN_H2H", raising=False)
        from app.config import AnalysisConfig
        cfg = AnalysisConfig()
        assert cfg.min_h2h == 5

    def test_frozen_dataclass(self):
        from app.config import AnalysisConfig
        cfg = AnalysisConfig()
        with pytest.raises(AttributeError):
            cfg.n_matches = 99
