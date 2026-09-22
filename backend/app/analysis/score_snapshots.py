"""Freeze exact-score lists against a baseline known at prediction time."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.league_filter import CUP_KEYWORDS, canonical_league_name, is_supported_league
from app.db.models import Match, ScoreSnapshot
from app.db.connection import get_session


SCORE_RULE_VERSION = "score-list-v1"
_SCORE_RE = re.compile(r"^(\d{1,2})-(\d{1,2})$")


def score_shortlist(*groups: list[str]) -> list[str]:
    """Preserve the displayed order and count each possible score once."""
    scores = list(dict.fromkeys(score for group in groups for score in group))
    if len(scores) > 50:
        raise ValueError("Score shortlist is unexpectedly large")
    for score in scores:
        match = _SCORE_RE.fullmatch(score) if isinstance(score, str) else None
        if match is None or any(int(value) > 30 for value in match.groups()):
            raise ValueError(f"Invalid score in shortlist: {score!r}")
    return scores


async def capture_score_snapshot(
    session: AsyncSession, *, match_id: str, analyzed_at: datetime,
    captured_at: datetime, kickoff_time: datetime | None,
    league_name: str | None, league_code: str | None,
    model_scores: list[str],
) -> bool:
    """Insert once; baseline uses only results fetched before captured_at."""
    if (
        kickoff_time is None or analyzed_at.tzinfo is None
        or captured_at.tzinfo is None or kickoff_time.tzinfo is None
        or analyzed_at > captured_at or captured_at >= kickoff_time
        or not is_supported_league(league_name, league_code)
    ):
        return False
    if await session.get(ScoreSnapshot, (match_id, SCORE_RULE_VERSION)) is not None:
        return False

    scores = score_shortlist(model_scores)
    baseline: list[str] | None = None
    if scores:
        final_score = func.concat(Match.actual_ft_home, "-", Match.actual_ft_away)
        frequency = func.count(Match.id)
        league_filter = tuple(
            ~func.lower(func.coalesce(field, "")).contains(keyword)
            for field in (Match.league_name, Match.league_code)
            for keyword in CUP_KEYWORDS
        )
        prior = (await session.execute(
            select(final_score, frequency)
            .where(
                Match.match_id != match_id,
                Match.deleted_at.is_(None),
                Match.kickoff_time < captured_at,
                Match.result_fetched_at <= captured_at,
                Match.result_fetched_at > Match.kickoff_time,
                Match.actual_ft_home.is_not(None),
                Match.actual_ft_away.is_not(None),
                *league_filter,
            )
            .group_by(final_score)
            .order_by(frequency.desc(), final_score.asc())
            .limit(len(scores))
        )).all()
        if len(prior) == len(scores):
            baseline = [row[0] for row in prior]

    written = await session.execute(
        insert(ScoreSnapshot).values(
            match_id=match_id,
            rule_version=SCORE_RULE_VERSION,
            captured_at=captured_at,
            analyzed_at=analyzed_at,
            kickoff_time=kickoff_time,
            league_name=league_name or canonical_league_name(league_code),
            model_scores=scores,
            baseline_scores=baseline,
        ).on_conflict_do_nothing(index_elements=["match_id", "rule_version"])
    )
    return written.rowcount == 1


async def capture_prepared_score_snapshots(target_date: date) -> int:
    """Freeze previously prepared analyses only while their matches are still upcoming."""
    istanbul = timezone(timedelta(hours=3))
    day_start = datetime.combine(target_date, datetime.min.time(), istanbul)
    day_end = day_start + timedelta(days=1)
    captured_at = datetime.now(timezone.utc)
    async with get_session() as session:
        prepared = (await session.execute(
            select(
                Match.match_id, Match.analyzed_at, Match.kickoff_time,
                Match.league_name, Match.league_code,
                Match.ft_scores_1, Match.ft_scores_x, Match.ft_scores_2,
            ).where(
                Match.deleted_at.is_(None),
                Match.kickoff_time >= day_start,
                Match.kickoff_time < day_end,
                Match.kickoff_time > captured_at,
                Match.analyzed_at.is_not(None),
                Match.analyzed_at <= captured_at,
                Match.analyzed_at < Match.kickoff_time,
                Match.pattern_computed_at.is_not(None),
                Match.pattern_computed_at < Match.kickoff_time,
            )
        )).all()
        count = 0
        for match in prepared:
            if await capture_score_snapshot(
                session,
                match_id=match.match_id,
                analyzed_at=match.analyzed_at,
                captured_at=captured_at,
                kickoff_time=match.kickoff_time,
                league_name=match.league_name,
                league_code=match.league_code,
                model_scores=(match.ft_scores_1 or []) + (match.ft_scores_x or []) + (match.ft_scores_2 or []),
            ):
                count += 1
        return count
