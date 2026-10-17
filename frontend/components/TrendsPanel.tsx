"use client";

import { memo } from "react";
import type { TrendBlock, TrendsData } from "@/lib/types";
import { useLocale } from "@/lib/locale-context";
import type { Dictionary } from "@/lib/i18n";

interface Props {
  trends: TrendsData | null;
  homeTeam: string;
  awayTeam: string;
}

function ResultDot({ r, t }: { r: "G" | "B" | "M"; t: Dictionary }) {
  const cfg =
    r === "G"
      ? { bg: "var(--nv-win)", label: t.trends.win[0] }
      : r === "B"
        ? { bg: "var(--nv-draw)", label: t.trends.draw[0] }
        : { bg: "var(--nv-loss)", label: t.trends.loss[0] };
  return (
    <span
      className="inline-flex items-center justify-center w-5 h-5 rounded text-[10px] font-bold"
      style={{
        backgroundColor: cfg.bg,
        color: "var(--nv-text-inverse)",
        fontFamily: "var(--nv-font-mono)",
      }}
    >
      {cfg.label}
    </span>
  );
}

function MetricRow({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div className="flex items-center justify-between text-xs">
      <span style={{ color: "var(--nv-text-secondary)" }}>{label}</span>
      <span
        className="font-bold"
        style={{
          fontFamily: "var(--nv-font-mono)",
          color: highlight ? "var(--nv-accent-green)" : "var(--nv-text-primary)",
        }}
      >
        {value}
      </span>
    </div>
  );
}

