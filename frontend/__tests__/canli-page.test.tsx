import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { LocaleProvider } from "@/lib/locale-context";
import type { LiveHTMatch, LivePrediction } from "@/lib/api";
import type { UseLiveWsResult } from "@/lib/use-live-ws";
import { minuteOrder } from "@/lib/live-order";

let wsState: UseLiveWsResult = { matches: [], status: "connected", lastUpdate: null };
vi.mock("@/lib/use-live-ws", () => ({ useLiveWs: () => wsState }));

const getLiveHTMatches = vi.fn<() => Promise<LiveHTMatch[]>>(() => Promise.resolve([]));
const getLivePrediction = vi.fn();
vi.mock("@/lib/api", () => ({
  getLiveHTMatches: () => getLiveHTMatches(),
  getLivePrediction: (...args: unknown[]) => getLivePrediction(...args),
}));
vi.mock("next/link", () => ({ default: ({ children }: { children: React.ReactNode }) => <>{children}</> }));

import CanliPage from "@/app/canli/page";

afterEach(() => { cleanup(); vi.clearAllMocks(); });

const prediction: LivePrediction = {
  rule_version: "live-ms-v1",
  ht: { home: 1, away: 0 },
  ms: {
    probs: { "1": 0.72, X: 0.19, "2": 0.09 }, pick: "1", prob: 0.72, tier: "high", n: 640,
    cond_level: "score", ht_baseline: { probs: { "1": 0.7, X: 0.2, "2": 0.1 }, pick: "1", prob: 0.7 },
  },
  over25: { applicable: true, pick: "under", prob: 0.55, n: 640, tier: "medium" },
  btts: { applicable: false, reason: "already_both" },
  frozen: true, frozen_at: "2026-10-18T15:47:00+00:00",
};

function match(id: string, minute: string | null, extra: Partial<LiveHTMatch> = {}): LiveHTMatch {
  return {
    match_id: id, home_team: `Ev ${id}`, away_team: `Dep ${id}`, ht_home: 1, ht_away: 0,
    live_home: 1, live_away: 0, live_minute: minute, phase: minute === "HT" ? "ht" : "2h",
    league_name: "English Premier League", kickoff_time: null, prediction, ...extra,
  };
}

function ui() {
  return <LocaleProvider initial="tr"><CanliPage /></LocaleProvider>;
}

describe("Canlı sayfa", () => {
  it("renders the frozen model prediction from WebSocket data", async () => {
    wsState = { matches: [match("1", "HT")], status: "connected", lastUpdate: new Date() };
    render(ui());
    expect(screen.getByText("Ev 1")).toBeTruthy();
    expect(screen.getByText(/Yüksek güven/)).toBeTruthy();
    expect(screen.getByText(/Kaydedildi/)).toBeTruthy();
    expect(screen.getByText(/İY tabanı: 1 %70.0/)).toBeTruthy();
    expect(screen.getByText(/MS 2.5 Alt/)).toBeTruthy();
    expect(screen.queryByText(/KG Var|KG Yok/)).toBeNull();
    expect(getLiveHTMatches).not.toHaveBeenCalled();
  });

  it("falls back to REST when WebSocket is unavailable", async () => {
    wsState = { matches: [], status: "fallback", lastUpdate: null };
    getLiveHTMatches.mockResolvedValueOnce([match("7", "60")]);
    render(ui());
    expect(await screen.findByText("Ev 7")).toBeTruthy();
  });

  it("loads secondary archive summaries only when expanded", async () => {
    wsState = { matches: [match("3", "HT")], status: "connected", lastUpdate: new Date() };
    getLivePrediction.mockResolvedValueOnce({
      ...prediction,
      archives: [
        { archive: "A1", n: 12, sufficient: true, probs: { "1": 0.5, X: 0.25, "2": 0.25 } },
        {
          archive: "A3", n: 2, sufficient: false, probs: { "1": 1, X: 0, "2": 0 },
          matches: [
            { match_id: "91", home_team: "Ev FK", away_team: "Dep SK", kickoff_time: "2025-03-01T15:00:00Z",
              ht: "0-1", ft: "2-1", result: "1", similarity: 0.981 },
          ],
        },
      ],
    });
    render(ui());
    expect(getLivePrediction).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText("Arşiv detayı"));
    expect(getLivePrediction).toHaveBeenCalledWith("3", true);
    // Az maçlı arşiv de yüzdesiyle gösterilir ("yetersiz örneklem" yok).
    expect(await screen.findByText("Maçları göster (1)")).toBeTruthy();
    expect(screen.queryByText("yetersiz örneklem")).toBeNull();
    fireEvent.click(screen.getByText("Maçları göster (1)"));
    expect(screen.getByText("Ev FK - Dep SK")).toBeTruthy();
    expect(screen.getByText("MS 2-1")).toBeTruthy();
    expect(screen.getByText("%98.1")).toBeTruthy();
  });
});

describe("minuteOrder", () => {
  it("puts half-time between first and second half, unknown second half last", () => {
    const order = [match("a", "67"), match("b", "HT"), match("c", null), match("d", "46")]
      .sort((x, y) => minuteOrder(x) - minuteOrder(y)).map((m) => m.match_id);
    expect(order).toEqual(["b", "d", "a", "c"]);
  });
});
