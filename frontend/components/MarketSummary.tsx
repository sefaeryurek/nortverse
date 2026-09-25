"use client";

import { useMemo } from "react";
import type { PatternResult } from "@/lib/types";
import type { Period } from "@/lib/labels";
import { getMarketSummary } from "@/lib/confidence";

interface Props {
  patternB: PatternResult | null;
  patternC: PatternResult | null;
  period: Period;
}

function pctTone(pct: number): { color: string; opacity: number } {
  if (pct >= 75) return { color: "var(--nv-accent-green)", opacity: 1 };
  if (pct >= 60) return { color: "var(--nv-text-primary)", opacity: 1 };
  if (pct >= 50) return { color: "var(--nv-text-secondary)", opacity: 1 };
  return { color: "var(--nv-text-tertiary)", opacity: 0.6 };
}

function Cell({
  value,
  accent,
}: {
  value: { selectionLabel: string; pct: number } | null;
  accent: string;
}) {
  if (!value) {
    return (
      <div
        className="text-xs text-center"
        style={{ color: "var(--nv-text-tertiary)", fontFamily: "var(--nv-font-mono)" }}
      >
        —
      </div>
    );
  }
  const pct = Math.round(value.pct);
  const { color, opacity } = pctTone(pct);
  return (
    <div className="flex flex-col items-end gap-1" style={{ opacity }}>
      <div className="flex items-center gap-2">
        <span className="text-[11px] truncate" style={{ color }}>
          {value.selectionLabel}
        </span>
        <span
          className="text-xs font-extrabold px-1.5 py-0.5"
          style={{
            fontFamily: "var(--nv-font-mono)",
            backgroundColor: "var(--nv-bg-elevated)",
            color,
            borderLeft: `2px solid ${accent}`,
            borderRadius: "var(--nv-radius-sm)",
          }}
        >
          %{pct}
        </span>
      </div>
      {/* Mini pct bar */}
      <div className="nv-pct-bar w-full" style={{ height: "3px" }}>
        <div
          className="nv-pct-bar-fill"
          style={{ width: `${pct}%`, backgroundColor: accent }}
        />
      </div>
    </div>
  );
}

export default function MarketSummary({ patternB, patternC, period }: Props) {
  const rows = useMemo(() => getMarketSummary(patternB, patternC, period), [patternB, patternC, period]);

  if (rows.length === 0) return null;

  return (
    <div
      className="nv-card nv-fade-in"
      style={{
        borderRadius: "var(--nv-radius-lg)",
        padding: "var(--nv-space-lg)",
      }}
    >
      <div className="flex items-center gap-2 mb-3">
        <span style={{ color: "var(--nv-text-tertiary)" }}>📊</span>
        <h3
          className="text-sm font-bold"
          style={{
            color: "var(--nv-text-primary)",
            letterSpacing: "var(--nv-tracking-wide)",
          }}
        >
          Ana Pazar Özeti
        </h3>
        <span className="nv-badge" style={{ backgroundColor: "var(--nv-bg-elevated)", color: "var(--nv-text-tertiary)" }}>
          arşivde en sık görülen seçim
        </span>
      </div>

      {/* Sütun başlıkları */}
      <div
        className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)] gap-2 px-1 pb-2 mb-2"
        style={{ borderBottom: "1px solid var(--nv-border)" }}
      >
        <div
          className="text-[10px] uppercase"
          style={{ color: "var(--nv-text-tertiary)", letterSpacing: "var(--nv-tracking-wide)" }}
        >
          Pazar
        </div>
        <div
          className="text-[10px] uppercase text-right"
          style={{ color: "var(--nv-accent-blue)" }}
        >
          Arşiv 1{patternB ? ` · ${patternB.match_count} maç` : ""}
        </div>
        <div
          className="text-[10px] uppercase text-right"
          style={{ color: "var(--nv-accent-purple)" }}
        >
          Arşiv 2{patternC ? ` · ${patternC.match_count} maç` : ""}
        </div>
      </div>

      {/* Satırlar */}
      <div className="space-y-2">
        {rows.map((row) => (
          <div
            key={row.marketKey}
            className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)] gap-2 items-center py-1 px-1 rounded-lg transition-colors"
            style={{
              backgroundColor: row.agreement ? "var(--nv-accent-amber-dim)" : "transparent",
            }}
          >
            <div className="flex items-center gap-1.5 min-w-0">
              {row.agreement && (
                <span
                  className="text-[8px] font-bold leading-none"
                  style={{ color: "var(--nv-accent-amber)" }}
                  title="İki arşiv aynı seçimde uyuşuyor"
                >
                  ✦
                </span>
              )}
              <span
                className="text-xs truncate"
                style={{ color: "var(--nv-text-secondary)" }}
              >
                {row.marketLabel}
              </span>
            </div>
            <Cell
              value={row.winnerA}
              accent="var(--nv-accent-blue)"
            />
            <Cell
              value={row.winnerB}
              accent="var(--nv-accent-purple)"
            />
          </div>
        ))}
      </div>

      <p
        className="text-[10px] pt-2 mt-2"
        style={{
          color: "var(--nv-text-tertiary)",
          borderTop: "1px solid var(--nv-border-subtle)",
        }}
      >
        <span style={{ color: "var(--nv-accent-amber)" }}>✦</span> = iki arşivde aynı seçim en sık görüldü. Yüzdeler doğrulanmış maç olasılığı değildir.
      </p>
    </div>
  );
}
