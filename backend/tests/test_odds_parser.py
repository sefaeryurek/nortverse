"""Oran kazıyıcı (Sprint 94 A1): kapalı satır, en yeni `mt`, maç içi çifte şans, bayat satır, geçmiş ezme.

Fikstürler 2993842'nin (27 Ekim, 2. yarı) gerçek yanıtlarından kısaltıldı: İY geçmişinin en yeni Ü/A ve AH
satırı `close:true` (oranlar 0), İY 1X2'nin en yeni satırı 3. dakikadan; MS geçmişi 45. dk ve devre arası.
"""

import json

from app.scraper.odds import build_current, latest_prematch, parse_odds, parse_summary, should_replace_history

HT_RAW = json.dumps({"ErrCode": 0, "Data": {
    "ah": [
        {"odds": {"u": "0", "g": "0", "d": "0"}, "hs": 2, "gs": 4, "mt": 1793125108, "ht": "45", "close": True, "type": 0},
        {"odds": {"u": "2.3", "g": "0", "d": "0.33"}, "hs": 2, "gs": 4, "mt": 1793125088, "ht": "45", "close": False, "type": 0},
        {"odds": {"u": "1", "g": "0", "d": "0.8"}, "hs": 0, "gs": 0, "mt": 1792528539, "ht": "", "close": False, "type": 2},
    ],
    "op": [
        {"odds": {"u": "4", "g": "2.4", "d": "2.5"}, "hs": 0, "gs": 0, "mt": 1793122404, "ht": "03", "close": False, "type": 0},
        {"odds": {"u": "3.75", "g": "2.4", "d": "2.5"}, "hs": 0, "gs": 0, "mt": 1793121110, "ht": "", "close": False, "type": 2},
    ],
    "ou": [
        {"odds": {"u": "0", "g": "0", "d": "0"}, "hs": 2, "gs": 4, "mt": 1793125108, "ht": "45", "close": True, "type": 0},
        {"odds": {"u": "5", "g": "6.5", "d": "0.13"}, "hs": 2, "gs": 4, "mt": 1793125088, "ht": "45", "close": False, "type": 0},
        {"odds": {"u": "0.7", "g": "1", "d": "1.1"}, "hs": 0, "gs": 0, "mt": 1792528539, "ht": "", "close": False, "type": 2},
    ],
}})

FT_RAW = json.dumps({"ErrCode": 0, "Data": {
    "ah": [{"odds": {"u": "0.95", "g": "-0.75", "d": "0.9"}, "hs": 2, "gs": 4, "mt": 1793125751, "ht": "HT", "close": False, "type": 0}],
    "op": [
        {"odds": {"u": "51", "g": "21", "d": "1.02"}, "hs": 2, "gs": 4, "mt": 1793125102, "ht": "45", "close": False, "type": 0},
        {"odds": {"u": "2.75", "g": "3.4", "d": "2.45"}, "hs": 0, "gs": 0, "mt": 1792382258, "ht": "", "close": False, "type": 2},
    ],
    "ou": [
        {"odds": {"u": "0.9", "g": "7.75", "d": "0.95"}, "hs": 2, "gs": 4, "mt": 1793125895, "ht": "HT", "close": False, "type": 0},
        {"odds": {"u": "0.98", "g": "2.75", "d": "0.88"}, "hs": 0, "gs": 0, "mt": 1792386496, "ht": "", "close": False, "type": 2},
    ],
}})

# Özet uç (t=10): MatchState canlıyken 0; çifte şans maç içinde güncellenmiyor (MS2 1.02 iken X2 1.29)
SUMMARY_RAW = json.dumps({"ErrCode": 0, "MatchState": 0, "Data": {
    "op": {"u": "51", "g": "21", "d": "1.02"}, "ou": {"u": "0.88", "g": "7.75", "d": "0.98"},
    "double": {"u": "0.8", "g": "0.29", "d": "0.29"}, "ah": {"u": "0.95", "g": "-0.75", "d": "0.9"},
}})

PRE_FT_RAW = json.dumps({"ErrCode": 0, "Data": {
    "op": [{"odds": {"u": "2.45", "g": "3.2", "d": "2.55"}, "hs": 0, "gs": 0, "mt": 1793100000, "ht": "", "close": False, "type": 2}],
    "ou": [{"odds": {"u": "0.95", "g": "2.25", "d": "0.85"}, "hs": 0, "gs": 0, "mt": 1793100000, "ht": "", "close": False, "type": 2}],
    "ah": [],
}})
PRE_SUMMARY_RAW = json.dumps({"ErrCode": 0, "MatchState": 0, "Data": {
    "op": {"u": "2.45", "g": "3.2", "d": "2.55"}, "ou": {"u": "0.95", "g": "2.25", "d": "0.85"},
    "double": {"u": "0.4", "g": "0.3", "d": "0.42"},
}})


