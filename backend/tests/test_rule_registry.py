"""Her kural sürümünün sabitlenmiş parmak izi var mı? (Sprint 94 C2)

Kural parametresi değişip sürüm artmazsa defterde aynı adla iki farklı kural birikir. Bu test `app/analysis`
altındaki tüm `*_RULE_VERSION` / `*_SHADOW_VERSION` sabitlerini tarar:
- her biri `rule_registry` listesinde olmalı,
- parmak izi aşağıdaki sabit değerle aynı olmalı.
Kırıldıysa: kuralı değiştirdiysen sürümü artır ve yeni sürümü buraya ekle (eski satır kalabilir).
"""

import re
from pathlib import Path

from app.analysis.rule_registry import fingerprints

PINNED = {
    "live-ms-v1": "ed8958ebf572",
    "live-arch-v2": "23cf009029b1",
    "live-arch-v2.1": "161c8d934efd",
    "live-poisson-v1.1": "bcfb140f66db",
    "live-poisson-v1.2": "1dd58b310735",
    "live-2h-v1.1": "5a6896243ca1",
    "live-cond-filter-v1": "bffbdc9eb23a",
    "ft-display-v5": "60715673e89e",
    "ft-display-v4.1": "6eb9a5a2aca8",
    "market-summary-v2": "538550936f14",
    "market-summary-v3": "acc785206c00",
    "ht-display-v1.1": "39fe438b9d24",
    "ht-value-v1": "87ceb4435a90",
    "score-list-v1": "2ccc0ba35378",
}
_CONST_RE = re.compile(r'^[A-Z0-9_]*(?:RULE|SHADOW)_VERSION\s*=\s*"([^"]+)"', re.MULTILINE)


def _declared_versions() -> set[str]:
    root = Path(__file__).resolve().parents[1] / "app" / "analysis"
    return {m.group(1) for path in root.glob("*.py") for m in _CONST_RE.finditer(path.read_text(encoding="utf-8"))}


def test_every_rule_version_has_pinned_fingerprint():
    declared = _declared_versions()
    registry = fingerprints()
    assert declared, "sürüm sabiti bulunamadı"
    assert declared - registry.keys() == set(), "rule_registry'de olmayan sürüm"
    actual = {version: fn() for version, fn in registry.items()}
    assert actual == PINNED


def test_shadow_versions_are_not_read_as_on_screen_versions():
    """Gölge sürümler ekranın okuduğu sürüm listelerinde olmamalı (kararlar iki kez görünür)."""
    from app.analysis import live_archive, live_poisson

    assert live_archive.LIVE_ARCHIVE_SHADOW_VERSION not in live_archive.LIVE_ARCHIVE_RULE_VERSIONS
    assert live_poisson.LIVE_POISSON_SHADOW_VERSION not in live_poisson.LIVE_POISSON_RULE_VERSIONS
