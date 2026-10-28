"""Kupon maçının tek kaynaktan okunması (Sprint 94 J6, K4): önce `matches`, yoksa bülten önbelleği.

Kupondaş artık analiz edilmemiş bülten maçlarını (kupa dahil) da kabul eder. Bu maçların `matches` satırı yok;
takım, lig, başlama saati ve sonuç `fixture_cache.matches_json`'dan okunur (`update-scores` bitmiş skoru ve İY
skorunu oraya da yazıyor — `runner._merge_fixture_scores`). Sahte (iskelet) `matches` satırı açılmaz: doğrulama,
temizlik ve onlarca sorgu o tabloyu "analiz edilmiş maç" sayıyor.

Bülten kaydı: listeden düşüp taşınmamış (carried olmayan), en son çekilen kayıt esas alınır (`match_status` ile aynı).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text

LOOKBACK_DAYS = 60

_FIXTURE_SQL = text("""
    SELECT f.cached_at, e AS item
    FROM fixture_cache f, jsonb_array_elements(f.matches_json) e
    WHERE f.date >= :since
      AND e->>'match_id' = ANY(:ids)
      AND coalesce(e->>'carried', 'false') <> 'true'
""")


@dataclass(frozen=True)
class MatchRef:
    match_id: str
    home_team: str
    away_team: str
    league_name: str | None
    kickoff_time: datetime | None
    source: str                       # 'db' (matches) | 'fixture' (sadece bülten)
    ft: tuple[int, int] | None = None  # maç sonu skoru (sadece kesin, 90 dk)
    ht: tuple[int, int] | None = None
    deleted: bool = False
    status: str | None = None          # bültenin son gördüğü durum (finished / live / postponed / abandoned …)


def _league(value) -> str | None:
    name = str(value or "").strip()
    return None if name in ("", "?") else name


def _kickoff(value) -> datetime | None:
    try:
        kickoff = datetime.fromisoformat(value) if value else None
    except (TypeError, ValueError):
        return None
    return kickoff if kickoff is None or kickoff.tzinfo is not None else kickoff.replace(tzinfo=timezone.utc)


def _pair(home, away) -> tuple[int, int] | None:
    return (int(home), int(away)) if home is not None and away is not None else None


def ref_from_fixture(item: dict) -> MatchRef | None:
    """Bülten kaydından maç bilgisi; takım adı yoksa None."""
    home, away = str(item.get("home_team") or "").strip(), str(item.get("away_team") or "").strip()
    if not item.get("match_id") or not home or not away:
        return None
    status = item.get("score_status")
    # Uzatmalı maçta kaynaktaki skor 90. dakika mı belli değil → kesin sonuç sayılmaz (runner ile aynı kural)
    ft = _pair(item.get("score_home"), item.get("score_away")) if status == "finished" else None
    return MatchRef(
        match_id=str(item["match_id"]), home_team=home, away_team=away,
        league_name=_league(item.get("league_name") or item.get("league_code")),
        kickoff_time=_kickoff(item.get("kickoff_time")), source="fixture", ft=ft,
        ht=_pair(item.get("actual_ht_home"), item.get("actual_ht_away")), status=status,
    )


async def latest_fixture_items(session, match_ids: list[str], now: datetime | None = None) -> dict[str, dict]:
    """{match_id: bültenin en son (carried olmayan) kaydı}."""
    if not match_ids:
        return {}
    since = ((now or datetime.now(timezone.utc)) - timedelta(days=LOOKBACK_DAYS)).date().isoformat()
    rows = (await session.execute(_FIXTURE_SQL, {"since": since, "ids": list(match_ids)})).all()
    latest: dict[str, tuple[datetime, dict]] = {}
    for cached_at, item in rows:
        mid = str(item.get("match_id"))
        if mid not in latest or cached_at > latest[mid][0]:
            latest[mid] = (cached_at, item)
    return {mid: item for mid, (_, item) in latest.items()}


async def load_match_refs(session, match_ids: list[str], now: datetime | None = None) -> dict[str, MatchRef]:
    """Maç bilgileri; `matches`'ta olan (silinmiş dahil, `deleted=True`) oradan, olmayan bültenden."""
    from app.db.models import Match

    ids = sorted({str(m) for m in match_ids})
    if not ids:
        return {}
    rows = (await session.execute(
        select(Match.match_id, Match.home_team, Match.away_team, Match.league_name, Match.kickoff_time,
               Match.actual_ft_home, Match.actual_ft_away, Match.actual_ht_home, Match.actual_ht_away,
               Match.deleted_at)
        .where(Match.match_id.in_(ids))
    )).all()
    items = await latest_fixture_items(session, ids, now)
    refs: dict[str, MatchRef] = {}
    for r in rows:
        refs[r.match_id] = MatchRef(
            match_id=r.match_id, home_team=r.home_team, away_team=r.away_team, league_name=r.league_name,
            kickoff_time=r.kickoff_time, source="db", ft=_pair(r.actual_ft_home, r.actual_ft_away),
            ht=_pair(r.actual_ht_home, r.actual_ht_away), deleted=r.deleted_at is not None,
            status=(items.get(r.match_id) or {}).get("score_status"),
        )
    for mid, item in items.items():
        if mid not in refs and (ref := ref_from_fixture(item)) is not None:
            refs[mid] = ref
    return refs
