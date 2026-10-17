import type { LiveHTMatch } from "./api";

/** Canlı maç sıralaması: devre arası (45.5) dakikaya göre sayısal; dakikası olmayan 2. yarı sonda. */
export function minuteOrder(match: Pick<LiveHTMatch, "live_minute" | "phase">): number {
  if (match.live_minute === "HT" || match.phase === "ht") return 45.5;
  const [base, extra] = (match.live_minute ?? "").split("+");
  const n = Number.parseInt(base, 10);
  if (Number.isNaN(n)) return match.phase === "2h" ? 90 : 999;
  return n + (Number.parseInt(extra ?? "0", 10) || 0) / 100;
}
