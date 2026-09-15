// Pazar çiftleri arası korelasyon düzeltme faktörleri.
// Poisson modelinden (λ_h=1.37, λ_a=1.12) hesaplanmış statik tablo.
// corr > 1.0 → pozitif korelasyon, corr < 1.0 → negatif korelasyon.

import TABLE from "./correlation-table.json";

const CORR_TABLE: Record<string, number> = TABLE;

function makeKey(outcomeA: string, outcomeB: string): string {
  return outcomeA < outcomeB ? `${outcomeA}|${outcomeB}` : `${outcomeB}|${outcomeA}`;
}

export function getCorrectionFactor(
  marketKeyA: string,
  selectionA: string,
  marketKeyB: string,
  selectionB: string,
): number {
  const key = makeKey(`${marketKeyA}:${selectionA}`, `${marketKeyB}:${selectionB}`);
  return CORR_TABLE[key] ?? 1.0;
}

export function computeJointProb(
  legs: Array<{ marketKey: string; selectionLabel: string; pct: number }>,
): number {
  if (legs.length === 0) return 1;
  if (legs.length === 1) return legs[0].pct / 100;

  let prob = 1;
  for (const leg of legs) {
    prob *= leg.pct / 100;
  }

  for (let i = 0; i < legs.length; i++) {
    for (let j = i + 1; j < legs.length; j++) {
      const corr = getCorrectionFactor(
        legs[i].marketKey,
        legs[i].selectionLabel,
        legs[j].marketKey,
        legs[j].selectionLabel,
      );
      prob *= corr;
    }
  }

  return Math.max(0, Math.min(1, prob));
}
