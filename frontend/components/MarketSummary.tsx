"use client";

import { useEffect, useId, useMemo, useState } from "react";
import type { PatternResult } from "@/lib/types";
import type { Period } from "@/lib/labels";
import { getMarketSummary } from "@/lib/confidence";
import type { MarketSummaryWinner } from "@/lib/confidence";
import { getPerformanceSummary } from "@/lib/api";
import type { PerformanceStats } from "@/lib/api";
import { useLocale } from "@/lib/locale-context";
import { localizeLabel } from "@/lib/label-i18n";

interface Props {
  patternB: PatternResult | null;
  patternC: PatternResult | null;
  patternD: PatternResult | null;
  period: Period;
}

/**
 * Ana Pazar Özeti — arşivde en sık görülen seçim (Sprint 94 H1, K7).
 * Sıklık olasılık değildir: geçmişte gösterilen %54,5 → gerçekleşen %48,1 çıktı. Bu yüzden hücre "7/13" (sayı/örneklem)
 * olarak gösterilir, yüzde ikincil; yeşil ton ve dolu çubuk yok; tablo varsayılan kapalı; başlıkta gerçek karne.
 */
function Cell({ value, accent }: { value: MarketSummaryWinner | null; accent: string }) {
  const { locale } = useLocale();
  if (!value) {
    return <div className="text-xs text-center" style={{ color: "var(--nv-text-tertiary)", fontFamily: "var(--nv-font-mono)" }}>—</div>;
  }
  return (
    <div className="flex flex-col items-end gap-0.5 min-w-0">
      <span className="text-[11px] truncate min-w-0 max-w-full" style={{ color: "var(--nv-text-secondary)" }}>
        {localizeLabel(value.selectionLabel, locale)}
      </span>
      <span className="text-xs font-semibold px-1.5" style={{
        fontFamily: "var(--nv-font-mono)", color: "var(--nv-text-primary)", borderLeft: `2px solid ${accent}`,
      }}>
        {value.count}/{value.n}
        <span className="ml-1 font-normal" style={{ color: "var(--nv-text-tertiary)" }}>%{Math.round(value.pct)}</span>
      </span>
    </div>
  );
}

export default function MarketSummary({ patternB, patternC, patternD, period }: Props) {
  const { t, locale } = useLocale();
  const ms = t.marketSummary;
  const [open, setOpen] = useState(false);
  const [record, setRecord] = useState<PerformanceStats | null>(null);
  const panelId = useId();
  const rows = useMemo(() => getMarketSummary(patternB, patternC, period, patternD), [patternB, patternC, patternD, period]);

  useEffect(() => {
    let cancelled = false;
    getPerformanceSummary("market_summary", "market")
      .then((s) => { if (!cancelled) setRecord(s.overall); })
      .catch(() => { /* karne yoksa rozet gösterilmez */ });
    return () => { cancelled = true; };
  }, []);

  if (rows.length === 0) return null;
  const fmt = (v: number) => (locale === "en" ? v.toFixed(1) : v.toFixed(1).replace(".", ","));

  return (
    <div className="nv-card nv-fade-in" style={{ borderRadius: "var(--nv-radius-lg)", padding: "var(--nv-space-lg)" }}>
      <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-controls={panelId}
        className="flex w-full flex-wrap items-center gap-2 text-left">
        <span aria-hidden="true" style={{ color: "var(--nv-text-tertiary)" }}>{open ? "▾" : "▸"}</span>
        <h3 className="text-sm font-bold" style={{ color: "var(--nv-text-primary)", letterSpacing: "var(--nv-tracking-wide)" }}>
          {ms.title}
        </h3>
        <span className="nv-badge" style={{ backgroundColor: "var(--nv-bg-elevated)", color: "var(--nv-text-tertiary)" }}>
          {ms.subtitle}
        </span>
        {record && record.avg_prob_pct != null && record.hit_pct != null && record.resolved > 0 && (
          <span className="nv-badge" style={{ backgroundColor: "var(--nv-bg-elevated)", color: "var(--nv-accent-amber)" }}
            title={ms.recordTooltip}>
            {ms.record.replace("{shown}", fmt(record.avg_prob_pct)).replace("{actual}", fmt(record.hit_pct))
              .replace("{n}", String(record.resolved))}
          </span>
        )}
      </button>

      {open && (
        <div id={panelId} className="mt-3">
          <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)] gap-2 px-1 pb-2 mb-2"
            style={{ borderBottom: "1px solid var(--nv-border)" }}>
            <div className="text-[10px] uppercase" style={{ color: "var(--nv-text-tertiary)", letterSpacing: "var(--nv-tracking-wide)" }}>
              {ms.market}
            </div>
            <div className="text-[10px] uppercase text-right" style={{ color: "var(--nv-accent-blue)" }}>A1 · {patternB ? patternB.match_count : "—"}</div>
            <div className="text-[10px] uppercase text-right" style={{ color: "var(--nv-accent-green)" }}>A2 · {patternC ? patternC.match_count : "—"}</div>
            <div className="text-[10px] uppercase text-right" style={{ color: "var(--nv-accent-amber)" }}>A3 · {patternD ? patternD.match_count : "—"}</div>
          </div>
          <p className="text-[10px] px-1 pb-2" style={{ color: "var(--nv-text-tertiary)" }}>{ms.frequencyCaption}</p>

          <div className="space-y-2">
            {rows.map((row) => (
              <div key={row.marketKey}
                className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)] gap-2 items-center py-1 px-1 rounded-lg"
                style={{ opacity: row.informational ? 0.55 : 1 }}>
                <div className="flex items-center gap-1.5 min-w-0">
                  {row.agreement && (
                    <span className="text-[9px] font-bold leading-none flex-shrink-0" style={{ color: "var(--nv-text-secondary)" }}
                      title={ms.agreementTooltip.replace("{n}", String(row.agreementCount))}>
                      <span aria-hidden="true">✦</span>{row.agreementCount}
                      <span className="sr-only">{ms.agreementTooltip.replace("{n}", String(row.agreementCount))}</span>
                    </span>
                  )}
                  <span className="min-w-0">
                    <span className="text-xs truncate block" style={{ color: "var(--nv-text-secondary)" }}>
                      {localizeLabel(row.marketLabel, locale)}
                    </span>
                    {row.informational && (
                      <span className="text-[9px] block" style={{ color: "var(--nv-text-tertiary)" }}>{ms.informational}</span>
                    )}
                  </span>
                </div>
                <Cell value={row.winnerA1} accent="var(--nv-accent-blue)" />
                <Cell value={row.winnerA2} accent="var(--nv-accent-green)" />
                <Cell value={row.winnerA3} accent="var(--nv-accent-amber)" />
              </div>
            ))}
          </div>

          <p className="text-[10px] pt-2 mt-2" style={{ color: "var(--nv-text-tertiary)", borderTop: "1px solid var(--nv-border-subtle)" }}>
            <span aria-hidden="true" style={{ color: "var(--nv-text-primary)" }}>✦</span> = {ms.footer}
          </p>
        </div>
      )}
    </div>
  );
}
