"use client";

import type { TrendBlock, TrendsData } from "@/lib/types";

interface Props {
  trends: TrendsData | null;
  homeTeam: string;
  awayTeam: string;
}

function ResultDot({ r }: { r: "G" | "B" | "M" }) {
  const cfg =
    r === "G"
      ? { bg: "var(--nv-win)", label: "G" }
      : r === "B"
        ? { bg: "var(--nv-draw)", label: "B" }
        : { bg: "var(--nv-loss)", label: "M" };
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
}: {
  block: TrendBlock;
  title: string;
  subtitle?: string;
  accent: string;
}) {
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
          {block.sample_size} maç
        </span>
      </div>

      {/* Son N Sonuç Timeline */}
      {block.last_n_results.length > 0 && (
        <div className="flex items-center gap-1 mb-2">
          {block.last_n_results.map((r, i) => (
            <ResultDot key={i} r={r} />
          ))}
          <span
            className="text-[9px] ml-1"
            style={{ color: "var(--nv-text-tertiary)" }}
          >
            son {block.last_n_results.length}
          </span>
        </div>
      )}

      {/* Metrikler */}
      <div
        className="space-y-1 pt-2 mt-auto"
        style={{ borderTop: "1px solid var(--nv-border)" }}
      >
        <MetricRow label="Galibiyet" value={`%${Math.round(block.win_pct)}`} highlight={block.win_pct >= 60} />
        <MetricRow label="Beraberlik" value={`%${Math.round(block.draw_pct)}`} />
        <MetricRow label="Mağlubiyet" value={`%${Math.round(block.loss_pct)}`} />
        <MetricRow label="KG Var" value={`%${Math.round(block.kg_var_pct)}`} highlight={block.kg_var_pct >= 60} />
        <MetricRow label="Üst 2.5" value={`%${Math.round(block.over_25_pct)}`} highlight={block.over_25_pct >= 60} />
        <MetricRow
          label="Att / Yedi"
          value={`${block.avg_goals_for.toFixed(1)} / ${block.avg_goals_against.toFixed(1)}`}
        />
      </div>
    </div>
  );
}

export default function TrendsPanel({ trends, homeTeam, awayTeam }: Props) {
  if (!trends) return null;
  const blocks: { block: TrendBlock | null; title: string; subtitle?: string; accent: string }[] = [
    {
      block: trends.home_form,
      title: "Ev Form",
      subtitle: homeTeam,
      accent: "var(--nv-accent-green)",
    },
    {
      block: trends.away_form,
      title: "Dep Form",
      subtitle: awayTeam,
      accent: "var(--nv-accent-amber)",
    },
    {
      block: trends.h2h,
      title: "H2H",
      subtitle: "Ev sahibi perspektifi",
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
          Form & H2H Trendleri
        </h3>
        <span
          className="nv-badge"
          style={{ backgroundColor: "var(--nv-bg-elevated)", color: "var(--nv-text-tertiary)" }}
        >
          son lig maçları
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
          />
        ))}
      </div>
    </div>
  );
}
