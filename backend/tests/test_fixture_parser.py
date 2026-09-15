"""Sprint 21 — Scraper fixture parse birim testleri.

_parse_fixture_html, _extract_match_info, _build_fixture_url, _is_row_hidden
fonksiyonları icin mock HTML ile test. DB baglantisi gereksiz.
"""

import sys
from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest
from bs4 import BeautifulSoup

from app.scraper.fixture import (
    _MATCH_ROW_RE,
    _ONCLICK_RE,
    _build_fixture_url,
    _build_league_map,
    _extract_match_info,
    _is_row_hidden,
    _parse_fixture_html,
)

# ---------------------------------------------------------------------------
# Test HTML sabitleri
# ---------------------------------------------------------------------------

LEAGUE_HEADER = """
<tr id="tr_36" class="Leaguestitle" sclassid="36">
  <td><span class="LGname">English Premier League</span></td>
</tr>
"""

MATCH_ROW_VISIBLE = """
<tr id="tr1_2813084" class="b2" sclassid="36" style="">
  <td onclick='soccerInPage.analysis(2813084,"Kayserispor","Karagumruk","Turkey Super Lig")'></td>
  <td class="time" data-t="2026-4-17 16:30:00">19:30</td>
</tr>
"""

MATCH_ROW_HIDDEN = """
<tr id="tr1_9999999" class="b2" sclassid="36" style="display: none;">
  <td onclick='soccerInPage.analysis(9999999,"TeamX","TeamY","Some League")'></td>
  <td class="time" data-t="2026-4-17 20:00:00">23:00</td>
</tr>
"""

MATCH_ROW_NO_ONCLICK = """
<tr id="tr1_1111111" class="b2" sclassid="36" style="">
  <td>No onclick here</td>
  <td class="time" data-t="2026-4-17 12:00:00">15:00</td>
</tr>
"""

MATCH_ROW_NO_TIME = """
<tr id="tr1_2222222" class="b2" sclassid="36" style="">
  <td onclick='soccerInPage.analysis(2222222,"Alpha","Beta","Test League")'></td>
</tr>
"""


def _full_page(*rows: str, league: str = LEAGUE_HEADER) -> str:
    return f"<html><body><table>{league}{''.join(rows)}</table></body></html>"


# ===========================================================================
# _is_row_hidden testleri
# ===========================================================================

class TestIsRowHidden:
    def _tag(self, html: str) -> "Tag":
        return BeautifulSoup(html, "lxml").find("tr")

    def test_visible_row(self):
        tr = self._tag('<tr id="tr1_1" style="">content</tr>')
        assert not _is_row_hidden(tr)

    def test_hidden_display_none(self):
        tr = self._tag('<tr id="tr1_2" style="display: none;">content</tr>')
        assert _is_row_hidden(tr)

    def test_hidden_no_space(self):
        tr = self._tag('<tr id="tr1_3" style="display:none;">content</tr>')
        assert _is_row_hidden(tr)

    def test_no_style_attr(self):
        tr = self._tag('<tr id="tr1_4">content</tr>')
        assert not _is_row_hidden(tr)

    def test_other_style(self):
        tr = self._tag('<tr id="tr1_5" style="color:red;">content</tr>')
        assert not _is_row_hidden(tr)

    def test_hidden_mixed_case(self):
        tr = self._tag('<tr id="tr1_6" style="Display:None;">content</tr>')
        assert _is_row_hidden(tr)


# ===========================================================================
# _extract_match_info testleri
# ===========================================================================

class TestExtractMatchInfo:
    def _tag(self, html: str) -> "Tag":
        return BeautifulSoup(html, "lxml").find("tr")

    def test_normal_row(self):
        tr = self._tag(MATCH_ROW_VISIBLE)
        info = _extract_match_info(tr)
        assert info is not None
        assert info["match_id"] == "2813084"
        assert info["home"] == "Kayserispor"
        assert info["away"] == "Karagumruk"
        assert info["league_name"] == "Turkey Super Lig"

    def test_kickoff_parsed_utc(self):
        tr = self._tag(MATCH_ROW_VISIBLE)
        info = _extract_match_info(tr)
        assert info["kickoff"] is not None
        assert info["kickoff"].tzinfo == timezone.utc
        assert info["kickoff"].hour == 16
        assert info["kickoff"].minute == 30

    def test_no_onclick_returns_none(self):
        tr = self._tag(MATCH_ROW_NO_ONCLICK)
        assert _extract_match_info(tr) is None

    def test_no_time_element(self):
        tr = self._tag(MATCH_ROW_NO_TIME)
        info = _extract_match_info(tr)
        assert info is not None
        assert info["match_id"] == "2222222"
        assert info["kickoff"] is None
        assert info["kickoff_text"] is None

    def test_kickoff_text_extracted(self):
        tr = self._tag(MATCH_ROW_VISIBLE)
        info = _extract_match_info(tr)
        assert info["kickoff_text"] == "19:30"

    def test_double_digit_date(self):
        html = """
        <tr id="tr1_3333333" class="b2" style="">
          <td onclick='soccerInPage.analysis(3333333,"A","B","Liga")'></td>
          <td class="time" data-t="2026-12-25 10:00:00">13:00</td>
        </tr>
        """
        tr = self._tag(html)
        info = _extract_match_info(tr)
        assert info["kickoff"].month == 12
        assert info["kickoff"].day == 25


