"""Isotonic regression ile confidence kalibrasyonu.

Ham shrinkage yüzdelerini gerçek olasılıklara dönüştürür:
  shrunk_pct → isotonic → calibrated_pct

Eğitim: tarihsel (shrunk_pct, hit) çiftlerinden öğrenir.
Tahmin: calibrate_pattern() sonrası uygulanır.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
from sklearn.isotonic import IsotonicRegression

from app.analysis.evaluation import _shrink_pct, get_base_rates
from app.config import ANALYSIS

log = logging.getLogger(__name__)


@dataclass
class CalibratorModels:
    result: IsotonicRegression
    over_25: IsotonicRegression
    btts: IsotonicRegression
    training_size: int
    version: str = "v1"


def _compute_shrunk_result(
    pattern: dict,
    league_name: str | None,
) -> tuple[str, float]:
    """Pattern'den result shrunk pct hesapla — calibrate_pattern ile aynı mantık."""
    base = get_base_rates(league_name)
    mc = pattern.get("match_count", 0)
    shrink = ANALYSIS.result_shrinkage / (1 + mc / ANALYSIS.shrinkage_half_life)

    pcts = {
        "1": pattern.get("result_1_pct", 0) or 0,
        "X": pattern.get("result_x_pct", 0) or 0,
        "2": pattern.get("result_2_pct", 0) or 0,
    }
    adj = {k: _shrink_pct(v, base[k], shrink) for k, v in pcts.items()}
    best = max(adj, key=lambda k: adj[k])
    return best, adj[best]


def _compute_shrunk_ou(
    pattern: dict,
    league_name: str | None,
) -> tuple[str, float]:
    """Pattern'den O/U shrunk pct hesapla."""
    base = get_base_rates(league_name)
    mc = pattern.get("match_count", 0)
    shrink = ANALYSIS.result_shrinkage / (1 + mc / ANALYSIS.shrinkage_half_life)
    ou_base = base.get("ou25", ANALYSIS.over_25_base_rate)
    raw = pattern.get("ust_25_pct", 0) or 0
    cal = _shrink_pct(raw, ou_base, shrink)
    is_over = cal > ou_base
    return ("over" if is_over else "under"), (cal if is_over else 100 - cal)


def _compute_shrunk_btts(
    pattern: dict,
    league_name: str | None,
) -> tuple[str, float]:
    """Pattern'den BTTS shrunk pct hesapla."""
    base = get_base_rates(league_name)
    mc = pattern.get("match_count", 0)
    shrink = ANALYSIS.result_shrinkage / (1 + mc / ANALYSIS.shrinkage_half_life)
    btts_base = base.get("btts", ANALYSIS.btts_base_rate)
    raw = pattern.get("kg_var_pct", 0) or 0
    cal = _shrink_pct(raw, btts_base, shrink)
    is_btts = cal > btts_base
    return ("yes" if is_btts else "no"), (cal if is_btts else 100 - cal)


