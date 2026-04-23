"""SQLAlchemy ORM modelleri."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    home_team: Mapped[str] = mapped_column(String(100), nullable=False)
    away_team: Mapped[str] = mapped_column(String(100), nullable=False)
    league_code: Mapped[str | None] = mapped_column(String(50))
    league_name: Mapped[str | None] = mapped_column(String(100))
    kickoff_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    season: Mapped[str | None] = mapped_column(String(10))
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Katman A — İlk Yarı
    ht_scores_1: Mapped[dict | None] = mapped_column(JSONB)
    ht_scores_x: Mapped[dict | None] = mapped_column(JSONB)
    ht_scores_2: Mapped[dict | None] = mapped_column(JSONB)
    ht_all_ratios: Mapped[dict | None] = mapped_column(JSONB)

    # Katman A — İkinci Yarı
    h2_scores_1: Mapped[dict | None] = mapped_column(JSONB)
    h2_scores_x: Mapped[dict | None] = mapped_column(JSONB)
    h2_scores_2: Mapped[dict | None] = mapped_column(JSONB)
    h2_all_ratios: Mapped[dict | None] = mapped_column(JSONB)

    # Katman A — Maç Sonu
    ft_scores_1: Mapped[dict | None] = mapped_column(JSONB)
    ft_scores_x: Mapped[dict | None] = mapped_column(JSONB)
    ft_scores_2: Mapped[dict | None] = mapped_column(JSONB)
    ft_all_ratios: Mapped[dict | None] = mapped_column(JSONB)

    # Gerçek sonuç
    actual_ht_home: Mapped[int | None] = mapped_column(Integer)
    actual_ht_away: Mapped[int | None] = mapped_column(Integer)
    actual_h2_home: Mapped[int | None] = mapped_column(Integer)
    actual_h2_away: Mapped[int | None] = mapped_column(Integer)
    actual_ft_home: Mapped[int | None] = mapped_column(Integer)
    actual_ft_away: Mapped[int | None] = mapped_column(Integer)
    result_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<Match {self.match_id}: {self.home_team} vs {self.away_team}>"


class FixtureCache(Base):
    """Günlük bülten listesi cache tablosu.

    Playwright scrape sonucu burada saklanır. Server restart'larından etkilenmez.
    Geçmiş tarihler kalıcı, bugün/gelecek için 1 saatlik TTL uygulanır.
    """

    __tablename__ = "fixture_cache"

    date: Mapped[str] = mapped_column(String(10), primary_key=True)  # "YYYY-MM-DD"
    matches_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    cached_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
