"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { createCoupon, getCoupons, getFixture, getMatchOdds } from "@/lib/api";
import type { CouponMarket, CouponPeriod, CouponView, MatchOdds } from "@/lib/api";
import type { FixtureMatch } from "@/lib/types";
import { formatTime } from "@/lib/dates";
import { useLocale } from "@/lib/locale-context";

type Dict = ReturnType<typeof useLocale>["t"];
type Draft = { match_id: string; home: string; away: string; period: CouponPeriod; market: CouponMarket; selection: string; line: number | null; odds: number };

function istanbulDate(offsetDays: number): string {
  const d = new Date(Date.now() + offsetDays * 86_400_000);
  return d.toLocaleDateString("sv-SE", { timeZone: "Europe/Istanbul" });
}

function num(value: number, digits: number, locale: string): string {
  const v = value.toFixed(digits);
  return locale === "en" ? v : v.replace(".", ",");
}

function pickLabel(period: CouponPeriod, market: CouponMarket, selection: string, line: number | null, t: Dict, locale: string): string {
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

function OddsPanel({ odds, draft, toggle, t, locale }: { odds: MatchOdds; draft: Draft[]; toggle: (d: Draft) => void; t: Dict; locale: string }) {
  const c = t.coupon;
  const isActive = (period: CouponPeriod, market: CouponMarket, selection: string) =>
    draft.some((d) => d.match_id === odds.match_id && d.period === period && d.market === market && d.selection === selection);
  const add = (period: CouponPeriod, market: CouponMarket, selection: string, price: number, line: number | null) =>
    toggle({ match_id: odds.match_id, home: odds.home_team, away: odds.away_team, period, market, selection, line, odds: price });

  return (
    <div className="space-y-3">
      {odds.live?.minute && (
        <p className="font-semibold" style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-live)" }}>
          {c.live.replace("{minute}", odds.live.minute).replace("{score}", odds.live.score ?? "")}
        </p>
      )}
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

const STATUS_COLOR: Record<CouponView["status"], string> = {
  pending: "var(--nv-text-tertiary)", won: "var(--nv-accent-green)", lost: "var(--nv-accent-red)", refund: "var(--nv-text-secondary)",
};
const OUTCOME_ICON: Record<string, { icon: string; color: string }> = {
  hit: { icon: "✓", color: "var(--nv-accent-green)" }, half_win: { icon: "½✓", color: "var(--nv-accent-green)" },
  miss: { icon: "✕", color: "var(--nv-accent-red)" }, half_loss: { icon: "½✕", color: "var(--nv-accent-amber)" },
  push: { icon: "↺", color: "var(--nv-text-tertiary)" }, void: { icon: "–", color: "var(--nv-text-tertiary)" },
};

function CouponCard({ coupon, t, locale }: { coupon: CouponView; t: Dict; locale: string }) {
  const c = t.coupon;
  return (
    <article className="nv-card p-3 space-y-2 min-w-0" style={coupon.mine ? { borderColor: "var(--nv-accent-blue)" } : undefined}>
      <header className="flex flex-wrap items-center gap-2" style={{ fontSize: "var(--nv-text-xs)" }}>
        <span className="font-bold" style={{ color: "var(--nv-text-primary)" }}>{coupon.username}</span>
        <span style={{ color: "var(--nv-text-tertiary)" }}>#{coupon.id} · {new Date(coupon.created_at).toLocaleString(locale === "en" ? "en-GB" : "tr-TR", { timeZone: "Europe/Istanbul", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}</span>
        <span className="flex-1" />
        <span className="font-semibold" style={{ color: STATUS_COLOR[coupon.status] }}>{c.status[coupon.status]}</span>
        <span className="font-extrabold" style={{ fontFamily: "var(--nv-font-mono)", color: "var(--nv-text-primary)" }}>{coupon.total_odds.toFixed(2)}</span>
      </header>
      {coupon.note && <p style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-secondary)" }}>{coupon.note}</p>}
      <ul className="space-y-1">
        {coupon.legs.map((leg, i) => {
          const out = leg.outcome ? OUTCOME_ICON[leg.outcome] : null;
          return (
            <li key={i} className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5" style={{ fontSize: "var(--nv-text-xs)" }}>
              <span className="min-w-0 truncate" style={{ color: "var(--nv-text-primary)" }}>{leg.home_team} - {leg.away_team}</span>
              <span style={{ color: "var(--nv-text-secondary)" }}>{pickLabel(leg.period, leg.market, leg.selection, leg.line, t, locale)}</span>
              {leg.live_minute && <span style={{ color: "var(--nv-live)" }}>{c.live.replace("{minute}", leg.live_minute).replace("{score}", leg.live_score ?? "")}</span>}
              <span className="flex-1" />
              {leg.score && <span style={{ fontFamily: "var(--nv-font-mono)", color: "var(--nv-text-tertiary)" }}>{leg.score}</span>}
              <span className="font-bold" style={{ fontFamily: "var(--nv-font-mono)", color: "var(--nv-text-primary)" }}>{leg.odds.toFixed(2)}</span>
              {out && leg.outcome && (
                <span className="font-semibold" style={{ color: out.color }} title={c.outcome[leg.outcome]}>
                  <span aria-hidden="true">{out.icon}</span> {c.outcome[leg.outcome]}
                </span>
              )}
            </li>
          );
        })}
      </ul>
      {coupon.return != null && coupon.status !== "lost" && (
        <p style={{ fontSize: "var(--nv-text-2xs)", color: "var(--nv-text-tertiary)" }}>{c.returnText.replace("{value}", num(coupon.return, 2, locale))}</p>
      )}
    </article>
  );
}

export default function KupondasPage() {
  const { t, locale } = useLocale();
  const c = t.coupon;
  const [day, setDay] = useState(0);
  // Yüklenen veri hangi güne / maça ait — "yükleniyor" durumu buradan türetilir
  const [fixtureState, setFixtureState] = useState<{ day: number; list: FixtureMatch[] } | null>(null);
  const [selected, setSelected] = useState<string>("");
  const [oddsResult, setOddsResult] = useState<{ id: string; odds: MatchOdds | null } | null>(null);
  const [draft, setDraft] = useState<Draft[]>([]);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const [scope, setScope] = useState<"all" | "mine">("all");
  const [coupons, setCoupons] = useState<CouponView[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    getFixture(istanbulDate(day))
      .then((list) => { if (!cancelled) setFixtureState({ day, list: list.filter((m) => m.status !== "pending") }); })
      .catch(() => { if (!cancelled) setFixtureState({ day, list: [] }); });
    return () => { cancelled = true; };
  }, [day]);
  const fixtures = fixtureState?.day === day ? fixtureState.list : null;

  useEffect(() => {
    if (!selected) return;
    let cancelled = false;
    getMatchOdds(selected)
      .then((o) => { if (!cancelled) setOddsResult({ id: selected, odds: o }); })
      .catch(() => { if (!cancelled) setOddsResult({ id: selected, odds: null }); });
    return () => { cancelled = true; };
  }, [selected]);
  const oddsReady = selected !== "" && oddsResult?.id === selected;
  const odds = oddsReady ? oddsResult!.odds : null;
  const oddsState: "idle" | "loading" | "error" = !selected ? "idle" : !oddsReady ? "loading" : odds ? "idle" : "error";

  const loadCoupons = useCallback(() => {
    getCoupons(scope).then((r) => setCoupons(r.coupons)).catch(() => setCoupons([]));
  }, [scope]);
  useEffect(() => { loadCoupons(); }, [loadCoupons]);

  const toggle = (d: Draft) => setDraft((prev) => {
    const same = (x: Draft) => x.match_id === d.match_id && x.period === d.period && x.market === d.market;
    const existing = prev.find(same);
    if (existing && existing.selection === d.selection) return prev.filter((x) => !same(x));
    return [...prev.filter((x) => !same(x)), d];
  });
  const total = useMemo(() => draft.reduce((acc, d) => acc * d.odds, 1), [draft]);

  async function save() {
    setSaving(true);
    setMessage(null);
    const res = await createCoupon(draft.map(({ match_id, period, market, selection }) => ({ match_id, period, market, selection })), note || null);
    setSaving(false);
    if (res.ok) {
      setDraft([]);
      setNote("");
      setMessage({ ok: true, text: c.saved });
      loadCoupons();
    } else {
      setMessage({ ok: false, text: res.message });
    }
  }

  const tabStyle = (active: boolean) => ({
    fontSize: "var(--nv-text-xs)", borderRadius: "var(--nv-radius-full)",
    backgroundColor: active ? "var(--nv-accent-blue-dim)" : "transparent",
    color: active ? "var(--nv-accent-blue)" : "var(--nv-text-secondary)",
    border: "1px solid var(--nv-border-subtle)",
  });

  return (
    <div className="flex flex-col h-full pb-[60px] md:pb-0">
      <div className="px-[var(--nv-page-gutter)] py-5 flex-shrink-0" style={{ borderBottom: "1px solid var(--nv-border)" }}>
        <h1 className="font-bold" style={{ fontSize: "var(--nv-text-xl)", color: "var(--nv-text-primary)" }}>{c.title}</h1>
        <p className="mt-1" style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)" }}>{c.subtitle}</p>
      </div>
      <div className="flex-1 overflow-y-auto">
        <div className="grid gap-4 px-[var(--nv-page-gutter)] py-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]" style={{ maxWidth: "var(--nv-max-content)" }}>
          <section className="nv-card p-3 space-y-3 min-w-0" aria-label={c.newCoupon}>
            <h2 className="font-bold" style={{ fontSize: "var(--nv-text-base)", color: "var(--nv-text-primary)" }}>{c.newCoupon}</h2>
            <div className="flex flex-wrap gap-1.5" role="tablist">
              {[c.today, c.tomorrow].map((label, i) => (
                <button key={label} role="tab" aria-selected={day === i} className="px-3 py-1" style={tabStyle(day === i)}
                  onClick={() => { setDay(i); setSelected(""); }}>{label}</button>
              ))}
            </div>
            {fixtures === null ? (
              <p style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)" }}>…</p>
            ) : fixtures.length === 0 ? (
              <p style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)" }}>{c.noMatches}</p>
            ) : (
              <label className="block space-y-1">
                <span style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-secondary)" }}>{c.pickMatch}</span>
                <select value={selected} onChange={(e) => setSelected(e.target.value)} className="w-full px-2 py-2"
                  style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-text-primary)", backgroundColor: "var(--nv-bg-elevated)", border: "1px solid var(--nv-border)", borderRadius: "var(--nv-radius-md)" }}>
                  <option value="">—</option>
                  {fixtures.map((m) => (
                    <option key={m.match_id} value={m.match_id}>
                      {m.kickoff_time ? `${formatTime(m.kickoff_time)} · ` : ""}{m.home_team} - {m.away_team}{m.status === "live" ? ` (${c.liveTag})` : ""}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {oddsState === "loading" && <p style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)" }}>{c.loadingOdds}</p>}
            {oddsState === "error" && <p style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-accent-red)" }}>{c.oddsError}</p>}
            {odds && oddsState === "idle" && <OddsPanel odds={odds} draft={draft} toggle={toggle} t={t} locale={locale} />}

            <div className="space-y-2 pt-2" style={{ borderTop: "1px solid var(--nv-border-subtle)" }}>
              <h3 className="font-bold" style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-text-primary)" }}>{c.draft}</h3>
              {draft.length === 0 ? (
                <p style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)" }}>{c.draftEmpty}</p>
              ) : (
                <ul className="space-y-1">
                  {draft.map((d) => (
                    <li key={`${d.match_id}:${d.period}:${d.market}`} className="flex items-baseline gap-2" style={{ fontSize: "var(--nv-text-xs)" }}>
                      <span className="min-w-0 truncate" style={{ color: "var(--nv-text-primary)" }}>{d.home} - {d.away}</span>
                      <span style={{ color: "var(--nv-text-secondary)" }}>{pickLabel(d.period, d.market, d.selection, d.line, t, locale)}</span>
                      <span className="flex-1" />
                      <span className="font-bold" style={{ fontFamily: "var(--nv-font-mono)" }}>{d.odds.toFixed(2)}</span>
                      <button type="button" onClick={() => toggle(d)} aria-label={c.remove} style={{ color: "var(--nv-text-tertiary)" }}>✕</button>
                    </li>
                  ))}
                </ul>
              )}
              {draft.length > 0 && (
                <>
                  <p className="font-semibold" style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-text-primary)" }}>
                    {c.totalOdds}: <span style={{ fontFamily: "var(--nv-font-mono)" }}>{total.toFixed(2)}</span>
                  </p>
                  <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={200} placeholder={c.note} className="w-full px-2 py-1.5"
                    style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-text-primary)", backgroundColor: "var(--nv-bg-elevated)", border: "1px solid var(--nv-border)", borderRadius: "var(--nv-radius-md)" }} />
                  <button type="button" disabled={saving} onClick={save} className="w-full py-2 font-semibold disabled:opacity-60"
                    style={{ fontSize: "var(--nv-text-sm)", backgroundColor: "var(--nv-accent-blue)", color: "var(--nv-text-on-accent)", borderRadius: "var(--nv-radius-md)" }}>
                    {saving ? c.saving : c.save}
                  </button>
                  <p style={{ fontSize: "var(--nv-text-2xs)", color: "var(--nv-text-tertiary)" }}>{c.frozenNote}</p>
                </>
              )}
              {message && (
                <p role="status" style={{ fontSize: "var(--nv-text-xs)", color: message.ok ? "var(--nv-accent-green)" : "var(--nv-accent-red)" }}>{message.text}</p>
              )}
            </div>
          </section>

          <section className="space-y-3 min-w-0" aria-label={c.title}>
            <div className="flex gap-1.5" role="tablist">
              {(["all", "mine"] as const).map((s) => (
                <button key={s} role="tab" aria-selected={scope === s} className="px-3 py-1" style={tabStyle(scope === s)} onClick={() => setScope(s)}>
                  {s === "all" ? c.all : c.mine}
                </button>
              ))}
            </div>
            {coupons === null ? (
              <p style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)" }}>…</p>
            ) : coupons.length === 0 ? (
              <p className="nv-card p-4" style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-text-tertiary)" }}>{c.noCoupons}</p>
            ) : (
              coupons.map((cp) => <CouponCard key={cp.id} coupon={cp} t={t} locale={locale} />)
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
