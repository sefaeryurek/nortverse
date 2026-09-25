"use client";

import { useMemo } from "react";
import type { PatternResult } from "@/lib/types";
import type { Period } from "@/lib/labels";
import { buildPicks, getTopPicks } from "@/lib/confidence";
import { generateCombos, comboTierLabel, comboTierAccent, type Combo } from "@/lib/combos";
import { useMatchInfo } from "@/lib/match-context";
import { useCart } from "@/lib/cart";

interface Props {
  patternB: PatternResult | null;
  patternC: PatternResult | null;
  period: Period;
}

function ComboCard({ combo, period }: { combo: Combo; period: Period }) {
  const accent = comboTierAccent(combo.tier);
  const tierLabel = comboTierLabel(combo.tier);
  const match = useMatchInfo();
  const { addItem } = useCart();

  const addAllLegs = () => {
    if (!match) return;
    for (const leg of combo.legs) {
      addItem({
        matchId: match.matchId,
        homeTeam: match.homeTeam,
        awayTeam: match.awayTeam,
        marketKey: leg.marketKey,
        marketLabel: leg.marketLabel,
        selectionLabel: leg.selectionLabel,
        pct: leg.pct,
        archive: leg.archive,
        period,
      });
    }
  };

  return (
    <div
      className="nv-card flex flex-col"
      style={{
        borderRadius: "var(--nv-radius-lg)",
        borderTop: `3px solid ${accent.color}`,
        padding: "var(--nv-space-md)",
      }}
    >
      {/* Baslik */}
      <div className="flex items-center justify-between mb-2">
        <span
          className="nv-badge"
          style={{ backgroundColor: accent.bg, color: accent.color }}
        >
          {tierLabel}
        </span>
        <span
          className="text-[10px]"
          style={{
            fontFamily: "var(--nv-font-mono)",
            color: "var(--nv-text-tertiary)",
          }}
        >
          {combo.legs.length} seçim
        </span>
      </div>

      {/* Leg listesi */}
      <div className="space-y-1.5 flex-1">
        {combo.legs.map((leg) => (
          <div
            key={`${leg.marketKey}-${leg.selectionLabel}`}
            className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs"
            style={{
              backgroundColor: "var(--nv-bg-surface)",
              borderRadius: "var(--nv-radius-md)",
            }}
          >
            <div className="flex-1 min-w-0">
              <span
                className="text-[9px] uppercase block truncate"
                style={{
                  color: "var(--nv-text-tertiary)",
                  letterSpacing: "var(--nv-tracking-wide)",
                }}
              >
                {leg.marketLabel}
              </span>
              <span
                className="font-semibold block truncate"
                style={{ color: "var(--nv-text-primary)" }}
              >
                {leg.selectionLabel}
              </span>
            </div>
            <span
              className="font-bold flex-shrink-0"
              style={{
                fontFamily: "var(--nv-font-mono)",
                color: accent.color,
              }}
            >
              %{Math.round(leg.pct)}
            </span>
          </div>
        ))}
      </div>

      {match && (
        <button
          onClick={addAllLegs}
          className="w-full text-xs py-2 mt-3 font-semibold transition-all"
          style={{
            backgroundColor: "var(--nv-accent-green-dim)",
            color: "var(--nv-accent-green)",
            border: "1px solid var(--nv-accent-green)",
            borderRadius: "var(--nv-radius-md)",
            transitionDuration: "var(--nv-duration-normal)",
            transitionTimingFunction: "var(--nv-ease)",
          }}
        >
          <svg className="w-3.5 h-3.5 inline-block mr-1 -mt-0.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 5v14m-7-7h14" />
          </svg>
          Sepete Ekle ({combo.legs.length} seçim)
        </button>
      )}
    </div>
  );
}

export default function ComboSuggestion({ patternB, patternC, period }: Props) {
  const combos = useMemo(() => {
    const picks = getTopPicks(buildPicks(patternB, patternC, period)).picks;
    return generateCombos(picks);
  }, [patternB, patternC, period]);

  if (combos.length === 0) return null;

  return (
    <div className="nv-card nv-fade-in" style={{ borderRadius: "var(--nv-radius-lg)", padding: "var(--nv-space-lg)" }}>
      {/* Baslik */}
      <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
        <div className="flex items-center gap-2">
          <h3
            className="text-sm font-bold"
            style={{
              color: "var(--nv-text-primary)",
              letterSpacing: "var(--nv-tracking-wide)",
            }}
          >
            Birlikte Değerlendirilebilen Seçimler
          </h3>
          <span className="nv-badge" style={{ backgroundColor: "var(--nv-bg-elevated)", color: "var(--nv-text-secondary)" }}>
            {combos.length}
          </span>
        </div>
        <span className="text-[10px]" style={{ color: "var(--nv-text-tertiary)" }}>
          Bu maçın tahminlerinden oluşturulan seçimler
        </span>
      </div>

      {/* Kombo kartlari */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {combos.map((c) => (
          <ComboCard key={c.tier} combo={c} period={period} />
        ))}
      </div>

      <p
        className="text-[10px] leading-snug mt-3"
        style={{ color: "var(--nv-text-tertiary)" }}
      >
        Aynı maçın seçimleri bağımsız değildir; birlikte gerçekleşme oranı için doğrulanmış bir tahmin sunulmuyor.
      </p>
    </div>
  );
}
