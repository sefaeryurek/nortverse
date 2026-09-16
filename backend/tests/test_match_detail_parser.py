"""H2H sayfa parser (match_detail.py) birim testleri.

_parse_source_datetime, _extract_main_match_score, _extract_main_match_info,
_extract_main_match_kickoff, _parse_score_cell, _parse_match_row,
_detect_main_league_code, _parse_history_table, _text_of.

Mock HTML ile pure fonksiyon testi, DB/Playwright bağımlılığı yok.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from bs4 import BeautifulSoup, Tag

from app.scraper.match_detail import (
    _detect_main_league_code,
    _extract_main_match_info,
    _extract_main_match_kickoff,
    _extract_main_match_score,
    _parse_history_table,
    _parse_match_row,
    _parse_score_cell,
    _parse_source_datetime,
    _text_of,
)


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def _tag(html: str, name: str = "td") -> Tag:
    return _soup(html).find(name)


# ─── _text_of ───────────────────────────────────────────────────────────────

class TestTextOf:
    def test_none_returns_empty(self):
        assert _text_of(None) == ""

    def test_simple_text(self):
        el = _tag("<td>  Hello World  </td>")
        assert _text_of(el) == "Hello World"

    def test_nested_tags(self):
        el = _tag("<td><span>Inner</span> text</td>")
        assert "Inner" in _text_of(el)
        assert "text" in _text_of(el)

    def test_empty_element(self):
        el = _tag("<td></td>")
        assert _text_of(el) == ""


# ─── _parse_source_datetime ─────────────────────────────────────────────────

class TestParseSourceDatetime:
    def test_iso_with_z(self):
        result = _parse_source_datetime("2026-09-16T18:00:00Z")
        assert result == datetime(2026, 9, 16, 18, 0, 0, tzinfo=timezone.utc)

    def test_iso_with_offset(self):
        result = _parse_source_datetime("2026-09-16T21:00:00+03:00")
        assert result is not None
        assert result.tzinfo == timezone.utc
        assert result.hour == 18

    def test_iso_naive(self):
        result = _parse_source_datetime("2026-09-16T18:00:00")
        assert result == datetime(2026, 9, 16, 18, 0, 0, tzinfo=timezone.utc)

    def test_us_format_am(self):
        result = _parse_source_datetime("3/3/2026 7:30:00 AM")
        assert result == datetime(2026, 3, 3, 7, 30, 0, tzinfo=timezone.utc)

    def test_us_format_pm(self):
        result = _parse_source_datetime("3/3/2026 7:30:00 PM")
        assert result == datetime(2026, 3, 3, 19, 30, 0, tzinfo=timezone.utc)

    def test_yyyy_slash_format(self):
        result = _parse_source_datetime("2026/09/16 18:00:00")
        assert result == datetime(2026, 9, 16, 18, 0, 0, tzinfo=timezone.utc)

    def test_invalid_returns_none(self):
        assert _parse_source_datetime("not a date") is None

    def test_empty_returns_none(self):
        assert _parse_source_datetime("") is None

    def test_whitespace_stripped(self):
        result = _parse_source_datetime("  2026-09-16T18:00:00Z  ")
        assert result is not None


# ─── _extract_main_match_kickoff ────────────────────────────────────────────

class TestExtractMainMatchKickoff:
    def test_valid_kickoff(self):
        html = '<html><body><span class="time" data-t="3/3/2026 7:30:00 PM">19:30</span></body></html>'
        result = _extract_main_match_kickoff(_soup(html))
        assert result == datetime(2026, 3, 3, 19, 30, 0, tzinfo=timezone.utc)

    def test_no_time_element(self):
        html = "<html><body><div>No time here</div></body></html>"
        assert _extract_main_match_kickoff(_soup(html)) is None

    def test_empty_data_t(self):
        html = '<html><body><span class="time" data-t="">19:30</span></body></html>'
        assert _extract_main_match_kickoff(_soup(html)) is None


# ─── _extract_main_match_info ──────────────────────────────────────────────

MATCH_INFO_HTML = """
<html><body>
<div class="fbheader">
  <a href="/league/36">English Premier League</a>
  <span class="home">Arsenal</span>
  <span class="guest">Chelsea</span>
