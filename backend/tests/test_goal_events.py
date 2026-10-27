"""Gol dakikası / kırmızı kart ayrıştırıcısı (Sprint 93)."""

from app.scraper.goal_events import events_match_score, goals_total, parse_goal_events


def _row(minute: str, home_tip: str = "", away_tip: str = "", home_score: str = "", away_score: str = "") -> str:
    def tip(t: str) -> str:
        return f'<span class="icontips" txt="{t}"><img src="/x.png"/></span>' if t else ""
    return (
        '<tr align="center">'
        f'<td>{home_score}</td><td>{tip(home_tip)}</td><td><b class="score">{minute}</b></td>'
        f'<td>{tip(away_tip)}</td><td>{away_score}</td></tr>'
    )


def _page(rows: list[str]) -> str:
    return ('<div id="teamEventDiv_detail"><table id="eventsTable"><tr class="ky_tit"><th>A</th></tr>'
            '<tr class="stage-tit"><td colspan="5">FT</td></tr>' + "".join(rows) + "</table></div>"
            # Olay tablosu dışındaki "Shots"/"Goal" satırları sayılmamalı
            '<table><tr><td></td><td><span class="icontips" txt="Goal"></span></td><td><b class="score">5\'</b></td>'
            "<td></td><td></td></tr></table>")


def _score(h: int, a: int) -> str:
    return f'<span class="ky_score">{h} - {a}</span>'


def test_goals_in_time_order_with_sides_and_scores():
    html = _page([  # sayfa en son olaydan geriye listeler
        _row("90+3'", home_tip="Goal", home_score=_score(2, 1)),
        _row("55'", away_tip="Yellow Card"),
        _row("45+1'", away_tip="Penalty", away_score=_score(1, 1)),
        _row("12'", home_tip="Goal", home_score=_score(1, 0)),
    ])
    events = parse_goal_events(html)
    assert [(e["minute"], e["extra"], e["side"], e["kind"]) for e in events] == [
        (12, 0, "home", "goal"), (45, 1, "away", "penalty"), (90, 3, "home", "goal")]
    assert goals_total(events) == (2, 1)
    assert events_match_score(events, (2, 1)) and not events_match_score(events, (1, 1))


def test_own_goal_side_taken_from_running_score_and_red_cards_kept():
    html = _page([
        _row("70'", home_tip="Red Card"),
        # İkon ev tarafında ama skor deplasmanın lehine arttı → deplasman golü
        _row("30'", home_tip="Own Goal", home_score=_score(0, 1)),
        _row("20'", away_tip="Penalty missed"),
    ])
    events = parse_goal_events(html)
    assert [(e["minute"], e["side"], e["kind"]) for e in events] == [(30, "away", "own_goal"), (70, "home", "red")]
    assert goals_total(events) == (0, 1)


def test_missing_table_returns_none():
    assert parse_goal_events("<html><body>yok</body></html>") is None
    assert events_match_score(None, (1, 0)) is False
