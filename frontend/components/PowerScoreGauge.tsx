"use client";

import type { AnalyzeResponse, PatternResult } from "@/lib/types";
import { useLocale } from "@/lib/locale-context";

export function computePowerScore(
  data: AnalyzeResponse,
  patternB: PatternResult | null,
  patternC: PatternResult | null,
  patternD: PatternResult | null = null,
): number {
  let score = 0;
  let factors = 0;

  if (patternB && patternB.match_count > 0) {
    score += Math.min(30, patternB.match_count);
    factors++;
  }

  if (patternC && patternC.match_count > 0) {
    score += Math.min(20, patternC.match_count * 2);
    factors++;
  }

  if (patternD && patternD.match_count > 0) {
    score += Math.min(15, patternD.match_count);
    factors++;
  }

  const topPct = Math.max(
    patternB?.result_1_pct ?? 0,
    patternB?.result_x_pct ?? 0,
    patternB?.result_2_pct ?? 0,
    patternB?.ust_25_pct ?? 0,
    patternB?.alt_25_pct ?? 0,
    patternB?.kg_var_pct ?? 0,
    patternB?.kg_yok_pct ?? 0,
  );
  if (topPct > 0) {
    score += Math.round(topPct * 0.3);
    factors++;
  }

  if (data.trends) {
    const trendBlocks = [data.trends.home_form, data.trends.away_form, data.trends.h2h].filter(Boolean).length;
    score += trendBlocks * 5;
    factors++;
  }

  const activeArchives = [patternB, patternC, patternD].filter(
    (p) => p && p.match_count >= 1,
  ).length;
  if (activeArchives >= 3) {
    score += 8;
    factors++;
  } else if (activeArchives >= 2) {
    score += 5;
    factors++;
  }

  return factors > 0 ? Math.min(100, score) : 0;
}

interface Props {
  score: number;
  patternB: PatternResult | null;
  patternC: PatternResult | null;
  patternD?: PatternResult | null;
  trendCount: number;
}

export default function PowerScoreGauge({ score, patternB, patternC, patternD, trendCount }: Props) {
  const { t } = useLocale();
  if (score <= 0) return null;

  const gaugeColor =
    score >= 70 ? "var(--nv-accent-green)" :
    score >= 40 ? "var(--nv-accent-blue)" :
    "var(--nv-accent-amber)";

  return (
    <div
      className="nv-card nv-fade-in"
      style={{
        borderRadius: "var(--nv-radius-lg)",
        padding: "var(--nv-space-lg)",
      }}
    >
      <div className="flex flex-col sm:flex-row items-center sm:items-start gap-4">
        <div
          className="flex-shrink-0 relative flex items-center justify-center"
          aria-hidden="true"
          style={{ width: 80, height: 80 }}
        >
          <div
            style={{
              position: "absolute",
              inset: 0,
              borderRadius: "50%",
              background: `conic-gradient(${gaugeColor} ${score * 3.6}deg, var(--nv-bg-elevated) ${score * 3.6}deg 360deg)`,
            }}
          />
          <div
            className="flex items-center justify-center"
            style={{
              position: "absolute",
              inset: 6,
              borderRadius: "50%",
              backgroundColor: "var(--nv-bg-card)",
            }}
          >
            <span
              style={{
                fontFamily: "var(--nv-font-mono)",
                fontSize: "var(--nv-text-xl, 1.25rem)",
                fontWeight: 700,
                color: gaugeColor,
                lineHeight: 1,
              }}
            >
              {score}
            </span>
          </div>
        </div>

        <div className="flex-1 min-w-0 text-center sm:text-left">
          <h3
            className="text-sm font-bold"
            style={{
              color: "var(--nv-text-primary)",
              letterSpacing: "var(--nv-tracking-wide)",
            }}
          >
            {t.powerScore.title}
          </h3>
          <div className="flex flex-wrap justify-center sm:justify-start gap-2 mt-2">
            {patternB && patternB.match_count > 0 && (
              <span
                className="nv-badge"
                style={{
                  backgroundColor: "var(--nv-bg-elevated)",
                  color: "var(--nv-text-secondary)",
                  fontSize: "var(--nv-text-xs)",
                }}
              >
                {t.analyze.archive1}: {patternB.match_count} {t.common.match}
              </span>
            )}
            {patternC && patternC.match_count > 0 && (
              <span
                className="nv-badge"
                style={{
                  backgroundColor: "var(--nv-bg-elevated)",
                  color: "var(--nv-text-secondary)",
                  fontSize: "var(--nv-text-xs)",
                }}
              >
                {t.analyze.archive2}: {patternC.match_count} {t.common.match}
              </span>
            )}
            {patternD && patternD.match_count > 0 && (
              <span
                className="nv-badge"
                style={{
                  backgroundColor: "var(--nv-bg-elevated)",
                  color: "var(--nv-text-secondary)",
                  fontSize: "var(--nv-text-xs)",
                }}
              >
                {t.analyze.archive3}: {patternD.match_count} {t.common.match}
              </span>
            )}
            {trendCount > 0 && (
              <span
                className="nv-badge"
                style={{
                  backgroundColor: "var(--nv-bg-elevated)",
                  color: "var(--nv-text-secondary)",
                  fontSize: "var(--nv-text-xs)",
                }}
              >
                {t.powerScore.trend}: {trendCount}/3
              </span>
            )}
            {(() => {
              const active = [patternB, patternC, patternD].filter(
                (p) => p && p.match_count >= 1,
              ).length;
              if (active >= 3) return (
                <span
                  className="nv-badge"
                  style={{
                    backgroundColor: "var(--nv-accent-green-dim, rgba(34,197,94,0.1))",
                    color: "var(--nv-accent-green)",
                    fontSize: "var(--nv-text-xs)",
                  }}
                >
                  {t.powerScore.tripleArchive}
                </span>
              );
              if (active >= 2) return (
                <span
                  className="nv-badge"
                  style={{
                    backgroundColor: "var(--nv-accent-green-dim, rgba(34,197,94,0.1))",
                    color: "var(--nv-accent-green)",
                    fontSize: "var(--nv-text-xs)",
                  }}
                >
                  {t.powerScore.dualArchive}
                </span>
              );
              return null;
            })()}
          </div>
        </div>
      </div>
    </div>
  );
}