def test_closed_row_is_kept_and_marked():
    ht = parse_odds(HT_RAW)
    assert ht["ou"][0] == {"mt": 1793125108, "pre": False, "min": "45", "score": "2-4", "closed": True}
    assert ht["ah"][0]["closed"] is True
    assert "closed" not in ht["ou"][1]


def test_closed_latest_row_removes_market_instead_of_falling_back():
    ht = parse_odds(HT_RAW)
    now = 1793125110  # kapanıştan 2 sn sonra
    current = build_current(None, None, ht, now=now)
    # Eskiden kapalı satır atılıp "6.5 alt @1.13" kesin kazanç olarak sunuluyordu
    assert "ou" not in current["ht"]


def test_live_info_comes_from_newest_mt_across_markets():
    current = build_current(parse_summary(SUMMARY_RAW), parse_odds(FT_RAW), parse_odds(HT_RAW), now=1793125900)
    # İY 1X2'nin en yeni satırı 3. dakika; asıl en yeni bilgi MS Ü/A'nın devre arası satırı
    assert current["live"] == {"minute": "HT", "score": "2-4", "mt": 1793125895}
    assert current["started"] is True


def test_double_chance_hidden_in_play():
    current = build_current(parse_summary(SUMMARY_RAW), parse_odds(FT_RAW), parse_odds(HT_RAW), now=1793125900)
    assert "dc" not in current["ft"]


def test_stale_in_play_row_is_not_current():
    ft = parse_odds(FT_RAW)
    fresh = build_current(None, ft, None, now=1793125895 + 30)
    assert fresh["ft"]["ou"]["line"] == 7.75
    stale = build_current(None, ft, None, now=1793125895 + 600)
    assert "ou" not in stale["ft"] and "result" not in stale["ft"]


def test_prematch_odds_from_history_and_summary_double_chance():
    current = build_current(parse_summary(PRE_SUMMARY_RAW), parse_odds(PRE_FT_RAW), {"op": [], "ou": [], "ah": []},
                            now=1793100100)
    assert current["started"] is False and current["live"] is None
    assert current["ft"]["result"] == {"1": 2.45, "X": 3.2, "2": 2.55}
    assert current["ft"]["ou"] == {"line": 2.25, "over": 1.95, "under": 1.85}
    assert current["ft"]["dc"] == {"1X": 1.4, "12": 1.3, "X2": 1.42}


def test_summary_used_only_when_ft_history_missing():
    current = build_current(parse_summary(PRE_SUMMARY_RAW), None, None, now=1793100100)
    assert current["ft"]["result"] == {"1": 2.45, "X": 3.2, "2": 2.55}


def test_summary_has_no_state():
    assert "state" not in parse_summary(SUMMARY_RAW)


def test_latest_prematch_skips_closed_rows():
    hist = {"op": [{"mt": 3, "pre": True, "closed": True},
                   {"mt": 2, "pre": True, "u": 2.0, "g": 3.0, "d": 4.0}], "ou": [], "ah": []}
    assert latest_prematch(hist)["op"]["1"] == 2.0


def test_empty_or_older_history_does_not_replace_stored():
    old = parse_odds(FT_RAW)
    assert should_replace_history(old, {"op": [], "ou": [], "ah": []}) is False
    assert should_replace_history(old, None) is False
    older = {"op": old["op"][1:], "ou": old["ou"], "ah": old["ah"]}
    assert should_replace_history(old, older) is False
    assert should_replace_history(old, old) is True
    assert should_replace_history(None, old) is True


def _responses(monkeypatch, replies):
    """`_request_once` taklidi: sıradaki (durum, başlıklar, gövde) yanıtı verir, istenen adresleri kaydeder."""
    from app.scraper import odds

    seen = []

    def fake(url, headers):
        seen.append(url)
        status, hdrs, body = replies.pop(0)
        return status, hdrs, body, "OK"

    monkeypatch.setattr(odds, "_request_once", fake)
    monkeypatch.setattr(odds, "_resolved_base", None)
    return seen


def test_get_follows_redirect_unzips_and_remembers_host(monkeypatch):
    """Kaynak gzip gönderiyor ve başka adrese yönlendiriyor; yönlendirilen adres hatırlanır (Sprint 94 I3)."""
    import gzip

    from app.scraper import odds

    seen = _responses(monkeypatch, [
        (302, {"Location": "https://live9.example/ajax/x"}, b""),
        (200, {}, gzip.compress(b'{"ok": 1}')),
        (200, {}, b'{"ok": 2}'),
    ])
    assert odds._get("/ajax/x", "1") == b'{"ok": 1}'
    assert odds._get("/ajax/y", "1") == b'{"ok": 2}'
    assert seen[0].startswith(odds.SCRAPER.odds_base_url)
    assert seen[1:] == ["https://live9.example/ajax/x", "https://live9.example/ajax/y"]


