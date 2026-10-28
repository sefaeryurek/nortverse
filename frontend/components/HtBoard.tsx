import Link from "next/link";
import { fmtNum } from "@/lib/format";
import { getHtStrategy } from "@/lib/api";
import type { HtMatch, HtOption } from "@/lib/api";
import { formatTime } from "@/lib/dates";
import { type Dictionary, type Locale, getDictionary } from "@/lib/i18n";
import { leagueDisplay } from "@/lib/leagues";
import { applyHtFilters, DEFAULT_FILTERS, filterHref, marketOptions, ODDS_DROP_MIN, oddsDrop, strongestOption } from "@/lib/ht-filters";
import type { HtFilters } from "@/lib/ht-filters";
import HtMinSlider from "@/components/HtMinSlider";

/**
 * İY oran panosu: maç kartları ve liste (Sprint 94 M3 — /iy sayfasından ayrıldı, test edilebilsin diye).
 * Sunucu bileşeni. Sprint 94 K-2: varsayılan sıra başlama saati, süzgeçler (zaman, pazar, lig, asgari olasılık),
 * kompakt satır (tıklayınca kart), başlamış/bitmiş maçlar altta katlı, açılıştan ≥%8 düşüş rozeti.
 */

function pct(value: number, locale: Locale): string {
  const v = fmtNum(value, 1);
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
          {fmtNum(o.odds, 2)}
        </span>
      </div>
      <div className="flex items-baseline justify-between gap-2" style={{ fontSize: "var(--nv-text-2xs)", fontVariantNumeric: "tabular-nums" }}>
        <span className="font-bold" style={{ fontFamily: "var(--nv-font-mono)", color: strongest ? "var(--nv-accent-green)" : "var(--nv-text-primary)" }}>
          {pct(o.pct, locale)} <DropBadge o={o} t={t} locale={locale} />
        </span>
        {out ? (
          <span className="font-semibold" style={{ color: out.color }}>
            <span aria-hidden="true">{out.icon}</span> {t.ht[out.key]}
          </span>
        ) : o.model_pct != null ? (
          <span title={t.ht.modelTip} style={{ color: "var(--nv-text-tertiary)" }}>
            {t.ht.model.replace("{pct}", locale === "en" ? fmtNum(o.model_pct, 1) : fmtNum(o.model_pct, 1).replace(".", ","))}
          </span>
        ) : null}
      </div>
    </div>
  );
}

function DropBadge({ o, t, locale }: { o: HtOption; t: Dictionary; locale: Locale }) {
  const drop = oddsDrop(o);
  if (drop == null || drop < ODDS_DROP_MIN) return null;
  return (
    <span className="font-semibold" style={{ color: "var(--nv-accent-amber)" }}
      title={t.ht.oddsDropTip.replace("{open}", fmtNum(o.open_odds, 2)).replace("{now}", fmtNum(o.odds, 2))}>
      <span aria-hidden="true">↓</span>{t.ht.oddsDrop.replace("{pct}", fmtPct(drop * 100, locale))}
    </span>
  );
}

function fmtPct(value: number, locale: Locale): string {
  const v = fmtNum(value, 0);
  return locale === "en" ? v : v.replace(".", ",");
}

export function HtMatchCard({ match, t, locale }: { match: HtMatch; t: Dictionary; locale: Locale }) {
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
          <span style={{ fontFamily: "var(--nv-font-mono)" }}>{pct(strongest.pct, locale)} · {fmtNum(strongest.odds, 2)}</span>
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
        {margin != null && <span>{t.ht.margin.replace("{pct}", locale === "en" ? fmtNum(margin, 1) : fmtNum(margin, 1).replace(".", ","))}</span>}
        {match.odds_at && <span>{t.ht.oddsTime.replace("{time}", formatTime(new Date(match.odds_at * 1000).toISOString()))}</span>}
        {match.expected_goals && (
          <span>{t.ht.expectedGoals}: <span style={{ fontFamily: "var(--nv-font-mono)" }}>{fmtNum(match.expected_goals.home, 2)} – {fmtNum(match.expected_goals.away, 2)}</span></span>
        )}
      </div>
    </article>
  );
}

