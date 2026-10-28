"""Ertelenen / iptal / taşınan maçlar (Sprint 94 B2): durum haritası, defter ve kupon geçersizliği."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.analysis.coupons import leg_void_reason
from app.analysis.ledger import unplayable_reason
from app.analysis.prematch_v4 import CAPTURE_HORIZON
from app.scraper import status as st
from app.scraper.fixture_scores import parse_fixture_scores

NOW = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)


def _row(source="top_pick", frozen=None, kickoff=None, recorded=None, ft=None):
    frozen = frozen or NOW - timedelta(days=1)
    return SimpleNamespace(source=source, frozen_kickoff=frozen, kickoff=kickoff or frozen,
                           recorded_at=recorded or frozen - timedelta(hours=10), actual_ft_home=ft)


def test_prematch_row_voided_when_kickoff_moved_beyond_capture_horizon():
    # Yer tutucu 18.10 12:00 ile 17.10 22:00'de yazıldı; gerçek maç 19.10 17:00 → saat 29 saat kaydı
    frozen = datetime(2026, 10, 18, 12, tzinfo=timezone.utc)
    row = _row(frozen=frozen, kickoff=datetime(2026, 10, 19, 17, tzinfo=timezone.utc),
               recorded=datetime(2026, 10, 17, 22, tzinfo=timezone.utc), ft=2)
    assert unplayable_reason(row, None, NOW, CAPTURE_HORIZON) == "rescheduled"


def test_prematch_row_written_too_early_is_voided():
    kickoff = NOW - timedelta(days=1)
    row = _row(frozen=kickoff - timedelta(hours=3), kickoff=kickoff, recorded=kickoff - timedelta(hours=50), ft=1)
    assert unplayable_reason(row, None, NOW, CAPTURE_HORIZON) == "capture_horizon"


def test_live_row_voided_when_match_replayed():
    played = NOW - timedelta(days=20)
    row = _row(source="live_ht", frozen=played, kickoff=NOW - timedelta(days=2), recorded=played + timedelta(minutes=47),
               ft=1)
    assert unplayable_reason(row, None, NOW, CAPTURE_HORIZON) == "rescheduled"


def test_small_kickoff_correction_is_not_a_reschedule():
    row = _row(frozen=NOW - timedelta(days=1), kickoff=NOW - timedelta(days=1, hours=-2), ft=1)
    assert unplayable_reason(row, None, NOW, CAPTURE_HORIZON) is None


@pytest.mark.parametrize("status,age,expected", [
    ("abandoned", timedelta(hours=5), "abandoned"),
    ("postponed", timedelta(days=1), None),          # henüz bekle (aynı hafta oynanabilir)
    ("postponed", timedelta(days=4), "postponed"),
    (None, timedelta(days=4), None),                 # durum yok: PC kapalı olabilir, 7 gün bekle
    (None, timedelta(days=8), "no_result"),
])
def test_no_result_rules(status, age, expected):
    row = _row(frozen=NOW - age, recorded=NOW - age - timedelta(hours=5))
    assert unplayable_reason(row, status, NOW, CAPTURE_HORIZON) == expected


def test_abandoned_match_voids_ledger_and_coupon_legs():
    row = _row(frozen=NOW - timedelta(hours=5))
    assert unplayable_reason(row, "abandoned", NOW, CAPTURE_HORIZON) == "abandoned"
    assert leg_void_reason(deleted=False, status="abandoned", has_score=False, kickoff=NOW - timedelta(hours=5),
                           now=NOW) == "abandoned"
    assert leg_void_reason(deleted=True, status=None, has_score=True, kickoff=NOW, now=NOW) == "deleted"
    assert leg_void_reason(deleted=False, status=None, has_score=False, kickoff=NOW - timedelta(hours=49),
                           now=NOW) == "no_result_48h"
    assert leg_void_reason(deleted=False, status=None, has_score=True, kickoff=NOW - timedelta(days=5),
                           now=NOW) is None


def _fixture_row(mid, status, score="", half=""):
    return (f'<tr id="tr1_{mid}"><td class="status">{status}</td><td class="handpoint">{score}</td>'
            f'<td>{half}</td><td class="toolimg"></td></tr>')


def test_status_map_covers_fixture_labels():
    html = "<table>" + "".join([
        _fixture_row("1", "FT", "2-1", "1-0"), _fixture_row("2", "AET", "2-1", "1-1"),
        _fixture_row("3", "Abd."), _fixture_row("4", "Canc."), _fixture_row("5", "Postp."),
        _fixture_row("6", "Pend."), _fixture_row("7", "19:00"), _fixture_row("8", "67", "0-0"),
    ]) + "</table>"
    scores = parse_fixture_scores(html)
    assert {k: v.status for k, v in scores.items()} == {
        "1": "finished", "2": "finished_extra", "3": "abandoned", "4": "abandoned",
        "5": "postponed", "6": "postponed", "8": "live",
    }


def test_aet_score_is_not_written_as_final():
    """Uzatmalı maçta kaynaktaki skor 90. dakika mı belli değil → sonuç olarak sayılmaz."""
    assert st.FINISHED_EXTRA != st.FINISHED


def test_unknown_label_is_reported(caplog):
    html = "<table>" + _fixture_row("1", "Weird") + "</table>"
    with caplog.at_level("WARNING"):
        assert parse_fixture_scores(html) == {}
    assert "Weird" in caplog.text


def test_board_codes():
    assert [st.board_status(c) for c in (-1, -10, -11, -12, -13, -14, 4, 99)] == [
        "finished", "abandoned", "postponed", "abandoned", "abandoned", "postponed", "live", None]


@pytest.mark.asyncio
async def test_postponed_carried_fixture_not_used_for_sync():
    from app.pipeline.runner import sync_kickoffs

    session = AsyncMock()
    items = [{"match_id": "1", "kickoff_time": "2026-10-30T18:00:00+00:00", "carried": True,
              "score_status": "postponed"}]
    assert await sync_kickoffs(session, items) == 0
    session.execute.assert_not_awaited()