def train_calibrator(
    rows: list[dict],
    min_patterns: int = 1,
    min_matches_per_pattern: int = 5,
) -> CalibratorModels:
    """Tarihsel veriden isotonic regression kalibratörleri eğit.

    rows: her biri pattern_ft_b, pattern_ft_c, pattern_ft_d,
          actual_result ("1"/"X"/"2"), actual_over_25 (bool),
          actual_btts (bool), league_name içeren dict listesi.

    Her pattern ayrı bir eğitim noktası üretir (B/C/D ayrı).
    """
    result_x: list[float] = []
    result_y: list[int] = []
    ou_x: list[float] = []
    ou_y: list[int] = []
    btts_x: list[float] = []
    btts_y: list[int] = []

    for row in rows:
        actual_result = row.get("actual_result")
        actual_ou = row.get("actual_over_25")
        actual_btts = row.get("actual_btts")
        league = row.get("league_name")

        for key in ("pattern_ft_b", "pattern_ft_c", "pattern_ft_d"):
            pat = row.get(key)
            if not isinstance(pat, dict):
                continue
            mc = pat.get("match_count", 0)
            if not isinstance(mc, int) or mc < min_matches_per_pattern:
                continue

            if actual_result in ("1", "X", "2"):
                pick, shrunk_pct = _compute_shrunk_result(pat, league)
                result_x.append(shrunk_pct)
                result_y.append(1 if pick == actual_result else 0)

            if actual_ou is not None:
                ou_pick, ou_pct = _compute_shrunk_ou(pat, league)
                ou_x.append(ou_pct)
                ou_y.append(1 if (ou_pick == "over") == actual_ou else 0)

            if actual_btts is not None:
                btts_pick, btts_pct = _compute_shrunk_btts(pat, league)
                btts_x.append(btts_pct)
                btts_y.append(1 if (btts_pick == "yes") == actual_btts else 0)

    if len(result_y) < 100:
        raise ValueError(f"Yetersiz eğitim verisi: {len(result_y)} veri noktası (min 100)")

    result_model = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
    result_model.fit(np.array(result_x), np.array(result_y))

    ou_model = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
    ou_model.fit(np.array(ou_x), np.array(ou_y))

    btts_model = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
    btts_model.fit(np.array(btts_x), np.array(btts_y))

    log.info(
        "Kalibratör eğitim tamamlandı: %d result, %d O/U, %d BTTS veri noktası",
        len(result_y), len(ou_y), len(btts_y),
    )

    return CalibratorModels(
        result=result_model,
        over_25=ou_model,
        btts=btts_model,
        training_size=len(result_y),
    )


def save_calibrator(models: CalibratorModels, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(models, path)
    log.info("Kalibratör kaydedildi: %s", path)


def load_calibrator(path: str | Path) -> CalibratorModels | None:
    path = Path(path)
    if not path.exists():
        return None
    try:
        models = joblib.load(path)
        if not isinstance(models, CalibratorModels):
            log.warning("Kalibratör dosyası geçersiz format: %s", path)
            return None
        return models
    except Exception:
        log.warning("Kalibratör dosyası yüklenemedi: %s", path, exc_info=True)
        return None


# Çalışma dizininden bağımsız: backend/models/calibrator.joblib (CALIBRATOR_PATH ile değiştirilebilir).
_DEFAULT_PATH = Path(
    os.environ.get("CALIBRATOR_PATH")
    or Path(__file__).resolve().parents[2] / "models" / "calibrator.joblib"
)
_cached_calibrator: CalibratorModels | None = None
_cache_checked: bool = False


def get_default_calibrator() -> CalibratorModels | None:
    """Varsayılan kalibratörü yükle (lazy, bir kez)."""
    global _cached_calibrator, _cache_checked
    if _cache_checked:
        return _cached_calibrator
    _cache_checked = True
    _cached_calibrator = load_calibrator(_DEFAULT_PATH)
    if _cached_calibrator:
        log.info("Varsayılan kalibratör yüklendi: %d veri noktasıyla eğitilmiş", _cached_calibrator.training_size)
    return _cached_calibrator


def reset_calibrator_cache() -> None:
    """Test veya yeniden yükleme için cache'i sıfırla."""
    global _cached_calibrator, _cache_checked
    _cached_calibrator = None
    _cache_checked = False


def apply_calibration(
    shrunk_pct: float,
    market: str,
    calibrator: CalibratorModels,
) -> float:
    """Shrunk yüzdeyi isotonic regression ile kalibre et.

    Returns: kalibre edilmiş yüzde (0-100).
    """
    model = {
        "result": calibrator.result,
        "over_25": calibrator.over_25,
        "btts": calibrator.btts,
    }.get(market)

    if model is None:
        return shrunk_pct

    calibrated = float(model.predict(np.array([shrunk_pct]))[0])
    return round(calibrated * 100, 1)
