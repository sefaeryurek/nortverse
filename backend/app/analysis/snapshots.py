"""Small, fixed-rule picks captured once before kickoff for future evaluation."""

from __future__ import annotations

import math
from datetime import datetime

from app.analysis.league_filter import is_supported_league


RULE_VERSION = "ft-core-v1"
MIN_ARCHIVE_MATCHES = 20
MIN_FREQUENCY_PCT = 65.0

_MARKETS = {
    "result": (("1", "result_1_pct"), ("X", "result_x_pct"), ("2", "result_2_pct")),
    "over_25": (("under", "alt_25_pct"), ("over", "ust_25_pct")),
    "btts": (("yes", "kg_var_pct"), ("no", "kg_yok_pct")),
}


def prekickoff_picks(
    *, analyzed_at: datetime, kickoff_time: datetime | None,
    league_name: str | None, patterns: dict | None, league_code: str | None = None,
) -> list[dict] | None:
    """Return an empty list for eligible analyses with no qualifying selection.

    None means the analysis is ineligible and must not create a snapshot.
    Archive percentages are frequencies, not calibrated probabilities.
    """
    if (
        kickoff_time is None or analyzed_at.tzinfo is None
        or kickoff_time.tzinfo is None or analyzed_at >= kickoff_time
        or not is_supported_league(league_name, league_code) or patterns is None
    ):
        return None

    picks = []
    for archive, key in (("archive_1", "pattern_ft_b"), ("archive_2", "pattern_ft_c")):
        pattern = patterns.get(key)
        if not isinstance(pattern, dict):
            continue
        count = pattern.get("match_count")
        if type(count) is not int or count < MIN_ARCHIVE_MATCHES:
            continue
        for market, choices in _MARKETS.items():
            values = [(selection, pattern.get(field)) for selection, field in choices]
            if any(type(value) not in (int, float) or not math.isfinite(value)
                   or value < 0 or value > 100 for _, value in values):
                continue
            selection, frequency = max(values, key=lambda item: item[1])
            if frequency >= MIN_FREQUENCY_PCT:
                picks.append({
                    "archive": archive, "market": market, "selection": selection,
                    "frequency_pct": round(float(frequency), 2), "match_count": count,
                })
    return picks
