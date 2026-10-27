import type { Metadata } from "next";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import Link from "next/link";
import DayTabs from "@/components/DayTabs";
import { getHtStrategy } from "@/lib/api";
import type { HtMatch, HtOption } from "@/lib/api";
import { formatTime, resolvePageDate } from "@/lib/dates";
import { type Dictionary, type Locale, COOKIE_NAME, defaultLocale, getDictionary, isLocale } from "@/lib/i18n";
import { leagueDisplay } from "@/lib/leagues";
import { SHADOW_COOKIE, shadowFromCookie } from "@/lib/shadow";

export const metadata: Metadata = {
  title: "İY Oranları",
  description: "İlk yarı pazarları: oran ve ima ettiği olasılık",
};

interface Props {
  searchParams: Promise<{ date?: string | string[] }>;
}

function pct(value: number, locale: Locale): string {
  const v = value.toFixed(1);
  return locale === "en" ? `${v}%` : `%${v.replace(".", ",")}`;
}

function lineText(line: number, locale: Locale): string {
  const v = String(line);
  return locale === "en" ? v : v.replace(".", ",");
}

function optionLabel(o: HtOption, t: Dictionary, locale: Locale): string {
  if (o.market === "result") return `${t.ht.result} ${o.selection}`;
  return `${t.ht.total.replace("{line}", lineText(o.line ?? 0, locale))} ${o.selection === "over" ? t.ht.over : t.ht.under}`;
}

function lineHint(line: number, t: Dictionary, locale: Locale): string | undefined {
  const quarter = Math.round(line * 4) % 4;
  if (quarter === 1 || quarter === 3) {
    return t.ht.quarterHint.replace("{lo}", lineText(line - 0.25, locale)).replace("{hi}", lineText(line + 0.25, locale));
  }
  if (quarter === 0) return t.ht.integerHint.replace("{line}", lineText(line, locale));
  return undefined;
}

const OUTCOME: Record<NonNullable<HtOption["outcome"]>, { icon: string; color: string; key: "won" | "lost" | "push" | "half" }> = {
  hit: { icon: "✓", color: "var(--nv-accent-green)", key: "won" },
  miss: { icon: "✕", color: "var(--nv-accent-red)", key: "lost" },
  push: { icon: "↺", color: "var(--nv-text-tertiary)", key: "push" },
  half: { icon: "½", color: "var(--nv-accent-amber)", key: "half" },
};

function OptionCell({ o, label, strongest, t, locale }: { o: HtOption; label: string; strongest: boolean; t: Dictionary; locale: Locale }) {
  const out = o.outcome ? OUTCOME[o.outcome] : null;
  return (
    <div
      className="flex flex-col gap-0.5 px-2.5 py-1.5 min-w-0"
      style={{
        borderRadius: "var(--nv-radius-md)",
        backgroundColor: strongest ? "var(--nv-accent-green-dim)" : "var(--nv-bg-elevated)",
        border: strongest ? "1px solid var(--nv-accent-green)" : "1px solid var(--nv-border-subtle)",
      }}
    >
      <div className="flex items-baseline justify-between gap-2">
        <span className="font-semibold truncate" style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-secondary)" }}>{label}</span>
        <span className="font-extrabold" style={{ fontFamily: "var(--nv-font-mono)", fontSize: "var(--nv-text-sm)", color: "var(--nv-text-primary)" }}>
          {o.odds.toFixed(2)}
        </span>
      </div>
      <div className="flex items-baseline justify-between gap-2" style={{ fontSize: "var(--nv-text-2xs)", fontVariantNumeric: "tabular-nums" }}>
        <span className="font-bold" style={{ fontFamily: "var(--nv-font-mono)", color: strongest ? "var(--nv-accent-green)" : "var(--nv-text-primary)" }}>
          {pct(o.pct, locale)}
        </span>
        {out ? (
          <span className="font-semibold" style={{ color: out.color }}>
            <span aria-hidden="true">{out.icon}</span> {t.ht[out.key]}
          </span>
        ) : o.model_pct != null ? (
          <span title={t.ht.modelTip} style={{ color: "var(--nv-text-tertiary)" }}>
            {t.ht.model.replace("{pct}", locale === "en" ? o.model_pct.toFixed(1) : o.model_pct.toFixed(1).replace(".", ","))}
          </span>
        ) : null}
      </div>
    </div>
  );
}

