"""Yalnız model satırları (Sprint 94 P1) ve takip edilen Avrupa kupası maçları (P4).

`matches`'a Katman A ve arşivsiz satır yazar: H2H yetersiz takip maçı (takım gücü + gölge v5.1) ve kupa maçı
(canlı gölge live-cup-cond-v1). Bu satırlar `Match.model_only` ile ortak havuzlardan ve ekran listelerinden
süzülür. runner.py 1000 satırı geçmesin diye ayrıldı.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func
from sqlalchemy.dialects.postgresql import insert

from app.analysis.league_filter import canonical_league_name, tracked_cup_name
from app.analysis.persist import pattern_as_of
from app.db.connection import get_session
from app.db.models import Match
from app.models import FixtureMatch, MatchRawData

log = logging.getLogger(__name__)


def _model_only_row(raw: MatchRawData, analyzed_at: datetime) -> dict:
    """H2H yetersiz takip maçının yalnız model satırı (Sprint 94 P1, K15): takım, lig, saat, skor.

    Katman A, arşivler (A1/A2/A3) ve trendler boş; λ kayıttan sonra yazılır. `model_only` satırları ortak
    havuzlara ve ekran listelerine girmez.
    """
    from app.analysis.engine import _current_season

    league = canonical_league_name(raw.league_code)
    row = {
        "match_id": raw.match_id, "home_team": raw.home_team, "away_team": raw.away_team,
        "league_code": league, "league_name": league, "season": _current_season(raw.kickoff_time),
        "analyzed_at": analyzed_at, "kickoff_time": raw.kickoff_time, "model_only": True,
        "actual_ft_home": raw.actual_ft_home, "actual_ft_away": raw.actual_ft_away,
        "actual_ht_home": raw.actual_ht_home, "actual_ht_away": raw.actual_ht_away,
        "actual_h2_home": raw.actual_h2_home, "actual_h2_away": raw.actual_h2_away,
    }
    if raw.actual_ft_home is not None and raw.kickoff_time:
        row["result_fetched_at"] = raw.kickoff_time + timedelta(hours=2)
    return row


async def upsert_model_only(raw: MatchRawData, captured_at: datetime | None = None) -> int:
    """Yalnız model satırını yazar, λ'yı hesaplar, gölge v5.1 kararını dondurur. Yazılan defter satırı sayısı.

    Tam analizli satır varsa ona dokunulmaz (yalnız model onun yerini almaz); silinmiş satır geri açılmaz.
    """
    from app.pipeline import runner as _r

    analyzed_at = datetime.now(timezone.utc)
    row = _model_only_row(raw, analyzed_at)
    ok, reason = _r._validate_row(row)
    if not ok:
        raise ValueError(f"Yalnız model satırı reddedildi [{raw.match_id}]: {reason}")
    if not await _write_model_only_row(row):
        return 0
    from app.analysis.live_poisson import team_lambdas_for_match
    from app.analysis.prematch_v5 import capture_model_only

    try:
        await team_lambdas_for_match(raw.match_id, pattern_as_of(analyzed_at, raw.kickoff_time))
    except Exception as exc:
        log.warning("Takım gücü λ yazılamadı [%s]: %s", raw.match_id, exc)
    async with get_session() as session:
        return await capture_model_only(
            session, match_id=raw.match_id, captured_at=captured_at or datetime.now(timezone.utc),
            kickoff_time=raw.kickoff_time, league=row["league_name"], home=raw.home_team, away=raw.away_team,
        )


async def _write_model_only_row(row: dict) -> bool:
    """Yalnız model satırını yazar; tam analizli ya da silinmiş satıra dokunmaz. Yazıldıysa True."""
    from app.pipeline import runner as _r

    updates = dict(row)
    for key in ("kickoff_time", "actual_ft_home", "actual_ft_away", "actual_ht_home",
                "actual_ht_away", "actual_h2_home", "actual_h2_away"):
        updates[key] = func.coalesce(row[key], getattr(Match, key))
    stmt = insert(Match).values(**row).on_conflict_do_update(
        index_elements=["match_id"], set_=updates,
        where=and_(Match.model_only.is_(True), Match.deleted_at.is_(None)),
    )

    async def _write() -> int:
        async with get_session() as session:
            return (await session.execute(stmt)).rowcount or 0

    return bool(await _r._with_retry(_write, label=f"model_only[{row['match_id']}]"))


def cup_match_row(fixture: FixtureMatch, analyzed_at: datetime) -> dict | None:
    """Takip edilen Avrupa kupası maçının satırı (Sprint 94 P4): bültenden — maç sayfası çekilmez.

    Yalnız model satırıdır (Katman A, arşiv, λ yok): ledger yabancı anahtarı ve canlı izleyici adayı için.
    Lig sayılmadığı için `_validate_row`'un kupa süzgecine girmez; takım adları burada denetlenir.
    """
    cup = tracked_cup_name(fixture.league_name, fixture.league_code)
    if cup is None or fixture.kickoff_time is None:
        return None
    if any(not t or not t.strip() or t.strip() == "?" for t in (fixture.home_team, fixture.away_team)):
        return None
    from app.analysis.engine import _current_season

    return {
        "match_id": fixture.match_id, "home_team": fixture.home_team.strip(), "away_team": fixture.away_team.strip(),
        "league_code": cup, "league_name": cup, "season": _current_season(fixture.kickoff_time),
        "analyzed_at": analyzed_at, "kickoff_time": fixture.kickoff_time, "model_only": True,
        "actual_ft_home": None, "actual_ft_away": None, "actual_ht_home": None, "actual_ht_away": None,
        "actual_h2_home": None, "actual_h2_away": None,
    }


async def refresh_cup_archive(ctx, seasons: int = 1) -> int:
    """Kupaların son `seasons` sezonunun bitmiş lig aşaması maçlarını `cup_results`'a yazar (kaldığı yerden; var
    olan satırın skoru güncellenir). Pipeline günde bir güncel sezonu çeker; ilk kurulum `build-cup-archive`."""
    from app.analysis.league_filter import TRACKED_CUPS
    from app.db.models import CupResult
    from app.scraper.cup import fetch_cup_season
    from app.scraper.league import fetch_league_seasons

    written = 0
    for competition, cup_id in TRACKED_CUPS.items():
        for season in (await fetch_league_seasons(cup_id, ctx=ctx))[:seasons]:
            rows = await fetch_cup_season(cup_id, competition, season, ctx=ctx)
            if not rows:
                continue
            stmt = insert(CupResult).values(rows)
            stmt = stmt.on_conflict_do_update(index_elements=["match_id"], set_={
                k: stmt.excluded[k] for k in ("ht_home", "ht_away", "ft_home", "ft_away", "kickoff_time", "round")})
            async with get_session() as session:
                await session.execute(stmt)
            written += len(rows)
            log.info("Kupa arşivi: %s %s → %d maç", competition, season, len(rows))
    return written


async def _prepare_cups(fixtures: list[FixtureMatch], ctx, stats: dict) -> None:
    """Avrupa kupaları (P4): başlamamış maçlara yalnız model satırı (canlı gölge kural için) + güncel sezon
    sonuçları. Hata pipeline'ı durdurmaz (kupa takibi yan iş)."""
    now = datetime.now(timezone.utc)
    for fixture in fixtures:
        row = cup_match_row(fixture, now)
        if row is None or row["kickoff_time"].astimezone(timezone.utc) <= now:
            continue
        try:
            stats["cup_matches"] += int(await _write_model_only_row(row))
        except Exception as exc:
            log.warning("Kupa maçı satırı yazılamadı [%s]: %s", fixture.match_id, exc)
    try:
        await refresh_cup_archive(ctx)
    except Exception as exc:
        log.warning("Kupa arşivi güncellenemedi: %s", exc)
