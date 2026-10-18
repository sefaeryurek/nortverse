"use client";

import Link from "next/link";
import type { LiveArchiveMatch, LiveArchiveSource, LiveArchiveView, LiveHighlight, LiveOutcome } from "@/lib/api";
import { liveMarketLabel, liveSelectionLabel } from "@/lib/live-labels";
import { useLocale } from "@/lib/locale-context";

const OUTCOME_COLORS: Record<LiveOutcome, string> = {
  "1": "var(--nv-win)",
  X: "var(--nv-draw)",
  "2": "var(--nv-loss)",
};

function fmtPct(value: number): string {
  return `%${value % 1 === 0 ? value.toFixed(0) : value.toFixed(1)}`;
}

/** Riskli işaret: ikon + metin (renk tek başına anlam taşımaz). */
export function RiskyBadge({ n, min }: { n: number; min: number }) {
  const { t } = useLocale();
  const a = t.live.archive;
  return (
    <span
      className="inline-flex items-center gap-0.5 px-1.5 font-semibold"
      style={{ fontSize: "var(--nv-text-2xs)", borderRadius: "var(--nv-radius-full)", backgroundColor: "var(--nv-accent-amber-dim, var(--nv-bg-elevated))", color: "var(--nv-accent-amber)" }}
      title={a.riskyTooltip.replace("{n}", String(n)).replace("{min}", String(min))}
    >
      <span aria-hidden="true">⚠</span> {a.risky}
    </span>
  );
}

type Group = { key: string; period: string; market: string; selection: string; pct: number; risky: boolean; items: LiveHighlight[] };

/** Aynı seçimi işaret eden kaynaklar tek satırda: "MS ÇŞ X2 %100 · A3 (6) · Genel (6)". */
export function groupHighlights(highlights: LiveHighlight[]): Group[] {
  const groups = new Map<string, Group>();
  for (const h of highlights) {
    const key = `${h.period}:${h.market}:${h.selection}`;
    const g = groups.get(key) ?? { key, period: h.period, market: h.market, selection: h.selection, pct: 0, risky: true, items: [] };
    g.items.push(h);
    g.pct = Math.max(g.pct, h.pct);
    g.risky = g.risky && h.risky;
    groups.set(key, g);
  }
  return [...groups.values()].sort((a, b) => Number(a.risky) - Number(b.risky) || b.pct - a.pct || b.items.length - a.items.length);
}

function archiveName(label: string, generalLabel: string): string {
  return label.toLowerCase() === "genel" ? generalLabel : label;
}

