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
from app.analysis.score_snapshots import capture_score_snapshot
from app.analysis.snapshots import RULE_VERSION, prekickoff_picks
from app.analysis.persist import compute_all_patterns
from app.analysis.skip_cache import save_skip
from app.analysis.trends import compute_trends
from app.db.connection import get_session
from app.db.models import AnalysisSnapshot, FixtureCache, Match, SkippedAnalysis
from app.models import FixtureMatch, MatchAnalysisResult, MatchRawData
from app.scraper.browser import browser_context
from app.scraper.fixture import fetch_istanbul_fixture
from app.scraper.fixture_scores import FixtureScore, fetch_fixture_scores
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
    # A completed calculation may legitimately find no matches in any pattern.
    # Keep that state separate from the nullable pattern result columns.
    for key in ("pattern_ht_b", "pattern_ht_c", "pattern_h2_b", "pattern_h2_c",
                "pattern_ft_b", "pattern_ft_c"):
        row[key] = patterns.get(key) if patterns is not None else None
    row["pattern_computed_at"] = r.analyzed_at if patterns is not None else None
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

    picks = prekickoff_picks(
        analyzed_at=result.analyzed_at,
        kickoff_time=raw.kickoff_time if raw else None,
        league_name=raw.league_name if raw else None,
        league_code=raw.league_code if raw else None,
        patterns=patterns,
    )

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
            if picks is not None:
                await session.execute(
                    insert(AnalysisSnapshot).values(
                        match_id=result.match_id,
                        rule_version=RULE_VERSION,
                        captured_at=result.analyzed_at,
                        kickoff_time=raw.kickoff_time,
                        league_name=raw.league_name or canonical_league_name(raw.league_code),
                        picks=picks,
                    ).on_conflict_do_nothing(
                        index_elements=["match_id", "rule_version"],
                    )
                )
            if raw is not None:
                await capture_score_snapshot(
                    session,
                    match_id=result.match_id,
                    analyzed_at=result.analyzed_at,
                    captured_at=datetime.now(timezone.utc),
                    kickoff_time=raw.kickoff_time,
                    league_name=raw.league_name,
                    league_code=raw.league_code,
                    model_scores=result.ft.scores_1 + result.ft.scores_x + result.ft.scores_2,
                )

    await _with_retry(_do, label=f"_upsert[{result.match_id}]")


async def save_fixture_cache(cache_day: date, fixtures: list[FixtureMatch]) -> int:
    """Keep compact source competition labels and already observed scores."""
    cache_date = cache_day.isoformat()
    istanbul_tz = timezone(timedelta(hours=3))
    cache_json = [
        {
            "match_id": f.match_id,
            "home_team": f.home_team,
            "away_team": f.away_team,
            "league_code": f.league_code,
            "league_name": f.league_name,
            "kickoff_time": f.kickoff_time.isoformat() if f.kickoff_time else None,
        }
        for f in fixtures
    ]
    async with get_session() as session:
        previous = await session.get(FixtureCache, cache_date)
        if previous is not None and isinstance(previous.matches_json, list):
            old_by_id = {item.get("match_id"): item for item in previous.matches_json
                         if isinstance(item, dict)}
            score_keys = ("score_status", "score_home", "score_away",
                          "score_checked_at", "actual_ht_home", "actual_ht_away")
            for item in cache_json:
                old = old_by_id.get(item["match_id"], {})
                item.update({key: old[key] for key in score_keys if key in old})
            new_ids = {item["match_id"] for item in cache_json}
            for old in old_by_id.values():
                if old.get("match_id") in new_ids or not old.get("kickoff_time"):
                    continue
                try:
                    old_day = datetime.fromisoformat(old["kickoff_time"]).astimezone(istanbul_tz).date()
                except (ValueError, TypeError):
                    continue
                if old_day == cache_day:
                    cache_json.append(old)
        await session.merge(FixtureCache(
            date=cache_date,
            matches_json=cache_json,
            cached_at=datetime.now(timezone.utc),
        ))
    log.info("fixture_cache yazıldı: %s (%d kaynak maçı)", cache_date, len(cache_json))
    return len(cache_json)


