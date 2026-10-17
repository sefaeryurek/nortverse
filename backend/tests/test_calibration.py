"""Isotonic regression kalibratör testleri."""

import math
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from app.analysis.calibration import (
    CalibratorModels,
    _compute_shrunk_btts,
    _compute_shrunk_ou,
    _compute_shrunk_result,
    apply_calibration,
    get_default_calibrator,
    load_calibrator,
    reset_calibrator_cache,
    save_calibrator,
    train_calibrator,
)


def _pattern(
    result_1: float = 45,
    result_x: float = 25,
    result_2: float = 30,
    ust_25: float = 55,
    kg_var: float = 50,
    count: int = 30,
) -> dict:
    return {
        "match_count": count,
        "result_1_pct": result_1,
        "result_x_pct": result_x,
        "result_2_pct": result_2,
        "ust_25_pct": ust_25,
        "kg_var_pct": kg_var,
        "alt_25_pct": 100 - ust_25,
        "kg_yok_pct": 100 - kg_var,
    }


def _training_rows(n: int = 200) -> list[dict]:
    """Basit eğitim verisi üret — shrunk pct yükseldikçe hit oranı artacak şekilde."""
    rows = []
    rng = np.random.RandomState(42)
    for i in range(n):
        r1 = 30 + rng.uniform(0, 40)
        rx = rng.uniform(10, 30)
        r2 = 100 - r1 - rx
        if r2 < 5:
            r2 = 5
            rx = 100 - r1 - r2

        if r1 > max(rx, r2):
            actual = "1" if rng.random() < (r1 / 100.0) else ("X" if rng.random() < 0.5 else "2")
        elif r2 > max(r1, rx):
            actual = "2" if rng.random() < (r2 / 100.0) else ("1" if rng.random() < 0.5 else "X")
        else:
            actual = "X" if rng.random() < 0.4 else ("1" if rng.random() < 0.5 else "2")

        ust = 40 + rng.uniform(0, 30)
        kg = 40 + rng.uniform(0, 30)
        total_goals = int(rng.poisson(2.5))
        ft_h = int(rng.poisson(1.3))
        ft_a = total_goals - ft_h if total_goals > ft_h else 0

        rows.append({
            "pattern_ft_b": _pattern(r1, rx, r2, ust, kg, count=30),
            "pattern_ft_c": _pattern(r1 + rng.uniform(-5, 5), rx, r2 + rng.uniform(-5, 5), ust, kg, count=25),
            "pattern_ft_d": None,
            "actual_result": actual,
            "actual_over_25": (ft_h + ft_a) > 2,
            "actual_btts": ft_h > 0 and ft_a > 0,
            "league_name": "English Premier League",
        })
    return rows


class TestShrunkComputation:
    def test_compute_shrunk_result(self):
        pat = _pattern(result_1=60, result_x=20, result_2=20)
        pick, pct = _compute_shrunk_result(pat, "English Premier League")
        assert pick == "1"
        assert 45 < pct < 60

    def test_compute_shrunk_result_away(self):
        pat = _pattern(result_1=15, result_x=20, result_2=65)
        pick, pct = _compute_shrunk_result(pat, None)
        assert pick == "2"
        assert 30 < pct < 65

    def test_compute_shrunk_ou(self):
        pat = _pattern(ust_25=70)
        pick, pct = _compute_shrunk_ou(pat, None)
        assert pick == "over"
        assert pct > 50

    def test_compute_shrunk_ou_under(self):
        pat = _pattern(ust_25=30)
        pick, pct = _compute_shrunk_ou(pat, None)
        assert pick == "under"
        assert pct > 50

    def test_compute_shrunk_btts(self):
        pat = _pattern(kg_var=70)
        pick, pct = _compute_shrunk_btts(pat, None)
        assert pick == "yes"
        assert pct > 50

    def test_compute_shrunk_btts_no(self):
        pat = _pattern(kg_var=30)
        pick, pct = _compute_shrunk_btts(pat, None)
        assert pick == "no"
        assert pct > 50


