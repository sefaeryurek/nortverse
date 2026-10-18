import { describe, expect, it } from "vitest";
import { pickBacktestRun } from "@/components/PerformancePanel";
import type { BacktestRun } from "@/lib/api";

function run(id: number, strategy: BacktestRun["strategy"], current: boolean): BacktestRun {
  return {
    id, strategy, current, rule_version: "v", params: {}, notes: null, n: 10,
    date_from: "2023-07-01T00:00:00+03:00", date_to: "2026-10-18T00:00:00+03:00", created_at: "2026-10-18T00:00:00Z",
  };
}

describe("pickBacktestRun", () => {
  const runs = [run(2, "live_ht", false), run(3, "live_ht", true), run(4, "live_ht", false), run(5, "top_pick", true)];

  it("defaults to the latest run made with today's settings, live first", () => {
    expect(pickBacktestRun(runs, null)?.id).toBe(3);
  });

  it("honours a valid requested run, even an experiment", () => {
    expect(pickBacktestRun(runs, 4)?.id).toBe(4);
  });

  it("falls back when the requested run does not exist", () => {
    expect(pickBacktestRun(runs, 999)?.id).toBe(3);
    expect(pickBacktestRun([], null)).toBeNull();
  });
});