async def refresh_fixture_cache(target_date: date, only_hot: bool = True) -> int:
    """Prepare a future bulletin without running analysis or storing match details."""
    async with browser_context() as ctx:
        fixtures = await fetch_istanbul_fixture(target_date, only_hot=only_hot, ctx=ctx)
    return await save_fixture_cache(target_date, fixtures)


async def _prepared_match_ids(match_ids: list[str]) -> set[str]:
    """Read only IDs already analyzed before kickoff or recently rejected."""
    if not match_ids:
        return set()
    now = datetime.now(timezone.utc)
    try:
        async with get_session() as session:
            analyzed = (await session.execute(select(Match.match_id).where(
                Match.match_id.in_(match_ids), Match.deleted_at.is_(None),
                Match.ft_scores_1.is_not(None), Match.pattern_computed_at.is_not(None),
                Match.analyzed_at < Match.kickoff_time,
                Match.pattern_computed_at < Match.kickoff_time,
            ))).scalars().all()
            rejected = (await session.execute(select(SkippedAnalysis.match_id).where(
                SkippedAnalysis.match_id.in_(match_ids),
                SkippedAnalysis.checked_at >= now - timedelta(hours=24),
            ))).scalars().all()
        return set(analyzed) | set(rejected)
    except Exception as exc:
        log.warning("Hazır analiz ID'leri okunamadı, pipeline devam edecek: %s", exc)
        return set()


async def run_pipeline(
    target_date: Optional[date] = None,
    only_hot: bool = True,
    incremental: bool = False,
) -> dict:
    """Hot maçları çek, analiz et, Supabase'e yaz.

    Dönüş: {"analyzed": N, "skipped": N, "errors": N}
    """
    stats = {"analyzed": 0, "skipped": 0, "errors": 0}

    IST = timezone(timedelta(hours=3))

    async with browser_context() as ctx:
        cache_day = target_date or datetime.now(IST).date()
        source_fixtures = await fetch_istanbul_fixture(cache_day, only_hot=only_hot, ctx=ctx)
        fixtures = [fixture for fixture in source_fixtures
                    if is_supported_league(fixture.league_name, fixture.league_code)]
        log.info("Pipeline başladı: %d maç işlenecek", len(fixtures))

        # GitHub Actions'taki scraper bülteni API isteğinden önce hazırlar.
        try:
            await save_fixture_cache(cache_day, source_fixtures)
        except Exception as exc:
            log.warning("fixture_cache yazılamadı: %s", exc)

        prepared = await _prepared_match_ids([f.match_id for f in fixtures]) if incremental else set()
        if prepared:
            log.info("Önceden hazırlanmış %d maç yeniden analiz edilmeyecek", len(prepared))

        for fixture in fixtures:
            mid = fixture.match_id
            if mid in prepared:
                stats["skipped"] += 1
                continue
            if fixture.kickoff_time and fixture.kickoff_time.astimezone(timezone.utc) <= datetime.now(timezone.utc):
                stats["skipped"] += 1
                continue
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
                    if check.reason is not None:
                        try:
                            await save_skip(raw, check.reason)
                        except Exception as exc:
                            log.warning("Atlanmış analiz kaydedilemedi [%s]: %s", mid, exc)
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


def _merge_fixture_scores(
    fixtures: list[dict], snapshots: dict[str, FixtureScore], checked_at: datetime,
) -> list[dict]:
    """Attach observed scores to today's fixture list without losing its metadata."""
    merged = []
    for fixture in fixtures:
        item = dict(fixture)
        snapshot = snapshots.get(item.get("match_id"))
        if snapshot is not None and item.get("score_status") != "finished":
            item["score_status"] = snapshot.status
            item["score_home"] = snapshot.home
            item["score_away"] = snapshot.away
            item["score_checked_at"] = checked_at.isoformat()
            if snapshot.status == "finished":
                item["actual_ht_home"] = snapshot.ht_home
                item["actual_ht_away"] = snapshot.ht_away
        elif snapshot is not None and snapshot.status == "finished":
            # A verified correction to a final result may arrive later.
            item.update(score_status="finished", score_home=snapshot.home,
                        score_away=snapshot.away, score_checked_at=checked_at.isoformat(),
                        actual_ht_home=snapshot.ht_home, actual_ht_away=snapshot.ht_away)
        merged.append(item)
    return merged


