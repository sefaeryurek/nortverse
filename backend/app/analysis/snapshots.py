"""Small, fixed-rule picks captured once before kickoff for future evaluation."""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.analysis.league_filter import is_supported_league


RULE_VERSION = "ft-display-v2"
MIN_ARCHIVE_MATCHES = 20
MIN_FREQUENCY_PCT = 65.0

_MARKETS = {
    "result": (("1", "result_1_pct"), ("X", "result_x_pct"), ("2", "result_2_pct")),
    "over_25": (("under", "alt_25_pct"), ("over", "ust_25_pct")),
    "btts": (("yes", "kg_var_pct"), ("no", "kg_yok_pct")),
}


def build_ft_recommendations(patterns: dict | None) -> list[dict]:
    """Build the only FT selections that the product may display as tracked picks."""
    if patterns is None:
        return []
    by_archive: dict[str, dict[str, dict]] = {}
    for archive, key in (("archive_1", "pattern_ft_b"), ("archive_2", "pattern_ft_c")):
        pattern = patterns.get(key)
        if not isinstance(pattern, dict):
            continue
        count = pattern.get("match_count")
        if type(count) is not int or count < MIN_ARCHIVE_MATCHES:
            continue
        candidates = {}
        for market, choices in _MARKETS.items():
            values = [(selection, pattern.get(field)) for selection, field in choices]
            if any(type(value) not in (int, float) or not math.isfinite(value)
                   or value < 0 or value > 100 for _, value in values):
                continue
            selection, frequency = max(values, key=lambda item: item[1])
            if frequency >= MIN_FREQUENCY_PCT:
                candidates[market] = {
                    "selection": selection,
                    "frequency_pct": round(float(frequency), 2),
                    "match_count": count,
                }
        by_archive[archive] = candidates

    picks = []
    for market in _MARKETS:
        first = by_archive.get("archive_1", {}).get(market)
        second = by_archive.get("archive_2", {}).get(market)
        if first and second and first["selection"] != second["selection"]:
            continue
        chosen = first or second
        if chosen is None:
            continue
        archive = "both" if first and second else "archive_1" if first else "archive_2"
        frequency = min(first["frequency_pct"], second["frequency_pct"]) if first and second else chosen["frequency_pct"]
        count = min(first["match_count"], second["match_count"]) if first and second else chosen["match_count"]
        picks.append({
            "recommendation_id": f"{RULE_VERSION}:{market}:{chosen['selection']}",
            "archive": archive,
            "market": market,
            "selection": chosen["selection"],
            "frequency_pct": frequency,
            "match_count": count,
            "archive_1_frequency_pct": first["frequency_pct"] if first else None,
            "archive_1_match_count": first["match_count"] if first else None,
            "archive_2_frequency_pct": second["frequency_pct"] if second else None,
            "archive_2_match_count": second["match_count"] if second else None,
        })
    return picks


def prekickoff_picks(
    *, analyzed_at: datetime, captured_at: datetime, kickoff_time: datetime | None,
    league_name: str | None, patterns: dict | None, league_code: str | None = None,
) -> list[dict] | None:
    """Return an empty list for eligible analyses with no qualifying selection.

    None means the analysis is ineligible and must not create a snapshot.
    Archive percentages are frequencies, not calibrated probabilities.
    """
    if (
        kickoff_time is None or analyzed_at.tzinfo is None or captured_at.tzinfo is None
        or kickoff_time.tzinfo is None or analyzed_at > captured_at or captured_at >= kickoff_time
        or not is_supported_league(league_name, league_code) or patterns is None
    ):
        return None

    return build_ft_recommendations(patterns)


async def capture_prepared_recommendations(target_date: date) -> int:
    """Recompute prepared matches with an as-of cutoff, then freeze display picks."""
    from app.analysis.persist import compute_all_patterns
    from app.db.connection import get_session
    from app.db.models import AnalysisSnapshot, Match

    istanbul = timezone(timedelta(hours=3))
    day_start = datetime.combine(target_date, datetime.min.time(), istanbul)
    day_end = day_start + timedelta(days=1)
    started_at = datetime.now(timezone.utc)
    async with get_session() as session:
        prepared = (await session.execute(
            select(
                Match.match_id, Match.analyzed_at, Match.kickoff_time,
                Match.league_name, Match.league_code,
                Match.ht_scores_1, Match.ht_scores_x, Match.ht_scores_2,
                Match.h2_scores_1, Match.h2_scores_x, Match.h2_scores_2,
                Match.ft_scores_1, Match.ft_scores_x, Match.ft_scores_2,
                Match.ft_all_ratios,
            ).where(
                Match.deleted_at.is_(None), Match.kickoff_time >= day_start,
                Match.kickoff_time < day_end, Match.kickoff_time > started_at,
                Match.analyzed_at.is_not(None), Match.analyzed_at <= started_at,
                Match.analyzed_at < Match.kickoff_time, Match.ft_scores_1.is_not(None),
            )
        )).all()

    count = 0
    for match in prepared:
        patterns = await compute_all_patterns(
            match_id=match.match_id,
            ht_scores=(match.ht_scores_1 or [], match.ht_scores_x or [], match.ht_scores_2 or []),
            h2_scores=(match.h2_scores_1 or [], match.h2_scores_x or [], match.h2_scores_2 or []),
            ft_scores=(match.ft_scores_1 or [], match.ft_scores_x or [], match.ft_scores_2 or []),
            ft_ratios=match.ft_all_ratios or {}, as_of=started_at,
        )
        captured_at = datetime.now(timezone.utc)
        picks = prekickoff_picks(
            analyzed_at=match.analyzed_at, captured_at=captured_at,
            kickoff_time=match.kickoff_time, league_name=match.league_name,
            league_code=match.league_code, patterns=patterns,
        )
        if picks is None:
            continue
        async with get_session() as session:
            written = await session.execute(
                insert(AnalysisSnapshot).values(
                    match_id=match.match_id, rule_version=RULE_VERSION,
                    captured_at=captured_at, analyzed_at=match.analyzed_at,
                    kickoff_time=match.kickoff_time,
                    league_name=match.league_name or match.league_code or "unknown",
                    picks=picks,
                ).on_conflict_do_nothing(index_elements=["match_id", "rule_version"])
            )
            if written.rowcount == 1:
                count += 1
    return count
