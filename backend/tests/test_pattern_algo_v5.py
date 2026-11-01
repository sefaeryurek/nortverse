"""Arşiv algoritması b3/c5/d5 (Sprint 94 B5 + B6)."""

import math
from datetime import datetime, timedelta, timezone

from app.analysis.market_catalog import MARKETS_BY_KEY
from app.analysis.pattern_b import candidate_filters, effective_kickoff
from app.analysis.pattern_d import _Candidate, nearest
from app.analysis.pattern_stats import FT_ONLY_FIELDS, compute_stats
from app.db.models import Match


def _row(**values):
    return Match(**(dict(actual_ft_home=2, actual_ft_away=1, actual_ht_home=1, actual_ht_away=0,
                         actual_h2_home=1, actual_h2_away=1) | values))


def test_ft_only_fields_are_none_outside_ft():
    """B5: İY/2Y periyodunda yalnız-MS alanları eskiden sahte 0.0 yazılıyordu (ör. iy_ust_05 %0)."""
    for period in ("ht", "h2"):
        stats = compute_stats([_row(), _row()], period)
        assert all(getattr(stats, f) is None for f in FT_ONLY_FIELDS), period
        assert stats.result_1_pct is not None
    ft = compute_stats([_row(), _row()], "ft")
    assert ft.iy_ust_05_pct == 100.0 and ft.ht_result_1_pct == 100.0 and ft.iy_ms_11_pct == 100.0
    assert compute_stats([_row()], "ht").model_dump()["iy_ust_05_pct"] is None   # JSON'da null


def test_ft_only_fields_match_the_market_catalog():
    """Katalogda ft_only olmayan bir pazar bu alanlardan okumamalı (İY/2Y'de None görür)."""
    for spec in MARKETS_BY_KEY.values():
        if not spec.ft_only:
            assert not {field for field, _ in spec.fields} & set(FT_ONLY_FIELDS), spec.key


def test_placeholder_kickoff_counts_as_end_of_day():
    """B6: kaynak saati açıklanmamış maç 15:59 UTC yazılıyor → aday kesiminde 23:59 UTC."""
    placeholder = datetime(2026, 10, 18, 15, 59, tzinfo=timezone.utc)
    assert effective_kickoff(placeholder) == datetime(2026, 10, 18, 23, 59, tzinfo=timezone.utc)
    real = datetime(2026, 10, 18, 19, 0, tzinfo=timezone.utc)
    assert effective_kickoff(real) == real
    istanbul = placeholder.astimezone(timezone(timedelta(hours=3)))           # saat dilimi fark etmez
    assert effective_kickoff(istanbul) == placeholder + timedelta(hours=8)


def test_candidate_sql_uses_effective_kickoff():
    sql = " ".join(str(f) for f in candidate_filters(datetime(2026, 10, 18, 22, 0, tzinfo=timezone.utc)))
    assert "to_char" in sql and "model_only" in sql


def _cand(mid: str, kickoff: datetime) -> _Candidate:
    return _Candidate(match_id=mid, log_h=math.log(1.5), log_a=math.log(1.1), league_name="L", kickoff_time=kickoff,
                      actual_ft_home=1, actual_ft_away=0, actual_ht_home=0, actual_ht_away=0,
                      actual_h2_home=1, actual_h2_away=0)


def test_a3_pool_skips_same_day_placeholder():
    target_kickoff = datetime(2026, 10, 18, 19, 0, tzinfo=timezone.utc)      # as_of − 3 saat = 16:00
    cutoff = target_kickoff - timedelta(hours=3)
    pool = [_cand("placeholder", datetime(2026, 10, 18, 15, 59, tzinfo=timezone.utc)),
            _cand("earlier", datetime(2026, 10, 17, 19, 0, tzinfo=timezone.utc))]
    hits = nearest(pool, (1.5, 1.1), cutoff=cutoff, exclude_match_id=None, top_k=10)
    assert [c.match_id for _, c in hits] == ["earlier"]


def test_frontend_ft_only_list_matches_backend():
    """Frontend doğrulayıcısı bu alanlarda null kabul ediyor — iki liste ayrışırsa sayfa düşer."""
    import re
    from pathlib import Path

    ts = (Path(__file__).resolve().parents[2] / "frontend" / "lib" / "pattern-fields.ts").read_text(encoding="utf-8")
    block = ts[ts.index("FT_ONLY_PATTERN_FIELDS"):]
    assert set(re.findall(r'"(\w+_pct)"', block)) == set(FT_ONLY_FIELDS)
