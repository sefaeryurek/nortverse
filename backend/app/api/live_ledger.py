"""Canlı İY→MS tahminlerini devre arasında bir kez dondurur (değişmez defter).

İzleyici WebSocket yayınından bağımsız çalışır — sayfayı kimse açmasa da kayıt alınır.
Sadece başlama saati [şimdi−150dk, şimdi−40dk] aralığında analiz edilmiş maç varken
canlı skor görüntüsünü okur.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.analysis import live_2h, live_archive, live_poisson
from app.analysis.league_filter import is_tracked_league
from app.analysis.ledger import record_predictions
from app.analysis.live_model import COND_WINDOW_YEARS, LIVE_RULE_VERSION, get_cond_table, predict_live
from app.analysis.persist import hash_string
from app.api.live_snapshot import get_live_snapshot
from app.db.connection import get_session
from app.db.models import Match, MatchHtObservation
from app.scraper.fixture_scores import FixtureScore, phase_from_minute

log = logging.getLogger(__name__)

WATCH_INTERVAL = 60.0
WINDOW_START = timedelta(minutes=150)
WINDOW_END = timedelta(minutes=40)
_OBS_SOURCE = "livescore"
# K10 (Sprint 94): eski COND modeli (live-ms-v1) ekranda yok ve penceresiz yazılıyordu (24 Ekim'de 17 kayıt
# ~97. dakikada) → artık deftere yazılmaz. Tahmin yine hesaplanır (CLI denemesi gösterir).
# "Bu maç değerlendirildi" işareti: izleyicinin yazdığı İY gözlemi (source=livescore) — kayıt çıkmasa da yazılır.
RECORD_LIVE_MS = False

_watcher_task: asyncio.Task | None = None


def match_phase(fs: FixtureScore) -> str | None:
    return fs.phase or phase_from_minute(fs.minute)


def observed_ht(fs: FixtureScore) -> tuple[int, int] | None:
    """Devre arasında anlık skor = İY skoru; 2. yarıda panonun İY alanı."""
    phase = match_phase(fs)
    if phase == "ht" and fs.home is not None and fs.away is not None:
        return fs.home, fs.away
    if phase == "2h" and fs.ht_home is not None and fs.ht_away is not None:
        return fs.ht_home, fs.ht_away
    return None


ARCHIVE_FREEZE_MAX_MINUTE = 50


# Dakika bilinmiyorsa (kaynak panosu 2. yarıda dakika vermez) başlamadan geçen süre kullanılır:
# 45 + ~15 dk ara + 5 dk ≈ 2. yarının 50. dakikası.
ARCHIVE_FREEZE_MAX_ELAPSED = timedelta(minutes=65)


def archive_freeze_allowed(fs: FixtureScore, kickoff: datetime | None = None,
                           now: datetime | None = None) -> bool:
    """Arşiv işaretleri sadece devre arasında ya da 2. yarının ilk dakikalarında yazılır.

    Geç dondurmada "skor hâlâ İY skoru" koşulu sonucu ayıklar (ör. 80'de 0-0 → Üst işaretleri
    düşük çıkar); bu yüzden 2. yarıda 50. dakika geçtiyse yazılmaz. Dakika bilinmiyorsa
    başlama saatinden geçen süreye bakılır (eskiden hiç yazılmıyordu → yeniden başlatma sonrası kayıp).
    """
    phase = match_phase(fs)
    if phase == "ht":
        return True
    if phase != "2h":
        return False
    head = (fs.minute or "").strip().split("+")[0]
    if head.isdigit():
        return int(head) <= ARCHIVE_FREEZE_MAX_MINUTE
    if kickoff is None:
        return False
    return (now or datetime.now(timezone.utc)) - kickoff <= ARCHIVE_FREEZE_MAX_ELAPSED


def pattern_hash(match: Match) -> str | None:
    return hash_string({f: getattr(match, f"pattern_{f}_hash") for f in "bcd"})


def ledger_rows(match: Match, prediction: dict, as_of: datetime, ht_observation_id: int,
                late: bool) -> list[dict]:
    """Tahmin sözlüğünden defter satırları (MS 1X2 + uygunsa MS Ü2.5 ve KG)."""
    ht = prediction["ht"]
    common = {
        "source": "live_ht", "rule_version": LIVE_RULE_VERSION, "pattern_hash": pattern_hash(match),
        "match_id": match.match_id, "league_name": match.league_name or "",
        "kickoff_time": match.kickoff_time, "as_of": as_of, "period": "ft",
        "ht_home": ht["home"], "ht_away": ht["away"], "ht_observation_id": ht_observation_id,
    }
    ms = prediction["ms"]
    rows = [{
        **common, "market": "result", "selection": ms["pick"],
        "prob_shown_bp": round(ms["prob"] * 10000),
        "prob_raw_bp": round(ms["ht_baseline"]["probs"][ms["pick"]] * 10000),
        "baseline_selection": ms["ht_baseline"]["pick"],
        "baseline_prob_bp": round(ms["ht_baseline"]["prob"] * 10000),
        "confidence_tier": ms["tier"], "sample_n": ms["n"] or None,
        "details": {**prediction, "late": late, "archive_rule_version": live_archive.LIVE_ARCHIVE_RULE_VERSION},
    }]
    for market, key in (("ou_25", "over25"), ("kg", "btts")):
        block = prediction[key]
        if block.get("applicable"):
            rows.append({
                **common, "market": market, "selection": block["pick"],
                "prob_shown_bp": round(block["prob"] * 10000),
                "confidence_tier": block["tier"], "sample_n": block["n"] or None,
                "details": {key: block, "late": late},
            })
    return rows


async def _ht_observation_id(session, match: Match, ht: tuple[int, int], phase: str,
                             observed_at: datetime) -> int:
    revision = f"{ht[0]}-{ht[1]}"
    inserted = await session.execute(
        insert(MatchHtObservation).values(
            match_id=match.match_id, kickoff_time=match.kickoff_time,
            ht_home=ht[0], ht_away=ht[1], phase="ht_break" if phase == "ht" else "second_half",
            observed_at=observed_at, source=_OBS_SOURCE, source_revision=revision,
        ).on_conflict_do_nothing(constraint="uq_match_ht_observations_source_revision")
        .returning(MatchHtObservation.id)
    )
    obs_id = inserted.scalar_one_or_none()
    if obs_id is None:
        obs_id = (await session.execute(
            select(MatchHtObservation.id).where(
                MatchHtObservation.match_id == match.match_id,
                MatchHtObservation.source == _OBS_SOURCE,
                MatchHtObservation.source_revision == revision,
            )
        )).scalar_one()
    return obs_id


async def plan_live_freeze(match: Match, fs: FixtureScore) -> tuple[str, dict | None]:
    """Dondurma kararı (yazmadan): ('ready', tahmin) ya da (neden, None)."""
    ht = observed_ht(fs)
    phase = match_phase(fs)
    if ht is None or phase not in ("ht", "2h"):
        return "no_ht", None
    if match.kickoff_time is None or datetime.now(timezone.utc) <= match.kickoff_time:
        return "not_started", None
    if phase == "2h" and (fs.home, fs.away) != ht:
        # 2. yarıda gol gördükten sonra "tahmin" yazılmaz.
        return "late_score_changed", None
    try:
        table = await get_cond_table()
        prediction = predict_live(
            table, match.league_name or "", ht,
            [match.pattern_ft_b, match.pattern_ft_c, match.pattern_ft_d],
        )
    except Exception:
        # Eski COND modelinin hatası ekrandaki karar (live-poisson-v1.1) ve gölge kayıtları engellemez.
        log.warning("COND tahmini hesaplanamadı [%s]", match.match_id, exc_info=True)
        prediction = None
    return "ready", prediction


async def _poisson_shadow(match: Match, fs: FixtureScore) -> tuple[dict | None, list[dict]]:
    """Poisson kararları (ekrandaki live-poisson-v1.1, penceresiz COND); hata diğer kayıtları asla engellemez."""
    try:
        ht = observed_ht(fs)
        league = match.league_name or ""
        model = await live_poisson.get_poisson_model()
        prediction = live_poisson.predict(model, league, match.home_team, match.away_team, ht)
        picks = live_poisson.decisions(prediction, live_poisson.cond_lookup(await get_cond_table(), league, ht))
        return prediction, picks
    except Exception:
        log.warning("Gölge Poisson tahmini hesaplanamadı [%s]", match.match_id, exc_info=True)
        return None, []


async def _windowed_shadows(match: Match, fs: FixtureScore, prediction: dict | None) -> tuple[dict | None, list[dict]]:
    """Pencereli COND'lu gölge sürümler (Sprint 94 C1): live-arch-v2.1 görünümü + live-poisson-v1.2 kararları."""
    ht = observed_ht(fs)
    league = match.league_name or ""
    view = None
    picks: list[dict] = []
    try:
        table = await get_cond_table(COND_WINDOW_YEARS)
        view = await live_archive.load_view(
            match.match_id, {"b": match.pattern_ft_b, "c": match.pattern_ft_c, "d": match.pattern_ft_d},
            ht, league=league, table=table)
        if prediction is not None:
            picks = live_poisson.decisions(prediction, live_poisson.cond_lookup(table, league, ht))
    except Exception:
        log.warning("Pencereli COND gölge kararları hesaplanamadı [%s]", match.match_id, exc_info=True)
    return view, picks


