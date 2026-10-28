import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import type { HtMatch } from "@/lib/api";

// İY oran panosu (Sprint 94 M3): sıralı kartlar, en güçlü seçenek, eski biçimli yanıtta çökmeme, hata/boş ayrımı
const api = vi.hoisted(() => ({ getHtStrategy: vi.fn() }));
vi.mock("@/lib/api", () => api);
vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => <a href={href}>{children}</a>,
}));

import { HtMatchList } from "@/components/HtBoard";

afterEach(() => { cleanup(); vi.clearAllMocks(); });

const match = (id: string, home: string, opts: Partial<HtMatch> = {}): HtMatch => ({
  match_id: id, home_team: home, away_team: `${home} Rakip`, league_name: "English Premier League",
  kickoff_time: "2026-10-28T19:00:00+00:00", shadow: false, final_ht: null, odds_at: null,
  expected_goals: { home: 0.7, away: 0.4 },
  options: [
    { market: "result", selection: "X", line: null, odds: 2.05, pct: 46.2, margin_pct: 5.4, model_pct: 44.1 },
    { market: "result", selection: "1", line: null, odds: 2.7, pct: 35.1, margin_pct: 5.4, model_pct: 38.0 },
    { market: "ou", selection: "under", line: 1.0, odds: 1.85, pct: 51.0, margin_pct: 4.2, model_pct: null },
  ],
  ...opts,
});

async function renderList() {
  render(await HtMatchList({ date: "2026-10-28", locale: "tr", shadow: false }));
}

it("renders match cards in server order with odds", async () => {
  api.getHtStrategy.mockResolvedValue({ date: "2026-10-28", matches: [match("1", "Arsenal"), match("2", "Chelsea")] });
  await renderList();
  const text = document.body.textContent ?? "";
  expect(text.indexOf("Arsenal")).toBeLessThan(text.indexOf("Chelsea"));
  expect(screen.getAllByText("2.05").length).toBeGreaterThan(0);
});

it("skips matches whose options are missing (old cached shape) instead of crashing", async () => {
  api.getHtStrategy.mockResolvedValue({ date: "2026-10-28", matches: [
    match("1", "Arsenal"), { ...match("2", "Eski"), options: undefined as unknown as HtMatch["options"] }] });
  await renderList();
  expect(screen.queryByText(/Eski/)).toBeNull();
  expect(screen.getAllByText(/Arsenal/).length).toBeGreaterThan(0);
});

it("survives missing expected goals and model probability", async () => {
  api.getHtStrategy.mockResolvedValue({ date: "2026-10-28", matches: [
    match("1", "Arsenal", { expected_goals: null }),
    match("2", "Chelsea", { options: [{ market: "result", selection: "1", line: null, odds: 1.9, pct: 50, margin_pct: 5, model_pct: null }] }),
  ] });
  await renderList();
  expect(screen.getAllByText(/Chelsea/).length).toBeGreaterThan(0);
});

it("shows an error card on failure and an empty message when there are no matches", async () => {
  api.getHtStrategy.mockRejectedValueOnce(new Error("kapalı"));
  await renderList();
  expect(screen.getByText("Veriler şu anda yüklenemiyor", { exact: false })).toBeTruthy();
  cleanup();
  api.getHtStrategy.mockResolvedValueOnce({ date: "2026-10-28", matches: [] });
  await renderList();
  expect(document.body.textContent).not.toContain("yüklenemiyor");
  expect(document.body.textContent?.length).toBeGreaterThan(0);  // boş durum mesajı
});
