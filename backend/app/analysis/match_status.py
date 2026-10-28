"""Maçın kaynaktaki son durumu (bitti / ertelendi / iptal ...) — defter ve kupon geçersizlik kuralları için.

`update-scores` gördüğü durumu bülten önbelleğine (`fixture_cache.matches_json[].score_status`) yazar;
burada her maç için listeden düşmemiş (carried olmayan) en son kayıt okunur (Sprint 94 B2).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import text

LOOKBACK_DAYS = 60

_STATUS_SQL = text("""
    SELECT f.cached_at, e->>'match_id' AS match_id, e->>'score_status' AS status
    FROM fixture_cache f, jsonb_array_elements(f.matches_json) e
    WHERE f.date >= :since
      AND e->>'match_id' = ANY(:ids)
      AND coalesce(e->>'carried', 'false') <> 'true'
      AND e->>'score_status' IS NOT NULL
""")


async def fixture_statuses(session, match_ids: list[str], now: datetime | None = None) -> dict[str, str]:
    """{match_id: son durum}; hiç durum görülmemiş maç sözlükte yok."""
    if not match_ids:
        return {}
    since = ((now or datetime.now(timezone.utc)) - timedelta(days=LOOKBACK_DAYS)).date().isoformat()
    rows = (await session.execute(_STATUS_SQL, {"since": since, "ids": list(match_ids)})).all()
    latest: dict[str, tuple] = {}
    for cached_at, match_id, status in rows:
        if match_id not in latest or cached_at > latest[match_id][0]:
            latest[match_id] = (cached_at, status)
    return {mid: status for mid, (_, status) in latest.items()}
