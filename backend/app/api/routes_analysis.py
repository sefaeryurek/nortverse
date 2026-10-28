"""Analiz ve maç detay endpoint'leri."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Path, Query, Request

from app.auth import is_admin_request
from sqlalchemy import select

from app.api.ratelimit import check_rate
from app.api.schemas import AnalyzeResponse, MatchSummary
from app.api.services import (
    ANALYSIS_TIMEOUT,
    analyze_and_cache,
    cache_put,
    do_analyze,
    get_or_make_lock,
)
from app.db.connection import get_session
from app.db.models import Match

log = logging.getLogger(__name__)
router = APIRouter()

# Hız sınırı kullanıcı kimliğine göre (Sprint 94 E3) — app/api/ratelimit.py
_RATE_LIMIT_GET = 30
_RATE_LIMIT_POST = 5


async def _kickoff_of(match_id: str) -> datetime | None:
    async with get_session() as session:
        return (await session.execute(
            select(Match.kickoff_time).where(Match.match_id == match_id, Match.deleted_at.is_(None))
        )).scalar_one_or_none()


@router.get("/api/analyze/{match_id}", response_model=AnalyzeResponse)
async def get_analyze(
    request: Request,
    match_id: str = Path(pattern=r"^[0-9]{1,12}$"),
) -> AnalyzeResponse:
    """Maçı analiz eder. Cache'te varsa anında döner, yoksa scrape eder."""
    check_rate(request, "analyze", _RATE_LIMIT_GET)
    try:
        return await asyncio.wait_for(analyze_and_cache(match_id, allow_scrape=is_admin_request(request)),
                                      timeout=ANALYSIS_TIMEOUT)
    except asyncio.TimeoutError:
        raise HTTPException(504, "Analiz zaman aşımına uğradı")


@router.post("/api/analyze/{match_id}", response_model=AnalyzeResponse)
async def post_analyze(
    request: Request,
    match_id: str = Path(pattern=r"^[0-9]{1,12}$"),
) -> AnalyzeResponse:
    """Maçı yeniden scrape eder ve cache'i günceller — yalnızca maç başlamadan.

    Başlamış/bitmiş maçta yeniden analiz maç öncesi analizi ezip maçı "arşiv" sınıfına
    taşırdı (değerlendirme bozulur); bu yüzden 409 döner.
    """
    check_rate(request, "analyze-post", _RATE_LIMIT_POST)
    if not is_admin_request(request):
        raise HTTPException(403, "Yeniden analiz sadece yönetici hesabıyla yapılabilir")
    kickoff = await _kickoff_of(match_id)
    if kickoff is not None and kickoff <= datetime.now(timezone.utc):
        raise HTTPException(409, "Maç başladı; maç öncesi analiz korunuyor")

    async def refresh():
        async with get_or_make_lock(match_id):
            response = await do_analyze(match_id)
            cache_put(match_id, response)
            return response

    try:
        return await asyncio.wait_for(refresh(), timeout=ANALYSIS_TIMEOUT)
    except asyncio.TimeoutError:
        raise HTTPException(504, "Analiz zaman aşımına uğradı")


