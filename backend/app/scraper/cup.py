"""Avrupa kupası sezon dosyası (Sprint 94 P4): `matchResult/json/{sezon}/c{id}_en.json`.

Lig dosyasından (s{id}) farklı: kupa turları `CupKindList`'te (ikinci alan 1 = lig/grup aşaması), maçlar
`ScheduleList`'te "G{tur_no}{grup}" anahtarlarıyla. Maç satırı: [maç_no, kupa_no, durum, "YYYY-AA-GG SS:DD"
(kaynak saati UTC+8), ev_no, dep_no, "MS", "İY", ...]; durum −1 = bitti. Takım adları `TeamList`'ten.

Sadece lig/grup aşaması alınır: eleme ve ön eleme turlarında uzatma/penaltı olabilir (kaynak skoru 90 dakika mı
belli değil) ve iki ayaklı eşleşmenin rövanşı farklı oynanır.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)

SOURCE_TZ = timezone(timedelta(hours=8))
FINISHED = -1
_SCORE_RE = re.compile(r"^(\d{1,2})-(\d{1,2})$")


def _score(value) -> tuple[int, int] | None:
    m = _SCORE_RE.match(str(value or "").strip())
    return (int(m.group(1)), int(m.group(2))) if m else None


def group_stage_kinds(data: dict) -> dict[str, str]:
    """Lig/grup aşaması tur numaraları → tur adı."""
    kinds = {}
    for kind in data.get("CupKindList") or []:
        if isinstance(kind, list) and len(kind) >= 3 and kind[1] == 1:
            kinds[str(kind[0])] = str(kind[2])
    return kinds


def parse_cup_season(data: dict, competition: str, season: str) -> list[dict]:
    """Bitmiş lig/grup aşaması maçları → cup_results satırları. Bozuk satırlar sayılıp atlanır."""
    if not isinstance(data, dict):
        return []
    kinds = group_stage_kinds(data)
    teams = {t[0]: str(t[1]) for t in data.get("TeamList") or [] if isinstance(t, list) and len(t) >= 2}
    rows, skipped = [], 0
    for key, matches in (data.get("ScheduleList") or {}).items():
        kind = next((k for k in kinds if str(key).startswith(f"G{k}")), None)
        if kind is None or not isinstance(matches, list):
            continue
        for m in matches:
            if not isinstance(m, list) or len(m) < 8 or m[2] != FINISHED:
                continue
            ft, ht = _score(m[6]), _score(m[7])
            home, away = teams.get(m[4]), teams.get(m[5])
            try:
                kickoff = datetime.strptime(str(m[3]), "%Y-%m-%d %H:%M").replace(tzinfo=SOURCE_TZ)
            except ValueError:
                kickoff = None
            if not (ft and ht and home and away and kickoff) or ht[0] > ft[0] or ht[1] > ft[1]:
                skipped += 1
                continue
            rows.append({
                "match_id": str(m[0]), "competition": competition, "season": season.replace("-", "/"),
                "round": kinds[kind], "kickoff_time": kickoff.astimezone(timezone.utc),
                "home_team": home, "away_team": away,
                "ht_home": ht[0], "ht_away": ht[1], "ft_home": ft[0], "ft_away": ft[1],
            })
    if skipped:
        log.warning("%s %s: %d bozuk satır atlandı", competition, season, skipped)
    return rows


async def fetch_cup_season(cup_id: int, competition: str, season: str, ctx=None) -> list[dict]:
    from app.scraper.league import _JSON_BASE, _fetch_json

    data = await _fetch_json(f"{_JSON_BASE}/{season}/c{cup_id}_en.json", ctx=ctx)
    return parse_cup_season(data, competition, season)
