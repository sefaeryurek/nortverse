"use client";

import { memo } from "react";
import type { FTRecommendation } from "@/lib/types";
import type { Period } from "@/lib/labels";
import { useMatchInfo } from "@/lib/match-context";
import { useLocale } from "@/lib/locale-context";
import type { Dictionary } from "@/lib/i18n";
import AddToCartButton from "./AddToCartButton";

interface Props {
  recommendations: FTRecommendation[];
  period: Period;
}

function marketLabel(t: Dictionary, market: FTRecommendation["market"]): string {
  return t.markets[market] ?? market;
}

function selectionLabel(t: Dictionary, sel: FTRecommendation["selection"]): string {
  const map: Record<string, string> = {
    "1": t.markets.home, X: t.markets.draw, "2": t.markets.away,
    under: t.markets.under, over: t.markets.over, yes: t.markets.yes, no: t.markets.no,
  };
  return map[sel] ?? sel;
}

const ARCHIVE_NAME: Record<string, string> = {
  archive_1: "A1", archive_2: "A2", archive_3: "A3",
};

function archiveLabel(archive: string): string {
  if (archive.includes("+")) {
    return archive.split("+").map((a) => ARCHIVE_NAME[a] ?? a).join("+");
  }
  return ARCHIVE_NAME[archive] ?? archive;
}

function pctColor(pct: number) {
  if (pct >= 80) return "var(--nv-accent-green)";
  if (pct >= 65) return "var(--nv-accent-blue)";
  if (pct >= 50) return "var(--nv-text-secondary)";
  return "var(--nv-text-tertiary)";
}

function archiveBadgeClass(archive: string) {
  if (archive.includes("+")) return "nv-badge nv-badge-purple";
  if (archive === "archive_1") return "nv-badge nv-badge-blue";
  if (archive === "archive_2") return "nv-badge nv-badge-green";
  return "nv-badge nv-badge-amber";
}

const RecommendationRow = memo(function RecommendationRow({ recommendation }: { recommendation: FTRecommendation }) {
  const match = useMatchInfo();
  const { t } = useLocale();
  const calPct = recommendation.calibrated_pct != null ? Math.round(recommendation.calibrated_pct) : null;
  const pct = calPct ?? Math.round(recommendation.frequency_pct);
  const color = pctColor(pct);
  const archive = archiveLabel(recommendation.archive);
  const mktLabel = marketLabel(t, recommendation.market);
  const selLabel = selectionLabel(t, recommendation.selection);

  return (
    <div
      className="nv-card-interactive flex items-center gap-3"
      style={{
        padding: "var(--nv-space-md)",
        borderRadius: "var(--nv-radius-md)",
      }}
    >
      {/* Confidence ring */}
      <div
        className="nv-conf-ring flex-shrink-0"
        style={{
          "--size": "40px",
          "--stroke": "4px",
          "--pct": pct,
          "--ring-color": color,
        } as React.CSSProperties}
      >
        <span
          className="absolute text-[10px] font-bold"
          style={{
            fontFamily: "var(--nv-font-mono)",
            color: color,
          }}
        >
          {pct}
        </span>
      </div>

      {/* Content */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 mb-0.5 flex-wrap">
          <span className={archiveBadgeClass(recommendation.archive)}>
            {archiveLabel(recommendation.archive)}
          </span>
          {recommendation.is_confident && (
            <span className="nv-badge" style={{
              backgroundColor: "rgba(34,197,94,0.15)",
              color: "var(--nv-accent-green)",
              fontSize: "9px",
              fontWeight: 700,
            }}>
              {t.evaluation.confident}
            </span>
          )}
          <span
            className="text-[10px] uppercase"
            style={{
              color: "var(--nv-text-tertiary)",
              letterSpacing: "var(--nv-tracking-wide)",
            }}
          >
            {mktLabel}
          </span>
        </div>
        <div
          className="text-sm font-semibold"
          style={{ color: "var(--nv-text-primary)" }}
        >
          {selLabel}
        </div>
        {/* Percentage bar */}
        <div className="nv-pct-bar mt-1.5" style={{ height: "4px" }}>
          <div
            className="nv-pct-bar-fill"
            style={{
              width: `${pct}%`,
              backgroundColor: pctColor(pct),
            }}
          />
        </div>
      </div>

      {/* Right side: pct + count + cart */}
      <div className="flex items-center gap-2 flex-shrink-0">
        <div className="text-right">
          <div
            className="text-base font-extrabold leading-none"
            style={{
              fontFamily: "var(--nv-font-mono)",
              color: color,
            }}
          >
            %{pct}
          </div>
          {calPct != null && (
            <div
              className="mt-0.5 text-[9px]"
              style={{
                fontFamily: "var(--nv-font-mono)",
                color: "var(--nv-text-tertiary)",
              }}
              title={t.topPicks.rawPctTooltip}
            >
              {t.topPicks.rawPct.replace("{pct}", String(Math.round(recommendation.frequency_pct)))}
            </div>
          )}
          <div
            className={`${calPct != null ? "" : "mt-0.5 "}text-[9px]`}
            style={{
              fontFamily: "var(--nv-font-mono)",
              color: "var(--nv-text-tertiary)",
            }}
          >
            {recommendation.match_count} {t.common.match}
          </div>
        </div>
        {match && <AddToCartButton item={{
          matchId: match.matchId, homeTeam: match.homeTeam, awayTeam: match.awayTeam,
          marketKey: recommendation.market, marketLabel: mktLabel,
          selectionLabel: selLabel, pct: recommendation.frequency_pct,
          archive, period: "ft",
        }} />}
      </div>
    </div>
  );
});

export default memo(function TopPicks({ recommendations, period }: Props) {
  const { t } = useLocale();
  if (period !== "ft") return null;
  if (recommendations.length === 0) {
    return (
      <div
        className="nv-card nv-fade-in"
        style={{
          borderRadius: "var(--nv-radius-lg)",
          padding: "var(--nv-space-lg)",
        }}
      >
        <h3
          className="text-sm font-bold"
          style={{
            color: "var(--nv-text-secondary)",
            letterSpacing: "var(--nv-tracking-wide)",
          }}
        >
          {t.topPicks.title}
        </h3>
        <p
          className="mt-1 text-xs leading-relaxed"
          style={{ color: "var(--nv-text-tertiary)" }}
        >
          {t.topPicks.emptyMessage}
        </p>
      </div>
    );
  }
  return (
    <div className="nv-card nv-fade-in" style={{ borderRadius: "var(--nv-radius-lg)", padding: "var(--nv-space-lg)" }}>
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <h3
          className="text-sm font-bold"
          style={{
            color: "var(--nv-text-primary)",
            letterSpacing: "var(--nv-tracking-wide)",
          }}
        >
          {t.topPicks.title}
        </h3>
        <span className="nv-badge" style={{ backgroundColor: "var(--nv-bg-elevated)", color: "var(--nv-text-tertiary)" }}>
          ft-display-v3 · {t.topPicks.selectionCount.replace("{count}", String(recommendations.length))}
        </span>
      </div>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {recommendations.map((recommendation) => (
          <RecommendationRow key={recommendation.recommendation_id} recommendation={recommendation} />
        ))}
      </div>
      <p
        className="text-[10px] leading-relaxed mt-3"
        style={{ color: "var(--nv-text-tertiary)" }}
      >
        {t.topPicks.disclaimer}
      </p>
    </div>
  );
});
