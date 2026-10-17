import { getPerformancePredictions, getPerformanceSummary } from "@/lib/api";
import type { LedgerPrediction, PerformanceStats, PerformanceSummary, PredictionSource } from "@/lib/api";
import type { Dictionary } from "@/lib/i18n";
import { leagueDisplay } from "@/lib/leagues";
import { formatTime } from "@/lib/dates";
import RetryButton from "./RetryButton";

type Perf = Dictionary["evaluation"]["perf"];

function fmt(value: number | null | undefined, suffix = ""): string {
  return value == null ? "—" : `${value.toFixed(1)}${suffix}`;
}

function rateColor(stats: PerformanceStats): string {
  if (stats.hit_pct == null || stats.stage === "cok_erken") return "var(--nv-text-secondary)";
  return stats.lift_pct != null && stats.lift_pct > 0 ? "var(--nv-accent-green)" : "var(--nv-text-primary)";
}

function marketLabel(market: string, p: Perf): string {
  return (p as Record<string, string>)[`market_${market}`] ?? market;
}

function selectionLabel(market: string, selection: string, t: Dictionary): string {
  const lp = t.live.prediction;
  const map: Record<string, string> = { over: lp.over, under: lp.under, yes: lp.yes, no: lp.no };
  return market === "result" ? selection : map[selection] ?? selection;
}

