"use client";

import { useMemo } from "react";
import type { PatternResult } from "@/lib/types";
import type { Period } from "@/lib/labels";
import { buildPicks, getTopPicks, confidenceTier, type Pick, type ConfidenceTier } from "@/lib/confidence";

interface Props {
  patternB: PatternResult | null;
  patternC: PatternResult | null;
  period: Period;
}

function tierStyle(tier: ConfidenceTier) {
  if (tier === "high") {
    return {
      bg: "#062618",
      border: "#16a34a",
      pillBg: "#16a34a",
      pillText: "#ecfdf5",
      labelText: "#bbf7d0",
      pctText: "#dcfce7",
    };
  }
  if (tier === "medium") {
    return {
      bg: "#0a1f17",
      border: "#15803d",
      pillBg: "#0f1f17",
      pillText: "#86efac",
      labelText: "#86efac",
      pctText: "#bbf7d0",
    };
  }
  return {
    bg: "#0f1625",
    border: "#1e293b",
    pillBg: "#0f1625",
    pillText: "#94a3b8",
    labelText: "#94a3b8",
    pctText: "#cbd5e1",
  };
}

function ArchiveBadge({ archive }: { archive: "A" | "B" | "AB" }) {
  const both = archive === "AB";
  const text = archive === "AB" ? "1+2" : archive === "A" ? "Arş.1" : "Arş.2";
  return (
    <span
      className="text-[9px] font-bold px-1.5 py-0.5 rounded font-mono tracking-tight"
      style={{
        backgroundColor: both ? "#1c1303" : "#0f172a",
        color: both ? "#fbbf24" : archive === "A" ? "#4ade80" : "#c084fc",
        border: `1px solid ${both ? "#92400e" : archive === "A" ? "#166534" : "#581c87"}`,
        minWidth: 38,
        textAlign: "center",
      }}
      title={
        both
          ? "Her iki arşivde de yüksek (≥%65) — güçlü tutarlılık"
          : archive === "A"
            ? "Sadece Arşiv 1 (Skor Seti) doğruluyor"
            : "Sadece Arşiv 2 (Oran Benzerliği) doğruluyor"
      }
    >
      {text}
    </span>
  );
}

function PickRow({ pick }: { pick: Pick }) {
  const tier = confidenceTier(pick.confidence);
  const s = tierStyle(tier);
  const pct = Math.round(pick.pct);
  return (
    <div
      className="flex items-center gap-2 px-2.5 py-2 rounded-lg border"
      style={{ backgroundColor: s.bg, borderColor: s.border }}
    >
      <ArchiveBadge archive={pick.archive} />
      <div className="flex-1 min-w-0">
        <div className="text-[10px] uppercase tracking-wider truncate" style={{ color: "#475569" }}>
          {pick.marketLabel}
        </div>
        <div className="text-sm font-semibold truncate" style={{ color: s.labelText }}>
          {pick.selectionLabel}
        </div>
      </div>
      <div className="flex flex-col items-end flex-shrink-0">
        <div className="text-base font-extrabold font-mono leading-none" style={{ color: s.pctText }}>
          %{pct}
        </div>
        {pick.archive === "AB" && pick.pctA !== null && pick.pctB !== null && (
          <div className="text-[9px] font-mono mt-0.5" style={{ color: "#475569" }}>
            {Math.round(pick.pctA)} · {Math.round(pick.pctB)}
          </div>
        )}
      </div>
    </div>
  );
}

export default function TopPicks({ patternB, patternC, period }: Props) {
  const { picks, effectiveMinPct, matchCount: totalMatches } = useMemo(
    () => getTopPicks(buildPicks(patternB, patternC, period), { limit: 8 }),
    [patternB, patternC, period],
  );

  if (picks.length === 0) {
    return (
      <div
        className="rounded-xl p-4 border"
        style={{ backgroundColor: "#0a0d14", borderColor: "#1e293b" }}
      >
        <div className="flex items-center gap-2 mb-1">
          <span style={{ color: "#475569" }}>⭐</span>
          <h3 className="text-sm font-bold tracking-wide" style={{ color: "#94a3b8" }}>
            Önerilen Bahisler
          </h3>
        </div>
        <p className="text-xs" style={{ color: "#475569" }}>
          Bu periyot için yeterince güvenli tahmin bulunmuyor. Aşağıdaki ana pazar özetini ve detaylı analizi inceleyebilirsiniz.
        </p>
      </div>
    );
  }

  return (
    <div
      className="rounded-xl p-4 border space-y-3"
      style={{
        backgroundColor: "#0a1410",
        borderColor: "#15803d",
        boxShadow: "0 0 20px rgba(22,163,74,0.08)",
      }}
    >
      {/* Başlık */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <span className="text-base">⭐</span>
          <h3 className="text-sm font-bold tracking-wide" style={{ color: "#86efac" }}>
            Önerilen Bahisler
          </h3>
          <span
            className="text-[10px] px-1.5 py-0.5 rounded font-mono"
            style={{ backgroundColor: "#0a1f17", color: "#4ade80" }}
          >
            {picks.length}
          </span>
        </div>
        <span
          className="text-[10px] font-mono"
          style={{ color: "#475569" }}
          title="Eşleşme sayısı arttıkça istatistiksel güven artar; düşük örneklemde daha yüksek yüzde eşiği uygulanır."
        >
          ⛁ {totalMatches} maç · Eşik: ≥%{Math.round(effectiveMinPct)}
        </span>
      </div>

      {/* Pick listesi */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {picks.map((p) => (
          <PickRow key={`${p.marketKey}-${p.selectionLabel}`} pick={p} />
        ))}
      </div>

      <p className="text-[10px] leading-snug" style={{ color: "#475569" }}>
        <span style={{ color: "#fbbf24" }}>1+2</span> rozeti = her iki arşivde de yüksek tutarlılık.{" "}
        <span style={{ color: "#4ade80" }}>Arş.1</span>/<span style={{ color: "#c084fc" }}>Arş.2</span> = tek arşivde geçerli.
      </p>
    </div>
  );
}
