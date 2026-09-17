"""Tarihsel veri onarımı — sorunlu kayıt tespit fonksiyonları (Sprint 20).

CLI komutu `repair-archive` bu modülün fonksiyonlarını kullanır.
Pure fonksiyonlar: DB bağımlılığı yok, test edilebilir.
"""

from __future__ import annotations

from typing import Any

from app.analysis.league_filter import canonical_league_name, is_supported_league


def detect_issues(row: dict[str, Any]) -> tuple[str, str] | None:
    """Tek bir maç kaydında sorun tespit et.

    Returns:
        (reason, detail) tuple'ı veya None (sorun yoksa).
    """
    home = row.get("home_team", "")
    away = row.get("away_team", "")
    label = f"{home} vs {away}"

    # 1. Boş/geçersiz takım
    if not home or str(home).strip() in ("", "?"):
        return "empty_team", f"home_team='{home}'"
    if not away or str(away).strip() in ("", "?"):
        return "empty_team", f"away_team='{away}'"

    # 2. Kupa/turnuva
    league_code = row.get("league_code")
    league_name = row.get("league_name")
    if not is_supported_league(league_name, league_code):
        return "non_league", f"league={league_code or league_name}"

    # 3. Skor aralık kontrolü (negatif veya >15)
    for field in ("actual_ft_home", "actual_ft_away",
                  "actual_ht_home", "actual_ht_away",
                  "actual_h2_home", "actual_h2_away"):
        val = row.get(field)
        if val is not None and (val < 0 or val > 15):
            return "bad_score", f"{field}={val} ({label})"

    # 4. Tutarsız yarılar: İY > MS
    ht_home = row.get("actual_ht_home")
    ft_home = row.get("actual_ft_home")
    if ht_home is not None and ft_home is not None and ht_home > ft_home:
        return "inconsistent_half", f"ht_home={ht_home} > ft_home={ft_home} ({label})"

    ht_away = row.get("actual_ht_away")
    ft_away = row.get("actual_ft_away")
    if ht_away is not None and ft_away is not None and ht_away > ft_away:
        return "inconsistent_half", f"ht_away={ht_away} > ft_away={ft_away} ({label})"

    return None


def needs_normalization(league_code: str | None, league_name: str | None) -> bool:
    """Lig adı kanonik formdan farklıysa True."""
    if league_code and canonical_league_name(league_code) != league_code:
        return True
    if league_name and canonical_league_name(league_name) != league_name:
        return True
    return False
