"use client";

import { useMemo } from "react";
import type { PatternResult } from "@/lib/types";
import type { Period } from "@/lib/labels";
import { getMarketSummary } from "@/lib/confidence";
import { useMatchInfo } from "@/lib/match-context";
import AddToCartButton from "./AddToCartButton";

interface Props {
  patternB: PatternResult | null;
  patternC: PatternResult | null;
  period: Period;
}

function pctTone(pct: number): { color: string; muted: boolean } {
  if (pct >= 75) return { color: "#86efac", muted: false };
  if (pct >= 60) return { color: "#cbd5e1", muted: false };
  if (pct >= 50) return { color: "#94a3b8", muted: false };
  return { color: "#475569", muted: true };
}

function Cell({
  value,
  accent,
  marketKey,
  marketLabel,
  archive,
  period,
}: {
  value: { selectionLabel: string; pct: number } | null;
  accent: string;
  marketKey: string;
  marketLabel: string;
  archive: "A" | "B";
  period: Period;
}) {
  const match = useMatchInfo();
  if (!value) {
    return (
      <div className="text-xs text-center font-mono" style={{ color: "#334155" }}>
        —
      </div>
    );
  }
  const pct = Math.round(value.pct);
  const { color, muted } = pctTone(pct);
  return (
    <div className="flex items-center justify-end gap-2" style={{ opacity: muted ? 0.55 : 1 }}>
      <span className="text-[11px] truncate" style={{ color }}>
        {value.selectionLabel}
      </span>
      <span
        className="text-xs font-extrabold font-mono px-1.5 py-0.5 rounded"
        style={{ backgroundColor: "#0f172a", color, borderLeft: `2px solid ${accent}` }}
      >
        %{pct}
      </span>
      {match && pct >= 60 && (
        <AddToCartButton
          item={{
            matchId: match.matchId,
            homeTeam: match.homeTeam,
            awayTeam: match.awayTeam,
            marketKey,
            marketLabel,
            selectionLabel: value.selectionLabel,
            pct: value.pct,
            archive,
            period,
          }}
        />
      )}
    </div>
  );
}

export default function MarketSummary({ patternB, patternC, period }: Props) {
  const rows = useMemo(() => getMarketSummary(patternB, patternC, period), [patternB, patternC, period]);

  if (rows.length === 0) return null;

  return (
    <div
      className="rounded-xl p-4 border space-y-2"
      style={{ backgroundColor: "#0f1625", borderColor: "#1e293b" }}
    >
      <div className="flex items-center gap-2 mb-1">
        <span style={{ color: "#64748b" }}>📊</span>
        <h3 className="text-sm font-bold tracking-wide" style={{ color: "#cbd5e1" }}>
          Ana Pazar Özeti
        </h3>
        <span className="text-[10px]" style={{ color: "#475569" }}>her pazarın en olası seçimi</span>
      </div>

      {/* Sütun başlıkları */}
      <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)] gap-2 px-1 pb-1 border-b" style={{ borderColor: "#1e293b" }}>
        <div className="text-[10px] uppercase tracking-wider" style={{ color: "#475569" }}>
          Pazar
        </div>
        <div className="text-[10px] uppercase tracking-wider text-right" style={{ color: "#4ade80" }}>
          Arşiv 1
        </div>
        <div className="text-[10px] uppercase tracking-wider text-right" style={{ color: "#c084fc" }}>
          Arşiv 2
        </div>
      </div>

      {/* Satırlar */}
      <div className="space-y-1.5 pt-1">
        {rows.map((row) => (
          <div
            key={row.marketKey}
            className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)] gap-2 items-center"
          >
            <div className="flex items-center gap-1.5 min-w-0">
              {row.agreement && (
                <span
                  className="text-[8px] font-bold leading-none"
                  style={{ color: "#fbbf24" }}
                  title="İki arşiv aynı seçimde uyuşuyor"
                >
                  ✦
                </span>
              )}
              <span className="text-xs truncate" style={{ color: "#94a3b8" }}>
                {row.marketLabel}
              </span>
            </div>
            <Cell
              value={row.winnerA}
              accent="#4ade80"
              marketKey={row.marketKey}
              marketLabel={row.marketLabel}
              archive="A"
              period={period}
            />
            <Cell
              value={row.winnerB}
              accent="#c084fc"
              marketKey={row.marketKey}
              marketLabel={row.marketLabel}
              archive="B"
              period={period}
            />
          </div>
        ))}
      </div>

      <p className="text-[10px] pt-1" style={{ color: "#475569" }}>
        <span style={{ color: "#fbbf24" }}>✦</span> = iki arşiv aynı seçimde uyuştu (güçlü sinyal).
      </p>
    </div>
  );
}
