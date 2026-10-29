"""Lig vs kupa/turnuva ayrımı + kanonik lig adı normalizasyonu.

Sistem **sadece lig maçlarını** işler. Kupa, Avrupa kupaları, friendly,
milli takım maçları:
- Bültenden çıkarılır
- DB'ye yazılmaz
- /api/results'tan filtrelenir

Hibrit yaklaşım: kara liste keyword (geniş kapsama) + opsiyonel kanonik form.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone

# Lig adında bu keyword'lerden biri geçiyorsa → kupa/turnuva → işleme.
# Keyword bazlı pragmatik filtre; yanlış pozitif çıkarsa bilinen liglere whitelist
# (LEAGUE_ALIASES kanonik dönüşümle) override edilebilir.
CUP_KEYWORDS = (
    # Avrupa kupaları
    "champions league",
    "europa league",
    "conference league",
    "uefa",
    " uel",
    " ucl",
    "europa",
    # "champions" tek kelime olarak _CUP_PATTERNS'ta — alt dize araması "Championship"i (İskoçya, USL,
    # Galler, K. İrlanda 2. lig) kupa sayıyordu (Sprint 94 F4)
    # Ulusal kupalar
    " cup",
    "cup ",
    "kupa",
    "coupe",
    "copa",
    "pokal",
    "coppa",
    "taca",
    "taça",
    # Süper kupalar
    "super cup",
    "supercup",
    "shield",
    "trophy",
    "supercopa",
    "beker",
    "asian games",
    "olympic games",
    "pan american games",
    # Hazırlık / dostluk
    "friendly",
    "friendlies",
    "exhibition",
    "amistosos",
    "amichevoli",
    # Milli takımlar / uluslararası
    "world cup",
    "euro 2",
    "nations league",
    "qualif",
    "playoff",
    "play-off",
    "international",
    "qualifier",
    "qualifying",
    "youth league",
    "u19",
    "u20",
    "u21",
    "u23",
)


# Bilinen ligler için kanonik ad eşlemesi.
# Aynı lig farklı kaynaklarda farklı isimlerle gelebilir (bülten vs H2H tablosu).
# Tüm sistem `canonical_league_name()` ile normalize edilmiş tek form kullanır.
# Anahtarlar lowercase, değerler kullanıcıya gösterilen kanonik form.
LEAGUE_ALIASES: dict[str, str] = {
    # İngiltere
    "english premier league": "English Premier League",
    "england premier league": "English Premier League",
    "premier league": "English Premier League",
    "eng pr": "English Premier League",
    "epl": "English Premier League",
    "english championship": "English Championship",
    "england championship": "English Championship",
    "eng ch": "English Championship",
    "eng lch": "English Championship",
    # İspanya
    "spanish la liga": "Spanish La Liga",
    "spain la liga": "Spanish La Liga",
    "la liga": "Spanish La Liga",
    "esp pr": "Spanish La Liga",
    "spa d1": "Spanish La Liga",
    "primera division": "Spanish La Liga",
    # İtalya
    "italy serie a": "Italy Serie A",
    "italian serie a": "Italy Serie A",
    "serie a": "Italy Serie A",
    "ita d1": "Italy Serie A",
    # Almanya
    "german bundesliga": "German Bundesliga",
    "germany bundesliga": "German Bundesliga",
    "bundesliga": "German Bundesliga",
    "ger d1": "German Bundesliga",
    # Fransa
    "french ligue 1": "French Ligue 1",
    "france ligue 1": "French Ligue 1",
    "ligue 1": "French Ligue 1",
    "fra d1": "French Ligue 1",
    # Türkiye
    "turkish super lig": "Turkish Super Lig",
    "turkey super lig": "Turkish Super Lig",
    "super lig": "Turkish Super Lig",
    "tur d1": "Turkish Super Lig",
    # Hollanda
    "dutch eredivisie": "Dutch Eredivisie",
    "netherlands eredivisie": "Dutch Eredivisie",
    "holland eredivisie": "Dutch Eredivisie",
    "eredivisie": "Dutch Eredivisie",
    "ned d1": "Dutch Eredivisie",
    "hol d1": "Dutch Eredivisie",
    # Portekiz
    "portuguese primeira liga": "Portuguese Primeira Liga",
    "portugal primeira liga": "Portuguese Primeira Liga",
    "primeira liga": "Portuguese Primeira Liga",
    "por d1": "Portuguese Primeira Liga",
    "liga portugal 1": "Portuguese Primeira Liga",
    "liga portugal": "Portuguese Primeira Liga",
    # Belçika
    "belgian pro league": "Belgian Pro League",
    "belgium pro league": "Belgian Pro League",
    "jupiler pro league": "Belgian Pro League",
    "bel d1": "Belgian Pro League",
    # İskoçya
    "scottish premiership": "Scottish Premiership",
    "scotland premiership": "Scottish Premiership",
    "sco pr": "Scottish Premiership",
    # İspanya 2. Lig
    "spanish segunda": "Spanish Segunda",
    "spain segunda": "Spanish Segunda",
    "spa d2": "Spanish Segunda",
    "spanish la liga 2": "Spanish Segunda",  # bülten adı (Sprint 94 F7)
    # İtalya 2. Lig
    "italy serie b": "Italy Serie B",
    "italian serie b": "Italy Serie B",
    "serie b": "Italy Serie B",
    "ita d2": "Italy Serie B",
    # Almanya 2. Lig
    "german 2. bundesliga": "German 2. Bundesliga",
    "germany 2. bundesliga": "German 2. Bundesliga",
    "2. bundesliga": "German 2. Bundesliga",
    "ger d2": "German 2. Bundesliga",
    # Bülten tam adları (Sprint 92: kısa kodla aynı kanonik ada gitmezse lig süzgeci boş kalır)
    "german bundesliga 2": "German 2. Bundesliga",
    "germany bundesliga 2": "German 2. Bundesliga",
    "bundesliga 2": "German 2. Bundesliga",
    # İngiltere League One/Two
    "england league one": "England League One",
    "eng l1": "England League One",
    "england league two": "England League Two",
    "eng l2": "England League Two",
    # Bülten tam adları (Sprint 94 F7): DB'de "England League 1" (12) ve "England League One" (1) aynı lig iki adla
    "england league 1": "England League One",
    "england league 2": "England League Two",
    # Türkiye 1. Lig (H2H kodu "TFF 1. Lig")
    "turkey 1. lig": "Turkey 1. Lig",
    "tff 1. lig": "Turkey 1. Lig",
    # Hollanda 2. Lig
    "holland eerste divisie": "Dutch Eerste Divisie",
    "dutch eerste divisie": "Dutch Eerste Divisie",
    "eerste divisie": "Dutch Eerste Divisie",
    "hol d2": "Dutch Eerste Divisie",
    # Çekya
    "czech republic gambrinus liga": "Czech First League",
    "czech first league": "Czech First League",
    "cze d1": "Czech First League",
    # Yunanistan
    "greece super league a": "Greek Super League",
    "greek super league": "Greek Super League",
    "gre d1": "Greek Super League",
    # ABD
    "major league soccer": "Major League Soccer",
    "mls": "Major League Soccer",
    "usa mls": "Major League Soccer",
    # Brezilya
    "brazilian serie a": "Brazilian Serie A",
    "brazil serie a": "Brazilian Serie A",
    "bra d1": "Brazilian Serie A",
    # Arjantin
    "argentine division 1": "Argentine Division 1",
    "argentina primera": "Argentine Division 1",
    "arg d1": "Argentine Division 1",
    # Mısır
    "egyptian premier league": "Egyptian Premier League",
    "egypt premier league": "Egyptian Premier League",
    "egy d1": "Egyptian Premier League",
    # Nijerya
    "nigerian premier league": "Nigerian Premier League",
    "nga pr": "Nigerian Premier League",
    # İrlanda
    "ireland premier division": "Ireland Premier Division",
    "ire pr": "Ireland Premier Division",
    # Kolombiya
    "categoria primera a": "Colombian Primera A",
    "col d1": "Colombian Primera A",
    # Uruguay
    "liga auf uruguaya": "Uruguayan Primera",
    "uru d1": "Uruguayan Primera",
    # Tunus
    "tunisian ligue 1": "Tunisian Ligue 1",
    "tun d1": "Tunisian Ligue 1",
    # İsviçre
    "switzerland super league": "Swiss Super League",
    "swiss super league": "Swiss Super League",
    "swi d1": "Swiss Super League",
    # Polonya
    "poland ekstraklasa": "Polish Ekstraklasa",
    "polish ekstraklasa": "Polish Ekstraklasa",
    "pol d1": "Polish Ekstraklasa",
    "pol pr": "Polish Ekstraklasa",  # H2H kodu (Sprint 94 F7)
    # İsveç
    "sweden superettan": "Swedish Superettan",
    "swe d2": "Swedish Superettan",
    "sweden allsvenskan": "Swedish Allsvenskan",
    "swe d1": "Swedish Allsvenskan",
}


MAIN_LEAGUES: frozenset[str] = frozenset({
    "English Premier League",
    "Spanish La Liga",
    "Italy Serie A",
    "German Bundesliga",
    "France Ligue 1",
    "French Ligue 1",
    "Turkey Super Lig",
    "Turkish Super Lig",
    "Dutch Eredivisie",
    "Holland Eredivisie",
})


# Gölgedeki ligler (Sprint 92, kullanıcı onaylı): arşivi kuruldu, tahminleri deftere yazılır ama ekranda
# (bülten, canlı sayfa, değerlendirme özeti) görünmez; karnesi ayrı tutulur. Ortak havuzlar (COND "tüm
# ligler", lig ortalaması genel değeri, Poisson 2. yarı payı) sadece ana liglerden kurulur → ana liglerin
# yüzdeleri değişmez.
SHADOW_LEAGUES: frozenset[str] = frozenset({
    "English Championship",
    "German 2. Bundesliga",
    "Portuguese Primeira Liga",
    "Belgian Pro League",
    "Scottish Premiership",
})


# Sprint 94 P3: ekran ve ortak havuz ayrı listeler.
# - POOL_LEAGUES: ortak havuzlara (COND "tüm ligler", lig ortalamasının genel değeri, Poisson 2. yarı payı) giren
#   ligler. Buraya lig eklemek ana liglerin yüzdelerini kaydırır → ayrı karar + yeni kural sürümleri (gölge).
# - DISPLAY_LEAGUES: ekranda (bülten, sonuçlar, canlı, İY panosu, değerlendirme ana karnesi) görünen ligler.
#   Gölgedeki bir lig ekrana alınınca (terfi) SADECE bu liste değişir.
# Terfi: kanonik ad → ekrana alındığı İstanbul günü. O günden önceki defter kayıtları gölge karnede kalır, sonrası
# ana karneye girer. Ölçütler `league-promotion-report <lig>` ile; karar sahibindir (audit_log + CLAUDE.md).
POOL_LEAGUES: frozenset[str] = MAIN_LEAGUES
PROMOTED_LEAGUES: dict[str, date] = {}
DISPLAY_LEAGUES: frozenset[str] = MAIN_LEAGUES | frozenset(PROMOTED_LEAGUES)


def _canonical_in(names: tuple[str | None, ...], pool) -> str | None:
    """Adlardan biri listedeyse listedeki adı döner (önce olduğu gibi, sonra kanonik form)."""
    for n in names:
        if not n:
            continue
        if n.strip() in pool:
            return n.strip()
        canonical = canonical_league_name(n)
        if canonical in pool:
            return canonical
    return None


def _promoted_by(league: str, at: datetime | None) -> bool:
    """Terfi edilen lig `at` anında ekranda mıydı? `at` verilmezse bugün."""
    since = PROMOTED_LEAGUES.get(league)
    if since is None:
        return False
    if at is None:
        return True
    from app.config import ISTANBUL_TZ

    day = (at if at.tzinfo else at.replace(tzinfo=timezone.utc)).astimezone(ISTANBUL_TZ).date()
    return day >= since


def is_display_league(*names: str | None, at: datetime | None = None) -> bool:
    """Ekranda görünen lig mi (7 ana lig + terfi edilenler). `at`: o anki durum (değerlendirme kayıt tarihi)."""
    if _canonical_in(names, MAIN_LEAGUES):
        return True
    promoted = _canonical_in(names, PROMOTED_LEAGUES)
    return promoted is not None and _promoted_by(promoted, at)


def is_pool_league(*names: str | None) -> bool:
    """Ortak havuzlara giren lig mi? (bugün sadece 7 ana lig)."""
    return _canonical_in(names, POOL_LEAGUES) is not None


def is_shadow_league(*names: str | None, at: datetime | None = None) -> bool:
    """Gölgede: takip edilir, deftere yazılır, ekranda görünmez (terfi tarihinden önce terfi edilen lig de)."""
    if is_display_league(*names, at=at):
        return False
    return _canonical_in(names, SHADOW_LEAGUES | frozenset(PROMOTED_LEAGUES)) is not None


def is_tracked_league(*names: str | None) -> bool:
    """Tahmin üretilip deftere yazılan ligler: ekrandaki ligler + gölgedeki ligler."""
    return is_display_league(*names) or is_shadow_league(*names)


def is_main_league(*names: str | None) -> bool:
    """Bugün ekranda görünen lig mi — `is_display_league` ile aynı (eski ad, çağıranlar ekran anlamında kullanır)."""
    return is_display_league(*names)


def match_league_name(league_code: str | None, league_name: str | None) -> str:
    """Maçın pattern/defter için lig adı — tek kaynak.

    Önce kısa kod (H2H sayfasından, tutarlı), sonra kaynak adı; ikisi de kanonik forma çevrilir.
    Boş lig adı lig süzgecini kapatıp başka liglerle eşleşmeye yol açıyordu (Sprint 90).
    """
    for candidate in (league_code, league_name):
        canonical = canonical_league_name(candidate)
        if canonical:
            return canonical
    return ""


def canonical_league_name(name: str | None) -> str:
    """Lig adını kanonik forma çevir. Tanınmıyorsa orijinali (trimmed) döner."""
    if not name:
        return ""
    key = name.lower().strip()
    return LEAGUE_ALIASES.get(key, name.strip())


_CUP_PATTERNS = (re.compile(r"\bchampions\b"),)


def _looks_like_cup(name: str) -> bool:
    low = name.lower()
    return any(keyword in low for keyword in CUP_KEYWORDS) or any(p.search(low) for p in _CUP_PATTERNS)


def is_supported_league(*names: str | None) -> bool:
    """Kupa işareti yoksa geçerli lig adı veya kodunu kabul et.

    Birden fazla parametre kabul eder (örn. league_name + league_code).
    Açık kupa/turnuva adı, diğer alandaki eski lig koduna üstün gelir.

    Boş/None değerler atlanır. Hiç geçerli değer yoksa False (güvenli taraf).
    """
    candidates = [n for n in names if n and n.strip() and n.strip() != "?"]
    if not candidates:
        return False

    # An explicit competition name must not be overridden by a stale league code.
    if any(_looks_like_cup(candidate) and candidate.lower().strip() not in LEAGUE_ALIASES
           for candidate in candidates):
        return False

    return True