function Card({ label, value, sub, hint, color }: { label: string; value: string; sub?: string; hint?: string; color?: string }) {
  return (
    <div className="nv-card p-4 min-w-0" title={hint}>
      <div style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)", fontWeight: 500, marginBottom: 6 }}>{label}</div>
      <div className="font-bold" style={{ fontSize: "var(--nv-text-xl)", color: color ?? "var(--nv-text-primary)", fontVariantNumeric: "tabular-nums" }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: "var(--nv-text-2xs)", color: "var(--nv-text-tertiary)", marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

function StatsTable({ title, rows, labelOf, p }: {
  title: string;
  rows: (PerformanceStats & { key: string })[];
  labelOf: (key: string) => string;
  p: Perf;
}) {
  if (rows.length === 0) return null;
  return (
    <div className="nv-card p-4 min-w-0">
      <h3 className="font-semibold mb-2" style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-text-primary)" }}>{title}</h3>
      <div style={{ overflowX: "auto" }}>
        <table className="w-full" style={{ fontSize: "var(--nv-text-xs)", fontVariantNumeric: "tabular-nums", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ color: "var(--nv-text-tertiary)", textAlign: "right" }}>
              <th style={{ textAlign: "left", padding: "4px 6px", fontWeight: 500 }}>{p.colGroup}</th>
              <th style={{ padding: "4px 6px", fontWeight: 500 }}>{p.colN}</th>
              <th style={{ padding: "4px 6px", fontWeight: 500 }}>{p.colHit}</th>
              <th style={{ padding: "4px 6px", fontWeight: 500 }}>{p.colAvg}</th>
              <th style={{ padding: "4px 6px", fontWeight: 500 }}>{p.colLift}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.key} style={{ borderTop: "1px solid var(--nv-border-subtle)", textAlign: "right", opacity: row.stage === "cok_erken" ? 0.65 : 1 }}>
                <td style={{ textAlign: "left", padding: "6px", color: "var(--nv-text-primary)" }}>{labelOf(row.key)}</td>
                <td style={{ padding: "6px", color: "var(--nv-text-secondary)" }}>{row.resolved}</td>
                <td style={{ padding: "6px", fontWeight: 700, color: rateColor(row) }}>{fmt(row.hit_pct, "%")}</td>
                <td style={{ padding: "6px", color: "var(--nv-text-secondary)" }}>{fmt(row.avg_prob_pct, "%")}</td>
                <td style={{ padding: "6px", color: "var(--nv-text-secondary)" }}>{row.lift_pct == null ? "—" : `${row.lift_pct > 0 ? "+" : ""}${row.lift_pct.toFixed(1)}`}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function CalibrationList({ buckets, p }: { buckets: PerformanceSummary["calibration"]; p: Perf }) {
  if (buckets.length === 0) return null;
  return (
    <div className="nv-card p-4 min-w-0">
      <h3 className="font-semibold mb-1" style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-text-primary)" }}>{p.calibrationTitle}</h3>
      <p className="mb-2" style={{ fontSize: "var(--nv-text-2xs)", color: "var(--nv-text-tertiary)" }}>{p.calibrationHint}</p>
      <div className="space-y-1.5">
        {buckets.map((b) => (
          <div key={b.lower} className="grid items-center gap-2" style={{ gridTemplateColumns: "64px 1fr 92px", fontSize: "var(--nv-text-xs)", fontVariantNumeric: "tabular-nums" }}>
            <span style={{ color: "var(--nv-text-tertiary)" }}>{p.bucket.replace("{low}", String(b.lower)).replace("{high}", String(b.upper))}</span>
            <div style={{ position: "relative", height: 8, borderRadius: 4, backgroundColor: "var(--nv-bg-elevated)" }}>
              <div style={{ width: `${b.hit_pct}%`, height: "100%", borderRadius: 4, backgroundColor: "var(--nv-accent-blue)" }} />
              <div style={{ position: "absolute", top: -2, bottom: -2, left: `${b.avg_prob_pct}%`, width: 2, backgroundColor: "var(--nv-text-primary)" }} />
            </div>
            <span className="text-right" style={{ color: "var(--nv-text-secondary)" }}>
              {b.hit_pct.toFixed(0)}% · n={b.n}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export async function PerformanceOverview({ source, t }: { source: PredictionSource; t: Dictionary }) {
  const p = t.evaluation.perf;
  let summary: PerformanceSummary;
  try {
    summary = await getPerformanceSummary(source);
  } catch {
    return (
      <div className="nv-card p-6 text-center space-y-3">
        <p style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-accent-red)" }}>{t.common.loadError}</p>
        <RetryButton />
      </div>
    );
  }
  const o = summary.overall;
  if (o.total === 0) {
    return (
      <div className="nv-card p-6 text-center">
        <p style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-text-secondary)" }}>{p.empty}</p>
        {source === "live_ht" && <p className="mt-1" style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)" }}>{p.emptyLive}</p>}
      </div>
    );
  }
  const tierLabel = (key: string) => (p as Record<string, string>)[`tier_${key}`] ?? key;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2" style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)" }}>
        <span className="font-semibold" style={{ color: "var(--nv-text-secondary)" }}>{p.allTime}</span>
        <span>· {summary.rule_versions.join(", ")}</span>
        <span>· {p.pendingCount.replace("{n}", String(o.pending))}</span>
        <span className="px-2 py-0.5" style={{ borderRadius: "var(--nv-radius-full)", backgroundColor: "var(--nv-bg-elevated)" }}>
          {(p as Record<string, string>)[`stage_${o.stage}`]}
        </span>
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Card
          label={p.winRate}
          value={fmt(o.hit_pct, "%")}
          sub={`${p.hitsOf.replace("{hits}", String(o.hits)).replace("{n}", String(o.resolved))}${o.ci_low != null ? ` · ${p.ci.replace("{low}", o.ci_low.toFixed(0)).replace("{high}", String(o.ci_high?.toFixed(0)))}` : ""}`}
          color={rateColor(o)}
        />
        <Card
          label={p.lift}
          value={o.lift_pct == null ? "—" : `${o.lift_pct > 0 ? "+" : ""}${o.lift_pct.toFixed(1)}`}
          sub={o.baseline_hit_pct == null ? undefined : `${p.baseline}: ${o.baseline_hit_pct.toFixed(1)}%`}
          hint={p.liftHint}
        />
        <Card label={p.calibration} value={`${fmt(o.avg_prob_pct, "%")} / ${fmt(o.hit_pct, "%")}`} hint={p.calibrationHint} />
        <Card label={p.brier} value={o.brier == null ? "—" : o.brier.toFixed(3)} sub={p.brierHint} />
      </div>
      <div className="grid gap-3 lg:grid-cols-2">
        <StatsTable title={p.byTier} rows={summary.groups.tier ?? []} labelOf={tierLabel} p={p} />
        <StatsTable title={p.byMarket} rows={summary.groups.market ?? []} labelOf={(k) => marketLabel(k, p)} p={p} />
      </div>
      <CalibrationList buckets={summary.calibration} p={p} />
    </div>
  );
}

function OutcomeBadge({ outcome, p }: { outcome: LedgerPrediction["outcome"]; p: Perf }) {
  const style = {
    hit: { bg: "var(--nv-accent-green-dim)", fg: "var(--nv-accent-green)", mark: "✓" },
    miss: { bg: "var(--nv-accent-red-dim)", fg: "var(--nv-accent-red)", mark: "✗" },
    void: { bg: "var(--nv-bg-elevated)", fg: "var(--nv-text-tertiary)", mark: "–" },
    pending: { bg: "var(--nv-bg-elevated)", fg: "var(--nv-text-tertiary)", mark: "…" },
  }[outcome];
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 font-semibold flex-shrink-0" style={{ fontSize: "var(--nv-text-xs)", borderRadius: "var(--nv-radius-sm)", backgroundColor: style.bg, color: style.fg }}>
      <span aria-hidden="true">{style.mark}</span> {p[`outcome_${outcome}`]}
    </span>
  );
}

