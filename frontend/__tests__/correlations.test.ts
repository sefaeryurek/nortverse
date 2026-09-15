import { describe, it, expect } from "vitest";
import { getCorrectionFactor, computeJointProb } from "@/lib/correlations";

describe("getCorrectionFactor", () => {
  it("KG Var + Üst 2.5 → pozitif korelasyon (>1.0)", () => {
    const f = getCorrectionFactor("kg", "KG Var", "ou_25", "Üst 2.5");
    expect(f).toBeGreaterThan(1.0);
  });

  it("KG Var + Alt 2.5 → negatif korelasyon (<1.0)", () => {
    const f = getCorrectionFactor("kg", "KG Var", "ou_25", "Alt 2.5");
    expect(f).toBeLessThan(1.0);
  });

  it("ters sıra aynı sonuç verir", () => {
    const f1 = getCorrectionFactor("kg", "KG Var", "ou_25", "Üst 2.5");
    const f2 = getCorrectionFactor("ou_25", "Üst 2.5", "kg", "KG Var");
    expect(f1).toBe(f2);
  });

  it("bilinmeyen çift → 1.0 (bağımsız varsayım)", () => {
    const f = getCorrectionFactor("unknown", "foo", "other", "bar");
    expect(f).toBe(1.0);
  });
});

describe("computeJointProb", () => {
  it("boş legs → 1", () => {
    expect(computeJointProb([])).toBe(1);
  });

  it("tek leg → pct/100", () => {
    expect(computeJointProb([{ marketKey: "result", selectionLabel: "1", pct: 80 }])).toBeCloseTo(0.8);
  });

  it("iki farklı market → düzeltme uygulanır", () => {
    const legs = [
      { marketKey: "kg", selectionLabel: "KG Var", pct: 60 },
      { marketKey: "ou_25", selectionLabel: "Üst 2.5", pct: 55 },
    ];
    const jp = computeJointProb(legs);
    const naive = 0.60 * 0.55;
    expect(jp).not.toBeCloseTo(naive, 3);
    expect(jp).toBeGreaterThan(naive);
  });

  it("negatif korelasyonlu çift → naive'den düşük", () => {
    const legs = [
      { marketKey: "kg", selectionLabel: "KG Var", pct: 60 },
      { marketKey: "ou_25", selectionLabel: "Alt 2.5", pct: 55 },
    ];
    const jp = computeJointProb(legs);
    const naive = 0.60 * 0.55;
    expect(jp).toBeLessThan(naive);
  });

  it("sonuç 0-1 aralığında kalır", () => {
    const legs = [
      { marketKey: "result", selectionLabel: "1", pct: 95 },
      { marketKey: "kg", selectionLabel: "KG Var", pct: 90 },
      { marketKey: "ou_25", selectionLabel: "Üst 2.5", pct: 85 },
    ];
    const jp = computeJointProb(legs);
    expect(jp).toBeGreaterThanOrEqual(0);
    expect(jp).toBeLessThanOrEqual(1);
  });

  it("bilinmeyen market → naive çarpım (corr=1.0)", () => {
    const legs = [
      { marketKey: "xxx", selectionLabel: "A", pct: 80 },
      { marketKey: "yyy", selectionLabel: "B", pct: 50 },
    ];
    const jp = computeJointProb(legs);
    expect(jp).toBeCloseTo(0.4, 5);
  });
});
