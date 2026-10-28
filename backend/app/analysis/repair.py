"""Tarihsel veri onarımı — sorunlu kayıt tespit fonksiyonları (Sprint 20).

CLI komutu `repair-archive` bu modülün fonksiyonlarını kullanır.
Pure fonksiyonlar: DB bağımlılığı yok, test edilebilir.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from app.analysis.league_filter import canonical_league_name, is_supported_league

# Sprint 94 B3 (K20) — grup kuralları
SEASON_CLOSED_AFTER = timedelta(days=30)   # sezonun son maçından bu kadar sonra skorsuz maç "iptal"
PLAYOFF_WINDOW = timedelta(days=30)        # sezonun son 30 gününde aynı ev-dep eşleşmesinin tekrarı = play-off
STRAY_MAX_ROWS = 3                         # eski bir lig-sezonunda ≤3 maç = arşiv değil, başıboş satır
STRAY_MIN_AGE = timedelta(days=365)
# Bu liglerde aynı eşleşmenin sezonda tekrarı normal (lig ikiye bölünüyor / play-off ligin parçası)
REPEAT_FORMAT_LEAGUES = frozenset({"Scottish Premiership", "Belgian Pro League"})


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


def detect_group_issues(rows: Iterable[dict[str, Any]], now: datetime | None = None) -> list[tuple[str, str, str]]:
    """Tek satıra bakarak görülmeyen sorunlar (lig + sezon grubu). Döner: (match_id, reason, detail).

    - `cancelled`: sezonu bitmiş (son maçı 30+ gün önce) ve skoru hiç gelmemiş maç (2019/20 COVID iptalleri)
    - `playoff`: sezonun son 30 gününde aynı ev-deplasman eşleşmesinin ikinci kez oynanması (Eredivisie
      Avrupa play-off'u, Championship play-off'u, 2011/12 Süper Final grubu) — normal lig maçı değil
    - `stray_season`: bir yıldan eski, ≤3 maçlık lig-sezonu (başka bir ligin arşivine karışmış tek satırlar)
    """
    now = now or datetime.now(timezone.utc)
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("kickoff_time") is None or not row.get("season"):
            continue
        groups[(row.get("league_name") or "", row["season"])].append(row)
    out: list[tuple[str, str, str]] = []
    for (league, season), items in groups.items():
        items.sort(key=lambda r: r["kickoff_time"])
        season_end = items[-1]["kickoff_time"]
        if len(items) <= STRAY_MAX_ROWS and season_end < now - STRAY_MIN_AGE:
            out += [(r["match_id"], "stray_season", f"{league} {season}: {len(items)} maç") for r in items]
            continue
        closed = season_end < now - SEASON_CLOSED_AFTER
        seen: set[tuple[str, str]] = set()
        for r in items:
            if r.get("actual_ft_home") is None:
                if closed:
                    out.append((r["match_id"], "cancelled", f"{league} {season}: skor yok, sezon bitti"))
                continue
            pair = (r.get("home_team"), r.get("away_team"))
            if (pair in seen and league not in REPEAT_FORMAT_LEAGUES
                    and r["kickoff_time"] >= season_end - PLAYOFF_WINDOW):
                out.append((r["match_id"], "playoff",
                            f"{league} {season}: {pair[0]} - {pair[1]} ikinci kez ({r['kickoff_time']:%Y-%m-%d})"))
            seen.add(pair)
    return out


def needs_normalization(league_code: str | None, league_name: str | None) -> bool:
    """Lig adı kanonik formdan farklıysa True."""
    if league_code and canonical_league_name(league_code) != league_code:
        return True
    if league_name and canonical_league_name(league_name) != league_name:
        return True
    return False


def compute_quality_score(
    *,
    total: int,
    active: int,
    non_league: int,
    missing_pattern: int,
    missing_actual: int,
    missing_trends: int,
    repair_candidates: int = 0,
    unnormalized: int = 0,
) -> float:
    """0-100 kalite skoru — CLI ve API ortak formülü."""
    if total == 0:
        return 0.0
    penalties = (
        (non_league / total) * 40
        + (missing_pattern / max(active, 1)) * 20
        + (missing_actual / max(active, 1)) * 30
        + (missing_trends / max(active, 1)) * 10
        + (repair_candidates / max(active, 1)) * 15
        + (unnormalized / max(active, 1)) * 5
    )
    return max(0.0, 100.0 - penalties)
