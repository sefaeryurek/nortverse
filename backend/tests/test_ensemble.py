"""Ensemble meta-model testleri (Sprint 81)."""

import math
import tempfile
from pathlib import Path

import pytest
import numpy as np

from app.analysis.ensemble import (
    EnsembleModels,
    EnsemblePrediction,
    build_result_features,
    build_ou_features,
    build_btts_features,
    train_ensemble,
    save_models,
    load_models,
    predict,
)


def _pattern(r1=50.0, rx=25.0, r2=25.0, ou=55.0, kg=50.0, mc=30):
    return {
        "match_count": mc,
        "result_1_pct": r1, "result_x_pct": rx, "result_2_pct": r2,
        "ust_25_pct": ou, "alt_25_pct": 100 - ou,
        "kg_var_pct": kg, "kg_yok_pct": 100 - kg,
    }


# --- Feature extraction ---

class TestBuildFeatures:
    def test_result_features_shape(self):
        f = build_result_features(_pattern(), _pattern(), _pattern())
        assert f.shape == (12,)

    def test_result_features_with_none_pattern(self):
        f = build_result_features(_pattern(), None, _pattern())
        assert f.shape == (12,)
        assert f[4] != 0  # baz oran doldurulmuş

    def test_result_features_all_none(self):
        f = build_result_features(None, None, None)
        assert f.shape == (12,)
        assert all(v >= 0 for v in f)

    def test_ou_features_shape(self):
        f = build_ou_features(_pattern(), _pattern(), _pattern())
        assert f.shape == (6,)

    def test_btts_features_shape(self):
        f = build_btts_features(_pattern(), _pattern(), _pattern())
        assert f.shape == (6,)

    def test_match_count_included(self):
        f = build_result_features(_pattern(mc=42), None, None)
        assert f[3] == 42.0  # 4. eleman = B match_count

    def test_league_name_affects_base(self):
        f1 = build_result_features(None, None, None, league_name=None)
        f2 = build_result_features(None, None, None, league_name="German Bundesliga")
        assert not np.array_equal(f1, f2)


# --- Training ---

def _training_data(n=200):
    """Basit eğitim verisi üret."""
    import random
    random.seed(42)
    data = []
    for _ in range(n):
        r = random.choice(["1", "X", "2"])
        ft_h = random.randint(0, 4)
        ft_a = random.randint(0, 4)
        data.append({
            "pattern_ft_b": _pattern(
                r1=random.uniform(30, 60), rx=random.uniform(15, 35),
                r2=random.uniform(20, 50), ou=random.uniform(40, 70),
                kg=random.uniform(35, 65), mc=random.randint(10, 100),
            ),
            "pattern_ft_c": _pattern(
                r1=random.uniform(30, 60), rx=random.uniform(15, 35),
                r2=random.uniform(20, 50), ou=random.uniform(40, 70),
                kg=random.uniform(35, 65), mc=random.randint(5, 80),
            ),
            "pattern_ft_d": _pattern(
                r1=random.uniform(30, 60), rx=random.uniform(15, 35),
                r2=random.uniform(20, 50), ou=random.uniform(40, 70),
                kg=random.uniform(35, 65), mc=random.randint(5, 50),
            ),
            "actual_result": "1" if ft_h > ft_a else ("X" if ft_h == ft_a else "2"),
            "actual_over_25": (ft_h + ft_a) > 2,
            "actual_btts": ft_h > 0 and ft_a > 0,
            "league_name": "English Premier League",
        })
    return data


class TestTraining:
    def test_train_returns_models(self):
        models = train_ensemble(_training_data())
        assert isinstance(models, EnsembleModels)
        assert models.training_size >= 50

    def test_train_insufficient_data(self):
        with pytest.raises(ValueError, match="Yetersiz"):
            train_ensemble(_training_data(10), min_patterns=2)

    def test_train_skips_missing_patterns(self):
        data = _training_data(100)
        for d in data[:50]:
            d["pattern_ft_b"] = None
            d["pattern_ft_c"] = None
        models = train_ensemble(data, min_patterns=2)
        assert models.training_size < 100

    def test_result_model_has_three_classes(self):
        models = train_ensemble(_training_data())
        assert set(models.result_model.classes_) == {"1", "X", "2"}


# --- Prediction ---

class TestPrediction:
    @pytest.fixture
    def models(self):
        return train_ensemble(_training_data(300))

    def test_predict_returns_prediction(self, models):
        pred = predict(models, _pattern(60, 20, 20), _pattern(55, 25, 20), _pattern(50, 25, 25))
        assert isinstance(pred, EnsemblePrediction)
        assert pred.result_pick in ("1", "X", "2")
        assert 0 <= pred.result_margin <= 100
        assert 0 <= pred.over_25_prob <= 100
        assert 0 <= pred.btts_prob <= 100

    def test_predict_probs_sum_to_100(self, models):
        pred = predict(models, _pattern(), _pattern(), _pattern())
        total = sum(pred.result_probs.values())
        assert abs(total - 100.0) < 1.0

    def test_predict_with_none_patterns(self, models):
        pred = predict(models, None, None, None)
        assert isinstance(pred, EnsemblePrediction)

    def test_predict_confident_flag(self, models):
        pred = predict(models, _pattern(80, 10, 10), _pattern(75, 15, 10), _pattern(70, 15, 15))
        assert isinstance(pred.is_confident, bool)

    def test_predict_ou_pick(self, models):
        pred = predict(models, _pattern(ou=80), _pattern(ou=75), _pattern(ou=70))
        assert pred.over_25_pick in ("over", "under")

    def test_predict_btts_pick(self, models):
        pred = predict(models, _pattern(kg=80), _pattern(kg=75), _pattern(kg=70))
        assert pred.btts_pick in ("yes", "no")


# --- Save/Load ---

class TestPersistence:
    def test_save_and_load(self):
        models = train_ensemble(_training_data())
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_model.joblib"
            save_models(models, path)
            loaded = load_models(path)
            assert loaded is not None
            assert loaded.training_size == models.training_size
            assert loaded.version == models.version

    def test_load_nonexistent(self):
        result = load_models(Path("/nonexistent/model.joblib"))
        assert result is None

    def test_save_creates_dirs(self):
        models = train_ensemble(_training_data())
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "subdir" / "deep" / "model.joblib"
            save_models(models, path)
            assert path.exists()

    def test_loaded_model_predicts_same(self):
        models = train_ensemble(_training_data(200))
        pb, pc, pd = _pattern(55, 25, 20), _pattern(50, 30, 20), _pattern(45, 25, 30)
        pred_before = predict(models, pb, pc, pd)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "model.joblib"
            save_models(models, path)
            loaded = load_models(path)
            pred_after = predict(loaded, pb, pc, pd)

        assert pred_before.result_pick == pred_after.result_pick
        assert abs(pred_before.result_margin - pred_after.result_margin) < 0.01
