"""Yeni sonuç geldi mi? — süreç içi önbelleklerin (A3 havuzu, canlı COND tablosu) yenilenme sinyali.

Pipeline ve skor güncellemesi ayrı CLI süreçlerinde çalışır; API sunucusunun belleğindeki
önbellekler bundan haberdar olmaz. Bu yüzden önbellek en fazla `CHECK_INTERVAL` saniyede bir
ucuz bir sorguyla (sonuçlu maç sayısı + son sonuç zamanı) karşılaştırılır; değiştiyse yeniden kurulur.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from sqlalchemy import func, select

CHECK_INTERVAL = 300.0


MARKER_DAYS = 30


async def results_marker() -> tuple:
    """Son 30 günün sonuçlu maç sayısı + son sonuç zamanı. Eski sezon arşiv eklemeleri işareti değiştirmez
    (Sprint 94 C1: arşiv tamamlama her 5 dk'da bir COND/A3 önbelleklerini yeniden kurduruyordu)."""
    from datetime import datetime, timedelta, timezone

    from app.db.connection import get_session
    from app.db.models import Match

    since = datetime.now(timezone.utc) - timedelta(days=MARKER_DAYS)
    async with get_session() as session:
        row = (await session.execute(
            select(func.count(Match.id), func.max(Match.result_fetched_at)).where(
                Match.deleted_at.is_(None), Match.actual_ft_home.isnot(None), Match.kickoff_time >= since,
            )
        )).one()
    return (int(row[0] or 0), row[1].isoformat() if row[1] else None)


@dataclass
class ResultsWatch:
    """Önbelleğin kurulduğu andaki işaret; `stale()` en fazla CHECK_INTERVAL'de bir DB'ye bakar."""

    interval: float = CHECK_INTERVAL
    marker: tuple | None = None
    checked_at: float = field(default=0.0)

    def mark(self, marker: tuple) -> None:
        self.marker = marker
        self.checked_at = time.monotonic()

    async def stale(self) -> bool:
        if self.marker is None:
            return True
        if time.monotonic() - self.checked_at < self.interval:
            return False
        current = await results_marker()
        self.checked_at = time.monotonic()
        return current != self.marker
