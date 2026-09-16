"""Sonuçlar ve maç listesi endpoint'leri."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.analysis.league_filter import is_supported_league
from app.api.schemas import MatchSummary, ResultOut
from app.db.connection import get_session
from app.db.models import Match

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
    """Belirli bir tarihte oynanan/oynanacak TÜM maçları döndürür."""
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

    now_utc = datetime.now(timezone.utc)
    out = []
    for row in rows:
        if not is_supported_league(row.league_name, row.league_code):
            continue

        h = row.actual_ft_home
        a = row.actual_ft_away
        kickoff = row.kickoff_time

        if h is not None and a is not None:
            status = "finished"
        elif kickoff and now_utc >= kickoff:
            status = "pending"
        else:
            status = "scheduled"

        result = None
        kg_var = None
        over_25 = None
        katman_a_covered = None
        if status == "finished" and h is not None and a is not None:
            result = "1" if h > a else ("2" if a > h else "X")
            kg_var = h > 0 and a > 0
            over_25 = (h + a) >= 3
            covered_list = (
                row.ft_scores_1 if result == "1"
                else row.ft_scores_2 if result == "2"
                else row.ft_scores_x
            ) or []
            katman_a_covered = len(covered_list) > 0

        out.append(ResultOut(
            match_id=row.match_id,
            home_team=row.home_team,
            away_team=row.away_team,
            league_code=row.league_code,
            league_name=row.league_name,
            kickoff_time=row.kickoff_time.isoformat() if row.kickoff_time else None,
            actual_ft_home=h,
            actual_ft_away=a,
            actual_ht_home=row.actual_ht_home,
            actual_ht_away=row.actual_ht_away,
            status=status,
            result=result,
            kg_var=kg_var,
            over_25=over_25,
            katman_a_covered=katman_a_covered,
        ))

    return out
