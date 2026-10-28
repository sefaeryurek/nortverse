"use client";

import { useCallback, useEffect, useState } from "react";
import { getCouponStats } from "@/lib/api";
import type { CouponUserStats } from "@/lib/api";
import { fmtNum } from "@/lib/format";
import { num } from "@/components/CouponOddsPanel";
import type { Dict } from "@/components/CouponOddsPanel";

/** Kupondaş puan tablosu (Sprint 94 J9): kullanıcı başına kupon, kazanan, bacak isabeti, 1 birim kâr ve ROI. */
export default function CouponLeaderboard({ t, locale }: { t: Dict; locale: string }) {
  const c = t.coupon;
  const [range, setRange] = useState<"week" | "all">("week");
  const [state, setState] = useState<{ range: string; users: CouponUserStats[] | null; error: string | null } | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getCouponStats(range)
      .then((r) => { if (!cancelled) setState({ range, users: r.users, error: null }); })
      .catch((err: unknown) => { if (!cancelled) setState({ range, users: null, error: err instanceof Error ? err.message : "" }); });
    return () => { cancelled = true; };
  }, [range, attempt]);
  const retry = useCallback(() => { setState(null); setAttempt((n) => n + 1); }, []);
  const current = state?.range === range ? state : null;

  const pctText = (v: number | null) => (v == null ? "—" : `%${num(v, 1, locale)}`);
  const signed = (v: number) => `${v > 0 ? "+" : ""}${num(v, 2, locale)}`;
  const chip = (active: boolean) => ({
    fontSize: "var(--nv-text-2xs)", borderRadius: "var(--nv-radius-full)",
    border: `1px solid ${active ? "var(--nv-accent-blue)" : "var(--nv-border-subtle)"}`,
    color: active ? "var(--nv-accent-blue)" : "var(--nv-text-secondary)",
    backgroundColor: active ? "var(--nv-accent-blue-dim)" : "transparent",
  });
  const th = { fontSize: "var(--nv-text-2xs)", color: "var(--nv-text-tertiary)", fontWeight: 600 } as const;

  return (
    <div className="nv-card p-3 space-y-3 min-w-0">
      <div className="flex flex-wrap gap-1.5">
        {(["week", "all"] as const).map((r) => (
          <button key={r} type="button" aria-pressed={range === r} className="px-2.5 py-1" style={chip(range === r)} onClick={() => setRange(r)}>
            {r === "week" ? c.week : c.allTime}
          </button>
        ))}
      </div>
      {current === null ? (
        <p style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)" }}>…</p>
      ) : current.error !== null ? (
        <div className="flex flex-wrap items-center gap-3" role="alert">
          <p style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-accent-red)" }}>{current.error || c.loadFailed}</p>
          <button type="button" className="px-3 py-1" style={chip(false)} onClick={retry}>{t.common.retry}</button>
        </div>
      ) : !current.users || current.users.length === 0 ? (
        <p style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-text-tertiary)" }}>{c.statsEmpty}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full" style={{ fontSize: "var(--nv-text-xs)", fontVariantNumeric: "tabular-nums" }}>
            <thead>
              <tr className="text-left">
                <th scope="col" className="py-1 pr-2" style={th}>#</th>
                <th scope="col" className="py-1 pr-2" style={th}>{c.statsUser}</th>
                <th scope="col" className="py-1 pr-2 text-right" style={th}>{c.statsCoupons}</th>
                <th scope="col" className="py-1 pr-2 text-right" style={th}>{c.statsWon}</th>
                <th scope="col" className="py-1 pr-2 text-right" style={th}>{c.statsLegHit}</th>
                <th scope="col" className="py-1 pr-2 text-right" style={th}>{c.statsProfit}</th>
                <th scope="col" className="py-1 pr-2 text-right" style={th}>{c.statsRoi}</th>
                <th scope="col" className="py-1 pr-2 text-right" style={th}>{c.statsAvgOdds}</th>
                <th scope="col" className="py-1 text-right" style={th}>{c.statsBest}</th>
              </tr>
            </thead>
            <tbody>
              {current.users.map((u, i) => (
                <tr key={u.username} style={{ borderTop: "1px solid var(--nv-border-subtle)" }}>
                  <td className="py-1.5 pr-2" style={{ color: "var(--nv-text-tertiary)" }}>{i + 1}</td>
                  <td className="py-1.5 pr-2 font-semibold whitespace-nowrap" style={{ color: "var(--nv-text-primary)" }}>{u.username}</td>
                  <td className="py-1.5 pr-2 text-right whitespace-nowrap" style={{ color: "var(--nv-text-primary)" }}>
                    {u.coupons}
                    {u.pending > 0 && (
                      <span className="block" style={{ fontSize: "var(--nv-text-2xs)", color: "var(--nv-text-tertiary)" }}>
                        {c.statsPending.replace("{n}", String(u.pending))}
                      </span>
                    )}
                  </td>
                  <td className="py-1.5 pr-2 text-right" style={{ color: "var(--nv-text-primary)" }}>{u.won}/{u.settled}</td>
                  <td className="py-1.5 pr-2 text-right" style={{ color: "var(--nv-text-secondary)" }}>{pctText(u.leg_hit_pct)}</td>
                  <td className="py-1.5 pr-2 text-right font-bold" style={{
                    fontFamily: "var(--nv-font-mono)",
                    color: u.profit > 0 ? "var(--nv-accent-green)" : u.profit < 0 ? "var(--nv-accent-red)" : "var(--nv-text-secondary)",
                  }}>{signed(u.profit)}</td>
                  <td className="py-1.5 pr-2 text-right" style={{ color: "var(--nv-text-secondary)" }}>{pctText(u.roi_pct)}</td>
                  <td className="py-1.5 pr-2 text-right" style={{ fontFamily: "var(--nv-font-mono)", color: "var(--nv-text-secondary)" }}>{fmtNum(u.avg_odds, 2)}</td>
                  <td className="py-1.5 text-right" style={{ fontFamily: "var(--nv-font-mono)", color: "var(--nv-text-secondary)" }}>
                    {u.best_won_odds != null ? fmtNum(u.best_won_odds, 2) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p style={{ fontSize: "var(--nv-text-2xs)", color: "var(--nv-text-tertiary)" }}>{c.statsNote}</p>
    </div>
  );
}