# ===========================================================================
# _build_league_map testleri
# ===========================================================================

class TestBuildLeagueMap:
    def test_single_league(self):
        html = _full_page()
        soup = BeautifulSoup(html, "lxml")
        leagues = _build_league_map(soup)
        assert leagues.get("36") == "English Premier League"

    def test_no_leagues(self):
        html = "<html><body><table></table></body></html>"
        soup = BeautifulSoup(html, "lxml")
        leagues = _build_league_map(soup)
        assert leagues == {}

    def test_multiple_leagues(self):
        league2 = """
        <tr id="tr_78" class="Leaguestitle" sclassid="78">
          <td><span class="LGname">Italy Serie A</span></td>
        </tr>
        """
        html = _full_page(league=LEAGUE_HEADER + league2)
        soup = BeautifulSoup(html, "lxml")
        leagues = _build_league_map(soup)
        assert leagues["36"] == "English Premier League"
        assert leagues["78"] == "Italy Serie A"


# ===========================================================================
# _parse_fixture_html testleri
# ===========================================================================

class TestParseFixtureHtml:
    def test_single_match(self):
        html = _full_page(MATCH_ROW_VISIBLE)
        matches = _parse_fixture_html(html)
        assert len(matches) == 1
        assert matches[0].match_id == "2813084"
        assert matches[0].home_team == "Kayserispor"
        assert matches[0].away_team == "Karagumruk"

    def test_league_from_header(self):
        html = _full_page(MATCH_ROW_VISIBLE)
        matches = _parse_fixture_html(html)
        assert matches[0].league_code == "English Premier League"
        assert matches[0].league_name == "English Premier League"

    def test_empty_html(self):
        html = "<html><body></body></html>"
        matches = _parse_fixture_html(html)
        assert matches == []

    def test_hidden_rows_filtered_in_hot_mode(self):
        html = _full_page(MATCH_ROW_VISIBLE, MATCH_ROW_HIDDEN)
        matches = _parse_fixture_html(html, only_hot=True)
        assert len(matches) == 1
        assert matches[0].match_id == "2813084"

    def test_hidden_rows_included_in_all_mode(self):
        html = _full_page(MATCH_ROW_VISIBLE, MATCH_ROW_HIDDEN)
        matches = _parse_fixture_html(html, only_hot=False)
        assert len(matches) == 2

    def test_no_onclick_row_skipped(self):
        html = _full_page(MATCH_ROW_NO_ONCLICK)
        matches = _parse_fixture_html(html)
        assert matches == []

    def test_duplicate_match_id_deduplicated(self):
        html = _full_page(MATCH_ROW_VISIBLE, MATCH_ROW_VISIBLE)
        matches = _parse_fixture_html(html)
        assert len(matches) == 1

    def test_kickoff_time_set(self):
        html = _full_page(MATCH_ROW_VISIBLE)
        matches = _parse_fixture_html(html)
        assert matches[0].kickoff_time is not None
        assert matches[0].kickoff_time.hour == 16

    def test_no_time_match_has_none_kickoff(self):
        html = _full_page(MATCH_ROW_NO_TIME)
        matches = _parse_fixture_html(html)
        assert len(matches) == 1
        assert matches[0].kickoff_time is None


# ===========================================================================
# _build_fixture_url testleri
# ===========================================================================

class TestBuildFixtureUrl:
    @patch("app.scraper.fixture.datetime")
    def test_today_returns_base(self, mock_dt):
        mock_dt.now.return_value = datetime(2026, 9, 16, 10, 0, tzinfo=timezone(datetime.resolution))
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        url = _build_fixture_url(None)
        assert url.endswith("/football/fixture")
        assert "?" not in url

    @patch("app.scraper.fixture.datetime")
    def test_future_date(self, mock_dt):
        now_istanbul = datetime(2026, 9, 16, 10, 0)
        mock_dt.now.return_value = now_istanbul
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        url = _build_fixture_url(date(2026, 9, 18))
        assert "?f=sc2" in url

    @patch("app.scraper.fixture.datetime")
    def test_past_date(self, mock_dt):
        now_istanbul = datetime(2026, 9, 16, 10, 0)
        mock_dt.now.return_value = now_istanbul
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        url = _build_fixture_url(date(2026, 9, 14))
        assert "?f=ft2" in url


# ===========================================================================
# Regex sabitleri testleri
# ===========================================================================

class TestRegexPatterns:
    def test_match_row_re(self):
        assert _MATCH_ROW_RE.match("tr1_2813084")
        assert _MATCH_ROW_RE.match("tr1_2813084").group(1) == "2813084"
        assert not _MATCH_ROW_RE.match("tr_36")
        assert not _MATCH_ROW_RE.match("tr1_abc")

    def test_onclick_re(self):
        onclick = 'soccerInPage.analysis(2813084,"Kayserispor","Karagumruk","Turkey Super Lig")'
        m = _ONCLICK_RE.search(onclick)
        assert m is not None
        assert m.group(1) == "2813084"
        assert m.group(2) == "Kayserispor"
        assert m.group(3) == "Karagumruk"
        assert m.group(4) == "Turkey Super Lig"

    def test_onclick_re_with_spaces(self):
        onclick = 'soccerInPage.analysis( 123 , "A" , "B" , "C" )'
        m = _ONCLICK_RE.search(onclick)
        assert m is not None
        assert m.group(1) == "123"
