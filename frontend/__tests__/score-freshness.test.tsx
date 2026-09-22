import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import LiveMatchBadge from "@/components/LiveMatchBadge";
import { isLiveScoreStale } from "@/lib/score-freshness";

afterEach(() => { cleanup(); vi.useRealTimers(); });

it("treats unknown and two-minute-old live scores as stale", () => {
  const now = Date.parse("2026-09-22T08:00:00Z");
  expect(isLiveScoreStale(null, now)).toBe(true);
  expect(isLiveScoreStale("2026-09-22T07:59:59Z", now)).toBe(false);
  expect(isLiveScoreStale("2026-09-22T07:58:00Z", now)).toBe(true);
});

it("relabels an open live badge when its score stops being fresh", () => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-09-22T08:00:00Z"));
  render(<LiveMatchBadge home={1} away={2} minute="67"
    checkedAt="2026-09-22T07:59:00Z" checkedLabel="10:59" initialStale={false} />);
  expect(screen.getByLabelText("Canlı skor")).toBeDefined();

  act(() => { vi.advanceTimersByTime(60_000); });
  expect(screen.getByLabelText("Son görülen skor; güncel veri bekleniyor")).toBeDefined();
  expect(screen.getByText("Son skor")).toBeDefined();
});
