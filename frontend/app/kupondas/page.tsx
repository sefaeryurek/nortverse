"use client";
import { istanbulDate, ISTANBUL_TZ } from "@/lib/dates";

import { fmtNum } from "@/lib/format";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createCoupon, getCouponMatches, getCoupons, getMatchOdds } from "@/lib/api";
import type { CouponLegLive, CouponMatch, CouponOddsChange, CouponView, MatchOdds } from "@/lib/api";
import { useLocale } from "@/lib/locale-context";
import { hasStarted, num, OddsPanel, pickLabel, priceFor } from "@/components/CouponOddsPanel";
import CouponMatchPicker from "@/components/CouponMatchPicker";
import CouponLeaderboard from "@/components/CouponLeaderboard";
import type { Dict, Draft } from "@/components/CouponOddsPanel";

function istanbulDay(offsetDays: number): string {
  const d = new Date(Date.now() + offsetDays * 86_400_000);
  return istanbulDate(d);
}

const STATUS_COLOR: Record<CouponView["status"], string> = {
  pending: "var(--nv-text-tertiary)", won: "var(--nv-accent-green)", lost: "var(--nv-accent-red)", refund: "var(--nv-text-secondary)",
  partial_loss: "var(--nv-accent-amber)",
};
const DRAFT_REFRESH_MS = 60_000;  // 10 bacakta dakikada 10 istek: kullanıcı başına oran sınırının (20) altında

function newKey(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
}
const OUTCOME_ICON: Record<string, { icon: string; color: string }> = {
  hit: { icon: "✓", color: "var(--nv-accent-green)" }, half_win: { icon: "½✓", color: "var(--nv-accent-green)" },
  miss: { icon: "✕", color: "var(--nv-accent-red)" }, half_loss: { icon: "½✕", color: "var(--nv-accent-amber)" },
  push: { icon: "↺", color: "var(--nv-text-tertiary)" }, void: { icon: "–", color: "var(--nv-text-tertiary)" },
};
const LIVE_COLOR: Record<CouponLegLive["state"], string> = {
  winning: "var(--nv-accent-green)", level: "var(--nv-text-secondary)", losing: "var(--nv-accent-red)",
};
const LIVE_REFRESH_MS = 45_000;  // canlı bacak varken kupon listesi (pano 45 sn'de bir tazelenir)

/** Bacağın anlık durumu (Sprint 94 J8): dakika · skor · şu an tutuyor/tutmuyor. */
function LiveLeg({ live, t }: { live: CouponLegLive; t: Dict }) {
  const c = t.coupon;
  const minute = live.phase === "ht" || live.minute === "HT" ? c.halftime : live.minute ? c.liveMinute.replace("{minute}", live.minute) : null;
  return (
    <span className="inline-flex items-center gap-1.5" style={{ fontSize: "var(--nv-text-2xs)" }}>
      {live.status === "live" && <span className="nv-live-pulse" aria-hidden="true" style={{ width: 6, height: 6, borderRadius: 9999, backgroundColor: "var(--nv-live)" }} />}
      {minute && <span style={{ color: "var(--nv-live)" }}>{minute}</span>}
      <span style={{ fontFamily: "var(--nv-font-mono)", color: "var(--nv-text-primary)" }}>{live.period_score}</span>
      <span className="font-semibold" style={{ color: LIVE_COLOR[live.state] }}>{live.period_over ? c.periodOver : c.liveState[live.state]}</span>
    </span>
  );
}

