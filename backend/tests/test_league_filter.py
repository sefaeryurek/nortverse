"""Sprint 8.9 — `is_supported_league` ve `canonical_league_name` testleri."""

import pytest

from app.analysis.league_filter import (
    canonical_league_name,
    is_supported_league,
    LEAGUE_ALIASES,
)


class TestIsSupportedLeague:
    """Lig vs kupa/turnuva ayrımı."""

    @pytest.mark.parametrize("name", [
        "English Premier League",
        "Italy Serie A",
        "Spain La Liga",
        "German Bundesliga",
        "French Ligue 1",
        "Turkish Super Lig",
        "Dutch Eredivisie",
        "Portuguese Primeira Liga",
        # Kanonik olmayan ama lig
        "Some Random Lig",  # kara liste eşleşmiyor → True (defansif lig kabul)
        "Norway Eliteserien",
    ])
    def test_known_leagues_passes(self, name: str) -> None:
        assert is_supported_league(name) is True, f"Lig olarak kabul edilmeli: {name}"

    @pytest.mark.parametrize("name", [
        "UEFA Champions League",
        "UEFA Europa League",
        "UEFA Conference League",
        "England FA Cup",
        "Turkey Cup",
        "Italy Coppa Italia",
        "Germany DFB Pokal",
        "Spain Copa del Rey",
        "France Coupe de France",
        "Friendly Match",
        "International Friendlies",
        "World Cup Qualifier",
        "Euro 2024 Qualifier",
        "UEFA Nations League",
        "Community Shield",
        "Super Cup",
        "Spain Supercopa",
        "U21 Championship",
        "Netherlands KNVB Beker",
        "Asian Games",
        "Olympic Games Women",
    ])
    def test_cup_competitions_rejected(self, name: str) -> None:
        assert is_supported_league(name) is False, f"Kupa olarak reddedilmeli: {name}"

    def test_empty_or_unknown_rejected(self) -> None:
        assert is_supported_league(None) is False
        assert is_supported_league("") is False
        assert is_supported_league("?") is False
        assert is_supported_league("   ") is False

    def test_multi_arg_any_match(self) -> None:
        """Birden fazla parametre verilirse, en az biri lig ise True."""
        # A stale code cannot turn an explicit cup into a league match.
        assert is_supported_league("UEFA Cup", "English Premier League") is False
        # Her ikisi de kupa → False
        assert is_supported_league("UEFA Cup", "FA Cup") is False
        # Birinden biri None
        assert is_supported_league(None, "Italy Serie A") is True

    def test_case_insensitive(self) -> None:
        assert is_supported_league("english premier league") is True
        assert is_supported_league("uefa champions league") is False
        # "CUP" tek başına gerçek bir lig adı olarak geçmez; gerçek vaka:
        assert is_supported_league("FA Cup") is False
        assert is_supported_league("fa cup") is False

    def test_known_alias_overrides_blacklist(self) -> None:
        """LEAGUE_ALIASES içinde olan ad, kara liste keyword içerse bile lig sayılır."""
        # Edge case: kanonik tablo bilinen liglere whitelist override sağlar
        # Şu an LEAGUE_ALIASES'taki tüm değerler zaten temiz, ama mantık doğru kalmalı
        for alias_key in LEAGUE_ALIASES:
            assert is_supported_league(alias_key) is True, \
                f"Kanonik alias lig sayılmalı: {alias_key}"


