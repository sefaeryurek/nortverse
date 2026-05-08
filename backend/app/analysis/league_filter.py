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
    # İspanya
    "spanish la liga": "Spanish La Liga",
    "spain la liga": "Spanish La Liga",
    "la liga": "Spanish La Liga",
    "esp pr": "Spanish La Liga",
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
    "eredivisie": "Dutch Eredivisie",
    "ned d1": "Dutch Eredivisie",
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
    # ABD
    "major league soccer": "Major League Soccer",
    "mls": "Major League Soccer",
    "usa mls": "Major League Soccer",
    # Brezilya
    "brazilian serie a": "Brazilian Serie A",
    "brazil serie a": "Brazilian Serie A",
    "bra d1": "Brazilian Serie A",
}


def canonical_league_name(name: str | None) -> str:
    """Lig adını kanonik forma çevir. Tanınmıyorsa orijinali (trimmed) döner."""
    if not name:
        return ""
    key = name.lower().strip()
    return LEAGUE_ALIASES.get(key, name.strip())


def is_supported_league(*names: str | None) -> bool:
    """Verilen lig adı/kodlarından **herhangi biri** lig maçı işareti veriyorsa True.

    Birden fazla parametre kabul eder (örn. league_name + league_code) — biri kanonik
    bilinen lig ise filtrelemeyi geçer; tümü kupa keyword'üne uyarsa False.

    Boş/None değerler atlanır. Hiç geçerli değer yoksa False (güvenli taraf).
    """
    candidates = [n for n in names if n and n.strip() and n.strip() != "?"]
    if not candidates:
        return False

    # 1. Bilinen lig listesinde varsa → kesin lig (kara liste override)
    for c in candidates:
        if c.lower().strip() in LEAGUE_ALIASES:
            return True

    # 2. Hiçbiri bilinen değil → kara liste keyword kontrolü
    # Eğer adlardan en az biri "temiz" görünürse (kara liste eşleşmiyor) → lig kabul
    # Tümü kara liste keyword'üne uyuyorsa → kupa
    has_clean = False
    for c in candidates:
        lower = c.lower()
        if not any(kw in lower for kw in CUP_KEYWORDS):
            has_clean = True
            break

    return has_clean
