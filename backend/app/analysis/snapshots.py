"""Small, fixed-rule picks captured once before kickoff for future evaluation."""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.league_filter import CUP_KEYWORDS, is_supported_league
from app.db.models import (
    AnalysisSnapshot,
    AnalysisSnapshotMarket,
    Match,
    MatchFinalResultObservation,
)


V3_RULE_VERSION = "ft-display-v3"
RULE_VERSION = V3_RULE_VERSION
BASELINE_VERSION = "global-modal-v1"
V3_ACTIVATION_CUTOFF = datetime(2026, 9, 23, 14, 55, 46, tzinfo=timezone.utc)
MIN_BASELINE_MATCHES = 100
MIN_ARCHIVE_MATCHES = 20
MIN_FREQUENCY_PCT = 65.0

_MARKETS = {
    "result": (("1", "result_1_pct"), ("X", "result_x_pct"), ("2", "result_2_pct")),
    "over_25": (("under", "alt_25_pct"), ("over", "ust_25_pct")),
    "btts": (("yes", "kg_var_pct"), ("no", "kg_yok_pct")),
}

_BASELINE_SCOPE = "global_supported_leagues"


async def load_market_baselines(
    session: AsyncSession, as_of: datetime,
) -> dict[str, dict | None]:
    """Load deterministic global modal baselines using one aggregate query.

    Every included result must have been observed by ``as_of`` and strictly
    after kickoff.  A baseline is withheld until the common cohort reaches
    ``MIN_BASELINE_MATCHES``; a short archive must never manufacture a
    comparator for the model.
    """
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")

    league_fields = (Match.league_name, Match.league_code)
    league_filter = tuple(
        ~func.lower(func.coalesce(field, "")).contains(keyword)
        for field in league_fields
        for keyword in CUP_KEYWORDS
    )
    has_league = or_(*(
        (
            func.length(func.trim(func.coalesce(field, ""))) > 0
        ) & (
            func.trim(func.coalesce(field, "")) != "?"
        )
        for field in league_fields
    ))

    observation = MatchFinalResultObservation
    latest = select(
        observation.match_id.label("match_id"),
        observation.kickoff_time.label("kickoff_time"),
        observation.ft_home.label("ft_home"),
        observation.ft_away.label("ft_away"),
        observation.observed_at.label("observed_at"),
        observation.ingested_at.label("ingested_at"),
        func.row_number().over(
            partition_by=observation.match_id,
            order_by=(observation.ingested_at.desc(), observation.id.desc()),
        ).label("latest_rank"),
    ).where(
        observation.ingested_at <= as_of,
        observation.observed_at > observation.kickoff_time,
    ).subquery("latest_result_observation")

    result_conditions = (
        latest.c.ft_home > latest.c.ft_away,
        latest.c.ft_home == latest.c.ft_away,
        latest.c.ft_home < latest.c.ft_away,
    )
    over_conditions = (
        latest.c.ft_home + latest.c.ft_away < 3,
        latest.c.ft_home + latest.c.ft_away >= 3,
    )
    btts_conditions = (
        (latest.c.ft_home > 0) & (latest.c.ft_away > 0),
        (latest.c.ft_home == 0) | (latest.c.ft_away == 0),
    )
    counts = [func.count(Match.id)]
    for conditions in (result_conditions, over_conditions, btts_conditions):
        counts.extend(func.count(Match.id).filter(condition) for condition in conditions)

    row = (await session.execute(
        select(*counts).select_from(
            Match,
        ).join(
            latest, latest.c.match_id == Match.match_id,
        ).where(
            Match.deleted_at.is_(None),
            Match.kickoff_time.is_not(None),
            latest.c.latest_rank == 1,
            latest.c.kickoff_time == Match.kickoff_time,
            latest.c.observed_at > Match.kickoff_time,
            latest.c.ingested_at <= as_of,
            Match.kickoff_time < as_of,
            has_league,
            *league_filter,
        )
    )).one()

    sample_size = int(row[0] or 0)
    baselines: dict[str, dict | None] = {market: None for market in _MARKETS}
    if sample_size < MIN_BASELINE_MATCHES:
        return baselines

    offset = 1
    for market, choices in _MARKETS.items():
        market_counts = [int(value or 0) for value in row[offset:offset + len(choices)]]
        offset += len(choices)
        # max() keeps the first option on a tie, making the order in _MARKETS
        # part of the versioned baseline definition.
        winner_index = max(range(len(choices)), key=market_counts.__getitem__)
        selection = choices[winner_index][0]
        winner_count = market_counts[winner_index]
        baselines[market] = {
            "selection": selection,
            "score_bp": round(10_000 * winner_count / sample_size),
            "sample_size": sample_size,
            "scope": _BASELINE_SCOPE,
        }
    return baselines


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


def _market_abstain_reason(patterns: dict | None, market: str) -> str:
    if not isinstance(patterns, dict):
        return "patterns_unavailable"

    choices = _MARKETS[market]
    qualified: list[str] = []
    saw_small_sample = False
    saw_below_threshold = False
    for key in ("pattern_ft_b", "pattern_ft_c"):
        pattern = patterns.get(key)
        if not isinstance(pattern, dict):
            continue
        count = pattern.get("match_count")
        if type(count) is not int or count < MIN_ARCHIVE_MATCHES:
            saw_small_sample = True
            continue
        values = [(selection, pattern.get(field)) for selection, field in choices]
        if any(
            type(value) not in (int, float)
            or not math.isfinite(value)
            or value < 0
            or value > 100
            for _, value in values
        ):
            continue
        selection, frequency = max(values, key=lambda item: item[1])
        if frequency < MIN_FREQUENCY_PCT:
            saw_below_threshold = True
            continue
        qualified.append(selection)

    if len(qualified) == 2 and qualified[0] != qualified[1]:
        return "archive_disagreement"
    if saw_below_threshold:
        return "frequency_below_threshold"
    if saw_small_sample:
        return "archive_sample_below_minimum"
    return "patterns_unavailable"