function Chip({ href, active, children }: { href: string; active: boolean; children: React.ReactNode }) {
  return (
    <Link href={href} scroll={false} aria-current={active ? "true" : undefined} className="px-2.5 py-1 whitespace-nowrap"
      style={{
        fontSize: "var(--nv-text-xs)", borderRadius: "var(--nv-radius-full)",
        border: `1px solid ${active ? "var(--nv-accent-green)" : "var(--nv-border-subtle)"}`,
        color: active ? "var(--nv-accent-green)" : "var(--nv-text-secondary)",
        backgroundColor: active ? "var(--nv-accent-green-dim)" : "transparent",
      }}>
      {children}
    </Link>
  );
}

function FilterBar({ date, f, leagues, t }: { date: string; f: HtFilters; leagues: { name: string; count: number }[]; t: Dictionary }) {
  const h = t.ht;
  const sliderBase = filterHref(date, f, { min: 0 });
  return (
    <div className="space-y-2" aria-label={h.filters}>
      <div className="flex flex-wrap items-center gap-1.5">
        <Chip href={filterHref(date, f, { sort: "time" })} active={f.sort === "time"}>{h.sortTime}</Chip>
        <Chip href={filterHref(date, f, { sort: "prob" })} active={f.sort === "prob"}>{h.sortProb}</Chip>
        <span className="w-2" />
        <Chip href={filterHref(date, f, { win: "all" })} active={f.win === "all"}>{h.winAll}</Chip>
        <Chip href={filterHref(date, f, { win: "3h" })} active={f.win === "3h"}>{h.win3h}</Chip>
        <Chip href={filterHref(date, f, { win: "rest" })} active={f.win === "rest"}>{h.winRest}</Chip>
        <span className="w-2" />
        <Chip href={filterHref(date, f, { mkt: "all" })} active={f.mkt === "all"}>{h.mktAll}</Chip>
        <Chip href={filterHref(date, f, { mkt: "result" })} active={f.mkt === "result"}>{h.mktResult}</Chip>
        <Chip href={filterHref(date, f, { mkt: "ou" })} active={f.mkt === "ou"}>{h.mktOu}</Chip>
      </div>
      {leagues.length > 1 && (
        <div className="flex gap-1.5 overflow-x-auto pb-1">
          <Chip href={filterHref(date, f, { league: null })} active={f.league == null}>{h.allLeagues}</Chip>
          {leagues.map((l) => {
            const { flag, short } = leagueDisplay(null, l.name);
            return (
              <Chip key={l.name} href={filterHref(date, f, { league: l.name })} active={f.league === l.name}>
                <span aria-hidden="true">{flag}</span> {short} · {l.count}
              </Chip>
            );
          })}
        </div>
      )}
      <HtMinSlider key={f.min} value={f.min} baseHref={sliderBase} label={h.minProb} />
    </div>
  );
}

