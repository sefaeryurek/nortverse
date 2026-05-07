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
      ? { bg: "#16a34a", text: "G", color: "#ecfdf5" }
      : r === "B"
        ? { bg: "#ca8a04", text: "B", color: "#fefce8" }
        : { bg: "#b91c1c", text: "M", color: "#fef2f2" };
  return (
    <span
      className="inline-flex items-center justify-center w-5 h-5 rounded text-[10px] font-bold font-mono"
      style={{ backgroundColor: cfg.bg, color: cfg.color }}
    >
      {cfg.text}
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
      <span style={{ color: "#64748b" }}>{label}</span>
      <span
        className="font-mono font-bold"
        style={{ color: highlight ? "#86efac" : "#cbd5e1" }}
      >
        {value}
      </span>
    </div>
  );
}

function TrendCard({
  block,
  icon,
  title,
  subtitle,
  accent,
}: {
  block: TrendBlock;
  icon: string;
  title: string;
  subtitle?: string;
  accent: string;
}) {
  return (
    <div
      className="rounded-xl p-3 border space-y-2.5 flex flex-col"
      style={{ backgroundColor: "#0f1625", borderColor: "#1e293b" }}
    >
      {/* Başlık */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 min-w-0">
          <span className="text-base flex-shrink-0">{icon}</span>
          <div className="min-w-0">
            <h4
              className="text-xs font-bold tracking-wide truncate"
              style={{ color: accent }}
            >
              {title}
            </h4>
            {subtitle && (
              <div className="text-[9px] truncate" style={{ color: "#475569" }}>
                {subtitle}
              </div>
            )}
          </div>
        </div>
        <span
          className="text-[10px] font-mono px-1.5 py-0.5 rounded flex-shrink-0"
          style={{ backgroundColor: "#1e293b", color: "#94a3b8" }}
        >
          {block.sample_size} maç
        </span>
      </div>

      {/* Son N Sonuç Timeline */}
      {block.last_n_results.length > 0 && (
        <div className="flex items-center gap-1">
          {block.last_n_results.map((r, i) => (
            <ResultDot key={i} r={r} />
          ))}
          <span className="text-[9px] ml-1" style={{ color: "#475569" }}>
            son {block.last_n_results.length}
          </span>
        </div>
      )}

      {/* Metrikler */}
      <div className="space-y-1 pt-1 border-t" style={{ borderColor: "#1e293b" }}>
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
  const blocks: { block: TrendBlock | null; icon: string; title: string; subtitle?: string; accent: string }[] = [
    {
      block: trends.home_form,
      icon: "🏠",
      title: "Ev Form",
      subtitle: homeTeam,
      accent: "#86efac",
    },
    {
      block: trends.away_form,
      icon: "✈",
      title: "Dep Form",
      subtitle: awayTeam,
      accent: "#fbbf24",
    },
    {
      block: trends.h2h,
      icon: "⚔",
      title: "H2H",
      subtitle: "Ev sahibi perspektifi",
      accent: "#c084fc",
    },
  ];

  const visible = blocks.filter((b) => b.block !== null);
  if (visible.length === 0) return null;

  return (
    <div
      className="rounded-xl p-4 border space-y-3"
      style={{ backgroundColor: "#0a0f1a", borderColor: "#1e293b" }}
    >
      <div className="flex items-center gap-2">
        <span style={{ color: "#64748b" }}>📈</span>
        <h3 className="text-sm font-bold tracking-wide" style={{ color: "#cbd5e1" }}>
          Form & H2H Trendleri
        </h3>
        <span className="text-[10px]" style={{ color: "#475569" }}>
          son lig maçları
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {visible.map((b) => (
          <TrendCard
            key={b.title}
            block={b.block!}
            icon={b.icon}
            title={b.title}
            subtitle={b.subtitle}
            accent={b.accent}
          />
        ))}
      </div>
    </div>
  );
}
