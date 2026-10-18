import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { LocaleProvider } from "@/lib/locale-context";
import type { LiveArchiveView, LiveHTMatch } from "@/lib/api";
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

const view: LiveArchiveView = {
  rule_version: "live-arch-v1", ht: { home: 1, away: 0 }, threshold_pct: 85, risky_below_n: 5,
  sources: [
    { archive: "a1", label: "A1", n: 12, risky: false, cells: [
      { period: "ft", market: "dc", selection: "1X", pct: 91.7, options: { "1X": 91.7, X2: 25, "12": 83.3 } },
      { period: "ft", market: "result", selection: "1", pct: 66.7, options: { "1": 66.7, X: 25, "2": 8.3 } },
    ] },
    { archive: "a2", label: "A2", n: 0, risky: false, cells: [] },
    { archive: "a3", label: "A3", n: 2, risky: true, cells: [
      { period: "h2", market: "ou_05", selection: "over", pct: 100, options: { under: 0, over: 100 } },
    ] },
    { archive: "genel", label: "Genel", n: 13, risky: false, cells: [
      { period: "ft", market: "dc", selection: "1X", pct: 92.3, options: { "1X": 92.3, X2: 23.1, "12": 84.6 } },
    ] },
  ],
  highlights: [
    { period: "ft", market: "dc", selection: "1X", pct: 92.3, archive: "genel", label: "Genel", n: 13, risky: false },
    { period: "ft", market: "dc", selection: "1X", pct: 91.7, archive: "a1", label: "A1", n: 12, risky: false },
    { period: "h2", market: "ou_05", selection: "over", pct: 100, archive: "a3", label: "A3", n: 2, risky: true,
      historical: { pct: 79.5, n: 2635, bucket: "2-4", pooled: false } },
  ],
};

function match(id: string, minute: string | null, extra: Partial<LiveHTMatch> = {}): LiveHTMatch {
  return {
    match_id: id, home_team: `Ev ${id}`, away_team: `Dep ${id}`, ht_home: 1, ht_away: 0,
    live_home: 1, live_away: 0, live_minute: minute, phase: minute === "HT" ? "ht" : "2h",
    league_name: "English Premier League", kickoff_time: null,
    frozen: true, frozen_at: "2026-10-18T15:47:00+00:00", archive_view: view, ...extra,
  };
}

function ui() {
  return <LocaleProvider initial="tr"><CanliPage /></LocaleProvider>;
}

describe("Canlı sayfa", () => {
  it("shows archive highlights on top, grouped, with a risky mark — no main model prediction", async () => {
    wsState = { matches: [match("1", "HT")], status: "connected", lastUpdate: new Date() };
    render(ui());
    expect(screen.getByText("Ev 1")).toBeTruthy();
    expect(screen.getByText("Öne çıkanlar (%85+)")).toBeTruthy();
    expect(screen.getAllByText("MS ÇŞ").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Riskli").length).toBe(1);          // sadece A3 (2 maç)
    expect(screen.getByText(/Kaydedildi/)).toBeTruthy();
    expect(screen.queryByText(/MS Tahmini|İY tabanı/)).toBeNull();
    expect(screen.getByText("geçmiş %80")).toBeTruthy();       // 2 maçlık %100 işaret geçmişte %79.5 tutmuş
    expect(getLiveHTMatches).not.toHaveBeenCalled();
  });

  it("states when no rate reaches the threshold", () => {
    wsState = { matches: [match("2", "HT", { archive_view: { ...view, highlights: [] } })], status: "connected", lastUpdate: new Date() };
    render(ui());
    expect(screen.getByText("%85 üzeri oran yok")).toBeTruthy();
  });

  it("falls back to REST when WebSocket is unavailable", async () => {
    wsState = { matches: [], status: "fallback", lastUpdate: null };
    getLiveHTMatches.mockResolvedValueOnce([match("7", "60")]);
    render(ui());
    expect(await screen.findByText("Ev 7")).toBeTruthy();
  });

  it("explains unanalysed matches instead of offering a detail request that would fail", () => {
    wsState = { matches: [match("4", "60", { archive_view: null, frozen: false })], status: "connected", lastUpdate: new Date() };
    render(ui());
    expect(screen.getByText(/başlamadan analiz edilmemiş/)).toBeTruthy();
    expect(screen.queryByText("Arşiv detayı")).toBeNull();
    expect(screen.queryByText("Canlı veri alınamadı.")).toBeNull();
  });

  it("loads matched game lists only when expanded", async () => {
    wsState = { matches: [match("3", "HT")], status: "connected", lastUpdate: new Date() };
    getLivePrediction.mockResolvedValueOnce({
      frozen: true, frozen_at: null,
      archive_view: { ...view, sources: view.sources.map((s) => s.archive === "a3" ? { ...s, matches: [
        { match_id: "91", home_team: "Ev FK", away_team: "Dep SK", kickoff_time: "2025-03-01T15:00:00Z",
          ht: "1-0", ft: "2-1", result: "1", similarity: 0.981 },
      ] } : { ...s, matches: [] }) },
    });
    render(ui());
    expect(getLivePrediction).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText("Arşiv detayı"));
    expect(getLivePrediction).toHaveBeenCalledWith("3", true);
    expect(await screen.findByText("Ev FK - Dep SK")).toBeTruthy();
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