async def update_results(target_date: Optional[date] = None) -> dict:
    """Refresh scores from the source calendar pages and update analyzed matches."""
    istanbul_tz = timezone(timedelta(hours=3))

    if target_date:
        d = target_date
    else:
        now_ist = datetime.now(istanbul_tz)
        # Gece 00:00–04:00 İstanbul'da çalışırsa önceki günün maçlarını güncelle
        d = (now_ist - timedelta(days=1)).date() if now_ist.hour < 4 else now_ist.date()

    day_start = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=istanbul_tz)
    day_end = day_start + timedelta(days=1)

    stats = {"updated": 0, "not_finished": 0, "errors": 0, "skipped": 0}
    async with get_session() as session:
        fixture_row = await session.get(FixtureCache, d.isoformat())
        match_rows = (await session.execute(
            select(Match).where(
                Match.kickoff_time >= day_start,
                Match.kickoff_time < day_end,
                Match.deleted_at.is_(None),
            )
        )).scalars().all()

    fixtures = fixture_row.matches_json if fixture_row and isinstance(fixture_row.matches_json, list) else []
    match_by_id = {row.match_id: row for row in match_rows}
    fixture_ids = {item["match_id"] for item in fixtures if isinstance(item, dict) and "match_id" in item}
    wanted_ids = fixture_ids | match_by_id.keys()
    log.info("Sonuç güncellemesi: %s için %d bülten, %d analiz maçı", d, len(fixtures), len(match_rows))
    if not wanted_ids:
        return stats
    snapshots = {mid: score for mid, score in (await fetch_fixture_scores(d)).items() if mid in wanted_ids}
    missing_ids = wanted_ids - snapshots.keys()
    if missing_ids:
        # UTC+8 calendar flips at 19:00 Istanbul; late fixtures live on the next page.
        snapshots.update({mid: score for mid, score in (await fetch_fixture_scores(d + timedelta(days=1))).items()
                          if mid in missing_ids})
    if not snapshots:
        raise RuntimeError(f"Kaynak bültende {d} için kayıtlı maç bulunamadı")
    checked_at = datetime.now(timezone.utc)
    stats["updated"] = sum(score.status == "finished" for score in snapshots.values())
    stats["not_finished"] = len(wanted_ids) - stats["updated"]

    async def _save():
        async with get_session() as session:
            if fixture_row is not None:
                await session.execute(
                    sa_update(FixtureCache).where(FixtureCache.date == d.isoformat())
                    .values(matches_json=_merge_fixture_scores(fixtures, snapshots, checked_at))
                )
            for match_id, existing in match_by_id.items():
                snapshot = snapshots.get(match_id)
                if snapshot is None or snapshot.status != "finished":
                    continue
                raw = MatchRawData(
                    match_id=match_id, home_team=existing.home_team,
                    away_team=existing.away_team, league_code=existing.league_code or "",
                    actual_ft_home=snapshot.home, actual_ft_away=snapshot.away,
                    actual_ht_home=snapshot.ht_home, actual_ht_away=snapshot.ht_away,
                )
                scores = _merge_result_scores(raw, existing)
                await session.execute(
                    sa_update(Match).where(Match.match_id == match_id, Match.deleted_at.is_(None))
                    .values(**scores, result_fetched_at=checked_at)
                )

    await _with_retry(_save, label=f"update_results[{d}]")

    log.info(
        "Sonuç güncellemesi tamamlandı: %d güncellendi, %d bitmemiş, %d atlandı, %d hata",
        stats["updated"], stats["not_finished"], stats["skipped"], stats["errors"],
    )
    return stats
