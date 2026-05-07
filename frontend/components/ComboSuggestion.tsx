"use client";

import { useMemo } from "react";
import type { PatternResult } from "@/lib/types";
import type { Period } from "@/lib/labels";
import { buildPicks } from "@/lib/confidence";
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
  const probPct = (combo.jointProb * 100).toFixed(1);
  const odds = combo.estDecimalOdds.toFixed(2);
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
      className="rounded-xl p-3 border space-y-2 flex flex-col"
      style={{ backgroundColor: accent.bg, borderColor: accent.border }}
    >
      {/* Başlık */}
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-bold tracking-wide uppercase" style={{ color: accent.color }}>
          {tierLabel}
        </h4>
        <span className="text-[10px] font-mono" style={{ color: accent.color, opacity: 0.7 }}>
          {combo.legs.length} maç
        </span>
      </div>

      {/* Leg listesi */}
      <div className="space-y-1 flex-1">
        {combo.legs.map((leg) => (
          <div
            key={`${leg.marketKey}-${leg.selectionLabel}`}
            className="flex items-center gap-2 px-2 py-1 rounded text-xs"
            style={{ backgroundColor: "#0a0f17" }}
          >
            <span className="flex-1 min-w-0 truncate" style={{ color: "#cbd5e1" }}>
              <span className="text-[9px] uppercase tracking-wider" style={{ color: "#475569" }}>
                {leg.marketLabel}
              </span>
              <br />
              <span className="font-semibold">{leg.selectionLabel}</span>
            </span>
            <span className="font-mono font-bold flex-shrink-0" style={{ color: accent.color }}>
              %{Math.round(leg.pct)}
            </span>
          </div>
        ))}
      </div>

      {/* Özet */}
      <div
        className="grid grid-cols-2 gap-2 pt-2 border-t"
        style={{ borderColor: accent.border }}
      >
        <div className="text-center">
          <div className="text-[9px] uppercase tracking-wider" style={{ color: "#475569" }}>
            Olasılık
          </div>
          <div className="text-sm font-bold font-mono" style={{ color: accent.color }}>
            ≈%{probPct}
          </div>
        </div>
        <div className="text-center">
          <div className="text-[9px] uppercase tracking-wider" style={{ color: "#475569" }}>
            Tahmini Oran
          </div>
          <div className="text-sm font-bold font-mono" style={{ color: accent.color }}>
            ≈{odds}
          </div>
        </div>
      </div>

      {/* Sepete ekle (tüm leg'ler) */}
      {match && (
        <button
          onClick={addAllLegs}
          className="w-full text-xs py-1.5 rounded-lg font-semibold transition-colors hover:opacity-80"
          style={{
            backgroundColor: "#0a0f17",
            color: accent.color,
            border: `1px solid ${accent.border}`,
          }}
        >
          + Sepete Ekle ({combo.legs.length} maç)
        </button>
      )}
    </div>
  );
}

export default function ComboSuggestion({ patternB, patternC, period }: Props) {
  const combos = useMemo(() => {
    const picks = buildPicks(patternB, patternC, period);
    return generateCombos(picks);
  }, [patternB, patternC, period]);

  if (combos.length === 0) return null;

  return (
    <div
      className="rounded-xl p-4 border space-y-3"
      style={{ backgroundColor: "#0a0f1a", borderColor: "#1e293b" }}
    >
      {/* Başlık */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <span className="text-base">🎯</span>
          <h3 className="text-sm font-bold tracking-wide" style={{ color: "#cbd5e1" }}>
            Önerilen Kuponlar
          </h3>
          <span
            className="text-[10px] px-1.5 py-0.5 rounded font-mono"
            style={{ backgroundColor: "#1e293b", color: "#94a3b8" }}
          >
            {combos.length}
          </span>
        </div>
        <span className="text-[10px]" style={{ color: "#475569" }}>
          Top Picks tahminlerinden otomatik kombine
        </span>
      </div>

      {/* Kombo kartları */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {combos.map((c) => (
          <ComboCard key={c.tier} combo={c} period={period} />
        ))}
      </div>

      <p className="text-[10px] leading-snug" style={{ color: "#475569" }}>
        Olasılık ve oran <span style={{ color: "#94a3b8" }}>≈ yaklaşık</span> hesaplanmıştır
        (her tahmin bağımsız varsayımıyla). Gerçek iddaa oranları farklı olabilir.
      </p>
    </div>
  );
}
