"""Pazar kataloğu — frontend `lib/confidence.ts` MARKETS tanımının Python karşılığı.

Her pazar seçimi bir PatternResult alanına ve kanonik bir seçim koduna bağlanır.
Defter (`prediction_ledger.market/selection`) bu anahtar ve kodları kullanır.
"""

from __future__ import annotations

from dataclasses import dataclass

PERIODS = ("ht", "h2", "ft")


@dataclass(frozen=True)
class MarketSpec:
    key: str
    fields: tuple[tuple[str, str], ...]  # (PatternResult alanı, seçim kodu)
    ft_only: bool = False
    exclude_periods: tuple[str, ...] = ()

    def active_in(self, period: str) -> bool:
        if self.ft_only and period != "ft":
            return False
        return period not in self.exclude_periods

    def field_for(self, selection: str) -> str | None:
        return next((field for field, code in self.fields if code == selection), None)


_NO_HT_H2 = ("ht", "h2")

MARKETS: tuple[MarketSpec, ...] = (
    MarketSpec("result", (("result_1_pct", "1"), ("result_x_pct", "X"), ("result_2_pct", "2"))),
    MarketSpec("dc", (("dc_1x_pct", "1X"), ("dc_x2_pct", "X2"), ("dc_12_pct", "12"))),
    MarketSpec("ou_25", (("alt_25_pct", "under"), ("ust_25_pct", "over")), exclude_periods=_NO_HT_H2),
    MarketSpec("kg", (("kg_var_pct", "yes"), ("kg_yok_pct", "no"))),
    MarketSpec("iy_ms", tuple(
        (f"iy_ms_{a}{b}_pct", f"{a.upper()}/{b.upper()}") for a in "1x2" for b in "1x2"
    ), ft_only=True),
    MarketSpec("hnd_a10", (("hnd_a10_1_pct", "1"), ("hnd_a10_x_pct", "X"), ("hnd_a10_2_pct", "2")),
               exclude_periods=_NO_HT_H2),
    MarketSpec("hnd_h10", (("hnd_h10_1_pct", "1"), ("hnd_h10_x_pct", "X"), ("hnd_h10_2_pct", "2")),
               exclude_periods=_NO_HT_H2),
    MarketSpec("ms_25_combo", tuple(
        (f"ms{r}_{ou}25_pct", f"{r.upper()}_{code}")
        for r in "1x2" for ou, code in (("alt", "under"), ("ust", "over"))
    ), exclude_periods=_NO_HT_H2),
    MarketSpec("ms_15_combo", tuple(
        (f"ms{r}_{ou}15_pct", f"{r.upper()}_{code}")
        for r in "1x2" for ou, code in (("alt", "under"), ("ust", "over"))
    )),
    MarketSpec("ms_kg_combo", tuple(
        (f"ms{r}_kg_{kg}_pct", f"{r.upper()}_{code}")
        for r in "1x2" for kg, code in (("var", "yes"), ("yok", "no"))
    )),
    MarketSpec("fark", (
        ("fark_ev1_pct", "h1"), ("fark_ev2_pct", "h2"), ("fark_ev3p_pct", "h3p"),
        ("fark_ber_pct", "d"),
        ("fark_dep1_pct", "a1"), ("fark_dep2_pct", "a2"), ("fark_dep3p_pct", "a3p"),
    )),
    MarketSpec("ou_15", (("alt_15_pct", "under"), ("ust_15_pct", "over"))),
    MarketSpec("ou_35", (("alt_35_pct", "under"), ("ust_35_pct", "over")), exclude_periods=_NO_HT_H2),
    MarketSpec("ev_05", (("ev_alt_05_pct", "under"), ("ev_ust_05_pct", "over"))),
    MarketSpec("ev_15", (("ev_alt_15_pct", "under"), ("ev_ust_15_pct", "over"))),
    MarketSpec("ev_25", (("ev_alt_25_pct", "under"), ("ev_ust_25_pct", "over")), exclude_periods=_NO_HT_H2),
    MarketSpec("dep_05", (("dep_alt_05_pct", "under"), ("dep_ust_05_pct", "over"))),
    MarketSpec("dep_15", (("dep_alt_15_pct", "under"), ("dep_ust_15_pct", "over"))),
    MarketSpec("dep_25", (("dep_alt_25_pct", "under"), ("dep_ust_25_pct", "over")), exclude_periods=_NO_HT_H2),
    MarketSpec("iy_05", (("iy_alt_05_pct", "under"), ("iy_ust_05_pct", "over")), ft_only=True),
    MarketSpec("iy_15", (("iy_alt_15_pct", "under"), ("iy_ust_15_pct", "over")), ft_only=True),
    MarketSpec("iki_yari_15", (("iki_yari_alt15_pct", "under"), ("iki_yari_ust15_pct", "over")), ft_only=True),
    MarketSpec("ht_result", (("ht_result_1_pct", "1"), ("ht_result_x_pct", "X"), ("ht_result_2_pct", "2")),
               ft_only=True),
    MarketSpec("ht_dc", (("ht_dc_1x_pct", "1X"), ("ht_dc_x2_pct", "X2"), ("ht_dc_12_pct", "12")), ft_only=True),
    MarketSpec("h2_result", (("h2_result_1_pct", "1"), ("h2_result_x_pct", "X"), ("h2_result_2_pct", "2")),
               ft_only=True),
    MarketSpec("ht_kg", (("ht_kg_var_pct", "yes"), ("ht_kg_yok_pct", "no")), ft_only=True),
    MarketSpec("h2_kg", (("h2_kg_var_pct", "yes"), ("h2_kg_yok_pct", "no")), ft_only=True),
    MarketSpec("gol_aralik", (
        ("gol_01_pct", "0-1"), ("gol_23_pct", "2-3"), ("gol_45_pct", "4-5"), ("gol_6p_pct", "6+"),
    )),
    MarketSpec("encok_yari", (
        ("encok_gol_1y_pct", "1h"), ("encok_gol_esit_pct", "eq"), ("encok_gol_2y_pct", "2h"),
    ), ft_only=True),
    MarketSpec("hnd_a20", (("hnd_a20_1_pct", "1"), ("hnd_a20_x_pct", "X"), ("hnd_a20_2_pct", "2")),
               exclude_periods=_NO_HT_H2),
    MarketSpec("hnd_h20", (("hnd_h20_1_pct", "1"), ("hnd_h20_x_pct", "X"), ("hnd_h20_2_pct", "2")),
               exclude_periods=_NO_HT_H2),
)

# Sadece canlı İY arşiv görünümünde (2. yarı gol var/yok): frontend MARKETS'te yok, eski kayıtlarda alan 0.
LIVE_ONLY_MARKETS: tuple[MarketSpec, ...] = (
    MarketSpec("ou_05", (("alt_05_pct", "under"), ("ust_05_pct", "over"))),
)

MARKETS_BY_KEY: dict[str, MarketSpec] = {m.key: m for m in MARKETS + LIVE_ONLY_MARKETS}

# Ana Pazar Özeti'nde gösterilen pazarlar (confidence.ts SUMMARY_MARKET_KEYS ile aynı sıra).
SUMMARY_MARKET_KEYS: tuple[str, ...] = (
    "result", "dc", "ou_25", "kg", "iy_ms", "hnd_a10", "hnd_h10", "ms_25_combo", "fark",
)


def get_market(key: str) -> MarketSpec:
    try:
        return MARKETS_BY_KEY[key]
    except KeyError:
        raise ValueError(f"Bilinmeyen pazar: {key}") from None
