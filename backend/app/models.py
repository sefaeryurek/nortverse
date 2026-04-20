"""Uygulamanın çekirdek veri tipleri.

Scraping, analiz ve CLI arasındaki sınırlarda bu tipler dolaşır.
Pydantic kullanıyoruz çünkü:
- Validasyon otomatik
- JSON serileştirme kolay
- IDE desteği güçlü
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Period(str, Enum):
    """Maç periyotları."""

    HT = "HT"  # İlk yarı (half time)
    H2 = "2H"  # İkinci yarı
    FT = "FT"  # Maç sonu (full time)


class MatchStatus(str, Enum):
    """Maç durumu."""

    SCHEDULED = "scheduled"
    LIVE = "live"
    FINISHED = "finished"
    POSTPONED = "postponed"
    CANCELLED = "cancelled"


class SkipReason(str, Enum):
    """Bir maçın neden atlandığını gösteren kodlar."""

    NOT_LEAGUE_MATCH = "not_league_match"
    HOME_TEAM_INSUFFICIENT = "home_team_insufficient"
    AWAY_TEAM_INSUFFICIENT = "away_team_insufficient"
    H2H_INSUFFICIENT = "h2h_insufficient"
    DATA_FETCH_FAILED = "data_fetch_failed"


class FixtureMatch(BaseModel):
    """Bültenden çekilen bir maçın minimal bilgisi.

    Detay analiz için bu ID kullanılarak match detail sayfası çekilir.
    """

    match_id: str  # Nowgoal match ID (örn: "2963207")
    home_team: str
    away_team: str
    league_code: str  # "ENG PR", "ITA D1"
    league_name: Optional[str] = None
    kickoff_time: Optional[datetime] = None


class HistoricalMatch(BaseModel):
    """Bir takımın geçmiş maçı (form maçı veya h2h maçı)."""

    opponent: str
    home_team: str  # Bu maçta ev sahibi hangisi
    away_team: str
    home_score_ht: Optional[int] = None
    away_score_ht: Optional[int] = None
    home_score_ft: int
    away_score_ft: int
    league_code: Optional[str] = None
    is_league_match: bool = True
    match_date: Optional[datetime] = None


class MatchRawData(BaseModel):
    """Bir maç için nowgoal'den çekilmiş ham veri.

    Analiz motoru bu veriyi alıp MatchAnalysisResult üretir.
    """

    match_id: str
    home_team: str
    away_team: str
    league_code: str
    league_name: Optional[str] = None
    kickoff_time: Optional[datetime] = None

    # Ligde oynadığı maç sayısı (filtreleme için)
    home_league_match_count: int = 0
    away_league_match_count: int = 0

    # Form maçları (son N maç)
    home_recent_matches: list[HistoricalMatch] = Field(default_factory=list)
    away_recent_matches: list[HistoricalMatch] = Field(default_factory=list)

    # H2H maçları
    h2h_matches: list[HistoricalMatch] = Field(default_factory=list)


class PeriodAnalysis(BaseModel):
    """Bir periyodun (HT/2H/FT) analiz sonucu."""

    period: Period

    # 3.5+ oran çıkan skorlar
    scores_1: list[str] = Field(default_factory=list)  # Ev kazandıran
    scores_x: list[str] = Field(default_factory=list)  # Beraberlik
    scores_2: list[str] = Field(default_factory=list)  # Deplasman kazandıran

    # Tüm 35 skor için ham oranlar (ARŞIV-2 için)
    # key: "1-0", "2-1", ...  value: 0.0-10.0 arası (0.5 katları)
    all_ratios: dict[str, float] = Field(default_factory=dict)

    @property
    def has_any_3_5_plus(self) -> bool:
        """Bu periyotta 3.5+ çıkan en az bir skor var mı?"""
        return bool(self.scores_1 or self.scores_x or self.scores_2)


class MatchAnalysisResult(BaseModel):
    """Bir maçın tam analiz sonucu (3 periyot)."""

    match_id: str
    home_team: str
    away_team: str
    league_code: str
    season: str  # "2025/2026"

    # Kullanılan ayarlar
    n_matches: int
    threshold: float

    # Periyot sonuçları
    ht: PeriodAnalysis
    half2: PeriodAnalysis
    ft: PeriodAnalysis

    analyzed_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def has_any_archive1_row(self) -> bool:
        """ARŞIV-1'e yazılabilir mi? (en az bir periyotta 3.5+ skor olmalı)"""
        return (
            self.ht.has_any_3_5_plus
            or self.half2.has_any_3_5_plus
            or self.ft.has_any_3_5_plus
        )


class SkippedMatch(BaseModel):
    """Filtreleme kurallarına takılan maç."""

    match_id: str
    home_team: str
    away_team: str
    league_code: str
    reason: SkipReason
    detail: Optional[str] = None
    skipped_at: datetime = Field(default_factory=datetime.utcnow)