async def _live_2h_shadow(match: Match, fs: FixtureScore) -> tuple[list[dict], dict | None]:
    """Gölge 2. yarı işaretleri (live-2h-v1.1); hata ana kaydı asla engellemez."""
    try:
        ht = observed_ht(fs)
        league = match.league_name or ""
        model = await live_poisson.get_poisson_model()
        dist = live_poisson.final_grid(model, league, match.home_team, match.away_team, ht)
        if dist is None:
            return [], None
        # live-2h-v1.1: COND 10 yıllık pencereyle
        table = await get_cond_table(live_2h.RULE_PARAMS["cond_window_years"])
        picks = live_2h.decide(dist["grid"], ht, live_2h.cond_lookup(table, league, ht))
        lambdas = {"2h": {"home": round(dist["r_h"], 3), "away": round(dist["r_a"], 3)},
                   "ft": {"home": round(dist["lam_h"], 3), "away": round(dist["lam_a"], 3)}}
        return picks, lambdas
    except Exception:
        log.warning("Gölge 2. yarı işaretleri hesaplanamadı [%s]", match.match_id, exc_info=True)
        return [], None


MARKET_SNAPSHOT_TIMEOUT = 10.0


async def market_snapshot(match_id: str, now: datetime) -> dict | None:
    """Devre arası anındaki MS piyasa fiyatı (Sprint 94 I2). Karar kuralına girmez (sürüm artmaz); canlı kararların
    gerçek fiyatını sonradan ölçmek için `details.market`'e yazılır. Kaynak yanıt vermezse kayıt yine yapılır."""
    try:
        from app.scraper.odds import current_odds

        snap = await asyncio.wait_for(current_odds(match_id), MARKET_SNAPSHOT_TIMEOUT)
    except Exception as exc:
        log.info("Devre arası fiyatı alınamadı [%s]: %s", match_id, exc)
        return None
    if not snap.get("ft"):
        return None
    return {"ft": snap["ft"], "live": snap.get("live"), "fetched_at": now.isoformat()}