function TrendCard({
  block,
  title,
  subtitle,
  accent,
  t,
}: {
  block: TrendBlock;
  title: string;
  subtitle?: string;
  accent: string;
  t: Dictionary;
}) {
  const maxGoal = Math.max(block.avg_goals_for, block.avg_goals_against, 0.1);
  const forPct = (block.avg_goals_for / maxGoal) * 100;
  const againstPct = (block.avg_goals_against / maxGoal) * 100;

  return (
    <div
      className="nv-card flex flex-col"
      style={{
        borderRadius: "var(--nv-radius-lg)",
        borderTop: `2px solid ${accent}`,
        padding: "var(--nv-space-md)",
      }}
    >
      {/* Başlık */}
      <div className="flex items-center justify-between mb-2">
        <div className="min-w-0">
          <h4
            className="text-xs font-bold truncate"
            style={{
              color: accent,
              letterSpacing: "var(--nv-tracking-wide)",
            }}
          >
            {title}
          </h4>
          {subtitle && (
            <div
              className="text-[9px] truncate mt-0.5"
              style={{ color: "var(--nv-text-tertiary)" }}
            >
              {subtitle}
            </div>
          )}
        </div>
        <span className="nv-badge" style={{ backgroundColor: "var(--nv-bg-elevated)", color: "var(--nv-text-secondary)" }}>
          {block.sample_size} {t.common.match}
        </span>
      </div>

      {/* Son N Sonuç Timeline */}
      {block.last_n_results.length > 0 && (
        <div className="flex items-center gap-1 mb-2">
          {block.last_n_results.map((r, i) => (
            <ResultDot key={i} r={r} t={t} />
          ))}
          <span
            className="text-[9px] ml-1"
            style={{ color: "var(--nv-text-tertiary)" }}
          >
            {t.trends.last.replace("{count}", String(block.last_n_results.length))}
          </span>
        </div>
      )}

      {/* Galibiyet / Beraberlik / Mağlubiyet Oranı Çubuğu */}
      <div
        className="flex overflow-hidden mb-2"
        style={{
          height: 6,
          borderRadius: "var(--nv-radius-full)",
          backgroundColor: "var(--nv-bg-elevated)",
        }}
      >
        {block.win_pct > 0 && (
          <div
            style={{
              width: `${block.win_pct}%`,
              backgroundColor: "var(--nv-win)",
              height: "100%",
            }}
          />
        )}
        {block.draw_pct > 0 && (
          <div
            style={{
              width: `${block.draw_pct}%`,
              backgroundColor: "var(--nv-draw)",
              height: "100%",
            }}
          />
        )}
        {block.loss_pct > 0 && (
          <div
            style={{
              width: `${block.loss_pct}%`,
              backgroundColor: "var(--nv-loss)",
              height: "100%",
            }}
          />
        )}
      </div>

      {/* Metrikler */}
      <div
        className="space-y-1 pt-2 mt-auto"
        style={{ borderTop: "1px solid var(--nv-border)" }}
      >
        <MetricRow label={t.trends.win} value={`%${Math.round(block.win_pct)}`} highlight={block.win_pct >= 60} />
        <MetricRow label={t.trends.draw} value={`%${Math.round(block.draw_pct)}`} />
        <MetricRow label={t.trends.loss} value={`%${Math.round(block.loss_pct)}`} />
        <MetricRow label={t.trends.bttsYes} value={`%${Math.round(block.kg_var_pct)}`} highlight={block.kg_var_pct >= 60} />
        <MetricRow label={t.trends.over25} value={`%${Math.round(block.over_25_pct)}`} highlight={block.over_25_pct >= 60} />
        <div className="text-xs space-y-1">
          <div className="flex items-center justify-between">
            <span style={{ color: "var(--nv-text-secondary)" }}>{t.trends.goalsForAgainst}</span>
            <span
              className="font-bold"
              style={{
                fontFamily: "var(--nv-font-mono)",
                color: "var(--nv-text-primary)",
              }}
            >
              {block.avg_goals_for.toFixed(1)} / {block.avg_goals_against.toFixed(1)}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex-1 flex items-center gap-1.5">
              <div
                style={{
                  width: `${forPct}%`,
                  height: 4,
                  backgroundColor: "var(--nv-win)",
                  borderRadius: "var(--nv-radius-full)",
                  minWidth: 2,
                }}
              />
              <span
                className="text-[9px] shrink-0"
                style={{
                  color: "var(--nv-win)",
                  fontFamily: "var(--nv-font-mono)",
                }}
              >
                {block.avg_goals_for.toFixed(1)}
              </span>
            </div>
            <div className="flex-1 flex items-center gap-1.5">
              <div
                style={{
                  width: `${againstPct}%`,
                  height: 4,
                  backgroundColor: "var(--nv-loss)",
                  borderRadius: "var(--nv-radius-full)",
                  minWidth: 2,
                }}
              />
              <span
                className="text-[9px] shrink-0"
                style={{
                  color: "var(--nv-loss)",
                  fontFamily: "var(--nv-font-mono)",
                }}
              >
                {block.avg_goals_against.toFixed(1)}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default memo(function TrendsPanel({ trends, homeTeam, awayTeam }: Props) {
  const { t } = useLocale();
  if (!trends) return null;
  const blocks: { block: TrendBlock | null; title: string; subtitle?: string; accent: string }[] = [
    {
      block: trends.home_form,
      title: t.trends.homeForm,
      subtitle: homeTeam,
      accent: "var(--nv-accent-green)",
    },
    {
      block: trends.away_form,
      title: t.trends.awayForm,
      subtitle: awayTeam,
      accent: "var(--nv-accent-amber)",
    },
    {
      block: trends.h2h,
      title: t.trends.h2h,
      subtitle: t.trends.h2hSubtitle,
      accent: "var(--nv-accent-purple)",
    },
  ];

  const visible = blocks.filter((b) => b.block !== null);
  if (visible.length === 0) return null;

  return (
    <div className="nv-card nv-fade-in" style={{ borderRadius: "var(--nv-radius-lg)", padding: "var(--nv-space-lg)" }}>
      <div className="flex items-center gap-2 mb-3">
        <span style={{ color: "var(--nv-text-tertiary)" }}>📈</span>
        <h3
          className="text-sm font-bold"
          style={{
            color: "var(--nv-text-primary)",
            letterSpacing: "var(--nv-tracking-wide)",
          }}
        >
          {t.trends.title}
        </h3>
        <span
          className="nv-badge"
          style={{ backgroundColor: "var(--nv-bg-elevated)", color: "var(--nv-text-tertiary)" }}
        >
          {t.trends.subtitle}
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {visible.map((b) => (
          <TrendCard
            key={b.title}
            block={b.block!}
            title={b.title}
            subtitle={b.subtitle}
            accent={b.accent}
            t={t}
          />
        ))}
      </div>
    </div>
  );
});
