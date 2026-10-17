"""Tahmin defteri yardımcıları — kayıt ekleme ve tuttu/tutmadı çözümü.

Defter (`prediction_ledger`) değişmezdir: aynı karar ikinci kez yazılırsa
`ON CONFLICT DO NOTHING` ile sessizce atlanır (ilk kayıt kazanır).
Sonuçlar `prediction_resolutions`'a eklenir; skor düzeltilirse yeni satır gelir.
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from app.analysis.market_resolver import RESOLVER_VERSION, resolve
from app.db.connection import get_session
from app.db.models import PredictionLedger, PredictionResolution

log = logging.getLogger(__name__)


def _uniform(rows: list[dict]) -> list[dict]:
    """Çok satırlı INSERT ilk satırın anahtarlarını kullanır; eksik anahtarlar None ile doldurulur."""
    keys = {key for row in rows for key in row}
    return [{key: row.get(key) for key in keys} for row in rows]


async def record_predictions(session, rows: list[dict]) -> int:
    """Defter satırlarını ekler; zaten varsa atlar. Eklenen satır sayısını döner."""
    if not rows:
        return 0
    stmt = insert(PredictionLedger).values(_uniform(rows)).on_conflict_do_nothing(
        constraint="uq_prediction_ledger_decision",
    )
    result = await session.execute(stmt)
    return result.rowcount or 0


# Çözümü olmayan veya skoru/çözücü sürümü değişmiş defter satırları.
_PENDING_SQL = text("""
    SELECT l.id, l.period, l.market, l.selection, m.deleted_at,
           m.actual_ht_home, m.actual_ht_away, m.actual_ft_home, m.actual_ft_away
    FROM prediction_ledger l
    JOIN matches m ON m.match_id = l.match_id
    LEFT JOIN LATERAL (
        SELECT pr.outcome, pr.resolver_version, pr.ft_home, pr.ft_away, pr.ht_home, pr.ht_away
        FROM prediction_resolutions pr
        WHERE pr.ledger_id = l.id ORDER BY pr.id DESC LIMIT 1
    ) r ON true
    WHERE l.id > :after
      AND (m.actual_ft_home IS NOT NULL OR m.deleted_at IS NOT NULL)
      AND (
        r.outcome IS NULL
        OR r.resolver_version <> :rv
        OR (m.deleted_at IS NOT NULL AND r.outcome <> 'void')
        OR (m.deleted_at IS NULL AND (
            r.ft_home IS DISTINCT FROM m.actual_ft_home OR r.ft_away IS DISTINCT FROM m.actual_ft_away
            OR r.ht_home IS DISTINCT FROM m.actual_ht_home OR r.ht_away IS DISTINCT FROM m.actual_ht_away
        ))
      )
    ORDER BY l.id
    LIMIT :limit
""")


def _outcome_row(row) -> dict | None:
    if row.deleted_at is not None:
        return {"ledger_id": row.id, "outcome": "void", "resolver_version": RESOLVER_VERSION,
                "ft_home": None, "ft_away": None, "ht_home": None, "ht_away": None}
    ft = (row.actual_ft_home, row.actual_ft_away) if row.actual_ft_home is not None else None
    ht = (row.actual_ht_home, row.actual_ht_away) if row.actual_ht_home is not None else None
    outcome = resolve(row.period, row.market, row.selection, ht, ft)
    if outcome is None:
        return None
    return {
        "ledger_id": row.id, "outcome": outcome, "resolver_version": RESOLVER_VERSION,
        "ft_home": ft[0], "ft_away": ft[1],
        "ht_home": ht[0] if ht else None, "ht_away": ht[1] if ht else None,
    }


async def resolve_pending(batch_size: int = 2000) -> dict[str, int]:
    """Skoru gelen defter satırlarını çözer. {'resolved', 'void', 'unresolvable'} döner."""
    stats = {"resolved": 0, "void": 0, "unresolvable": 0}
    after = 0
    while True:
        async with get_session() as session:
            pending = (await session.execute(
                _PENDING_SQL, {"rv": RESOLVER_VERSION, "limit": batch_size, "after": after},
            )).all()
            if not pending:
                log.info("Defter çözümü: %s", stats)
                return stats
            after = pending[-1].id
            rows = []
            for p in pending:
                outcome = _outcome_row(p)
                if outcome is None:
                    stats["unresolvable"] += 1
                    continue
                rows.append(outcome)
                stats["void" if outcome["outcome"] == "void" else "resolved"] += 1
            if rows:
                await session.execute(
                    insert(PredictionResolution).values(_uniform(rows)).on_conflict_do_nothing(
                        constraint="uq_prediction_resolutions_state",
                    )
                )
