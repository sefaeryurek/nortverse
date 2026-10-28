"""Uzun iş kuralları (Sprint 94 D5)."""

from datetime import datetime

from app.cli import _long_jobs as lj
from app.config import ISTANBUL_TZ


def ist(y, mo, d, h, mi=0):
    return datetime(y, mo, d, h, mi, tzinfo=ISTANBUL_TZ)


def test_match_hours_weekday_and_weekend():
    # 28 Ekim 2026 Çarşamba, 31 Ekim Cumartesi
    assert not lj.in_match_hours(ist(2026, 10, 28, 18, 59))
    assert lj.in_match_hours(ist(2026, 10, 28, 19, 0))
    assert lj.in_match_hours(ist(2026, 10, 29, 0, 15))  # bir önceki akşamın maçları
    assert not lj.in_match_hours(ist(2026, 10, 29, 0, 30))
    assert not lj.in_match_hours(ist(2026, 10, 31, 12, 59))
    assert lj.in_match_hours(ist(2026, 10, 31, 13, 0))


def test_paced_delay():
    assert lj.paced_delay(6, ist(2026, 10, 28, 21, 0)) == lj.MATCH_HOURS_DELAY
    assert lj.paced_delay(6, ist(2026, 10, 28, 3, 0)) == 6
    assert lj.paced_delay(20, ist(2026, 10, 28, 21, 0)) == 20


def test_backoff_grows_and_caps():
    assert [lj.backoff_delay(n) for n in (1, 2, 3)] == [60, 120, 240]
    assert lj.backoff_delay(50) == lj.BACKOFF_MAX


def test_until_rolls_to_next_day():
    assert lj.parse_until("12:00", ist(2026, 10, 29, 1, 0)) == ist(2026, 10, 29, 12, 0)
    assert lj.parse_until("12:00", ist(2026, 10, 29, 13, 0)) == ist(2026, 10, 30, 12, 0)
    assert lj.parse_until(None) is None
    deadline = ist(2026, 10, 29, 12, 0)
    assert not lj.past_deadline(deadline, ist(2026, 10, 29, 11, 59))
    assert lj.past_deadline(deadline, ist(2026, 10, 29, 12, 0))
    assert not lj.past_deadline(None)
