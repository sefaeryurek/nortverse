"""Tahmin defteri performans özetleri — saf hesap fonksiyonları (DB'siz test edilir).

Bir satır: {outcome: 'hit'|'miss'|'void'|None, prob_shown_bp, baseline_outcome, ...grup alanları}.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from app.analysis.stats_utils import sample_stage, verdict, wilson_ci
from app.config import ISTANBUL_TZ

GROUP_FIELDS = {
    "market": lambda r: r["market"],
    "selection": lambda r: f'{r["market"]}:{r["selection"]}',
    "tier": lambda r: r.get("confidence_tier") or "none",
    "league": lambda r: r.get("league_name") or "-",
    "period": lambda r: r["period"],
    "period_market": lambda r: f'{r["period"]}:{r["market"]}',
    "archive": lambda r: r.get("archive") or "-",
    "agreement": lambda r: "-" if r.get("agreement") is None else str(r["agreement"]),
    "informational": lambda r: "info" if r.get("informational") else "main",
    "risk": lambda r: "risky" if r.get("confidence_tier") == "insufficient" else "normal",
    "week": lambda r: _iso_week(r["kickoff_time"]),
    "day": lambda r: r["kickoff_time"].astimezone(ISTANBUL_TZ).date().isoformat(),
}


def _iso_week(kickoff: datetime) -> str:
    year, week, _ = kickoff.astimezone(ISTANBUL_TZ).isocalendar()
    return f"{year}-W{week:02d}"


def decision_key(row: dict) -> tuple:
    """Bir kararın kimliği: aynı maçta aynı periyot/pazar/seçim → aynı karar (hangi arşivden gelirse gelsin)."""
    return (row.get("match_id"), row.get("rule_version"), row["period"], row["market"], row["selection"])


def dedupe_decisions(rows: list[dict]) -> list[dict]:
    """Tekil sayım: A1/A2/A3/Genel aynı seçimi işaret ettiyse tek karar sayılır.

    Temsilci satır en büyük örneklemli kaynaktır (eşitse yüksek olasılık) — "riskli" etiketi de
    ondan gelir, yani kaynaklardan biri bile normal örneklemliyse karar normaldir.
    `sources` alanı kararı destekleyen arşivleri listeler. match_id yoksa satırlar olduğu gibi döner.
    """
    if not rows or rows[0].get("match_id") is None:
        return rows
    best: dict[tuple, dict] = {}
    sources: dict[tuple, list[str]] = defaultdict(list)
    for row in rows:
        key = decision_key(row)
        sources[key].append(row.get("archive") or "genel")
        current = best.get(key)
        rank = ((row.get("sample_n") or 0), row["prob_shown_bp"])
        if current is None or rank > ((current.get("sample_n") or 0), current["prob_shown_bp"]):
            best[key] = row
    return [{**row, "sources": sources[key]} for key, row in best.items()]


def summarize(rows: list[dict]) -> dict:
    """Tek grup için isabet, güven aralığı, kalibrasyon, Brier ve tabana göre fark."""
    resolved = [r for r in rows if r.get("outcome") in ("hit", "miss")]
    hits = sum(r["outcome"] == "hit" for r in resolved)
    n = len(resolved)
    hit_rate = hits / n if n else None
    ci = wilson_ci(hits, n)
    probs = [r["prob_shown_bp"] / 10000 for r in resolved]
    avg_prob = sum(probs) / n if n else None
    brier = (sum((p - (r["outcome"] == "hit")) ** 2 for p, r in zip(probs, resolved)) / n) if n else None
    with_base = [r for r in resolved if r.get("baseline_outcome") in ("hit", "miss")]
    base_hits = sum(r["baseline_outcome"] == "hit" for r in with_base)
    base_rate = base_hits / len(with_base) if with_base else None
    model_on_base = sum(r["outcome"] == "hit" for r in with_base)

    def pct(value: float | None) -> float | None:
        return None if value is None else round(value * 100, 1)

    return {
        "total": len(rows),
        "resolved": n,
        "pending": sum(r.get("outcome") is None for r in rows),
        "void": sum(r.get("outcome") == "void" for r in rows),
        "hits": hits,
        "hit_pct": pct(hit_rate),
        "ci_low": pct(ci[0]) if ci else None,
        "ci_high": pct(ci[1]) if ci else None,
        "avg_prob_pct": pct(avg_prob),
        "calibration_gap": None if avg_prob is None else round((avg_prob - hit_rate) * 100, 1),
        "brier": None if brier is None else round(brier, 4),
        "baseline_resolved": len(with_base),
        "baseline_hit_pct": pct(base_rate),
        "lift_pct": None if base_rate is None else round((model_on_base - base_hits) / len(with_base) * 100, 1),
        "stage": sample_stage(n),
        "verdict": verdict(hits, n, avg_prob),
        "expected_hits": None if not n else round(sum(probs), 1),
    }


def group_summaries(rows: list[dict], by: str) -> list[dict]:
    key_of = GROUP_FIELDS[by]
    buckets: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        buckets[key_of(row)].append(row)
    out = [{"key": key, **summarize(items)} for key, items in buckets.items()]
    if by in ("week", "day"):
        return sorted(out, key=lambda g: g["key"])
    return sorted(out, key=lambda g: (-g["resolved"], g["key"]))


def calibration_buckets(rows: list[dict], width: int = 10) -> list[dict]:
    """Gösterilen olasılığı %width'lik kovalara ayırır: ortalama tahmin vs gözlenen isabet."""
    buckets: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        if row.get("outcome") not in ("hit", "miss"):
            continue
        pct = row["prob_shown_bp"] / 100
        buckets[min(int(pct // width) * width, 100 - width)].append(row)
    out = []
    for lower in sorted(buckets):
        items = buckets[lower]
        hits = sum(r["outcome"] == "hit" for r in items)
        out.append({
            "lower": lower, "upper": lower + width, "n": len(items),
            "avg_prob_pct": round(sum(r["prob_shown_bp"] for r in items) / len(items) / 100, 1),
            "hit_pct": round(hits / len(items) * 100, 1),
        })
    return out
