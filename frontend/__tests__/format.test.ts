import { describe, expect, it } from "vitest";
import { fairOdds } from "@/lib/format";

describe("fairOdds", () => {
  it("converts probability to 1/p odds with locale decimal", () => {
    expect(fairOdds(92, "tr")).toBe("1,09");
    expect(fairOdds(50, "en")).toBe("2.00");
    expect(fairOdds(100, "en")).toBe("1.00");
  });

  it("returns null for missing or out-of-range values", () => {
    expect(fairOdds(null, "tr")).toBeNull();
    expect(fairOdds(undefined, "tr")).toBeNull();
    expect(fairOdds(0, "tr")).toBeNull();
    expect(fairOdds(101, "tr")).toBeNull();
    expect(fairOdds(Number.NaN, "tr")).toBeNull();
  });
});
