"""Uzun işlerin (arşiv, gol dakikası, oran backfill) canlı operasyonla yarışmaması için ortak kurallar (Sprint 94 D5).

27 Ekim 19:00'daki skor güncellemesi zaman aşımı, aynı anda süren arşiv çekimiyle çakıştı. Bu yüzden:
- maç saatlerinde (hafta içi 19:00–00:30, hafta sonu 13:00–00:30, İstanbul) uzun işler yavaşlar
- kaynak hatası işi durdurmaz: artan aralıklarla bekleyip devam eder (eskiden 5 hatada duruyordu)
- `--until HH:MM` ile iş o saatte kendiliğinden biter (gece görevi 01:00–12:00)
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

from app.config import ISTANBUL_TZ

MATCH_HOURS_DELAY = 12.0       # sn — maç saatlerinde istekler arası en az bu kadar
MATCH_HOURS_CONCURRENCY = 1    # arşiv çekiminde aynı anda maç
BACKOFF_START = 60.0           # sn — üst üste hatada bekleme 1 dk → 2 → 4 ... → 30 dk
BACKOFF_MAX = 30 * 60.0


def in_match_hours(now: datetime | None = None) -> bool:
    local = (now or datetime.now(ISTANBUL_TZ)).astimezone(ISTANBUL_TZ)
    t = local.time()
    if t < time(0, 30):
        return True  # bir önceki akşamın maçları
    start = time(13, 0) if local.weekday() >= 5 else time(19, 0)
    return t >= start


def paced_delay(base: float, now: datetime | None = None) -> float:
    return max(base, MATCH_HOURS_DELAY) if in_match_hours(now) else base


def backoff_delay(failures_in_row: int) -> float:
    """Üst üste n. hatadan sonra beklenecek süre (1. hata → 1 dk)."""
    return min(BACKOFF_MAX, BACKOFF_START * 2 ** max(0, failures_in_row - 1))


def parse_until(value: str | None, now: datetime | None = None) -> datetime | None:
    """"12:00" → bir sonraki 12:00 (İstanbul). Şu an 12:00'den önceyse bugün, sonraysa yarın."""
    if not value:
        return None
    hour, minute = (int(x) for x in value.split(":", 1))
    local = (now or datetime.now(ISTANBUL_TZ)).astimezone(ISTANBUL_TZ)
    target = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return target if target > local else target + timedelta(days=1)


def past_deadline(deadline: datetime | None, now: datetime | None = None) -> bool:
    return deadline is not None and (now or datetime.now(ISTANBUL_TZ)) >= deadline
