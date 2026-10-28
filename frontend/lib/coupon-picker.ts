/**
 * Kupondaş maç seçicisi (Sprint 94 J10): arama + lige göre gruplama. Liste artık o günün bülteninin tamamı
 * (300+ maç, kupa dahil — J6); açılır kutu mobilde kullanılmıyordu.
 */
import type { CouponMatch } from "./api";

export interface PickerOptions {
  query: string;
  onlyAnalyzed: boolean;
  showStarted: boolean;
}

export interface PickerGroup {
  league: string | null;
  matches: CouponMatch[];
}

/** Büyük/küçük harf ve aksan duyarsız (İ/ı, ş, ü … "istanbul" = "İstanbul"). */
export function normalizeText(s: string): string {
  return s
    .replace(/İ/g, "i").replace(/I/g, "ı")
    .toLocaleLowerCase("tr")
    .replace(/ı/g, "i")
    .normalize("NFD").replace(/[̀-ͯ]/g, "");
}

export function isStarted(m: CouponMatch, now: number): boolean {
  if (m.started) return true;
  const t = m.kickoff_time ? Date.parse(m.kickoff_time) : NaN;
  return Number.isFinite(t) && now >= t;
}

export function matchesQuery(m: CouponMatch, query: string): boolean {
  const words = normalizeText(query).split(/\s+/).filter(Boolean);
  if (words.length === 0) return true;
  const hay = normalizeText(`${m.home_team} ${m.away_team} ${m.league_name ?? ""}`);
  return words.every((w) => hay.includes(w));
}

/** Süzülmüş maçlar lig gruplarında; gruplar ilk maçlarının saatine göre, analizli maçı olan lig önce değil — saat esas. */
export function groupCouponMatches(list: CouponMatch[], opts: PickerOptions, now: number): PickerGroup[] {
  const kick = (m: CouponMatch) => (m.kickoff_time ? Date.parse(m.kickoff_time) : Number.MAX_SAFE_INTEGER);
  const kept = list
    .filter((m) => (opts.showStarted || !isStarted(m, now)) && (!opts.onlyAnalyzed || m.analyzed) && matchesQuery(m, opts.query))
    .sort((a, b) => kick(a) - kick(b));
  const groups = new Map<string, PickerGroup>();
  for (const m of kept) {
    const key = m.league_name ?? "";
    if (!groups.has(key)) groups.set(key, { league: m.league_name, matches: [] });
    groups.get(key)!.matches.push(m);
  }
  return [...groups.values()];
}
