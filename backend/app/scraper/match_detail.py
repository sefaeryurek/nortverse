"""Bir maçın H2H + form verilerini nowgoal h2h sayfasından çeker.

URL: https://live5.nowgoal26.com/match/h2h-{match_id}

Sayfa yapısı:
- Ana maç bilgisi: .fbheader içinde lig adı + takımlar + (maç bitmişse) skor
- Ev takımı adı: .home (span)
- Deplasman takımı adı: .guest (span)
- Ev son maçları: table#table_v1, rows: tr[id=tr1_N], index=matchId
- Dep son maçları: table#table_v2, rows: tr[id=tr2_N], index=matchId
- H2H: table#table_v3, rows: tr[id=tr3_N]

Maç satırı sütun yapısı:
  td[0] = lig kısa kodu (TUR D1, ENG PR, TUR Cup, INT CF...)
          .title attribute = tam ad (Turkey Super Lig, Turkey Cup...)
  td[1] = tarih
  td[2] = ev sahibi takım
  td[3] = skor: <span class="fscore_1">2-1</span><span class="hscore_1">(1-0)</span>
  td[4] = deplasman takım
  td[5+] = korner, oranlar...
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Optional

from bs4 import BeautifulSoup
from bs4.element import Tag

from app.analysis.league_filter import canonical_league_name, is_supported_league
from app.config import SCRAPER
from app.models import HistoricalMatch, MatchRawData
from app.scraper.browser import browser_context, close_ad_overlay, goto_with_retry

log = logging.getLogger(__name__)

_SCORE_FT_RE = re.compile(r"(\d+)\s*-\s*(\d+)")
_SCORE_HT_RE = re.compile(r"\((\d+)\s*-\s*(\d+)\)")
_ROW_ID_RE = re.compile(r"^tr[123]_\d+$")


def _text_of(el: Optional[Tag]) -> str:
    if el is None:
        return ""
    return el.get_text(strip=True)


_HT_IN_VS_RE = re.compile(r"\(\s*(\d+)\s*-\s*(\d+)\s*,")  # "( 0-0 , 1-0 )" → HT


def _extract_main_match_kickoff(soup: BeautifulSoup) -> Optional[datetime]:
    """Ana maçın kickoff tarih/saatini çıkar.

    Yapı: <span class="time" data-t="3/3/2026 7:30:00 PM" ...>
    Format: M/D/YYYY H:MM:SS AM/PM
    """
    el = soup.select_one("span.time[data-t]")
    if el is None:
        el = soup.select_one("[data-t]")
    if el is None:
        return None
    data_t = el.get("data-t", "").strip()
    for fmt in ("%m/%d/%Y %I:%M:%S %p", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(data_t, fmt)
        except ValueError:
            continue
    return None


def _extract_main_match_score(
    soup: BeautifulSoup,
) -> tuple[Optional[int], Optional[int], Optional[int], Optional[int], Optional[int], Optional[int]]:
    """Ana maçın FT, HT ve 2Y skorlarını çıkar (bitmiş maçlar için).

    Yeni yapı (.fbheader > .end içinde):
      <div class="score">0</div>          ← home FT
      <span title="Score 1st Half">0-0</span>
      <span title="Score 2nd Half">0-0</span>
      <div class="score">0</div>          ← away FT

    Returns: (ft_home, ft_away, ht_home, ht_away, h2_home, h2_away)
    """
    ft_home = ft_away = ht_home = ht_away = h2_home = h2_away = None

    fbheader = soup.select_one(".fbheader")
    if fbheader is None:
        return ft_home, ft_away, ht_home, ht_away, h2_home, h2_away

    # FT: iki ayrı .score div'i
    score_divs = fbheader.select(".score")
    if len(score_divs) >= 2:
        try:
            ft_home = int(score_divs[0].get_text(strip=True))
            ft_away = int(score_divs[1].get_text(strip=True))
        except (ValueError, IndexError):
            ft_home = ft_away = None

    # HT ve 2Y: title attribute ile doğrudan çek
    ht_el = fbheader.select_one('[title="Score 1st Half"]')
    h2_el = fbheader.select_one('[title="Score 2nd Half"]')

    def _parse_half_score(el: Optional[Tag]) -> tuple[Optional[int], Optional[int]]:
        if el is None:
            return None, None
        m = _SCORE_FT_RE.search(el.get_text(strip=True))
        if m:
            return int(m.group(1)), int(m.group(2))
        return None, None

    ht_home, ht_away = _parse_half_score(ht_el)
    h2_home, h2_away = _parse_half_score(h2_el)

    # Fallback: eski yöntem — .vs/.end text içinden regex
    if ht_home is None:
        vs_el = fbheader.select_one(".vs, .end")
        if vs_el:
            m = _HT_IN_VS_RE.search(vs_el.get_text(" ", strip=True))
            if m:
                ht_home = int(m.group(1))
                ht_away = int(m.group(2))

    return ft_home, ft_away, ht_home, ht_away, h2_home, h2_away


def _extract_main_match_info(soup: BeautifulSoup) -> tuple[str, str, str, str]:
    """Ana maç bilgisi: home, away, league_code, league_full_name.

    Lig kısa kodu yok bu sayfada — tam adı alıp h2h tablolarından kısaltmayı çıkaracağız.
    """
    # Home ve away takım isimleri
    home_el = soup.select_one(".home") or soup.select_one(".teamHome")
    away_el = soup.select_one(".guest") or soup.select_one(".teamAway")

    home = _text_of(home_el)
    away = _text_of(away_el)

    # Lig - .fbheader > a ilk link ya da "Turkey Super Lig" tarzı metin
    league_full = ""
    fbheader = soup.select_one(".fbheader")
    if fbheader:
        # İlk <a> link genelde lig linki
        league_a = fbheader.find("a")
        if league_a:
            league_full = _text_of(league_a)

    # Fallback
    if not league_full:
        league_el = soup.select_one(".LInfo, .leagueInfo, .matchHead .league")
        league_full = _text_of(league_el)

    # Kısa kod — h2h tablolarından çıkarılacak, şimdilik boş
    return home, away, "", league_full


def _parse_score_cell(td: Tag) -> tuple[Optional[int], Optional[int], Optional[int], Optional[int]]:
    """Skor hücresinden FT ve HT skorlarını çıkar.

    Yapı: <span class="fscore_1">2-1</span><span class="hscore_1">(1-0)</span>

    Returns:
        (home_ft, away_ft, home_ht, away_ht) — HT yoksa None.
    """
    home_ft = away_ft = home_ht = away_ht = None

    fscore = td.select_one(".fscore_1, .fscore_2, .fscore_3, [class*='fscore']")
    if fscore:
        m = _SCORE_FT_RE.search(fscore.get_text(strip=True))
        if m:
            home_ft = int(m.group(1))
            away_ft = int(m.group(2))

    hscore = td.select_one(".hscore_1, .hscore_2, .hscore_3, [class*='hscore']")
    if hscore:
        m = _SCORE_HT_RE.search(hscore.get_text(strip=True))
        if m:
            home_ht = int(m.group(1))
            away_ht = int(m.group(2))

    # Fallback: span yoksa direkt metinden ara
    if home_ft is None:
        text = td.get_text(" ", strip=True)
        m = _SCORE_FT_RE.search(text)
        if m:
            home_ft = int(m.group(1))
            away_ft = int(m.group(2))
        m2 = _SCORE_HT_RE.search(text)
        if m2:
            home_ht = int(m2.group(1))
            away_ht = int(m2.group(2))

    return home_ft, away_ft, home_ht, away_ht


def _parse_match_row(
    tr: Tag, main_league_code: str
) -> Optional[HistoricalMatch]:
    """Bir maç satırından HistoricalMatch oluştur.

    main_league_code: Analiz edilen maçın lig kısa kodu (TUR D1 gibi).
                      Eşleşirse is_league_match=True olur.
    """
    tds = tr.find_all("td", recursive=False)
    if len(tds) < 5:
        return None

    # td[0]: lig kodu
    league_code = _text_of(tds[0])
    if not league_code:
        return None

    # td[1]: tarih (data-t attribute veya metin)
    match_date: Optional[datetime] = None
    date_td = tds[1]
    date_span = date_td.find("span", attrs={"data-t": True})
    if date_span:
        data_t = date_span.get("data-t", "")
        try:
            match_date = datetime.strptime(data_t, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass

    # td[2]: ev sahibi takım
    home_team = _text_of(tds[2])

    # td[3]: skor
    home_ft, away_ft, home_ht, away_ht = _parse_score_cell(tds[3])
    if home_ft is None or away_ft is None:
        return None

    # td[4]: deplasman takımı
    away_team = _text_of(tds[4])

    if not home_team or not away_team:
        return None

    # Lig kodu ana maçla aynı mı? (Sprint 8.9 — kanonik karşılaştırma)
    # H2H tablolarında "ENG PR" gibi kısa kod olabilir; ana maç için "English Premier League"
    # tam adı gelmiş olabilir → kanonik forma çevirip karşılaştır.
    # Ek olarak: H2H satırının kendisi kupa ise lig maçı sayma (UEL/Cup karışıklığı).
    canon_row = canonical_league_name(league_code)
    canon_main = canonical_league_name(main_league_code)
    is_league = (
        bool(canon_main)
        and canon_row == canon_main
        and is_supported_league(league_code)
    )

    return HistoricalMatch(
        opponent=away_team,  # perspektif sonra ayarlanır
        home_team=home_team,
        away_team=away_team,
        home_score_ft=home_ft,
        away_score_ft=away_ft,
        home_score_ht=home_ht,
        away_score_ht=away_ht,
        league_code=league_code,
        is_league_match=is_league,
        match_date=match_date,
    )


def _detect_main_league_code(
    home_team: str,
    away_team: str,
    home_table: Optional[Tag],
    away_table: Optional[Tag],
    h2h_table: Optional[Tag],
) -> str:
    """Analiz edilen maçın lig kısa kodunu tespit et.

    Strateji: H2H tablosunda en çok geçen lig kodu,
    yoksa home_table'da en çok geçen lig kodu.
    Çünkü ana maç da aynı ligde oynanacak.
    """
    from collections import Counter

    counter: Counter[str] = Counter()

    # H2H en iyi sinyal çünkü aynı iki takımın maçları
    if h2h_table is not None:
        for tr in h2h_table.find_all("tr", id=_ROW_ID_RE):
            tds = tr.find_all("td", recursive=False)
            if tds:
                code = _text_of(tds[0])
                # "TUR Cup" gibi kupa maçlarını düşük ağırlıklı say
                if code and "cup" not in code.lower() and "friendly" not in code.lower():
                    counter[code] += 2

    # Home table'dan da destek al
    if home_table is not None:
        for tr in home_table.find_all("tr", id=_ROW_ID_RE):
            tds = tr.find_all("td", recursive=False)
            if tds:
                code = _text_of(tds[0])
                if code and "cup" not in code.lower() and "friendly" not in code.lower():
                    counter[code] += 1

    if counter:
        most_common = counter.most_common(1)[0][0]
        log.debug("Ana maç lig kodu tespit edildi: %s (sayım: %s)", most_common, dict(counter))
        return most_common

    return ""


def _parse_history_table(
    table: Optional[Tag], main_league_code: str
) -> list[HistoricalMatch]:
    """Bir tablodan tüm maç satırlarını HistoricalMatch listesi olarak çıkar."""
    if table is None:
        return []

    matches: list[HistoricalMatch] = []
    for tr in table.find_all("tr", id=_ROW_ID_RE):
        m = _parse_match_row(tr, main_league_code)
        if m:
            matches.append(m)
    return matches


def _save_debug_html(match_id: str, html: str) -> None:
    SCRAPER.debug_dir.mkdir(parents=True, exist_ok=True)
    path = SCRAPER.debug_dir / f"h2h_{match_id}_{datetime.now():%Y%m%d_%H%M%S}.html"
    path.write_text(html, encoding="utf-8")
    log.info("H2H HTML debug'e kaydedildi: %s", path)


async def fetch_match_detail(
    match_id: str,
    ctx=None,
    expected_league_name: Optional[str] = None,
) -> MatchRawData:
    """Verilen maç ID için H2H sayfasından detay veriyi çek.

    ctx: Varolan BrowserContext (pipeline'dan gelir). None ise yeni browser açılır.
    expected_league_name: Bültenden gelen kanonik lig adı (Sprint 8.9). Verildiyse
        H2H tabanlı tespit yerine bu kullanılır — UEL/UCL gibi maçlarda H2H'ın
        yanlış "ENG PR" döndürmesini engeller.
    """
    url = SCRAPER.base_url + SCRAPER.match_detail_path.format(match_id=match_id)
    log.info("Match detail çekiliyor: %s", url)

    async def _fetch(ctx_) -> str:
        page = await ctx_.new_page()
        await goto_with_retry(page, url)
        await page.wait_for_timeout(int(SCRAPER.default_wait * 1000))
        await close_ad_overlay(page)
        await page.wait_for_timeout(1000)
        html = await page.content()
        await page.close()
        return html

    if ctx is not None:
        html = await _fetch(ctx)
    else:
        async with browser_context() as new_ctx:
            html = await _fetch(new_ctx)

    soup = BeautifulSoup(html, "lxml")

    # Ana maç bilgisi
    home, away, _, league_full = _extract_main_match_info(soup)
    kickoff_time = _extract_main_match_kickoff(soup)
    actual_ft_home, actual_ft_away, actual_ht_home, actual_ht_away, actual_h2_home, actual_h2_away = _extract_main_match_score(soup)

    if not home or not away:
        log.warning("Takım isimleri çıkarılamadı (match_id=%s)", match_id)
        _save_debug_html(match_id, html)

    # Tabloları bul
    home_table = soup.find("table", id="table_v1")
    away_table = soup.find("table", id="table_v2")
    h2h_table = soup.find("table", id="table_v3")

    # Ana maçın lig kısa kodunu tespit et — Sprint 8.9 önceliği:
    # 1) Bültenden gelen ad (expected_league_name) en güvenilir
    # 2) HTML .fbheader'daki tam ad (league_full)
    # 3) H2H tablosundan istatistiksel tespit (eski yöntem)
    if expected_league_name:
        main_league_code = expected_league_name
    elif league_full:
        main_league_code = league_full
    else:
        main_league_code = _detect_main_league_code(home, away, home_table, away_table, h2h_table)

    # Tabloları parse et
    home_recent = _parse_history_table(home_table, main_league_code)
    away_recent = _parse_history_table(away_table, main_league_code)
    h2h = _parse_history_table(h2h_table, main_league_code)

    # Ligde oynanan maç sayıları
    home_league_count = sum(1 for m in home_recent if m.is_league_match)
    away_league_count = sum(1 for m in away_recent if m.is_league_match)

    raw = MatchRawData(
        match_id=match_id,
        home_team=home or "?",
        away_team=away or "?",
        league_code=main_league_code or league_full or "?",
        league_name=league_full or None,
        kickoff_time=kickoff_time,
        home_recent_matches=home_recent,
        away_recent_matches=away_recent,
        h2h_matches=h2h,
        home_league_match_count=home_league_count,
        away_league_match_count=away_league_count,
        actual_ft_home=actual_ft_home,
        actual_ft_away=actual_ft_away,
        actual_ht_home=actual_ht_home,
        actual_ht_away=actual_ht_away,
        actual_h2_home=actual_h2_home,
        actual_h2_away=actual_h2_away,
    )

    log.info(
        "Çekildi: %s vs %s [%s] | ev=%d (lig=%d) dep=%d (lig=%d) h2h=%d (lig=%d)",
        raw.home_team,
        raw.away_team,
        raw.league_code,
        len(raw.home_recent_matches),
        home_league_count,
        len(raw.away_recent_matches),
        away_league_count,
        len(raw.h2h_matches),
        sum(1 for m in raw.h2h_matches if m.is_league_match),
    )

    if not home_recent and not away_recent and not h2h:
        log.warning("Hiç tablo parse edilemedi, HTML debug'e kaydediliyor")
        _save_debug_html(match_id, html)

    return raw