def build_market_evaluation_rows(
    patterns: dict | None,
    baselines: dict[str, dict | None] | None,
) -> list[dict]:
    """Normalize one frozen model decision and comparator for every FT market.

    Baselines are attached after the model decision is built and therefore can
    neither create nor change a model selection.
    """
    picks = {pick["market"]: pick for pick in build_ft_recommendations(patterns)}
    baselines = baselines or {}
    rows: list[dict] = []
    for market in _MARKETS:
        pick = picks.get(market)
        baseline = baselines.get(market)
        row = {
            "market": market,
            "model_selection": pick["selection"] if pick else None,
            "model_score_bp": round(100 * pick["frequency_pct"]) if pick else None,
            "model_sample_size": pick["match_count"] if pick else None,
            "model_source": pick["archive"] if pick else None,
            "baseline_selection": baseline["selection"] if baseline else None,
            "baseline_score_bp": baseline["score_bp"] if baseline else None,
            "baseline_sample_size": baseline["sample_size"] if baseline else None,
            "baseline_scope": baseline["scope"] if baseline else None,
            "abstain_reason": None if pick else _market_abstain_reason(patterns, market),
        }
        rows.append(row)
    return rows


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
        or analyzed_at < V3_ACTIVATION_CUTOFF
        or not is_supported_league(league_name, league_code) or patterns is None
    ):
        return None

    has_ft_data = any(
        isinstance(patterns.get(k), dict)
        for k in ("pattern_ft_b", "pattern_ft_c")
    )
    if not has_ft_data:
        return None

    return build_ft_recommendations(patterns)


async def capture_v3_recommendations(
    session: AsyncSession,
    *,
    match_id: str,
    analyzed_at: datetime,
    captured_at: datetime,
    kickoff_time: datetime | None,
    league_name: str | None,
    league_code: str | None,
    patterns: dict | None,
) -> tuple[list[dict] | None, bool]:
    """Atomically freeze one prospective v3 decision bundle.

    The header insert is the compare-and-set operation.  Only its winner loads
    the historical baseline and writes the three normalized market rows in the
    same transaction.  A conflict loser returns the already frozen UI picks.
    """
    picks = prekickoff_picks(
        analyzed_at=analyzed_at,
        captured_at=captured_at,
        kickoff_time=kickoff_time,
        league_name=league_name,
        league_code=league_code,
        patterns=patterns,
    )
    if picks is None:
        return None, False

    written = await session.execute(
        insert(AnalysisSnapshot).values(
            match_id=match_id,
            rule_version=RULE_VERSION,
            captured_at=captured_at,
            analyzed_at=analyzed_at,
            kickoff_time=kickoff_time,
            league_name=league_name or league_code or "unknown",
            picks=picks,
            baseline_version=BASELINE_VERSION,
        ).on_conflict_do_nothing(
            index_elements=["match_id", "rule_version"],
        )
    )
    if written.rowcount == 1:
        baselines = await load_market_baselines(session, analyzed_at)
        market_rows = build_market_evaluation_rows(patterns, baselines)
        if len(market_rows) != len(_MARKETS):
            raise RuntimeError("v3 snapshot must contain every tracked market")
        await session.execute(
            insert(AnalysisSnapshotMarket),
            [
                {"match_id": match_id, "rule_version": RULE_VERSION, **row}
                for row in market_rows
            ],
        )
        return picks, True

    snapshot = await session.get(AnalysisSnapshot, (match_id, RULE_VERSION))
    frozen = snapshot.picks if snapshot and isinstance(snapshot.picks, list) else []
    return frozen, False


async def capture_prepared_recommendations(target_date: date) -> int:
    """Recompute prepared matches with an as-of cutoff, then freeze display picks."""
    from app.analysis.persist import compute_all_patterns
    from app.db.connection import get_session
    from app.db.models import Match

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
                Match.analyzed_at >= V3_ACTIVATION_CUTOFF,
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
            ft_ratios=match.ft_all_ratios or {}, as_of=match.analyzed_at,
        )
        captured_at = datetime.now(timezone.utc)
        async with get_session() as session:
            current = (await session.execute(
                select(Match).where(
                    Match.match_id == match.match_id,
                    Match.deleted_at.is_(None),
                    Match.analyzed_at == match.analyzed_at,
                    Match.kickoff_time == match.kickoff_time,
                    Match.kickoff_time > captured_at,
                ).with_for_update()
            )).scalar_one_or_none()
            if current is None:
                continue
            picks, created = await capture_v3_recommendations(
                session,
                match_id=match.match_id,
                analyzed_at=match.analyzed_at,
                captured_at=captured_at,
                kickoff_time=current.kickoff_time,
                league_name=current.league_name,
                league_code=current.league_code,
                patterns=patterns,
            )
            if created and picks is not None:
                count += 1
    return count
