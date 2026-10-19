"""Maç öncesi strateji v4 (ft-display-v4) + tahmin defteri yazımı.

1X2: A1+A2+A3 (her biri ≥10 maç) havuzlanır, Dirichlet(k=20) ile son 3 sezon lig ortalamasına
çekilir. Yayın şartı: havuz ≥30 maç, seçimin olasılığı lig ortalamasını ≥5 puan aşıyor, seçim X değil.
Backtest (5509 maç, 2023-07..2026-10): yayınlanan 2350 seçim %50.5 tuttu (aynı maçlarda lig ortalaması
seçimi %46.4, iki dönemde de +4.1); gösterilen ortalama olasılık %51.5 → kalibre.
Ü/A 2.5 ve KG'de beceri yok → Top Picks'e girmez, deftere `informational` olarak yazılır.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.ledger import record_predictions
from app.analysis.league_filter import canonical_league_name, is_supported_league
from app.analysis.live_model import OUTCOMES, get_cond_table, prematch_posterior
from app.analysis.market_catalog import SUMMARY_MARKET_KEYS, get_market
from app.analysis.persist import hash_string, pattern_hashes
from app.config import ISTANBUL_TZ
from app.db.models import AnalysisSnapshot, Match

log = logging.getLogger(__name__)

# Arşiv algoritması (A2 c4, A3 d4) Sprint 91.4'te değişti → arşive dayanan iki kural yeni sürüm (Sprint 92.4).
V4_RULE_VERSION = "ft-display-v4.1"
MARKET_SUMMARY_RULE_VERSION = "market-summary-v2"
LEGACY_V4_RULE_VERSIONS = ("ft-display-v4",)  # o gün gösterilen eski seçimler okunabilsin
RULE_PARAMS = {
    "k": 20.0, "min_archive_matches": 10, "min_pooled": 30, "min_edge": 0.05,
    "exclude": ["X"], "tier_high_edge": 0.15, "tier_medium_edge": 0.10,
}
_ARCHIVES = (("archive_1", "a1", "b"), ("archive_2", "a2", "c"), ("archive_3", "a3", "d"))
_RESULT_FIELDS = {"1": "result_1_pct", "X": "result_x_pct", "2": "result_2_pct"}


def rule_params_fingerprint() -> str:
    """Kural parametreleri + arşiv algoritması sürümü: ikisinden biri değişince sabitlenmiş test kırılır
    (arşiv havuzunu kullanan kural, arşiv değişince de yeni sürüm almalı)."""
    from app.analysis.persist import PATTERN_ALGO_VERSION

    payload = {**RULE_PARAMS, "pattern_algo": PATTERN_ALGO_VERSION}
    return hashlib.sha1(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]


def _eligible_archives(patterns: dict) -> list[tuple[str, dict]]:
    out = []
    for name, _, family in _ARCHIVES:
        blob = patterns.get(f"pattern_ft_{family}")
        if isinstance(blob, dict) and (blob.get("match_count") or 0) >= RULE_PARAMS["min_archive_matches"]:
            out.append((name, blob))
    return out


def _tier(edge: float) -> str:
    if edge >= RULE_PARAMS["tier_high_edge"]:
        return "high"
    if edge >= RULE_PARAMS["tier_medium_edge"]:
        return "medium"
    return "low"


def decide_result(patterns: dict, prior: dict[str, float]) -> dict | None:
    """1X2 kararı; yayınlanmayacaksa None (sebebi `abstain_reason`'dan)."""
    archives = _eligible_archives(patterns)
    if not archives:
        return {"abstain_reason": "archive_sample_below_minimum"}
    post, pooled_n = prematch_posterior([b for _, b in archives], prior, k=RULE_PARAMS["k"])
    pick = max(OUTCOMES, key=lambda o: post[o])
    edge = post[pick] - prior[pick]
    decision = {
        "selection": pick, "posterior": post, "prior": prior, "edge": edge, "pooled_n": pooled_n,
        "archives": archives, "tier": _tier(edge),
        "agreeing": [name for name, blob in archives
                     if max(OUTCOMES, key=lambda o: blob.get(_RESULT_FIELDS[o], 0.0)) == pick],
    }
    if pooled_n < RULE_PARAMS["min_pooled"]:
        decision["abstain_reason"] = "pooled_sample_below_minimum"
    elif pick in RULE_PARAMS["exclude"]:
        decision["abstain_reason"] = "draw_excluded"
    elif edge < RULE_PARAMS["min_edge"]:
        decision["abstain_reason"] = "edge_below_minimum"
    return decision


def _raw_frequency(archives: list[tuple[str, dict]], selection: str) -> float:
    total = sum(b["match_count"] for _, b in archives)
    return sum(b["match_count"] * b.get(_RESULT_FIELDS[selection], 0.0) for _, b in archives) / total


def build_v4_recommendations(patterns: dict | None, prior: dict[str, float]) -> list[dict]:
    """Ekranda gösterilen Top Picks (şimdilik sadece MS 1X2)."""
    if not isinstance(patterns, dict):
        return []
    decision = decide_result(patterns, prior)
    if decision is None or decision.get("abstain_reason"):
        return []
    archives = decision["archives"]
    by_name = dict(archives)
    pick = decision["selection"]
    pick_row = {
        "recommendation_id": f"{V4_RULE_VERSION}:result:{pick}",
        "archive": "+".join(name for name, _ in archives),
        "market": "result",
        "selection": pick,
        "frequency_pct": round(_raw_frequency(archives, pick), 2),
        "match_count": int(round(decision["pooled_n"])),
        "calibrated_pct": round(decision["posterior"][pick] * 100, 1),
        "margin": round(decision["edge"] * 100, 1),
        "is_confident": decision["tier"] == "high",
        "confidence_tier": decision["tier"],
        "prior_pct": round(decision["prior"][pick] * 100, 1),
        "agreement": len(decision["agreeing"]),
    }
    for name, _, _family in _ARCHIVES:
        blob = by_name.get(name)
        pick_row[f"{name}_frequency_pct"] = round(blob.get(_RESULT_FIELDS[pick], 0.0), 2) if blob else None
        pick_row[f"{name}_match_count"] = blob["match_count"] if blob else None
    return [pick_row]


def _pooled_binary(archives: list[tuple[str, dict]], field: str, prior: float) -> tuple[float, float]:
    total = sum(b["match_count"] for _, b in archives)
    hits = sum(b["match_count"] * b.get(field, 0.0) / 100 for _, b in archives)
    k = RULE_PARAMS["k"]
    return (hits + k * prior) / (total + k), total


def _market_summary_rows(patterns: dict, common: dict) -> list[dict]:
    """Ana Pazar Özeti kazananları (confidence.ts getMarketSummary ile aynı: eşiksiz en yüksek)."""
    rows = []
    for period in ("ht", "h2", "ft"):
        for key in SUMMARY_MARKET_KEYS:
            spec = get_market(key)
            if not spec.active_in(period):
                continue
            for _, short, family in _ARCHIVES:
                blob = patterns.get(f"pattern_{period}_{family}")
                if not isinstance(blob, dict) or not blob.get("match_count"):
                    continue
                values = [(code, float(blob.get(field) or 0.0)) for field, code in spec.fields]
                if all(v == 0 for _, v in values):
                    continue
                best_code, best_pct = values[0]
                for code, pct in values[1:]:
                    if pct > best_pct:
                        best_code, best_pct = code, pct
                rows.append({
                    **common, "source": "market_summary", "rule_version": MARKET_SUMMARY_RULE_VERSION,
                    "period": period, "market": key, "selection": best_code, "archive": short,
                    "prob_shown_bp": round(best_pct * 100), "sample_n": blob["match_count"],
                })
    return rows


def ledger_rows_v4(patterns: dict, prior: dict[str, float], goal_prior: dict[str, float],
                   common: dict) -> list[dict]:
    rows: list[dict] = []
    decision = decide_result(patterns, prior)
    if decision and not decision.get("abstain_reason"):
        pick = decision["selection"]
        prior_pick = max(OUTCOMES, key=lambda o: prior[o])
        rows.append({
            **common, "source": "top_pick", "rule_version": V4_RULE_VERSION, "period": "ft",
            "market": "result", "selection": pick,
            "prob_shown_bp": round(decision["posterior"][pick] * 10000),
            "prob_raw_bp": round(_raw_frequency(decision["archives"], pick) * 100),
            "baseline_selection": prior_pick, "baseline_prob_bp": round(prior[prior_pick] * 10000),
            "confidence_tier": decision["tier"], "sample_n": int(round(decision["pooled_n"])),
            "agreement": len(decision["agreeing"]),
            "agreement_set": "+".join(n.replace("archive_", "a") for n in decision["agreeing"]) or None,
            "details": {"posterior": decision["posterior"], "prior": prior, "edge": decision["edge"],
                        "params": rule_params_fingerprint()},
        })
    archives = _eligible_archives(patterns)
    if len(archives) >= 1:
        for market, field, yes, no, prior_key in (("ou_25", "ust_25_pct", "over", "under", "over25"),
                                                  ("kg", "kg_var_pct", "yes", "no", "btts")):
            p_yes, total = _pooled_binary(archives, field, goal_prior[prior_key])
            pick, prob = (yes, p_yes) if p_yes >= 0.5 else (no, 1 - p_yes)
            base_yes = goal_prior[prior_key]
            rows.append({
                **common, "source": "top_pick", "rule_version": V4_RULE_VERSION, "period": "ft",
                "market": market, "selection": pick, "prob_shown_bp": round(prob * 10000),
                "baseline_selection": yes if base_yes >= 0.5 else no,
                "baseline_prob_bp": round(max(base_yes, 1 - base_yes) * 10000),
                "sample_n": int(round(total)) or None, "informational": True,
                "details": {"p_yes": p_yes, "prior_yes": base_yes},
            })
    rows.extend(_market_summary_rows(patterns, common))
    return rows


# Karar en erken başlamadan 48 saat önce dondurulur. İlk kayıt kazandığı için daha erken bir sayfa
# ziyareti (ör. Mayıs maçına Ekim'de) maç günü güncel takım gücüyle karar verilmesini engelliyordu.
CAPTURE_HORIZON = timedelta(hours=48)


def _eligible(analyzed_at: datetime, captured_at: datetime, kickoff_time: datetime | None,
              league_name: str | None, league_code: str | None, patterns: dict | None) -> bool:
    return not (
        kickoff_time is None or analyzed_at.tzinfo is None or captured_at.tzinfo is None
        or kickoff_time.tzinfo is None or analyzed_at > captured_at or captured_at >= kickoff_time
        or kickoff_time - captured_at > CAPTURE_HORIZON
        or not is_supported_league(league_name, league_code) or not isinstance(patterns, dict)
        or not any(isinstance(patterns.get(f"pattern_ft_{f}"), dict) for f in "bcd")
    )


def started_evidence(*, actual_ft_home: int | None, ht_observed: bool, cache_rows: list[tuple[datetime, list]],
                     match_id: str, captured_at: datetime) -> str | None:
    """Maç zaten başlamış mı? DB'deki başlama saatinden BAĞIMSIZ kanıtlar (o saat yer tutucu olabilir).

    Döner: neden kodu (kayıt yapılmaz) veya None. `cache_rows` = (cached_at, matches_json) — bültenin
    en son çekilen ve listeden düşmemiş (carried olmayan) kaydı esas alınır.
    """
    if actual_ft_home is not None:
        return "result_known"
    if ht_observed:
        return "ht_observed"
    latest = None
    for cached_at, items in sorted(cache_rows, key=lambda r: r[0]):
        for item in items or []:
            if isinstance(item, dict) and str(item.get("match_id")) == match_id and not item.get("carried"):
                latest = item
    if latest is None:
        return None
    if latest.get("score_status") in ("live", "finished"):
        return "source_started"
    try:
        kickoff = datetime.fromisoformat(latest["kickoff_time"]) if latest.get("kickoff_time") else None
    except (TypeError, ValueError):
        kickoff = None
    if kickoff is not None and kickoff.tzinfo is not None and kickoff <= captured_at:
        return "source_kickoff_passed"
    return None


async def match_already_started(session: AsyncSession, match_id: str, captured_at: datetime) -> str | None:
    from sqlalchemy import exists, text

    from app.db.models import MatchHtObservation

    actual = (await session.execute(select(Match.actual_ft_home).where(Match.match_id == match_id))).scalar()
    ht_observed = bool((await session.execute(
        select(exists().where(MatchHtObservation.match_id == match_id))
    )).scalar())
    cache_rows = (await session.execute(
        text("SELECT cached_at, matches_json FROM fixture_cache WHERE matches_json @> CAST(:probe AS jsonb)"),
        {"probe": json.dumps([{"match_id": match_id}])},
    )).all()
    return started_evidence(actual_ft_home=actual, ht_observed=ht_observed,
                            cache_rows=[(r[0], r[1]) for r in cache_rows],
                            match_id=match_id, captured_at=captured_at)


async def capture_v4_recommendations(
    session: AsyncSession, *, match_id: str, analyzed_at: datetime, captured_at: datetime,
    kickoff_time: datetime | None, league_name: str | None, league_code: str | None,
    patterns: dict | None, pattern_hash: str | None = None,
) -> tuple[list[dict] | None, bool]:
    """Maç öncesi kararı bir kez dondurur: ekran listesi + tahmin defteri (aynı transaction).

    `pattern_hash`: kullanılan pattern'lerin parmak izi (verilmezse güncel ayar — taze hesaplanmış varsayılır).
    """
    if not _eligible(analyzed_at, captured_at, kickoff_time, league_name, league_code, patterns):
        return None, False
    reason = await match_already_started(session, match_id, captured_at)
    if reason is not None:
        # DB saati yer tutucu kalmışken oynanmış maça "maç öncesi" tahmin yazılmasın (3026756 vakası).
        log.warning("Maç öncesi kayıt atlandı [%s]: maç başlamış görünüyor (%s)", match_id, reason)
        return None, False
    league = canonical_league_name(league_name or league_code or "")
    table = await get_cond_table()
    prior = table.league_prior(league)
    phash = pattern_hash or hash_string(pattern_hashes())
    # Hangi arşiv ayarıyla donduruldu → sayfadaki güncel yüzdelerle farklıysa kullanıcıya söylenir.
    picks = [{**pick, "pattern_hash": phash} for pick in build_v4_recommendations(patterns, prior)]

    written = await session.execute(
        insert(AnalysisSnapshot).values(
            match_id=match_id, rule_version=V4_RULE_VERSION, captured_at=captured_at,
            analyzed_at=analyzed_at, kickoff_time=kickoff_time, league_name=league or "unknown",
            picks=picks,
        ).on_conflict_do_nothing(index_elements=["match_id", "rule_version"])
    )
    if written.rowcount != 1:
        snapshot = await session.get(AnalysisSnapshot, (match_id, V4_RULE_VERSION))
        return (snapshot.picks if snapshot and isinstance(snapshot.picks, list) else []), False

    common = {
        "match_id": match_id, "league_name": league, "kickoff_time": kickoff_time,
        "as_of": captured_at, "pattern_hash": phash,
    }
    await record_predictions(session, ledger_rows_v4(patterns, prior, table.league_goal_prior(league), common))
    return picks, True


async def capture_prepared_recommendations(target_date: date) -> int:
    """Hazır maçların pattern'lerini güncel ayarla hesaplayıp yazar, sonra v4 kararını dondurur.

    Pattern'ler DB'ye de yazılır → ekrandaki Ana Pazar ile dondurulan seçim aynı veriden gelir.
    """
    from app.analysis.persist import compute_all_patterns, update_match_patterns
    from app.db.connection import get_session

    day_start = datetime.combine(target_date, datetime.min.time(), ISTANBUL_TZ)
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
            league_name=match.league_name,
        )
        try:
            await update_match_patterns(match.match_id, patterns, expected_analyzed_at=match.analyzed_at,
                                        computed_as_of=match.analyzed_at)
        except Exception:
            continue
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
            from app.analysis.prematch_v5 import capture_recommendations

            picks, created = await capture_recommendations(
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
