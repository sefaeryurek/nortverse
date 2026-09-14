"""Shared history selection for eligibility, predictions and trends."""

from datetime import datetime, timezone

from app.models import HistoricalMatch, MatchRawData


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def select_history(
    matches: list[HistoricalMatch],
    team: str,
    *,
    opponent: str | None = None,
    before: datetime | None = None,
    exclude_id: str | None = None,
) -> list[HistoricalMatch]:
    """Keep relevant league games, newest first, without future/self duplicates.

    Undated legacy rows retain source order after dated rows. No date is invented.
    """
    result = []
    seen = set()
    for match in matches:
        if not match.is_league_match or team not in (match.home_team, match.away_team):
            continue
        if opponent is not None and {match.home_team, match.away_team} != {team, opponent}:
            continue
        if exclude_id and match.match_id == exclude_id:
            continue
        if before and match.match_date and _utc(match.match_date) >= _utc(before):
            continue
        if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 30
                   for v in (match.home_score_ft, match.away_score_ft)):
            continue
        key = ("id", match.match_id) if match.match_id else (
            (_utc(match.match_date), match.home_team, match.away_team) if match.match_date else None
        )
        if key is not None:
            if key in seen:
                continue
            seen.add(key)
        result.append(match)
    return sorted(result, key=lambda m: _utc(m.match_date) if m.match_date else datetime.min.replace(tzinfo=timezone.utc), reverse=True)


def prepare_history(data: MatchRawData) -> MatchRawData:
    """Return a copy so scraping/debug data remains available unchanged."""
    common = {"before": data.kickoff_time, "exclude_id": data.match_id}
    return data.model_copy(update={
        "home_recent_matches": select_history(data.home_recent_matches, data.home_team, **common),
        "away_recent_matches": select_history(data.away_recent_matches, data.away_team, **common),
        "h2h_matches": select_history(data.h2h_matches, data.home_team, opponent=data.away_team, **common),
    })
