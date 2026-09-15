"""Pipeline: Fetch → Analyze → Persist.

Tek browser context ile tüm maçları işler, sonuçları Supabase'e yazar.
Idempotent: aynı match_id için tekrar çalıştırılırsa günceller (upsert).
"""

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Awaitable, Callable, Optional, TypeVar

from sqlalchemy import func, or_, select, update as sa_update
from sqlalchemy.dialects.postgresql import insert

from app.analysis import analyze_match, check_match_filters
from app.analysis.league_filter import canonical_league_name, is_supported_league
from app.analysis.persist import compute_all_patterns
from app.analysis.trends import compute_trends
from app.db.connection import get_session
from app.db.models import FixtureCache, Match
from app.models import MatchAnalysisResult, MatchRawData
from app.scraper.browser import browser_context
from app.scraper.fixture import fetch_fixture
from app.scraper.match_detail import fetch_match_detail

T = TypeVar("T")


class StaleAnalysisWrite(ValueError):
    """An older analysis cannot replace a newer or deleted record."""


async def _with_retry(
    op: Callable[[], Awaitable[T]],
    label: str,
    attempts: int = 3,
    base_delay: float = 0.5,
) -> T:
    """Geçici DB hatalarına karşı exponential backoff ile retry.

    Supabase PgBouncer ara sıra connection drop yaşıyor; ilk denemede
    başarısız olan bir işlem 2-3 deneme içinde genelde tutar.
    Son deneme yine başarısız olursa exception yukarı fırlatılır.
    """
    last_exc: Exception | None = None
    for i in range(attempts):
        try:
            return await op()
        except ValueError:
            raise  # Invalid data will not be repaired by retrying the same operation.
        except Exception as exc:
            last_exc = exc
            if i == attempts - 1:
                raise
            wait = base_delay * (2 ** i)
            log.warning("%s — deneme %d/%d başarısız: %s (yeniden deneme %.1fs sonra)",
                        label, i + 1, attempts, exc, wait)
            await asyncio.sleep(wait)
    # mantık olarak buraya gelinmez ama tip checker memnun olsun
    raise last_exc if last_exc else RuntimeError("retry tükendi")

log = logging.getLogger(__name__)


def _result_to_row(
    r: MatchAnalysisResult,
    raw: MatchRawData | None = None,
    patterns: dict[str, dict | None] | None = None,
) -> dict:
    """MatchAnalysisResult → matches tablosu satırı.

    patterns parametresi compute_all_patterns()'in çıktısıdır; verilirse
    pattern_*_b/c kolonları da satıra eklenir.
    `trends` kolonu ham veriden hesaplanır (raw verildiyse).
    """
    # Sprint 8.9: lig adını kanonik forma çevir — "ENG PR" / "English Premier League"
    # tutarsızlığı önlenir; tüm DB tek bir kanonik form kullanır.
    canonical_code = canonical_league_name(r.league_code)
    row = {
        "match_id": r.match_id,
        "home_team": r.home_team,
        "away_team": r.away_team,
        "league_code": canonical_code,
        "league_name": canonical_code,
        "season": r.season,
        "analyzed_at": r.analyzed_at,
        "ht_scores_1": r.ht.scores_1,
        "ht_scores_x": r.ht.scores_x,
        "ht_scores_2": r.ht.scores_2,
        "ht_all_ratios": r.ht.all_ratios,
        "h2_scores_1": r.half2.scores_1,
        "h2_scores_x": r.half2.scores_x,
        "h2_scores_2": r.half2.scores_2,
        "h2_all_ratios": r.half2.all_ratios,
        "ft_scores_1": r.ft.scores_1,
        "ft_scores_x": r.ft.scores_x,
        "ft_scores_2": r.ft.scores_2,
        "ft_all_ratios": r.ft.all_ratios,
        "kickoff_time": raw.kickoff_time if raw else None,
        "actual_ft_home": raw.actual_ft_home if raw else None,
        "actual_ft_away": raw.actual_ft_away if raw else None,
        "actual_ht_home": raw.actual_ht_home if raw else None,
        "actual_ht_away": raw.actual_ht_away if raw else None,
        "actual_h2_home": raw.actual_h2_home if raw else None,
        "actual_h2_away": raw.actual_h2_away if raw else None,
    }
    if patterns:
        row.update(patterns)
    if raw is not None:
        try:
            row["trends"] = compute_trends(raw).model_dump()
        except Exception as exc:
            log.warning("Trend hesaplanamadı [%s]: %s", r.match_id, exc)
            row["trends"] = None
    return row


