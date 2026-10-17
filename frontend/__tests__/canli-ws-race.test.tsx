import { afterEach, expect, it, vi } from "vitest";
import { act, cleanup, render, screen } from "@testing-library/react";
import { LocaleProvider } from "@/lib/locale-context";
import type { LiveHTMatch, MatchedMatchesResponse } from "@/lib/api";
import type { UseLiveWsResult } from "@/lib/use-live-ws";

let wsState: UseLiveWsResult = { matches: [], status: "connected", lastUpdate: null };
vi.mock("@/lib/use-live-ws", () => ({ useLiveWs: () => wsState }));

let resolveMatched: ((v: MatchedMatchesResponse) => void) | null = null;
vi.mock("@/lib/api", () => ({
  getLiveHTMatches: vi.fn(() => Promise.resolve([])),
  getMatchedMatches: vi.fn(() => new Promise<MatchedMatchesResponse>((r) => { resolveMatched = r; })),
}));
vi.mock("next/link", () => ({ default: ({ children }: { children: React.ReactNode }) => <>{children}</> }));

import CanliPage from "@/app/canli/page";

afterEach(() => { cleanup(); resolveMatched = null; });

const match: LiveHTMatch = {
  match_id: "1", home_team: "Ev Takımı", away_team: "Dep Takımı", ht_home: 1, ht_away: 0,
  live_home: 1, live_away: 0, live_minute: "HT", league_name: "English Premier League", kickoff_time: null,
};
const archiveRow = { match_id: "9", home_team: "a", away_team: "b", league_code: "x", ht: "1-0", h2: "1-0", ft: "2-0" };

function ui() {
  return <LocaleProvider initial="tr"><CanliPage /></LocaleProvider>;
}

it("does not stay stuck when a same-id broadcast arrives during validation", async () => {
  wsState = { matches: [match], status: "connected", lastUpdate: new Date(1) };
  const view = render(ui());
  // Doğrulama sürerken aynı maçlarla yeni yayın (yeni dizi + yeni zaman damgası)
  wsState = { matches: [{ ...match }], status: "connected", lastUpdate: new Date(2) };
  view.rerender(ui());
  await act(async () => {
    resolveMatched?.({ archive_b: [archiveRow], archive_c: [], archive_d: [] });
  });
  expect(await screen.findByText("Ev Takımı")).toBeTruthy();
});
