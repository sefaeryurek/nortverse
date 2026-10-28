"""Kaynağın maç durumu → tek harita (Sprint 94 B2).

Eskiden her kazıyıcı kendi kümesini tutuyordu: fikstür sayfası sadece "Postp." tanıyordu (AET, Pen., Abd., Canc.,
Pend. satırları atlanıyor, maç hiç bitmiyordu), pano −10/−12/−13 kodlarını sessizce atlıyordu, canlı sayfa
iptal edilen maçı "ertelendi" sayıyordu. Tanınmayan etiket ve kodlar sayılıp log'a yazılır (site biçim
değiştirirse erken haber).

Durumlar:
- finished: normal süre bitti (FT)
- finished_extra: uzatma / penaltı (AET, Pen.) — fikstür sayfasındaki skor 90. dakika skoru mu belli değil →
  sonuç olarak YAZILMAZ; detay sayfası ya da elle kontrol
- live, scheduled
- postponed: ertelendi / tarihi belirsiz (Postp., Pend., −11, −14)
- abandoned: iptal / yarıda kaldı / tatil (Abd., Canc., Int., Susp., −10, −12, −13)
"""

from __future__ import annotations

import logging
import re
from collections import Counter

log = logging.getLogger(__name__)

FINISHED = "finished"
FINISHED_EXTRA = "finished_extra"
LIVE = "live"
SCHEDULED = "scheduled"
POSTPONED = "postponed"
ABANDONED = "abandoned"
UNPLAYED = frozenset({POSTPONED, ABANDONED})

FIXTURE_LABELS: dict[str, str] = {
    "FT": FINISHED,
    "AET": FINISHED_EXTRA, "Pen.": FINISHED_EXTRA, "Pens.": FINISHED_EXTRA, "Pen": FINISHED_EXTRA,
    "Postp.": POSTPONED, "Pend.": POSTPONED, "TBD": POSTPONED,
    "Abd.": ABANDONED, "Canc.": ABANDONED, "Cancl.": ABANDONED, "Int.": ABANDONED, "Susp.": ABANDONED,
    "1st Half": LIVE, "2nd Half": LIVE, "HT": LIVE, "ET": LIVE, "Ext.": LIVE, "Pen. Shootout": LIVE,
}

# Pano (SoccerAjax type=6) alan 7: 0 başlamadı, 1/2/3 1.Y/devre/2.Y, 4/5 uzatma/penaltı, −1 bitti,
# −10 iptal, −11 belirsiz, −12 yarıda kaldı, −13 durduruldu, −14 ertelendi
BOARD_CODES: dict[int, str] = {
    0: SCHEDULED, 1: LIVE, 2: LIVE, 3: LIVE, 4: LIVE, 5: LIVE, -1: FINISHED,
    -10: ABANDONED, -11: POSTPONED, -12: ABANDONED, -13: ABANDONED, -14: POSTPONED,
}


class UnknownTally:
    """Bir sayfadaki tanınmayan etiketleri sayar; sayfa bitince tek satır uyarı yazar."""

    def __init__(self, source: str):
        self.source = source
        self.counts: Counter = Counter()

    def add(self, value) -> None:
        self.counts[str(value)] += 1

    def report(self) -> None:
        if self.counts:
            log.warning("%s: tanınmayan maç durumu %s", self.source, dict(self.counts.most_common(10)))


_KICKOFF_LABEL = re.compile(r"^\d{1,2}:\d{2}$")


def fixture_status(label: str) -> str | None:
    """Fikstür/canlı sayfası durum etiketi → durum. Boş etiket veya başlama saati ("19:00") = başlamadı;
    dakika etiketi ("67", "45+2") çağıranda canlı sayılır."""
    label = (label or "").strip()
    if not label or label == "-" or _KICKOFF_LABEL.match(label):
        return SCHEDULED
    return FIXTURE_LABELS.get(label)


def board_status(code) -> str | None:
    return BOARD_CODES.get(code) if isinstance(code, int) else None