def attach_market(rows: list[dict], market: dict | None) -> list[dict]:
    """Maç sonu (ve 2. yarı) kararlarına devre arası fiyatını ekler; İY periyodu zaten bitmiş."""
    if market:
        for row in rows:
            if row.get("period") in ("ft", "h2") and isinstance(row.get("details"), dict):
                row["details"] = {**row["details"], "market": market}
    return rows


async def freeze_live_prediction(match: Match, fs: FixtureScore, *, dry_run: bool = False,
                                 report: dict | None = None) -> str:
    """İY gözlemini ve tahmini bir kez kaydeder. Durum kodunu döner (tahmin `report`'a yazılır)."""
    status, prediction = await plan_live_freeze(match, fs)
    view = None
    if status == "ready":
        try:
            view = await live_archive.load_view(
                match.match_id, {"b": match.pattern_ft_b, "c": match.pattern_ft_c, "d": match.pattern_ft_d},
                observed_ht(fs), league=match.league_name or "", table=await get_cond_table())
        except Exception:
            # Arşiv görünümü hatası ana kaydı ve İY gözlemini engellemez (eskiden tüm dondurma düşüyordu).
            log.warning("Canlı arşiv görünümü hesaplanamadı [%s]", match.match_id, exc_info=True)
    shadow_pred, shadow_picks = await _poisson_shadow(match, fs) if status == "ready" else (None, [])
    h2_picks, h2_lambdas = await _live_2h_shadow(match, fs) if status == "ready" else ([], None)
    view_w, poisson_w = await _windowed_shadows(match, fs, shadow_pred) if status == "ready" else (None, [])
    if report is not None:
        report["prediction"] = prediction
        report["view"] = view
        report["poisson"] = shadow_picks
        report["live_2h"] = h2_picks
    if status == "late_score_changed":
        log.info("Canlı tahmin dondurulmadı (2. yarıda skor değişmiş) [%s]", match.match_id)
    if status != "ready":
        return status
    if dry_run:
        return "dry_run"
    ht = observed_ht(fs)
    phase = match_phase(fs)
    now = datetime.now(timezone.utc)
    market = await market_snapshot(match.match_id, now)  # DB işlemi açılmadan (HTTP beklerken kilit tutulmasın)
    async with get_session() as session:
        obs_id = await _ht_observation_id(session, match, ht, phase, now)
        rows = (ledger_rows(match, prediction, now, obs_id, late=phase == "2h")
                if RECORD_LIVE_MS and prediction is not None else [])
        # Canlı arşiv %85+ işaretleri: ana kayıt ile aynı İY gözlemine bağlı; geç kalındıysa yazılmaz.
        # Arşiv ve gölge işaretleri sadece devre arası / 2. yarının başında; geç kalındıysa yazılmaz.
        window_ok = archive_freeze_allowed(fs, match.kickoff_time, now)
        archive_ok = window_ok and view is not None
        common = {
            "match_id": match.match_id, "league_name": match.league_name or "",
            "kickoff_time": match.kickoff_time, "as_of": now, "pattern_hash": pattern_hash(match),
            "ht_home": ht[0], "ht_away": ht[1], "ht_observation_id": obs_id,
        }
        if archive_ok:
            rows += live_archive.ledger_rows(view, common, late=phase == "2h")
        if window_ok and shadow_picks:
            # Ekrandaki ana canlı karar (live-poisson-v1.1)
            rows += live_poisson.ledger_rows(shadow_pred, shadow_picks, common, late=phase == "2h")
        if window_ok and view_w is not None:
            # Gölge: aynı kurallar 10 yıllık COND ile (live-arch-v2.1, live-poisson-v1.2) — K9, 100 karar sonra karne
            rows += live_archive.ledger_rows(view_w, common, late=phase == "2h", shadow=True)
        if window_ok and poisson_w:
            rows += live_poisson.ledger_rows(shadow_pred, poisson_w, common, late=phase == "2h", shadow=True)
        if window_ok and h2_picks:
            # Gölge 2. yarı işaretleri (live-2h-v1.1): ekranda yok, 100 tekil karar sonra karne
            rows += live_2h.ledger_rows(h2_picks, common, lambdas=h2_lambdas, late=phase == "2h")
        if not window_ok:
            log.info("Arşiv/gölge işaretleri yazılmadı (2. yarı %s. dk) [%s]", fs.minute, match.match_id)
        elif view is None:
            log.warning("Arşiv işaretleri yazılmadı (görünüm yok) [%s]", match.match_id)
        written = await record_predictions(session, attach_market(rows, market))
    if written:
        log.info("Canlı kararlar donduruldu [%s] İY %s-%s · %d satır (%d arşiv işareti, %d Poisson)",
                 match.match_id, ht[0], ht[1], written, len(view["highlights"]) if archive_ok else 0,
                 len(shadow_picks) if window_ok else 0)
        return "frozen"
    # İY gözlemi yazıldı ama kaydedilecek karar yok (ya da geç kalındı) → maç değerlendirilmiş sayılır
    return "evaluated"