def test_get_rejects_challenge_page_and_resets_host(monkeypatch):
    import pytest

    from app.scraper import odds

    _responses(monkeypatch, [(200, {}, b'{"ok": 1}'), (200, {}, b"<html>Just a moment...</html>")])
    odds._get("/ajax/x", "1")
    assert odds._resolved_base == odds.SCRAPER.odds_base_url
    with pytest.raises(odds.SourceUnavailable):
        odds._get("/ajax/y", "1")
    assert odds._resolved_base is None  # bir dahaki istek ana adresten


def test_get_raises_http_error_for_throttling(monkeypatch):
    import pytest
    from urllib.error import HTTPError

    from app.scraper import odds

    _responses(monkeypatch, [(429, {}, b"")])
    with pytest.raises(HTTPError) as error:
        odds._get("/ajax/x", "1")
    assert error.value.code == 429  # E9 bekleme kademesi bunu yakalar


def test_concurrent_same_request_is_fetched_once(monkeypatch):
    import asyncio

    from app.scraper import odds

    calls = []

    async def slow(path, referer):
        calls.append(path)
        await asyncio.sleep(0.05)
        return b"{}"

    monkeypatch.setattr(odds, "_fetch_gated", slow)

    async def run():
        return await asyncio.gather(*(odds._fetch("/ajax/x", "1") for _ in range(3)), odds._fetch("/ajax/z", "1"))

    assert asyncio.run(run()) == [b"{}"] * 4
    assert sorted(calls) == ["/ajax/x", "/ajax/z"]


def test_opening_prematch_and_movement_on_same_line_only():
    """Sprint 94 K-2: açılış oranı (en eski maç öncesi satır); Ü/A çizgisi değiştiyse karşılaştırma yok."""
    from app.scraper.odds import opening_prematch, with_opening

    history = {
        "op": [{"mt": 3, "pre": True, "u": 1.8, "g": 3.4, "d": 4.5},       # en yeni
               {"mt": 2, "pre": True, "closed": True},
               {"mt": 1, "pre": True, "u": 2.1, "g": 3.2, "d": 3.6}],      # açılış
        "ou": [{"mt": 3, "pre": True, "u": 0.9, "g": 1.25, "d": 0.95},
               {"mt": 1, "pre": True, "u": 0.85, "g": 1.0, "d": 1.0}],     # açılış çizgisi farklı
    }
    opening = opening_prematch(history)
    assert opening["op"]["1"] == 2.1 and opening["ou"]["line"] == 1.0
    options = with_opening([
        {"market": "result", "selection": "1", "line": None},
        {"market": "ou", "selection": "over", "line": 1.25},
        {"market": "ou", "selection": "over", "line": 1.0},
    ], opening)
    assert [o["open_odds"] for o in options] == [2.1, None, 1.85]
    assert opening_prematch(None) == {}


def test_power_devig_sums_to_one_and_favours_favourite():
    """Sprint 94 K-3: 1X2 payı power yöntemiyle; favori orantılıdan biraz yüksek, toplam 1."""
    from app.scraper.odds import market_options, power_devig

    inv = {"1": 1 / 1.6, "X": 1 / 3.6, "2": 1 / 6.5}
    fair = power_devig(inv)
    assert abs(sum(fair.values()) - 1) < 1e-9
    proportional = inv["1"] / sum(inv.values())
    assert fair["1"] > proportional and fair["2"] < inv["2"] / sum(inv.values())
    assert power_devig({}) == {} and power_devig({"1": 0.0}) == {}
    opts = {o["selection"]: o["pct"] for o in market_options({"op": {"1": 1.6, "X": 3.6, "2": 6.5}})}
    assert opts == {"1": 60.7, "X": 25.6, "2": 13.7}


def test_ht_board_outcome_uses_coupon_classification():
    """Yarım kazanç 'half_win', yarım kayıp 'half_loss' (eskiden ikisi de yanlış etiketleniyordu)."""
    from app.analysis.coupons import leg_return

    assert leg_return("ht", "ou", "over", 1.25, 1.9, (1, 0), None)[0] == "half_loss"
    assert leg_return("ht", "ou", "under", 1.25, 1.9, (1, 0), None)[0] == "half_win"
    assert leg_return("ht", "ou", "over", 1.0, 1.9, (1, 0), None)[0] == "push"
