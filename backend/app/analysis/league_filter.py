"""Lig vs kupa/turnuva ayrımı + kanonik lig adı normalizasyonu.

Sistem **sadece lig maçlarını** işler. Kupa, Avrupa kupaları, friendly,
milli takım maçları:
- Bültenden çıkarılır
- DB'ye yazılmaz
- /api/results'tan filtrelenir

Hibrit yaklaşım: kara liste keyword (geniş kapsama) + opsiyonel kanonik form.
"""

from __future__ import annotations

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
    "champions",
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
    # İngiltere League One/Two
    "england league one": "England League One",
    "eng l1": "England League One",
    "england league two": "England League Two",
    "eng l2": "England League Two",
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
    # İsveç
    "sweden superettan": "Swedish Superettan",
    "swe d2": "Swedish Superettan",
    "sweden allsvenskan": "Swedish Allsvenskan",
    "swe d1": "Swedish Allsvenskan",
}


def canonical_league_name(name: str | None) -> str:
    """Lig adını kanonik forma çevir. Tanınmıyorsa orijinali (trimmed) döner."""
    if not name:
        return ""
    key = name.lower().strip()
    return LEAGUE_ALIASES.get(key, name.strip())


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
    if any(any(keyword in candidate.lower() for keyword in CUP_KEYWORDS)
           and candidate.lower().strip() not in LEAGUE_ALIASES for candidate in candidates):
        return False

    return True
