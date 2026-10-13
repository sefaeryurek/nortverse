"""source_board.py parse testleri — ast.literal_eval güvenliği + parse_source_board davranışı."""

import gzip
import json
import pytest

from app.scraper.source_board import parse_source_board


def _make_payload(rows: list[str], err_code: int = 0) -> bytes:
    data_str = "\n".join(f"A[{i}]={r};" for i, r in enumerate(rows))
    return json.dumps({"ErrCode": err_code, "Data": data_str}).encode()


def _simple_row(match_id: int = 123456, code: int = -1,
                home: int = 2, away: int = 1,
                ht_home: int = 1, ht_away: int = 0) -> str:
    return (
        f"[{match_id},'a','b','c','d','e','f',{code},{home},{away},"
        f"{ht_home},{ht_away},'x','y']"
    )


class TestParseSourceBoard:
    def test_finished_match(self):
        payload = _make_payload([_simple_row()])
        result = parse_source_board(payload)
        assert "123456" in result
        s = result["123456"]
        assert s.status == "finished"
        assert s.home == 2
        assert s.away == 1
        assert s.ht_home == 1
        assert s.ht_away == 0

    def test_live_match(self):
        payload = _make_payload([_simple_row(code=1)])
        result = parse_source_board(payload)
        assert result["123456"].status == "live"

    def test_scheduled_match(self):
        payload = _make_payload([_simple_row(code=0, home=0, away=0)])
        result = parse_source_board(payload)
        s = result["123456"]
        assert s.status == "scheduled"
        assert s.home is None
        assert s.away is None

    def test_postponed_match(self):
        payload = _make_payload([_simple_row(code=-11)])
        result = parse_source_board(payload)
        assert result["123456"].status == "postponed"

    def test_unknown_code_skipped(self):
        payload = _make_payload([_simple_row(code=99)])
        with pytest.raises(ValueError, match="Empty"):
            parse_source_board(payload)

    def test_multiple_matches(self):
        rows = [_simple_row(match_id=1, code=-1), _simple_row(match_id=2, code=1)]
        payload = _make_payload(rows)
        result = parse_source_board(payload)
        assert len(result) == 2
        assert result["1"].status == "finished"
        assert result["2"].status == "live"

    def test_gzip_payload(self):
        raw = _make_payload([_simple_row()])
        compressed = gzip.compress(raw)
        result = parse_source_board(compressed)
        assert "123456" in result

    def test_invalid_err_code(self):
        payload = json.dumps({"ErrCode": 1, "Data": ""}).encode()
        with pytest.raises(ValueError, match="Invalid"):
            parse_source_board(payload)

    def test_empty_data(self):
        payload = json.dumps({"ErrCode": 0, "Data": ""}).encode()
        with pytest.raises(ValueError, match="Empty"):
            parse_source_board(payload)

    def test_short_fields_skipped(self):
        payload = _make_payload(["[1,2,3]"])
        with pytest.raises(ValueError, match="Empty"):
            parse_source_board(payload)

    def test_invalid_score_skipped(self):
        payload = _make_payload([_simple_row(home=50, away=0)])
        with pytest.raises(ValueError, match="Empty"):
            parse_source_board(payload)

    def test_consecutive_commas(self):
        row = "[999,'a','b','c','d','e','f',-1,3,0,,,'x','y']"
        payload = _make_payload([row])
        result = parse_source_board(payload)
        assert "999" in result
        assert result["999"].ht_home is None

    def test_ast_literal_eval_not_eval(self):
        """ast.literal_eval güvenli olduğunu doğrula — __import__ gibi ifadeler reddedilir."""
        evil = "[__import__('os').system('echo pwned')]"
        payload = _make_payload([evil])
        with pytest.raises(ValueError, match="Empty"):
            parse_source_board(payload)
