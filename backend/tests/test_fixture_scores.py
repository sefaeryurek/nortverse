from datetime import date, datetime, timezone
from unittest.mock import patch

from app.scraper.fixture import _build_fixture_url
from app.scraper.fixture_scores import parse_fixture_scores


def test_only_explicit_full_time_is_a_final_score():
    html = """
    <table>
      <tr id="tr1_101"><td class="status">FT</td><td class="handpoint">2 - 1</td>
        <td>irrelevant</td><td>1-0</td><td class="toolimg"></td></tr>
      <tr id="tr1_102"><td class="status">2nd Half</td><td class="handpoint">1 - 1</td>
        <td>0-0</td><td class="toolimg"></td></tr>
      <tr id="tr1_103"><td class="status">Postp.</td><td class="handpoint">-</td></tr>
      <tr id="tr1_104"><td class="status">FT</td><td class="handpoint">42 - 0</td></tr>
      <tr id="tr1_105"><td class="status">FT</td><td class="handpoint">1 - 0</td>
        <td>2-0</td><td class="toolimg"></td></tr>
      <tr id="tr1_106"><td class="status">45+4</td><td class="handpoint">0 - 1</td></tr>
    </table>"""
    scores = parse_fixture_scores(html)
    assert (scores["101"].status, scores["101"].home, scores["101"].away) == ("finished", 2, 1)
    assert (scores["101"].ht_home, scores["101"].ht_away) == (1, 0)
    assert scores["102"].status == "live"
    assert scores["103"].status == "postponed"
    assert "104" not in scores
    assert scores["105"].ht_home is None
    assert scores["106"].minute == "45+4"


@patch("app.scraper.fixture.datetime")
def test_fixture_calendar_uses_source_timezone_after_istanbul_evening(mock_dt):
    mock_dt.now.return_value = datetime(2026, 9, 20, 1, 0, tzinfo=timezone.utc)
    mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
    assert _build_fixture_url(date(2026, 9, 19)).endswith("?f=ft1")
