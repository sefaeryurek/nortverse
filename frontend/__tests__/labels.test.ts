import { describe, expect, it } from "vitest";
import { periodLabels } from "@/lib/labels";
import type { Period } from "@/lib/labels";

describe("periodLabels", () => {
  it("returns İY prefix for ht period", () => {
    const labels = periodLabels("ht");
    expect(labels.prefix).toBe("İY");
  });

  it("returns 2Y prefix for h2 period", () => {
    const labels = periodLabels("h2");
    expect(labels.prefix).toBe("2Y");
  });

  it("returns MS prefix for ft period", () => {
    const labels = periodLabels("ft");
    expect(labels.prefix).toBe("MS");
  });

  it("ht labels reference 1. Yarı", () => {
    const labels = periodLabels("ht");
    expect(labels.sonuc).toContain("1. Yarı");
    expect(labels.hnd).toContain("1. Yarı");
    expect(labels.fark).toContain("1. Yarı");
  });

  it("h2 labels reference 2. Yarı", () => {
    const labels = periodLabels("h2");
    expect(labels.sonuc).toContain("2. Yarı");
    expect(labels.hnd).toContain("2. Yarı");
    expect(labels.fark).toContain("2. Yarı");
  });

  it("ft labels do not reference specific yarı", () => {
    const labels = periodLabels("ft");
    expect(labels.sonuc).toBe("Maç Sonucu");
    expect(labels.fark).not.toContain("Yarı");
  });

  it("all periods return all required keys", () => {
    const keys = ["prefix", "sonuc", "hnd", "combo15", "combo25", "comboKg", "fark", "taraf", "toplamGol"];
    for (const period of ["ht", "h2", "ft"] as Period[]) {
      const labels = periodLabels(period);
      for (const key of keys) {
        expect(labels).toHaveProperty(key);
        expect((labels as Record<string, string>)[key]).toBeTruthy();
      }
    }
  });

  it("ft comboKg mentions Karşılıklı Gol", () => {
    const labels = periodLabels("ft");
    expect(labels.comboKg).toContain("Karşılıklı Gol");
  });
});
