"""Ensemble meta-model: B+C+D pattern yüzdelerinden LogisticRegression ile tahmin."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from app.analysis.evaluation import get_base_rates

log = logging.getLogger(__name__)

_RESULT_FEATURES = [
    "result_1_pct", "result_x_pct", "result_2_pct",
]
_OU_FEATURE = "ust_25_pct"
_BTTS_FEATURE = "kg_var_pct"


@dataclass
class EnsemblePrediction:
    result_probs: dict[str, float]
    result_pick: str
    result_margin: float
    is_confident: bool
    over_25_prob: float
    over_25_pick: str
    btts_prob: float
    btts_pick: str


def _extract_pattern_features(
    pattern: dict | None,
    fields: list[str],
    base_rates: dict[str, float],
) -> list[float]:
    """Pattern'den feature'ları çıkar, eksikse baz oranları kullan."""
    if not isinstance(pattern, dict) or not pattern.get("match_count"):
        return [base_rates.get(f.replace("_pct", "").replace("result_", ""), 33.3) for f in fields]
    return [float(pattern.get(f, 0) or 0) for f in fields]


def build_result_features(
    pattern_b: dict | None,
    pattern_c: dict | None,
    pattern_d: dict | None,
    league_name: str | None = None,
) -> np.ndarray:
    """3 pattern'den 12 feature'lık vektör oluştur (result pazarı)."""
    base = get_base_rates(league_name)
    result_base = {"1": base["1"], "X": base.get("X", 24.9), "2": base["2"]}

    features = []
    for pat in (pattern_b, pattern_c, pattern_d):
        feats = _extract_pattern_features(pat, _RESULT_FEATURES, result_base)
        mc = pat.get("match_count", 0) if isinstance(pat, dict) else 0
        features.extend(feats)
        features.append(float(mc))

    return np.array(features, dtype=np.float64)


def build_ou_features(
    pattern_b: dict | None,
    pattern_c: dict | None,
    pattern_d: dict | None,
    league_name: str | None = None,
) -> np.ndarray:
    """3 pattern'den 6 feature'lık vektör oluştur (Üst/Alt 2.5 pazarı)."""
    base = get_base_rates(league_name)
    ou_base = base.get("ou25", 52.7)

    features = []
    for pat in (pattern_b, pattern_c, pattern_d):
        if isinstance(pat, dict) and pat.get("match_count"):
            features.append(float(pat.get(_OU_FEATURE, 0) or 0))
        else:
            features.append(ou_base)
        mc = pat.get("match_count", 0) if isinstance(pat, dict) else 0
        features.append(float(mc))

    return np.array(features, dtype=np.float64)


def build_btts_features(
    pattern_b: dict | None,
    pattern_c: dict | None,
    pattern_d: dict | None,
    league_name: str | None = None,
) -> np.ndarray:
    """3 pattern'den 6 feature'lık vektör oluştur (KG pazarı)."""
    base = get_base_rates(league_name)
    btts_base = base.get("btts", 53.2)

    features = []
    for pat in (pattern_b, pattern_c, pattern_d):
        if isinstance(pat, dict) and pat.get("match_count"):
            features.append(float(pat.get(_BTTS_FEATURE, 0) or 0))
        else:
            features.append(btts_base)
        mc = pat.get("match_count", 0) if isinstance(pat, dict) else 0
        features.append(float(mc))

    return np.array(features, dtype=np.float64)


@dataclass
class EnsembleModels:
    result_model: LogisticRegression
    result_scaler: StandardScaler
    ou_model: LogisticRegression
    ou_scaler: StandardScaler
    btts_model: LogisticRegression
    btts_scaler: StandardScaler
    training_size: int
    version: str = "v1"


def train_ensemble(
    rows: list[dict],
    min_patterns: int = 2,
) -> EnsembleModels:
    """Tarihsel veriden 3 model eğit (result, O/U, BTTS).

    rows: her biri pattern_ft_b, pattern_ft_c, pattern_ft_d,
          actual_result ("1"/"X"/"2"), actual_over_25 (bool),
          actual_btts (bool), league_name alanlarına sahip dict listesi.
    """
    result_X, result_y = [], []
    ou_X, ou_y = [], []
    btts_X, btts_y = [], []

    for row in rows:
        pb = row.get("pattern_ft_b")
        pc = row.get("pattern_ft_c")
        pd = row.get("pattern_ft_d")

        present = sum(1 for p in (pb, pc, pd) if isinstance(p, dict) and p.get("match_count", 0) >= 5)
        if present < min_patterns:
            continue

        league = row.get("league_name")
        actual_result = row.get("actual_result")
        actual_ou = row.get("actual_over_25")
        actual_btts = row.get("actual_btts")

        if actual_result in ("1", "X", "2"):
            result_X.append(build_result_features(pb, pc, pd, league))
            result_y.append(actual_result)

        if actual_ou is not None:
            ou_X.append(build_ou_features(pb, pc, pd, league))
            ou_y.append(1 if actual_ou else 0)

        if actual_btts is not None:
            btts_X.append(build_btts_features(pb, pc, pd, league))
            btts_y.append(1 if actual_btts else 0)

    if len(result_y) < 50:
        raise ValueError(f"Yetersiz eğitim verisi: {len(result_y)} maç (min 50)")

    result_scaler = StandardScaler()
    X_result = result_scaler.fit_transform(np.array(result_X))
    result_model = LogisticRegression(
        solver="lbfgs", max_iter=1000, C=1.0, random_state=42,
    )
    result_model.fit(X_result, result_y)

    ou_scaler = StandardScaler()
    X_ou = ou_scaler.fit_transform(np.array(ou_X))
    ou_model = LogisticRegression(solver="lbfgs", max_iter=1000, C=1.0, random_state=42)
    ou_model.fit(X_ou, ou_y)

    btts_scaler = StandardScaler()
    X_btts = btts_scaler.fit_transform(np.array(btts_X))
    btts_model = LogisticRegression(solver="lbfgs", max_iter=1000, C=1.0, random_state=42)
    btts_model.fit(X_btts, btts_y)

    log.info(
        "Ensemble eğitim tamamlandı: %d result, %d O/U, %d BTTS maç",
        len(result_y), len(ou_y), len(btts_y),
    )

    return EnsembleModels(
        result_model=result_model, result_scaler=result_scaler,
        ou_model=ou_model, ou_scaler=ou_scaler,
        btts_model=btts_model, btts_scaler=btts_scaler,
        training_size=len(result_y),
    )


def save_models(models: EnsembleModels, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(models, path)
    log.info("Ensemble modelleri kaydedildi: %s", path)


def load_models(path: str | Path) -> EnsembleModels | None:
    path = Path(path)
    if not path.exists():
        return None
    try:
        models = joblib.load(path)
        if not isinstance(models, EnsembleModels):
            log.warning("Model dosyası geçersiz format: %s", path)
            return None
        return models
    except Exception:
        log.warning("Model dosyası yüklenemedi: %s", path, exc_info=True)
        return None


def predict(
    models: EnsembleModels,
    pattern_b: dict | None,
    pattern_c: dict | None,
    pattern_d: dict | None,
    league_name: str | None = None,
    min_margin: float = 10.0,
) -> EnsemblePrediction:
    """Eğitilmiş ensemble ile tahmin üret."""
    X_result = models.result_scaler.transform(
        build_result_features(pattern_b, pattern_c, pattern_d, league_name).reshape(1, -1)
    )
    probs = models.result_model.predict_proba(X_result)[0]
    classes = models.result_model.classes_
    prob_dict = {str(c): round(float(p) * 100, 1) for c, p in zip(classes, probs)}

    sorted_probs = sorted(prob_dict.values(), reverse=True)
    margin = sorted_probs[0] - sorted_probs[1]
    result_pick = max(prob_dict, key=lambda k: prob_dict[k])

    X_ou = models.ou_scaler.transform(
        build_ou_features(pattern_b, pattern_c, pattern_d, league_name).reshape(1, -1)
    )
    ou_prob = float(models.ou_model.predict_proba(X_ou)[0][1]) * 100
    ou_pick = "over" if ou_prob > 50 else "under"

    X_btts = models.btts_scaler.transform(
        build_btts_features(pattern_b, pattern_c, pattern_d, league_name).reshape(1, -1)
    )
    btts_prob = float(models.btts_model.predict_proba(X_btts)[0][1]) * 100
    btts_pick = "yes" if btts_prob > 50 else "no"

    return EnsemblePrediction(
        result_probs=prob_dict,
        result_pick=result_pick,
        result_margin=round(margin, 1),
        is_confident=margin >= min_margin,
        over_25_prob=round(ou_prob, 1),
        over_25_pick=ou_pick,
        btts_prob=round(btts_prob, 1),
        btts_pick=btts_pick,
    )