export async function PredictionDayList({ source, day, t }: { source: PredictionSource; day: string; t: Dictionary }) {
  const p = t.evaluation.perf;
  let rows: LedgerPrediction[];
  try {
    rows = await getPerformancePredictions(source, day);
  } catch {
    return <p className="nv-card p-4" style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-accent-red)" }}>{t.common.loadError}</p>;
  }
  if (rows.length === 0) {
    return <p className="nv-card p-4 text-center" style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-text-tertiary)" }}>{p.emptyDay}</p>;
  }
  const byMatch = new Map<string, LedgerPrediction[]>();
  for (const row of rows) byMatch.set(row.match_id, [...(byMatch.get(row.match_id) ?? []), row]);
  return (
    <div className="space-y-2">
      <h3 className="font-semibold" style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-text-primary)" }}>{p.dayList}</h3>
      {[...byMatch.values()].map((preds) => {
        const first = preds[0];
        const { flag, short } = leagueDisplay(null, first.league_name);
        return (
          <div key={first.match_id} className="nv-card p-3 space-y-2 min-w-0">
            <div className="flex flex-wrap items-center gap-2" style={{ fontSize: "var(--nv-text-xs)" }}>
              <span aria-hidden="true">{flag}</span>
              <span style={{ color: "var(--nv-text-tertiary)" }}>{short} · {formatTime(first.kickoff_time)}</span>
              <span className="font-semibold min-w-0 truncate" style={{ color: "var(--nv-text-primary)" }}>
                {first.home_team} - {first.away_team}
              </span>
              <span className="flex-1" />
              {first.ht && <span style={{ color: "var(--nv-text-tertiary)", fontFamily: "var(--nv-font-mono)" }}>{t.live.ht} {first.ht}</span>}
              {first.final_ft && <span className="font-bold" style={{ color: "var(--nv-text-primary)", fontFamily: "var(--nv-font-mono)" }}>{t.live.ft} {first.final_ft}</span>}
            </div>
            <div className="flex flex-wrap gap-2">
              {preds.map((pred) => (
                <div key={pred.id} className="flex items-center gap-2 px-2 py-1" style={{ borderRadius: "var(--nv-radius-md)", backgroundColor: "var(--nv-bg-surface)", border: "1px solid var(--nv-border-subtle)", fontSize: "var(--nv-text-xs)", opacity: pred.informational ? 0.7 : 1 }}>
                  <span style={{ color: "var(--nv-text-tertiary)" }}>{marketLabel(pred.market, p)}</span>
                  <span className="font-bold" style={{ color: "var(--nv-text-primary)" }}>{selectionLabel(pred.market, pred.selection, t)}</span>
                  <span style={{ fontFamily: "var(--nv-font-mono)", color: "var(--nv-text-secondary)" }}>%{pred.prob_pct.toFixed(1)}</span>
                  {pred.informational && <span style={{ color: "var(--nv-text-tertiary)" }}>({p.info})</span>}
                  {pred.late && <span style={{ color: "var(--nv-text-tertiary)" }}>({p.late})</span>}
                  <OutcomeBadge outcome={pred.outcome} p={p} />
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