/** Kompakt satır: maç · en güçlü seçenek · oran · olasılık; tıklayınca tam kart (Sprint 94 K-2). */
function MatchRow({ match, f, t, locale }: { match: HtMatch; f: HtFilters; t: Dictionary; locale: Locale }) {
  const { flag, short } = leagueDisplay(null, match.league_name);
  const best = strongestOption(match, f.mkt);
  const outcome = best?.outcome ? OUTCOME[best.outcome] : null;
  const shown = { ...match, options: [...marketOptions(match, f.mkt)].sort((a, b) => b.pct - a.pct) };
  return (
    <details className="nv-card min-w-0 group">
      <summary className="flex flex-wrap items-center gap-x-3 gap-y-1 p-3 cursor-pointer" style={{ fontSize: "var(--nv-text-sm)" }}>
        <span style={{ fontFamily: "var(--nv-font-mono)", color: "var(--nv-text-tertiary)", fontSize: "var(--nv-text-xs)" }}>
          {match.kickoff_time ? formatTime(match.kickoff_time) : "—"}
        </span>
        <span aria-hidden="true">{flag}</span>
        <span className="min-w-0 truncate font-semibold" style={{ color: "var(--nv-text-primary)" }}>
          {match.home_team} - {match.away_team}
        </span>
        <span className="sr-only">{short}</span>
        <span className="flex-1" />
        {match.final_ht && (
          <span style={{ fontFamily: "var(--nv-font-mono)", color: "var(--nv-text-secondary)", fontSize: "var(--nv-text-xs)" }}>
            {t.ht.finalHt} {match.final_ht}
          </span>
        )}
        {match.odds_pending || !best ? (
          <span style={{ color: "var(--nv-text-tertiary)", fontSize: "var(--nv-text-xs)" }}>{t.ht.oddsPending}</span>
        ) : (
          <span className="flex items-center gap-2" style={{ fontSize: "var(--nv-text-xs)" }}>
            <b style={{ color: "var(--nv-accent-green)" }}>{optionLabel(best, t, locale)}</b>
            <span style={{ fontFamily: "var(--nv-font-mono)", color: "var(--nv-text-primary)" }}>{fmtNum(best.odds, 2)}</span>
            <span style={{ fontFamily: "var(--nv-font-mono)", color: "var(--nv-text-secondary)" }}>{pct(best.pct, locale)}</span>
            <DropBadge o={best} t={t} locale={locale} />
            {outcome && <span style={{ color: outcome.color }} title={t.ht[outcome.key]}><span aria-hidden="true">{outcome.icon}</span><span className="sr-only">{t.ht[outcome.key]}</span></span>}
          </span>
        )}
      </summary>
      {!match.odds_pending && shown.options.length > 0 && (
        <div className="px-1 pb-1"><HtMatchCard match={shown} t={t} locale={locale} /></div>
      )}
    </details>
  );
}

export async function HtMatchList({ date, locale, shadow, now, filters = DEFAULT_FILTERS }: {
  date: string; locale: Locale; shadow: boolean; /** epoch ms — sayfadan (süzgeçler "şimdi"ye göre) */ now: number;
  filters?: HtFilters;
}) {
  const t = getDictionary(locale);
  let matches: HtMatch[] = [];
  try {
    // Önbellekte eski biçimli yanıt kalmış olabilir → seçeneği olmayan maç gösterilmez (oranı gelmekte olan hariç)
    matches = ((await getHtStrategy(date, shadow)).matches ?? [])
      .filter((m) => Array.isArray(m.options) && (m.options.length > 0 || m.odds_pending === true));
  } catch {
    return <p className="nv-card p-4 m-4" style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-accent-red)" }}>{t.common.loadError}</p>;
  }
  if (matches.length === 0) {
    return <p className="nv-card p-6 m-4 text-center" style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-text-tertiary)" }}>{t.ht.empty}</p>;
  }
  const view = applyHtFilters(matches, filters, now);
  return (
    <div className="grid gap-3 px-[var(--nv-page-gutter)] py-4" style={{ maxWidth: "var(--nv-max-content)" }}>
      <FilterBar date={date} f={filters} leagues={view.leagues} t={t} />
      {view.upcoming.length === 0 && view.finished.length === 0 && (
        <p className="nv-card p-4 text-center" style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-text-tertiary)" }}>{t.ht.noMatchFilter}</p>
      )}
      {view.upcoming.map((m) => <MatchRow key={m.match_id} match={m} f={filters} t={t} locale={locale} />)}
      {view.finished.length > 0 && (
        <details className="space-y-2">
          <summary className="cursor-pointer py-1" style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-text-secondary)" }}>
            {t.ht.finishedSection.replace("{n}", String(view.finished.length))}
          </summary>
          <div className="grid gap-2 pt-2">
            {view.finished.map((m) => <MatchRow key={m.match_id} match={m} f={filters} t={t} locale={locale} />)}
          </div>
        </details>
      )}
    </div>
  );
}
