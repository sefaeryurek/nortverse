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
        # league_name kupa ama league_code (kanonik) bilinen lig
        assert is_supported_league("UEFA Cup", "English Premier League") is True
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