/** live-arch-v2 kararı: pazar başına tek satır; ana oran lig geçmişinden, arşiv oranı ikincil. */
function DecisionRow({ h }: { h: LiveHighlight }) {
  const { t } = useLocale();
  const a = t.live.archive;
  const generalLabel = t.evaluation.perf.archive_genel;
  return (
    <li
      className="flex flex-wrap items-center gap-x-2 gap-y-1 px-2.5 py-1.5"
      style={{ borderRadius: "var(--nv-radius-md)", backgroundColor: "var(--nv-accent-green-dim)", border: "1px solid var(--nv-border-subtle)" }}
    >
      <span style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-secondary)" }}>{liveMarketLabel(h.period, h.market, t)}</span>
      <span className="font-bold" style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-text-primary)" }}>{liveSelectionLabel(h.selection, t)}</span>
      <span
        className="font-extrabold"
        style={{ fontFamily: "var(--nv-font-mono)", fontSize: "var(--nv-text-sm)", color: "var(--nv-accent-green)" }}
        title={a.condTooltip.replace("{n}", String(h.cond_n ?? "?"))}
      >
        {fmtPct(h.pct)}
      </span>
      <span style={{ fontSize: "var(--nv-text-2xs)", color: "var(--nv-text-tertiary)" }}>
        {(h.cond_level === "global" ? a.condGlobal : a.condLeague).replace("{n}", String(h.cond_n ?? "?"))}
      </span>
      <span className="flex-1" />
      <span className="inline-flex flex-wrap items-center gap-1" style={{ fontSize: "var(--nv-text-2xs)", color: "var(--nv-text-secondary)", fontVariantNumeric: "tabular-nums" }}>
        <span style={{ color: "var(--nv-text-tertiary)" }}>{a.archiveLabel}:</span>
        <span className="font-semibold">{(h.sources ?? [h.label]).map((l) => archiveName(l, generalLabel)).join(" + ")}</span>
        {h.archive_pct != null && <span style={{ fontFamily: "var(--nv-font-mono)" }}>{fmtPct(h.archive_pct)}</span>}
        <span style={{ color: "var(--nv-text-tertiary)" }}>({h.n})</span>
        {h.conflict && (
          <span title={a.conflictTooltip} style={{ color: "var(--nv-accent-amber)" }}>
            <span aria-hidden="true">⚠</span> {a.conflict}
          </span>
        )}
        {h.historical && (
          <span
            className="px-1.5"
            style={{ borderRadius: "var(--nv-radius-sm)", backgroundColor: "var(--nv-bg-surface)", color: "var(--nv-text-primary)", fontFamily: "var(--nv-font-mono)" }}
            title={a.historicalTooltip.replace("{bucket}", h.historical.bucket).replace("{n}", String(h.historical.n))
              + (h.historical.pooled ? ` ${a.historicalPooled}` : "")}
          >
            {a.historical.replace("{pct}", h.historical.pct.toFixed(0))}
          </span>
        )}
      </span>
    </li>
  );
}