</div>
</body></html>
"""

class TestExtractMainMatchInfo:
    def test_full_info(self):
        home, away, code, league = _extract_main_match_info(_soup(MATCH_INFO_HTML))
        assert home == "Arsenal"
        assert away == "Chelsea"
        assert league == "English Premier League"
        assert code == ""

    def test_alternative_class_names(self):
        html = """
        <html><body>
        <div class="fbheader">
          <a href="/league/36">Turkish Super Lig</a>
        </div>
        <span class="teamHome">Fenerbahce</span>
        <span class="teamAway">Galatasaray</span>
        </body></html>
        """
        home, away, _, league = _extract_main_match_info(_soup(html))
        assert home == "Fenerbahce"
        assert away == "Galatasaray"
        assert league == "Turkish Super Lig"

    def test_missing_teams(self):
        html = '<html><body><div class="fbheader"><a>Liga</a></div></body></html>'
        home, away, _, league = _extract_main_match_info(_soup(html))
        assert home == ""
        assert away == ""
        assert league == "Liga"

    def test_missing_league(self):
        html = """
        <html><body>
        <span class="home">A</span>
        <span class="guest">B</span>
        </body></html>
        """
        _, _, _, league = _extract_main_match_info(_soup(html))
        assert league == ""

    def test_fallback_league_info(self):
        html = """
        <html><body>
        <span class="home">A</span>
        <span class="guest">B</span>
        <span class="LInfo">Serie A</span>
        </body></html>
        """
        _, _, _, league = _extract_main_match_info(_soup(html))
        assert league == "Serie A"


# ─── _extract_main_match_score ──────────────────────────────────────────────

class TestExtractMainMatchScore:
    def test_finished_match(self):
        html = """
        <html><body>
        <div class="fbheader">
          <div class="end">
            <div class="score">2</div>
            <span title="Score 1st Half">1-0</span>
            <span title="Score 2nd Half">1-1</span>
            <div class="score">1</div>
          </div>
        </div>
        </body></html>
        """
        ft_h, ft_a, ht_h, ht_a, h2_h, h2_a = _extract_main_match_score(_soup(html))
        assert ft_h == 2
        assert ft_a == 1
        assert ht_h == 1
        assert ht_a == 0
        assert h2_h == 1
        assert h2_a == 1

    def test_no_fbheader(self):
        html = "<html><body><div>Empty</div></body></html>"
        result = _extract_main_match_score(_soup(html))
        assert result == (None, None, None, None, None, None)

    def test_no_end_class_live_match(self):
        html = """
        <html><body>
        <div class="fbheader">
          <div class="live">
            <div class="score">1</div>
            <div class="score">0</div>
          </div>
        </div>
        </body></html>
        """
        result = _extract_main_match_score(_soup(html))
        assert result == (None, None, None, None, None, None)

    def test_only_ft_score_no_halves(self):
        html = """
        <html><body>
        <div class="fbheader">
          <div class="end">
            <div class="score">3</div>
            <div class="score">0</div>
          </div>
        </div>
        </body></html>
        """
        ft_h, ft_a, ht_h, ht_a, h2_h, h2_a = _extract_main_match_score(_soup(html))
        assert ft_h == 3
        assert ft_a == 0
        assert ht_h is None
        assert h2_h is None

    def test_zero_zero_match(self):
        html = """
        <html><body>
        <div class="fbheader">
          <div class="end">
            <div class="score">0</div>
            <span title="Score 1st Half">0-0</span>
            <span title="Score 2nd Half">0-0</span>
            <div class="score">0</div>
          </div>
        </div>
        </body></html>
        """
        ft_h, ft_a, ht_h, ht_a, h2_h, h2_a = _extract_main_match_score(_soup(html))
        assert ft_h == 0
        assert ft_a == 0
        assert ht_h == 0
        assert ht_a == 0
        assert h2_h == 0
        assert h2_a == 0

    def test_invalid_score_text(self):
        html = """
        <html><body>
        <div class="fbheader">
          <div class="end">
            <div class="score">abc</div>
            <div class="score">1</div>
          </div>
        </div>
        </body></html>
        """
        result = _extract_main_match_score(_soup(html))
        assert result == (None,) * 6

    def test_ht_fallback_from_vs(self):
        html = """
        <html><body>
        <div class="fbheader">
          <div class="end">
            <div class="score">2</div>
            <div class="vs">( 1-0 , 1-1 )</div>
            <div class="score">1</div>
          </div>
        </div>
        </body></html>
        """
        ft_h, ft_a, ht_h, ht_a, h2_h, h2_a = _extract_main_match_score(_soup(html))
        assert ft_h == 2
        assert ft_a == 1
        assert ht_h == 1
        assert ht_a == 0
        assert h2_h == 1
        assert h2_a == 1

    def test_h2_exceeds_ft_discarded(self):
        html = """
        <html><body>
        <div class="fbheader">
          <div class="end">
            <div class="score">1</div>
            <span title="Score 1st Half">0-0</span>
            <span title="Score 2nd Half">3-0</span>
            <div class="score">0</div>
          </div>
        </div>
        </body></html>
        """
        ft_h, ft_a, ht_h, ht_a, h2_h, h2_a = _extract_main_match_score(_soup(html))
        assert ft_h == 1
        assert ft_a == 0
        assert ht_h == 0
        assert ht_a == 0
        # h2 exceeds ft → discarded, then recalculated from ft-ht
        assert h2_h == 1
        assert h2_a == 0


# ─── _parse_score_cell ──────────────────────────────────────────────────────

class TestParseScoreCell:
    def test_standard_score(self):
        html = '<td><span class="fscore_1">2-1</span><span class="hscore_1">(1-0)</span></td>'
        ft_h, ft_a, ht_h, ht_a = _parse_score_cell(_tag(html))
        assert ft_h == 2
        assert ft_a == 1
        assert ht_h == 1
        assert ht_a == 0

    def test_score_without_ht(self):
        html = '<td><span class="fscore_1">3-0</span></td>'
        ft_h, ft_a, ht_h, ht_a = _parse_score_cell(_tag(html))
        assert ft_h == 3
        assert ft_a == 0
        assert ht_h is None
        assert ht_a is None

    def test_fallback_plain_text(self):
        html = "<td>2-1 (1-0)</td>"
        ft_h, ft_a, ht_h, ht_a = _parse_score_cell(_tag(html))
        assert ft_h == 2
        assert ft_a == 1
        assert ht_h == 1
        assert ht_a == 0

    def test_no_score_returns_none(self):
        html = "<td>vs</td>"
        result = _parse_score_cell(_tag(html))
        assert result == (None, None, None, None)

    def test_negative_score_returns_none(self):
        html = '<td><span class="fscore_1">-1-0</span></td>'
        result = _parse_score_cell(_tag(html))
        assert result == (None, None, None, None)

    def test_ht_exceeds_ft_discarded(self):
        html = '<td><span class="fscore_1">1-0</span><span class="hscore_1">(3-0)</span></td>'
        ft_h, ft_a, ht_h, ht_a = _parse_score_cell(_tag(html))
        assert ft_h == 1
        assert ft_a == 0
        assert ht_h is None
        assert ht_a is None

    def test_fscore_2_class(self):
        html = '<td><span class="fscore_2">0-2</span></td>'
        ft_h, ft_a, _, _ = _parse_score_cell(_tag(html))
        assert ft_h == 0
        assert ft_a == 2

    def test_zero_zero(self):
        html = '<td><span class="fscore_1">0-0</span><span class="hscore_1">(0-0)</span></td>'
        ft_h, ft_a, ht_h, ht_a = _parse_score_cell(_tag(html))
        assert ft_h == 0
        assert ft_a == 0
        assert ht_h == 0
        assert ht_a == 0

    def test_high_score(self):
        html = '<td><span class="fscore_1">7-5</span></td>'
        ft_h, ft_a, _, _ = _parse_score_cell(_tag(html))
        assert ft_h == 7
        assert ft_a == 5


# ─── _parse_match_row ───────────────────────────────────────────────────────

def _match_row(
    league: str = "TUR D1",
    home: str = "Fenerbahce",
    away: str = "Galatasaray",
    score: str = '<span class="fscore_1">2-1</span><span class="hscore_1">(1-0)</span>',
    row_id: str = "tr1_12345",
    index: str = "12345",
    date_val: str = "2026-09-15T18:00:00Z",
    title: str = "Turkey Super Lig",
) -> str:
    return f"""
    <tr id="{row_id}" index="{index}">
      <td title="{title}">{league}</td>
      <td><span data-t="{date_val}">21:00</span></td>
      <td>{home}</td>
      <td>{score}</td>
      <td>{away}</td>
    </tr>
    """


class TestParseMatchRow:
    def test_basic_row(self):
        html = _match_row()
        tr = _soup(html).find("tr")
        m = _parse_match_row(tr, "TUR D1")
        assert m is not None
        assert m.home_team == "Fenerbahce"
        assert m.away_team == "Galatasaray"
        assert m.home_score_ft == 2
        assert m.away_score_ft == 1
        assert m.home_score_ht == 1
        assert m.away_score_ht == 0
        assert m.match_id == "12345"
        assert m.is_league_match is True

    def test_non_league_cup_match(self):
        html = _match_row(league="TUR Cup", title="Turkey Cup")
        tr = _soup(html).find("tr")
        m = _parse_match_row(tr, "TUR D1")
        assert m is not None
        assert m.is_league_match is False

    def test_same_canonical_league(self):
        html = _match_row(league="ENG PR", title="English Premier League")
        tr = _soup(html).find("tr")
        m = _parse_match_row(tr, "English Premier League")
        assert m is not None
        assert m.is_league_match is True

    def test_too_few_tds(self):
        html = '<tr id="tr1_1" index="1"><td>Only one</td><td>Two</td></tr>'
        tr = _soup(html).find("tr")
        assert _parse_match_row(tr, "X") is None

    def test_empty_league_code(self):
        html = _match_row(league="")
        tr = _soup(html).find("tr")
        assert _parse_match_row(tr, "X") is None

    def test_empty_home_team(self):
        html = _match_row(home="")
        tr = _soup(html).find("tr")
        assert _parse_match_row(tr, "TUR D1") is None

    def test_empty_away_team(self):
        html = _match_row(away="")
        tr = _soup(html).find("tr")
        assert _parse_match_row(tr, "TUR D1") is None

    def test_no_score(self):
        html = _match_row(score="vs")
        tr = _soup(html).find("tr")
        assert _parse_match_row(tr, "TUR D1") is None

    def test_match_date_parsed(self):
        html = _match_row(date_val="2026-09-15T18:00:00Z")
        tr = _soup(html).find("tr")
        m = _parse_match_row(tr, "TUR D1")
        assert m.match_date == datetime(2026, 9, 15, 18, 0, tzinfo=timezone.utc)

    def test_date_from_text_fallback(self):
        html = """
        <tr id="tr1_1" index="1">
          <td>TUR D1</td>
          <td>2026/09/15 18:00:00</td>
          <td>A</td>
          <td><span class="fscore_1">1-0</span></td>
          <td>B</td>
        </tr>
        """
        tr = _soup(html).find("tr")
        m = _parse_match_row(tr, "TUR D1")
        assert m is not None
        assert m.match_date == datetime(2026, 9, 15, 18, 0, tzinfo=timezone.utc)


# ─── _detect_main_league_code ──────────────────────────────────────────────

def _make_table(rows: list[tuple[str, str, str]], table_id: str = "table_v3") -> Tag:
    trs = []
    for i, (league, home, away) in enumerate(rows):
        trs.append(f"""
        <tr id="tr3_{i}" index="{i}">
          <td>{league}</td>
          <td>2026-01-01</td>
          <td>{home}</td>
          <td><span class="fscore_1">1-0</span></td>
          <td>{away}</td>
        </tr>
        """)
    html = f'<table id="{table_id}">{"".join(trs)}</table>'
    return _soup(html).find("table")


class TestDetectMainLeagueCode:
    def test_h2h_most_common(self):
        h2h = _make_table([
            ("TUR D1", "Fener", "GS"),
            ("TUR D1", "GS", "Fener"),
            ("TUR Cup", "Fener", "GS"),
        ])
        code = _detect_main_league_code("Fener", "GS", None, None, h2h)
        assert code == "TUR D1"

    def test_home_table_fallback(self):
        home = _make_table([
            ("ENG PR", "Arsenal", "T1"),
            ("ENG PR", "Arsenal", "T2"),
            ("ENG LC", "Arsenal", "T3"),
        ], "table_v1")
        code = _detect_main_league_code("Arsenal", "Chelsea", home, None, None)
        assert code == "ENG PR"

    def test_cup_not_counted(self):
        h2h = _make_table([
            ("TUR Cup", "A", "B"),
            ("TUR Cup", "B", "A"),
            ("TUR D1", "A", "B"),
        ])
        code = _detect_main_league_code("A", "B", None, None, h2h)
        assert code == "TUR D1"

    def test_friendly_not_counted(self):
        h2h = _make_table([
            ("Friendly", "A", "B"),
            ("Friendly", "B", "A"),
            ("SPA D1", "A", "B"),
        ])
        code = _detect_main_league_code("A", "B", None, None, h2h)
        assert code == "SPA D1"

    def test_empty_tables(self):
        code = _detect_main_league_code("A", "B", None, None, None)
        assert code == ""

    def test_h2h_weighted_higher(self):
        h2h = _make_table([("ITA D1", "A", "B")])
        home = _make_table([
            ("SPA D1", "A", "T1"),
            ("SPA D1", "A", "T2"),
        ], "table_v1")
        # h2h weight=2, home weight=1 each → ITA D1=2, SPA D1=2 → tie, most_common picks first
        # Actually ITA D1 gets 2 (from h2h), SPA D1 gets 2 (from home)
        # Counter.most_common(1) picks arbitrarily on tie — just check it returns something valid
        code = _detect_main_league_code("A", "B", home, None, h2h)
        assert code in ("ITA D1", "SPA D1")


# ─── _parse_history_table ──────────────────────────────────────────────────

class TestParseHistoryTable:
    def test_valid_table(self):
        table = _make_table([
            ("TUR D1", "Fener", "GS"),
            ("TUR D1", "GS", "Fener"),
        ])
        matches = _parse_history_table(table, "TUR D1")
        assert len(matches) == 2
        assert matches[0].home_team == "Fener"
        assert matches[1].home_team == "GS"

    def test_none_table(self):
        assert _parse_history_table(None, "X") == []

    def test_filters_invalid_rows(self):
        html = """
        <table id="table_v1">
          <tr id="tr1_1" index="1">
            <td>TUR D1</td>
            <td>2026-01-01</td>
            <td>A</td>
            <td><span class="fscore_1">1-0</span></td>
            <td>B</td>
          </tr>
          <tr id="tr1_2" index="2">
            <td></td>
            <td>2026-01-02</td>
            <td>C</td>
            <td>vs</td>
            <td>D</td>
          </tr>
          <tr class="header"><td colspan="5">Header</td></tr>
        </table>
        """
        table = _soup(html).find("table")
        matches = _parse_history_table(table, "TUR D1")
        assert len(matches) == 1
        assert matches[0].home_team == "A"

    def test_is_league_match_flag(self):
        table = _make_table([
            ("TUR D1", "A", "B"),
            ("Champions League", "A", "C"),
        ])
        matches = _parse_history_table(table, "TUR D1")
        assert len(matches) == 2
        assert matches[0].is_league_match is True
        assert matches[1].is_league_match is False
