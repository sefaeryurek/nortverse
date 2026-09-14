from datetime import timezone
from unittest.mock import AsyncMock

from bs4 import BeautifulSoup
import pytest

from app.scraper import fixture, match_detail


def soup(html):
    return BeautifulSoup(html, "lxml")


def test_kickoff_is_utc():
    value = match_detail._extract_main_match_kickoff(soup('<span class="time" data-t="3/3/2026 7:30:00 PM"></span>'))
    assert value.tzinfo == timezone.utc
    assert value.hour == 19


def test_history_date_is_not_main_kickoff():
    assert match_detail._extract_main_match_kickoff(soup('<table><span data-t="2020-01-01 12:00:00"></span></table>')) is None


def test_live_score_not_saved_as_final():
    assert match_detail._extract_main_match_score(soup('<div class="fbheader"><div class="score">2</div><div class="score">1</div></div>')) == (None,) * 6


def test_final_score_derives_second_half():
    html = '<div class="fbheader"><div class="end"><div class="score">3</div><div class="score">1</div><span title="Score 1st Half">1-0</span></div></div>'
    assert match_detail._extract_main_match_score(soup(html)) == (3, 1, 1, 0, 2, 1)


@pytest.mark.parametrize("text", ["(1-0)", "-1-0", "31-0", "FT pending (1-0)",
                                  '<span class="fscore_1">-1-0</span><span class="hscore_1">(0-0)</span>'])
def test_invalid_history_score_is_not_a_finished_match(text):
    td = soup(f"<table><tr><td>{text}</td></tr></table>").find("td")
    assert match_detail._parse_score_cell(td) == (None,) * 4


def test_plain_text_final_and_half_score_remain_supported():
    td = soup("<table><tr><td>2-1 (1-0)</td></tr></table>").find("td")
    assert match_detail._parse_score_cell(td) == (2, 1, 1, 0)


@pytest.mark.parametrize("value", ["2026-03-03 19:30:00", "3/3/2026 7:30:00 PM",
                                   "2026/03/03 19:30:00", "2026-03-03T22:30:00+03:00"])
def test_history_dates_use_same_parser_and_utc(value):
    html = f'<table><tr><td>ENG PR</td><td><span data-t="{value}"></span></td><td>Home</td><td>2-1</td><td>Away</td></tr></table>'
    row = match_detail._parse_match_row(soup(html).find("tr"), "ENG PR")
    assert row.match_date.isoformat() == "2026-03-03T19:30:00+00:00"


@pytest.mark.parametrize("home", ["-1", "31", "pending"])
def test_invalid_main_final_score_discards_partial_result(home):
    html = f'<div class="fbheader"><div class="end"><div class="score">{home}</div><div class="score">0</div><span title="Score 1st Half">0-0</span></div></div>'
    assert match_detail._extract_main_match_score(soup(html)) == (None,) * 6


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["fixture", "detail"])
async def test_page_closed_after_navigation_failure(monkeypatch, kind):
    context = AsyncMock()
    page = context.new_page.return_value
    module = fixture if kind == "fixture" else match_detail
    monkeypatch.setattr(module, "goto_with_retry", AsyncMock(side_effect=RuntimeError("navigation failed")))
    with pytest.raises(RuntimeError, match="navigation failed"):
        if kind == "fixture":
            await fixture._fetch_fixture_with_ctx(context, "http://test", True)
        else:
            await match_detail.fetch_match_detail("123", ctx=context)
    page.close.assert_awaited_once()
