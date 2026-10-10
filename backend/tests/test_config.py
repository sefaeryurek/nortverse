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

    def test_default_pattern_c_tolerance(self, monkeypatch):
        monkeypatch.delenv("PATTERN_C_TOLERANCE", raising=False)
        from app.config import AnalysisConfig
        cfg = AnalysisConfig()
        assert cfg.pattern_c_tolerance == 0.5

    def test_override_pattern_c_tolerance(self, monkeypatch):
        monkeypatch.setenv("PATTERN_C_TOLERANCE", "1.0")
        from app.config import AnalysisConfig
        cfg = AnalysisConfig()
        assert cfg.pattern_c_tolerance == 1.0

    def test_default_pattern_c_max_tolerance(self, monkeypatch):
        monkeypatch.delenv("PATTERN_C_MAX_TOLERANCE", raising=False)
        from app.config import AnalysisConfig
        cfg = AnalysisConfig()
        assert cfg.pattern_c_max_tolerance == 1.0

    def test_override_pattern_c_max_tolerance(self, monkeypatch):
        monkeypatch.setenv("PATTERN_C_MAX_TOLERANCE", "1.5")
        from app.config import AnalysisConfig
        cfg = AnalysisConfig()
        assert cfg.pattern_c_max_tolerance == 1.5

    def test_default_pattern_c_tolerance_step(self, monkeypatch):
        monkeypatch.delenv("PATTERN_C_TOLERANCE_STEP", raising=False)
        from app.config import AnalysisConfig
        cfg = AnalysisConfig()
        assert cfg.pattern_c_tolerance_step == 0.25

    def test_default_pattern_c_adaptive_min(self, monkeypatch):
        monkeypatch.delenv("PATTERN_C_ADAPTIVE_MIN", raising=False)
        from app.config import AnalysisConfig
        cfg = AnalysisConfig()
        assert cfg.pattern_c_adaptive_min == 3

    def test_override_pattern_c_adaptive_min(self, monkeypatch):
        monkeypatch.setenv("PATTERN_C_ADAPTIVE_MIN", "5")
        from app.config import AnalysisConfig
        cfg = AnalysisConfig()
        assert cfg.pattern_c_adaptive_min == 5

    def test_default_eval_min_matches(self, monkeypatch):
        monkeypatch.delenv("EVAL_MIN_MATCHES", raising=False)
        from app.config import AnalysisConfig
        cfg = AnalysisConfig()
        assert cfg.eval_min_matches == 5

    def test_override_eval_min_matches(self, monkeypatch):
        monkeypatch.setenv("EVAL_MIN_MATCHES", "10")
        from app.config import AnalysisConfig
        cfg = AnalysisConfig()
        assert cfg.eval_min_matches == 10

    def test_default_pattern_b_match_cap(self, monkeypatch):
        monkeypatch.delenv("PATTERN_B_MATCH_CAP", raising=False)
        from app.config import AnalysisConfig
        cfg = AnalysisConfig()
        assert cfg.pattern_b_match_cap == 150

    def test_override_pattern_b_match_cap(self, monkeypatch):
        monkeypatch.setenv("PATTERN_B_MATCH_CAP", "200")
        from app.config import AnalysisConfig
        cfg = AnalysisConfig()
        assert cfg.pattern_b_match_cap == 200

    def test_default_pattern_c_match_cap(self, monkeypatch):
        monkeypatch.delenv("PATTERN_C_MATCH_CAP", raising=False)
        from app.config import AnalysisConfig
        cfg = AnalysisConfig()
        assert cfg.pattern_c_match_cap == 150

    def test_override_pattern_c_match_cap(self, monkeypatch):
        monkeypatch.setenv("PATTERN_C_MATCH_CAP", "100")
        from app.config import AnalysisConfig
        cfg = AnalysisConfig()
        assert cfg.pattern_c_match_cap == 100

    def test_default_pattern_d_top_n(self, monkeypatch):
        monkeypatch.delenv("PATTERN_D_TOP_N", raising=False)
        from app.config import AnalysisConfig
        cfg = AnalysisConfig()
        assert cfg.pattern_d_top_n == 20

    def test_override_pattern_d_top_n(self, monkeypatch):
        monkeypatch.setenv("PATTERN_D_TOP_N", "50")
        from app.config import AnalysisConfig
        cfg = AnalysisConfig()
        assert cfg.pattern_d_top_n == 50

    def test_default_pattern_d_min_similarity(self, monkeypatch):
        monkeypatch.delenv("PATTERN_D_MIN_SIMILARITY", raising=False)
        from app.config import AnalysisConfig
        cfg = AnalysisConfig()
        assert cfg.pattern_d_min_similarity == 0.85

    def test_override_pattern_d_min_similarity(self, monkeypatch):
        monkeypatch.setenv("PATTERN_D_MIN_SIMILARITY", "0.90")
        from app.config import AnalysisConfig
        cfg = AnalysisConfig()
        assert cfg.pattern_d_min_similarity == 0.90

    def test_default_temporal_decay_half_life(self, monkeypatch):
        monkeypatch.delenv("TEMPORAL_DECAY_HALF_LIFE", raising=False)
        from app.config import AnalysisConfig
        cfg = AnalysisConfig()
        assert cfg.temporal_decay_half_life_years == 3.0

    def test_override_temporal_decay_half_life(self, monkeypatch):
        monkeypatch.setenv("TEMPORAL_DECAY_HALF_LIFE", "5.0")
        from app.config import AnalysisConfig
        cfg = AnalysisConfig()
        assert cfg.temporal_decay_half_life_years == 5.0

    def test_frozen_dataclass(self):
        from app.config import AnalysisConfig
        cfg = AnalysisConfig()
        with pytest.raises(AttributeError):
            cfg.n_matches = 99
