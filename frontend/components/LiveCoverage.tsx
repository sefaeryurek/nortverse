import { getLiveCoverage } from "@/lib/api";
import type { PerformanceScope } from "@/lib/api";
import { formatTime } from "@/lib/dates";
import { fmtNum } from "@/lib/format";
import type { Dictionary } from "@/lib/i18n";
import { leagueDisplay } from "@/lib/leagues";

/**
 * Canlı kapsama karnesi (Sprint 94 C4): devre arasına gelen izlenen maçların kaçında canlı kayıt düştü.
 * Karneler sadece kaydedilen maçları anlatır — düşük kapsama karneyi seçici yapabilir. Sunucu bileşeni.
 */
export default async function LiveCoverage({ t, scope, days = 7 }: { t: Dictionary; scope: PerformanceScope; days?: number }) {
  const p = t.evaluation.perf;
  let data;
  try {
    data = await getLiveCoverage(days, scope);
  } catch {
    return null; // kapsama yardımcı bilgi — yüklenemezse sayfa yine çalışır
  }
  if (!data || typeof data.reached_ht !== "number" || data.reached_ht === 0) return null;
  const pct = data.pct ?? 0;
  const color = pct >= 90 ? "var(--nv-accent-green)" : pct >= 75 ? "var(--nv-accent-amber)" : "var(--nv-accent-red)";
  const missed = Array.isArray(data.missed) ? data.missed : [];
  return (
    <section className="nv-card p-3 space-y-2" aria-label={p.coverageTitle.replace("{days}", String(days))}>
      <h3 className="font-bold" style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-text-primary)" }}>
        {p.coverageTitle.replace("{days}", String(days))}
      </h3>
      <p style={{ fontSize: "var(--nv-text-sm)", color: "var(--nv-text-secondary)" }}>
        <span className="font-bold" style={{ color }}>{p.coverageLine
          .replace("{n}", String(data.reached_ht)).replace("{k}", String(data.frozen))
          .replace("{pct}", fmtNum(data.pct, 1))}</span>
      </p>
      <p style={{ fontSize: "var(--nv-text-2xs)", color: "var(--nv-text-tertiary)" }}>{p.coverageNote}</p>
      {missed.length > 0 && (
        <details>
          <summary className="cursor-pointer" style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-secondary)" }}>
            {p.coverageMissed} ({missed.length})
          </summary>
          <ul className="mt-1 space-y-0.5">
            {missed.map((m) => (
              <li key={m.match_id} className="flex gap-2" style={{ fontSize: "var(--nv-text-xs)", color: "var(--nv-text-tertiary)" }}>
                <span style={{ fontFamily: "var(--nv-font-mono)" }}>{formatTime(m.kickoff_time)}</span>
                <span aria-hidden="true">{leagueDisplay(null, m.league_name).flag}</span>
                <span className="truncate" style={{ color: "var(--nv-text-secondary)" }}>{m.home_team} - {m.away_team}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
