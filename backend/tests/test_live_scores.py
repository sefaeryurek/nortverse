"""live_scores.py parse testleri — mock HTML ile birim test."""

from app.scraper.live_scores import parse_live_scores


def _row(match_id: str, status: str, score: str = "2 - 1",
         score_class: str = "f-b blue") -> str:
    return (
        f'<tr id="tr1_{match_id}">'
        f'<td class="status">{status}</td>'
        f'<td class="{score_class}">{score}</td>'
        f'</tr>'
    )


def _wrap(rows: str) -> str:
    return f"<html><body><table>{rows}</table></body></html>"


class TestParseLiveScores:
    def test_finished_match(self):
        html = _wrap(_row("111", "FT"))
        result = parse_live_scores(html)
        assert result["111"].status == "finished"
        assert result["111"].home == 2
        assert result["111"].away == 1

    def test_live_match_minute(self):
        html = _wrap(_row("222", "45"))
        result = parse_live_scores(html)
        assert result["222"].status == "live"
        assert result["222"].minute == "45"

    def test_live_match_added_time(self):
        html = _wrap(_row("333", "90+3"))
        result = parse_live_scores(html)
        assert result["333"].status == "live"
        assert result["333"].minute == "90+3"

    def test_halftime(self):
        html = _wrap(_row("444", "HT", "1 - 0"))
        result = parse_live_scores(html)
        assert result["444"].status == "live"
        assert result["444"].minute == "HT"
        assert result["444"].home == 1

    def test_second_half(self):
        html = _wrap(_row("555", "2nd Half", "3 - 2"))
        result = parse_live_scores(html)
        assert result["555"].status == "live"
        assert result["555"].minute is None

    def test_postponed(self):
        html = _wrap(_row("666", "Postp."))
        result = parse_live_scores(html)
        assert result["666"].status == "postponed"

    def test_cancelled(self):
        html = _wrap(_row("777", "Canc."))
        result = parse_live_scores(html)
        assert result["777"].status == "postponed"

    def test_scheduled(self):
        html = _wrap(_row("888", "19:00"))
        result = parse_live_scores(html)
        assert result["888"].status == "scheduled"
        assert result["888"].home is None

    def test_multiple_matches(self):
        rows = _row("1", "FT", "1 - 0") + _row("2", "45", "0 - 0")
        html = _wrap(rows)
        result = parse_live_scores(html)
        assert len(result) == 2
        assert result["1"].status == "finished"
        assert result["2"].status == "live"

    def test_invalid_score_skipped(self):
        html = _wrap(_row("999", "FT", "invalid"))
        result = parse_live_scores(html)
        assert "999" not in result

    def test_empty_html(self):
        result = parse_live_scores("<html><body></body></html>")
        assert result == {}

    def test_no_score_cell(self):
        html = _wrap(
            '<tr id="tr1_111"><td class="status">FT</td></tr>'
        )
        result = parse_live_scores(html)
        assert "111" not in result