def _validate_row(row: dict) -> tuple[bool, str | None]:
    """DB'ye yazılmadan önce sanity kontrolleri (Sprint 8.9).

    Bozuk veri DB'ye sızmasın. None döner True/None — sorun yok.
    False/"reason" döner — yazma reddedilir.
    """
    if not row.get("home_team") or row["home_team"] == "?":
        return False, "home_team boş veya '?'"
    if not row.get("away_team") or row["away_team"] == "?":
        return False, "away_team boş veya '?'"
    if not row.get("league_code") or row["league_code"] == "?":
        return False, "league_code boş veya '?'"
    # Lig kontrolü — kupa maçı son anda yakalanır
    if not is_supported_league(row.get("league_code")):
        return False, f"lig maçı değil (kupa filtresi): {row.get('league_code')}"
    # Skorlar makul aralıkta mı (negatif veya saçma değer DB'ye girmesin)
    for k in ("actual_ft_home", "actual_ft_away", "actual_ht_home", "actual_ht_away",
              "actual_h2_home", "actual_h2_away"):
        v = row.get(k)
        if v is not None and (v < 0 or v > 30):
            return False, f"{k}={v} aralık dışı (0-30)"
    return True, None


async def _upsert(
    result: MatchAnalysisResult,
    raw: MatchRawData | None = None,
    patterns: dict[str, dict | None] | None = None,
) -> None:
    """Analiz sonucunu (varsa pattern'lerle) DB'ye yaz; zaten varsa güncelle.

    Geçici DB hatalarına karşı 3 denemeli retry (Supabase PgBouncer drop).
    Sprint 8.9: pre-write validation — bozuk veri reddedilir.
    """
    row = _result_to_row(result, raw, patterns)

    ok, reason = _validate_row(row)
    if not ok:
        log.error("DB write reddedildi [%s]: %s", result.match_id, reason)
        raise ValueError(f"DB write reddedildi [{result.match_id}]: {reason}")

    async def _do():
        updates = dict(row)
        for key in ("kickoff_time", "actual_ft_home", "actual_ft_away", "actual_ht_home",
                    "actual_ht_away", "actual_h2_home", "actual_h2_away"):
            updates[key] = func.coalesce(row[key], getattr(Match, key))
        stmt = (
            insert(Match)
            .values(**row)
            .on_conflict_do_update(index_elements=["match_id"], set_=updates,
                                  where=(Match.deleted_at.is_(None) & or_(
                                      Match.analyzed_at.is_(None), Match.analyzed_at <= result.analyzed_at)))
        )
        async with get_session() as session:
            written = await session.execute(stmt)
            if written.rowcount == 0:
                raise StaleAnalysisWrite(f"Newer or deleted analysis exists: {result.match_id}")

    await _with_retry(_do, label=f"_upsert[{result.match_id}]")