export function HighlightList({ view }: { view: LiveArchiveView }) {
  const { t } = useLocale();
  const a = t.live.archive;
  const threshold = String(view.threshold_pct);
  const decisions = view.highlights.filter((h) => h.sources);
  if (decisions.length > 0 || view.rule_version !== "live-arch-v1") {
    return (
      <section className="space-y-1.5" aria-label={a.decisionsTitle.replace("{pct}", threshold)}>
        <h4 className="font-bold" style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)", letterSpacing: "var(--nv-tracking-wide)" }}>
          {a.decisionsTitle.replace("{pct}", threshold)}
        </h4>
        {decisions.length === 0 ? (
          <p style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)" }}>{a.noDecisions}</p>
        ) : (
          <ul className="flex flex-col gap-1.5">
            {decisions.map((h) => <DecisionRow key={`${h.period}:${h.market}`} h={h} />)}
          </ul>
        )}
        <p style={{ fontSize: "var(--nv-text-2xs)", color: "var(--nv-text-tertiary)" }}>
          {a.decisionRule.replace(/\{pct\}/g, threshold).replace("{min}", String(view.risky_below_n))}
        </p>
      </section>
    );
  }
  // Eski (live-arch-v1) kayıtlı maçlar: arşiv başına işaretler, aynı seçim tek satırda
  const groups = groupHighlights(view.highlights);
  return (
    <section className="space-y-1.5" aria-label={a.highlightsTitle.replace("{pct}", threshold)}>
      <h4 className="font-bold" style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)", letterSpacing: "var(--nv-tracking-wide)" }}>
        {a.highlightsTitle.replace("{pct}", threshold)}
      </h4>
      {groups.length === 0 ? (
        <p style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)" }}>{a.noHighlights.replace("{pct}", threshold)}</p>
      ) : (
        <ul className="flex flex-col gap-1.5">
          {groups.map((g) => (
            <li
              key={g.key}
              className="flex flex-wrap items-center gap-x-2 gap-y-1 px-2.5 py-1.5"
              style={{
                borderRadius: "var(--nv-radius-md)",
                backgroundColor: g.risky ? "var(--nv-bg-elevated)" : "var(--nv-accent-green-dim)",
                border: "1px solid var(--nv-border-subtle)",
              }}
            >
              <span style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-secondary)" }}>{liveMarketLabel(g.period, g.market, t)}</span>
              <span className="font-bold" style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-text-primary)" }}>{liveSelectionLabel(g.selection, t)}</span>
              <span className="font-extrabold" style={{ fontFamily: "var(--nv-font-mono)", fontSize: "var(--nv-text-sm)", color: g.risky ? "var(--nv-text-primary)" : "var(--nv-accent-green)" }}>
                {fmtPct(g.pct)}
              </span>
              <span className="flex-1" />
              {g.items.map((h) => (
                <span key={h.archive} className="inline-flex items-center gap-1" style={{ fontSize: "var(--nv-text-2xs)", color: "var(--nv-text-secondary)", fontVariantNumeric: "tabular-nums" }}>
                  <span className="font-semibold">{h.archive === "genel" ? t.evaluation.perf.archive_genel : h.label}</span>
                  <span style={{ color: "var(--nv-text-tertiary)" }}>({h.n})</span>
                  {h.pct !== g.pct && <span style={{ fontFamily: "var(--nv-font-mono)" }}>{fmtPct(h.pct)}</span>}
                  {h.historical && (
                    <span
                      className="px-1.5"
                      style={{ borderRadius: "var(--nv-radius-sm)", backgroundColor: "var(--nv-bg-surface)", color: "var(--nv-text-primary)", fontFamily: "var(--nv-font-mono)" }}
                      title={t.live.archive.historicalTooltip
                        .replace("{bucket}", h.historical.bucket)
                        .replace("{n}", String(h.historical.n))
                        + (h.historical.pooled ? ` ${t.live.archive.historicalPooled}` : "")}
                    >
                      {t.live.archive.historical.replace("{pct}", h.historical.pct.toFixed(0))}
                    </span>
                  )}
                  {h.risky && <RiskyBadge n={h.n} min={view.risky_below_n} />}
                </span>
              ))}
            </li>
          ))}
        </ul>
      )}
      {groups.some((g) => g.items.some((h) => h.historical)) && (
        <p style={{ fontSize: "var(--nv-text-2xs)", color: "var(--nv-text-tertiary)" }}>{a.historicalNote}</p>
      )}
    </section>
  );
}

function sourceLabel(src: Pick<LiveArchiveSource, "archive" | "label">, generalLabel: string): string {
  return src.archive === "genel" ? generalLabel : src.label;
}