function MatchCard({ match, t, locale }: { match: HtMatch; t: Dictionary; locale: Locale }) {
  const { flag, short } = leagueDisplay(null, match.league_name);
  const strongest = match.options[0];
  const result = (["1", "X", "2"] as const)
    .map((sel) => match.options.find((o) => o.market === "result" && o.selection === sel))
    .filter((o): o is HtOption => o != null);
  const totals = (["over", "under"] as const)
    .map((sel) => match.options.find((o) => o.market === "ou" && o.selection === sel))
    .filter((o): o is HtOption => o != null);
  const totalLine = totals[0]?.line;
  const isStrongest = (o: HtOption) => o.market === strongest.market && o.selection === strongest.selection;
  const margin = match.options.find((o) => o.market === "result")?.margin_pct;

  return (
    <article className="nv-card p-3 space-y-2.5 min-w-0">
      <header className="flex flex-wrap items-center gap-2" style={{ fontSize: "var(--nv-text-xs)" }}>
        <span aria-hidden="true">{flag}</span>
        <span style={{ color: "var(--nv-text-tertiary)" }}>{short}{match.kickoff_time ? ` · ${formatTime(match.kickoff_time)}` : ""}</span>
        {match.shadow && (
          <span className="px-1.5 font-semibold" title={t.common.shadowBadgeHint}
            style={{ fontSize: "var(--nv-text-2xs)", borderRadius: "var(--nv-radius-sm)", backgroundColor: "var(--nv-accent-amber-dim)", color: "var(--nv-accent-amber)" }}>
            {t.common.shadowBadge}
          </span>
        )}
        <span className="flex-1" />
        {match.final_ht && (
          <span className="font-bold" style={{ fontFamily: "var(--nv-font-mono)", color: "var(--nv-text-primary)" }}>{t.ht.finalHt} {match.final_ht}</span>
        )}
      </header>
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <Link href={`/analyze/${match.match_id}?home=${encodeURIComponent(match.home_team)}&away=${encodeURIComponent(match.away_team)}`}
          className="font-semibold hover:underline min-w-0" style={{ fontSize: "var(--nv-text-base)", color: "var(--nv-text-primary)" }}>
          {match.home_team} - {match.away_team}
        </Link>
        <span style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-secondary)" }}>
          {t.ht.strongest}: <b style={{ color: "var(--nv-accent-green)" }}>{optionLabel(strongest, t, locale)}</b>{" "}
          <span style={{ fontFamily: "var(--nv-font-mono)" }}>{pct(strongest.pct, locale)} · {strongest.odds.toFixed(2)}</span>
        </span>
      </div>

      {result.length > 0 && (
        <div className="grid grid-cols-3 gap-1.5">
          {result.map((o) => <OptionCell key={o.selection} o={o} label={`${t.ht.result} ${o.selection}`} strongest={isStrongest(o)} t={t} locale={locale} />)}
        </div>
      )}
      {totals.length > 0 && totalLine != null && (
        <div className="space-y-1">
          <div className="grid grid-cols-2 gap-1.5">
            {totals.map((o) => (
              <OptionCell key={o.selection} o={o} t={t} locale={locale} strongest={isStrongest(o)}
                label={optionLabel(o, t, locale)} />
            ))}
          </div>
          {lineHint(totalLine, t, locale) && (
            <p style={{ fontSize: "var(--nv-text-2xs)", color: "var(--nv-text-tertiary)" }}>{lineHint(totalLine, t, locale)}</p>
          )}
        </div>
      )}
      <div className="flex flex-wrap gap-x-3 gap-y-0.5" style={{ fontSize: "var(--nv-text-2xs)", color: "var(--nv-text-tertiary)" }}>
        {margin != null && <span>{t.ht.margin.replace("{pct}", locale === "en" ? margin.toFixed(1) : margin.toFixed(1).replace(".", ","))}</span>}
        {match.odds_at && <span>{t.ht.oddsTime.replace("{time}", formatTime(new Date(match.odds_at * 1000).toISOString()))}</span>}
        {match.expected_goals && (
          <span>{t.ht.expectedGoals}: <span style={{ fontFamily: "var(--nv-font-mono)" }}>{match.expected_goals.home.toFixed(2)} – {match.expected_goals.away.toFixed(2)}</span></span>
        )}
      </div>
    </article>
  );
}

async function MatchList({ date, locale, shadow }: { date: string; locale: Locale; shadow: boolean }) {
  const t = getDictionary(locale);
  let matches: HtMatch[] = [];
  try {
    // Önbellekte eski biçimli yanıt kalmış olabilir → seçeneği olmayan maç gösterilmez
    matches = ((await getHtStrategy(date, shadow)).matches ?? []).filter((m) => Array.isArray(m.options) && m.options.length > 0);
  } catch {
    return <p className="nv-card p-4 m-4" style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-accent-red)" }}>{t.common.loadError}</p>;
  }
  if (matches.length === 0) {
    return <p className="nv-card p-6 m-4 text-center" style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-text-tertiary)" }}>{t.ht.empty}</p>;
  }
  // Sunucu en güçlü seçeneğe göre sıralı gönderir
  return (
    <div className="grid gap-3 px-[var(--nv-page-gutter)] py-4" style={{ maxWidth: "var(--nv-max-content)" }}>
      {matches.map((m) => <MatchCard key={m.match_id} match={m} t={t} locale={locale} />)}
    </div>
  );
}

export default async function IyPage({ searchParams }: Props) {
  const params = await searchParams;
  const today = new Date().toLocaleDateString("sv-SE", { timeZone: "Europe/Istanbul" });
  const date = resolvePageDate(params.date, today, true);
  if (date === null) redirect("/iy");
  const cookieStore = await cookies();
  const raw = cookieStore.get(COOKIE_NAME)?.value;
  const locale: Locale = isLocale(raw) ? raw : defaultLocale;
  const shadow = shadowFromCookie(cookieStore.get(SHADOW_COOKIE)?.value);
  const t = getDictionary(locale);

  return (
    <div className="flex flex-col h-full pb-[60px] md:pb-0">
      <div className="px-[var(--nv-page-gutter)] py-5 flex-shrink-0" style={{ borderBottom: "1px solid var(--nv-border)" }}>
        <h1 className="font-bold" style={{ fontSize: "var(--nv-text-xl)", color: "var(--nv-text-primary)", letterSpacing: "var(--nv-tracking-tight)" }}>
          {t.ht.title}
        </h1>
        <p className="mt-1" style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)" }}>{t.ht.subtitle}</p>
        <p className="mt-2" style={{ fontSize: "var(--nv-text-2xs)", color: "var(--nv-text-tertiary)", maxWidth: "65ch" }}>{t.ht.note}</p>
      </div>
      <DayTabs referenceDate={today} activeDate={date} basePath="/iy" locale={locale} />
      <div className="flex-1 overflow-y-auto">
        <Suspense fallback={<p className="p-6" style={{ color: "var(--nv-text-tertiary)" }}>…</p>}>
          <MatchList date={date} locale={locale} shadow={shadow} />
        </Suspense>
      </div>
    </div>
  );
}
