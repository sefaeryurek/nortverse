import { describe, expect, it } from "vitest";
import { localizeLabel } from "@/lib/label-i18n";

describe("localizeLabel", () => {
  it("leaves Turkish untouched", () => {
    expect(localizeLabel("Ev 1 fark", "tr")).toBe("Ev 1 fark");
  });
  it.each([
    ["Ev 1 fark", "Home by 1"],
    ["Dep 3+ fark", "Away by 3+"],
    ["KG Var", "BTTS Yes"],
    ["1 + Alt 2.5", "1 + Under 2.5"],
    ["Çifte Şans", "Double Chance"],
    ["Ev Üst 1.5", "Home Over 1.5"],
    ["Berabere", "Draw"],
    ["İY KG Yok", "HT BTTS No"],
  ])("%s → %s", (tr, en) => {
    expect(localizeLabel(tr, "en")).toBe(en);
  });
});