class TestCanonicalLeagueName:
    """Lig adı kanonik form çevrimi."""

    def test_known_aliases(self) -> None:
        assert canonical_league_name("eng pr") == "English Premier League"
        assert canonical_league_name("ENG PR") == "English Premier League"
        assert canonical_league_name("English Premier League") == "English Premier League"
        assert canonical_league_name("ita d1") == "Italy Serie A"
        assert canonical_league_name("Serie A") == "Italy Serie A"
        assert canonical_league_name("la liga") == "Spanish La Liga"
        assert canonical_league_name("tur d1") == "Turkish Super Lig"
        assert canonical_league_name("NGA PR") == "Nigerian Premier League"

    def test_unknown_passes_through(self) -> None:
        # Tanınmayan ad olduğu gibi (trim) döner
        assert canonical_league_name("Romanian Liga 1") == "Romanian Liga 1"
        assert canonical_league_name("  Some League  ") == "Some League"

    def test_empty_returns_empty(self) -> None:
        assert canonical_league_name("") == ""
        assert canonical_league_name(None) == ""

    def test_case_insensitive_lookup(self) -> None:
        assert canonical_league_name("EPL") == "English Premier League"
        assert canonical_league_name("epl") == "English Premier League"
        assert canonical_league_name("ePl") == "English Premier League"


def test_match_league_name_single_source():
    from app.analysis.league_filter import match_league_name
    assert match_league_name("ENG PR", "") == "English Premier League"
    assert match_league_name("", "English Premier League") == "English Premier League"
    assert match_league_name(None, "TUR D1") == canonical_league_name("TUR D1")
    assert match_league_name(None, None) == ""


# Sprint 94 F4: "champions" alt dizesi "Championship"i kupa saymamalı
import pytest as _pytest  # noqa: E402

from app.analysis.league_filter import is_supported_league as _supported  # noqa: E402


@_pytest.mark.parametrize("name", ["Scottish Championship", "USL Championship", "Welsh Championship",
                                   "Northern Ireland Championship", "English Championship"])
def test_championship_leagues_are_not_cups(name):
    assert _supported(name)


@_pytest.mark.parametrize("name", ["UEFA Champions League", "AFC Champions", "CONCACAF Champions Cup",
                                   "Champions League Qualification"])
def test_champions_competitions_still_rejected(name):
    assert not _supported(name)


# Sprint 94 F7: kaynakta görülen (H2H kısa kodu, satır başlığı = bülten adı) çiftleri (29 Ekim örneklemi).
# Takip edilen ve aday (K16) liglerde ikisi aynı kanonik ada gitmeli — yoksa DB'de aynı lig iki adla yazılır,
# lig süzgeci yarım kalır (arşiv, takım gücü, ortalama).
SOURCE_LEAGUE_PAIRS = [
    ("ENG PR", "English Premier League"), ("SPA D1", "Spanish La Liga"), ("ITA D1", "Italy Serie A"),
    ("GER D1", "German Bundesliga"), ("FRA D1", "France Ligue 1"), ("TUR D1", "Turkey Super Lig"),
    ("HOL D1", "Holland Eredivisie"), ("ENG LCH", "England Championship"), ("GER D2", "German Bundesliga 2"),
    ("POR D1", "Liga Portugal 1"), ("BEL D1", "Belgian Pro League"), ("SCO PR", "Scottish Premiership"),
    ("ENG L1", "England League 1"), ("ENG L2", "England League 2"), ("SPA D2", "Spanish La Liga 2"),
    ("TFF 1. Lig", "Turkey 1. Lig"), ("HOL D2", "Holland Eerste Divisie"), ("POL PR", "Poland Ekstraklasa"),
    ("CZE D1", "Czech Republic Gambrinus Liga"), ("GRE D1", "Greece Super League A"),
]


@pytest.mark.parametrize("code,title", SOURCE_LEAGUE_PAIRS)
def test_short_code_and_bulletin_name_share_canonical(code, title):
    from app.analysis.league_filter import match_league_name

    assert canonical_league_name(code) == canonical_league_name(title)
    assert match_league_name(code, title) == match_league_name(None, title)


def test_tracked_leagues_recognised_from_bulletin_name():
    from app.analysis.league_filter import is_tracked_league

    for _code, title in SOURCE_LEAGUE_PAIRS[:12]:
        assert is_tracked_league(title), title