async def run_tick(*, dry_run: bool = False, snapshot=None) -> list[dict]:
    """İzleyicinin bir turu. Her aday maç için {match, score, status, prediction} döner.

    `snapshot` verilmezse süreç içi canlı görüntü kullanılır (CLI tam yenilenmiş görüntü verir).
    """
    now = datetime.now(timezone.utc)
    try:
        from app.config import ISTANBUL_TZ
        from app.pipeline.runner import sync_kickoffs_from_cache
        today = now.astimezone(ISTANBUL_TZ).date()
        await sync_kickoffs_from_cache([today - timedelta(days=1), today])
    except Exception:
        log.warning("Başlama saatleri senkronlanamadı", exc_info=True)
    async with get_session() as session:
        candidates = (await session.execute(
            select(Match).where(
                Match.deleted_at.is_(None),
                Match.ft_scores_1.isnot(None),
                Match.kickoff_time >= now - WINDOW_START,
                Match.kickoff_time <= now - WINDOW_END,
            ).order_by(Match.kickoff_time)
        )).scalars().all()
        # 7 ana lig + gölgedeki ligler (arşivi olanlar); diğer küçük liglerin arşivi yok, kayıt gürültü olur.
        # Gölge liglerin kayıtları ekranda görünmez, değerlendirmede ayrı karne (scope=shadow).
        candidates = [m for m in candidates if is_tracked_league(m.league_name, m.league_code)]
        if not candidates:
            return []
        # Değerlendirilmiş maç = izleyicinin İY gözlemi var (kararlarla aynı işlemde yazılır).
        # Eskiden live-ms-v1 ana satırına bakılıyordu; o model hata verince diğer kayıtlar da tekrar denenmiyordu.
        frozen = set((await session.execute(
            select(MatchHtObservation.match_id).where(
                MatchHtObservation.source == _OBS_SOURCE,
                MatchHtObservation.match_id.in_([m.match_id for m in candidates]),
            ).distinct()
        )).scalars().all())
    report = [{"match": m, "score": None, "status": "already_frozen", "prediction": None}
              for m in candidates if m.match_id in frozen]
    pending = [m for m in candidates if m.match_id not in frozen]
    if not pending:
        return report
    if snapshot is None:
        snapshot = await get_live_snapshot()
    for match in pending:
        entry = {"match": match, "score": None, "status": "no_snapshot", "prediction": None}
        report.append(entry)
        if snapshot is None:
            continue
        fs = snapshot.scores.get(match.match_id)
        entry["score"] = fs
        if fs is None or fs.status != "live":
            entry["status"] = "not_live"
            continue
        try:
            entry["status"] = await freeze_live_prediction(match, fs, dry_run=dry_run, report=entry)
        except Exception:
            entry["status"] = "error"
            log.warning("Canlı tahmin dondurulamadı [%s]", match.match_id, exc_info=True)
    return report