export function ArchiveTable({ view }: { view: LiveArchiveView }) {
  const { t } = useLocale();
  const a = t.live.archive;
  const generalLabel = t.evaluation.perf.archive_genel;
  const rows: { period: string; market: string }[] = [];
  for (const src of view.sources) {
    for (const c of src.cells) {
      if (!rows.some((r) => r.period === c.period && r.market === c.market)) rows.push({ period: c.period, market: c.market });
    }
  }
  return (
    <section className="space-y-1.5">
      <h4 className="font-bold" style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)", letterSpacing: "var(--nv-tracking-wide)" }}>
        {a.tableTitle.replace("{home}", String(view.ht.home)).replace("{away}", String(view.ht.away))}
      </h4>
      <div style={{ overflowX: "auto" }}>
        <table className="w-full" style={{ borderCollapse: "collapse", fontSize: "var(--nv-text-2xs)", fontVariantNumeric: "tabular-nums", minWidth: 360 }}>
          <thead>
            <tr style={{ color: "var(--nv-text-tertiary)" }}>
              <th className="text-left font-medium py-1 pr-2">{a.market}</th>
              {view.sources.map((src) => (
                <th key={src.archive} className="text-right font-medium py-1 px-1 whitespace-nowrap">
                  <span className="font-semibold" style={{ color: "var(--nv-text-secondary)" }}>{sourceLabel(src, generalLabel)}</span>
                  <span> ({src.n})</span>
                  {src.risky && <span className="ml-1" aria-label={a.risky} title={a.riskyTooltip.replace("{n}", String(src.n)).replace("{min}", String(view.risky_below_n))} style={{ color: "var(--nv-accent-amber)" }}>⚠</span>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr><td colSpan={view.sources.length + 1} className="py-2" style={{ color: "var(--nv-text-tertiary)" }}>{a.noMatches}</td></tr>
            )}
            {rows.map((row) => (
              <tr key={`${row.period}:${row.market}`} style={{ borderTop: "1px solid var(--nv-border-subtle)" }}>
                <td className="py-1 pr-2 whitespace-nowrap" style={{ color: "var(--nv-text-secondary)" }}>{liveMarketLabel(row.period, row.market, t)}</td>
                {view.sources.map((src) => {
                  const cell = src.cells.find((c) => c.period === row.period && c.market === row.market);
                  if (!cell) return <td key={src.archive} className="text-right px-1" style={{ color: "var(--nv-text-tertiary)" }}>—</td>;
                  const strong = cell.pct >= view.threshold_pct;
                  return (
                    <td
                      key={src.archive}
                      className="text-right py-1 px-1 whitespace-nowrap"
                      title={Object.entries(cell.options).map(([k, v]) => `${liveSelectionLabel(k, t)} ${fmtPct(v)}`).join(" · ")}
                      style={{ color: strong ? (src.risky ? "var(--nv-text-primary)" : "var(--nv-accent-green)") : "var(--nv-text-secondary)", fontWeight: strong ? 700 : 400 }}
                    >
                      {liveSelectionLabel(cell.selection, t)} <span style={{ fontFamily: "var(--nv-font-mono)" }}>{fmtPct(cell.pct)}</span>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p style={{ fontSize: "var(--nv-text-2xs)", color: "var(--nv-text-tertiary)" }}>{a.generalNote}</p>
    </section>
  );
}

export function ArchiveMatchList({ matches }: { matches: LiveArchiveMatch[] }) {
  const { t, locale } = useLocale();
  const p = t.live.prediction;
  return (
    <ul className="space-y-1 pl-2 sm:pl-8 pb-1">
      {matches.map((m) => (
        <li key={m.match_id}>
          <Link
            href={`/analyze/${m.match_id}?home=${encodeURIComponent(m.home_team)}&away=${encodeURIComponent(m.away_team)}`}
            className="grid items-center gap-2 py-0.5 hover:underline"
            style={{ gridTemplateColumns: "64px minmax(0,1fr) auto", fontSize: "var(--nv-text-2xs)", fontVariantNumeric: "tabular-nums" }}
          >
            <span style={{ color: "var(--nv-text-tertiary)" }}>
              {m.kickoff_time ? new Date(m.kickoff_time).toLocaleDateString(locale === "en" ? "en-GB" : "tr-TR", { day: "2-digit", month: "2-digit", year: "2-digit" }) : "—"}
            </span>
            <span className="truncate" style={{ color: "var(--nv-text-secondary)" }}>
              {m.home_team} - {m.away_team}
            </span>
            <span className="flex items-center gap-2" style={{ fontFamily: "var(--nv-font-mono)" }}>
              <span style={{ color: "var(--nv-text-tertiary)" }}>{t.live.ht} {m.ht}</span>
              <span className="font-bold" style={{ color: "var(--nv-text-primary)" }}>{t.live.ft} {m.ft}</span>
              <span className="inline-flex items-center gap-1" style={{ color: "var(--nv-text-primary)" }}>
                <span aria-hidden="true" style={{ width: 6, height: 6, borderRadius: "50%", backgroundColor: OUTCOME_COLORS[m.result] }} />
                {m.result}
              </span>
              {m.similarity != null && (
                <span style={{ color: "var(--nv-text-tertiary)" }} title={p.similarity}>%{(m.similarity * 100).toFixed(1)}</span>
              )}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
