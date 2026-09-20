"""Sonuçlar ve maç listesi endpoint'leri."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.analysis.league_filter import is_supported_league
from app.api.schemas import MatchSummary, ResultOut
from app.api.live_snapshot import get_live_snapshot
from app.api.score_state import _utc as _utc_datetime, resolve_match_state
from app.db.connection import get_session
from app.db.models import FixtureCache, Match

router = APIRouter()


@router.get("/api/matches", response_model=list[MatchSummary])
async def list_matches(
    league: Optional[str] = Query(None, description="Lig kodu (örn: ENG PR)"),
    limit: int = Query(50, ge=1, le=200),
) -> list[MatchSummary]:
    async with get_session() as session:
        stmt = (
            select(
                Match.match_id, Match.home_team, Match.away_team,
                Match.league_code, Match.season,
                Match.actual_ft_home, Match.actual_ft_away,
                Match.actual_ht_home, Match.actual_ht_away,
                Match.ft_scores_1, Match.ft_scores_x, Match.ft_scores_2,
                Match.analyzed_at,
            )
            .where(Match.deleted_at.is_(None))
            .order_by(Match.analyzed_at.desc())
            .limit(limit)
        )
        if league:
            stmt = stmt.where(Match.league_code == league)
        rows = (await session.execute(stmt)).all()

    return [
        MatchSummary(
            match_id=row.match_id,
            home_team=row.home_team,
            away_team=row.away_team,
            league_code=row.league_code,
            season=row.season,
            actual_ft_home=row.actual_ft_home,
            actual_ft_away=row.actual_ft_away,
            actual_ht_home=row.actual_ht_home,
            actual_ht_away=row.actual_ht_away,
            ft_scores_1=row.ft_scores_1,
            ft_scores_x=row.ft_scores_x,
            ft_scores_2=row.ft_scores_2,
        )
        for row in rows
    ]


@router.get("/api/results", response_model=list[ResultOut])
async def get_results(target_date: Optional[str] = Query(None, alias="date")) -> list[ResultOut]:
    """Only confirmed full-time matches belong to the results page."""
    if target_date:
        try:
            d = date.fromisoformat(target_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Geçersiz tarih formatı. Kullanım: YYYY-MM-DD")
    else:
        d = datetime.now(timezone(timedelta(hours=3))).date()

    day_start = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=timezone(timedelta(hours=3)))
    day_end = day_start + timedelta(days=1)

    async with get_session() as session:
        fixture_row = await session.get(FixtureCache, d.isoformat())
        rows = (
            await session.execute(
                select(
                    Match.match_id, Match.home_team, Match.away_team,
                    Match.league_code, Match.league_name, Match.kickoff_time,
                    Match.actual_ft_home, Match.actual_ft_away,
                    Match.actual_ht_home, Match.actual_ht_away,
                    Match.ft_scores_1, Match.ft_scores_x, Match.ft_scores_2,
                )
                .where(Match.kickoff_time >= day_start)
                .where(Match.kickoff_time < day_end)
                .where(Match.deleted_at.is_(None))
                .order_by(Match.kickoff_time)
            )
        ).all()

    by_id = {row.match_id: row for row in rows}
    today = datetime.now(timezone(timedelta(hours=3))).date()
    live_snapshot = await get_live_snapshot() if today - timedelta(days=1) <= d <= today else None
    fixtures = fixture_row.matches_json if fixture_row and isinstance(fixture_row.matches_json, list) else []
    istanbul_tz = timezone(timedelta(hours=3))
    listed = [
        item for item in fixtures
        if isinstance(item, dict) and item.get("match_id")
        and (
            (kickoff := _utc_datetime(item.get("kickoff_time"))) is None
            or kickoff.astimezone(istanbul_tz).date() == d
        )
    ]
    seen = {item["match_id"] for item in listed}
    listed.extend({"match_id": row.match_id} for row in rows if row.match_id not in seen)

    now_utc = datetime.now(timezone.utc)
    out: list[ResultOut] = []
    for item in listed:
        row = by_id.get(item["match_id"])
        league_code = item.get("league_code") or (row.league_code if row else None)
        league_name = item.get("league_name") or (row.league_name if row else None)
        if not is_supported_league(league_name, league_code):
            continue

        kickoff = _utc_datetime(item.get("kickoff_time") or (row.kickoff_time if row else None))
        observed = live_snapshot.scores.get(item["match_id"]) if live_snapshot else None
        state = resolve_match_state(
            item, kickoff, row.actual_ft_home if row else None, row.actual_ft_away if row else None,
            observed, live_snapshot.checked_at if live_snapshot else None, now_utc,
        )
        if state.status != "finished":
            continue
        h, a = state.final_home, state.final_away

        result = None
        kg_var = None
        over_25 = None
        katman_a_covered = None
        if h is not None and a is not None:
            result = "1" if h > a else ("2" if a > h else "X")
            kg_var = h > 0 and a > 0
            over_25 = (h + a) >= 3
            if row is not None:
                covered_list = (
                    row.ft_scores_1 if result == "1"
                    else row.ft_scores_2 if result == "2"
                    else row.ft_scores_x
                ) or []
                katman_a_covered = f"{h}-{a}" in covered_list

        out.append(ResultOut(
            match_id=item["match_id"],
            home_team=item.get("home_team") or (row.home_team if row else ""),
            away_team=item.get("away_team") or (row.away_team if row else ""),
            league_code=league_code,
            league_name=league_name,
            kickoff_time=kickoff.isoformat() if kickoff else None,
            actual_ft_home=h,
            actual_ft_away=a,
            actual_ht_home=(row.actual_ht_home if row and row.actual_ht_home is not None
                            else item.get("actual_ht_home")),
            actual_ht_away=(row.actual_ht_away if row and row.actual_ht_away is not None
                            else item.get("actual_ht_away")),
            score_checked_at=state.score_checked_at,
            status="finished",
            result=result,
            kg_var=kg_var,
            over_25=over_25,
            katman_a_covered=katman_a_covered,
        ))

    return sorted(out, key=lambda match: match.kickoff_time or "")