_SETTLE_EVERY = 300.0
_last_settle = 0.0


async def _settle_coupons() -> None:
    """Kuponlar sayfa açılınca değil, izleyici turunda (5 dk'da bir) sonuçlanır (Sprint 94 J5)."""
    global _last_settle
    import time

    if time.monotonic() - _last_settle < _SETTLE_EVERY:
        return
    _last_settle = time.monotonic()
    from app.analysis.coupons import settle_pending

    try:
        async with get_session() as session:
            written = await settle_pending(session)
        if written:
            log.info("Kupondaş: %d kupon maçı sonuçlandı", written)
    except Exception:
        log.warning("Kupon sonuçlandırma başarısız", exc_info=True)


async def _tick() -> None:
    await run_tick()
    await _settle_coupons()


async def _watch_loop() -> None:
    while True:
        try:
            await _tick()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.warning("Canlı defter izleyicisi hatası", exc_info=True)
        await asyncio.sleep(WATCH_INTERVAL)


def start_live_watcher() -> None:
    global _watcher_task
    if _watcher_task is None or _watcher_task.done():
        _watcher_task = asyncio.create_task(_watch_loop())
        log.info("Canlı defter izleyicisi başlatıldı (%.0fs)", WATCH_INTERVAL)


async def stop_live_watcher() -> None:
    global _watcher_task
    task = _watcher_task
    _watcher_task = None
    if task is not None and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
