"""Form ve H2H trend istatistikleri.

Pattern B/C arşiv tabanlı; trends ise spesifik takımın/H2H'ın son maçlarını özetler.
Aynı `MatchRawData` veriyi kullanır — ekstra scrape yok.

Frontend'e 3 blok döner:
- home_form: ev sahibinin son N ev maçı (lig)
- away_form: deplasmanın son N dış maçı (lig)
- h2h: iki takımın son lig karşılaşmaları (ev sahibi perspektifinden)
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.models import HistoricalMatch, MatchRawData

MIN_SAMPLE = 3  # Bu sayının altında trend gösterilmez (yetersiz veri)
MAX_SAMPLE = 10  # En fazla son N maça bakılır


class TrendBlock(BaseModel):
    """Bir takımın veya H2H'ın son N maçındaki istatistik özeti."""

    label: str
    sample_size: int
    win_pct: float
    draw_pct: float
    loss_pct: float
    kg_var_pct: float
    over_25_pct: float
    avg_goals_for: float
    avg_goals_against: float
    last_n_results: list[str] = Field(default_factory=list)  # "G", "B", "M" — son 5


class TrendsData(BaseModel):
    """3 trend bloğu — null olabilir (örnek <3 ise)."""

    home_form: Optional[TrendBlock] = None
    away_form: Optional[TrendBlock] = None
    h2h: Optional[TrendBlock] = None


def _result_letter(scored: int, conceded: int) -> str:
    """G(alibiyet) / B(erabere) / M(ağlubiyet) — perspektif takımı için."""
    if scored > conceded:
        return "G"
    if scored == conceded:
        return "B"
    return "M"


def _filter_league(matches: list[HistoricalMatch]) -> list[HistoricalMatch]:
    return [m for m in matches if m.is_league_match]


def _compute_block(
    matches: list[HistoricalMatch],
    perspective_team: str,
    label: str,
    role: str = "any",  # "home" | "away" | "any"
) -> Optional[TrendBlock]:
    """Verilen maç listesinden perspektif takımı için trend hesapla.

    `role`:
        "home" → sadece perspective_team ev sahibi olduğu maçlar
        "away" → sadece perspective_team deplasman olduğu maçlar
        "any"  → ikisi de
    """
    # Lig + rol filtresi
    league = _filter_league(matches)
    if role == "home":
        relevant = [m for m in league if m.home_team == perspective_team]
    elif role == "away":
        relevant = [m for m in league if m.away_team == perspective_team]
    else:
        relevant = [
            m for m in league if m.home_team == perspective_team or m.away_team == perspective_team
        ]

    relevant = relevant[:MAX_SAMPLE]
    n = len(relevant)
    if n < MIN_SAMPLE:
        return None

    win = draw = loss = 0
    kg = over25 = 0
    goals_for = goals_against = 0
    last_results: list[str] = []

    for m in relevant:
        if m.home_team == perspective_team:
            scored, conceded = m.home_score_ft, m.away_score_ft
        else:
            scored, conceded = m.away_score_ft, m.home_score_ft

        res = _result_letter(scored, conceded)
        last_results.append(res)
        if res == "G":
            win += 1
        elif res == "B":
            draw += 1
        else:
            loss += 1

        if m.home_score_ft > 0 and m.away_score_ft > 0:
            kg += 1
        if (m.home_score_ft + m.away_score_ft) >= 3:
            over25 += 1

        goals_for += scored
        goals_against += conceded

    def pct(x: int) -> float:
        return round(x / n * 100, 1)

    return TrendBlock(
        label=label,
        sample_size=n,
        win_pct=pct(win),
        draw_pct=pct(draw),
        loss_pct=pct(loss),
        kg_var_pct=pct(kg),
        over_25_pct=pct(over25),
        avg_goals_for=round(goals_for / n, 2),
        avg_goals_against=round(goals_against / n, 2),
        last_n_results=last_results[:5],
    )


def compute_trends(raw: MatchRawData) -> TrendsData:
    """Bir maç için 3 trend bloğu üretir. Veri yetersizse ilgili blok None döner."""
    home_form = _compute_block(
        raw.home_recent_matches,
        raw.home_team,
        label="Ev Form",
        role="home",
    )
    away_form = _compute_block(
        raw.away_recent_matches,
        raw.away_team,
        label="Dep Form",
        role="away",
    )
    h2h = _compute_block(
        raw.h2h_matches,
        raw.home_team,  # H2H'da ev sahibi perspektifinden bakıyoruz
        label="H2H (Ev Sahibi Perspektifi)",
        role="any",
    )

    return TrendsData(home_form=home_form, away_form=away_form, h2h=h2h)