async def run_pipeline(
    target_date: Optional[date] = None,
    only_hot: bool = True,
) -> dict:
    """Hot maçları çek, analiz et, Supabase'e yaz.

    Dönüş: {"analyzed": N, "skipped": N, "errors": N}
    """
    stats = {"analyzed": 0, "skipped": 0, "errors": 0}

    IST = timezone(timedelta(hours=3))

    async with browser_context() as ctx:
        fixtures = await fetch_fixture(target_date=target_date, only_hot=only_hot, ctx=ctx)
        log.info("Pipeline başladı: %d maç işlenecek", len(fixtures))

        # fixture_cache tablosunu doldur — Render Playwright çalıştıramıyor,
        # bu yüzden GitHub Actions'ta pipeline çalışınca cache'i biz yazıyoruz.
        cache_date = (target_date or datetime.now(IST).date()).isoformat()
        league_fixtures = [f for f in fixtures if is_supported_league(f.league_name, f.league_code)]
        cache_json = [
            {
                "match_id": f.match_id,
                "home_team": f.home_team,
                "away_team": f.away_team,
                "league_code": f.league_code,
                "league_name": f.league_name,
                "kickoff_time": f.kickoff_time.isoformat() if f.kickoff_time else None,
            }
            for f in league_fixtures
        ]
        try:
            async with get_session() as session:
                await session.merge(FixtureCache(
                    date=cache_date,
                    matches_json=cache_json,
                    cached_at=datetime.now(timezone.utc),
                ))
            log.info("fixture_cache yazıldı: %s (%d lig maçı)", cache_date, len(cache_json))
        except Exception as exc:
            log.warning("fixture_cache yazılamadı: %s", exc)

        for fixture in fixtures:
            mid = fixture.match_id
            try:
                # Bültenden gelen lig adını match_detail'e geçir (Sprint 8.9):
                # H2H tabanlı tespit yerine bu kullanılır → UEL/UCL gibi maçlarda
                # H2H'ın yanlış "ENG PR" döndürmesi engellenir.
                raw = await fetch_match_detail(
                    mid,
                    ctx=ctx,
                    expected_league_name=fixture.league_name or fixture.league_code,
                )
                check = check_match_filters(raw)

                if not check.passed:
                    log.info("Atlandı [%s]: %s", mid, check.reason.value)
                    stats["skipped"] += 1
                    continue

                result = analyze_match(raw)
                # Pattern B/C'leri hesapla (exclude_match_id=mid ile self-exclusion)
                patterns = await compute_all_patterns(
                    match_id=mid,
                    ht_scores=(result.ht.scores_1, result.ht.scores_x, result.ht.scores_2),
                    h2_scores=(result.half2.scores_1, result.half2.scores_x, result.half2.scores_2),
                    ft_scores=(result.ft.scores_1, result.ft.scores_x, result.ft.scores_2),
                    ft_ratios=result.ft.all_ratios,
                )
                await _upsert(result, raw, patterns)
                stats["analyzed"] += 1
                log.info(
                    "Kaydedildi [%s]: %s vs %s | FT 3.5+: %s",
                    mid,
                    result.home_team,
                    result.away_team,
                    result.ft.scores_1 + result.ft.scores_x + result.ft.scores_2,
                )

            except Exception as e:
                log.error("Hata [%s]: %s", mid, e, exc_info=True)
                stats["errors"] += 1

    log.info(
        "Pipeline tamamlandı: %d analiz, %d atlandı, %d hata",
        stats["analyzed"],
        stats["skipped"],
        stats["errors"],
    )
    return stats


def _merge_result_scores(raw: MatchRawData, existing: Match) -> dict:
    """Keep missing halves only if the final result is unchanged and consistent."""
    ft = (raw.actual_ft_home, raw.actual_ft_away)
    if not all(type(v) is int and 0 <= v <= 30 for v in ft):
        raise ValueError("Invalid final score")

    def valid(pair):
        return all(type(v) is int and 0 <= v <= total for v, total in zip(pair, ft))

    ht = (raw.actual_ht_home, raw.actual_ht_away)
    h2 = (raw.actual_h2_home, raw.actual_h2_away)
    for pair in (ht, h2):
        if any(v is not None for v in pair) and not valid(pair):
            raise ValueError("Invalid or incomplete half score")
    if valid(ht) and valid(h2) and tuple(a + b for a, b in zip(ht, h2)) != ft:
        raise ValueError("Half scores do not match final score")

    if not valid(ht) and not valid(h2) and ft == (existing.actual_ft_home, existing.actual_ft_away):
        previous_ht = (existing.actual_ht_home, existing.actual_ht_away)
        previous_h2 = (existing.actual_h2_home, existing.actual_h2_away)
        if valid(previous_ht):
            ht = previous_ht
        elif valid(previous_h2):
            h2 = previous_h2
    if valid(ht):
        h2 = tuple(total - first for total, first in zip(ft, ht))
    elif valid(h2):
        ht = tuple(total - second for total, second in zip(ft, h2))
    return dict(actual_ft_home=ft[0], actual_ft_away=ft[1],
                actual_ht_home=ht[0], actual_ht_away=ht[1],
                actual_h2_home=h2[0], actual_h2_away=h2[1])