class TestTrainCalibrator:
    def test_trains_with_sufficient_data(self):
        rows = _training_rows(200)
        models = train_calibrator(rows)
        assert isinstance(models, CalibratorModels)
        assert models.training_size > 0
        assert models.version == "v1"

    def test_raises_on_insufficient_data(self):
        rows = _training_rows(10)
        for r in rows:
            r["pattern_ft_c"] = None
        with pytest.raises(ValueError, match="Yetersiz"):
            train_calibrator(rows, min_matches_per_pattern=5)

    def test_ignores_small_patterns(self):
        rows = _training_rows(200)
        for r in rows:
            if r["pattern_ft_b"]:
                r["pattern_ft_b"]["match_count"] = 2
        models = train_calibrator(rows, min_matches_per_pattern=5)
        assert models.training_size > 0

    def test_calibrator_output_range(self):
        rows = _training_rows(200)
        models = train_calibrator(rows)
        result = apply_calibration(50.0, "result", models)
        assert 0 <= result <= 100
        ou_result = apply_calibration(55.0, "over_25", models)
        assert 0 <= ou_result <= 100
        btts_result = apply_calibration(60.0, "btts", models)
        assert 0 <= btts_result <= 100


class TestApplyCalibration:
    def test_unknown_market_passthrough(self):
        rows = _training_rows(200)
        models = train_calibrator(rows)
        assert apply_calibration(42.5, "unknown_market", models) == 42.5

    def test_monotonicity(self):
        """Yüksek shrunk_pct → yüksek calibrated_pct (isotonic regression monoton)."""
        rows = _training_rows(500)
        models = train_calibrator(rows)
        prev = apply_calibration(30.0, "result", models)
        for pct in range(35, 75, 5):
            curr = apply_calibration(float(pct), "result", models)
            assert curr >= prev, f"{pct}% → {curr} < {prev} (monotonluk ihlali)"
            prev = curr


class TestSaveLoad:
    def test_roundtrip(self, tmp_path: Path):
        rows = _training_rows(200)
        models = train_calibrator(rows)
        path = tmp_path / "test_calibrator.joblib"
        save_calibrator(models, path)
        loaded = load_calibrator(path)
        assert loaded is not None
        assert loaded.training_size == models.training_size
        assert loaded.version == models.version
        original = apply_calibration(50.0, "result", models)
        reloaded = apply_calibration(50.0, "result", loaded)
        assert abs(original - reloaded) < 0.01

    def test_load_nonexistent(self, tmp_path: Path):
        assert load_calibrator(tmp_path / "nonexistent.joblib") is None

    def test_load_invalid_file(self, tmp_path: Path):
        path = tmp_path / "bad.joblib"
        path.write_text("not a model")
        assert load_calibrator(path) is None


class TestDefaultCalibrator:
    def setup_method(self):
        reset_calibrator_cache()

    def teardown_method(self):
        reset_calibrator_cache()

    def test_returns_none_when_no_model(self, tmp_path, monkeypatch):
        import app.analysis.calibration as calibration
        monkeypatch.setattr(calibration, "_DEFAULT_PATH", tmp_path / "yok.joblib")
        result = get_default_calibrator()
        assert result is None

    def test_caches_result(self):
        get_default_calibrator()
        with patch("app.analysis.calibration.load_calibrator") as mock:
            mock.return_value = None
            get_default_calibrator()
            mock.assert_not_called()


class TestCalibratePatternIntegration:
    def test_calibrate_pattern_without_calibrator(self):
        """Kalibratör yoksa mevcut davranış korunur."""
        from app.analysis.evaluation import calibrate_pattern
        pat = _pattern(result_1=60, result_x=20, result_2=20, ust_25=60, kg_var=55)
        picks = calibrate_pattern(pat, league_name=None, calibrator=None)
        assert len(picks) == 3
        assert picks[0].market == "result"

    def test_calibrate_pattern_with_calibrator(self):
        """Kalibratör varsa calibrated_pct değişir."""
        from app.analysis.evaluation import calibrate_pattern
        rows = _training_rows(300)
        models = train_calibrator(rows)

        pat = _pattern(result_1=60, result_x=20, result_2=20, ust_25=60, kg_var=55)
        picks_without = calibrate_pattern(pat, league_name=None, calibrator=None)
        picks_with = calibrate_pattern(pat, league_name=None, calibrator=models)

        assert picks_without[0].calibrated_pct != picks_with[0].calibrated_pct
        assert 0 < picks_with[0].calibrated_pct <= 100