@router.get("/api/match/{match_id}", response_model=MatchSummary)
async def get_match(
    request: Request,
    match_id: str = Path(pattern=r"^[0-9]{1,12}$"),
) -> MatchSummary:
    """Maçın özet bilgisi. DB'de yoksa Playwright ile çek + DB'ye kaydet, sonra dön."""
    check_rate(request, "analyze", _RATE_LIMIT_GET)
    async with get_session() as session:
        row = (
            await session.execute(
                select(Match).where(Match.match_id == match_id, Match.deleted_at.is_(None))
            )
        ).scalar_one_or_none()

    if not row and not is_admin_request(request):
        raise HTTPException(404, f"Maç bulunamadı: {match_id}")
    if not row:
        log.info("/api/match miss — Playwright fallback: %s", match_id)

        async def _scrape() -> None:
            async with get_or_make_lock(match_id):
                await do_analyze(match_id)

        try:
            await asyncio.wait_for(_scrape(), timeout=25.0)
        except asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail=f"Maç verisi çekilemedi (timeout): {match_id}")
        except HTTPException:
            raise
        except Exception as exc:
            log.warning("Maç fallback scrape başarısız [%s]: %s", match_id, exc)
            raise HTTPException(status_code=404, detail=f"Maç bulunamadı: {match_id}")

        async with get_session() as session:
            row = (
                await session.execute(
                    select(Match).where(Match.match_id == match_id, Match.deleted_at.is_(None))
                )
            ).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail=f"Maç bulunamadı: {match_id}")

    return MatchSummary(
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


@router.get("/api/analyze/{match_id}/matched-matches")
async def get_matched_matches(
    match_id: str = Path(pattern=r"^[0-9]{1,12}$"),
    period: Literal["ht", "h2", "ft"] = Query("ft"),
) -> dict:
    """Ana Pazar Özeti'ndeki sayıların dayandığı arşiv maçlarını döndürür.

    Liste, pattern hesaplanırken saklanan matched_ids'ten okunur → istatistik
    ile liste her periyotta birebir aynı maç kümesidir.
    """
    async with get_session() as session:
        target = (
            await session.execute(
                select(Match).where(Match.match_id == match_id, Match.deleted_at.is_(None))
            )
        ).scalar_one_or_none()
        if not target:
            raise HTTPException(404, "Maç bulunamadı")

        blobs = {f: getattr(target, f"pattern_{period}_{f}") or {} for f in ("b", "c", "d")}
        ids_by_family = {f: [str(i) for i in blob.get("matched_ids") or []] for f, blob in blobs.items()}
        all_ids = {mid for ids in ids_by_family.values() for mid in ids}
        details = {}
        if all_ids:
            rows = (await session.execute(
                select(
                    Match.match_id, Match.home_team, Match.away_team, Match.league_code,
                    Match.actual_ht_home, Match.actual_ht_away,
                    Match.actual_ft_home, Match.actual_ft_away,
                    Match.kickoff_time,
                ).where(Match.match_id.in_(all_ids), Match.deleted_at.is_(None))
            )).all()
            details = {r.match_id: r for r in rows}

    def _row_to_dict(r) -> dict:
        ht_h, ht_a = r.actual_ht_home, r.actual_ht_away
        ft_h, ft_a = r.actual_ft_home, r.actual_ft_away
        h2_h = ft_h - ht_h if ht_h is not None and ft_h is not None else None
        h2_a = ft_a - ht_a if ht_a is not None and ft_a is not None else None
        return {
            "match_id": r.match_id,
            "home_team": r.home_team,
            "away_team": r.away_team,
            "league_code": r.league_code,
            "ht": f"{ht_h}-{ht_a}" if ht_h is not None else None,
            "h2": f"{h2_h}-{h2_a}" if h2_h is not None else None,
            "ft": f"{ft_h}-{ft_a}" if ft_h is not None else None,
            "kickoff_time": r.kickoff_time.isoformat() if r.kickoff_time else None,
        }

    def _family_list(family: str) -> list[dict]:
        sims = blobs[family].get("matched_sims") or []
        out = []
        for idx, mid in enumerate(ids_by_family[family]):
            r = details.get(mid)
            if r is None:
                continue
            item = _row_to_dict(r)
            if family == "d" and idx < len(sims):
                item["similarity"] = sims[idx]
            out.append(item)
        return out

    return {
        "period": period,
        "archive_b": _family_list("b"),
        "archive_c": _family_list("c"),
        "archive_d": _family_list("d"),
        # Eşleşme var ama liste saklanmamışsa (eski kayıt) arayüz "liste henüz yok" diyebilir.
        "list_available": {
            f"archive_{f}": not blobs[f] or "matched_ids" in blobs[f] for f in ("b", "c", "d")
        },
    }