async def update_results(target_date: Optional[date] = None) -> dict:
    """DB'deki maçların gerçek sonuçlarını günceller — Katman A/B/C verisi dokunulmaz.

    Gece çalıştırılır: sabah pipeline'ının kaydettiği maçları tekrar scrape eder,
    actual_ft/ht skorlarını doldurur → /sonuclar sayfasında görünür hale gelir.
    """
    istanbul_tz = timezone(timedelta(hours=3))

    if target_date:
        d = target_date
    else:
        now_ist = datetime.now(istanbul_tz)
        # Gece 00:00–04:00 İstanbul'da çalışırsa önceki günün maçlarını güncelle
        d = (now_ist - timedelta(days=1)).date() if now_ist.hour < 4 else now_ist.date()

    day_start = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=istanbul_tz)
    day_end = day_start + timedelta(days=1)

    async with get_session() as session:
        match_ids = list(
            (await session.execute(
                select(Match.match_id)
                .where(
                    Match.kickoff_time >= day_start,
                    Match.kickoff_time < day_end,
                    Match.deleted_at.is_(None),  # Sprint 8.9: silinmiş maçların skoru güncellenmez
                )
            )).scalars().all()
        )

    log.info("Sonuç güncellemesi: %s için %d maç bulundu", d, len(match_ids))
    stats = {"updated": 0, "not_finished": 0, "errors": 0, "skipped": 0}
    if not match_ids:
        return stats

    async with browser_context() as ctx:
        for match_id in match_ids:
            try:
                raw = await fetch_match_detail(match_id, ctx=ctx)
                if raw.actual_ft_home is None or raw.actual_ft_away is None:
                    stats["not_finished"] += 1
                    continue

                async def _do_update(_raw=raw, _mid=match_id):
                    async with get_session() as session:
                        existing = (await session.execute(
                            select(Match).where(Match.match_id == _mid, Match.deleted_at.is_(None))
                            .with_for_update()
                        )).scalar_one_or_none()
                        if existing is None:
                            return False
                        if _raw.match_id != _mid:
                            raise ValueError("Result match ID does not match requested match")
                        scores = _merge_result_scores(_raw, existing)
                        await session.execute(
                            sa_update(Match)
                            .where(Match.match_id == _mid, Match.deleted_at.is_(None))
                            .values(
                                **scores,
                                result_fetched_at=datetime.now(timezone.utc),
                            )
                        )
                        return True

                updated = await _with_retry(_do_update, label=f"update_results[{match_id}]")
                if not updated:
                    stats["skipped"] += 1
                    continue
                stats["updated"] += 1
                log.info(
                    "Güncellendi [%s]: %s vs %s | %d-%d",
                    match_id, raw.home_team, raw.away_team,
                    raw.actual_ft_home, raw.actual_ft_away,
                )
            except Exception as e:
                log.error("Güncelleme hatası [%s]: %s", match_id, e, exc_info=True)
                stats["errors"] += 1

    log.info(
        "Sonuç güncellemesi tamamlandı: %d güncellendi, %d bitmemiş, %d atlandı, %d hata",
        stats["updated"], stats["not_finished"], stats["skipped"], stats["errors"],
    )
    return stats
