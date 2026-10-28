"use client";

import type { CouponMarket, CouponPeriod, MatchOdds } from "@/lib/api";
import type { useLocale } from "@/lib/locale-context";

export type Dict = ReturnType<typeof useLocale>["t"];
export type Draft = {
  match_id: string; home: string; away: string; period: CouponPeriod; market: CouponMarket; selection: string;
  line: number | null; odds: number;
  /** Taslak yenilenirken bu seçim artık açık değilse (maç başladı / pazar kapandı) */
  unavailable?: boolean;
};

/** Güncel oranlardan taslak seçiminin oranı ve çizgisi; pazar kapalıysa null. */
export function priceFor(odds: MatchOdds, d: Draft): { odds: number; line: number | null } | null {
  const m = odds.markets[d.period];
  if (!m || m.closed) return null;
  if (d.market === "ou") {
    const price = m.ou?.[d.selection as "over" | "under"];
    return m.ou && price ? { odds: price, line: m.ou.line } : null;
  }
  const table = d.market === "dc" ? m.dc : m.result;
  const price = table ? (table as Record<string, number>)[d.selection] : undefined;
  return price ? { odds: price, line: null } : null;
}

export function num(value: number, digits: number, locale: string): string {
  const v = value.toFixed(digits);
  return locale === "en" ? v : v.replace(".", ",");
}

export function pickLabel(period: CouponPeriod, market: CouponMarket, selection: string, line: number | null, t: Dict, locale: string): string {
  const c = t.coupon;
  const head = period === "ht" ? c.ht : c.ft;
  if (market === "ou") return `${head} ${c.ou.replace("{line}", num(line ?? 0, 2, locale).replace(/[.,]?0+$/, ""))} ${selection === "over" ? c.over : c.under}`;
  return `${head} ${market === "dc" ? c.dc : c.result} ${selection}`;
}

function OddsButton({ label, odds, active, onClick }: { label: string; odds: number; active: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className="flex flex-col items-center px-2 py-1.5 min-w-0 transition-colors"
      style={{
        borderRadius: "var(--nv-radius-md)",
        backgroundColor: active ? "var(--nv-accent-blue)" : "var(--nv-bg-elevated)",
        color: active ? "var(--nv-text-on-accent)" : "var(--nv-text-primary)",
        border: "1px solid var(--nv-border-subtle)",
      }}
    >
      <span style={{ fontSize: "var(--nv-text-2xs)", opacity: 0.8 }}>{label}</span>
      <span className="font-bold" style={{ fontFamily: "var(--nv-font-mono)", fontSize: "var(--nv-text-sm)" }}>{odds.toFixed(2)}</span>
    </button>
  );
}

/** Maç başladı mı (Sprint 94 K2: kupon sadece maç öncesi; sunucu da reddeder, bu yalnız ekran savunması). */
export function hasStarted(kickoff: string | null | undefined, now: number): boolean {
  if (!kickoff) return false;
  const t = Date.parse(kickoff);
  return Number.isFinite(t) && now >= t;
}

export function OddsPanel({ odds, kickoff, now, draft, toggle, t, locale }: {
  odds: MatchOdds; kickoff: string | null; now: number; draft: Draft[]; toggle: (d: Draft) => void; t: Dict; locale: string;
}) {
  const c = t.coupon;
  if (hasStarted(kickoff, now)) {
    return <p style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)" }}>{c.prematchOnly}</p>;
  }
  const isActive = (period: CouponPeriod, market: CouponMarket, selection: string) =>
    draft.some((d) => d.match_id === odds.match_id && d.period === period && d.market === market && d.selection === selection);
  const add = (period: CouponPeriod, market: CouponMarket, selection: string, price: number, line: number | null) =>
    toggle({ match_id: odds.match_id, home: odds.home_team, away: odds.away_team, period, market, selection, line, odds: price });

  return (
    <div className="space-y-3">
      {(["ft", "ht"] as const).map((period) => {
        const m = odds.markets[period];
        return (
          <section key={period} className="space-y-1.5">
            <h3 className="font-bold" style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)" }}>
              {period === "ft" ? c.ft : c.ht}{m.closed ? ` — ${m.closed}` : ""}
            </h3>
            {!m.closed && (
              <div className="grid grid-cols-3 gap-1.5">
                {m.result && (["1", "X", "2"] as const).map((s) => (
                  <OddsButton key={`r${s}`} label={`${c.result} ${s}`} odds={m.result![s]} active={isActive(period, "result", s)}
                    onClick={() => add(period, "result", s, m.result![s], null)} />
                ))}
                {m.dc && (["1X", "12", "X2"] as const).map((s) => (
                  <OddsButton key={`d${s}`} label={`${c.dc} ${s}`} odds={m.dc![s]} active={isActive(period, "dc", s)}
                    onClick={() => add(period, "dc", s, m.dc![s], null)} />
                ))}
                {m.ou && (["over", "under"] as const).map((s) => (
                  <OddsButton key={`o${s}`} label={pickLabel(period, "ou", s, m.ou!.line, t, locale).replace(`${period === "ht" ? c.ht : c.ft} `, "")}
                    odds={m.ou![s]} active={isActive(period, "ou", s)} onClick={() => add(period, "ou", s, m.ou![s], m.ou!.line)} />
                ))}
              </div>
            )}
          </section>
        );
      })}
    </div>
  );
}
