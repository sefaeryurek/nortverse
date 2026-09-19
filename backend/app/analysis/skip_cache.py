"""Short lived, shared cache for analyses rejected by the input filters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.db.connection import get_session
from app.db.models import SkippedAnalysis
from app.models import MatchRawData, SkipReason


# Günlük pipeline saatlerce gecikebilir; filtre sonucu akşam bülteninde
# geçerli kalsın, ertesi günkü çalışmada yenilensin.
SKIP_CACHE_TTL = timedelta(hours=24)


@dataclass(frozen=True)
class SkipSnapshot:
    match_id: str
    home_team: str
    away_team: str
    league_code: str
    reason: str


async def get_recent_skip(match_id: str) -> SkipSnapshot | None:
    cutoff = datetime.now(timezone.utc) - SKIP_CACHE_TTL
    async with get_session() as session:
        row = (await session.execute(
            select(
                SkippedAnalysis.match_id,
                SkippedAnalysis.home_team,
                SkippedAnalysis.away_team,
                SkippedAnalysis.league_code,
                SkippedAnalysis.reason,
            ).where(
                SkippedAnalysis.match_id == match_id,
                SkippedAnalysis.checked_at >= cutoff,
            )
        )).one_or_none()
    if row is None:
        return None
    return SkipSnapshot(row.match_id, row.home_team, row.away_team,
                        row.league_code or "", row.reason)


async def save_skip(raw: MatchRawData, reason: SkipReason) -> None:
    # A failed parse can recover on the next scrape; do not make it sticky.
    if reason == SkipReason.DATA_FETCH_FAILED:
        return
    values = {
        "match_id": raw.match_id,
        "home_team": raw.home_team,
        "away_team": raw.away_team,
        "league_code": raw.league_code,
        "reason": reason.value,
        "checked_at": datetime.now(timezone.utc),
    }
    stmt = insert(SkippedAnalysis).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[SkippedAnalysis.match_id],
        set_={key: value for key, value in values.items() if key != "match_id"},
    )
    async with get_session() as session:
        await session.execute(stmt)
