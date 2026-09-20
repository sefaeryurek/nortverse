"""One status decision shared by bulletin and results."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.scraper.fixture_scores import FixtureScore

LIVE_FRESH_SECONDS = 120


@dataclass(frozen=True)
class MatchState:
    status: str
    final_home: int | None = None
    final_away: int | None = None
    live_home: int | None = None
    live_away: int | None = None
    live_minute: str | None = None
    score_checked_at: str | None = None


def _utc(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    except (ValueError, TypeError):
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def resolve_match_state(
    item: dict,
    kickoff: datetime | None,
    actual_home: int | None,
    actual_away: int | None,
    observed: FixtureScore | None,
    observed_at: datetime | None,
    now: datetime,
) -> MatchState:
    checked_at = observed_at.isoformat() if observed and observed_at else item.get("score_checked_at")
    if observed and observed.status == "finished" and observed.home is not None and observed.away is not None:
        return MatchState("finished", observed.home, observed.away, score_checked_at=checked_at)
    if actual_home is not None and actual_away is not None:
        return MatchState("finished", actual_home, actual_away, score_checked_at=checked_at)
    if item.get("score_status") == "finished" and item.get("score_home") is not None and item.get("score_away") is not None:
        return MatchState("finished", item["score_home"], item["score_away"], score_checked_at=checked_at)

    if observed and observed.status == "postponed":
        return MatchState("postponed", score_checked_at=checked_at)
    if observed and observed.status == "scheduled":
        return MatchState("scheduled", score_checked_at=checked_at)
    observed_time = _utc(observed_at)
    if observed and observed.status == "live" and observed_time and observed.home is not None and observed.away is not None:
        age = (now - observed_time).total_seconds()
        if 0 <= age < LIVE_FRESH_SECONDS:
            return MatchState("live", live_home=observed.home, live_away=observed.away,
                              live_minute=observed.minute, score_checked_at=checked_at)

    if item.get("score_status") == "postponed":
        return MatchState("postponed", score_checked_at=checked_at)
    old_time = _utc(item.get("score_checked_at"))
    if item.get("score_status") == "live" and old_time and item.get("score_home") is not None and item.get("score_away") is not None:
        age = (now - old_time).total_seconds()
        if 0 <= age < LIVE_FRESH_SECONDS:
            return MatchState("live", live_home=item["score_home"], live_away=item["score_away"],
                              live_minute=item.get("live_minute"), score_checked_at=checked_at)
    return MatchState("pending" if kickoff and now >= kickoff else "scheduled", score_checked_at=checked_at)
