"use client";

import { useMemo, useState } from "react";
import type { CouponMatch } from "@/lib/api";
import { groupCouponMatches, isStarted } from "@/lib/coupon-picker";
import { formatTime } from "@/lib/dates";
import { leagueDisplay } from "@/lib/leagues";
import type { Dict } from "@/components/CouponOddsPanel";

/**
 * Aramalı, lige göre gruplu maç seçici (Sprint 94 J10). Başlamış maç varsayılan olarak gizli; gösterilirse
 * "başladı" rozetiyle seçilemez (kupon sadece maç öncesi — K2). "Analizli" rozeti: maçın tahmin analizi var.
 */
export default function CouponMatchPicker({ matches, selected, onSelect, now, t }: {
  matches: CouponMatch[]; selected: string; onSelect: (id: string) => void; now: number; t: Dict;
}) {
  const c = t.coupon;
  const [query, setQuery] = useState("");
  const [onlyAnalyzed, setOnlyAnalyzed] = useState(false);
  const [showStarted, setShowStarted] = useState(false);
  const groups = useMemo(
    () => groupCouponMatches(matches, { query, onlyAnalyzed, showStarted }, now),
    [matches, query, onlyAnalyzed, showStarted, now],
  );
  const count = groups.reduce((n, g) => n + g.matches.length, 0);
  const chip = (active: boolean) => ({
    fontSize: "var(--nv-text-2xs)", borderRadius: "var(--nv-radius-full)",
    border: `1px solid ${active ? "var(--nv-accent-blue)" : "var(--nv-border-subtle)"}`,
    color: active ? "var(--nv-accent-blue)" : "var(--nv-text-secondary)",
    backgroundColor: active ? "var(--nv-accent-blue-dim)" : "transparent",
  });

  return (
    <div className="space-y-2">
      <label className="block">
        <span className="sr-only">{c.pickMatch}</span>
        <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder={c.searchMatch}
          className="w-full px-2 py-2" autoComplete="off"
          style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-text-primary)", backgroundColor: "var(--nv-bg-elevated)", border: "1px solid var(--nv-border)", borderRadius: "var(--nv-radius-md)" }} />
      </label>
      <div className="flex flex-wrap items-center gap-1.5">
        <button type="button" aria-pressed={onlyAnalyzed} className="px-2.5 py-1" style={chip(onlyAnalyzed)}
          onClick={() => setOnlyAnalyzed((v) => !v)}>{c.onlyAnalyzed}</button>
        <button type="button" aria-pressed={showStarted} className="px-2.5 py-1" style={chip(showStarted)}
          onClick={() => setShowStarted((v) => !v)}>{c.showStarted}</button>
        <span className="flex-1" />
        <span style={{ fontSize: "var(--nv-text-2xs)", color: "var(--nv-text-tertiary)" }}>{c.matchCount.replace("{n}", String(count))}</span>
      </div>
      {count === 0 ? (
        <p style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)" }}>{c.noSearchResult}</p>
      ) : (
        <div className="max-h-80 overflow-y-auto space-y-2 pr-1" role="listbox" aria-label={c.pickMatch}>
          {groups.map((g) => {
            const { flag } = leagueDisplay(null, g.league);
            return (
              <div key={g.league ?? ""} role="group" aria-label={g.league ?? c.unknownLeague}>
                <p className="sticky top-0 py-1 font-semibold truncate" style={{ fontSize: "var(--nv-text-2xs)", color: "var(--nv-text-tertiary)", backgroundColor: "var(--nv-bg-card)" }}>
                  <span aria-hidden="true">{flag}</span> {g.league ?? c.unknownLeague}
                </p>
                <ul className="space-y-0.5">
                  {g.matches.map((m) => {
                    const started = isStarted(m, now);
                    const active = m.match_id === selected;
                    return (
                      <li key={m.match_id}>
                        <button type="button" role="option" aria-selected={active} disabled={started}
                          onClick={() => onSelect(active ? "" : m.match_id)}
                          className="w-full flex items-center gap-2 px-2 py-1.5 text-left disabled:opacity-50 disabled:cursor-not-allowed"
                          style={{
                            fontSize: "var(--nv-text-xs)", borderRadius: "var(--nv-radius-md)",
                            backgroundColor: active ? "var(--nv-accent-blue-dim)" : "transparent",
                            border: `1px solid ${active ? "var(--nv-accent-blue)" : "transparent"}`,
                          }}>
                          <span style={{ fontFamily: "var(--nv-font-mono)", color: "var(--nv-text-tertiary)" }}>
                            {m.kickoff_time ? formatTime(m.kickoff_time) : "—"}
                          </span>
                          <span className="min-w-0 flex-1 truncate" style={{ color: "var(--nv-text-primary)" }}>{m.home_team} - {m.away_team}</span>
                          {m.analyzed && <span style={{ color: "var(--nv-accent-green)", fontSize: "var(--nv-text-2xs)" }}>{c.analyzedTag}</span>}
                          {started && <span style={{ color: "var(--nv-live)", fontSize: "var(--nv-text-2xs)" }}>{c.startedTag}</span>}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