function CouponCard({ coupon, t, locale }: { coupon: CouponView; t: Dict; locale: string }) {
  const c = t.coupon;
  return (
    <article className="nv-card p-3 space-y-2 min-w-0" style={coupon.mine ? { borderColor: "var(--nv-accent-blue)" } : undefined}>
      <header className="flex flex-wrap items-center gap-2" style={{ fontSize: "var(--nv-text-xs)" }}>
        <span className="font-bold" style={{ color: "var(--nv-text-primary)" }}>{coupon.username}</span>
        <span style={{ color: "var(--nv-text-tertiary)" }}>#{coupon.id} · {new Date(coupon.created_at).toLocaleString(locale === "en" ? "en-GB" : "tr-TR", { timeZone: ISTANBUL_TZ, day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}</span>
        <span className="flex-1" />
        {coupon.live_state && (
          <span className="font-semibold" style={{ color: LIVE_COLOR[coupon.live_state] }}>{c.couponLive[coupon.live_state]}</span>
        )}
        <span className="font-semibold" style={{ color: STATUS_COLOR[coupon.status] }}>{c.status[coupon.status]}</span>
        <span className="font-extrabold" style={{ fontFamily: "var(--nv-font-mono)", color: "var(--nv-text-primary)" }}>{fmtNum(coupon.total_odds, 2)}</span>
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
              {leg.live && !leg.outcome && <LiveLeg live={leg.live} t={t} />}
              <span className="flex-1" />
              {leg.score && <span style={{ fontFamily: "var(--nv-font-mono)", color: "var(--nv-text-tertiary)" }}>{leg.score}</span>}
              <span className="font-bold" style={{ fontFamily: "var(--nv-font-mono)", color: "var(--nv-text-primary)" }}>{fmtNum(leg.odds, 2)}</span>
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
  const [fixtureState, setFixtureState] = useState<{ day: number; list: CouponMatch[]; error: string | null } | null>(null);
  const [selected, setSelected] = useState<string>("");
  const [oddsResult, setOddsResult] = useState<{ id: string; odds: MatchOdds | null } | null>(null);
  const [draft, setDraft] = useState<Draft[]>([]);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const [scope, setScope] = useState<"all" | "mine" | "stats">("all");
  const [coupons, setCoupons] = useState<CouponView[] | null>(null);
  // Hata ve boş durum ayrı (Sprint 94 L1): eskiden yükleme hatası "Henüz kupon yok" gibi görünüyordu
  const [couponsError, setCouponsError] = useState<string | null>(null);
  const [changes, setChanges] = useState<CouponOddsChange[] | null>(null);
  // Aynı gönderim için aynı anahtar (çift tıklama / ağ tekrarı ikinci kupon yazmaz); başarı ya da onaydan sonra yenilenir
  const idemKey = useRef<string>("");
  // Başlama saati geçen maç seçilemesin diye saat 30 sn'de bir yenilenir
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    let cancelled = false;
    getCouponMatches(istanbulDay(day))
      .then((list) => { if (!cancelled) setFixtureState({ day, list, error: null }); })
      .catch((err: unknown) => {
        if (!cancelled) setFixtureState({ day, list: [], error: err instanceof Error ? err.message : "" });
      });
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
    if (scope === "stats") return;
    getCoupons(scope)
      .then((r) => { setCoupons(r.coupons); setCouponsError(null); })
      .catch((err: unknown) => { setCoupons([]); setCouponsError(err instanceof Error ? err.message : ""); });
  }, [scope]);
  useEffect(() => { loadCoupons(); }, [loadCoupons]);
  // Başlamış ve sonuçlanmamış bacak varken liste kendini yeniler (Sprint 94 J8)
  const hasLive = useMemo(() => (coupons ?? []).some((cp) => cp.status === "pending"
    && cp.legs.some((l) => !l.outcome && (l.live != null || hasStarted(l.kickoff_time, now)))), [coupons, now]);
  useEffect(() => {
    if (!hasLive) return;
    const id = setInterval(loadCoupons, LIVE_REFRESH_MS);
    return () => clearInterval(id);
  }, [hasLive, loadCoupons]);

  // Maç başına tek seçim (K3): aynı maçtan başka bir seçim öncekinin yerine geçer
  const toggle = (d: Draft) => setDraft((prev) => {
    const existing = prev.find((x) => x.match_id === d.match_id);
    const same = existing && existing.period === d.period && existing.market === d.market && existing.selection === d.selection;
    const rest = prev.filter((x) => x.match_id !== d.match_id);
    return same ? rest : [...rest, d];
  });
  const total = useMemo(() => draft.reduce((acc, d) => acc * d.odds, 1), [draft]);

  // Taslaktaki oranlar 60 sn'de bir tazelenir (kayıt anındaki oran gösterilenden çok farklı olmasın)
  const draftIds = useMemo(() => [...new Set(draft.map((d) => d.match_id))].sort().join(","), [draft]);
  useEffect(() => {
    if (!draftIds) return;
    let cancelled = false;
    const refresh = async () => {
      const ids = draftIds.split(",");
      const fresh = await Promise.all(ids.map((id) => getMatchOdds(id).catch(() => null)));
      if (cancelled) return;
      const byId = new Map(ids.map((id, i) => [id, fresh[i]]));
      setDraft((prev) => prev.map((d) => {
        const o = byId.get(d.match_id);
        if (!o) return d;
        const p = priceFor(o, d);
        return p ? { ...d, odds: p.odds, line: p.line, unavailable: false } : { ...d, unavailable: true };
      }));
    };
    const id = setInterval(refresh, DRAFT_REFRESH_MS);
    return () => { cancelled = true; clearInterval(id); };
  }, [draftIds]);

  async function save(current: Draft[] = draft) {
    setSaving(true);
    setMessage(null);
    setChanges(null);
    if (!idemKey.current) idemKey.current = newKey();
    const res = await createCoupon(
      current.map(({ match_id, period, market, selection, line, odds: seen }) => ({ match_id, period, market, selection, line, seen_odds: seen })),
      note || null, idemKey.current,
    );
    setSaving(false);
    if (res.ok) {
      idemKey.current = "";
      setDraft([]);
      setNote("");
      setMessage({ ok: true, text: c.saved });
      loadCoupons();
    } else if (res.changes && res.changes.length) {
      idemKey.current = "";
      setChanges(res.changes);
    } else {
      setMessage({ ok: false, text: res.message });
    }
  }

  // Kullanıcı yeni oranları onayladı: taslak güncellenir ve yeni oranlarla tekrar gönderilir
  function acceptChanges() {
    if (!changes) return;
    const updated = draft.map((d) => {
      const ch = changes.find((x) => x.match_id === d.match_id && x.period === d.period && x.market === d.market && x.selection === d.selection);
      return ch ? { ...d, odds: ch.new_odds, line: ch.new_line ?? d.line } : d;
    });
    setDraft(updated);
    void save(updated);
  }

  const tabStyle = (active: boolean) => ({
    fontSize: "var(--nv-text-xs)", borderRadius: "var(--nv-radius-full)",
    backgroundColor: active ? "var(--nv-accent-blue-dim)" : "transparent",
    color: active ? "var(--nv-accent-blue)" : "var(--nv-text-secondary)",
    border: "1px solid var(--nv-border-subtle)",
  });

  return (
    <div className="flex flex-col h-full pb-[var(--nv-mobile-bottom)] md:pb-0">
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
            ) : fixtureState?.error != null ? (
              <p role="alert" style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-accent-red)" }}>{fixtureState.error || c.loadFailed}</p>
            ) : fixtures.length === 0 ? (
              <p style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)" }}>{c.noMatches}</p>
            ) : (
              <CouponMatchPicker matches={fixtures} selected={selected} onSelect={setSelected} now={now} t={t} />
            )}
            {oddsState === "loading" && <p style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)" }}>{c.loadingOdds}</p>}
            {oddsState === "error" && <p style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-accent-red)" }}>{c.oddsError}</p>}
            {odds && oddsState === "idle" && (
              <OddsPanel odds={odds} kickoff={fixtures?.find((m) => m.match_id === odds.match_id)?.kickoff_time ?? null}
                now={now} draft={draft} toggle={toggle} t={t} locale={locale} />
            )}

            <div className="space-y-2 pt-2" style={{ borderTop: "1px solid var(--nv-border-subtle)" }}>
              <h3 className="font-bold" style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-text-primary)" }}>{c.draft}</h3>
              {draft.length === 0 ? (
                <p style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)" }}>{c.draftEmpty}</p>
              ) : (
                <ul className="space-y-1">
                  {draft.map((d) => (
                    <li key={`${d.match_id}:${d.period}:${d.market}`} className="flex items-baseline gap-2" style={{ fontSize: "var(--nv-text-xs)", opacity: d.unavailable ? 0.5 : 1 }}>
                      <span className="min-w-0 truncate" style={{ color: "var(--nv-text-primary)" }}>{d.home} - {d.away}</span>
                      <span style={{ color: "var(--nv-text-secondary)" }}>{pickLabel(d.period, d.market, d.selection, d.line, t, locale)}</span>
                      {d.unavailable && <span style={{ color: "var(--nv-accent-amber)" }}>{c.unavailable}</span>}
                      <span className="flex-1" />
                      <span className="font-bold" style={{ fontFamily: "var(--nv-font-mono)" }}>{fmtNum(d.odds, 2)}</span>
                      <button type="button" onClick={() => toggle(d)} aria-label={c.remove} style={{ color: "var(--nv-text-tertiary)" }}>✕</button>
                    </li>
                  ))}
                </ul>
              )}
              {draft.length > 0 && (
                <>
                  <p className="font-semibold" style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-text-primary)" }}>
                    {c.totalOdds}: <span style={{ fontFamily: "var(--nv-font-mono)" }}>{fmtNum(total, 2)}</span>
                  </p>
                  <input value={note} onChange={(e) => setNote(e.target.value)} maxLength={200} placeholder={c.note} className="w-full px-2 py-1.5"
                    style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-text-primary)", backgroundColor: "var(--nv-bg-elevated)", border: "1px solid var(--nv-border)", borderRadius: "var(--nv-radius-md)" }} />
                  <button type="button" disabled={saving || draft.some((d) => d.unavailable)} onClick={() => void save()} className="w-full py-2 font-semibold disabled:opacity-60"
                    style={{ fontSize: "var(--nv-text-sm)", backgroundColor: "var(--nv-accent-blue)", color: "var(--nv-text-on-accent)", borderRadius: "var(--nv-radius-md)" }}>
                    {saving ? c.saving : c.save}
                  </button>
                  <p style={{ fontSize: "var(--nv-text-2xs)", color: "var(--nv-text-tertiary)" }}>{c.frozenNote}</p>
                </>
              )}
              {changes && (
                <div role="alert" className="space-y-1.5 p-2" style={{ fontSize: "var(--nv-text-xs)", border: "1px solid var(--nv-accent-amber)", borderRadius: "var(--nv-radius-md)" }}>
                  <p className="font-semibold" style={{ color: "var(--nv-accent-amber)" }}>{c.oddsChanged}</p>
                  <ul className="space-y-0.5">
                    {changes.map((ch) => (
                      <li key={`${ch.match_id}:${ch.period}:${ch.market}:${ch.selection}`} style={{ color: "var(--nv-text-secondary)" }}>
                        {ch.home_team} - {ch.away_team} · {pickLabel(ch.period, ch.market, ch.selection, ch.new_line ?? ch.old_line, t, locale)}:{" "}
                        <span style={{ fontFamily: "var(--nv-font-mono)" }}>{ch.old_odds != null ? fmtNum(ch.old_odds, 2) : "—"} → {fmtNum(ch.new_odds, 2)}</span>
                        {ch.old_line != null && ch.new_line != null && ch.old_line !== ch.new_line && ` (${c.lineChanged.replace("{old}", String(ch.old_line)).replace("{new}", String(ch.new_line))})`}
                      </li>
                    ))}
                  </ul>
                  <div className="flex gap-2">
                    <button type="button" disabled={saving} onClick={acceptChanges} className="px-3 py-1 font-semibold"
                      style={{ backgroundColor: "var(--nv-accent-blue)", color: "var(--nv-text-on-accent)", borderRadius: "var(--nv-radius-md)" }}>{c.acceptNewOdds}</button>
                    <button type="button" onClick={() => setChanges(null)} className="px-3 py-1"
                      style={{ color: "var(--nv-text-secondary)", border: "1px solid var(--nv-border)", borderRadius: "var(--nv-radius-md)" }}>{c.cancel}</button>
                  </div>
                </div>
              )}
              {message && (
                <p role="status" style={{ fontSize: "var(--nv-text-xs)", color: message.ok ? "var(--nv-accent-green)" : "var(--nv-accent-red)" }}>{message.text}</p>
              )}
            </div>
          </section>

          <section className="space-y-3 min-w-0" aria-label={c.title}>
            <div className="flex gap-1.5" role="tablist">
              {(["all", "mine", "stats"] as const).map((s) => (
                <button key={s} role="tab" aria-selected={scope === s} className="px-3 py-1" style={tabStyle(scope === s)} onClick={() => setScope(s)}>
                  {s === "all" ? c.all : s === "mine" ? c.mine : c.leaderboard}
                </button>
              ))}
            </div>
            {scope === "stats" ? (
              <CouponLeaderboard t={t} locale={locale} />
            ) : coupons === null ? (
              <p style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)" }}>…</p>
            ) : couponsError !== null ? (
              <div className="nv-card p-4 flex flex-wrap items-center gap-3" role="alert">
                <p style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-accent-red)" }}>{couponsError || c.loadFailed}</p>
                <button type="button" className="px-3 py-1" style={tabStyle(false)} onClick={loadCoupons}>{t.common.retry}</button>
              </div>
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
